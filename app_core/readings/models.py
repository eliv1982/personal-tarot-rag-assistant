from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


SelectionMode = Literal["virtual", "physical"]
Orientation = Literal["upright", "reversed"]


def utc_now() -> datetime:
    """Timezone-aware UTC 'now' for all timestamp defaults."""
    return datetime.now(timezone.utc)


class ReadingCard(BaseModel):
    """
    One selected tarot card inside a reading.

    Orientation is always required.
    """

    position_index: int
    position_name: str

    card_slug: str
    card_name: str

    orientation: Orientation


class ReadingMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime = Field(default_factory=utc_now)


class ReadingSession(BaseModel):
    reading_id: UUID

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime = Field(
        default_factory=lambda: utc_now() + timedelta(days=3)
    )

    spread_type: str
    user_question: str
    selection_mode: SelectionMode

    cards: list[ReadingCard] = []

    initial_answer: str = ""
    messages: list[ReadingMessage] = []

