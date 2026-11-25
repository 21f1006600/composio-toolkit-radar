
import json
from datetime import datetime, timezone

from src.config import DATA_DIR
from src.storage import ResearchStorage


def export_results():
    storage = ResearchStorage()

    records = storage.get_completed_results()
    progress = storage.get_progress()

    export = {
        "project": "Toolkit Radar",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "progress": progress,
        "total_exported": len(records),
        "applications": records,
    }

    output_path = DATA_DIR / "research_results.json"

    output_path.write_text(
        json.dumps(export, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("=" * 60)
    print("RESEARCH DATASET EXPORT")
    print("=" * 60)
    print(f"Applications exported: {len(records)}")
    print(f"Total applications: {progress['total']}")
    print(f"Completion rate: {progress['completion_rate']}%")
    print(f"Output: {output_path}")
    print(f"File size: {output_path.stat().st_size / 1024:.2f} KB")

    if len(records) < progress["total"]:
        print("NOTE: This is a partial dataset.")


if __name__ == "__main__":
    export_results()
