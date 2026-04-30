from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional
from uuid import UUID, uuid4

from dotenv import load_dotenv

from app_core.readings.models import (
    ReadingCard,
    ReadingMessage,
    ReadingSession,
    SelectionMode,
    utc_now,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

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
    if not (db_url.startswith("postgresql://") or db_url.startswith("postgres://")):
        raise ValueError("DATABASE_URL must start with postgresql:// or postgres://")
    return db_url


def _connect() -> Any:
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "psycopg 3 is required for PostgreSQL reading storage. "
            "Install project dependencies from requirements.txt."
        ) from exc

    return psycopg.connect(get_database_url(), row_factory=dict_row)


def _as_uuid(value: UUID | str) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


def _execute_sql_script(cursor: Any, sql: str) -> None:
    for statement in sql.split(";"):
        statement = statement.strip()
        if statement:
            cursor.execute(statement)


def cleanup_expired_readings() -> int:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM readings WHERE expires_at < NOW()")
            return int(cur.rowcount or 0)


def build_reading_messages(messages: Iterable[ReadingMessage]) -> list[dict[str, Any]]:
    return [m.model_dump() for m in messages]


def build_reading_cards(cards: Iterable[ReadingCard]) -> list[dict[str, Any]]:
    return [c.model_dump() for c in cards]


def init_db() -> None:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(READINGS_TABLE_SQL)
            cur.execute(READING_CARDS_TABLE_SQL)
            cur.execute(READING_MESSAGES_TABLE_SQL)
            _execute_sql_script(cur, READING_INDEXES_SQL)


def create_reading_session(
    session: Optional[ReadingSession] = None,
    *,
    spread_type: Optional[str] = None,
    user_question: Optional[str] = None,
    selection_mode: Optional[SelectionMode] = None,
    cards: Optional[Iterable[ReadingCard | Mapping[str, Any]]] = None,
    initial_answer: str = "",
) -> UUID:
    if session is None:
        if not spread_type:
            raise ValueError("spread_type is required")
        if not user_question:
            raise ValueError("user_question is required")
        if selection_mode not in ("virtual", "physical"):
            raise ValueError("selection_mode must be 'virtual' or 'physical'")

        now = utc_now()
        session = ReadingSession(
            reading_id=uuid4(),
            created_at=now,
            updated_at=now,
            expires_at=now + timedelta(days=3),
            spread_type=spread_type,
            user_question=user_question,
            selection_mode=selection_mode,
            cards=[_coerce_reading_card(card) for card in (cards or [])],
            initial_answer=initial_answer,
            messages=[],
        )

    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO readings (
                  reading_id,
                  created_at,
                  updated_at,
                  expires_at,
                  spread_type,
                  user_question,
                  selection_mode,
                  initial_answer
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    session.reading_id,
                    session.created_at,
                    session.updated_at,
                    session.expires_at,
                    session.spread_type,
                    session.user_question,
                    session.selection_mode,
                    session.initial_answer,
                ),
            )

            for card in session.cards:
                cur.execute(
                    """
                    INSERT INTO reading_cards (
                      reading_id,
                      position_index,
                      position_name,
                      card_slug,
                      card_name,
                      orientation
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        session.reading_id,
                        card.position_index,
                        card.position_name,
                        card.card_slug,
                        card.card_name,
                        card.orientation,
                    ),
                )

            for message in session.messages:
                cur.execute(
                    """
                    INSERT INTO reading_messages (reading_id, role, content, created_at)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        session.reading_id,
                        message.role,
                        message.content,
                        message.created_at,
                    ),
                )

    return session.reading_id


def get_reading_session(reading_id: UUID | str) -> Optional[ReadingSession]:
    rid = _as_uuid(reading_id)

    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  reading_id,
                  created_at,
                  updated_at,
                  expires_at,
                  spread_type,
                  user_question,
                  selection_mode,
                  initial_answer
                FROM readings
                WHERE reading_id = %s
                """,
                (rid,),
            )
            reading = cur.fetchone()
            if reading is None:
                return None

            cur.execute(
                """
                SELECT position_index, position_name, card_slug, card_name, orientation
                FROM reading_cards
                WHERE reading_id = %s
                ORDER BY position_index
                """,
                (rid,),
            )
            cards = [_coerce_reading_card(row) for row in cur.fetchall()]

            cur.execute(
                """
                SELECT role, content, created_at
                FROM reading_messages
                WHERE reading_id = %s
                ORDER BY created_at
                """,
                (rid,),
            )
            messages = [ReadingMessage(**row) for row in cur.fetchall()]

    return ReadingSession(
        reading_id=reading["reading_id"],
        created_at=reading["created_at"],
        updated_at=reading["updated_at"],
        expires_at=reading["expires_at"],
        spread_type=reading["spread_type"],
        user_question=reading["user_question"],
        selection_mode=reading["selection_mode"],
        cards=cards,
        initial_answer=reading["initial_answer"],
        messages=messages,
    )


def add_reading_message(
    reading_id: UUID | str,
    role: ReadingMessage | str,
    content: Optional[str] = None,
) -> ReadingMessage:
    rid = _as_uuid(reading_id)
    if isinstance(role, ReadingMessage):
        message = role
    else:
        if role not in ("user", "assistant"):
            raise ValueError("role must be 'user' or 'assistant'")
        if content is None or not str(content).strip():
            raise ValueError("content must be a non-empty string")
        message = ReadingMessage(role=role, content=str(content))

    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM readings WHERE reading_id = %s",
                (rid,),
            )
            if cur.fetchone() is None:
                raise ValueError(f"Reading session not found: {rid}")

            cur.execute(
                """
                INSERT INTO reading_messages (reading_id, role, content, created_at)
                VALUES (%s, %s, %s, %s)
                RETURNING role, content, created_at
                """,
                (rid, message.role, message.content, message.created_at),
            )
            inserted = cur.fetchone()
            cur.execute(
                "UPDATE readings SET updated_at = NOW() WHERE reading_id = %s",
                (rid,),
            )

    return ReadingMessage(**inserted)


def _coerce_reading_card(card: ReadingCard | Mapping[str, Any]) -> ReadingCard:
    if isinstance(card, ReadingCard):
        return card
    return ReadingCard(**dict(card))

