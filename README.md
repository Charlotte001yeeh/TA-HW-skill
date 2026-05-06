# Homework Grading Codex Skill

This repository folder contains a repo-local Codex skill for grading student homework from local files. It is designed to run inside a Codex workspace using skill instructions, Python scripts, JSON schemas, and reference policies. It does not require LangGraph, a web UI, a database, or a standalone API orchestration layer.

## What This Skill Does

The skill grades homework using this fixed project layout:

```text
project-root/
├── as/                         # Standard answer PDFs
├── hw/                         # Student submissions: PDF or DOCX
├── work/                       # Generated outputs, created by the workflow
└── .agents/skills/homework-grading/
```

Generated outputs are written under `work/`:

```text
work/extracted/                 # Extracted text, OCR outputs, split questions
work/rubric/rubric.json          # Structured grading rubric
work/answers/{student_id}.answers.json
work/grading/{student_id}.grading.json
work/reports/{student_id}.report.md
work/reports/summary.csv
work/reports/review_queue.csv
work/final/{student_id}.final.pdf
```

The structured JSON files are the source of truth. Final PDFs are generated from validated `grading.json` files.

## Installation

Copy or clone this skill folder into your Codex project:

```text
project-root/.agents/skills/homework-grading/
```

The folder must contain:

```text
homework-grading/
├── SKILL.md
├── scripts/
│   ├── extract_docx_text.py
│   ├── extract_pdf_text.py
│   ├── ocr_scanned_pdf.py
│   ├── render_final_pdf.py
│   ├── render_report.py
│   ├── split_questions.py
│   ├── update_summary.py
│   ├── validate_grading.py
│   └── validate_rubric.py
└── references/
    ├── answers_schema.json
    ├── grading_policy.md
    ├── grading_schema.json
    ├── prompt_templates.md
    └── rubric_schema.json
```

## Python Environment

Use Python 3.10 or newer.

Install the required Python packages:

```bash
python -m pip install pymupdf python-docx jsonschema reportlab pillow pytesseract
```

Package purpose:

- `pymupdf`: PDF text extraction.
- `python-docx`: DOCX text extraction.
- `jsonschema`: Rubric and grading validation.
- `reportlab`: Final PDF rendering.
- `pillow` and `pytesseract`: OCR support for scanned PDFs.

## OCR Dependency

For scanned PDFs, install the Tesseract executable separately and make sure it is available on `PATH`.

Check whether Tesseract is available:

```bash
tesseract --version
```

If Tesseract is missing, normal text PDFs can still be graded, but scanned/image-only PDFs will fail OCR fallback and should be listed as failed files.

## Required Project Inputs

Create these folders at the project root:

```text
as/
hw/
```

Place standard answer PDFs in `as/`.

- If `as/` contains exactly one PDF, the full grading workflow uses it automatically.
- If `as/` contains multiple PDFs, Codex must stop and ask which standard answer to use.
- If `as/` contains no PDF, grading must stop.

Place student submissions in `hw/`.

- Supported formats: `.pdf`, `.docx`.
- Each file represents one student submission.
- The filename stem is used as the default `student_id`.

Do not place inputs in alternative folders such as `input/standard_answer.pdf` or `input/submissions/`.

## Usage In Codex

Use the skill in a Codex workspace by referring to it as:

```text
$homework-grading
```

### Full Grading

Use full grading when you want to process all supported files under `hw/`:

```text
开始自动批改
```

Equivalent intents include:

- `开始完整批改`
- `run full grading`
- `批改 hw 下所有作业`

Full grading should:

1. Check `as/`.
2. Check all supported files in `hw/`.
3. Create `work/` subdirectories.
4. Extract the standard answer.
5. Generate and validate `work/rubric/rubric.json`.
6. Extract each student submission.
7. Generate `answers.json`.
8. Generate and validate `grading.json`.
9. Generate Markdown reports.
10. Generate final PDFs in `work/final/`.
11. Rebuild `summary.csv` and `review_queue.csv`.

### Continue Grading

Use continue grading when you only want to process new or incomplete submissions:

```text
继续批改
```

Equivalent intents include:

- `continue grading`
- `resume grading`
- `继续处理新增作业`
- `批改新增作业`
- `只批改新增作业`

Continue grading reuses an existing valid `work/rubric/rubric.json` and skips a student if all of these exist and validate:

- `work/answers/{student_id}.answers.json`
- `work/grading/{student_id}.grading.json`
- `work/reports/{student_id}.report.md`
- `work/final/{student_id}.final.pdf`
- a matching row in `work/reports/summary.csv`

It should process only missing, invalid, failed, or explicitly selected submissions.

### Force Regrade One Student

