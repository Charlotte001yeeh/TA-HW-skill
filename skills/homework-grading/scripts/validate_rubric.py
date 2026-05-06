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
    parser = argparse.ArgumentParser(description="Validate rubric schema and scoring totals.")
    parser.add_argument("--rubric", required=True, help="Rubric JSON path.")
    parser.add_argument("--schema", required=True, help="Rubric schema JSON path.")
    args = parser.parse_args()

    errors = []
    rubric_path = Path(args.rubric)
    schema_path = Path(args.schema)
    try:
        rubric = load_json(rubric_path)
        schema = load_json(schema_path)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)

    try:
        import jsonschema
        jsonschema.validate(instance=rubric, schema=schema)
    except ImportError:
        errors.append("Missing dependency jsonschema. Install with: pip install jsonschema")
    except Exception as exc:
        errors.append(f"Schema validation failed: {exc}")

    questions = rubric.get("questions", [])
    seen = set()
    max_score_total = 0.0
    for question in questions:
        qid = question.get("question_id")
        if qid in seen:
            errors.append(f"Duplicate question_id: {qid}")
        seen.add(qid)
        max_score = float(question.get("max_score", 0))
        max_score_total += max_score
        point_total = sum(float(point.get("score", 0)) for point in question.get("scoring_points", []))
        if abs(point_total - max_score) > EPSILON:
            errors.append(f"Question {qid}: scoring_points total {point_total} != max_score {max_score}")

    total_score = float(rubric.get("total_score", 0))
    if abs(max_score_total - total_score) > EPSILON:
        errors.append(f"Rubric total_score {total_score} != sum(question max_score) {max_score_total}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
    print(f"OK: rubric valid ({len(questions)} questions, total_score={total_score})")


if __name__ == "__main__":
    main()
