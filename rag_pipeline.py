from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

from app_core.cache.storage import RAGCache
from app_core.config.knowledge import default_corpus_entries
from app_core.generation.answer_generator import generate_answer
from app_core.generation.prompts import build_rag_prompt
from app_core.llm.client import get_llm_client
from app_core.retrieval.vector_store import VectorStore


def _as_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _cache_path_from_env() -> str:
    explicit = (os.getenv("RAG_CACHE_DB_PATH") or "").strip()
    if explicit:
        return explicit
    return str(Path("runtime") / "rag_cache.db")


class RAGPipeline:
    def __init__(
        self,
        collection_name: Optional[str] = None,
        persist_directory: Optional[str] = None,
    ) -> None:
        self.collection_name = collection_name or os.getenv("CHROMA_COLLECTION", "rag_collection")
        self.persist_directory = (
            persist_directory
            or os.getenv("CHROMA_PERSIST_DIRECTORY")
            or os.getenv("RAG_CHROMA_PATH")
        )

        self.top_k = int(os.getenv("RAG_TOP_K", "6"))
        self.max_tokens = int(os.getenv("RAG_MAX_TOKENS", "1500"))
        self.temperature = float(os.getenv("RAG_TEMPERATURE", "0.3"))
        self.chat_model = os.getenv("RAG_CHAT_MODEL", "gpt-4o-mini")
        self.use_cache = _as_bool(os.getenv("RAG_USE_CACHE"), default=True)

        self.llm_client = get_llm_client()
        self.vector_store = VectorStore(
            collection_name=self.collection_name,
            persist_directory=self.persist_directory,
        )

        self.cache: Optional[RAGCache] = None
        if self.use_cache:
            self.cache = RAGCache(_cache_path_from_env())

    def ingest_if_needed(
        self,
        force: bool = False,
        *,
        force_reindex: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Backward compatibility: keyword-only ``force_reindex`` is an alias for ``force``
        when explicitly passed (non-None). Prefer ``force`` for new code.
        """
        effective_force = force if force_reindex is None else force_reindex
        before_count = self.vector_store.collection.count()
        indexed_now = False
        reindexed = False

        if effective_force and before_count > 0:
            self.vector_store.client.delete_collection(name=self.collection_name)
            self.vector_store.collection = self.vector_store.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            before_count = self.vector_store.collection.count()
            reindexed = True

        if before_count == 0:
            entries = default_corpus_entries()
            self.vector_store.load_corpus(
                corpus_entries=entries,
                base_dir=Path(__file__).resolve().parent,
            )
            indexed_now = True

        stats = self.vector_store.get_collection_stats()
        stats.update(
            {
                "indexed_now": indexed_now,
                "reindexed": reindexed,
                "force": effective_force,
                "cache_enabled": self.use_cache,
                "model": self.chat_model,
                "top_k": self.top_k,
            }
        )
        return stats

    def query(self, question: str) -> Dict[str, Any]:
        normalized_question = (question or "").strip()
        if not normalized_question:
            raise ValueError("Пустой вопрос. Передайте непустую строку question.")

        if self.cache is not None:
            cached = self.cache.get(normalized_question)
        else:
            cached = None

        if cached:
            return {
                "answer": cached.get("answer", ""),
                "context_docs": cached.get("context") or [],
                "from_cache": True,
                "model": self.chat_model,
                "cached_at": cached.get("created_at", ""),
            }

        self.ingest_if_needed(force=False)
        context_docs = self.vector_store.search(normalized_question, top_k=self.top_k)
        prompt = build_rag_prompt(normalized_question, context_docs)
        answer = generate_answer(
            llm_client=self.llm_client,
            model=self.chat_model,
            prompt=prompt,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        if self.cache is not None:
            self.cache.set(normalized_question, answer, context_docs)

        return {
            "answer": answer,
            "context_docs": context_docs,
            "from_cache": False,
            "model": self.chat_model,
            "cached_at": "",
        }
