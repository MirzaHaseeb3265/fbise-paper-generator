from __future__ import annotations

import json
import os

import requests


# =========================================================
# FBISE QUESTION STYLE
# =========================================================

FBISE_STYLE = """
Calibrate difficulty to FBISE Pakistan HSSC Physics level.

Use a suitable mixture of:
- knowledge/recall
- conceptual understanding
- reasoning
- applications
- short calculations/numericals where relevant
- derivations where relevant

Typical FBISE commands include:
define, differentiate, explain why, state, explain,
derive, calculate, show/prove, and apply.

MCQs should normally test one clear concept or relationship
and should contain plausible distractors.

Short questions should be compact FBISE-style tasks.

Long questions may combine explanation, derivation,
application or numerical work where supported by the
textbook evidence.

Do not make questions artificially advanced.
"""


# =========================================================
# SYSTEM INSTRUCTIONS
# =========================================================

SYSTEM = f"""
You are an expert FBISE Pakistan HSSC Physics paper setter.

Use ONLY the supplied textbook evidence as factual knowledge.

{FBISE_STYLE}

GROUNDING RULES:

1. Never introduce a Physics concept unsupported by the
   supplied textbook evidence.

2. In TOPIC-WISE MODE, every generated question must
   directly test one of the teacher's requested topics.

3. Related textbook material may only be used when necessary
   to understand or solve the requested topic.

4. Do not generate questions merely because another concept
   appears on the same textbook page.

5. The requested topics are a HARD SCOPE BOUNDARY in
   Topic-wise mode.

6. In CHAPTER-WISE MODE, questions may come from anywhere
   within the selected unit(s), provided the supplied
   textbook evidence supports them.

7. Never invent unsupported facts, formulas, numerical
   constants or relationships.

8. Avoid duplicate and near-duplicate questions.

9. Numerical questions must contain sufficient data.

10. Preserve correct Physics notation where possible.

11. Student question text must never reveal its answer.

12. Follow the supplied JSON schema exactly.
"""


# =========================================================
# API CONFIGURATION
# =========================================================

def _cfg():

    key = (
        os.getenv("LLM_API_KEY")
        or os.getenv("GROQ_API_KEY")
    )

    base = os.getenv(
        "LLM_BASE_URL",
        "https://api.groq.com/openai/v1",
    ).rstrip("/")

    model = os.getenv(
        "LLM_MODEL",
        "openai/gpt-oss-120b",
    )

    return key, base, model


# =========================================================
# STRICT JSON SCHEMA
# =========================================================

PAPER_JSON_SCHEMA = {
    "type": "object",

    "properties": {

        "mcqs": {
            "type": "array",

            "items": {
                "type": "object",

                "properties": {

                    "question": {
                        "type": "string"
                    },

                    "options": {
                        "type": "object",

                        "properties": {
                            "A": {"type": "string"},
                            "B": {"type": "string"},
                            "C": {"type": "string"},
                            "D": {"type": "string"},
                        },

                        "required": [
                            "A",
                            "B",
                            "C",
                            "D",
                        ],

                        "additionalProperties": False,
                    },

                    "correct_answer": {
                        "type": "string",
                        "enum": [
                            "A",
                            "B",
                            "C",
                            "D",
                        ],
                    },
                },

                "required": [
                    "question",
                    "options",
                    "correct_answer",
                ],

                "additionalProperties": False,
            },
        },

        "short_questions": {
            "type": "array",

            "items": {
                "type": "object",

                "properties": {

                    "question": {
                        "type": "string"
                    },

                    # Strict mode requires the property to exist.
                    # null means there is no OR question.
                    "or_question": {
                        "type": [
                            "string",
                            "null",
                        ]
                    },
                },

                "required": [
                    "question",
                    "or_question",
                ],

                "additionalProperties": False,
            },
        },

        "long_questions": {
            "type": "array",

            "items": {
                "type": "object",

                "properties": {

                    "question": {
                        "type": "string"
                    },

                    "or_question": {
                        "type": [
                            "string",
                            "null",
                        ]
                    },
                },

                "required": [
                    "question",
                    "or_question",
                ],

                "additionalProperties": False,
            },
        },
    },

    "required": [
        "mcqs",
        "short_questions",
        "long_questions",
    ],

    "additionalProperties": False,
}


# =========================================================
# PAPER GENERATOR
# =========================================================

