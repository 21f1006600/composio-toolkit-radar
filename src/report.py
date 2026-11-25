
import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.analytics import AnalyticsEngine
from src.storage import ResearchStorage
from src.config import DATA_DIR, DOCS_DIR, TEMPLATES_DIR


class ReportGenerator:

    def __init__(self):
        self.storage = ResearchStorage()
        self.analytics = AnalyticsEngine(self.storage)

        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=select_autoescape(["html", "xml"])
        )

    def generate(self):
        analytics = self.analytics.generate()
        records = self.storage.get_completed_results()

        applications = [
            record["result"] for record in records
        ]

        applications.sort(
            key=lambda app: app["app"]["name"].lower()
        )

        audit_path = DATA_DIR / "manual_accuracy.json"

        manual_accuracy = (
            json.loads(audit_path.read_text(encoding="utf-8"))
            if audit_path.exists()
            else None
        )

        template = self.env.get_template("index.html")

        html = template.render(
            analytics=analytics,
            applications=applications,
            manual_accuracy=manual_accuracy
        )

        DOCS_DIR.mkdir(parents=True, exist_ok=True)

        output = DOCS_DIR / "index.html"
        output.write_text(html, encoding="utf-8")

        print("=" * 60)
        print("TOOLKIT RADAR REPORT")
        print("=" * 60)
        print(f"Applications included: {len(applications)}")
        print(f"Report size: {output.stat().st_size:,} bytes")
        print(f"Report generated: {output.resolve()}")

        return output


if __name__ == "__main__":
    ReportGenerator().generate()
