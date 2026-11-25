from src.storage import ResearchStorage

from src.schemas import (
    AppInput,
    ResearchResult,
    Claim,
    Evidence,
    VerificationStatus,
)

from datetime import datetime, timezone


def make_app(app_id=1):

    return AppInput(
        id=app_id,
        name=f"Example App {app_id}",
        category="CRM",
        website_hint="https://example.com",
    )


def make_output(app):

    result = ResearchResult(
        app=app,
        description="Example CRM application.",
        claims=[
            Claim(
                field="description",
                statement="Example CRM application.",
                verification_status=(
                    VerificationStatus.SUPPORTED
                ),
                evidence=[
                    Evidence(
                        source_url=(
                            "https://example.com/docs"
                        ),
                        excerpt="Example CRM application.",
                        retrieved_at=datetime.now(
                            timezone.utc
                        ),
                        official_source=True,
                    )
                ],
            )
        ],
    )

    return {
        "final_result": result.model_dump(
            mode="json"
        ),
        "final_verification": {
            "support_rate": 1.0,
            "total_claims": 1,
            "supported_claims": 1,
        },
        "selected_attempt": 1,
        "attempts": 1,
        "execution_time": 10.5,
        "pipeline_errors": [],
        "history": [
            {
                "attempt": 1,
                "research": result.model_dump(
                    mode="json"
                ),
                "verification": {
                    "support_rate": 1.0
                },
                "documents": 3,
                "score": [1, 1.0, 0],
            }
        ],
    }


def test_database_initialization(tmp_path):

    database = tmp_path / "test.db"

    storage = ResearchStorage(database)

    assert database.exists()
    assert storage.get_progress()["total"] == 0


def test_register_apps(tmp_path):

    storage = ResearchStorage(
        tmp_path / "test.db"
    )

    storage.register_apps([
        make_app(1),
        make_app(2),
    ])

    progress = storage.get_progress()

    assert progress["total"] == 2
    assert progress["pending"] == 2


def test_registration_is_idempotent(tmp_path):

    storage = ResearchStorage(
        tmp_path / "test.db"
    )

    apps = [make_app(1)]

    storage.register_apps(apps)
    storage.register_apps(apps)

    assert storage.get_progress()["total"] == 1


def test_save_pipeline_output(tmp_path):

    storage = ResearchStorage(
        tmp_path / "test.db"
    )

    app = make_app()

    storage.register_apps([app])
    storage.mark_running(app.id)

    status = storage.save_pipeline_output(
        app.id,
        make_output(app),
    )

    assert status == "completed"
    assert storage.get_status(app.id) == "completed"

    results = storage.get_completed_results()

    assert len(results) == 1
    assert results[0]["support_rate"] == 1.0


def test_completed_apps_are_skipped(tmp_path):

    storage = ResearchStorage(
        tmp_path / "test.db"
    )

    first = make_app(1)
    second = make_app(2)

    storage.register_apps([first, second])

    storage.save_pipeline_output(
        first.id,
        make_output(first),
    )

    pending = storage.get_pending_apps()

    assert len(pending) == 1
    assert pending[0].id == second.id


def test_failed_apps_can_be_retried(tmp_path):

    storage = ResearchStorage(
        tmp_path / "test.db"
    )

    app = make_app()

    storage.register_apps([app])

    storage.mark_failed(
        app.id,
        "Simulated API error",
    )

    assert storage.get_pending_apps() == []

    retry = storage.get_pending_apps(
        retry_failed=True
    )

    assert len(retry) == 1
    assert retry[0].id == app.id


def test_interrupted_apps_can_resume(tmp_path):

    storage = ResearchStorage(
        tmp_path / "test.db"
    )

    app = make_app()

    storage.register_apps([app])
    storage.mark_running(app.id)

    reopened = ResearchStorage(
        tmp_path / "test.db"
    )

    pending = reopened.get_pending_apps()

    assert len(pending) == 1
    assert pending[0].id == app.id


def test_attempt_history_is_preserved(tmp_path):

    storage = ResearchStorage(
        tmp_path / "test.db"
    )

    app = make_app()

    storage.register_apps([app])

    storage.save_pipeline_output(
        app.id,
        make_output(app),
    )

    history = storage.get_attempt_history(
        app.id
    )

    assert len(history) == 1
    assert history[0]["attempt_number"] == 1
    assert history[0]["document_count"] == 3
    assert history[0]["score"] == [1, 1.0, 0]


def test_progress_calculation(tmp_path):

    storage = ResearchStorage(
        tmp_path / "test.db"
    )

    first = make_app(1)
    second = make_app(2)

    storage.register_apps([first, second])

    storage.save_pipeline_output(
        first.id,
        make_output(first),
    )

    progress = storage.get_progress()

    assert progress["total"] == 2
    assert progress["completed"] == 1
    assert progress["pending"] == 1
    assert progress["completion_rate"] == 50.0