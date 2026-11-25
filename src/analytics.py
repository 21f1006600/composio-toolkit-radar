
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone

from src.config import DATA_DIR
from src.storage import ResearchStorage


class AnalyticsEngine:

    CRITICAL_FIELDS = [
        "description",
        "auth_methods",
        "access_types",
        "api_types",
        "api_breadth",
        "example_operations",
        "mcp_status",
        "buildability",
    ]

    def __init__(self, storage=None):
        self.storage = storage or ResearchStorage()

    @staticmethod
    def is_resolved(value):
        if value is None:
            return False

        if isinstance(value, list):
            return any(
                AnalyticsEngine.is_resolved(v)
                for v in value
            )

        if isinstance(value, str):
            return value.strip().lower() not in {
                "", "unknown"
            }

        return True

    @staticmethod
    def distribution(records, field):
        counts = Counter()

        for record in records:
            value = record["result"].get(field)

            if isinstance(value, list):
                values = set(value) or {"unknown"}
            else:
                values = {value or "unknown"}

            counts.update(values)

        return dict(counts.most_common())

    def category_analysis(self, records):
        groups = defaultdict(list)

        for record in records:
            category = record["result"]["app"]["category"]
            groups[category].append(record)

        output = []

        for category, items in sorted(groups.items()):
            output.append({
                "category": category,
                "expected_apps": 10,
                "completed_apps": len(items),
                "completion_rate": round(
                    len(items) / 10 * 100, 2
                ),
                "buildability": self.distribution(
                    items, "buildability"
                ),
                "mcp_status": self.distribution(
                    items, "mcp_status"
                ),
            })

        return output

    def evidence_analysis(self, records):
        total_claims = 0
        supported_claims = 0
        evidence_backed_claims = 0
        source_urls = set()
        official_urls = set()

        for record in records:
            claims = record["result"].get("claims", [])

            for claim in claims:
                total_claims += 1

                if claim.get("verification_status") == "supported":
                    supported_claims += 1

                evidence = claim.get("evidence", [])

                if evidence:
                    evidence_backed_claims += 1

                for item in evidence:
                    url = item.get("source_url")

                    if url:
                        source_urls.add(url)

                        if item.get("official_source"):
                            official_urls.add(url)

        return {
            "published_claims": total_claims,
            "supported_claims": supported_claims,
            "evidence_backed_claims": evidence_backed_claims,
            "unique_sources": len(source_urls),
            "official_domain_matched_sources": len(official_urls),
            "evidence_coverage": round(
                evidence_backed_claims / total_claims * 100, 2
            ) if total_claims else 0,
        }

    def completeness_analysis(self, records):
        field_counts = Counter()
        app_scores = []

        for record in records:
            result = record["result"]

            resolved = [
                field
                for field in self.CRITICAL_FIELDS
                if self.is_resolved(result.get(field))
            ]

            field_counts.update(resolved)

            app_scores.append({
                "app": result["app"]["name"],
                "resolved_fields": len(resolved),
                "total_fields": len(self.CRITICAL_FIELDS),
                "completeness": round(
                    len(resolved) /
                    len(self.CRITICAL_FIELDS) * 100,
                    2
                ),
            })

        count = len(records)

        return {
            "average_critical_completeness": round(
                sum(item["completeness"] for item in app_scores)
                / count, 2
            ) if count else 0,
            "field_coverage": {
                field: {
                    "resolved": field_counts[field],
                    "unresolved": count - field_counts[field],
                    "coverage": round(
                        field_counts[field] / count * 100, 2
                    ) if count else 0,
                }
                for field in self.CRITICAL_FIELDS
            },
            "application_scores": app_scores,
        }

    def opportunity_analysis(self, records):
        opportunities = {
            "easy_wins": [],
            "conditional_integrations": [],
            "outreach_candidates": [],
            "needs_more_research": [],
        }

        for record in records:
            result = record["result"]

            buildability = result.get(
                "buildability", "unknown"
            )

            access = result.get("access_types", [])
            blockers = result.get("blockers", [])

            item = {
                "name": result["app"]["name"],
                "category": result["app"]["category"],
                "auth_methods": result.get("auth_methods", []),
                "api_types": result.get("api_types", []),
                "access_types": access,
                "api_breadth": result.get("api_breadth"),
                "mcp_status": result.get("mcp_status"),
                "buildability": buildability,
                "blockers": blockers,
                "reason": result.get("verdict_reason", ""),
            }

            if (
                buildability == "ready"
                and not blockers
                and "free" in access
                and result.get("api_breadth") in {
                    "broad", "moderate"
                }
            ):
                group = "easy_wins"

            elif (
                buildability == "blocked"
                or "partner_gated" in access
            ):
                group = "outreach_candidates"

            elif buildability in {"ready", "conditional"}:
                group = "conditional_integrations"

            else:
                group = "needs_more_research"

            opportunities[group].append(item)

        return opportunities

    @staticmethod
    def benchmark_analysis():
        filenames = {
            "v2": "quality_benchmark_v2.json",
            "v3": "quality_benchmark_v3.json",
            "v4": "quality_benchmark_v4.json",
        }

        versions = {}

        for version, filename in filenames.items():
            path = DATA_DIR / filename

            if not path.exists():
                continue

            rows = json.loads(
                path.read_text(encoding="utf-8")
            )

            successful = [
                row for row in rows
                if row.get("pipeline_output", {}).get(
                    "selected_attempt"
                ) is not None
                and row.get("after", {}).get(
                    "published_claims", 0
                ) > 0
            ]

            count = len(successful)

            before = (
                sum(
                    row["before"]["completeness"]
                    for row in successful
                ) / count
                if count else None
            )

            after = (
                sum(
                    row["after"]["completeness"]
                    for row in successful
                ) / count
                if count else None
            )

            versions[version] = {
                "successful": count,
                "failed": len(rows) - count,
                "matched_baseline": (
                    round(before, 2)
                    if before is not None else None
                ),
                "average_completeness": (
                    round(after, 2)
                    if after is not None else None
                ),
                "improvement_pp": (
                    round(after - before, 2)
                    if count else None
                ),
                "applications": [
                    {
                        "name": row["app_name"],
                        "before": row["before"]["completeness"],
                        "after": row["after"]["completeness"],
                    }
                    for row in successful
                ],
            }

        return versions

    def generate(self):
        records = self.storage.get_completed_results()

        return {
            "generated_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "progress": self.storage.get_progress(),
            "analyzed_applications": len(records),
            "distributions": {
                field: self.distribution(records, field)
                for field in [
                    "auth_methods",
                    "access_types",
                    "api_types",
                    "api_breadth",
                    "mcp_status",
                    "buildability",
                ]
            },
            "categories": self.category_analysis(records),
            "evidence": self.evidence_analysis(records),
            "completeness": self.completeness_analysis(records),
            "opportunities": self.opportunity_analysis(records),
            "benchmarks": self.benchmark_analysis(),
        }

    def export(self, output_path=None):
        output_path = (
            output_path or DATA_DIR / "analytics.json"
        )

        analytics = self.generate()

        output_path.write_text(
            json.dumps(
                analytics,
                indent=2,
                ensure_ascii=False
            ),
            encoding="utf-8"
        )

        return analytics


if __name__ == "__main__":
    engine = AnalyticsEngine()
    analytics = engine.export()

    print("=" * 60)
    print("TOOLKIT RADAR ANALYTICS")
    print("=" * 60)

    print("\nProgress:")
    print(json.dumps(analytics["progress"], indent=2))

    print("\nBuildability:")
    print(json.dumps(
        analytics["distributions"]["buildability"],
        indent=2
    ))

    print("\nMCP availability:")
    print(json.dumps(
        analytics["distributions"]["mcp_status"],
        indent=2
    ))

    print("\nEvidence:")
    print(json.dumps(analytics["evidence"], indent=2))

    print("\nIntegration opportunities:")

    for group, apps in analytics["opportunities"].items():
        print(f"{group}: {len(apps)}")

    print("\nBenchmark results:")
    print(json.dumps(analytics["benchmarks"], indent=2))

    print("\nAnalytics saved to data/analytics.json")
