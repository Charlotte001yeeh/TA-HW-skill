#!/usr/bin/env python3
"""Audit grading JSON files against rubric structure and score arithmetic."""

from __future__ import annotations

import argparse
import csv
import json
import math
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

GENERIC_REASONS = {
    "答案不完整",
    "错了",
    "扣分",
    "缺少步骤",
    "incomplete",
    "wrong",
    "deducted",
    "missing steps",
    "not enough",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def get_questions(grading: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("questions", "results", "grading", "question_results"):
        value = grading.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def get_details(question: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("scoring_details", "scoring_points", "details", "rubric_results"):
        value = question.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def question_score(question: dict[str, Any]) -> float | None:
    for key in ("score", "score_awarded", "awarded_score", "points", "points_awarded"):
        number = as_float(question.get(key))
        if number is not None:
            return number
    return None


def detail_score(detail: dict[str, Any]) -> float | None:
    for key in ("score_awarded", "score", "awarded_score", "points", "points_awarded"):
        number = as_float(detail.get(key))
        if number is not None:
            return number
    return None


def max_score(question: dict[str, Any], rubric_question: dict[str, Any] | None) -> float | None:
    for source in (question, rubric_question or {}):
        for key in ("max_score", "points", "score"):
            number = as_float(source.get(key))
            if number is not None:
                return number
    return None


def reason_text(question: dict[str, Any], detail: dict[str, Any] | None = None) -> str:
    pieces: list[str] = []
    if detail:
        for key in ("reason", "deduction_reason", "explanation", "comment"):
            value = detail.get(key)
            if value:
                pieces.append(str(value))
    for key in ("final_reason", "reason", "deduction_reason", "review_reason"):
        value = question.get(key)
        if value:
            pieces.append(str(value))
    return " ".join(pieces).strip()


def evidence_text(detail: dict[str, Any]) -> str:
    for key in ("evidence", "student_evidence", "answer_excerpt", "excerpt", "student_answer"):
        value = detail.get(key)
        if value:
            return str(value).strip()
    return ""


def unclear_reason(text: str) -> bool:
    stripped = " ".join(text.split()).strip()
    if not stripped:
        return True
    lower = stripped.lower()
    if lower in GENERIC_REASONS:
        return True
    return len(stripped) < 8


def make_disc(
    severity: str,
    student_id: str,
    student_name: str,
    file: str,
    issue_type: str,
    location: str,
    current: Any,
    expected: Any,
    explanation: str,
    action: str,
    human: bool,
) -> dict[str, str]:
    return {
        "severity": severity,
        "student_id": student_id,
        "student_name": student_name,
        "file": file,
        "issue_type": issue_type,
        "location": location,
        "current_value": "" if current is None else str(current),
        "expected_value": "" if expected is None else str(expected),
        "explanation": explanation,
        "suggested_action": action,
        "needs_human_review": str(bool(human)).lower(),
    }


def rubric_maps(rubric: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, set[str]]]:
    questions = rubric.get("questions", [])
    qmap: dict[str, dict[str, Any]] = {}
    pmap: dict[str, set[str]] = {}
    if isinstance(questions, list):
        for question in questions:
            if not isinstance(question, dict):
                continue
            qid = str(question.get("question_id") or question.get("id") or question.get("title") or "")
            if not qid:
                continue
            qmap[qid] = question
            points = question.get("scoring_points") or question.get("points") or []
            pmap[qid] = {
                str(point.get("point_id") or point.get("id"))
                for point in points
                if isinstance(point, dict) and (point.get("point_id") or point.get("id"))
            }
    return qmap, pmap


def audit_one(path: Path, root: Path, rubric_q: dict[str, dict[str, Any]], rubric_points: dict[str, set[str]]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    file_rel = rel(path, root)
    discrepancies: list[dict[str, str]] = []
    try:
        grading = load_json(path)
    except Exception as exc:  # noqa: BLE001
        student_id = path.name.replace(".grading.json", "")
        review = {
            "student_id": student_id,
            "student_name": "",
            "source_files": {"grading_json_path": file_rel},
            "grading_json_path": file_rel,
            "answers_json_path": "",
            "summary_row": None,
            "total_score_from_grading": None,
            "total_score_from_summary": None,
            "recomputed_total": None,
            "score_consistency_status": "INVALID",
            "identity_consistency_status": "UNKNOWN",
            "question_reviews": [],
            "needs_human_review": True,
            "review_status": "NEEDS_HUMAN_REVIEW",
            "review_comments": [f"Cannot parse grading JSON: {exc}"],
            "suggested_total_score": None,
            "reviewer_notes": "",
        }
        discrepancies.append(make_disc("CRITICAL", student_id, "", file_rel, "MISSING_GRADING_JSON", "json", "invalid", "valid JSON", str(exc), "Regenerate or manually repair this grading JSON.", True))
        return review, discrepancies

    student_id = str(grading.get("student_id") or path.name.replace(".grading.json", ""))
    student_name = str(grading.get("student_name") or grading.get("name") or "")
    questions = get_questions(grading)
    seen_qids: set[str] = set()
    question_reviews: list[dict[str, Any]] = []
    recomputed_total = 0.0
    fatal_or_fix = False
    minor = False
    human = bool(grading.get("needs_human_review", False))
    comments: list[str] = []

    if not student_id:
        fatal_or_fix = True
        discrepancies.append(make_disc("ERROR", "", student_name, file_rel, "NAME_ID_MISMATCH", "student_id", "", "student_id", "Grading JSON is missing student_id.", "Recover student_id from file name or source records.", True))
    if not questions:
        fatal_or_fix = True
        discrepancies.append(make_disc("ERROR", student_id, student_name, file_rel, "RUBRIC_POINT_NOT_FOUND", "questions", "", "question list", "Grading JSON has no questions/results list.", "Regenerate grading details.", True))

    for question in questions:
        qid = str(question.get("question_id") or question.get("id") or question.get("title") or "")
        seen_qids.add(qid)
        rq = rubric_q.get(qid)
        qmax = max_score(question, rq)
        score = question_score(question)
        details = get_details(question)
        q_issues: list[str] = []
        score_status = "PASS"
        rubric_status = "PASS"
        evidence_status = "PASS"
        reason_status = "NOT_APPLICABLE"

        if not qid or rq is None:
            rubric_status = "QUESTION_NOT_IN_RUBRIC"
            q_issues.append("Question is not present in rubric.")
            fatal_or_fix = True
            discrepancies.append(make_disc("ERROR", student_id, student_name, file_rel, "RUBRIC_POINT_NOT_FOUND", qid or "question_id", qid, "rubric question_id", "Question cannot be aligned to rubric.", "Check question IDs and rubric.", True))

        if score is None:
            score_status = "MISSING"
            q_issues.append("Question score is missing or nonnumeric.")
            fatal_or_fix = True
            discrepancies.append(make_disc("ERROR", student_id, student_name, file_rel, "QUESTION_SCORE_MISMATCH", qid, question.get("score"), "numeric score", "Question score cannot be parsed.", "Repair or regenerate question score.", True))
        else:
            recomputed_total += score
            if qmax is not None and (score < -1e-9 or score > qmax + 1e-9):
                score_status = "OUT_OF_RANGE"
                q_issues.append("Question score is outside [0, max_score].")
                fatal_or_fix = True
                discrepancies.append(make_disc("ERROR", student_id, student_name, file_rel, "SCORE_OUT_OF_RANGE", qid, score, f"0..{qmax}", "Question score is outside the legal range.", "Manually review and correct this score.", True))

        detail_sum_values = [detail_score(detail) for detail in details]
        if details and all(value is not None for value in detail_sum_values) and score is not None:
            detail_sum = sum(value or 0.0 for value in detail_sum_values)
            if abs(detail_sum - score) > 1e-6:
                score_status = "MISMATCH"
                q_issues.append("Question score does not equal scoring detail sum.")
                fatal_or_fix = True
                discrepancies.append(make_disc("ERROR", student_id, student_name, file_rel, "QUESTION_SCORE_MISMATCH", qid, score, detail_sum, "Question score differs from scoring detail sum.", "Reconcile question score with scoring details.", True))

        valid_points = rubric_points.get(qid, set())
        for detail in details:
            point_id = str(detail.get("point_id") or detail.get("id") or "")
            if valid_points and point_id and point_id not in valid_points:
                rubric_status = "MISSING_RUBRIC_POINT"
                q_issues.append(f"Scoring point {point_id} is not in rubric.")
                fatal_or_fix = True
                discrepancies.append(make_disc("ERROR", student_id, student_name, file_rel, "RUBRIC_POINT_NOT_FOUND", f"{qid}/{point_id}", point_id, "rubric scoring point", "Scoring detail references an unknown rubric point.", "Check rubric alignment.", True))

            evidence = evidence_text(detail)
            if not evidence:
                evidence_status = "MISSING"
                q_issues.append("Scoring detail has no student-answer evidence.")
                minor = True
                discrepancies.append(make_disc("WARNING", student_id, student_name, file_rel, "MISSING_EVIDENCE", f"{qid}/{point_id}", "", "student evidence", "Scoring point lacks evidence or answer excerpt.", "Add evidence or cite extracted answer text.", True))
            elif "see extracted text" in evidence.lower() or "keyword-based evidence" in evidence.lower():
                if evidence_status != "MISSING":
                    evidence_status = "WEAK"
                q_issues.append("Evidence is a weak pointer rather than a concrete excerpt.")
                minor = True

        if score is not None and qmax is not None and score < qmax - 1e-9:
            reason = reason_text(question)
            if not reason:
                reason_status = "MISSING"
                q_issues.append("Deduction reason is missing.")
                fatal_or_fix = True
                discrepancies.append(make_disc("ERROR", student_id, student_name, file_rel, "MISSING_DEDUCTION_REASON", qid, "", "specific deduction reason", "A non-full score has no deduction reason.", "Add a rubric-specific deduction reason.", True))
            elif unclear_reason(reason):
                reason_status = "UNCLEAR"
                q_issues.append("Deduction reason is too generic or unclear.")
                minor = True
                discrepancies.append(make_disc("WARNING", student_id, student_name, file_rel, "UNCLEAR_DEDUCTION_REASON", qid, reason, "specific deduction reason", "Deduction reason is not audit-ready.", "Replace with a rubric-specific explanation.", True))
            else:
                reason_status = "PASS"

        if rq and (rq.get("needs_teacher_review") or "inferred" in str(rq.get("rubric_source", "")).lower()):
            human = True
            comments.append(f"{qid}: rubric is inferred or marked for teacher review.")

        if question.get("needs_human_review"):
            human = True
        elif q_issues and any("missing" in issue.lower() or "outside" in issue.lower() or "cannot" in issue.lower() for issue in q_issues):
            discrepancies.append(make_disc("WARNING", student_id, student_name, file_rel, "REVIEW_QUEUE_MISSING", qid, "needs_human_review=false", "needs_human_review=true", "Question has high-risk issues but is not flagged for human review.", "Add this student/question to review queue.", True))
            human = True

        question_reviews.append(
            {
                "question_id": qid,
                "max_score": qmax,
                "score_awarded": score,
                "recomputed_score": sum(value or 0.0 for value in detail_sum_values) if details and all(value is not None for value in detail_sum_values) else score,
                "score_status": score_status,
                "rubric_alignment_status": rubric_status,
                "evidence_status": evidence_status,
                "deduction_reason_status": reason_status,
                "issues": q_issues,
                "suggested_fix": "Review this question manually." if q_issues else "",
            }
        )

    for qid in sorted(set(rubric_q) - seen_qids):
        fatal_or_fix = True
        human = True
        question_reviews.append(
            {
                "question_id": qid,
                "max_score": as_float(rubric_q[qid].get("max_score")),
                "score_awarded": None,
                "recomputed_score": None,
                "score_status": "MISSING",
                "rubric_alignment_status": "PASS",
                "evidence_status": "UNKNOWN",
                "deduction_reason_status": "MISSING",
                "issues": ["Rubric question is missing from grading JSON."],
                "suggested_fix": "Regenerate or manually add this question's grading record.",
            }
        )
        discrepancies.append(make_disc("ERROR", student_id, student_name, file_rel, "QUESTION_SCORE_MISMATCH", qid, "missing", "present in grading JSON", "Rubric question is missing from grading JSON.", "Review and repair grading JSON.", True))

    total_from_grading = as_float(grading.get("total_score") or grading.get("total") or grading.get("score"))
    score_consistency = "PASS"
    if total_from_grading is None:
        score_consistency = "MISSING"
        fatal_or_fix = True
        discrepancies.append(make_disc("ERROR", student_id, student_name, file_rel, "TOTAL_SCORE_MISMATCH", "total_score", "", round(recomputed_total, 6), "Total score is missing.", "Set total_score to the sum of question scores.", True))
    elif abs(total_from_grading - recomputed_total) > 1e-6:
        score_consistency = "MISMATCH"
        fatal_or_fix = True
        discrepancies.append(make_disc("ERROR", student_id, student_name, file_rel, "TOTAL_SCORE_MISMATCH", "total_score", total_from_grading, round(recomputed_total, 6), "Total score does not equal the sum of question scores.", "Recompute total from question scores.", True))

    if human:
        status = "NEEDS_HUMAN_REVIEW"
    elif fatal_or_fix:
        status = "NEEDS_FIX"
    elif minor:
        status = "MINOR_ISSUES"
    else:
        status = "PASS"

    if not comments and status == "PASS":
        comments.append("No grading JSON issues found.")
    elif fatal_or_fix:
        comments.append("One or more score, total, or rubric-alignment issues require correction.")
    elif minor:
        comments.append("Minor auditability issues found; scores appear arithmetically usable.")

    answers_path = root / "work" / "answers" / f"{student_id}.answers.json"
    review = {
        "student_id": student_id,
        "student_name": student_name,
        "source_files": {
            "grading_json_path": file_rel,
            "answers_json_path": rel(answers_path, root) if answers_path.exists() else "",
        },
        "grading_json_path": file_rel,
        "answers_json_path": rel(answers_path, root) if answers_path.exists() else "",
        "summary_row": None,
        "total_score_from_grading": total_from_grading,
        "total_score_from_summary": None,
        "recomputed_total": round(recomputed_total, 6),
        "score_consistency_status": score_consistency,
        "identity_consistency_status": "UNKNOWN",
        "question_reviews": question_reviews,
        "needs_human_review": human,
        "review_status": status,
        "review_comments": sorted(set(comments)),
        "suggested_total_score": round(recomputed_total, 6) if total_from_grading is None or score_consistency == "MISMATCH" else total_from_grading,
        "reviewer_notes": "",
    }
    return review, discrepancies


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument("--student-id", help="Audit one student ID only")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    rubric_path = root / "work" / "rubric" / "rubric.json"
    grading_dir = root / "work" / "grading"
    review_dir = root / "work" / "review"
    student_review_dir = review_dir / "student_review"
    review_dir.mkdir(parents=True, exist_ok=True)
    student_review_dir.mkdir(parents=True, exist_ok=True)

    rubric = load_json(rubric_path) if rubric_path.exists() else {}
    rubric_q, rubric_points = rubric_maps(rubric if isinstance(rubric, dict) else {})
    paths = sorted(grading_dir.glob("*.grading.json"))
    if args.student_id:
        paths = [path for path in paths if path.name == f"{args.student_id}.grading.json"]

    all_discrepancies: list[dict[str, str]] = []
    for path in paths:
        review, discrepancies = audit_one(path, root, rubric_q, rubric_points)
        all_discrepancies.extend(discrepancies)
        out = student_review_dir / f"{review['student_id']}.review.json"
        out.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")

    disc_path = review_dir / "discrepancies.csv"
    with disc_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=DISCREPANCY_FIELDS)
        writer.writeheader()
        writer.writerows(all_discrepancies)

    print(f"Audited {len(paths)} grading JSON files.")
    print(f"Wrote {len(paths)} student review JSON files to {rel(student_review_dir, root)}")
    print(f"Wrote {len(all_discrepancies)} discrepancies to {rel(disc_path, root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
