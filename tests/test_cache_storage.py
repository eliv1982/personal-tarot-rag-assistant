from __future__ import annotations

import sqlite3
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app_core.cache.storage import RAGCache, normalize_query_for_cache


def test_normalize_query_for_cache_collapses_whitespace_case_and_punctuation():
    assert normalize_query_for_cache("  What  Is  THE Fool?!  ") == "what is the fool"


def test_normalize_query_for_cache_is_stable_for_equivalent_queries():
    a = normalize_query_for_cache("Что значит Шут?")
    b = normalize_query_for_cache("что значит шут")
    assert a == b


def test_get_put_roundtrip(tmp_path):
    cache = RAGCache(str(tmp_path / "cache.db"))

    assert cache.get("What is the Fool card?") is None

    cache.set("What is the Fool card?", "It suggests a new beginning.", [{"id": "doc1"}])
    result = cache.get("what is the fool card?")

    assert result is not None
    assert result["answer"] == "It suggests a new beginning."
    assert result["context"] == [{"id": "doc1"}]


def test_cache_key_changes_with_corpus_version(tmp_path, monkeypatch):
    cache = RAGCache(str(tmp_path / "cache.db"))

    monkeypatch.setenv("RAG_CORPUS_VERSION", "v1")
    cache.set("question", "answer-v1")
    assert cache.get("question")["answer"] == "answer-v1"

    monkeypatch.setenv("RAG_CORPUS_VERSION", "v2")
    assert cache.get("question") is None


def test_connection_is_closed_even_when_an_error_occurs(tmp_path):
    cache = RAGCache(str(tmp_path / "cache.db"))
    captured = {}

    with pytest.raises(RuntimeError):
        with cache._connection() as conn:
            captured["conn"] = conn
            raise RuntimeError("boom")

    with pytest.raises(sqlite3.ProgrammingError):
        captured["conn"].execute("SELECT 1")


def test_connection_is_closed_after_normal_use(tmp_path):
    cache = RAGCache(str(tmp_path / "cache.db"))
    captured = {}

    with cache._connection() as conn:
        captured["conn"] = conn

    with pytest.raises(sqlite3.ProgrammingError):
        captured["conn"].execute("SELECT 1")
