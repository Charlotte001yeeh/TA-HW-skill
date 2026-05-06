#!/usr/bin/env python3
"""Render a Markdown review report from structured review artifacts."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


DISCREPANCY_FIELDS = [
    "severity",
    "student_id",
    "student_name",
    "file",
    "issue_type",
    "location",
    "current_value",
    "expected_value",
    "explanation",
    "suggested_action",
    "needs_human_review",
]


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig", errors="replace") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def append_final_pdf_discrepancy(root: Path, discrepancies: list[dict[str, str]]) -> list[dict[str, str]]:
    final_dir = root / "work" / "final"
    has_pdf = final_dir.exists() and any(final_dir.glob("*.pdf"))
    if has_pdf:
        return discrepancies
    row = {
        "severity": "WARNING",
        "student_id": "",
        "student_name": "",
        "file": rel(final_dir, root),
        "issue_type": "FINAL_REPORT_MISSING",
        "location": "work/final",
        "current_value": "no final PDF",
        "expected_value": "final PDF generated from reviewed JSON/CSV",
        "explanation": "No final PDF artifact is present. This is an output gap, not a basis for changing grades.",
        "suggested_action": "Generate final PDFs from structured reviewed grades after resolving review issues.",
        "needs_human_review": "false",
    }
    key = (row["issue_type"], row["file"], row["location"])
    if not any((d.get("issue_type"), d.get("file"), d.get("location")) == key for d in discrepancies):
        discrepancies.append(row)
        write_csv(root / "work" / "review" / "discrepancies.csv", discrepancies, DISCREPANCY_FIELDS)
    return discrepancies


def load_reviews(root: Path) -> list[dict[str, Any]]:
    reviews: list[dict[str, Any]] = []
    for path in sorted((root / "work" / "review" / "student_review").glob("*.review.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict):
            reviews.append(data)
    return reviews


def count_files(path: Path, pattern: str) -> int:
    return len(list(path.glob(pattern))) if path.exists() else 0


def main_issues(review: dict[str, Any], limit: int = 3) -> str:
    issues: list[str] = []
    for question in review.get("question_reviews", []):
        if not isinstance(question, dict):
            continue
        qid = question.get("question_id", "")
        for issue in question.get("issues", []):
            issues.append(f"{qid}: {issue}")
            if len(issues) >= limit:
                return "; ".join(issues)
    comments = review.get("review_comments", [])
    return "; ".join(str(item) for item in comments[:limit])


def table_row(values: list[Any]) -> str:
    return "| " + " | ".join(str(value).replace("\n", " ") for value in values) + " |"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Repository root")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    review_dir = root / "work" / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    discrepancies = append_final_pdf_discrepancy(root, read_csv(review_dir / "discrepancies.csv"))
    reviews = load_reviews(root)
    reviewed_grades = read_csv(review_dir / "reviewed_grades.csv")
    queue = read_csv(review_dir / "review_queue_reviewed.csv")

    status_counts = Counter(str(review.get("review_status", "UNKNOWN")) for review in reviews)
    issue_counts = Counter(row.get("issue_type", "") for row in discrepancies)
    severity_counts = Counter(row.get("severity", "") for row in discrepancies)
    high_risk = [row for row in discrepancies if row.get("severity") in {"CRITICAL", "ERROR"}]
    high_risk = sorted(high_risk, key=lambda row: (row.get("severity") != "CRITICAL", row.get("student_id", ""), row.get("issue_type", "")))[:50]

    as_dir = root / "as"
    lines: list[str] = []
    lines.append("# Homework Grading Review Report")
    lines.append("")
    lines.append(f"Generated: {datetime.now().isoformat(timespec='seconds')}")
    lines.append("")
    lines.append("## Project Info")
    lines.append("")
    lines.append(table_row(["Item", "Path / Count"]))
    lines.append(table_row(["---", "---"]))
    lines.append(table_row(["Standard answers", rel(as_dir, root)]))
    lines.append(table_row(["Rubric", rel(root / "work" / "rubric" / "rubric.json", root)]))
    lines.append(table_row(["grading JSON count", count_files(root / "work" / "grading", "*.grading.json")]))
    lines.append(table_row(["answers JSON count", count_files(root / "work" / "answers", "*.answers.json")]))
    lines.append(table_row(["summary.csv", rel(root / "work" / "reports" / "summary.csv", root) if (root / "work" / "reports" / "summary.csv").exists() else "missing"]))
    lines.append(table_row(["grades.csv", rel(root / "work" / "reports" / "grades.csv", root) if (root / "work" / "reports" / "grades.csv").exists() else "missing"]))
    lines.append(table_row(["original review_queue.csv", rel(root / "work" / "reports" / "review_queue.csv", root) if (root / "work" / "reports" / "review_queue.csv").exists() else "missing"]))
    lines.append(table_row(["reviewed queue rows", len(queue)]))
    lines.append("")
    lines.append("## Overall Conclusion")
    lines.append("")
    lines.append(table_row(["Metric", "Count"]))
    lines.append(table_row(["---", "---"]))
    lines.append(table_row(["Students reviewed", len(reviews)]))
    for status in ["PASS", "MINOR_ISSUES", "NEEDS_FIX", "NEEDS_HUMAN_REVIEW"]:
        lines.append(table_row([status, status_counts.get(status, 0)]))
    lines.append(table_row(["Discrepancies", len(discrepancies)]))
    lines.append(table_row(["CRITICAL", severity_counts.get("CRITICAL", 0)]))
    lines.append(table_row(["ERROR", severity_counts.get("ERROR", 0)]))
    lines.append(table_row(["WARNING", severity_counts.get("WARNING", 0)]))
    lines.append("")
    lines.append("- Total score mismatches found: " + str(issue_counts.get("TOTAL_SCORE_MISMATCH", 0)))
    lines.append("- Name/ID mismatches found: " + str(issue_counts.get("NAME_ID_MISMATCH", 0)))
    lines.append("- Missing grading JSON issues found: " + str(issue_counts.get("MISSING_GRADING_JSON", 0)))
    lines.append("- Summary/grading inconsistencies found: " + str(issue_counts.get("QUESTION_SCORE_MISMATCH", 0) + issue_counts.get("MISSING_SUMMARY_ROW", 0)))
    if issue_counts.get("FINAL_REPORT_MISSING", 0):
        lines.append("- Final PDF is missing and should be generated later from structured reviewed JSON/CSV, not from raw PDFs.")
    lines.append("")
    lines.append("## High-Risk Issues")
    lines.append("")
    if high_risk:
        lines.append(table_row(["Severity", "Student ID", "Issue", "Location", "Explanation", "Suggested action"]))
        lines.append(table_row(["---", "---", "---", "---", "---", "---"]))
        for row in high_risk:
            lines.append(table_row([row.get("severity", ""), row.get("student_id", ""), row.get("issue_type", ""), row.get("location", ""), row.get("explanation", ""), row.get("suggested_action", "")]))
    else:
        lines.append("No CRITICAL or ERROR discrepancies were found.")
    lines.append("")
    lines.append("## Student Review Results")
    lines.append("")
    lines.append(table_row(["student_id", "student_name", "current_total", "recomputed_total", "suggested_total", "review_status", "needs_human_review", "main_issues"]))
    lines.append(table_row(["---", "---", "---", "---", "---", "---", "---", "---"]))
    for review in reviews:
        lines.append(
            table_row(
                [
                    review.get("student_id", ""),
                    review.get("student_name", ""),
                    review.get("total_score_from_summary", review.get("total_score_from_grading", "")),
                    review.get("recomputed_total", ""),
                    review.get("suggested_total_score", ""),
                    review.get("review_status", ""),
                    review.get("needs_human_review", ""),
                    main_issues(review),
                ]
            )
        )
    if not reviews and reviewed_grades:
        lines.append("")
        lines.append("Student review JSON files are missing; reviewed_grades.csv exists and should be used only as a partial summary.")
    lines.append("")
    lines.append("## Recommended Fixes")
    lines.append("")
    suggestions = {
        "TOTAL_SCORE_MISMATCH": "Recompute totals from per-question scores and regenerate reviewed_grades.csv.",
        "QUESTION_SCORE_MISMATCH": "Reconcile report question columns with grading JSON before final release.",
        "NAME_ID_MISMATCH": "Manually verify student identity and check for shifted rows.",
        "SCORE_OUT_OF_RANGE": "Manually correct out-of-range question scores.",
        "MISSING_DEDUCTION_REASON": "Add rubric-specific deduction reasons for non-full-score items.",
        "UNCLEAR_DEDUCTION_REASON": "Replace generic deduction reasons with audit-ready explanations.",
        "MISSING_EVIDENCE": "Add answer excerpts or precise extracted-text references.",
        "REVIEW_QUEUE_MISSING": "Add affected students/questions to the reviewed human-review queue.",
        "OCR_UNCERTAIN_NOT_FLAGGED": "Inspect original submission and extracted text before finalizing.",
        "FINAL_REPORT_MISSING": "Generate final PDFs only after review issues are resolved.",
    }
    for issue_type, suggestion in suggestions.items():
        count = issue_counts.get(issue_type, 0)
        if count:
            lines.append(f"- {issue_type} ({count}): {suggestion}")
    if not any(issue_counts.get(key, 0) for key in suggestions):
        lines.append("- No targeted fixes suggested by current discrepancy set.")

    out = review_dir / "review_report.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote review report to {rel(out, root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
