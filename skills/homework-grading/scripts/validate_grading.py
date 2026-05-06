#!/usr/bin/env python
import argparse
import json
import sys
from pathlib import Path


EPSILON = 0.000001


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"Failed to read JSON {path}: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate grading schema, rubric coverage, and scoring totals.")
    parser.add_argument("--grading", required=True, help="Grading JSON path.")
    parser.add_argument("--rubric", required=True, help="Rubric JSON path.")
    parser.add_argument("--schema", required=True, help="Grading schema JSON path.")
    args = parser.parse_args()

    errors = []
    try:
        grading = load_json(Path(args.grading))
        rubric = load_json(Path(args.rubric))
        schema = load_json(Path(args.schema))
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)

    try:
        import jsonschema
        jsonschema.validate(instance=grading, schema=schema)
    except ImportError:
        errors.append("Missing dependency jsonschema. Install with: pip install jsonschema")
    except Exception as exc:
        errors.append(f"Schema validation failed: {exc}")

    rubric_questions = {q.get("question_id"): q for q in rubric.get("questions", [])}
    rubric_point_scores = {
        qid: {p.get("point_id"): float(p.get("score", 0)) for p in q.get("scoring_points", [])}
        for qid, q in rubric_questions.items()
    }
    results = grading.get("results", [])
    result_questions = {r.get("question_id") for r in results}
    missing = set(rubric_questions) - result_questions
    extra = result_questions - set(rubric_questions)
    for qid in sorted(missing):
        errors.append(f"Missing grading result for rubric question_id: {qid}")
    for qid in sorted(extra):
        errors.append(f"Grading contains unknown question_id not in rubric: {qid}")

    result_total = 0.0
    for result in results:
        qid = result.get("question_id")
        score = float(result.get("score", 0))
        max_score = float(result.get("max_score", 0))
        detail_total = 0.0
        if qid in rubric_questions:
            rubric_max = float(rubric_questions[qid].get("max_score", 0))
            if abs(max_score - rubric_max) > EPSILON:
                errors.append(f"Question {qid}: max_score {max_score} != rubric max_score {rubric_max}")
        for detail in result.get("scoring_details", []):
            point_id = detail.get("point_id")
            awarded = float(detail.get("score_awarded", 0))
            detail_total += awarded
            point_max = float(detail.get("max_score", 0))
            rubric_point_max = rubric_point_scores.get(qid, {}).get(point_id)
            if rubric_point_max is not None and abs(point_max - rubric_point_max) > EPSILON:
                errors.append(f"Question {qid} point {point_id}: detail max_score {point_max} != rubric point score {rubric_point_max}")
            if awarded - point_max > EPSILON:
                errors.append(f"Question {qid} point {point_id}: score_awarded {awarded} exceeds max_score {point_max}")
        if abs(score - detail_total) > EPSILON:
            errors.append(f"Question {qid}: score {score} != scoring_details total {detail_total}")
        if score - max_score > EPSILON:
            errors.append(f"Question {qid}: score {score} exceeds max_score {max_score}")
        result_total += score

    total_score = float(grading.get("total_score", 0))
    if abs(total_score - result_total) > EPSILON:
        errors.append(f"total_score {total_score} != sum(question scores) {result_total}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
    print(f"OK: grading valid ({grading.get('student_id')}, total_score={total_score})")


if __name__ == "__main__":
    main()
