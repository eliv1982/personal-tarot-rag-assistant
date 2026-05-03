from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app_core.tarot.spreads import SpreadDefinition, get_spread, list_spreads

MVP_SPREAD_SLUGS = (
    "one_card",
    "three_card_past_present_future",
    "three_card_situation_obstacle_outcome",
    "three_card_relationships",
    "three_card_choice",
    "five_card_deep_reading",
)

SPREAD_CALLBACK_BY_SLUG = {
    slug: f"s{index}" for index, slug in enumerate(MVP_SPREAD_SLUGS)
}
SPREAD_SLUG_BY_CALLBACK = {
    callback_id: slug for slug, callback_id in SPREAD_CALLBACK_BY_SLUG.items()
}

TELEGRAM_SPREAD_LABELS = {
    "one_card": "🎯 Одна карта — фокус момента",
    "three_card_past_present_future": "🕰 Три карты — прошлое / сейчас / возможный вектор",
    "three_card_situation_obstacle_outcome": "🧭 Три карты — ситуация / препятствие / ориентир",
    "three_card_relationships": "🤝 Три карты — я / другой / динамика",
    "three_card_choice": "⚖️ Три карты — вариант A / вариант B / что учесть",
    "five_card_deep_reading": "🔎 Пять карт — глубокий разбор",
}

MODE_LABELS = {
    "virtual": "🌙 Виртуальная колода",
    "physical_deck": "🕯 Физическая колода",
    "quick_draw": "✨ Автовыбор карт",
}


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🌙 Виртуальная колода",
                    callback_data="m:v",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🕯 Физическая колода",
                    callback_data="m:p",
                )
            ],
            [
                InlineKeyboardButton(
                    text="✨ Автовыбор карт",
                    callback_data="m:q",
                )
            ],
        ]
    )


def menu_button_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏠 В меню", callback_data="menu")],
        ]
    )


def reading_result_keyboard(*, has_follow_up: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if has_follow_up:
        rows.append([InlineKeyboardButton(text="💬 Уточнить по раскладу", callback_data="reading_follow_up")])
    rows.append([InlineKeyboardButton(text="🏠 В меню", callback_data="menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def physical_orientation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="☀️ Прямое положение",
                    callback_data="phys_orient:upright",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🌙 Перевёрнутое положение",
                    callback_data="phys_orient:reversed",
                )
            ],
            [InlineKeyboardButton(text="🏠 В меню", callback_data="menu")],
        ]
    )


def spread_selection_keyboard(mode_callback_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for spread in _mvp_spreads():
        spread_id = SPREAD_CALLBACK_BY_SLUG[spread.slug]
        builder.button(
            text=TELEGRAM_SPREAD_LABELS.get(spread.slug, spread.title_ru),
            callback_data=f"sp:{mode_callback_id}:{spread_id}",
        )
    builder.adjust(1)
    return builder.as_markup()


def virtual_deck_keyboard(
    selected_indices: list[int],
    *,
    card_count: int,
    ready_to_open: bool,
) -> InlineKeyboardMarkup:
    selected = set(selected_indices)
    builder = InlineKeyboardBuilder()

    for deck_index in range(card_count):
        builder.button(
            text="✨" if deck_index in selected else "🌙",
            callback_data=f"c:{deck_index}",
        )

    builder.adjust(6)
    if ready_to_open:
        builder.row(InlineKeyboardButton(text="✨ Открыть карты", callback_data="open"))
    return builder.as_markup()


def get_spread_by_callback_id(callback_id: str) -> SpreadDefinition | None:
    spread_slug = SPREAD_SLUG_BY_CALLBACK.get(callback_id)
    if spread_slug is None:
        return None
    try:
        return get_spread(spread_slug)
    except ValueError:
        return None


def get_mode_display_label(mode: str) -> str:
    return MODE_LABELS.get(mode, mode)


def get_spread_display_label(spread_slug: str) -> str:
    spread = get_spread(spread_slug)
    return TELEGRAM_SPREAD_LABELS.get(spread.slug, spread.title_ru)


def _mvp_spreads() -> list[SpreadDefinition]:
    spreads_by_slug = {spread.slug: spread for spread in list_spreads()}
    return [spreads_by_slug[slug] for slug in MVP_SPREAD_SLUGS if slug in spreads_by_slug]
