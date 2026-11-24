import json
from collections import Counter

from src.config import APPS_FILE
from src.schemas import AppInput


def load_apps() -> list[AppInput]:
    with APPS_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)

    apps = [
        AppInput.model_validate(app)
        for app in data["apps"]
    ]

    if len(apps) != 100:
        raise ValueError("Expected exactly 100 applications")

    ids = [app.id for app in apps]

    if sorted(ids) != list(range(1, 101)):
        raise ValueError("Missing or duplicate application IDs")

    categories = Counter(app.category for app in apps)

    if len(categories) != 10:
        raise ValueError("Expected exactly 10 categories")

    if any(count != 10 for count in categories.values()):
        raise ValueError("Expected 10 apps per category")

    return apps


def main():
    apps = load_apps()

    print("Toolkit Radar")
    print("=" * 50)
    print(f"Applications loaded: {len(apps)}")

    categories = Counter(app.category for app in apps)

    print(f"Categories: {len(categories)}")
    print("\nDataset distribution:")

    for category, count in categories.items():
        print(f"  {category}: {count}")

    print("\nDataset validation successful.")


if __name__ == "__main__":
    main()