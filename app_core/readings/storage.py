from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional
from uuid import UUID

from dotenv import load_dotenv

from app_core.readings.models import ReadingCard, ReadingMessage, ReadingSession


PROJECT_ROOT = Path(__file__).resolve().parents[3]

_env_path = PROJECT_ROOT / ".env"
if _env_path.exists():
    load_dotenv(_env_path)
else:
    load_dotenv()


# Minimal PostgreSQL schema (intentionally not applied automatically yet).
# Note: Extensions for UUID generation are not assumed; app can supply reading_id.
READINGS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS readings (
  reading_id UUID PRIMARY KEY,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '3 days',
  spread_type TEXT NOT NULL,
  user_question TEXT NOT NULL,
  selection_mode TEXT NOT NULL CHECK (selection_mode IN ('virtual', 'physical')),
  initial_answer TEXT NOT NULL DEFAULT ''
);
"""


READING_CARDS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS reading_cards (
  card_row_id BIGSERIAL PRIMARY KEY,
  reading_id UUID NOT NULL REFERENCES readings(reading_id) ON DELETE CASCADE,
  position_index INTEGER NOT NULL,
  position_name TEXT NOT NULL,
  card_slug TEXT NOT NULL,
  card_name TEXT NOT NULL,
  orientation TEXT NOT NULL CHECK (orientation IN ('upright', 'reversed')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(reading_id, position_index)
);
"""

READING_MESSAGES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS reading_messages (
  message_id BIGSERIAL PRIMARY KEY,
  reading_id UUID NOT NULL REFERENCES readings(reading_id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
  content TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


READING_INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS idx_readings_expires_at
  ON readings(expires_at);

CREATE INDEX IF NOT EXISTS idx_reading_cards_reading_id
  ON reading_cards(reading_id);

CREATE INDEX IF NOT EXISTS idx_reading_messages_reading_id_created_at
  ON reading_messages(reading_id, created_at);
"""


def get_database_url() -> str:
    db_url = (os.getenv("DATABASE_URL") or "").strip()
    if not db_url:
        raise ValueError("DATABASE_URL is not set in environment/.env")
    return db_url


def cleanup_expired_readings(now: Optional[datetime] = None) -> str:
    """
    Return SQL for expiring old readings.

    Integration (executing SQL) is intentionally deferred until next steps.
    """
    return "DELETE FROM readings WHERE expires_at < NOW();"


def build_reading_messages(messages: Iterable[ReadingMessage]) -> list[dict[str, Any]]:
    return [m.model_dump() for m in messages]


def build_reading_cards(cards: Iterable[ReadingCard]) -> list[dict[str, Any]]:
    return [c.model_dump() for c in cards]


def init_db() -> list[str]:
    """
    Return SQL statements needed to initialize schema.

    Execution is intentionally deferred until a later patch (after choosing a DB driver).
    """
    return [
        READINGS_TABLE_SQL,
        READING_CARDS_TABLE_SQL,
        READING_MESSAGES_TABLE_SQL,
        READING_INDEXES_SQL,
    ]


def create_reading_session(session: ReadingSession) -> None:
    raise NotImplementedError("PostgreSQL reading session storage is planned but not yet integrated.")


def get_reading_session(reading_id: UUID) -> Optional[ReadingSession]:
    raise NotImplementedError("PostgreSQL reading session retrieval is planned but not yet integrated.")


def add_reading_message(reading_id: UUID, message: ReadingMessage) -> None:
    raise NotImplementedError("PostgreSQL reading message storage is planned but not yet integrated.")

