import asyncio
import logging
import time

from src.config import (
    BATCH_CONCURRENCY,
    BATCH_MAX_ATTEMPTS,
    MAX_CONSECUTIVE_FAILURES,
)

from src.pipeline import ResearchPipeline
from src.storage import ResearchStorage


logger = logging.getLogger(__name__)


class BatchRunner:

    def __init__(
        self,
        concurrency: int = BATCH_CONCURRENCY,
        max_attempts: int = BATCH_MAX_ATTEMPTS,
    ):

        if concurrency < 1:
            raise ValueError(
                "Concurrency must be at least 1."
            )

        if max_attempts < 1:
            raise ValueError(
                "Max attempts must be at least 1."
            )

        self.storage = ResearchStorage()
        self.pipeline = ResearchPipeline()

        self.concurrency = concurrency
        self.max_attempts = max_attempts

        self.consecutive_failures = 0
        self.stop_event = asyncio.Event()

    # ======================================
    # Research one application
    # ======================================

    async def process_app(self, app):

        started = time.perf_counter()

        logger.info(
            "Starting application %d: %s",
            app.id,
            app.name,
        )

        self.storage.mark_running(app.id)

        try:

            output = await self.pipeline.run(
                app=app,
                max_attempts=self.max_attempts,
            )

            status = self.storage.save_pipeline_output(
                app.id,
                output,
            )

            if status == "completed":

                self.consecutive_failures = 0

                logger.info(
                    "Completed: %s | %.2fs",
                    app.name,
                    time.perf_counter() - started,
                )

            else:

                self.consecutive_failures += 1

                logger.warning(
                    "No publishable research: %s",
                    app.name,
                )

        except Exception as exc:

            message = (
                f"{type(exc).__name__}: {exc}"
            )

            self.storage.mark_failed(
                app.id,
                message,
            )

            self.consecutive_failures += 1

            logger.error(
                "Application failed: %s | %s",
                app.name,
                message,
            )

        if (
            self.consecutive_failures
            >= MAX_CONSECUTIVE_FAILURES
        ):

            logger.error(
                "Stopping batch after repeated failures."
            )

            self.stop_event.set()

        self.print_progress()

    # ======================================
    # Worker
    # ======================================

    async def worker(self, queue):

        while not self.stop_event.is_set():

            try:
                app = queue.get_nowait()

            except asyncio.QueueEmpty:
                return

            try:

                await self.process_app(app)

            finally:

                queue.task_done()

    # ======================================
    # Progress
    # ======================================

    def print_progress(self):

        progress = self.storage.get_progress()

        logger.info(
            "Progress | Completed: %d/%d | "
            "Pending: %d | Running: %d | "
            "Failed: %d | %.2f%%",
            progress["completed"],
            progress["total"],
            progress["pending"],
            progress["running"],
            progress["failed"],
            progress["completion_rate"],
        )

    # ======================================
    # Execute batch
    # ======================================

    async def run(
        self,
        limit: int | None = None,
        retry_failed: bool = False,
        app_ids: list[int] | None = None,
    ):

        started = time.perf_counter()

        self.consecutive_failures = 0
        self.stop_event.clear()

        if limit is not None and limit < 1:
            raise ValueError(
                "Limit must be positive."
            )

        apps = self.storage.get_pending_apps(
            retry_failed=retry_failed,
        )

        if app_ids is not None:

            selected_ids = set(app_ids)

            apps = [
                app for app in apps
                if app.id in selected_ids
            ]

        if limit is not None:
            apps = apps[:limit]

        logger.info(
            "Applications selected: %d",
            len(apps),
        )

        logger.info(
            "Concurrency: %d",
            self.concurrency,
        )

        logger.info(
            "Maximum attempts per app: %d",
            self.max_attempts,
        )

        if not apps:

            logger.info(
                "No eligible applications remaining."
            )

            return self.storage.get_progress()

        queue = asyncio.Queue()

        for app in apps:
            queue.put_nowait(app)

        workers = [
            asyncio.create_task(
                self.worker(queue)
            )
            for _ in range(
                min(self.concurrency, len(apps))
            )
        ]

        await asyncio.gather(*workers)

        progress = self.storage.get_progress()

        print("\n" + "=" * 60)
        print("BATCH EXECUTION SUMMARY")
        print("=" * 60)

        for key, value in progress.items():
            print(f"{key}: {value}")

        print(
            "Batch execution time:",
            round(time.perf_counter() - started, 2),
            "seconds",
        )

        print(
            "Stopped due to repeated failures:",
            self.stop_event.is_set(),
        )

        return progress