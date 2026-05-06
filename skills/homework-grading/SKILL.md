---
name: homework-grading
description: Grade student homework in a repo-local Codex workspace using as/ standard-answer PDFs, hw/ student PDF/DOCX submissions, auditable JSON intermediates, scoring-point grading, validation scripts, Markdown reports, final PDFs, summary.csv, and review_queue.csv under work/. Use for full batch grading, continuing only newly added or incomplete submissions, force-regading selected students, or regenerating rubrics where every score must be traceable and human review must be flagged for uncertain rubric, OCR, or answer alignment.
---

# Homework Grading

Use this skill to grade homework inside the current project directory. The fixed input directories are `as/` for standard-answer PDFs and `hw/` for student submissions (`.pdf` or `.docx`). Write every intermediate and final artifact under `work/`; never overwrite files in `as/` or `hw/`.

Do not create LangGraph workflows, web services, databases, Web UI assumptions, or an OpenAI API orchestration layer. Do not grade directly from raw PDF/DOCX to final scores.

## Required Directories

Create these directories before processing:

```text
work/extracted/
work/rubric/
work/answers/
work/grading/
work/reports/
work/final/
```

Expected outputs:

- `work/rubric/rubric.json`
- `work/answers/{student_id}.answers.json`
- `work/grading/{student_id}.grading.json`
- `work/reports/{student_id}.report.md`
- `work/reports/summary.csv`
- `work/reports/review_queue.csv`
- `work/final/{student_id}.final.pdf`

## Standard Workflow

1. Check `as/` for standard-answer PDFs. If more than one exists, ask the user to choose unless the user already specified one.
2. Check `hw/` for student homework files (`.pdf`, `.docx`). Use each filename stem as the default `student_id`.
3. Create the `work/` subdirectories listed above.
4. Extract standard-answer text:
   - Use `scripts/extract_pdf_text.py --input as/<answer>.pdf --output work/extracted/standard_answer.extracted.json`.
   - If `needs_ocr=true`, run `scripts/ocr_scanned_pdf.py` and use the OCR JSON for downstream work.
5. Split the standard answer with `scripts/split_questions.py`.
6. Read `references/rubric_schema.json`, `references/grading_policy.md`, and the rubric extraction prompt in `references/prompt_templates.md`. Generate `work/rubric/rubric.json` from the structured extracted/split standard answer.
7. Validate the rubric:
   - `python .agents/skills/homework-grading/scripts/validate_rubric.py --rubric work/rubric/rubric.json --schema .agents/skills/homework-grading/references/rubric_schema.json`
   - Stop if validation fails.
8. Extract every student submission:
   - PDF: `extract_pdf_text.py`; if low quality, `ocr_scanned_pdf.py`.
   - DOCX: `extract_docx_text.py`.
9. Split each student answer with `scripts/split_questions.py`, align it to rubric `question_id`s, and write `work/answers/{student_id}.answers.json` conforming to `references/answers_schema.json`.
10. Grade each student question by question using `references/grading_policy.md` and the question grading prompt. Every result must score each rubric scoring point and cite student evidence.
11. Write `work/grading/{student_id}.grading.json`, then validate it:
    - `python .agents/skills/homework-grading/scripts/validate_grading.py --grading work/grading/{student_id}.grading.json --rubric work/rubric/rubric.json --schema .agents/skills/homework-grading/references/grading_schema.json`
    - Stop for that student if validation fails.
12. Render each student report:
    - `python .agents/skills/homework-grading/scripts/render_report.py --grading work/grading/{student_id}.grading.json --output work/reports/{student_id}.report.md`
13. Render each student's final readable PDF from validated grading JSON:
    - `python .agents/skills/homework-grading/scripts/render_final_pdf.py --grading work/grading/{student_id}.grading.json --output work/final/{student_id}.final.pdf`
