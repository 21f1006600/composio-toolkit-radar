import json
from pathlib import Path

from src.storage import ResearchStorage
from src.schemas import ResearchResult
from src.pipeline import ResearchPipeline


def main():

    path = Path("data/pipeline_sample.json")

    audit = json.loads(
        path.read_text(encoding="utf-8")
    )

    candidates = []

    for attempt in audit["history"]:

        if "error" in attempt:
            continue

        result = ResearchResult.model_validate(
            attempt["research"]
        )

        feedback = attempt["verification"]

        clean = ResearchPipeline.sanitize_result(
            result,
            feedback,
        )

        score = ResearchPipeline.attempt_score(
            feedback,
            clean,
        )

        candidates.append({
            "attempt": attempt["attempt"],
            "result": clean,
            "feedback": feedback,
            "score": score,
        })

    if not candidates:
        raise RuntimeError(
            "No valid research attempts found."
        )

    best = max(
        candidates,
        key=lambda candidate: candidate["score"],
    )

    audit["final_result"] = best[
        "result"
    ].model_dump(mode="json")

    audit["final_verification"] = best["feedback"]
    audit["selected_attempt"] = best["attempt"]

    storage = ResearchStorage()

    app = best["result"].app

    if storage.get_status(app.id) is None:
        raise RuntimeError(
            "Application not registered in database."
        )

    status = storage.save_pipeline_output(
        app.id,
        audit,
    )

    print("=" * 60)
    print("PILOT RESEARCH IMPORT")
    print("=" * 60)

    print("Application:", app.name)
    print("Status:", status)
    print("Selected attempt:", best["attempt"])
    print("Published claims:", len(best["result"].claims))
    print("External API calls: 0")

    print("\nDatabase progress:")

    for key, value in storage.get_progress().items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()