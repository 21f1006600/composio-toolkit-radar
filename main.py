import argparse
import asyncio
import json
import logging

from collections import Counter

from src.config import (
    APPS_FILE,
    BATCH_CONCURRENCY,
    BATCH_MAX_ATTEMPTS,
)

from src.schemas import AppInput
from src.storage import ResearchStorage


logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | %(levelname)s | "
        "%(name)s | %(message)s"
    ),
    datefmt="%H:%M:%S",
)

logging.getLogger("httpx").setLevel(
    logging.WARNING
)


def load_apps():

    raw_data = json.loads(
        APPS_FILE.read_text(encoding="utf-8")
    )

    raw_apps = (
        raw_data.get("apps")
        if isinstance(raw_data, dict)
        else raw_data
    )

    if not isinstance(raw_apps, list):
        raise ValueError("Invalid application dataset.")

    apps = [
        AppInput.model_validate(app)
        for app in raw_apps
    ]

    if len(apps) != 100:
        raise ValueError(
            f"Expected 100 applications, found {len(apps)}."
        )

    if len({app.id for app in apps}) != len(apps):
        raise ValueError("Duplicate application IDs.")

    return apps


def positive_int(value):

    number = int(value)

    if number < 1:
        raise argparse.ArgumentTypeError(
            "Value must be positive."
        )

    return number


def build_parser():

    parser = argparse.ArgumentParser(
        description=(
            "Toolkit Radar: Agentic API "
            "Integration Research"
        )
    )

    commands = parser.add_subparsers(
        dest="command",
        required=True,
    )

    commands.add_parser(
        "validate",
        help="Validate the application dataset",
    )

    commands.add_parser(
        "init",
        help="Initialize the research database",
    )

    commands.add_parser(
        "status",
        help="Show research progress",
    )

    run = commands.add_parser(
        "run",
        help="Execute the research pipeline",
    )

    run.add_argument(
        "--limit",
        type=positive_int,
        default=None,
    )

    run.add_argument(
        "--concurrency",
        type=positive_int,
        default=BATCH_CONCURRENCY,
    )

    run.add_argument(
        "--attempts",
        type=positive_int,
        default=BATCH_MAX_ATTEMPTS,
    )

    run.add_argument(
        "--retry-failed",
        action="store_true",
    )

    run.add_argument(
        "--ids",
        nargs="+",
        type=positive_int,
        default=None,
    )

    return parser


def main():

    args = build_parser().parse_args()

    if args.command == "validate":

        apps = load_apps()

        categories = Counter(
            app.category for app in apps
        )

        print("Applications:", len(apps))
        print("Categories:", len(categories))

        for category, count in categories.items():
            print(f"{category}: {count}")

        return

    storage = ResearchStorage()

    if args.command == "init":

        storage.register_apps(load_apps())

        print("Database initialized.")
        print(storage.get_progress())

    elif args.command == "status":

        print("=" * 60)
        print("TOOLKIT RADAR STATUS")
        print("=" * 60)

        for key, value in storage.get_progress().items():
            print(f"{key}: {value}")

    elif args.command == "run":

        from src.batch import BatchRunner

        storage.register_apps(load_apps())

        async def execute():

            runner = BatchRunner(
                concurrency=args.concurrency,
                max_attempts=args.attempts,
            )

            await runner.run(
                limit=args.limit,
                retry_failed=args.retry_failed,
                app_ids=args.ids,
            )

        try:

            asyncio.run(execute())

        except KeyboardInterrupt:

            print("\nBatch interrupted.")
            print("Completed research has been saved.")
            print("Run the same command to resume.")


if __name__ == "__main__":
    main()