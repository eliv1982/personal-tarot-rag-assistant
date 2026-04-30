from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional, Protocol, Sequence
from uuid import UUID, uuid4

from app_core.readings.models import ReadingCard, ReadingMessage, ReadingSession
from app_core.readings.storage import cleanup_expired_readings, create_reading_session
from app_core.tarot.deck import CARD_BY_SLUG, TarotCard
from app_core.tarot.draw import StructuredSpreadDraw, draw_virtual_spread
from app_core.tarot.spreads import SpreadDefinition, SpreadPosition, get_spread
from rag_pipeline import RAGPipeline

Orientation = Literal["upright", "reversed"]
SelectionMode = Literal["virtual", "physical"]


class PipelineLike(Protocol):
    def query(self, question: str) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class SelectedPhysicalCard:
    position_index: int
    card_slug: str
    orientation: Orientation


@dataclass(frozen=True)
class StructuredReadingCard:
    position_index: int
    position_name_ru: str
    position_name_en: str
    position_prompt_hint_ru: str
    card_slug: str
    card_name_en: str
    card_name_ru: str
    orientation: Orientation
    knowledge_path: str


@dataclass(frozen=True)
class StructuredReadingResult:
    reading_id: Optional[UUID]
    spread: SpreadDefinition
    cards: list[StructuredReadingCard]
    answer: str
    context_docs: list[Any]
    model: str
    from_cache: bool
    debug: dict[str, Any]


def build_structured_reading_query(
    *,
    spread: SpreadDefinition,
    user_question: str,
    cards: Sequence[StructuredReadingCard],
) -> str:
    question = (user_question or "").strip()
    if not question:
        raise ValueError("user_question must be a non-empty string.")

    lines = [
        "Тема пользователя:",
        question,
        "",
        "Расклад:",
        f"{spread.title_ru} ({spread.title_en})",
        spread.description_ru,
        "",
        "Позиции и карты:",
    ]

    for card in cards:
        lines.extend(
            [
                (
                    f"{card.position_index + 1}. {card.position_name_ru} "
                    f"({card.position_name_en})"
                ),
                f"   Подсказка позиции: {card.position_prompt_hint_ru}",
                (
                    f"   Карта: {card.card_name_ru} ({card.card_name_en}), "
                    f"slug: {card.card_slug}, orientation: {card.orientation}"
                ),
                f"   Источник карты: {card.knowledge_path}",
            ]
        )

    lines.extend(
        [
            "",
            "Дай мягкую символическую интерпретацию этого расклада без фатализма.",
            "Не утверждай будущее как неизбежное; описывай вероятные динамики, выборы и точки внимания.",
            "Не делай фактических утверждений о событиях, людях или будущем без достаточных оснований.",
        ]
    )
    return "\n".join(lines)


def create_virtual_reading(
    spread_slug: str,
    user_question: str,
    *,
    persist: bool = True,
) -> StructuredReadingResult:
    spread = get_spread(spread_slug)
    draw = draw_virtual_spread(spread_slug)
    cards = _cards_from_draw(draw)
    return _create_reading(
        spread=spread,
        user_question=user_question,
        cards=cards,
        selection_mode="virtual",
        persist=persist,
    )


def create_physical_reading(
    spread_slug: str,
    user_question: str,
    selected_cards: list[SelectedPhysicalCard | dict[str, Any]],
    *,
    persist: bool = True,
) -> StructuredReadingResult:
    spread = get_spread(spread_slug)
    cards = _cards_from_physical_selection(spread, selected_cards)
    return _create_reading(
        spread=spread,
        user_question=user_question,
        cards=cards,
        selection_mode="physical",
        persist=persist,
    )


def _create_reading(
    *,
    spread: SpreadDefinition,
    user_question: str,
    cards: list[StructuredReadingCard],
    selection_mode: SelectionMode,
    pipeline: Optional[PipelineLike] = None,
    persist: bool = True,
) -> StructuredReadingResult:
    query = build_structured_reading_query(
        spread=spread,
        user_question=user_question,
        cards=cards,
    )
    rag = pipeline or RAGPipeline()
    rag_result = rag.query(query)
    answer = str(rag_result.get("answer", ""))
    context_docs = list(rag_result.get("context_docs") or [])
    model = str(rag_result.get("model", ""))
    from_cache = bool(rag_result.get("from_cache", False))

    reading_id = None
    if persist:
        reading_id = _store_reading(
            spread=spread,
            user_question=user_question,
            cards=cards,
            selection_mode=selection_mode,
            answer=answer,
        )

    return StructuredReadingResult(
        reading_id=reading_id,
        spread=spread,
        cards=cards,
        answer=answer,
        context_docs=context_docs,
        model=model,
        from_cache=from_cache,
        debug={
            "query": query,
            "selection_mode": selection_mode,
            "cached_at": rag_result.get("cached_at", ""),
            "storage_connected": reading_id is not None,
            # TODO: extend this service with follow-up message handling.
        },
    )


