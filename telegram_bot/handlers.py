from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from app_core.tarot.draw import StructuredSpreadDraw, draw_virtual_spread
from app_core.tarot.selection import create_virtual_deck_draft, select_virtual_cards
from app_core.tarot.spreads import get_spread
from telegram_bot.keyboards import (
    get_spread_by_callback_id,
    main_menu_keyboard,
    menu_button_keyboard,
    spread_selection_keyboard,
    virtual_deck_keyboard,
)
from telegram_bot.state import get_flow, reset_flow

router = Router()
logger = logging.getLogger(__name__)

START_TEXT = (
    "🌙 Arcana Whisper ✨\n\n"
    "Твой мягкий помощник в понимании себя через символы таро.\n\n"
    "Здесь таро — не про жёсткие предсказания, а про бережное размышление, "
    "внутренний отклик и более ясный взгляд на ситуацию.\n\n"
    "Выбери формат, который тебе ближе:"
)

PHYSICAL_DECK_TEXT = (
    "Перед раскладом дай себе минуту тишины. Сделай несколько спокойных вдохов "
    "и выдохов. Сформулируй тему так, чтобы она была про тебя, твой выбор и "
    "твоё состояние. Перемешай колоду привычным способом, вытяни карты по "
    "позициям расклада и внеси их ниже.\n\n"
    "Ручной ввод карт подключим следующим шагом."
)

INTERPRETATION_PLACEHOLDER = "Интерпретацию подключим следующим шагом."


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    user_id = message.from_user.id
    reset_flow(user_id)
    logger.info("/start user_id=%s", user_id)
    await message.answer(
        START_TEXT,
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )


@router.message(Command("menu"))
async def handle_menu_command(message: Message) -> None:
    user_id = message.from_user.id
    reset_flow(user_id)
    logger.info("/menu user_id=%s", user_id)
    await message.answer(
        START_TEXT,
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )


