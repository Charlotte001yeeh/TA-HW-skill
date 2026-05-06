# TA Homework Codex Skills

This repository contains repo-local Codex skills for TA homework grading and grading review. The skills are intended to live under `.agent/skills/` in a Codex workspace and operate on local course files without a web UI, database, LangGraph workflow, or standalone API service.

## Included Skills

```text
.agent/skills/
├── homework-grading/          # Batch grading from standard answers and submissions
└── homework-grading-review/   # Audit and reconcile existing grading outputs
```

### `homework-grading`

Use this skill to grade student submissions from local files.

Expected workspace layout:

```text
project-root/
├── .agent/skills/homework-grading/
├── as/                         # Standard answer PDFs
├── hw/                         # Student submissions: PDF or DOCX
└── work/                       # Generated grading outputs
```

Key outputs:

- `work/rubric/rubric.json`
- `work/answers/{student_id}.answers.json`
- `work/grading/{student_id}.grading.json`
- `work/reports/{student_id}.report.md`
- `work/reports/summary.csv`
- `work/reports/review_queue.csv`
- `work/final/{student_id}.final.pdf`

Useful prompts:

- `开始自动批改`
- `开始完整批改`
- `批改 hw 下所有作业`
- `继续批改`
- `只批改新增作业`
- `重批 student_001`
- `重新生成 rubric`

### `homework-grading-review`

Use this skill after grading has already produced `work/rubric/`, `work/answers/`, `work/grading/`, and `work/reports/`. It audits score arithmetic, summary consistency, identity matching, evidence quality, deduction reasons, and review queue coverage.

Review outputs are written under `work/review/`, including:

- `work/review/student_review/{student_id}.review.json`
- `work/review/discrepancies.csv`
- `work/review/summary_consistency.csv`
- `work/review/review_queue_reviewed.csv`
- `work/review/reviewed_grades.csv`
- `work/review/review_report.md`
- `work/review/review_report.pdf`

Useful prompts:

- `检查批改结果`
- `复核 summary.csv 和 grading.json`
- `审查某个学生 2025231006 的批改是否合理`
- `生成复核报告`

## Python Environment

Use Python 3.10 or newer.

Install packages needed by the grading scripts:

```bash
python -m pip install pymupdf python-docx jsonschema reportlab pillow pytesseract
```

For scanned PDFs, install the Tesseract executable separately and ensure it is available on `PATH`:

```bash
tesseract --version
```

## Validation

Validate skill metadata:

```bash
python C:/Users/bonobong/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agent/skills/homework-grading
python C:/Users/bonobong/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agent/skills/homework-grading-review
```

Check the review skill inputs in a grading workspace:

```bash
python .agent/skills/homework-grading-review/scripts/validate_review_inputs.py --root .
```

## Repository Hygiene

The repository tracks skill instructions, scripts, schemas, and reference policy files. It intentionally ignores local course data and generated outputs:

- `as/`
- `hw/`
- `work/`
- `tools/`

Do not commit student submissions, answer PDFs, generated grades, reports, or review artifacts unless you intentionally create a private data snapshot.