14. Update class summaries:
    - `python .agents/skills/homework-grading/scripts/update_summary.py --grading-dir work/grading --report-dir work/reports --rubric work/rubric/rubric.json --schema .agents/skills/homework-grading/references/grading_schema.json`

## Command Semantics

- "开始完整批改", "开始自动批改", "run full grading", or "批改 hw 下所有作业": process every supported file under `hw/` using the full grading workflow.
- "继续批改", "continue grading", "继续处理新增作业", "批改新增作业", "只批改新增作业", or "resume grading": process only newly added or incomplete files under `hw/`; skip completed submissions.
- "重批 student_001", "重新批改 hw/student_001.pdf", or "force regrade student_001": reprocess only the specified `student_id` or file, even if its prior results are complete.
- "重新生成 rubric": reparse `as/`, regenerate `work/rubric/rubric.json`, and validate it before any grading.

## One-shot full grading workflow

When the user asks to "start grading", "run full grading", "开始完整批改", "开始自动批改", "批改 hw 下所有作业", or an equivalent request, execute the complete workflow end-to-end without asking for step-by-step confirmation.

Use these fixed directories:

- Standard answers: `as/`
- Student submissions: `hw/`
- Outputs: `work/`, including final display PDFs in `work/final/`

Only stop or ask the user when there is a blocking ambiguity or unrecoverable setup issue.

### Blocking conditions

Stop and ask for user input only when:

1. `as/` contains multiple PDF files and the user did not specify which one to use.
2. `as/` contains no PDF standard answer.
3. `hw/` contains no supported student submissions.
4. A required script is missing and cannot be safely repaired.
5. A required dependency is missing and cannot be installed or clearly remediated.
6. Schema validation repeatedly fails and cannot be safely corrected.
7. The user explicitly requests staged execution or step-by-step confirmation.

### Default full workflow

1. Inspect `as/`.
   - If there is exactly one PDF, use it as the standard answer.
   - If there are multiple PDFs, list them and stop for user selection.
   - If there is no PDF, stop and report the issue.

2. Inspect `hw/`.
   - Process supported files: PDF and DOCX.
   - Use each file name stem as the default `student_id`.
   - If no supported files exist, stop and report the issue.

3. Create required output directories if missing:
   - `work/extracted/`
   - `work/rubric/`
   - `work/answers/`
   - `work/grading/`
   - `work/reports/`
   - `work/final/`

4. Extract the standard answer PDF into structured JSON.
   - Use the PDF text extraction script first.
   - If extraction quality is low, use OCR fallback.
   - Preserve page numbers, source snippets, extraction method, and confidence where available.

5. Split the standard answer into questions.

6. Generate `work/rubric/rubric.json`.
   - Extract each question's `question_id`, `max_score`, standard solution, and scoring points.
   - If scoring points are not explicit, infer candidate scoring points from the solution, set `rubric_source="inferred_from_solution"`, and set `needs_teacher_review=true`.

7. Validate the rubric.
   - Run `validate_rubric.py`.
   - If validation fails, repair the rubric and rerun validation.
   - Do not grade submissions until the rubric validates.

8. For each supported file in `hw/`:
   - Extract text or OCR content into `work/extracted/`.
   - Align student answers to the rubric's `question_id`s.
   - Save `work/answers/{student_id}.answers.json`.
   - Grade each question strictly against the rubric.
   - Save `work/grading/{student_id}.grading.json`.
   - Run `validate_grading.py`.
   - If validation fails, repair the grading JSON and rerun validation.
   - Render `work/reports/{student_id}.report.md`.
   - Render the final display PDF `work/final/{student_id}.final.pdf` from the validated grading JSON.

9. If one submission fails:
   - Record the file name and failure reason.
   - Continue processing remaining submissions.
   - Include the failure in the final summary.

10. After all submissions are processed:
    - Generate or update `work/reports/summary.csv`.
    - Generate or update `work/reports/review_queue.csv`.
    - Rebuild these CSVs from all valid `work/grading/*.grading.json` files so existing valid students remain represented.

