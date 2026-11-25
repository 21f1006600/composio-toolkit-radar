import json

from src.config import APPS_FILE, DATABASE_PATH
from src.schemas import AppInput
from src.storage import ResearchStorage


def main():

    raw_data = json.loads(
        APPS_FILE.read_text(encoding="utf-8")
    )

    # Support both wrapped and unwrapped JSON datasets.
    if isinstance(raw_data, dict):
        raw_apps = raw_data.get("apps")
    else:
        raw_apps = raw_data

    if not isinstance(raw_apps, list):
        raise ValueError(
            "Invalid dataset: expected a list of applications."
        )

    apps = [
        AppInput.model_validate(app)
        for app in raw_apps
    ]

    # Validate dataset integrity.
    if len(apps) != 100:
        raise ValueError(
            f"Expected 100 applications, found {len(apps)}."
        )

    app_ids = [app.id for app in apps]

    if len(app_ids) != len(set(app_ids)):
        raise ValueError("Duplicate application IDs found.")

    storage = ResearchStorage()

    storage.register_apps(apps)

    progress = storage.get_progress()

    print("=" * 60)
    print("DATABASE INITIALIZATION")
    print("=" * 60)

    print("Database:", DATABASE_PATH)
    print("Registered applications:", len(apps))
    print("Categories:", len({app.category for app in apps}))

    for key, value in progress.items():
        print(f"{key}: {value}")

    print("\nDatabase initialized successfully.")


if __name__ == "__main__":
    main()