from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Literal, Optional

from app_core.tarot.selection import VirtualDeckDraft

SelectionMode = Literal["virtual", "physical", "quick"]


@dataclass
class PendingFlow:
    selected_mode: Optional[SelectionMode] = None
    selected_spread_slug: Optional[str] = None
    virtual_deck_draft: Optional[VirtualDeckDraft] = None
    selected_indices: list[int] = field(default_factory=list)
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
