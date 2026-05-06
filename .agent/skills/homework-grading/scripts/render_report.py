#!/usr/bin/env python
import argparse
import json
import sys
from pathlib import Path


def fail(message: str, code: int = 1) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(code)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a student grading JSON as Markdown.")
    parser.add_argument("--grading", required=True, help="Grading JSON path.")
    parser.add_argument("--output", required=True, help="Output Markdown path.")
    args = parser.parse_args()

    grading_path = Path(args.grading)
    output_path = Path(args.output)
    if not grading_path.exists():
        fail(f"Grading JSON not found: {grading_path}")
    try:
        grading = json.loads(grading_path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"Failed to read grading JSON {grading_path}: {exc}")

    student_id = grading.get("student_id", "")
    student_name = grading.get("student_name") or ""
    lines = [
        f"# Homework Grading Report: {student_id}",
        "",
        f"- student_id: {student_id}",
        f"- student_name: {student_name}",
        f"- total_score: {grading.get('total_score')}",
        "",
    ]
    for result in grading.get("results", []):
        review = "yes" if result.get("needs_human_review") else "no"
        lines.extend(
            [
                f"## Question {result.get('question_id')}",
                "",
                f"- score: {result.get('score')} / {result.get('max_score')}",
                f"- needs_human_review: {review}",
                f"- review_reason: {result.get('review_reason', '')}",
                "",
                "### Scoring Details",
                "",
            ]
        )
        for detail in result.get("scoring_details", []):
            lines.extend(
                [
                    f"- {detail.get('point_id')}: {detail.get('score_awarded')} / {detail.get('max_score')}",
                    f"  - reason: {detail.get('reason', '')}",
                    f"  - evidence: {detail.get('evidence', '')}",
                ]
            )
        lines.extend(["", "### Final Reason", "", str(result.get("final_reason", "")), ""])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
