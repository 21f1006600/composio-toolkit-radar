import json
import sqlite3

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from src.config import DATABASE_PATH
from src.schemas import AppInput, ResearchResult


class ResearchStorage:

    def __init__(
        self,
        database_path: str | Path = DATABASE_PATH,
    ):

        self.database_path = Path(database_path)

        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.initialize_database()

    # ======================================
    # Database connection
    # ======================================

    @contextmanager
    def connection(self):

        conn = sqlite3.connect(
            self.database_path,
            timeout=30,
        )

        conn.row_factory = sqlite3.Row

        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 30000")

        try:
            yield conn
            conn.commit()

        except Exception:
            conn.rollback()
            raise

        finally:
            conn.close()

    @staticmethod
    def now():

        return datetime.now(
            timezone.utc
        ).isoformat()

    # ======================================
    # Database initialization
    # ======================================

    def initialize_database(self):

        with self.connection() as conn:

            conn.execute("PRAGMA journal_mode = WAL")

            conn.executescript("""
                CREATE TABLE IF NOT EXISTS applications (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    website_hint TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS research_results (
                    app_id INTEGER PRIMARY KEY,

                    status TEXT NOT NULL DEFAULT 'pending'
                        CHECK (
                            status IN (
                                'pending',
                                'running',
                                'completed',
                                'failed'
                            )
                        ),

                    result_json TEXT,
                    verification_json TEXT,

                    selected_attempt INTEGER,
                    total_attempts INTEGER DEFAULT 0,

                    support_rate REAL,
                    execution_time REAL,

                    error_message TEXT,

                    started_at TEXT,
                    completed_at TEXT,
                    updated_at TEXT NOT NULL,

                    FOREIGN KEY (app_id)
                        REFERENCES applications(id)
                );

                CREATE TABLE IF NOT EXISTS research_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    app_id INTEGER NOT NULL,
                    attempt_number INTEGER NOT NULL,

                    research_json TEXT,
                    verification_json TEXT,
                    score_json TEXT,

                    document_count INTEGER,
                    error_message TEXT,

                    created_at TEXT NOT NULL,

                    FOREIGN KEY (app_id)
                        REFERENCES applications(id),

                    UNIQUE (app_id, attempt_number)
                );

                CREATE INDEX IF NOT EXISTS idx_research_status
                    ON research_results(status);

                CREATE INDEX IF NOT EXISTS idx_app_category
                    ON applications(category);
            """)

    # ======================================
    # Register applications
    # ======================================

    def register_apps(
        self,
        apps: list[AppInput],
    ):

        with self.connection() as conn:

            for app in apps:

                conn.execute(
                    """
                    INSERT INTO applications (
                        id,
                        name,
                        category,
                        website_hint
                    )
                    VALUES (?, ?, ?, ?)

                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        category = excluded.category,
                        website_hint = excluded.website_hint
                    """,
                    (
                        app.id,
                        app.name,
                        app.category,
                        app.website_hint,
                    ),
                )

                conn.execute(
                    """
                    INSERT OR IGNORE INTO research_results (
                        app_id,
                        status,
                        updated_at
                    )
                    VALUES (?, 'pending', ?)
                    """,
                    (
                        app.id,
                        self.now(),
                    ),
                )

    # ======================================
    # Application status
    # ======================================

    def get_status(self, app_id: int):

        with self.connection() as conn:

            row = conn.execute(
                """
                SELECT status
                FROM research_results
                WHERE app_id = ?
                """,
                (app_id,),
            ).fetchone()

        return row["status"] if row else None

    def mark_running(self, app_id: int):

        with self.connection() as conn:

            conn.execute(
                """
                UPDATE research_results
                SET
                    status = 'running',
                    started_at = ?,
                    updated_at = ?,
                    completed_at = NULL,
                    error_message = NULL
                WHERE app_id = ?
                """,
                (
                    self.now(),
                    self.now(),
                    app_id,
                ),
            )

    def mark_failed(
        self,
        app_id: int,
        error_message: str,
    ):

        with self.connection() as conn:

            conn.execute(
                """
                UPDATE research_results
                SET
                    status = 'failed',
                    error_message = ?,
                    updated_at = ?
                WHERE app_id = ?
                """,
                (
                    error_message,
                    self.now(),
                    app_id,
                ),
            )

    # ======================================
    # Save complete pipeline output
    # ======================================

    def save_pipeline_output(
        self,
        app_id: int,
        output: dict,
    ):

        result = ResearchResult.model_validate(
            output["final_result"]
        )

        if result.app.id != app_id:
            raise ValueError("Application ID mismatch.")

        feedback = output.get(
            "final_verification"
        ) or {}

        history = output.get("history", [])

        selected_attempt = output.get(
            "selected_attempt"
        )

        if (
            selected_attempt is None
            or not result.claims
        ):

            status = "failed"

            error_message = "; ".join(
                output.get("pipeline_errors", [])
            ) or "No publishable research produced."

        else:

            status = "completed"
            error_message = None

        timestamp = self.now()

        with self.connection() as conn:

            # Replace the previous run's attempt history.
            # All attempts from the current run are retained.

            conn.execute(
                """
                DELETE FROM research_attempts
                WHERE app_id = ?
                """,
                (app_id,),
            )

            for attempt in history:

                conn.execute(
                    """
                    INSERT INTO research_attempts (
                        app_id,
                        attempt_number,
                        research_json,
                        verification_json,
                        score_json,
                        document_count,
                        error_message,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        app_id,
                        attempt["attempt"],
                        json.dumps(
                            attempt.get("research"),
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            attempt.get("verification"),
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            attempt.get("score")
                        ),
                        attempt.get("documents"),
                        attempt.get("error"),
                        timestamp,
                    ),
                )

            conn.execute(
                """
                UPDATE research_results
                SET
                    status = ?,
                    result_json = ?,
                    verification_json = ?,
                    selected_attempt = ?,
                    total_attempts = ?,
                    support_rate = ?,
                    execution_time = ?,
                    error_message = ?,
                    completed_at = ?,
                    updated_at = ?
                WHERE app_id = ?
                """,
                (
                    status,
                    result.model_dump_json(),
                    json.dumps(
                        feedback,
                        ensure_ascii=False,
                    ),
                    selected_attempt,
                    output.get("attempts", 0),
                    feedback.get("support_rate"),
                    output.get("execution_time"),
                    error_message,
                    timestamp if status == "completed"
                    else None,
                    timestamp,
                    app_id,
                ),
            )

        return status

    # ======================================
    # Resume incomplete research
    # ======================================

    def get_pending_apps(
        self,
        retry_failed: bool = False,
        limit: int | None = None,
    ) -> list[AppInput]:

        statuses = ["pending", "running"]

        if retry_failed:
            statuses.append("failed")

        placeholders = ",".join(
            "?" for _ in statuses
        )

        query = f"""
            SELECT
                a.id,
                a.name,
                a.category,
                a.website_hint

            FROM applications a

            JOIN research_results r
                ON a.id = r.app_id

            WHERE r.status IN ({placeholders})

            ORDER BY a.id
        """

        parameters = list(statuses)

        if limit is not None:

            if limit < 1:
                raise ValueError(
                    "Limit must be positive."
                )

            query += " LIMIT ?"
            parameters.append(limit)

        with self.connection() as conn:

            rows = conn.execute(
                query,
                parameters,
            ).fetchall()

        return [
            AppInput.model_validate(dict(row))
            for row in rows
        ]

    # ======================================
    # Progress tracking
    # ======================================

    def get_progress(self):

        progress = {
            "pending": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
        }

        with self.connection() as conn:

            rows = conn.execute("""
                SELECT status, COUNT(*) AS count
                FROM research_results
                GROUP BY status
            """).fetchall()

        for row in rows:

            progress[row["status"]] = row["count"]

        progress["total"] = sum(
            progress.values()
        )

        progress["completion_rate"] = (
            round(
                progress["completed"]
                / progress["total"] * 100,
                2,
            )
            if progress["total"]
            else 0
        )

        return progress

    # ======================================
    # Retrieve completed research
    # ======================================

    def get_completed_results(self):

        with self.connection() as conn:

            rows = conn.execute("""
                SELECT
                    app_id,
                    result_json,
                    verification_json,
                    selected_attempt,
                    total_attempts,
                    support_rate,
                    execution_time

                FROM research_results

                WHERE status = 'completed'

                ORDER BY app_id
            """).fetchall()

        results = []

        for row in rows:

            item = dict(row)

            item["result"] = json.loads(
                item.pop("result_json")
            )

            item["verification"] = json.loads(
                item.pop("verification_json")
                or "{}"
            )

            results.append(item)

        return results

    # ======================================
    # Retrieve research audit
    # ======================================

    def get_attempt_history(self, app_id: int):

        with self.connection() as conn:

            rows = conn.execute(
                """
                SELECT *
                FROM research_attempts
                WHERE app_id = ?
                ORDER BY attempt_number
                """,
                (app_id,),
            ).fetchall()

        history = []

        for row in rows:

            item = dict(row)

            for field in (
                "research_json",
                "verification_json",
                "score_json",
            ):

                item[field.removesuffix("_json")] = (
                    json.loads(item.pop(field) or "null")
                )

            history.append(item)

        return history