def _cards_from_draw(draw: StructuredSpreadDraw) -> list[StructuredReadingCard]:
    return [
        _structured_card_from_parts(
            position=drawn.position,
            card=drawn.card,
            orientation=drawn.orientation,
        )
        for drawn in draw.drawn_cards
    ]


def _cards_from_physical_selection(
    spread: SpreadDefinition,
    selected_cards: Sequence[SelectedPhysicalCard | dict[str, Any]],
) -> list[StructuredReadingCard]:
    if len(selected_cards) != len(spread.positions):
        raise ValueError(
            f"Spread {spread.slug!r} requires {len(spread.positions)} cards, "
            f"got {len(selected_cards)}."
        )

    positions_by_index = {p.index: p for p in spread.positions}
    seen_positions: set[int] = set()
    seen_cards: set[str] = set()
    out: list[StructuredReadingCard] = []

    for selected in selected_cards:
        item = _normalize_selected_card(selected)
        if item.position_index not in positions_by_index:
            known = sorted(positions_by_index)
            raise ValueError(f"Unknown position_index {item.position_index}. Known: {known}")
        if item.position_index in seen_positions:
            raise ValueError(f"Duplicate position_index {item.position_index}.")
        if item.card_slug in seen_cards:
            raise ValueError(f"Duplicate card_slug {item.card_slug!r}.")
        if item.orientation not in ("upright", "reversed"):
            raise ValueError("orientation must be 'upright' or 'reversed'.")

        card = CARD_BY_SLUG.get(item.card_slug)
        if card is None:
            known = ", ".join(sorted(CARD_BY_SLUG.keys())[:20])
            raise ValueError(f"Unknown card_slug {item.card_slug!r}. Known examples: {known}...")

        seen_positions.add(item.position_index)
        seen_cards.add(item.card_slug)
        out.append(
            _structured_card_from_parts(
                position=positions_by_index[item.position_index],
                card=card,
                orientation=item.orientation,
            )
        )

    return sorted(out, key=lambda c: c.position_index)


def _normalize_selected_card(
    selected: SelectedPhysicalCard | dict[str, Any],
) -> SelectedPhysicalCard:
    if isinstance(selected, SelectedPhysicalCard):
        return selected

    missing = [
        key
        for key in ("position_index", "card_slug", "orientation")
        if key not in selected or selected[key] in (None, "")
    ]
    if missing:
        raise ValueError(f"Selected card is missing required fields: {', '.join(missing)}")

    return SelectedPhysicalCard(
        position_index=int(selected["position_index"]),
        card_slug=str(selected["card_slug"]).strip(),
        orientation=_normalize_orientation(selected["orientation"]),
    )


def _normalize_orientation(value: Any) -> Orientation:
    normalized = str(value or "").strip()
    if normalized not in ("upright", "reversed"):
        raise ValueError("orientation must be 'upright' or 'reversed'.")
    return normalized  # type: ignore[return-value]


def _structured_card_from_parts(
    *,
    position: SpreadPosition,
    card: TarotCard,
    orientation: Orientation,
) -> StructuredReadingCard:
    return StructuredReadingCard(
        position_index=position.index,
        position_name_ru=position.name_ru,
        position_name_en=position.name_en,
        position_prompt_hint_ru=position.prompt_hint_ru,
        card_slug=card.slug,
        card_name_en=card.display_name_en,
        card_name_ru=card.display_name_ru,
        orientation=orientation,
        knowledge_path=card.knowledge_path,
    )


def _store_reading(
    *,
    spread: SpreadDefinition,
    user_question: str,
    cards: Sequence[StructuredReadingCard],
    selection_mode: SelectionMode,
    answer: str,
) -> UUID:
    session = ReadingSession(
        reading_id=uuid4(),
        spread_type=spread.slug,
        user_question=user_question,
        selection_mode=selection_mode,
        cards=[
            ReadingCard(
                position_index=card.position_index,
                position_name=card.position_name_ru,
                card_slug=card.card_slug,
                card_name=card.card_name_ru,
                orientation=card.orientation,
            )
            for card in cards
        ],
        initial_answer=answer,
        messages=[
            ReadingMessage(role="user", content=user_question),
            ReadingMessage(role="assistant", content=answer),
        ],
    )

    try:
        cleanup_expired_readings()
        return create_reading_session(session)
    except Exception as exc:
        raise RuntimeError(
            "Failed to persist tarot reading session. "
            "Check DATABASE_URL and PostgreSQL availability, or call with persist=False."
        ) from exc
