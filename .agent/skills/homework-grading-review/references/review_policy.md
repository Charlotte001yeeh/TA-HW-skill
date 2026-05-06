# Homework Grading Review Policy

## Scope

Review existing grading artifacts after an initial grading process. The reviewer checks consistency, traceability, and auditability. The reviewer does not grade from raw submissions or overwrite original grading outputs by default.

## Score Consistency

- Recompute each student's total from question scores in `grading.json`.
- Compare recomputed totals with `grading_json.total_score`.
- Compare `summary.csv` and `grades.csv` question columns and total columns with `grading.json`.
- Flag negative scores, nonnumeric scores, and scores above question max.
- Flag missing questions by comparing grading question IDs with rubric question IDs.
- Treat conflicting totals as `NEEDS_FIX` or `NEEDS_HUMAN_REVIEW` when automatic correction is uncertain.

## Identity Consistency

- Match rows by `student_id` before using names.
- Flag duplicate student IDs in any summary table.
- Flag student IDs present in grading JSON but missing from summary/grades.
- Flag summary/grades rows with no corresponding grading JSON.
- Flag name mismatches when both sides provide nonempty names.
- Treat name/ID mismatch or row shift as high risk and include it in review output.

## Rubric Alignment

- Every question in grading JSON should map to a rubric question.
- Every scoring detail should reference a rubric scoring point when point IDs exist.
- Every awarded score should be traceable to a question max score and, where possible, a scoring point max score.
- If the rubric was inferred, incomplete, or marked for teacher review, the affected item should remain eligible for human review.

## Evidence Requirements

- Each scoring point should include concrete student-answer evidence, excerpt, or a clear pointer to extracted answer text.
- Generic evidence such as "see extracted text" is acceptable only as a weak pointer and should be treated as a minor audit issue when no answer excerpt is present.
- Missing, unreadable, too-short, OCR-uncertain, or alignment-uncertain answers must be routed to review output.

## Deduction Reason Quality

Each deduction must have a specific reason tied to the rubric point and student answer.

Poor reasons include:

- "答案不完整"
- "错了"
- "扣分"
- "缺少步骤"
- "incomplete"
- "wrong"
- "deducted"

Good reasons include:

- "Q3(b) 未说明投影梯度的可行性条件，缺少与 KKT 条件对应的解释，因此扣 2 分。"
- "该题 scoring point 2 要求写出更新公式，但学生只给出文字描述，未给出数学表达式，因此该点不得分。"

Flag empty, overly short, generic, or template-only reasons. A deduction reason is stronger when it identifies the question, rubric point, missing concept, student evidence, and point impact.

## Human Review Rules

Set review status and include the item in review outputs when any of the following occur:

- OCR is uncertain or extracted text is too short.
- Answer is missing, unreadable, or question alignment is uncertain.
- Rubric is inferred or a scoring judgment is uncertain.
- Student name and ID do not match across artifacts.
- Summary total conflicts with grading JSON or recomputed total.
- A question score is out of range or cannot be parsed.
- A grading JSON is missing required fields.
- Deduction reasons are missing or unclear.
- Evidence is missing for a scoring point.
- `needs_human_review` is false despite high-risk signals.

## Review Queue Rules

The reviewed queue should include original `work/reports/review_queue.csv` rows plus any new rows triggered by discrepancies, grading flags, answer extraction uncertainty, missing evidence, rubric alignment failure, score conflicts, or identity conflicts.

## Automatic Fix Boundary

Allowed default outputs:

- `work/review/reviewed_grades.csv`
- `work/review/discrepancies.csv`
- `work/review/summary_consistency.csv`
- `work/review/review_queue_reviewed.csv`
- `work/review/student_review/{student_id}.review.json`
- `work/review/corrected_grading/{student_id}.grading.json`
- `work/review/review_report.md`
- `work/review/review_report.pdf`

Do not overwrite:

- `as/*`
- `hw/*`
- `work/grading/*.grading.json`
- `work/reports/summary.csv`
- `work/reports/grades.csv`
- `work/reports/review_queue.csv`

Only overwrite original grading or reports when the user explicitly confirms applying fixes.

## Review Status

- `PASS`: Consistent, traceable, and no clear audit issue.
- `MINOR_ISSUES`: Formatting, weak explanation, or weak evidence issues that do not affect the total.
- `NEEDS_FIX`: Deterministic inconsistency exists and should be corrected.
- `NEEDS_HUMAN_REVIEW`: An uncertainty or high-risk issue cannot be resolved safely by automation.

Final review comments should state the main issue, the affected artifact, and the suggested next action.
