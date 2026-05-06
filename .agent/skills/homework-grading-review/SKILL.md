---
name: homework-grading-review
description: Review and reconcile existing local homework grading outputs for TAs. Use when the user asks to check grading results, review homework scores, audit summary.csv or grades.csv against grading.json, inspect per-question deduction reasons, generate a review report, rebuild or supplement review_queue.csv, regenerate reviewed grades, or check whether one student's grading is reasonable. This skill reviews existing rubric, answers, grading JSON, and report CSV artifacts; it does not grade homework from scratch.
---

# Homework Grading Review

Use this repo-local skill to audit completed homework grading artifacts. Treat `work/rubric/rubric.json`, `work/answers/*.answers.json`, `work/grading/*.grading.json`, and `work/reports/*.csv` as audit sources. Write review outputs to `work/review/`.

## Boundaries

Do not use this skill to:

- grade submissions from scratch
- regenerate the rubric
- assign final grades directly from raw PDFs or images
- build a Web UI, database, API orchestration layer, or LangGraph flow

Do not overwrite `as/`, `hw/`, `work/grading/`, or `work/reports/` unless the user explicitly asks to apply fixes to original files. Put corrected grading drafts under `work/review/corrected_grading/`.

For detailed policy, read `references/review_policy.md`. For output schemas and LLM review prompts, read:

- `references/review_schema.json`
- `references/discrepancy_schema.json`
- `references/prompt_templates.md`

## Workflows

### Full Review

1. Validate inputs and repo paths.
2. Audit every `work/grading/*.grading.json` against the rubric.
3. Compare `summary.csv` and `grades.csv` with grading JSON.
4. Rebuild the review queue from discrepancies and uncertainty signals.
5. Render `work/review/review_report.md`.
6. Optionally render `work/review/review_report.pdf` from the Markdown report.

Commands:

```bash
python .agent/skills/homework-grading-review/scripts/validate_review_inputs.py --root .
python .agent/skills/homework-grading-review/scripts/audit_grading_json.py --root .
python .agent/skills/homework-grading-review/scripts/audit_summary_consistency.py --root .
python .agent/skills/homework-grading-review/scripts/build_review_queue.py --root .
python .agent/skills/homework-grading-review/scripts/render_review_report.py --root .
python .agent/skills/homework-grading-review/scripts/render_review_pdf.py --root .
```

### Single Student Review

Use `--student-id` to focus the JSON audit:

```bash
python .agent/skills/homework-grading-review/scripts/audit_grading_json.py --root . --student-id 2025231006
```

Then inspect `work/review/student_review/2025231006.review.json` and summarize whether the student needs human review.

### Summary Consistency Review

Check student identity, per-question scores, totals, missing rows, duplicate IDs, and deduction reason coverage:

```bash
python .agent/skills/homework-grading-review/scripts/audit_summary_consistency.py --root .
```

Outputs include `work/review/summary_consistency.csv`, `work/review/discrepancies.csv`, and `work/review/reviewed_grades.csv`.

### Review Queue Review

Rebuild a reviewed queue from original queue rows, grading flags, answer extraction signals, and discrepancies:

```bash
python .agent/skills/homework-grading-review/scripts/build_review_queue.py --root .
```

Output: `work/review/review_queue_reviewed.csv`.

### Report Regeneration

Render reports from structured review artifacts, not from raw PDFs:

```bash
python .agent/skills/homework-grading-review/scripts/render_review_report.py --root .
python .agent/skills/homework-grading-review/scripts/render_review_pdf.py --root .
```

If PDF dependencies are unavailable, keep the Markdown report and state that PDF rendering was skipped.
