from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Literal, Optional, Protocol, Sequence
from uuid import UUID, uuid4

from app_core.readings.models import ReadingCard, ReadingMessage, ReadingSession
from app_core.readings.storage import (
    add_reading_message,
    cleanup_expired_readings,
    create_reading_session,
    get_reading_session,
)
from app_core.tarot.deck import CARD_BY_SLUG, TarotCard
from app_core.tarot.draw import StructuredSpreadDraw, draw_virtual_spread
from app_core.tarot.spreads import SpreadDefinition, SpreadPosition, get_spread
from rag_pipeline import RAGPipeline

Orientation = Literal["upright", "reversed"]
SelectionMode = Literal["virtual", "physical"]

logger = logging.getLogger(__name__)


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


@dataclass(frozen=True)
class FollowUpReadingResult:
    reading_id: UUID
    answer: str
    context_docs: list[Any]
    model: str
    from_cache: bool
    messages_count: int
    debug: dict[str, Any]


def _presence(value: str | None) -> str:
    return "set" if (value or "").strip() else "missing"


def _safe_env_diagnostics() -> dict[str, str]:
    return {
        "DATABASE_URL": _presence(os.getenv("DATABASE_URL")),
        "OPENAI_API_KEY": _presence(os.getenv("OPENAI_API_KEY")),
        "OPENAI_BASE_URL": _presence(os.getenv("OPENAI_BASE_URL")),
        "OPENAI_MODEL": _presence(os.getenv("OPENAI_MODEL")),
        "RAG_USE_CACHE": _presence(os.getenv("RAG_USE_CACHE")),
        "RAG_CACHE_DB_PATH": _presence(os.getenv("RAG_CACHE_DB_PATH")),
        "LLM_API_KEY": _presence(os.getenv("LLM_API_KEY")),
        "LLM_BASE_URL": _presence(os.getenv("LLM_BASE_URL")),
        "RAG_CHAT_MODEL": _presence(os.getenv("RAG_CHAT_MODEL")),
    }


def build_structured_reading_query(
    *,
    spread: SpreadDefinition,
    user_question: str,
    cards: Sequence[StructuredReadingCard],
) -> str:
    question = (user_question or "").strip()
    if not question:
        raise ValueError("user_question must be a non-empty string.")
    output_schema = _tarot_output_schema(user_question=user_question, cards=cards)

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
            "Не повторяй одну и ту же мысль в разных разделах. Каждое предложение должно добавлять новый смысл.",
            "Если мысль уже названа в одном разделе, в следующем дай новый слой: контекст, нюанс, практический ориентир или вопрос к себе.",
            "Не делай длинное заключение, если оно повторяет уже сказанное.",
            "Не заканчивай ответ приглашением продолжить в стиле 'Если хотите, я могу...'.",
            "Не переписывай заново полный список карт, если он уже указан отдельно; ссылайся только на те карты и позиции, которые нужны для смысла.",
            "Используй plain text headings без markdown-маркеров.",
            "Если отвечаешь по-русски, не используй raw English orientation words вроде upright/reversed.",
            "",
            "Структура ответа:",
            output_schema,
        ]
    )
    return "\n".join(lines)


def _tarot_output_schema(
    *,
    user_question: str,
    cards: Sequence[StructuredReadingCard],
) -> str:
    is_ru = _has_cyrillic(user_question)
    card_count = len(cards)

    if is_ru:
        if card_count <= 1:
            return "\n".join(
                [
                    "Смысл карты:",
                    "2-4 предложения.",
                    "",
                    "Связь с вопросом:",
                    "2-4 предложения.",
                    "",
                    "На что обратить внимание:",
                    "- 2-4 коротких пункта.",
                    "",
                    "Вопрос к себе:",
                    "1 вопрос.",
                ]
            )
        if card_count <= 3:
            return "\n".join(
                [
                    "Общий рисунок:",
                    "3-5 предложений.",
                    "",
                    "По позициям:",
                    "1. <позиция> — <карта>",
                    "2-3 предложения.",
                    "2. ...",
                    "3. ...",
                    "",
                    "На что обратить внимание:",
                    "- 2-4 коротких пункта.",
                    "",
                    "Вопрос к себе:",
                    "1 вопрос.",
                ]
            )
        return "\n".join(
            [
                "Общий рисунок:",
                "4-6 предложений.",
                "",
                "Ключевые акценты:",
                "- 3-5 пунктов, каждый связан с конкретной картой или позицией.",
                "",
                "Следующий бережный шаг:",
                "2-4 предложения.",
                "",
                "Вопрос к себе:",
                "1 вопрос.",
            ]
        )

    if card_count <= 1:
        return "\n".join(
            [
                "Card meaning:",
                "2-4 sentences.",
                "",
                "Connection to the question:",
                "2-4 sentences.",
                "",
                "What to notice:",
                "- 2-4 short bullet points.",
                "",
                "Question for yourself:",
                "1 question.",
            ]
        )
    if card_count <= 3:
        return "\n".join(
            [
                "Overall pattern:",
                "3-5 sentences.",
                "",
                "By position:",
                "1. <position> — <card>",
                "2-3 sentences.",
                "2. ...",
                "3. ...",
                "",
                "What to notice:",
                "- 2-4 short bullet points.",
                "",
                "Question for yourself:",
                "1 question.",
            ]
        )
    return "\n".join(
        [
            "Overall pattern:",
            "4-6 sentences.",
            "",
            "Key accents:",
            "- 3-5 bullet points, each tied to a specific card or position.",
            "",
            "Gentle next step:",
            "2-4 sentences.",
            "",
            "Question for yourself:",
            "1 question.",
        ]
    )


