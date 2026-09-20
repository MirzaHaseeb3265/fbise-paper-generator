from __future__ import annotations

import pickle
import re
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


# ---------------------------------------------------------
# LOAD VECTOR DATABASE
# ---------------------------------------------------------

def load_knowledge_base(store_dir: Path):

    idx = store_dir / "index.faiss"
    meta = store_dir / "metadata.pkl"

    if not idx.exists() or not meta.exists():
        raise FileNotFoundError(
            f"Run ingest.py first. Missing files in {store_dir}"
        )

    index = faiss.read_index(str(idx))

    with open(meta, "rb") as f:
        metadata = pickle.load(f)

    return index, metadata


def load_embedding_model():
    return SentenceTransformer(MODEL_NAME)


# ---------------------------------------------------------
# UNIT / CHAPTER HELPERS
# ---------------------------------------------------------

def chapter_label(item):
    """
    Convert OCR metadata into a friendly chapter label.

    Example:
        Unit 8 — Heat and Thermodynamics
    """

    unit = item.get("unit")
    title = item.get("unit_title", "")

    if unit is None:
        return "Unknown"

    if title:
        return f"Unit {unit} — {title}"

    return f"Unit {unit}"


def chapters_from_metadata(metadata):
    """
    Return all units available in the selected textbook.
    """

    chapters = {}

    for item in metadata:

        unit = item.get("unit")

        if unit is None:
            continue

        title = item.get("unit_title", "")

        chapters[int(unit)] = (
            f"Unit {unit} — {title}"
            if title
            else f"Unit {unit}"
        )

    return [
        chapters[number]
        for number in sorted(chapters)
    ]


def unit_number_from_label(label):
    """
    Extract 8 from:
    Unit 8 — Heat and Thermodynamics
    """

    if label is None:
        return None

    match = re.search(r"\b(?:Unit|Chapter)\s*(\d+)", str(label), re.I)

    if match:
        return int(match.group(1))

    try:
        return int(label)
    except Exception:
        return None


# ---------------------------------------------------------
# GENERAL RETRIEVAL
# ---------------------------------------------------------

def retrieve(
    query,
    index,
    metadata,
    model,
    chapters=None,
    top_k=12,
):

    q = np.asarray(
        model.encode(
            [query],
            normalize_embeddings=True,
        ),
        dtype="float32",
    )

    # Search more candidates first so chapter filtering
    # still leaves enough useful chunks.
    k = min(
        max(top_k * 12, 80),
        index.ntotal,
    )

    scores, ids = index.search(q, k)

    wanted_units = set()

    for chapter in chapters or []:

        number = unit_number_from_label(chapter)

        if number is not None:
            wanted_units.add(number)

    out = []

    for score, i in zip(scores[0], ids[0]):

        if i < 0:
            continue

        m = metadata[int(i)]

        if wanted_units:

            try:
                metadata_unit = int(m.get("unit"))
            except (TypeError, ValueError):
                continue

            if metadata_unit not in wanted_units:
                continue

        item = dict(m)

        # Compatibility fields for the rest of the app.
        item["chapter"] = chapter_label(m)
        item["page"] = m.get("pdf_page")
        item["chunk_id"] = m.get("chunk_number")

        item["score"] = float(score)

        out.append(item)

        if len(out) >= top_k:
            break

    return out


# ---------------------------------------------------------
# TOPIC-WISE RETRIEVAL
# ---------------------------------------------------------

def split_topics(text: str):

    return [
        x.strip()
        for x in re.split(r"[,;\n]+", text)
        if x.strip()
    ]


def retrieve_topics(
    topic_text,
    index,
    metadata,
    model,
    per_topic=10,
    total_limit=48,
):
    """
    Search every teacher-entered topic independently.

    Example:
        Heat Engine, Isothermal Process

    Heat Engine is searched separately.
    Isothermal Process is searched separately.

    This prevents one topic from dominating retrieval.
    """

    topics = split_topics(topic_text)

    if not topics and topic_text.strip():
        topics = [topic_text.strip()]

    merged = []
    seen = set()
    topic_map = {}

    for topic in topics:

        # Add Physics-oriented wording to improve retrieval
        # while keeping the original topic dominant.
        search_query = (
            f"{topic}. Physics textbook explanation, definition, "
            f"principle, equation, application and example."
        )

        hits = retrieve(
            search_query,
            index,
            metadata,
            model,
            chapters=None,
            top_k=per_topic,
        )

        topic_map[topic] = hits

        for hit in hits:

            key = (
                hit.get("pdf_page"),
                hit.get("chunk_number"),
                hit.get("text", "")[:100],
            )

            if key not in seen:
                seen.add(key)
                merged.append(hit)

    # Keep best matches overall.
    merged.sort(
        key=lambda h: h.get("score", 0),
        reverse=True,
    )

    return merged[:total_limit], topic_map


# ---------------------------------------------------------
# INFER UNITS FOR A TOPIC
# ---------------------------------------------------------

def infer_topic_chapters(
    query,
    index,
    metadata,
    model,
    top_k=16,
):

    hits, _ = retrieve_topics(
        query,
        index,
        metadata,
        model,
        per_topic=max(6, top_k // 2),
        total_limit=top_k,
    )

    chapter_scores = {}

    for hit in hits:

        chapter = hit.get("chapter", "Unknown")

        if chapter == "Unknown":
            continue

        chapter_scores.setdefault(
            chapter,
            [],
        ).append(
            hit.get("score", 0.0)
        )

    ranked = sorted(
        chapter_scores,
        key=lambda chapter: (
            sum(chapter_scores[chapter][:4])
            / min(4, len(chapter_scores[chapter]))
        ),
        reverse=True,
    )

    return ranked[:3], hits