@router.message(Command("cancel"))
async def handle_cancel_command(message: Message) -> None:
    user_id = message.from_user.id
    reset_flow(user_id)
    logger.info("/cancel user_id=%s", user_id)
    await message.answer(
        "Текущий выбор отменён. Можно начать заново.",
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(F.data == "menu")
async def handle_menu_callback(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    reset_flow(user_id)
    logger.info("menu callback user_id=%s", user_id)
    message = await _editable_message_or_answer(callback)
    if message is None:
        return
    await message.edit_text(
        START_TEXT,
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "m:v")
async def handle_virtual_mode(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    reset_flow(user_id, selected_mode="virtual")
    logger.info("selected mode user_id=%s mode=virtual", user_id)
    message = await _editable_message_or_answer(callback)
    if message is None:
        return
    await message.edit_text(
        "Выбери расклад для виртуальной колоды:",
        reply_markup=spread_selection_keyboard("v"),
    )
    await callback.answer()


@router.callback_query(F.data == "m:q")
async def handle_quick_mode(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    reset_flow(user_id, selected_mode="quick")
    logger.info("selected mode user_id=%s mode=quick", user_id)
    message = await _editable_message_or_answer(callback)
    if message is None:
        return
    await message.edit_text(
        "Выбери расклад для быстрого вытягивания:",
        reply_markup=spread_selection_keyboard("q"),
    )
    await callback.answer()


@router.callback_query(F.data == "m:p")
async def handle_physical_mode(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    reset_flow(user_id, selected_mode="physical")
    logger.info("selected mode user_id=%s mode=physical", user_id)
    message = await _editable_message_or_answer(callback)
    if message is None:
        return
    await message.edit_text(PHYSICAL_DECK_TEXT, reply_markup=menu_button_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("sp:"))
async def handle_spread_selection(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    parts = (callback.data or "").split(":")
    if len(parts) != 3:
        logger.warning("unknown spread callback user_id=%s callback_data=%r", user_id, callback.data)
        await callback.answer("Не удалось распознать расклад.", show_alert=True)
        return

    _, mode_callback_id, spread_callback_id = parts
    spread = get_spread_by_callback_id(spread_callback_id)
    if spread is None:
        logger.warning(
            "unknown spread user_id=%s mode=%s spread_callback_id=%s",
            user_id,
            mode_callback_id,
            spread_callback_id,
        )
        message = await _editable_message_or_answer(
            callback,
            text="Не смогла найти этот расклад. Вернись в меню и выбери расклад заново.",
        )
        if message is not None:
            await message.edit_text(
                "Не смогла найти этот расклад. Вернись в меню и выбери расклад заново.",
                reply_markup=main_menu_keyboard(),
            )
            await callback.answer()
        return

    message = await _editable_message_or_answer(callback)
    if message is None:
        return

    flow = get_flow(user_id)
    flow.selected_spread_slug = spread.slug
    logger.info(
        "selected spread user_id=%s spread_slug=%s mode=%s",
        user_id,
        spread.slug,
        mode_callback_id,
    )

    if mode_callback_id == "v":
        flow.selected_mode = "virtual"
        flow.virtual_deck_draft = create_virtual_deck_draft(spread.slug)
        flow.selected_indices = []
        await message.edit_text(
            _virtual_selection_text(spread.slug, 0),
            reply_markup=virtual_deck_keyboard(
                [],
                card_count=len(flow.virtual_deck_draft.cards),
                ready_to_open=False,
            ),
        )
    elif mode_callback_id == "q":
        flow.selected_mode = "quick"
        draw = draw_virtual_spread(spread.slug)
        logger.info("quick draw user_id=%s spread_slug=%s", user_id, spread.slug)
        await message.edit_text(_draw_result_text(draw), reply_markup=menu_button_keyboard())
    else:
        await callback.answer("Этот режим пока недоступен.", show_alert=True)
        return

    await callback.answer()


@router.callback_query(F.data.startswith("c:"))
async def handle_card_selection(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    flow = get_flow(user_id)
    draft = flow.virtual_deck_draft
    if flow.selected_mode != "virtual" or draft is None:
        await callback.answer("Начни выбор заново через /start.", show_alert=True)
        return
    message = await _editable_message_or_answer(callback)
    if message is None:
        return

    try:
        deck_index = int((callback.data or "").split(":", maxsplit=1)[1])
    except (IndexError, ValueError):
        logger.warning("unknown card callback user_id=%s callback_data=%r", user_id, callback.data)
        await callback.answer("Не удалось распознать карту.", show_alert=True)
        return
    if deck_index < 0 or deck_index >= len(draft.cards):
        logger.warning(
            "out-of-range card index user_id=%s deck_index=%s card_count=%s",
            user_id,
            deck_index,
            len(draft.cards),
        )
        await callback.answer("Не удалось найти эту карту.", show_alert=True)
        return

    if deck_index in flow.selected_indices:
        flow.selected_indices.remove(deck_index)
    elif len(flow.selected_indices) < draft.required_count:
        flow.selected_indices.append(deck_index)
    else:
        await callback.answer("Для этого расклада уже выбраны все карты.")
        return

    logger.info(
        "virtual card selected user_id=%s selected_count=%s required_count=%s",
        user_id,
        len(flow.selected_indices),
        draft.required_count,
    )
    ready = len(flow.selected_indices) == draft.required_count
    await message.edit_text(
        _virtual_selection_text(draft.spread_slug, len(flow.selected_indices)),
        reply_markup=virtual_deck_keyboard(
            flow.selected_indices,
            card_count=len(draft.cards),
            ready_to_open=ready,
        ),
    )
    await callback.answer()


@router.callback_query(F.data == "open")
async def handle_open_cards(callback: CallbackQuery) -> None:
    flow = get_flow(callback.from_user.id)
    draft = flow.virtual_deck_draft
    if flow.selected_mode != "virtual" or draft is None:
        await callback.answer("Начни выбор заново через /start.", show_alert=True)
        return
    if len(flow.selected_indices) != draft.required_count:
        await callback.answer("Сначала выбери все карты расклада.", show_alert=True)
        return

    message = await _editable_message_or_answer(callback)
    if message is None:
        return

    draw = select_virtual_cards(draft, flow.selected_indices)
    await message.edit_text(_draw_result_text(draw), reply_markup=menu_button_keyboard())
    await callback.answer()


@router.callback_query()
async def handle_unknown_callback(callback: CallbackQuery) -> None:
    logger.warning(
        "unknown callback user_id=%s callback_data=%r",
        callback.from_user.id,
        callback.data,
    )
    await callback.answer("Не удалось распознать действие. Открой меню заново.", show_alert=True)


def _virtual_selection_text(spread_slug: str, selected_count: int) -> str:
    spread = get_spread(spread_slug)
    required_count = len(spread.positions)
    return (
        f"{spread.title_ru}\n"
        f"{spread.description_ru}\n\n"
        f"Выбрано карт: {selected_count}/{required_count}"
    )


def _draw_result_text(draw: StructuredSpreadDraw) -> str:
    lines = [
        draw.spread.title_ru,
        draw.spread.description_ru,
        "",
        "Карты:",
    ]
    for drawn in draw.drawn_cards:
        lines.append(
            f"{drawn.position.name_ru}: {drawn.card.display_name_ru} — {drawn.orientation}"
        )

    lines.extend(["", INTERPRETATION_PLACEHOLDER])
    return "\n".join(lines)


async def _editable_message_or_answer(
    callback: CallbackQuery,
    *,
    text: str = "Сообщение недоступно. Открой меню заново.",
):
    if callback.message is None:
        await callback.answer(text, show_alert=True)
        return None
    return callback.message
