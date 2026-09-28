# app_core

Shared, domain-agnostic RAG core used by both entrypoints in this repo.

## Layout

- `llm/client.py` - hosted LLM client.
- `config/knowledge.py` - discovers and labels `knowledge_base` files.
- `cache/storage.py` - SQLite question/answer cache.
- `retrieval/vector_store.py` - chunking, embeddings, Chroma index + search.
- `generation/prompts.py`, `generation/answer_generator.py` - grounded prompt
  construction and hosted-model answer generation.
- `readings/` - PostgreSQL-backed structured reading session storage
  (`storage.py`, `models.py`), used by the Telegram bot.
- `tarot/` - deterministic deck/spread/draw engine and reading orchestration
  (`reading_service.py`), used by the Telegram bot.
- `ingestion/`, `schemas/`, `evaluation/` - reserved for future use; currently
  empty placeholders with no implementation.

## Entrypoints

There is no root-level `app.py`. The two entrypoints are:

- `rag_pipeline.py` (repo root) - orchestrates retrieval + generation + cache
  for the core Q&A flow.
- `web/app.py` + `web/routes.py` - FastAPI Q&A UI, the primary entrypoint.
- `telegram_bot/` - experimental structured Tarot reading flow (deterministic
  card draw, spreads, optional PostgreSQL persistence), built on top of this
  core.
