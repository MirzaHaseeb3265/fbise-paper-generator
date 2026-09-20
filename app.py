from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from utils.rag import (
    load_knowledge_base,
    load_embedding_model,
    chapters_from_metadata,
    retrieve,
    retrieve_topics,
)

from utils.question_generator import (
    generate_paper,
    generate_single_question,
)

from utils.validators import validate_paper
from utils.docx_exporter import build_docx, build_answer_key_docx
from utils.pdf_exporter import build_pdf


# =========================================================
# CONFIGURATION
# =========================================================

ROOT = Path(__file__).resolve().parent

st.set_page_config(
    page_title="FBISE Physics AI Paper Generator",
    page_icon="📘",
    layout="wide",
)

st.title("FBISE Physics AI Paper Generator")

st.caption(
    "Textbook-grounded • FBISE-calibrated • "
    "Simple Test or FLP • Compact printing"
)


# =========================================================
# LOAD STREAMLIT SECRETS
# =========================================================

for k in [
    "GROQ_API_KEY",
    "LLM_API_KEY",
    "LLM_MODEL",
    "LLM_BASE_URL",
]:
    try:
        if k in st.secrets:
            os.environ[k] = str(st.secrets[k])
    except Exception:
        pass


# =========================================================
# CACHED MODELS / KNOWLEDGE BASE
# =========================================================

@st.cache_resource
def emb():
    return load_embedding_model()


@st.cache_resource
def kb(year):
    return load_knowledge_base(
        ROOT / "vector_store" / year
    )


# =========================================================
# PAPER PREVIEW
# =========================================================

def preview(p, s):

    st.subheader("Paper Preview")

    mcqs = p.get("mcqs", [])
    short_questions = p.get("short_questions", [])
    long_questions = p.get("long_questions", [])

    mcq_marks = s.get("mcq_marks", 1)
    short_marks = s.get("short_marks", 3)
    long_marks = s.get("long_marks", 5)

    short_attempt = s.get(
        "short_attempt",
        len(short_questions),
    )

    long_attempt = s.get(
        "long_attempt",
        len(long_questions),
    )

    # -----------------------------------------------------
    # TITLE
    # -----------------------------------------------------

    if s.get("paper_type") == "FLP Paper":

        st.markdown(
            f"### Physics {s.get('level', '')} - FLP"
        )

        st.markdown(
            "#### SECTION-A (OBJECTIVE)"
        )

        st.write(
            f"Q No 1: MULTIPLE CHOICE QUESTIONS "
            f"[{mcq_marks}×{len(mcqs)}="
            f"{mcq_marks * len(mcqs)}]"
        )

    else:

        part = (
            "PART-I"
            if s.get("level") == "HSSC-I"
            else "PART-II"
        )

        st.markdown(
            f"### FSC {part} (FEDERAL)"
        )

        if s.get("scope_mode") == "Topic-wise test":

            st.write(
                "Topics: "
                + s.get("topics", "")
            )

        else:

            st.write(
                "Chapters ("
                + ", ".join(
                    s.get("chapters", [])
                )
                + ")"
            )

        st.markdown(
            "#### Encircle the right answer"
        )

    # -----------------------------------------------------
    # MCQs
    # -----------------------------------------------------

    for i, q in enumerate(mcqs, 1):

        question = q.get(
            "question",
            "",
        )

        options = q.get(
            "options",
            {},
        )

        st.markdown(
            f"**{i}. {question}**"
        )

        st.write(
            f"A. {options.get('A', '')}    "
            f"B. {options.get('B', '')}    "
            f"C. {options.get('C', '')}    "
            f"D. {options.get('D', '')}"
        )

    # -----------------------------------------------------
    # SHORT QUESTIONS
    # -----------------------------------------------------

    if s.get("paper_type") == "FLP Paper":

        st.markdown(
            "#### SECTION-B (SHORT QUESTIONS)"
        )

    else:

        st.markdown(
            "#### Short questions"
        )

    if short_questions:

        if short_attempt < len(short_questions):

            attempt_text = (
                f"any {short_attempt}"
            )

        else:

            attempt_text = "all"

        st.caption(
            f"Attempt {attempt_text} questions. "
            f"Each question carries "
            f"{short_marks} marks."
        )

    for i, q in enumerate(
        short_questions,
        1,
    ):

        st.write(
            f"{i}. {q.get('question', '')}"
        )

        if q.get("or_question"):

            st.markdown(
                "**OR**"
            )

            st.write(
                q.get("or_question")
            )

    # -----------------------------------------------------
    # LONG QUESTIONS
    # -----------------------------------------------------

    if s.get("paper_type") == "FLP Paper":

        st.markdown(
            "#### SECTION-C (LONG QUESTIONS)"
        )

    else:

        st.markdown(
            "#### Long questions"
        )

    if long_questions:

        if long_attempt < len(long_questions):

            attempt_text = (
                f"any {long_attempt}"
            )

        else:

            attempt_text = "all"

        st.caption(
            f"Attempt {attempt_text} questions. "
            f"Each question carries "
            f"{long_marks} marks."
        )

    for i, q in enumerate(
        long_questions,
        1,
    ):

        st.write(
            f"{i}. {q.get('question', '')}"
        )

        if q.get("or_question"):

            st.markdown(
                "**OR**"
            )

            st.write(
                q.get("or_question")
            )


