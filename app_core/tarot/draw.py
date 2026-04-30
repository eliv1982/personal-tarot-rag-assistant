from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Literal, Optional

from app_core.tarot.deck import TarotCard
from app_core.tarot.spreads import SpreadDefinition, SpreadPosition

Orientation = Literal["upright", "reversed"]


@dataclass(frozen=True)
class DrawnCard:
    position: SpreadPosition
    card: TarotCard
    orientation: Orientation


@dataclass(frozen=True)
class StructuredSpreadDraw:
    spread: SpreadDefinition
    drawn_cards: List[DrawnCard]


def draw_virtual_spread(spread_slug: str) -> StructuredSpreadDraw:
    """
    Virtual draw:
    - random cards without repeats
    - number of cards = number of positions in the spread
    - each card gets random orientation: upright or reversed
    """
    from app_core.tarot.spreads import get_spread
    from app_core.tarot.deck import list_cards

    spread = get_spread(spread_slug)
    deck_cards = list_cards()
    k = len(spread.positions)

    if k > len(deck_cards):
        raise ValueError(f"Spread needs {k} cards, but deck has only {len(deck_cards)} cards.")

    rng = random.SystemRandom()
    picked_cards = rng.sample(deck_cards, k=k)

    drawn: List[DrawnCard] = []
    for pos, card in zip(spread.positions, picked_cards):
        orientation: Orientation = rng.choice(["upright", "reversed"])
        drawn.append(DrawnCard(position=pos, card=card, orientation=orientation))

    return StructuredSpreadDraw(spread=spread, drawn_cards=drawn)

