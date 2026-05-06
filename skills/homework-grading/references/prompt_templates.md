# Prompt Templates

Use these templates after file extraction and splitting. Replace bracketed placeholders with paths or JSON content. The response must be strict JSON only: no Markdown fences, no explanations, no commentary.

## Rubric Extraction Prompt

You are converting a standard answer into a grading rubric. Use only the structured extracted standard-answer JSON and split-question JSON below.

Inputs:
- Extracted standard answer JSON: [EXTRACTED_STANDARD_JSON]
- Split standard questions JSON: [SPLIT_STANDARD_QUESTIONS_JSON]
- Rubric schema: [RUBRIC_SCHEMA_JSON]

Output strict JSON conforming to the rubric schema. Include `assignment_id`, `total_score`, and `questions`.

For each question include `question_id`, `title`, `max_score`, `standard_solution`, `rubric_source`, `needs_teacher_review`, and `scoring_points`.

If explicit scoring points are present, set `rubric_source="explicit_from_answer_key"` and preserve them. If scoring points are not explicit, infer candidate scoring points from the solution, set `rubric_source="inferred_from_solution"`, and set `needs_teacher_review=true`.

Ensure each question's scoring point scores sum exactly to `max_score`. Ensure all question `max_score` values sum exactly to `total_score`. Output JSON only.

## Answer Alignment Prompt

You are aligning one student's extracted homework answers to a validated rubric.

Inputs:
- Student ID: [STUDENT_ID]
- Student name if known: [STUDENT_NAME]
- Student source file: [SOURCE_FILE]
- Extracted student JSON: [EXTRACTED_STUDENT_JSON]
- Split student questions JSON: [SPLIT_STUDENT_QUESTIONS_JSON]
- Rubric JSON: [RUBRIC_JSON]
- Answers schema: [ANSWERS_SCHEMA_JSON]

Output strict JSON conforming to the answers schema. Create one answer object for every rubric `question_id`. Preserve source pages and snippets. Set `needs_human_review=true` with a specific `review_reason` if an answer is missing, OCR confidence is low, extraction confidence is low, or question alignment is uncertain. Output JSON only.

## Question Grading Prompt

You are grading one student's answer for one question by rubric scoring point.

Inputs:
- Grading policy: [GRADING_POLICY]
- Rubric question JSON: [RUBRIC_QUESTION_JSON]
- Student answer JSON: [STUDENT_ANSWER_JSON]
- Grading schema result shape: each result requires `question_id`, `max_score`, `score`, `scoring_details`, `final_reason`, `needs_human_review`, and `review_reason`.

Output strict JSON for one result object only. For every scoring point, output one `scoring_detail` with `point_id`, `max_score`, `score_awarded`, `reason`, and `evidence`.

Award credit for equivalent correct methods. Do not exceed point maximums. The result `score` must equal the sum of `score_awarded`. Use concrete evidence from the student's answer. Set `needs_human_review=true` if OCR, alignment, rubric clarity, or grading certainty is insufficient. Output JSON only.

## Grading Verification Prompt

You are verifying a completed grading JSON before script validation.

Inputs:
- Rubric JSON: [RUBRIC_JSON]
- Grading JSON: [GRADING_JSON]
- Grading schema: [GRADING_SCHEMA_JSON]

Output strict JSON with:
- `is_valid`: boolean
- `errors`: array of strings
- `required_fixes`: array of strings

Check that every rubric question is present, every scoring point is represented, score totals are exact, no score exceeds maximum, evidence is present, and human review flags are set for uncertainty. Output JSON only.

## Report Writing Prompt

You are preparing a concise Markdown report from validated grading JSON.

Inputs:
- Validated grading JSON: [GRADING_JSON]

Output strict JSON only with:
- `student_id`
- `student_name`
- `report_markdown`

The Markdown must include total score, per-question score, scoring details, deducted-point reasons, evidence, human review flags, and review reasons. Do not change any scores. Output JSON only.
