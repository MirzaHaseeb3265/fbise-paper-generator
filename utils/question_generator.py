from __future__ import annotations

import json
import os
import re
import requests


FBISE_STYLE = """
Calibrate difficulty to the supplied FBISE reference-paper style, not to
generic difficult questions.

Use an HSSC/FSC Federal Board level mixture of:
- concise knowledge/recall
- conceptual understanding
- reasoning
- applications
- dimensional reasoning where relevant
- short calculations/numericals where relevant
- derivations where appropriate

Typical commands include:
define, differentiate, explain why, under what condition, state and explain,
derive, calculate, show/prove, and apply.

MCQs should normally test one clear concept or relationship and have plausible
distractors.

Short questions should normally be compact FBISE-style tasks.

Long questions may combine explanation, derivation, application or numerical
work when supported by the supplied textbook evidence.

Do not make questions artificially advanced.
"""


SYSTEM = f"""
You are an expert FBISE Pakistan HSSC Physics paper setter.

Use ONLY the supplied textbook evidence as factual knowledge.

{FBISE_STYLE}

CRITICAL GROUNDING RULES:

1. Never introduce a Physics concept that is not supported by the supplied
   textbook evidence.

2. If TOPIC-WISE MODE is specified, every generated question MUST directly
   test one of the teacher's requested topics.

3. Related textbook material may be used only when it is necessary to
   understand or solve the requested topic.

4. Do NOT generate questions merely because another concept appears in the
   same chapter or retrieved textbook page.

5. A requested topic is a HARD SCOPE BOUNDARY in Topic-wise mode.

6. If CHAPTER-WISE MODE is specified, questions may come from anywhere in
   the selected chapter(s), provided they are supported by the supplied
   textbook evidence.

7. Never invent facts, formulas, numerical constants or unsupported
   relationships.

8. Avoid duplicate and near-duplicate questions.

9. Numerical questions must provide sufficient information to solve them.

10. Preserve correct Physics notation as far as possible.

11. Student question text must never reveal the answer.

12. Return valid JSON only.
"""


def _cfg():

    key = (
        os.getenv("LLM_API_KEY")
        or os.getenv("GROQ_API_KEY")
    )

    base = os.getenv(
        "LLM_BASE_URL",
        "https://api.groq.com/openai/v1",
    ).rstrip("/")

    # Current fallback used if LLM_MODEL is not provided
    # through Streamlit Secrets.
    model = os.getenv(
        "LLM_MODEL",
        "openai/gpt-oss-120b",
    )

    return key, base, model


def _json(text):

    text = re.sub(
        r"^```(?:json)?|```$",
        "",
        text.strip(),
        flags=re.M,
    ).strip()

    a = text.find("{")
    b = text.rfind("}")

    if a < 0 or b < a:
        raise ValueError(
            "The LLM did not return valid JSON."
        )

    return json.loads(text[a:b + 1])