Use force regrade only when you want to overwrite an already completed student's outputs:

```text
重批 student_001
```

Equivalent intents include:

- `重新批改 hw/student_001.pdf`
- `force regrade student_001`

### Regenerate Rubric

Only regenerate the rubric when explicitly requested:

```text
重新生成 rubric
```

Continue grading should not regenerate the rubric if `work/rubric/rubric.json` exists and validates.

## Manual Script Checks

Run help checks after setup:

```bash
python .agents/skills/homework-grading/scripts/extract_pdf_text.py --help
python .agents/skills/homework-grading/scripts/extract_docx_text.py --help
python .agents/skills/homework-grading/scripts/ocr_scanned_pdf.py --help
python .agents/skills/homework-grading/scripts/split_questions.py --help
python .agents/skills/homework-grading/scripts/validate_rubric.py --help
python .agents/skills/homework-grading/scripts/validate_grading.py --help
python .agents/skills/homework-grading/scripts/render_report.py --help
python .agents/skills/homework-grading/scripts/render_final_pdf.py --help
python .agents/skills/homework-grading/scripts/update_summary.py --help
```

## Validation Commands

Validate a rubric:

```bash
python .agents/skills/homework-grading/scripts/validate_rubric.py \
  --rubric work/rubric/rubric.json \
  --schema .agents/skills/homework-grading/references/rubric_schema.json
```

Validate one student's grading result:

```bash
python .agents/skills/homework-grading/scripts/validate_grading.py \
  --grading work/grading/{student_id}.grading.json \
  --rubric work/rubric/rubric.json \
  --schema .agents/skills/homework-grading/references/grading_schema.json
```

Rebuild class summaries from valid grading files:

```bash
python .agents/skills/homework-grading/scripts/update_summary.py \
  --grading-dir work/grading \
  --report-dir work/reports \
  --rubric work/rubric/rubric.json \
  --schema .agents/skills/homework-grading/references/grading_schema.json
```

Render a final PDF from validated grading JSON:

```bash
python .agents/skills/homework-grading/scripts/render_final_pdf.py \
  --grading work/grading/{student_id}.grading.json \
  --output work/final/{student_id}.final.pdf
```

## Usage Rules

Always follow these rules:

- Do not overwrite original files in `as/` or `hw/`.
- Do not skip intermediate JSON files.
- Do not generate final scores directly from raw PDF or DOCX files.
- Keep `grading.json` as the grading source of truth.
- Generate final PDFs only from validated `grading.json`.
- Do not award scores above the maximum.
- Every score must trace back to a scoring point.
- Every deduction must have a specific reason.
- Every scoring point should include evidence from the student answer.
- Mark `needs_human_review=true` when OCR is uncertain, alignment is unclear, the answer is missing, the rubric was inferred, or the grading judgment is uncertain.
- Do not paste full reports or PDF contents into chat unless explicitly requested.

## Human Review Queue

Items should be included in `work/reports/review_queue.csv` when:

- OCR confidence is low.
- Question alignment is uncertain.
- The rubric was inferred from the solution rather than explicitly provided.
- The student answer is missing, unreadable, or ambiguous.
- The grading judgment is uncertain.
- The student solution may be valid but differs substantially from the standard solution.

## Troubleshooting

### `Missing dependency PyMuPDF`

Install dependencies:

```bash
python -m pip install pymupdf
```

### `Missing dependency ReportLab`

Install ReportLab:

```bash
python -m pip install reportlab
```

### OCR fallback fails

Install Tesseract and ensure it is available on `PATH`:

```bash
tesseract --version
```

If Tesseract is unavailable, scanned PDFs cannot be OCR-processed by the bundled OCR script.

### Schema validation fails

Do not continue to final reports or final PDFs until validation passes. Repair the JSON so that:

- Rubric scoring point totals match each question's `max_score`.
- Rubric question totals match `total_score`.
- Grading question scores equal the sum of `scoring_details`.
- No question score exceeds `max_score`.
- No scoring point score exceeds its maximum.
- No rubric question is missing from grading.

## Expected Final Response Style

After full grading, report only a compact summary:

- Standard answer file used.
- Number of supported submissions found.
- Number successfully graded.
- Failed files and reasons.
- Number of questions requiring human review.
- Paths to `rubric.json`, `summary.csv`, `review_queue.csv`, reports, and final PDFs.

After continue grading, report only:

- Mode: continue grading.
- Rubric: reused or regenerated.
- Total supported submissions under `hw/`.
- Number skipped as already complete.
- Number processed as new or incomplete.
- Number successfully graded this run.
- Failed files and reasons.
- New final PDF paths generated this run.
- Current `summary.csv` and `review_queue.csv` paths.
