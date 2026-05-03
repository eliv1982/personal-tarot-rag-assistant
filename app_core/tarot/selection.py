from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List
from uuid import UUID, uuid4

from app_core.tarot.deck import CARD_BY_SLUG, list_cards
from app_core.tarot.draw import DrawnCard, Orientation, StructuredSpreadDraw
from app_core.tarot.spreads import get_spread


@dataclass(frozen=True)
class VirtualDeckCard:
    deck_index: int
    card_slug: str
    orientation: Orientation


@dataclass(frozen=True)
class VirtualDeckDraft:
    draft_id: UUID
    spread_slug: str
    cards: List[VirtualDeckCard]
    required_count: int
    selected_indices: List[int]


def create_virtual_deck_draft(spread_slug: str) -> VirtualDeckDraft:
    spread = get_spread(spread_slug)
    rng = random.SystemRandom()
    shuffled_cards = list_cards()
    rng.shuffle(shuffled_cards)

    cards = [
        VirtualDeckCard(
            deck_index=index,
            card_slug=card.slug,
            orientation=rng.choice(["upright", "reversed"]),
        )
        for index, card in enumerate(shuffled_cards)
    ]

    return VirtualDeckDraft(
        draft_id=uuid4(),
        spread_slug=spread.slug,
        cards=cards,
        required_count=len(spread.positions),
        selected_indices=[],
    )


def select_virtual_cards(
    draft: VirtualDeckDraft,
    selected_indices: List[int],
) -> StructuredSpreadDraw:
    if len(selected_indices) != draft.required_count:
        raise ValueError(
            f"Draft requires {draft.required_count} selected cards, got {len(selected_indices)}."
        )
    if len(selected_indices) != len(set(selected_indices)):
        raise ValueError("selected_indices must be unique.")

    cards_by_index = {card.deck_index: card for card in draft.cards}
    invalid_indices = [index for index in selected_indices if index not in cards_by_index]
    if invalid_indices:
        raise ValueError(f"selected_indices out of range: {invalid_indices}")

    spread = get_spread(draft.spread_slug)
    drawn_cards: List[DrawnCard] = []
    for position, deck_index in zip(spread.positions, selected_indices):
        draft_card = cards_by_index[deck_index]
        tarot_card = CARD_BY_SLUG[draft_card.card_slug]
        drawn_cards.append(
            DrawnCard(
                position=position,
                card=tarot_card,
                orientation=draft_card.orientation,
            )
        )

    return StructuredSpreadDraw(spread=spread, drawn_cards=drawn_cards)


def create_draw_from_virtual_selection(
    draft: VirtualDeckDraft,
    selected_indices: List[int],
) -> StructuredSpreadDraw:
    return select_virtual_cards(draft, selected_indices)
