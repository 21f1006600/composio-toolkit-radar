
import asyncio
import json
import logging
import time
from pathlib import Path

from src.config import APPS_FILE
from src.schemas import AppInput
from src.pipeline import ResearchPipeline
from src.storage import ResearchStorage


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)

logging.getLogger("httpx").setLevel(logging.WARNING)

BENCHMARK_IDS = [21, 61, 81]

FIELDS = [
    "description",
    "auth_methods",
    "access_types",
    "access_details",
    "api_types",
    "api_breadth",
    "example_operations",
    "mcp_status",
    "mcp_url",
    "buildability",
    "blockers",
    "verdict_reason",
]

OUTPUT_PATH = Path("data/quality_benchmark.json")


def is_resolved(value):
    if value is None:
        return False

    if isinstance(value, list):
        return any(is_resolved(item) for item in value)

    if isinstance(value, str):
        return value.strip().lower() not in {
            "", "unknown", "none"
        }

    return bool(value)


def calculate_metrics(result):
    resolved = [
        field for field in FIELDS
        if is_resolved(result.get(field))
    ]

    unresolved = [
        field for field in FIELDS
        if field not in resolved
    ]

    return {
        "resolved_fields": len(resolved),
        "total_fields": len(FIELDS),
        "completeness": round(
            len(resolved) / len(FIELDS) * 100, 2
        ),
        "resolved": resolved,
        "unresolved": unresolved,
        "published_claims": len(result.get("claims", [])),
    }


async def main():
    started = time.perf_counter()

    baseline_path = Path("data/quality_baseline.db")

    if not baseline_path.exists():
        raise FileNotFoundError(
            "Baseline database is missing."
        )

    baseline_storage = ResearchStorage(baseline_path)

    baseline_records = {
        record["app_id"]: record
        for record in baseline_storage.get_completed_results()
    }

    raw = json.loads(
        APPS_FILE.read_text(encoding="utf-8")
    )

    apps = raw["apps"] if isinstance(raw, dict) else raw

    selected = [
        AppInput.model_validate(app)
        for app in apps
        if app["id"] in BENCHMARK_IDS
    ]

    if len(selected) != len(BENCHMARK_IDS):
        raise RuntimeError("Benchmark apps are missing.")

    pipeline = ResearchPipeline()

    benchmark = []

    for app in selected:
        print("\n" + "=" * 65)
        print(f"BENCHMARK: {app.name}")
        print("=" * 65)

        baseline = baseline_records.get(app.id)

        if not baseline:
            print("Baseline record missing. Skipping.")
            continue

        before = calculate_metrics(baseline["result"])

        try:
            output = await pipeline.run(
                app,
                max_attempts=2,
            )

            after = calculate_metrics(
                output["final_result"]
            )

            feedback = output.get("final_verification") or {}

            improvement = round(
                after["completeness"]
                - before["completeness"],
                2,
            )

            record = {
                "app_id": app.id,
                "app_name": app.name,
                "before": before,
                "after": after,
                "improvement_pp": improvement,
                "baseline_support_rate": baseline.get(
                    "support_rate"
                ),
                "new_support_rate": feedback.get(
                    "support_rate"
                ),
                "pipeline_output": output,
            }

            benchmark.append(record)

            print(f"Before: {before['completeness']}%")
            print(f"After: {after['completeness']}%")
            print(f"Change: {improvement:+.2f} pp")
            print(
                f"Published claims: "
                f"{after['published_claims']}"
            )
            print(
                f"Unresolved fields: "
                f"{after['unresolved']}"
            )

        except Exception as exc:
            benchmark.append({
                "app_id": app.id,
                "app_name": app.name,
                "error": type(exc).__name__,
            })

            print(
                f"Benchmark failed: {type(exc).__name__}"
            )

        OUTPUT_PATH.write_text(
            json.dumps(
                benchmark,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    successful = [
        record for record in benchmark
        if "before" in record and "after" in record
    ]

    print("\n" + "=" * 65)
    print("QUALITY BENCHMARK SUMMARY")
    print("=" * 65)

    for record in successful:
        print(
            f"{record['app_name']}: "
            f"{record['before']['completeness']}% -> "
            f"{record['after']['completeness']}% "
            f"({record['improvement_pp']:+.2f} pp)"
        )

    if successful:
        count = len(successful)

        before_avg = sum(
            r["before"]["completeness"]
            for r in successful
        ) / count

        after_avg = sum(
            r["after"]["completeness"]
            for r in successful
        ) / count

        print(f"\nAverage before: {before_avg:.2f}%")
        print(f"Average after: {after_avg:.2f}%")
        print(
            f"Average improvement: "
            f"{after_avg - before_avg:+.2f} pp"
        )

    print(f"Benchmarked: {len(successful)}/{len(selected)}")
    print(f"Execution time: {time.perf_counter() - started:.2f}s")
    print(f"Results saved to: {OUTPUT_PATH}")
    print("Production research records were not overwritten.")


if __name__ == "__main__":
    asyncio.run(main())