def generate_paper(chunks, s):

    key, base, model = _cfg()

    if not key:
        raise RuntimeError(
            "API key missing. Add GROQ_API_KEY "
            "to Streamlit Secrets."
        )

    # -----------------------------------------------------
    # TEXTBOOK EVIDENCE
    # -----------------------------------------------------

    context_parts = []

    for c in chunks:

        chapter = c.get(
            "chapter",
            c.get("unit_title", "Unknown"),
        )

        page = c.get(
            "page",
            c.get("pdf_page", "?"),
        )

        text = c.get(
            "text",
            "",
        )

        context_parts.append(
            f"[TEXTBOOK | {chapter} | "
            f"PDF page {page}]\n{text}"
        )

    ctx = "\n\n".join(context_parts)

    # Keep evidence small enough to leave substantial room
    # under the Groq TPM limit for FLP output.
    MAX_CONTEXT_CHARS = 4500

    if len(ctx) > MAX_CONTEXT_CHARS:
        ctx = ctx[:MAX_CONTEXT_CHARS]

    # -----------------------------------------------------
    # MODE
    # -----------------------------------------------------

    scope_mode = s.get(
        "scope_mode",
        "Chapter-wise test",
    )

    topics = s.get(
        "topics",
        "",
    ).strip()

    # -----------------------------------------------------
    # TOPIC-WISE SCOPE
    # -----------------------------------------------------

    if scope_mode == "Topic-wise test":

        scope_rule = f"""
TOPIC-WISE MODE

Teacher's requested topics:

{topics}

STRICT RULE:

Every MCQ, short question, long question and OR
alternative must directly test one of those topics.

Do NOT broaden the scope to the entire unit.

Retrieved passages may contain neighbouring concepts.
Their presence does NOT make them part of the test.

Use neighbouring material only when it is necessary
to understand or solve one of the requested topics.

Before keeping a question, check internally:

"Does this directly assess one of the requested topics?"

If not, discard it.
"""

    # -----------------------------------------------------
    # CHAPTER-WISE SCOPE
    # -----------------------------------------------------

    else:

        selected = ", ".join(
            s.get(
                "chapters",
                [],
            )
        )

        scope_rule = f"""
CHAPTER-WISE MODE

Selected unit(s):

{selected}

Generate questions only from these selected units.

Questions may cover different concepts inside the
selected units as long as they are supported by the
supplied textbook evidence.

Do not use material from units outside the selection.
"""

    # -----------------------------------------------------
    # PAPER TYPE
    # -----------------------------------------------------

    if s.get("paper_type") == "FLP Paper":

        pattern = """
PAPER TYPE: FLP

Use FBISE FLP-style questions.

Section A consists of MCQs.
Section B consists of short questions.
Section C consists of long questions.

Use contextual, conceptual, reasoning and
application-oriented wording where appropriate.

Keep the wording concise.
"""

    else:

        pattern = """
PAPER TYPE: SIMPLE TEST

Use compact FBISE college-test style.

Do not add unnecessary FLP wording.

Keep the wording concise.
"""

    # -----------------------------------------------------
    # OR CHOICES
    # -----------------------------------------------------

    if s.get("or_short"):

        short_or_rule = """
Every short question must have a comparable
OR alternative.

Therefore short-question or_question must contain
a question string.
"""

    else:

        short_or_rule = """
Short-question OR choices are OFF.

Therefore every short-question or_question
must be null.
"""

    if s.get("or_long"):

        long_or_rule = """
Every long question must have a comparable
OR alternative.

Therefore long-question or_question must contain
a question string.
"""

    else:

        long_or_rule = """
Long-question OR choices are OFF.

Therefore every long-question or_question
must be null.
"""

    # -----------------------------------------------------
    # QUESTION COUNTS
    # -----------------------------------------------------

    mcq_count = int(
        s.get(
            "mcq_count",
            0,
        )
    )

    short_count = int(
        s.get(
            "short_count",
            0,
        )
    )

    long_count = int(
        s.get(
            "long_count",
            0,
        )
    )

    # -----------------------------------------------------
    # PROMPT
    # -----------------------------------------------------

    prompt = f"""
Generate ONE FBISE HSSC Physics student paper.

{scope_rule}

{pattern}

{short_or_rule}

{long_or_rule}

EXACT COUNTS:

MCQs:
{mcq_count}

Short questions:
{short_count}

Long questions:
{long_count}

Class:
{s.get('level', '')}

Difficulty:
{s.get('difficulty', 'FBISE Standard')}

Balanced distribution:
{s.get('balanced', False)}

Additional teacher instruction/scenario:
{s.get('scenario') or 'None'}

Question mixture:
{s.get(
    'question_mix',
    'Use an FBISE-style mixture of conceptual, '
    'knowledge, application, numerical and derivation '
    'questions where appropriate.'
)}

IMPORTANT:

The textbook evidence is a KNOWLEDGE SOURCE.

It does NOT expand the requested topic/chapter scope.

Generate exactly the requested number of questions.

For each MCQ:
- provide exactly four options A, B, C and D
- correct_answer must be A, B, C or D
- only one option should be the best answer

For short and long questions:
- follow the OR-choice rules above exactly

Do not repeat questions.

Do not include answer explanations.

Do not include marking schemes.

Do not include source-page metadata.

Do not include chapter metadata in the output.

================ TEXTBOOK EVIDENCE ===============

{ctx}

==================================================
"""

    # -----------------------------------------------------
    # GROQ REQUEST
    # -----------------------------------------------------

    payload = {
        "model": model,

        # Lower reasoning reduces unnecessary token usage
        # on GPT-OSS while retaining enough reasoning for
        # question construction.
        "reasoning_effort": "low",

        "temperature": 0.0,

        "messages": [
            {
                "role": "system",
                "content": SYSTEM,
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],

        # Strict Structured Outputs.
        # Groq constrains generation to this schema.
        "response_format": {
            "type": "json_schema",

            "json_schema": {
                "name": "fbise_physics_paper",

                "strict": True,

                "schema": PAPER_JSON_SCHEMA,
            },
        },
    }

    r = requests.post(
        base + "/chat/completions",

        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },

        json=payload,

        timeout=180,
    )

    # -----------------------------------------------------
    # API ERROR
    # -----------------------------------------------------

    if not r.ok:

        raise RuntimeError(
            f"LLM API error {r.status_code}: "
            f"{r.text[:800]}"
        )

    # -----------------------------------------------------
    # READ STRICT JSON
    # -----------------------------------------------------

    response_data = r.json()

    try:

        raw_output = (
            response_data["choices"][0]
            ["message"]["content"]
        )

    except (
        KeyError,
        IndexError,
        TypeError,
    ):

        raise RuntimeError(
            "Groq returned an unexpected response."
        )

    if not raw_output:

        raise RuntimeError(
            "Groq returned an empty paper."
        )

    # With strict structured output this should always
    # be valid JSON conforming to PAPER_JSON_SCHEMA.
    try:

        paper = json.loads(
            raw_output
        )

    except json.JSONDecodeError as e:

        raise RuntimeError(
            "Groq Structured Output unexpectedly "
            f"returned invalid JSON: {e}"
        )

    # -----------------------------------------------------
    # EXTRA SAFETY CHECKS
    # -----------------------------------------------------

    if len(
        paper.get(
            "mcqs",
            [],
        )
    ) != mcq_count:

        raise RuntimeError(
            "Groq returned the wrong number of MCQs."
        )

    if len(
        paper.get(
            "short_questions",
            [],
        )
    ) != short_count:

        raise RuntimeError(
            "Groq returned the wrong number "
            "of short questions."
        )

    if len(
        paper.get(
            "long_questions",
            [],
        )
    ) != long_count:

        raise RuntimeError(
            "Groq returned the wrong number "
            "of long questions."
        )

    return paper


# =========================================================
# SINGLE QUESTION GENERATOR
# =========================================================

def generate_single_question(
    chunks,
    level,
    topic,
    mode="Simple Question",
):

    settings = {

        "mcq_count": 0,

        "short_count": 1,

        "long_count": 0,

        "difficulty": "FBISE Standard",

        "paper_type": (
            "FLP Paper"
            if mode.startswith("FLP")
            else "Simple Test"
        ),

        "chapters": sorted(
            {
                c.get(
                    "chapter",
                    c.get(
                        "unit_title",
                        "Unknown",
                    ),
                )
                for c in chunks
            }
        ),

        "scope_mode": "Topic-wise test",

        "topics": topic,

        "scenario": "",

        "balanced": False,

        "or_short": False,

        "or_long": False,
    }

    paper = generate_paper(
        chunks,
        settings,
    )

    return paper[
        "short_questions"
    ][0]