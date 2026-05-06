# Grading Policy

Grade every answer by rubric scoring point. Do not assign a final score that cannot be traced to individual scoring points.

Do not award more than a scoring point's maximum score, a question's maximum score, or the assignment total score.

Do not penalize different wording, notation, ordering, or solution method unless it changes correctness or fails a scoring point. Equivalent correct solutions receive the relevant credit.

Missing answers receive 0 for the relevant scoring points. State exactly that the answer is missing and cite the absence as the evidence.

OCR uncertainty, unreadable text, low extraction confidence, unclear question boundaries, weak answer-to-question alignment, or ambiguous standard-answer scoring requires `needs_human_review=true`.

If the standard answer lacks explicit scoring points, generate candidate scoring points from the standard solution, set `rubric_source="inferred_from_solution"`, and set `needs_teacher_review=true`.

Every deducted point needs a concrete reason tied to the scoring point. Avoid vague statements such as "incorrect" without explaining what is missing or wrong.

Every awarded point needs evidence from the student's structured answer. Evidence may be a direct phrase, formula, result, argument step, or a note that the answer is absent or unreadable.

When uncertain, do not force a definitive grading conclusion. Award only clearly supported credit and put the item in the human review queue.
