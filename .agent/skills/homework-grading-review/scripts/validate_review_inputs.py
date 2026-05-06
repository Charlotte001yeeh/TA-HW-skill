#!/usr/bin/env python3
"""Validate homework grading review inputs without modifying source artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


TEXT_SUFFIXES = {".md", ".py", ".txt", ".json", ".yaml", ".yml", ".csv"}


def count_files(path: Path, pattern: str) -> int:
    return len(list(path.glob(pattern))) if path.exists() else 0


def scan_wrong_skill_paths(root: Path) -> list[str]:
    hits: list[str] = []
    wrong_slash = ".agent" + "s/skills"
    wrong_backslash = ".agent" + "s\\skills"
    for path in root.rglob("*"):
        if ".git" in path.parts or not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if wrong_slash in text or wrong_backslash in text:
            hits.append(str(path.relative_to(root)))
    return hits


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    work = root / "work"
    review_skill = root / ".agent" / "skills" / "homework-grading-review"
    checks: list[dict[str, object]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "ok": ok, "detail": detail})

    rubric = work / "rubric" / "rubric.json"
    answers = work / "answers"
    grading = work / "grading"
    reports = work / "reports"
    summary = reports / "summary.csv"
    grades = reports / "grades.csv"

    add("repo_root", root.exists(), str(root))
    add("skill_path", review_skill.exists(), str(review_skill.relative_to(root) if review_skill.exists() else review_skill))
    add("rubric_json", rubric.exists(), str(rubric.relative_to(root)))
    add("answers_dir", answers.exists() and count_files(answers, "*.answers.json") > 0, f"{count_files(answers, '*.answers.json')} answers JSON files")
    add("grading_dir", grading.exists() and count_files(grading, "*.grading.json") > 0, f"{count_files(grading, '*.grading.json')} grading JSON files")
    add("summary_or_grades", summary.exists() or grades.exists(), f"summary={summary.exists()} grades={grades.exists()}")

    if rubric.exists():
        try:
            data = json.loads(rubric.read_text(encoding="utf-8"))
            add("rubric_parse", isinstance(data, dict), f"{len(data.get('questions', [])) if isinstance(data, dict) else 0} rubric questions")
        except Exception as exc:  # noqa: BLE001
            add("rubric_parse", False, str(exc))

    wrong_refs = scan_wrong_skill_paths(root)
    add("wrong_agents_path_refs", not wrong_refs, ", ".join(wrong_refs[:20]) if wrong_refs else "no wrong agents skill path references found")

    output = {
        "root": str(root),
        "ok": all(bool(item["ok"]) for item in checks),
        "checks": checks,
        "review_output_dir": str((work / "review").relative_to(root)),
    }

    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(f"Review input validation for {root}")
        for item in checks:
            status = "OK" if item["ok"] else "FAIL"
            print(f"[{status}] {item['check']}: {item['detail']}")
        print(f"Overall: {'OK' if output['ok'] else 'FAIL'}")

    return 0 if output["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
