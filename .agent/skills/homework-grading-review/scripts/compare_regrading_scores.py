#!/usr/bin/env python3
"""Compare original grading with second-pass review grading.

The script writes only the high-difference summary CSV requested by the review
workflow and copies the matching original submission files into review/problem.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import shutil
import sys
from pathlib import Path
from typing import Any


CSV_FIELDS = [
    "student_id",
    "original_total",
    "review_total",
    "total_abs_diff",
    "total_pct_diff",
    "max_question_abs_diff",
    "changed_questions",
    "quantitative_flags",
    "difference_reason",
    "original_files",
    "copied_problem_files",
    "original_grading_json",
    "review_grading_json",
]


SUPPORTED_SUBMISSION_SUFFIXES = {
    ".pdf",
    ".docx",
    ".doc",
    ".jpg",
    ".jpeg",
    ".png",
    ".heic",
}


def fail(message: str, code: int = 1) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(code)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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


def extract_student_id(text: str) -> str:
    preferred = re.search(r"(?<!\d)(20\d{8})(?!\d)", text)
    if preferred:
        return preferred.group(1)
    fallback = re.search(r"(?<!\d)(\d{8,12})(?!\d)", text)
    return fallback.group(1) if fallback else ""


def grading_student_id(path: Path, grading: dict[str, Any]) -> str:
    for key in ("student_id", "id", "sid"):
        value = grading.get(key)
        if value:
            sid = extract_student_id(str(value))
            return sid or str(value).strip()
    stem = path.name.replace(".grading.json", "")
    return extract_student_id(stem) or stem


def get_questions(grading: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("results", "questions", "grading", "question_results"):
        value = grading.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def question_id(question: dict[str, Any]) -> str:
    return str(question.get("question_id") or question.get("id") or question.get("title") or "").strip()


def question_score(question: dict[str, Any]) -> float | None:
    for key in ("score", "score_awarded", "awarded_score", "points", "points_awarded"):
        number = as_float(question.get(key))
        if number is not None:
            return number
    return None


def question_max(question: dict[str, Any]) -> float | None:
    for key in ("max_score", "points", "score_max"):
        number = as_float(question.get(key))
        if number is not None:
            return number
    return None


def total_score(grading: dict[str, Any]) -> float | None:
    for key in ("total_score", "total", "score"):
        number = as_float(grading.get(key))
        if number is not None:
            return number
    scores = [question_score(question) for question in get_questions(grading)]
    if scores and all(score is not None for score in scores):
        return sum(score or 0.0 for score in scores)
    return None


def total_possible(root: Path, gradings: list[dict[str, Any]]) -> float | None:
    rubric_path = root / "work" / "rubric" / "rubric.json"
    if rubric_path.exists():
        try:
            rubric = load_json(rubric_path)
            questions = rubric.get("questions", []) if isinstance(rubric, dict) else []
            values = [as_float(question.get("max_score")) for question in questions if isinstance(question, dict)]
            if values and all(value is not None for value in values):
                return sum(value or 0.0 for value in values)
        except Exception:
            pass
    maxes: dict[str, float] = {}
    for grading in gradings:
        for question in get_questions(grading):
            qid = question_id(question)
            qmax = question_max(question)
            if qid and qmax is not None:
                maxes[qid] = max(maxes.get(qid, 0.0), qmax)
    return sum(maxes.values()) if maxes else None


def reason_text(question: dict[str, Any] | None) -> str:
    if not question:
        return ""
    pieces: list[str] = []
    for key in ("final_reason", "reason", "deduction_reason", "review_reason", "comment"):
        value = question.get(key)
        if value:
            pieces.append(str(value).strip())
    for detail in question.get("scoring_details", []) or []:
        if not isinstance(detail, dict):
            continue
        point = detail.get("point_id") or detail.get("id") or ""
        score = detail.get("score_awarded", detail.get("score", ""))
        reason = detail.get("reason") or detail.get("deduction_reason") or ""
        if reason:
            pieces.append(f"{point}({score}): {reason}".strip())
    return " | ".join(piece for piece in pieces if piece)


def load_grading_dir(path: Path) -> dict[str, tuple[Path, dict[str, Any]]]:
    rows: dict[str, tuple[Path, dict[str, Any]]] = {}
    for grading_path in sorted(path.glob("*.grading.json")):
        try:
            data = load_json(grading_path)
        except Exception as exc:
            print(f"WARNING: skipping unreadable grading JSON {grading_path}: {exc}", file=sys.stderr)
            continue
        if not isinstance(data, dict):
            continue
        sid = grading_student_id(grading_path, data)
        if sid:
            rows[sid] = (grading_path, data)
    return rows


def find_submission_files(homework_dir: Path, student_id: str) -> list[Path]:
    matches: list[Path] = []
    if not homework_dir.exists():
        return matches
    for path in sorted(homework_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUBMISSION_SUFFIXES:
            continue
        if extract_student_id(path.name) == student_id:
            matches.append(path)
    return matches


def copy_problem_files(files: list[Path], problem_dir: Path) -> list[Path]:
    problem_dir.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for source in files:
        target = problem_dir / source.name
        shutil.copy2(source, target)
        copied.append(target)
    return copied


def compare_student(
    root: Path,
    student_id: str,
    original_path: Path,
    original: dict[str, Any],
    review_path: Path,
    review: dict[str, Any],
    possible_total: float | None,
    args: argparse.Namespace,
) -> dict[str, Any] | None:
    original_total = total_score(original)
    review_total = total_score(review)
    if original_total is None or review_total is None:
        total_abs_diff = None
        total_pct_diff = None
    else:
        total_abs_diff = abs(review_total - original_total)
        denominator = possible_total or max(abs(original_total), abs(review_total), 1.0)
        total_pct_diff = total_abs_diff / denominator

    original_questions = {question_id(question): question for question in get_questions(original) if question_id(question)}
    review_questions = {question_id(question): question for question in get_questions(review) if question_id(question)}
    changed: list[str] = []
    reason_parts: list[str] = []
    max_question_diff = 0.0

    for qid in sorted(set(original_questions) | set(review_questions)):
        oq = original_questions.get(qid)
        rq = review_questions.get(qid)
        oscore = question_score(oq) if oq else None
        rscore = question_score(rq) if rq else None
        if oscore is None or rscore is None:
            changed.append(qid)
            reason_parts.append(f"{qid}: one pass is missing a numeric score")
            continue
        qdiff = abs(rscore - oscore)
        max_question_diff = max(max_question_diff, qdiff)
        qmax = question_max(rq or {}) or question_max(oq or {}) or 1.0
        if qdiff >= args.question_points_threshold or qdiff / max(qmax, 1.0) >= args.question_ratio_threshold:
            changed.append(qid)
            original_reason = reason_text(oq)
            review_reason = reason_text(rq)
            reason = f"{qid}: original={oscore:g}, review={rscore:g}, diff={qdiff:g}"
            if original_reason or review_reason:
                reason += f"; original_reason={original_reason[:180]}; review_reason={review_reason[:180]}"
            reason_parts.append(reason)

    flags: list[str] = []
    if total_abs_diff is None:
        flags.append("missing_total_score")
    elif total_abs_diff >= args.total_points_threshold:
        flags.append(f"total_abs_diff>={args.total_points_threshold:g}")
    if total_pct_diff is not None and total_pct_diff >= args.total_ratio_threshold:
        flags.append(f"total_pct_diff>={args.total_ratio_threshold:.0%}")
    if max_question_diff >= args.question_points_threshold:
        flags.append(f"question_abs_diff>={args.question_points_threshold:g}")
    if changed:
        flags.append(f"{len(changed)}_changed_questions")

    if not flags:
        return None

    if total_abs_diff is not None:
        reason_parts.insert(0, f"total: original={original_total:g}, review={review_total:g}, diff={total_abs_diff:g}")

    original_files = find_submission_files(root / args.homework_dir, student_id)
    copied_files = copy_problem_files(original_files, root / args.problem_dir)
    return {
        "student_id": student_id,
        "original_total": "" if original_total is None else f"{original_total:g}",
        "review_total": "" if review_total is None else f"{review_total:g}",
        "total_abs_diff": "" if total_abs_diff is None else f"{total_abs_diff:g}",
        "total_pct_diff": "" if total_pct_diff is None else f"{total_pct_diff:.4f}",
        "max_question_abs_diff": f"{max_question_diff:g}",
        "changed_questions": "; ".join(changed),
        "quantitative_flags": "; ".join(flags),
        "difference_reason": " || ".join(reason_parts),
        "original_files": "; ".join(rel(path, root) for path in original_files),
        "copied_problem_files": "; ".join(rel(path, root) for path in copied_files),
        "original_grading_json": rel(original_path, root),
        "review_grading_json": rel(review_path, root),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="List large score differences between original and review grading.")
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument("--original-dir", default="work/grading", help="Existing grading JSON directory")
    parser.add_argument("--review-dir", default="work/review/regrading", help="Second-pass review grading JSON directory")
    parser.add_argument("--homework-dir", default="hw", help="Original homework submission directory")
    parser.add_argument("--out-csv", default="work/review/score_discrepancies.csv", help="Output CSV for large score differences")
    parser.add_argument("--problem-dir", default="work/review/problem", help="Directory for copied original submissions with large score differences")
    parser.add_argument("--total-points-threshold", type=float, default=2.0, help="Flag if absolute total-score difference is at least this many points")
    parser.add_argument("--total-ratio-threshold", type=float, default=0.05, help="Flag if total-score difference is at least this fraction of total possible score")
    parser.add_argument("--question-points-threshold", type=float, default=1.0, help="Flag if any question-score difference is at least this many points")
    parser.add_argument("--question-ratio-threshold", type=float, default=0.20, help="Flag if any question-score difference is at least this fraction of that question's max score")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    original_dir = root / args.original_dir
    review_dir = root / args.review_dir
    if not original_dir.exists():
        fail(f"Original grading directory not found: {rel(original_dir, root)}")
    if not review_dir.exists():
        fail(f"Second-pass review grading directory not found: {rel(review_dir, root)}")

    original_rows = load_grading_dir(original_dir)
    review_rows = load_grading_dir(review_dir)
    if not original_rows:
        fail(f"No readable *.grading.json files found in {rel(original_dir, root)}")
    if not review_rows:
        fail(f"No readable *.grading.json files found in {rel(review_dir, root)}")

    possible_total = total_possible(root, [grading for _, grading in [*original_rows.values(), *review_rows.values()]])
    rows: list[dict[str, Any]] = []
    for student_id in sorted(set(original_rows) & set(review_rows)):
        original_path, original = original_rows[student_id]
        review_path, review = review_rows[student_id]
        row = compare_student(root, student_id, original_path, original, review_path, review, possible_total, args)
        if row:
            rows.append(row)

    out_csv = root / args.out_csv
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    missing_review = sorted(set(original_rows) - set(review_rows))
    missing_original = sorted(set(review_rows) - set(original_rows))
    print(f"Compared {len(set(original_rows) & set(review_rows))} students.")
    print(f"Wrote {len(rows)} large-difference rows to {rel(out_csv, root)}")
    print(f"Copied problem submissions to {args.problem_dir}")
    if missing_review:
        print(f"WARNING: {len(missing_review)} original students have no second-pass grading.", file=sys.stderr)
    if missing_original:
        print(f"WARNING: {len(missing_original)} second-pass students have no original grading.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
