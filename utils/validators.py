from difflib import SequenceMatcher


def _norm(x):
    return " ".join((x or "").lower().split())


def _unit_number(value):
    """
    Extract unit/chapter number from labels such as:
    'Unit 8 — Heat and Thermodynamics'
    'Unit 8'
    'Chapter 8'
    """

    import re

    if value is None:
        return None

    match = re.search(
        r"\b(?:unit|chapter)\s*(\d+)",
        str(value),
        re.IGNORECASE,
    )

    if match:
        return int(match.group(1))

    return None


def validate_paper(
    paper,
    counts,
    chapters,
    scope_mode="Chapter-wise test",
):
    """
    Validate structure and basic scope.

    Chapter-wise:
        Check that generated questions belong to selected units.

    Topic-wise:
        Do NOT apply chapter-membership validation because the
        teacher's typed topics are the actual scope boundary.
        Topic scope is enforced by the generation prompt.
    """

    errs = []

    keys = [
        "mcqs",
        "short_questions",
        "long_questions",
    ]

    # --------------------------------------------------
    # CHECK QUESTION COUNTS
    # --------------------------------------------------

    for key, expected in zip(keys, counts):

        actual = len(
            paper.get(key, [])
        )

        if actual != expected:
            errs.append(
                f"{key}: expected {expected}, got {actual}"
            )

    # --------------------------------------------------
    # MCQ STRUCTURE
    # --------------------------------------------------

    for i, q in enumerate(
        paper.get("mcqs", []),
        1,
    ):

        if set(q.get("options", {})) != {
            "A",
            "B",
            "C",
            "D",
        }:
            errs.append(
                f"MCQ {i} must have exactly A-D options"
            )

    # --------------------------------------------------
    # CHAPTER VALIDATION
    # ONLY FOR CHAPTER-WISE MODE
    # --------------------------------------------------

    if scope_mode == "Chapter-wise test":

        selected_units = {
            _unit_number(ch)
            for ch in chapters
        }

        selected_units.discard(None)

        if selected_units:

            for section_name in keys:

                for i, q in enumerate(
                    paper.get(section_name, []),
                    1,
                ):

                    question_unit = _unit_number(
                        q.get("chapter")
                    )

                    # Only flag when the LLM explicitly reports
                    # a recognizable unit outside the selection.
                    if (
                        question_unit is not None
                        and question_unit not in selected_units
                    ):
                        errs.append(
                            f"{section_name} question {i} "
                            f"may be outside the selected unit(s)"
                        )

    # --------------------------------------------------
    # EMPTY QUESTIONS
    # --------------------------------------------------

    all_questions = []

    for key in keys:

        for q in paper.get(key, []):

            question = _norm(
                q.get("question")
            )

            if not question:
                errs.append(
                    f"Empty question in {key}"
                )

            if question:
                all_questions.append(question)

            # Also check OR alternative if present.
            or_question = _norm(
                q.get("or_question")
            )

            if or_question:
                all_questions.append(or_question)

    # --------------------------------------------------
    # DUPLICATE CHECK
    # --------------------------------------------------