# =========================================================
# CLASS / LEVEL
# =========================================================

level_label = st.selectbox(
    "1. Class / Level",
    [
        "FSC Part-I / HSSC-I / First Year",
        "FSC Part-II / HSSC-II / Second Year",
    ],
)

year = (
    "first_year"
    if "Part-I" in level_label
    else "second_year"
)

level = (
    "HSSC-I"
    if year == "first_year"
    else "HSSC-II"
)


# =========================================================
# LOAD KNOWLEDGE BASE
# =========================================================

try:

    index, metadata = kb(year)

    available = chapters_from_metadata(
        metadata
    )

except Exception as e:

    st.error(str(e))

    st.info(
        "First run `python ingest.py`, commit "
        "vector_store to GitHub, then deploy."
    )

    st.stop()


# =========================================================
# SCOPE
# =========================================================

scope_mode = st.radio(
    "2. What do you want the test from?",
    [
        "Chapter-wise test",
        "Topic-wise test",
    ],
    horizontal=True,
    help=(
        "Chapter-wise: questions may come from anywhere "
        "in the selected chapter(s). "
        "Topic-wise: type topic names and the app "
        "finds their chapter(s) automatically."
    ),
)


if scope_mode == "Chapter-wise test":

    if not available:

        st.error(
            "No chapter headings were detected in "
            "this textbook index."
        )

    chapters = st.multiselect(
        "Select chapter(s)",
        available,
        default=available[:1],
    )

    topic_text = ""

    st.caption(
        "Complete chapter means questions can be "
        "generated from any supported content anywhere "
        "in the selected chapter(s)."
    )

else:

    chapters = []

    topic_text = st.text_area(
        "Type the topic name(s)",
        placeholder=(
            "Examples: projectile motion; "
            "angular momentum; Bernoulli equation"
        ),
        help=(
            "You do not need to know the chapter number. "
            "Enter topics that exist in the selected "
            "Physics textbook."
        ),
    )

    st.caption(
        "The app searches the selected textbook, "
        "finds relevant passages and keeps the generated "
        "paper focused on the requested topics."
    )


# =========================================================
# PAPER TYPE
# =========================================================

paper_type = st.radio(
    "3. Paper pattern",
    [
        "Simple Test",
        "FLP Paper",
    ],
    horizontal=True,
)

st.info(
    "Selected output pattern: **"
    + paper_type
    + "**"
)


# =========================================================
# DIFFICULTY
# =========================================================

difficulty = st.radio(
    "4. Difficulty",
    [
        "FBISE Standard",
        "Easy",
        "Moderate",
        "Challenging",
    ],
    horizontal=True,
    index=0,
)

st.caption(
    "FBISE Standard uses concise conceptual, "
    "reasoning, application, numerical and "
    "derivation-style questions where appropriate."
)


# =========================================================
# QUESTION COUNTS / MARKS
# =========================================================

c1, c2, c3 = st.columns(3)

with c1:

    mcq_count = st.number_input(
        "MCQs",
        0,
        50,
        10,
    )

    mcq_marks = st.number_input(
        "Marks / MCQ",
        1,
        10,
        1,
    )

with c2:

    short_count = st.number_input(
        "Short questions",
        0,
        30,
        11,
    )

    short_marks = st.number_input(
        "Marks / short",
        1,
        20,
        3,
    )

