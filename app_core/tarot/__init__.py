from __future__ import annotations

from typing import List

from app_core.tarot.deck import ALL_TAROT_CARDS, CARD_BY_SLUG, TarotCard
from app_core.tarot.spreads import SPREAD_BY_SLUG, SPREADS, SpreadDefinition


def list_cards() -> List[TarotCard]:
    return list(ALL_TAROT_CARDS)


def get_card_by_slug(slug: str) -> TarotCard:
    key = (slug or "").strip()
    if key in CARD_BY_SLUG:
        return CARD_BY_SLUG[key]
    known = ", ".join(sorted(CARD_BY_SLUG.keys())[:20])
    raise ValueError(f"Unknown card slug: {slug!r}. Known examples: {known}...")


def list_spreads() -> List[SpreadDefinition]:
    return list(SPREADS)


def get_spread(spread_slug: str) -> SpreadDefinition:
    key = (spread_slug or "").strip()
    if key in SPREAD_BY_SLUG:
        return SPREAD_BY_SLUG[key]
    known = ", ".join(sorted(SPREAD_BY_SLUG.keys()))
    raise ValueError(f"Unknown spread slug: {spread_slug!r}. Known: {known}")


__all__ = [
    "TarotCard",
    "SpreadDefinition",
    "list_cards",
    "get_card_by_slug",
    "list_spreads",
    "get_spread",
]

