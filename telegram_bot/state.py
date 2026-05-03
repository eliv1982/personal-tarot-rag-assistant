from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Literal, Optional

from app_core.tarot.draw import StructuredSpreadDraw
from app_core.tarot.selection import VirtualDeckDraft

SelectionMode = Literal["virtual", "physical_deck", "quick_draw"]


@dataclass
class PhysicalCardEntry:
    position_index: int
    position_name_ru: str
    card_name: str
    card_slug: str
    orientation: str


@dataclass
class PendingFlow:
    selected_mode: Optional[SelectionMode] = None
    selected_spread_slug: Optional[str] = None
    user_question: Optional[str] = None
    question_received: bool = False
    awaiting_question: bool = False
    question_prompt_message_id: Optional[int] = None
    awaiting_virtual_selection: bool = False
    awaiting_physical_card_name: bool = False
    awaiting_physical_orientation: bool = False
    current_card_position_index: int = 0
    pending_physical_card_name: Optional[str] = None
    pending_physical_card_slug: Optional[str] = None
    physical_cards: list[PhysicalCardEntry] = field(default_factory=list)
    virtual_deck_draft: Optional[VirtualDeckDraft] = None
    selected_indices: list[int] = field(default_factory=list)
    last_drawn_cards: Optional[StructuredSpreadDraw] = None
    last_reading_id: Optional[str] = None


# MVP in-memory state. For server deployment, pending draft storage should move
# to PostgreSQL so restarts and multi-worker polling do not lose user progress.
_USER_STATE: Dict[int, PendingFlow] = {}


def get_flow(user_id: int) -> PendingFlow:
    return _USER_STATE.setdefault(user_id, PendingFlow())


def reset_flow(user_id: int, *, selected_mode: Optional[SelectionMode] = None) -> PendingFlow:
    flow = PendingFlow(selected_mode=selected_mode)
    _USER_STATE[user_id] = flow
    return flow