with c3:

    long_count = st.number_input(
        "Long questions",
        0,
        15,
        3,
    )

    long_marks = st.number_input(
        "Marks / long",
        1,
        30,
        5,
    )


# =========================================================
# OR PATTERN
# =========================================================

st.markdown(
    "#### 5. Student choice / OR pattern"
)

or_mode = st.radio(
    "OR choices",
    [
        "No OR choices",
        "OR in Short Questions only",
        "OR in Long Questions only",
        "OR in both Short and Long Questions",
    ],
    horizontal=True,
)

or_short = or_mode in [
    "OR in Short Questions only",
    "OR in both Short and Long Questions",
]

or_long = or_mode in [
    "OR in Long Questions only",
    "OR in both Short and Long Questions",
]


# =========================================================
# BALANCE / ATTEMPT COUNTS
# =========================================================

balanced = st.checkbox(
    "Balanced chapter distribution",
    True,
)

ca, cb = st.columns(2)

with ca:

    short_attempt = st.number_input(
        "Short questions students must attempt",
        0,
        int(short_count),
        int(short_count),
    )

with cb:

    long_attempt = st.number_input(
        "Long questions students must attempt",
        0,
        int(long_count),
        int(long_count),
    )


# =========================================================
# SCENARIO
# =========================================================

scenario = st.text_area(
    "6. Describe the test you want",
    placeholder=(
        "Focus on projectile motion and rotational "
        "dynamics; prefer conceptual questions."
    ),
)


answer_key = st.checkbox(
    "Generate Teacher Answer Key"
)


# =========================================================
# SETTINGS
# =========================================================

s = {
    "level": level,
    "chapters": chapters,
    "scope_mode": scope_mode,
    "topics": topic_text,
    "paper_type": paper_type,
    "difficulty": difficulty,
    "mcq_count": int(mcq_count),
    "short_count": int(short_count),
    "long_count": int(long_count),
    "mcq_marks": int(mcq_marks),
    "short_marks": int(short_marks),
    "long_marks": int(long_marks),
    "or_short": or_short,
    "or_long": or_long,
    "balanced": balanced,
    "short_attempt": int(short_attempt),
    "long_attempt": int(long_attempt),
    "scenario": scenario,
}


ready = (
    bool(chapters)
    if scope_mode == "Chapter-wise test"
    else bool(topic_text.strip())
)


# =========================================================
# GENERATE PAPER
# =========================================================

if st.button(
    "Generate Paper",
    type="primary",
    disabled=not ready,
):

    try:

        wanted_k = max(
            10,
            min(
                18,
                int(mcq_count)
                + int(short_count)
                + int(long_count),
            ),
        )

        # -------------------------------------------------
        # CHAPTER-WISE
        # -------------------------------------------------

        if scope_mode == "Chapter-wise test":

            q = (
                f"Physics assessment evidence from "
                f"{', '.join(chapters)}. "
                f"{scenario} "
                f"definitions laws principles applications "
                f"examples derivations numericals conceptual "
                f"exercise"
            )

            chunks = retrieve(
                q,
                index,
                metadata,
                emb(),
                chapters,
                top_k=wanted_k,
            )

            effective_chapters = chapters

            if not chunks:

                raise RuntimeError(
                    "No textbook evidence found "
                    "for those chapters."
                )

        # -------------------------------------------------
        # TOPIC-WISE
        # -------------------------------------------------

        else:

            chunks, topic_map = retrieve_topics(
                topic_text.strip(),
                index,
                metadata,
                emb(),
                per_topic=4,
                total_limit=min(
                    10,
                    wanted_k,
                ),
            )

            if scenario.strip():

                extra = retrieve(
                    scenario.strip(),
                    index,
                    metadata,
                    emb(),
                    chapters=None,
                    top_k=2,
                )

                known = {
                    (
                        c.get("page"),
                        c.get("chunk_id"),
                    )
                    for c in chunks
                }

                chunks += [
                    c
                    for c in extra
                    if (
                        c.get("page"),
                        c.get("chunk_id"),
                    )
                    not in known
                ]

            if not chunks:

                raise RuntimeError(
                    "No matching textbook passages "
                    "were found for those topics."
                )

            inferred = sorted(
                {
                    c.get("chapter")
                    for c in chunks
                    if c.get("chapter")
                    not in (
                        None,
                        "Unknown",
                    )
                }
            )

            effective_chapters = inferred

            s["chapters"] = effective_chapters

            if inferred:

                st.info(
                    "Relevant textbook material found in: **"
                    + ", ".join(inferred)
                    + "**. The paper will stay focused on: **"
                    + topic_text.strip()
                    + "**."
                )

            else:

                st.info(
                    "Relevant textbook passages were found. "
                    "The PDF chapter label was not readable, "
                    "but topic-wise generation can continue "
                    "from the matched textbook pages."
                )

        # -------------------------------------------------
        # GENERATION
        # -------------------------------------------------

        with st.spinner(
            "Retrieving textbook evidence and generating "
            "FBISE-style paper..."
        ):

            p = generate_paper(
                chunks,
                s,
            )

        # -------------------------------------------------
        # VALIDATION
        # -------------------------------------------------

        errs = validate_paper(
            p,
            (
                int(mcq_count),
                int(short_count),
                int(long_count),
            ),
            effective_chapters,
            scope_mode,
        )

        # IMPORTANT:
        # save a COPY so later Streamlit widget changes
        # do not unexpectedly modify generated settings.

        st.session_state.paper = p
        st.session_state.settings = dict(s)
        st.session_state.chunks = chunks

        if errs:

            st.warning(
                "Review suggested: "
                + " | ".join(
                    errs[:6]
                )
            )

    except Exception as e:

        st.error(
            str(e)
        )