def generate_paper(chunks, s):

    key, base, model = _cfg()

    if not key:
        raise RuntimeError(
            "API key missing. Add GROQ_API_KEY to Streamlit Secrets."
        )

    # -----------------------------------------------------
    # TEXTBOOK CONTEXT
    # -----------------------------------------------------

    ctx = "\n\n".join(
        (
            f"[TEXTBOOK | {c.get('chapter', 'Unknown')} | "
            f"PDF page {c.get('page', '?')}]\n"
            f"{c.get('text', '')}"
        )
        for c in chunks
    )

    # -----------------------------------------------------
    # PAPER PATTERN
    # -----------------------------------------------------

    if s["paper_type"] == "FLP Paper":

        pattern = """
FLP PATTERN:
Use Section A for objective questions,
Section B for short questions,
and Section C for long questions.

Questions may use contextual/application-oriented FBISE wording where
supported by the textbook evidence.
"""

    else:

        pattern = """
SIMPLE TEST PATTERN:
Use the compact college-test style represented by the supplied
Chapter 1,2,3,4,5 sample.

Do not use unnecessary FLP-style section language.
"""

    # -----------------------------------------------------
    # OR RULES
    # -----------------------------------------------------

    or_rule = f"""
Short-question OR choices: {'ON' if s['or_short'] else 'OFF'}
Long-question OR choices: {'ON' if s['or_long'] else 'OFF'}

When OR is OFF:
or_question MUST be null.

When OR is ON:
each relevant question must contain a comparable alternative testing
approximately the same level of difficulty.
"""

    # -----------------------------------------------------
    # SCOPE RULES
    # -----------------------------------------------------

    scope_mode = s.get(
        "scope_mode",
        "Chapter-wise test",
    )

    topics = s.get(
        "topics",
        "",
    ).strip()

    if scope_mode == "Topic-wise test":

        scope_rule = f"""
================ TOPIC-WISE MODE ================

TEACHER'S REQUESTED TOPICS:

{topics}

These topics are a STRICT SCOPE BOUNDARY.

EVERY MCQ, EVERY SHORT QUESTION, EVERY LONG QUESTION,
and EVERY OR ALTERNATIVE must directly test one of the
requested topics above.

Do NOT generate a question simply because its concept occurs
in the same unit/chapter.

Do NOT broaden the paper to the whole chapter.

For example, if the requested topic is "Heat Engine", retrieved
pages may contain entropy, temperature, thermodynamic processes
or other material. That does NOT automatically permit questions
about those concepts.

Only use surrounding textbook information when it directly
supports the requested topic.

Before including each question, internally ask:

"Does this question directly assess one of the teacher's
requested topics?"

If NO, discard it and generate another question.

=================================================
"""

    else:

        selected = ", ".join(
            s.get("chapters", [])
        )

        scope_rule = f"""
================ CHAPTER-WISE MODE ==============

Selected chapter/unit(s):

{selected}

Questions may be generated from anywhere within these selected
units, provided the question is supported by the supplied
textbook evidence.

Do NOT use material from units outside the selection.

=================================================
"""

    # -----------------------------------------------------
    # JSON FORMAT
    # -----------------------------------------------------

    schema = {
        "mcqs": [
            {
                "question": "",
                "options": {
                    "A": "",
                    "B": "",
                    "C": "",
                    "D": "",
                },
                "correct_answer": "A",
                "chapter": "Unit 1",
                "source_pages": [1],
                "question_type": "conceptual",
                "answer_explanation": "",
            }
        ],
        "short_questions": [
            {
                "question": "",
                "or_question": None,
                "chapter": "Unit 1",
                "source_pages": [1],
                "question_type": "reasoning",
                "answer_key_points": [],
            }
        ],
        "long_questions": [
            {
                "question": "",
                "or_question": None,
                "chapter": "Unit 1",
                "source_pages": [1],
                "question_type": "derivation",
                "marking_outline": [],
            }
        ],
    }

    # -----------------------------------------------------
    # FINAL PROMPT
    # -----------------------------------------------------

    prompt = f"""
Generate ONE student Physics paper.

{scope_rule}

{pattern}

{or_rule}

EXACT NUMBER OF QUESTIONS:

MCQs: {s['mcq_count']}
Short questions: {s['short_count']}
Long questions: {s['long_count']}

Class:
{s['level']}

Difficulty:
{s['difficulty']}

Balanced distribution:
{s['balanced']}

Additional teacher instruction/scenario:
{s.get('scenario') or 'None'}

Question mixture:
{s.get(
    'question_mix',
    'Use the FBISE reference-paper mixture of conceptual, knowledge, '
    'application, numerical and derivation tasks where appropriate.'
)}

IMPORTANT:

The textbook evidence below is a KNOWLEDGE SOURCE.
It does NOT expand the requested scope.

In Topic-wise mode, retrieved passages may contain neighbouring
concepts. Ignore those neighbouring concepts unless they are directly
necessary for the teacher's requested topic.

Return exactly the following JSON structure, with arrays containing
the exact requested number of questions:

{json.dumps(schema, ensure_ascii=False)}

================ TEXTBOOK EVIDENCE ===============

{ctx}

==================================================
"""

    # -----------------------------------------------------
    # GROQ REQUEST
    # -----------------------------------------------------

    r = requests.post(
        base + "/chat/completions",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "temperature": 0.20,
            "response_format": {
                "type": "json_object"
            },
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
        },
        timeout=180,
    )

    if not r.ok:

        raise RuntimeError(
            f"LLM API error {r.status_code}: "
            f"{r.text[:500]}"
        )

    return _json(
        r.json()["choices"][0]["message"]["content"]
    )


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
                c.get("chapter", "Unknown")
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

    return generate_paper(
        chunks,
        settings,
    )["short_questions"][0]