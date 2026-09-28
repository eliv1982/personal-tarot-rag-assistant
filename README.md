# Personal Tarot RAG Assistant

A local, personal Retrieval-Augmented Generation (RAG) assistant over a
hand-curated Tarot knowledge base. You ask a question, the app retrieves the
most relevant Tarot knowledge (card meanings, spread references, style and
safety guidance) from a local vector store, and a hosted LLM writes a
grounded, reflection-oriented answer.

This is a personal/portfolio project, not a production service.

## What this is (and isn't)

- **Is:** a free-form Q&A assistant grounded in a curated Tarot knowledge
  base. You type a question, the RAG pipeline retrieves relevant chunks from
  Chroma and asks the LLM to answer using only that retrieved context.
- **Isn't (in the primary web UI):** a deterministic card-draw or spread
  engine. The web interface does not shuffle a deck or lay out a structured
  spread for you — it answers questions about Tarot using retrieval +
  generation.
- **Secondary interface:** the repository also contains an optional Telegram
  bot (`telegram_bot/`) that *does* implement a deterministic virtual/physical
  card draw, spread selection, and structured multi-card readings (backed by
  the same RAG pipeline for interpretation text, optionally persisted to
  PostgreSQL). It is more experimental than the web UI and needs extra setup
  (a bot token and, if you want persistence, a Postgres database). It is not
  required to use the core Q&A assistant.

## Architecture

```
knowledge_base/tarot/          curated Markdown source of truth (cards, spreads, style, safety)
        │
        ▼
app_core/config/knowledge.py   discovers and labels knowledge_base files
        │
        ▼
app_core/retrieval/vector_store.py   chunking, embeddings, Chroma index + search
        │
        ▼
app_core/generation/prompts.py       builds the grounded prompt (+ Tarot guardrails)
        │
        ▼
app_core/generation/answer_generator.py   calls the hosted chat model
        │
        ▼
app_core/cache/storage.py      SQLite cache of question → answer (+ context)
        │
        ▼
rag_pipeline.py                 orchestrates the steps above
        │
        ▼
web/app.py + web/routes.py      FastAPI web UI (primary entrypoint)
```

`app_core/tarot/` (deck, spreads, draw, selection, reading_service) and
`app_core/readings/` (PostgreSQL-backed reading sessions) implement the
deterministic draw/spread engine used by the optional Telegram bot
(`telegram_bot/`); the web UI does not use them.

## Requirements

- Python 3.12 (developed and tested against 3.12.10; other 3.12.x should
  work, earlier/later versions are untested).
- A hosted OpenAI-compatible API key for chat completions and embeddings.

## Setup

```bash
git clone <this-repo>
cd personal-tarot-rag-assistant

python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# then edit .env and set at least LLM_API_KEY
```

### `.env` configuration

Copy `.env.example` to `.env` and fill in the values you need. At minimum:

- `LLM_API_KEY` — your hosted OpenAI-compatible API key.
- `RAG_CHAT_MODEL` / `RAG_EMBEDDING_MODEL` — which hosted models to use.

Every variable in `.env.example` is read by the code as shipped; nothing
in that file is aspirational. `RAG_MAX_DISTANCE` is a cosine-distance
retrieval threshold — see "Current limitations" below for a caveat on its
default value.

The Telegram bot and PostgreSQL-backed reading persistence
(`TELEGRAM_BOT_TOKEN`, `DATABASE_URL`, `TELEGRAM_PERSIST_READINGS`) are only
needed if you run `telegram_bot/bot.py`; the web UI does not need them.

### Run the web app

```bash
uvicorn web.app:app --reload --port 8010
```

Then open `http://127.0.0.1:8010/`. The first question triggers ingestion
(chunking + embedding the knowledge base into a local Chroma collection)
if the collection is empty; subsequent runs reuse the persisted index in
`runtime/chroma_db/`.

You can also run ingestion explicitly:

```bash
python scripts/tarot/run_ingest.py
# or, to rebuild the index from scratch:
python scripts/tarot/run_ingest.py --force-reindex
```

### Run the tests

```bash
pytest
```

Tests are fully offline: no API key, no network access, and no writes to
`runtime/` are required.

## Storage and privacy boundaries

- **Chroma** (`runtime/chroma_db/`, gitignored) stores the embedded Tarot
  knowledge base locally on disk.
- **SQLite** (`runtime/rag_cache.db`, gitignored) caches question → answer
  pairs locally, keyed by a normalized question plus `RAG_CORPUS_VERSION`.
- **PostgreSQL** (optional, only used by the Telegram bot's structured
  reading sessions) stores drawn cards and reading history if you configure
  `DATABASE_URL` and enable persistence.
- **Hosted LLM/embedding API**: your question text and retrieved knowledge
  base context are sent to whichever OpenAI-compatible endpoint you
  configure (`LLM_BASE_URL`, or the default OpenAI API). No other outbound
  network calls are made by the core pipeline.
- Nothing in `knowledge_base/` or your own `.env` is sent anywhere except as
  part of that LLM call.

## Current limitations

- The web UI does not perform deterministic card draws or generate
  structured spreads — it is a grounded Q&A assistant, not a reading
  generator, unless you use the Telegram bot's structured-reading flow.
- `RAG_MAX_DISTANCE` (cosine-distance retrieval threshold) ships with a
  reasonable default but has not been formally calibrated against a labeled
  offline evaluation set; treat it as a starting point that may need
  live tuning against real queries.
- This is a single-process, local, single-user design. It has no
  authentication, no multi-user isolation, and is not intended for shared or
  production deployment.
- There is no automated retrieval-quality evaluation harness; retrieval
  quality depends on the chosen embedding model and the curated knowledge
  base.
- The Telegram bot and PostgreSQL-backed reading persistence are more
  experimental than the web UI and are optional.

## Safety and interpretive framing

Tarot interpretation, as implemented here, is treated strictly as a symbolic
and reflective framework — not as objective prediction, and not as a
substitute for medical, legal, financial, or mental-health advice. The
generation prompts (see `app_core/generation/prompts.py`) explicitly instruct
the model to:

- avoid stating illness, death, legal outcomes, or similarly high-impact
  claims as fact;
- avoid claiming certainty about another person's private thoughts or
  actions;
- stay within the retrieved context and mark uncertainty when the context is
  incomplete;
- preserve the user's agency rather than presenting fatalistic conclusions.

## Possible future directions

These are ideas, not commitments, and are **not** implemented today:
deterministic draw/spread engine parity for the web UI, a local reading
journal/history view, card-aware retrieval balancing for multi-card
questions, a retrieval-quality evaluation harness, spread-position
explainability, broader i18n, and optional multi-user profiles if a real
need for them appears.