# =========================================================
# DISPLAY GENERATED PAPER
# =========================================================

if "paper" in st.session_state:

    p = st.session_state.paper

    s_saved = st.session_state.get(
        "settings",
        {},
    )

    preview(
        p,
        s_saved,
    )

    # -----------------------------------------------------
    # TEXTBOOK SOURCES
    # -----------------------------------------------------

    with st.expander(
        "Teacher grounding / textbook sources"
    ):

        for c in st.session_state.get(
            "chunks",
            [],
        )[:12]:

            chapter = c.get(
                "chapter",
                c.get(
                    "unit_title",
                    "Unknown",
                ),
            )

            page = c.get(
                "page",
                c.get(
                    "pdf_page",
                    "?",
                ),
            )

            score = c.get(
                "score",
                0.0,
            )

            st.caption(
                f"{chapter} • "
                f"p.{page} • "
                f"similarity {score:.3f}"
            )

            st.write(
                c.get(
                    "text",
                    "",
                )[:550]
            )

    # -----------------------------------------------------
    # DOWNLOADS
    # -----------------------------------------------------

    a, b, c = st.columns(3)

    a.download_button(
        "Download Word",
        build_docx(
            p,
            s_saved,
        ),
        "FBISE_Physics_Paper.docx",
    )

    b.download_button(
        "Download PDF",
        build_pdf(
            p,
            s_saved,
        ),
        "FBISE_Physics_Paper.pdf",
        "application/pdf",
    )

    # The new structured generator intentionally keeps
    # the first generation compact. The existing exporter
    # can still create a basic key for available fields.

    if answer_key:

        c.download_button(
            "Download Answer Key",
            build_answer_key_docx(
                p,
                s_saved,
            ),
            "Teacher_Answer_Key.docx",
        )


# =========================================================
# SINGLE QUESTION
# =========================================================

st.divider()

st.subheader(
    "Generate one question"
)

topic = st.text_input(
    "Topic / scenario",
    placeholder=(
        "Projectile motion of a football"
    ),
)

mode = st.radio(
    "Question style",
    [
        "Simple Question",
        "FLP-Style Question",
    ],
    horizontal=True,
)


if st.button(
    "Generate One Question",
    disabled=not topic,
):

    try:

        hits, _ = retrieve_topics(
            topic,
            index,
            metadata,
            emb(),
            per_topic=6,
            total_limit=8,
        )

        if not hits:

            raise RuntimeError(
                "Topic not found in the "
                "selected textbook."
            )

        inferred = sorted(
            {
                h.get("chapter")
                for h in hits
                if h.get("chapter")
                not in (
                    None,
                    "Unknown",
                )
            }
        )

        st.caption(
            "Detected chapter: "
            + (
                ", ".join(inferred)
                if inferred
                else (
                    "chapter label unavailable; "
                    "matched textbook pages used"
                )
            )
        )

        result = generate_single_question(
            hits,
            level,
            topic,
            mode,
        )

        st.success(
            result.get(
                "question",
                "",
            )
        )

    except Exception as e:

        st.error(
            str(e)
        )