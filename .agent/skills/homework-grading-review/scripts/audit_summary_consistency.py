#!/usr/bin/env python3
"""Compare summary/grades CSV files with grading JSON outputs."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
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


def as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig", errors="replace") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def make_disc(severity: str, sid: str, name: str, file: str, issue_type: str, location: str, current: Any, expected: Any, explanation: str, action: str, human: bool) -> dict[str, str]:
    return {
        "severity": severity,
        "student_id": sid,
        "student_name": name,
        "file": file,
        "issue_type": issue_type,
        "location": location,
        "current_value": "" if current is None else str(current),
        "expected_value": "" if expected is None else str(expected),
        "explanation": explanation,
        "suggested_action": action,
        "needs_human_review": str(bool(human)).lower(),
    }


def get_questions(grading: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("questions", "results", "grading", "question_results"):
        value = grading.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def q_score(question: dict[str, Any]) -> float | None:
    for key in ("score", "score_awarded", "awarded_score", "points", "points_awarded"):
        number = as_float(question.get(key))
        if number is not None:
            return number
    return None


def q_max(question: dict[str, Any]) -> float | None:
    for key in ("max_score", "points"):
        number = as_float(question.get(key))
        if number is not None:
            return number
    return None


def grading_rows(root: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for path in sorted((root / "work" / "grading").glob("*.grading.json")):
        try:
            data = load_json(path)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        sid = str(data.get("student_id") or path.name.replace(".grading.json", ""))
        name = str(data.get("student_name") or data.get("name") or "")
        questions = get_questions(data)
        scores = {str(q.get("question_id") or q.get("id") or q.get("title") or ""): q_score(q) for q in questions}
        maxes = {str(q.get("question_id") or q.get("id") or q.get("title") or ""): q_max(q) for q in questions}
        total = as_float(data.get("total_score") or data.get("total") or data.get("score"))
        recomputed = sum(value or 0.0 for value in scores.values() if value is not None)
        deductions: list[str] = []
        for q in questions:
            qid = str(q.get("question_id") or q.get("id") or q.get("title") or "")
            score = q_score(q)
            maximum = q_max(q)
            if score is not None and maximum is not None and score < maximum - 1e-9:
                reason = str(q.get("final_reason") or q.get("reason") or q.get("deduction_reason") or "")
                if reason:
                    deductions.append(f"{qid}: {reason}")
        rows[sid] = {
            "student_id": sid,
            "student_name": name,
            "path": path,
            "scores": scores,
            "maxes": maxes,
            "total": total,
            "recomputed_total": round(recomputed, 6),
            "deduction_reason": "; ".join(deductions),
        }
    return rows


def id_value(row: dict[str, str]) -> str:
    for key in ("student_id", "id", "sid", "学号"):
        if key in row and row[key]:
            return str(row[key]).strip()
    return ""


def name_value(row: dict[str, str]) -> str:
    for key in ("student_name", "name", "姓名"):
        if key in row and row[key]:
            return str(row[key]).strip()
    return ""


def total_value(row: dict[str, str]) -> float | None:
    for key in ("total", "total_score", "score", "总分"):
        if key in row:
            return as_float(row.get(key))
    return None


def append_discrepancies(path: Path, rows: list[dict[str, str]]) -> None:
    existing: list[dict[str, str]] = []
    if path.exists():
        with path.open("r", newline="", encoding="utf-8-sig", errors="replace") as handle:
            existing = list(csv.DictReader(handle))
    combined = existing + rows
    seen: set[tuple[str, str, str, str, str]] = set()
    deduped: list[dict[str, str]] = []
    for row in combined:
        key = (row.get("student_id", ""), row.get("file", ""), row.get("issue_type", ""), row.get("location", ""), row.get("explanation", ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append({field: row.get(field, "") for field in DISCREPANCY_FIELDS})
    write_csv(path, deduped, DISCREPANCY_FIELDS)


def update_student_reviews(root: Path, report_rows: dict[str, dict[str, str]], report_path: Path) -> None:
    review_dir = root / "work" / "review" / "student_review"
    for path in review_dir.glob("*.review.json"):
        try:
            review = load_json(path)
        except Exception:
            continue
        sid = str(review.get("student_id") or path.name.replace(".review.json", ""))
        row = report_rows.get(sid)
        if not row:
            continue
        review["summary_row"] = row
        review["total_score_from_summary"] = total_value(row)
        review.setdefault("source_files", {})["summary_csv_path"] = rel(report_path, root)
        grading_total = review.get("total_score_from_grading")
        summary_total = review.get("total_score_from_summary")
        if grading_total is not None and summary_total is not None and abs(float(grading_total) - float(summary_total)) > 1e-6:
            review["score_consistency_status"] = "MISMATCH"
            review["review_status"] = "NEEDS_FIX"
            review.setdefault("review_comments", []).append("Summary total differs from grading JSON total.")
        grading_name = str(review.get("student_name") or "")
        summary_name = name_value(row)
        if grading_name and summary_name and grading_name != summary_name:
            review["identity_consistency_status"] = "MISMATCH"
            review["needs_human_review"] = True
            review["review_status"] = "NEEDS_HUMAN_REVIEW"
            review.setdefault("review_comments", []).append("Student name differs between summary row and grading JSON.")
        elif summary_name or grading_name:
            review["identity_consistency_status"] = "PASS"
        path.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")


def audit_report(root: Path, report_path: Path, grading: dict[str, dict[str, Any]], question_ids: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, str]], dict[str, dict[str, str]]]:
    report_rel = rel(report_path, root)
    rows = read_csv(report_path)
    row_by_id: dict[str, dict[str, str]] = {}
    discrepancies: list[dict[str, str]] = []
    consistency_rows: list[dict[str, Any]] = []

    ids = [id_value(row) for row in rows if id_value(row)]
    duplicates = {sid for sid, count in Counter(ids).items() if count > 1}
    for sid in duplicates:
        discrepancies.append(make_disc("CRITICAL", sid, "", report_rel, "DUPLICATE_STUDENT_ID", "student_id", sid, "unique student_id", "Report contains duplicate student_id rows.", "Resolve duplicated or shifted report rows.", True))

    for row in rows:
        sid = id_value(row)
        if sid and sid not in row_by_id:
            row_by_id[sid] = row
        name = name_value(row)
        status = "PASS"
        notes: list[str] = []
        if not sid:
            status = "NEEDS_HUMAN_REVIEW"
            notes.append("Missing student_id in report row.")
            discrepancies.append(make_disc("ERROR", "", name, report_rel, "NAME_ID_MISMATCH", "student_id", "", "student_id", "Report row is missing student_id.", "Recover or remove the row after manual review.", True))
            continue
        grow = grading.get(sid)
        if not grow:
            status = "NEEDS_HUMAN_REVIEW"
            notes.append("Missing grading JSON for report row.")
            discrepancies.append(make_disc("ERROR", sid, name, report_rel, "MISSING_GRADING_JSON", sid, "report row only", "grading JSON", "Report contains a student with no grading JSON.", "Locate or regenerate grading JSON.", True))
        else:
            gname = str(grow.get("student_name") or "")
            if gname and name and gname != name:
                status = "NEEDS_HUMAN_REVIEW"
                notes.append("Name mismatch.")
                discrepancies.append(make_disc("CRITICAL", sid, name, report_rel, "NAME_ID_MISMATCH", "name", name, gname, "Student name differs between report and grading JSON.", "Check whether rows are shifted or mislabeled.", True))
            for qid in question_ids:
                if qid not in row:
                    continue
                report_score = as_float(row.get(qid))
                grading_score = grow["scores"].get(qid)
                if report_score is None and grading_score is None:
                    continue
                if report_score is None or grading_score is None or abs(report_score - grading_score) > 1e-6:
                    status = "NEEDS_FIX"
                    notes.append(f"{qid} score mismatch.")
                    discrepancies.append(make_disc("ERROR", sid, name, report_rel, "QUESTION_SCORE_MISMATCH", qid, report_score, grading_score, "Report question score differs from grading JSON.", "Regenerate reviewed grades from grading JSON after review.", True))
            report_total = total_value(row)
            grading_total = grow.get("total")
            recomputed = grow.get("recomputed_total")
            expected_total = grading_total if grading_total is not None else recomputed
            if report_total is None and expected_total is not None:
                status = "NEEDS_FIX"
                notes.append("Report total missing.")
                discrepancies.append(make_disc("ERROR", sid, name, report_rel, "TOTAL_SCORE_MISMATCH", "total", "", expected_total, "Report total is missing.", "Regenerate report total.", True))
            elif report_total is not None and expected_total is not None and abs(report_total - float(expected_total)) > 1e-6:
                status = "NEEDS_FIX"
                notes.append("Total mismatch.")
                discrepancies.append(make_disc("ERROR", sid, name, report_rel, "TOTAL_SCORE_MISMATCH", "total", report_total, expected_total, "Report total differs from grading JSON.", "Regenerate report from reviewed grading data.", True))
            if grow.get("deduction_reason") and not str(row.get("deduction_reason") or "").strip():
                status = "MINOR_ISSUES" if status == "PASS" else status
                notes.append("Deduction reason missing from report row.")
                discrepancies.append(make_disc("WARNING", sid, name, report_rel, "MISSING_DEDUCTION_REASON", "deduction_reason", "", "deduction reason summary", "Report row omits deduction reasons present in grading JSON.", "Copy or summarize deduction reasons in reviewed grades.", False))

        consistency_rows.append({"report": report_path.name, "student_id": sid, "student_name": name, "status": status, "notes": "; ".join(notes)})

    for sid, grow in grading.items():
        if sid not in row_by_id:
            discrepancies.append(make_disc("ERROR", sid, str(grow.get("student_name") or ""), report_rel, "MISSING_SUMMARY_ROW", sid, "missing", "present", "Grading JSON has no matching report row.", "Add this student to reviewed grades and check original reports.", True))
            consistency_rows.append({"report": report_path.name, "student_id": sid, "student_name": grow.get("student_name", ""), "status": "NEEDS_FIX", "notes": "Grading JSON missing from report."})

    return consistency_rows, discrepancies, row_by_id


def build_reviewed_grades(root: Path, grading: dict[str, dict[str, Any]], report_rows: dict[str, dict[str, str]], question_ids: list[str]) -> None:
    review_dir = root / "work" / "review"
    fields = ["name", "student_id", *question_ids, "total", "reviewed_total", "review_status", "needs_human_review", "review_comments", "source"]
    rows: list[dict[str, Any]] = []
    review_json_dir = review_dir / "student_review"
    for sid in sorted(set(grading) | set(report_rows)):
        grow = grading.get(sid)
        report = report_rows.get(sid, {})
        row: dict[str, Any] = {
            "name": (grow or {}).get("student_name") or name_value(report),
            "student_id": sid,
            "total": total_value(report) if report else (grow or {}).get("total"),
            "reviewed_total": (grow or {}).get("recomputed_total") if grow else total_value(report),
            "source": "grading_json" if grow else "report_only",
        }
        for qid in question_ids:
            value = (grow or {}).get("scores", {}).get(qid)
            row[qid] = value if value is not None else report.get(qid, "")
        review_path = review_json_dir / f"{sid}.review.json"
        if review_path.exists():
            try:
                review = load_json(review_path)
                row["review_status"] = review.get("review_status", "")
                row["needs_human_review"] = review.get("needs_human_review", "")
                row["review_comments"] = "; ".join(review.get("review_comments", [])[:3])
            except Exception:
                row["review_status"] = ""
                row["needs_human_review"] = ""
                row["review_comments"] = ""
        rows.append(row)
    write_csv(review_dir / "reviewed_grades.csv", rows, fields)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Repository root")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    review_dir = root / "work" / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    grading = grading_rows(root)

    rubric_path = root / "work" / "rubric" / "rubric.json"
    question_ids: list[str] = []
    if rubric_path.exists():
        rubric = load_json(rubric_path)
        if isinstance(rubric, dict) and isinstance(rubric.get("questions"), list):
            question_ids = [str(q.get("question_id") or q.get("id") or q.get("title")) for q in rubric["questions"] if isinstance(q, dict)]
    if not question_ids:
        question_ids = sorted({qid for row in grading.values() for qid in row["scores"] if qid})

    reports = [path for path in [root / "work" / "reports" / "summary.csv", root / "work" / "reports" / "grades.csv"] if path.exists()]
    all_consistency: list[dict[str, Any]] = []
    all_discrepancies: list[dict[str, str]] = []
    preferred_rows: dict[str, dict[str, str]] = {}
    preferred_path: Path | None = None
    for report_path in reports:
        consistency, discrepancies, rows = audit_report(root, report_path, grading, question_ids)
        all_consistency.extend(consistency)
        all_discrepancies.extend(discrepancies)
        if preferred_path is None:
            preferred_path = report_path
            preferred_rows = rows

    write_csv(review_dir / "summary_consistency.csv", all_consistency, ["report", "student_id", "student_name", "status", "notes"])
    append_discrepancies(review_dir / "discrepancies.csv", all_discrepancies)
    if preferred_path:
        update_student_reviews(root, preferred_rows, preferred_path)
    build_reviewed_grades(root, grading, preferred_rows, question_ids)

    print(f"Compared {len(reports)} report CSV files with {len(grading)} grading JSON files.")
    print(f"Wrote {rel(review_dir / 'summary_consistency.csv', root)}")
    print(f"Wrote {rel(review_dir / 'reviewed_grades.csv', root)}")
    print(f"Updated {rel(review_dir / 'discrepancies.csv', root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
