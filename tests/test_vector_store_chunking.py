from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app_core.retrieval.vector_store import CARD_CHUNK_HARD_LIMIT, VectorStore


CARD_TEXT = """# The Fool

card_name: The Fool
arcana: major
suit: none
rank: 0
slug: the_fool

## Core Themes
- beginnings, openness, and fresh possibility
- trust, curiosity, and creative risk

## Upright Meaning
The Fool suggests a threshold moment: something new is opening, but it may
not yet be fully defined. This card can describe a fresh start, a change of
direction, or the need to meet life with curiosity rather than over-control.

## Shadow Or Reversed Nuance
The shadow of The Fool is impulsiveness, naivety, avoidance of consequences,
or risk without reflection. It can also show fear of the unknown or clinging
to old methods.

## Interpretation Notes
- Read this card as potential, not proof that a new path will succeed.
- In advice positions, it often favors openness and experimentation.
"""

GENERIC_STYLE_TEXT = "# Some Style Doc\n\n" + "\n\n".join(
    f"Paragraph {i}: " + ("lorem ipsum dolor sit amet consectetur adipiscing elit " * 4)
    for i in range(6)
)


def _make_vector_store(tmp_path, monkeypatch, *, chunk_size="500", chunk_overlap="60", min_chunk_len="60"):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("RAG_CHUNK_SIZE", chunk_size)
    monkeypatch.setenv("RAG_CHUNK_OVERLAP", chunk_overlap)
    monkeypatch.setenv("RAG_MIN_CHUNK_LEN", min_chunk_len)
    monkeypatch.delenv("RAG_MAX_DISTANCE", raising=False)
    return VectorStore(
        collection_name=f"test_{tmp_path.name}",
        persist_directory=str(tmp_path),
    )


def test_card_document_is_a_single_chunk(tmp_path, monkeypatch):
    vs = _make_vector_store(tmp_path, monkeypatch)

    rows = vs._build_chunks_for_file(
        CARD_TEXT,
        source="card:the_fool",
        source_display="Card: The Fool",
        source_kind="card",
        doc_type="overview",
        source_path="knowledge_base/tarot/cards/major_arcana/00_the_fool.md",
    )

    assert len(rows) == 1
    doc_text, meta = rows[0]
    assert "Upright Meaning" in doc_text
    assert "Shadow Or Reversed Nuance" in doc_text
    assert meta["source_kind"] == "card"


def test_normal_size_card_survives_hard_limit_pass_as_one_chunk(tmp_path, monkeypatch):
    vs = _make_vector_store(tmp_path, monkeypatch)

    rows = vs._build_chunks_for_file(
        CARD_TEXT,
        source="card:the_fool",
        source_display="Card: The Fool",
        source_kind="card",
        doc_type="overview",
        source_path="knowledge_base/tarot/cards/major_arcana/00_the_fool.md",
    )
    limited = vs._enforce_hard_chunk_limit(rows, overlap=vs.chunk_overlap)

    assert len(limited) == 1


def test_non_card_document_is_still_chunked(tmp_path, monkeypatch):
    vs = _make_vector_store(tmp_path, monkeypatch)

    rows = vs._build_chunks_for_file(
        GENERIC_STYLE_TEXT,
        source="style:some_doc",
        source_display="Style: Some Doc",
        source_kind="style",
        doc_type="overview",
        source_path="knowledge_base/tarot/style/some_doc.md",
    )

    assert len(rows) > 1
    for doc_text, _meta in rows:
        assert len(doc_text) <= vs.chunk_size


def test_hard_limit_still_splits_an_oversized_card(tmp_path, monkeypatch):
    vs = _make_vector_store(tmp_path, monkeypatch)

    huge_text = "# Huge Card\n\n## Upright Meaning\n" + ("word " * 3000)
    assert len(huge_text) > CARD_CHUNK_HARD_LIMIT

    rows = vs._build_chunks_for_file(
        huge_text,
        source="card:huge",
        source_display="Card: Huge",
        source_kind="card",
        doc_type="overview",
        source_path="knowledge_base/tarot/cards/major_arcana/99_huge.md",
    )
    # The per-file builder does not split cards; the hard-limit pass is the safety net.
    assert len(rows) == 1
    assert len(rows[0][0]) > CARD_CHUNK_HARD_LIMIT

    limited = vs._enforce_hard_chunk_limit(rows, overlap=vs.chunk_overlap)

    assert len(limited) > 1
    for doc_text, _meta in limited:
        assert len(doc_text) <= CARD_CHUNK_HARD_LIMIT
