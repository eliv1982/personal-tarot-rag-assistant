from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app_core.retrieval.vector_store import VectorStore


def _doc(distance):
    return {"id": f"doc-{distance}", "text": "text", "distance": distance, "metadata": {}}


def test_filter_drops_candidates_above_threshold():
    docs = [_doc(0.1), _doc(0.44), _doc(0.45), _doc(0.9)]

    filtered = VectorStore._filter_by_max_distance(docs, max_distance=0.44)

    assert [d["distance"] for d in filtered] == [0.1, 0.44]


def test_filter_is_noop_when_threshold_is_unset():
    docs = [_doc(0.1), _doc(5.0)]

    assert VectorStore._filter_by_max_distance(docs, max_distance=None) == docs


def test_filter_keeps_backfill_docs_with_no_distance():
    docs = [_doc(None), _doc(0.9)]

    filtered = VectorStore._filter_by_max_distance(docs, max_distance=0.44)

    assert filtered == [docs[0]]


def test_filter_can_leave_nothing_after_threshold():
    docs = [_doc(0.9), _doc(1.2)]

    assert VectorStore._filter_by_max_distance(docs, max_distance=0.44) == []


def test_max_distance_is_read_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("RAG_MAX_DISTANCE", "0.44")

    vs = VectorStore(collection_name=f"t1_{tmp_path.name}", persist_directory=str(tmp_path))

    assert vs.max_distance == 0.44


def test_max_distance_defaults_to_none_when_unset(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.delenv("RAG_MAX_DISTANCE", raising=False)

    vs = VectorStore(collection_name=f"t2_{tmp_path.name}", persist_directory=str(tmp_path))

    assert vs.max_distance is None