Do not overwrite original files in `as/` or `hw/`. All intermediate JSON must be written to disk.

### Human review rules

Set `needs_human_review=true` and include the item in `review_queue.csv` when any of the following occurs:

- OCR confidence is low.
- Question alignment is uncertain.
- The rubric was inferred rather than explicitly provided.
- The student answer is missing, unreadable, or ambiguous.
- The grading judgment is uncertain.
- The student solution may be valid but differs substantially from the standard solution.

### Final response

After a full run, respond with a compact summary only:

- Standard answer file used.
- Number of supported submissions found.
- Number successfully graded.
- Failed files and reasons, if any.
- Number of questions requiring human review.
- Paths to:
  - `work/rubric/rubric.json`
  - `work/reports/summary.csv`
  - `work/reports/review_queue.csv`
  - generated per-student reports
  - generated final PDFs under `work/final/`

Do not paste full grading reports or PDF contents into the chat unless the user explicitly asks.

## Continue grading workflow

When the user asks to "继续批改", "continue grading", "继续处理新增作业", "批改新增作业", "只批改新增作业", "resume grading", or an equivalent request, do not regrade all submissions. Process only files in `hw/` that are new, incomplete, invalid, or explicitly selected for regrading.

Use `Path(file).stem` as `student_id` for each supported `hw/` file.

### Rubric reuse rules

1. If `work/rubric/rubric.json` exists and passes `validate_rubric.py`, reuse it. Do not reparse `as/` and do not regenerate the rubric.
2. If `work/rubric/rubric.json` is missing, run the standard-answer extraction flow from `as/`, generate the rubric, and validate it before grading.
3. If `work/rubric/rubric.json` exists but fails validation, try to repair it and rerun validation. Stop if it cannot be safely repaired.
4. Reparse `as/` and regenerate the rubric only when the rubric is missing/invalid or the user explicitly asks to "重新生成 rubric".

### Completed submission criteria

Treat a submission as completed, and skip it in continue mode, only when all of these are true:

1. `work/answers/{student_id}.answers.json` exists.
2. `work/grading/{student_id}.grading.json` exists.
3. The grading JSON passes `validate_grading.py` against the current rubric.
4. `work/reports/{student_id}.report.md` exists.
5. `work/final/{student_id}.final.pdf` exists.
6. `work/reports/summary.csv` contains a row for `student_id`.
7. The submission is not listed as failed in the latest failure list.

Treat a submission as incomplete, and process it in continue mode, when any of these are true:

1. `work/answers/{student_id}.answers.json` is missing or obviously incomplete.
2. `work/grading/{student_id}.grading.json` is missing.
3. The grading JSON exists but fails `validate_grading.py`.
4. `work/reports/{student_id}.report.md` is missing.
5. `work/final/{student_id}.final.pdf` is missing.
6. The latest failure list records a previous failure for the file.
7. The file exists in `hw/` but `work/reports/summary.csv` has no row for `student_id`.

### Default continue workflow

1. Identify that the user requested continue grading rather than full grading.
2. Check and reuse `work/rubric/rubric.json` according to the rubric reuse rules.
3. Scan all PDF and DOCX files under `hw/`.
4. For each supported file, compute `student_id` from the filename stem and check the completed submission criteria.
5. Skip completed submissions.
6. For each new or incomplete submission:
   - Extract text or OCR content into `work/extracted/`.
   - Align student answers to the rubric's `question_id`s.
   - Save `work/answers/{student_id}.answers.json`.
   - Grade each question strictly against the rubric.
   - Save `work/grading/{student_id}.grading.json`.
   - Run `validate_grading.py`.
   - If validation fails, repair the grading JSON and rerun validation.
   - Render `work/reports/{student_id}.report.md`.
   - Render `work/final/{student_id}.final.pdf`.