def _has_cyrillic(text: str) -> bool:
    return bool(re.search(r"[А-Яа-яЁё]", text or ""))


def build_follow_up_query(
    *,
    session: ReadingSession,
    follow_up_question: str,
) -> str:
    question = (follow_up_question or "").strip()
    if not question:
        raise ValueError("follow_up_question must be a non-empty string.")

    lines = [
        "Это уточняющий вопрос к уже существующему tarot reading.",
        "Не делай новый расклад, не вытягивай новые карты и не меняй исходный расклад.",
        "Отвечай только как уточнение к сохранённым картам и исходной интерпретации.",
        "Не делай фактических утверждений о событиях, людях или будущем без достаточных оснований.",
        "Сохраняй agency пользователя: описывай выборы, возможные динамики и точки внимания.",
        "",
        "Исходный вопрос пользователя:",
        session.user_question,
        "",
        "Тип расклада:",
        session.spread_type,
        "",
        "Сохранённые карты:",
    ]

    for card in session.cards:
        lines.append(
            (
                f"{card.position_index + 1}. {card.position_name}: "
                f"{card.card_name}, slug: {card.card_slug}, orientation: {card.orientation}"
            )
        )

    lines.extend(
        [
            "",
            "Исходная интерпретация:",
            session.initial_answer,
            "",
            "Предыдущие сообщения:",
        ]
    )

    if session.messages:
        for message in session.messages:
            lines.append(f"{message.role}: {message.content}")
    else:
        lines.append("(нет предыдущих сообщений)")

    lines.extend(
        [
            "",
            "Новый уточняющий вопрос:",
            question,
        ]
    )
    return "\n".join(lines)


def create_virtual_reading(
    spread_slug: str,
    user_question: str,
    *,
    persist: bool = True,
) -> StructuredReadingResult:
    draw = draw_virtual_spread(spread_slug)
    return create_reading_from_drawn_cards(
        draw=draw,
        user_question=user_question,
        persist=persist,
    )


def create_reading_from_drawn_cards(
    *,
    draw: StructuredSpreadDraw,
    user_question: str,
    persist: bool = True,
) -> StructuredReadingResult:
    cards = _cards_from_draw(draw)
    return _create_reading(
        spread=draw.spread,
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


def answer_follow_up(
    reading_id: str | UUID,
    follow_up_question: str,
) -> FollowUpReadingResult:
    question = (follow_up_question or "").strip()
    if not question:
        raise ValueError("follow_up_question must be a non-empty string.")

    session = get_reading_session(reading_id)
    if session is None:
        raise ValueError(f"Reading session not found: {reading_id}")

    add_reading_message(session.reading_id, "user", question)
    query = build_follow_up_query(session=session, follow_up_question=question)

    rag_result = RAGPipeline().query(query)
    answer = str(rag_result.get("answer", ""))
    add_reading_message(session.reading_id, "assistant", answer)

    updated_session = get_reading_session(session.reading_id)
    messages_count = len(updated_session.messages) if updated_session is not None else 0

    return FollowUpReadingResult(
        reading_id=session.reading_id,
        answer=answer,
        context_docs=list(rag_result.get("context_docs") or []),
        model=str(rag_result.get("model", "")),
        from_cache=bool(rag_result.get("from_cache", False)),
        messages_count=messages_count,
        debug={
            "query": query,
            "cached_at": rag_result.get("cached_at", ""),
            "cards_count": len(session.cards),
        },
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
    try:
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
            },
        )
    except Exception:
        logger.exception(
            "Tarot reading generation failed selection_mode=%s spread_slug=%s persist=%s env=%s",
            selection_mode,
            spread.slug,
            persist,
            _safe_env_diagnostics(),
        )
        raise


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
