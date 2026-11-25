from collections import Counter

from src.storage import ResearchStorage


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


def is_resolved(value):

    if value is None:
        return False

    if isinstance(value, list):
        return any(is_resolved(item) for item in value)

    if isinstance(value, str):
        return value.strip().lower() not in {
            "",
            "unknown",
            "none",
        }

    return True


def main():

    storage = ResearchStorage()
    results = storage.get_completed_results()

    missing_fields = Counter()
    buildability = Counter()
    coverage_scores = []

    print("=" * 70)
    print("RESEARCH QUALITY AUDIT")
    print("=" * 70)

    for record in results:

        result = record["result"]
        app = result["app"]

        print("\n" + "=" * 70)
        print("APPLICATION:", app["name"])
        print("CATEGORY:", app["category"])
        print("SELECTED ATTEMPT:", record["selected_attempt"])
        print("TOTAL ATTEMPTS:", record["total_attempts"])
        print("=" * 70)

        resolved = 0

        for field in FIELDS:

            value = result.get(field)

            if is_resolved(value):
                resolved += 1
            else:
                missing_fields[field] += 1

            print(f"{field}: {value}")

        coverage = resolved / len(FIELDS) * 100
        coverage_scores.append(coverage)

        claims = result.get("claims", [])

        buildability[result.get("buildability", "unknown")] += 1

        print("\nPublished claims:", len(claims))
        print("Populated fields:", f"{resolved}/{len(FIELDS)}")
        print("Field population:", f"{coverage:.2f}%")

        support_rate = record.get("support_rate")

        if support_rate is not None:
            print(
                "Semantic support:",
                f"{support_rate * 100:.2f}%",
            )

        print("\nEvidence sources:")

        sources = set()

        for claim in claims:
            for evidence in claim.get("evidence", []):
                sources.add(evidence["source_url"])

        for source in sorted(sources):
            print("-", source)

    print("\n" + "=" * 70)
    print("AGGREGATE QUALITY SUMMARY")
    print("=" * 70)

    print("Completed applications:", len(results))

    if coverage_scores:
        print(
            "Average field population:",
            f"{sum(coverage_scores) / len(coverage_scores):.2f}%",
        )

    print("\nMissing or unresolved fields:")

    for field, count in missing_fields.most_common():
        print(f"{field}: {count}/{len(results)}")

    print("\nBuildability distribution:")

    for verdict, count in buildability.most_common():
        print(f"{verdict}: {count}")

    print("\nDatabase progress:")

    for key, value in storage.get_progress().items():
        print(f"{key}: {value}")

    print("\nExternal API calls: 0")
    print("Database records modified: 0")


if __name__ == "__main__":
    main()