7. If one submission fails, record the file name and failure reason, continue processing remaining submissions, and include the failure in the final summary.
8. Rebuild `work/reports/summary.csv` and `work/reports/review_queue.csv` from all valid `work/grading/*.grading.json` files after processing.

### Continue mode prohibitions

Do not:

- Regrade all completed submissions.
- Overwrite an existing `work/grading/{student_id}.grading.json` that passes validation.
- Overwrite an existing `work/final/{student_id}.final.pdf` when the corresponding grading JSON passes validation.
- Regenerate the rubric unless it is missing, invalid, or explicitly requested.
- Delete `work/reports/summary.csv` or `work/reports/review_queue.csv`; rebuild them only from valid grading JSON files.
- Modify original files in `as/` or `hw/`.
- Paste full reports or PDF contents into the chat.

### Allowed overwrite cases

In continue mode, overwrite or rebuild only these incomplete or invalid artifacts:

- A grading JSON that exists but fails `validate_grading.py`.
- A missing final PDF.
- A missing Markdown report.
- A missing or obviously incomplete answers JSON.
- Artifacts for a `student_id` or file the user explicitly selected for regrading.

### Continue final response

After continue grading, respond with a compact summary only:

- Mode: continue grading.
- Rubric: reused or regenerated.
- Total supported submissions under `hw/`.
- Number skipped as already complete.
- Number processed as new or incomplete.
- Number successfully graded this run.
- Failed files and reasons, if any.
- Number of newly processed questions requiring human review.
- New final PDF paths generated this run.
- Current `work/reports/summary.csv`.
- Current `work/reports/review_queue.csv`.

Do not paste full grading reports into the chat unless the user explicitly asks.

## Rubric Rules

- If the standard answer has explicit scoring points, preserve them.
- If no explicit scoring points exist, infer candidate scoring points from the standard solution, set `rubric_source="inferred_from_solution"`, and set `needs_teacher_review=true`.
- Validate that every question's scoring point scores sum to `max_score`, all question `max_score`s sum to `total_score`, and `question_id` values are unique.

## Grading Rules

- Grade by scoring point only; do not assign untraceable holistic scores.
- Every `score_awarded` must be less than or equal to the scoring point `max_score`.
- Every question `score` must equal the sum of its scoring details and must not exceed `max_score`.
- Give credit for logically correct equivalent methods that satisfy scoring points.
- Give 0 for missing answers and state the concrete reason.
- Set `needs_human_review=true` when the answer is missing, OCR is uncertain, question alignment is unclear, evidence is weak, the rubric point is inferred/unclear, or the grading conclusion is uncertain.
- Each scoring detail must include specific `reason` and `evidence` from the student's answer.

## Bundled Resources

- `scripts/extract_pdf_text.py`: PyMuPDF PDF text extraction to JSON.
- `scripts/extract_docx_text.py`: python-docx extraction of paragraphs and tables to JSON.
- `scripts/ocr_scanned_pdf.py`: OCR fallback for scanned PDFs; fails loudly when OCR dependencies are unavailable.
- `scripts/split_questions.py`: Rough question segmentation for extracted JSON.
- `scripts/validate_rubric.py`: Schema and score consistency checks for `rubric.json`.
- `scripts/validate_grading.py`: Schema, rubric coverage, and score consistency checks for grading JSON.
- `scripts/render_report.py`: Markdown report renderer.
- `scripts/render_final_pdf.py`: Final readable PDF renderer from validated grading JSON.
- `scripts/update_summary.py`: Class summary and human review queue CSV generator; rebuilds from valid grading JSON files when rubric/schema validation inputs are provided.
- `references/rubric_schema.json`, `answers_schema.json`, `grading_schema.json`: Required output schemas.
- `references/grading_policy.md`: Detailed grading policy.
- `references/prompt_templates.md`: Strict-JSON prompt templates for Codex-assisted extraction, alignment, grading, verification, and reports.
