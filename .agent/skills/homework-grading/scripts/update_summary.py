#!/usr/bin/env python
import argparse
import csv
import json
import sys
from pathlib import Path


def fail(message: str, code: int = 1) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(code)


def warn(message: str) -> None:
    print(f"WARNING: {message}", file=sys.stderr)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_grading(grading: dict, rubric: dict | None, schema: dict | None) -> list[str]:
    errors = []
    if schema is not None:
        try:
            import jsonschema
            jsonschema.validate(instance=grading, schema=schema)
        except ImportError:
            errors.append("Missing dependency jsonschema. Install with: pip install jsonschema")
        except Exception as exc:
            errors.append(f"Schema validation failed: {exc}")

    if rubric is None:
        return errors

    rubric_questions = {q.get("question_id"): q for q in rubric.get("questions", [])}
    result_questions = {r.get("question_id") for r in grading.get("results", [])}
    missing = set(rubric_questions) - result_questions
    extra = result_questions - set(rubric_questions)
    if missing:
        errors.append("Missing rubric questions: " + ", ".join(sorted(missing)))
    if extra:
        errors.append("Unknown grading questions: " + ", ".join(sorted(extra)))

    total = 0.0
    for result in grading.get("results", []):
        qid = result.get("question_id")
        score = float(result.get("score", 0) or 0)
        max_score = float(result.get("max_score", 0) or 0)
        detail_total = sum(float(d.get("score_awarded", 0) or 0) for d in result.get("scoring_details", []))
        if abs(score - detail_total) > 0.000001:
            errors.append(f"Question {qid}: score does not equal scoring_details total")
        if score - max_score > 0.000001:
            errors.append(f"Question {qid}: score exceeds max_score")
        if qid in rubric_questions and abs(max_score - float(rubric_questions[qid].get("max_score", 0) or 0)) > 0.000001:
            errors.append(f"Question {qid}: max_score does not match rubric")
        total += score
    if abs(float(grading.get("total_score", 0) or 0) - total) > 0.000001:
        errors.append("total_score does not equal sum of question scores")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate summary.csv and review_queue.csv from grading JSON files.")
    parser.add_argument("--grading-dir", required=True, help="Directory containing *.grading.json files.")
    parser.add_argument("--report-dir", required=True, help="Directory where CSV reports will be written.")
    parser.add_argument("--rubric", help="Optional rubric JSON path. When provided, invalid grading files are skipped.")
    parser.add_argument("--schema", help="Optional grading schema JSON path. When provided, invalid grading files are skipped.")
    args = parser.parse_args()

    grading_dir = Path(args.grading_dir)
    report_dir = Path(args.report_dir)
    if not grading_dir.exists():
        fail(f"Grading directory not found: {grading_dir}")

    grading_files = sorted(grading_dir.glob("*.grading.json"))
    if not grading_files:
        fail(f"No *.grading.json files found in {grading_dir}")

    rubric = None
    schema = None
    if args.rubric:
        rubric_path = Path(args.rubric)
        if not rubric_path.exists():
            fail(f"Rubric JSON not found: {rubric_path}")
        try:
            rubric = load_json(rubric_path)
        except Exception as exc:
            fail(f"Failed to read rubric JSON {rubric_path}: {exc}")
    if args.schema:
        schema_path = Path(args.schema)
        if not schema_path.exists():
            fail(f"Grading schema JSON not found: {schema_path}")
        try:
            schema = load_json(schema_path)
        except Exception as exc:
            fail(f"Failed to read grading schema JSON {schema_path}: {exc}")

    summary_rows = []
    review_rows = []
    for grading_file in grading_files:
        try:
            grading = load_json(grading_file)
        except Exception as exc:
            warn(f"Skipping unreadable grading JSON {grading_file}: {exc}")
            continue
        validation_errors = validate_grading(grading, rubric, schema)
        if validation_errors:
            warn(f"Skipping invalid grading JSON {grading_file}: {'; '.join(validation_errors)}")
            continue
        review_count = 0
        for result in grading.get("results", []):
            if result.get("needs_human_review"):
                review_count += 1
                review_rows.append(
                    {
                        "student_id": grading.get("student_id", ""),
                        "question_id": result.get("question_id", ""),
                        "score": result.get("score", ""),
                        "max_score": result.get("max_score", ""),
                        "review_reason": result.get("review_reason", ""),
                    }
                )
        summary_rows.append(
            {
                "student_id": grading.get("student_id", ""),
                "student_name": grading.get("student_name", ""),
                "total_score": grading.get("total_score", ""),
                "needs_human_review_count": review_count,
            }
        )

    if not summary_rows:
        fail(f"No valid grading JSON files found in {grading_dir}")

    report_dir.mkdir(parents=True, exist_ok=True)
    with (report_dir / "summary.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=["student_id", "student_name", "total_score", "needs_human_review_count"])
        writer.writeheader()
        writer.writerows(summary_rows)

    with (report_dir / "review_queue.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=["student_id", "question_id", "score", "max_score", "review_reason"])
        writer.writeheader()
        writer.writerows(review_rows)

    print(f"OK: wrote {report_dir / 'summary.csv'} and {report_dir / 'review_queue.csv'}")


if __name__ == "__main__":
    main()
