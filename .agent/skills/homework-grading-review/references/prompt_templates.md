# Prompt Templates

Use these templates only when deterministic script checks are not enough. Keep raw submissions as supporting context; do not assign final scores directly from raw PDFs.

## Single Question Explanation Review

```
You are reviewing an existing homework grading decision, not grading from scratch.

Rubric question:
{rubric_question_json}

Student extracted answer:
{student_answer_excerpt}

Existing grading detail:
{grading_question_json}

Check whether the score, evidence, and deduction reason are traceable to the rubric scoring points. Return:
- review_status: PASS, MINOR_ISSUES, NEEDS_FIX, or NEEDS_HUMAN_REVIEW
- issues
- suggested_fix
- concise review_comment
```

## Single Student Grading JSON Review

```
Review this student's existing grading JSON against the rubric and extracted answers.

Student ID: {student_id}
Rubric: {rubric_json}
Answers JSON: {answers_json}
Grading JSON: {grading_json}
Summary row: {summary_row}

Check identity, missing questions, score ranges, total score, rubric scoring point alignment, evidence, deduction reasons, and human-review flags. Do not overwrite original files. Return a review JSON matching references/review_schema.json.
```

## Summary Consistency Review

```
Compare report rows with grading JSON records.

Summary/grades rows:
{report_rows}

Grading-derived rows:
{grading_rows}

Find duplicate IDs, missing students, name mismatches, question score mismatches, total mismatches, and deduction reason gaps. Return discrepancies matching references/discrepancy_schema.json.
```

## Review Queue Supplement

```
Build a reviewed human-review queue from these sources:

Original review_queue.csv:
{review_queue_rows}

Discrepancies:
{discrepancies}

Student review records:
{student_reviews}

Answers metadata:
{answers_metadata}

Include all cases involving OCR uncertainty, missing answers, uncertain alignment, score conflicts, identity conflicts, unclear deduction reasons, missing evidence, rubric alignment failure, or inconsistent needs_human_review flags.
```

## Review Report Generation

```
Generate a concise TA-facing review report from structured artifacts only.

Project info:
{project_info}

Student reviews:
{student_reviews}

Discrepancies:
{discrepancies}

Reviewed grades:
{reviewed_grades}

Include overall counts, high-risk issues, student-level summaries, and recommended fixes. Note missing final PDFs as output gaps; do not derive grades from raw PDFs.
```
