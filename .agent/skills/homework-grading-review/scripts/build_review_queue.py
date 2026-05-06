#!/usr/bin/env python3
"""Build a reviewed human-review queue from grading audit artifacts."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


FIELDS = ["student_id", "student_name", "source_file", "reason", "issue_types", "severity", "suggested_action"]
HIGH_RISK_TYPES = {
    "MISSING_GRADING_JSON",
    "MISSING_ANSWERS_JSON",
    "MISSING_SUMMARY_ROW",
    "DUPLICATE_STUDENT_ID",
    "NAME_ID_MISMATCH",
    "QUESTION_SCORE_MISMATCH",
    "TOTAL_SCORE_MISMATCH",
    "SCORE_OUT_OF_RANGE",
    "MISSING_DEDUCTION_REASON",
    "MISSING_EVIDENCE",
    "RUBRIC_POINT_NOT_FOUND",
    "REVIEW_QUEUE_MISSING",
    "OCR_UNCERTAIN_NOT_FLAGGED",
}


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


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def stringify(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value


def uncertain_text(text: str) -> bool:
    lower = text.lower()
    keywords = ["ocr", "unreadable", "too little", "too short", "missing answer", "alignment", "uncertain", "扫描", "不可读", "缺失", "过少"]
    return any(keyword in lower for keyword in keywords)


def row_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (str(row.get("student_id", "")), str(row.get("issue_types", "")), str(row.get("reason", ""))[:120])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Repository root")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    review_dir = root / "work" / "review"
    rows: list[dict[str, Any]] = []

    original_queue = root / "work" / "reports" / "review_queue.csv"
    for row in read_csv(original_queue):
        rows.append(
            {
                "student_id": row.get("student_id", ""),
                "student_name": row.get("student_name", "") or row.get("name", ""),
                "source_file": row.get("source_file", rel(original_queue, root)),
                "reason": row.get("reason", "Original review_queue.csv item."),
                "issue_types": "ORIGINAL_REVIEW_QUEUE",
                "severity": "WARNING",
                "suggested_action": "Manually review original queued item.",
            }
        )

    for disc in read_csv(review_dir / "discrepancies.csv"):
        issue_type = disc.get("issue_type", "")
        needs_human = str(disc.get("needs_human_review", "")).lower() == "true"
        if needs_human or issue_type in HIGH_RISK_TYPES or disc.get("severity") in {"ERROR", "CRITICAL"}:
            rows.append(
                {
                    "student_id": disc.get("student_id", ""),
                    "student_name": disc.get("student_name", ""),
                    "source_file": disc.get("file", ""),
                    "reason": disc.get("explanation", ""),
                    "issue_types": issue_type,
                    "severity": disc.get("severity", "WARNING"),
                    "suggested_action": disc.get("suggested_action", "Manually review this discrepancy."),
                }
            )

    for path in sorted((review_dir / "student_review").glob("*.review.json")):
        try:
            review = load_json(path)
        except Exception:
            continue
        if review.get("needs_human_review") or review.get("review_status") in {"NEEDS_FIX", "NEEDS_HUMAN_REVIEW"}:
            comments = "; ".join(review.get("review_comments", [])[:4])
            rows.append(
                {
                    "student_id": review.get("student_id", ""),
                    "student_name": review.get("student_name", ""),
                    "source_file": review.get("grading_json_path", rel(path, root)),
                    "reason": comments or f"Student review status is {review.get('review_status')}.",
                    "issue_types": review.get("review_status", "STUDENT_REVIEW"),
                    "severity": "ERROR" if review.get("review_status") == "NEEDS_FIX" else "WARNING",
                    "suggested_action": "Inspect student review JSON and resolve listed issues.",
                }
            )

    answers_dir = root / "work" / "answers"
    grading_ids = {path.name.replace(".grading.json", "") for path in (root / "work" / "grading").glob("*.grading.json")}
    answer_ids = {path.name.replace(".answers.json", "") for path in answers_dir.glob("*.answers.json")}
    for sid in sorted(grading_ids - answer_ids):
        rows.append(
            {
                "student_id": sid,
                "student_name": "",
                "source_file": rel(root / "work" / "grading" / f"{sid}.grading.json", root),
                "reason": "Missing answers JSON for an existing grading JSON.",
                "issue_types": "MISSING_ANSWERS_JSON",
                "severity": "ERROR",
                "suggested_action": "Recover or regenerate answers JSON before finalizing.",
            }
        )

    for path in sorted(answers_dir.glob("*.answers.json")):
        sid = path.name.replace(".answers.json", "")
        try:
            data = load_json(path)
        except Exception:
            rows.append(
                {
                    "student_id": sid,
                    "student_name": "",
                    "source_file": rel(path, root),
                    "reason": "Answers JSON is not parseable.",
                    "issue_types": "MISSING_ANSWERS_JSON",
                    "severity": "ERROR",
                    "suggested_action": "Regenerate or manually inspect extracted answers.",
                }
            )
            continue
        text = stringify(data)
        if len(text.strip()) < 120 or uncertain_text(text):
            rows.append(
                {
                    "student_id": sid,
                    "student_name": str(data.get("student_name", "") if isinstance(data, dict) else ""),
                    "source_file": rel(path, root),
                    "reason": "Answers extraction appears short, missing, OCR-uncertain, or alignment-uncertain.",
                    "issue_types": "OCR_UNCERTAIN_NOT_FLAGGED",
                    "severity": "WARNING",
                    "suggested_action": "Compare extracted answers with source submission and confirm grading basis.",
                }
            )

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    severity_order = {"CRITICAL": 0, "ERROR": 1, "WARNING": 2, "INFO": 3}
    for row in sorted(rows, key=lambda item: (severity_order.get(str(item.get("severity")), 9), str(item.get("student_id", "")))):
        key = row_key(row)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)

    out = review_dir / "review_queue_reviewed.csv"
    write_csv(out, deduped)
    print(f"Wrote {len(deduped)} reviewed queue rows to {rel(out, root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
