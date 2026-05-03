from __future__ import annotations

import asyncio
import logging
import os

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, FSInputFile, Message

from app_core.tarot.deck import CARD_BY_SLUG, resolve_card_by_name
from app_core.tarot.draw import (
    PhysicalDrawCard,
    StructuredSpreadDraw,
    create_draw_from_physical_cards,
    draw_virtual_spread,
)
from app_core.tarot.reading_service import (
    FollowUpReadingResult,
    StructuredReadingResult,
    answer_follow_up,
    create_reading_from_drawn_cards,
)
from app_core.tarot.selection import (
    create_draw_from_virtual_selection,
    create_virtual_deck_draft,
)
from app_core.tarot.spreads import get_spread
from telegram_bot.card_assets import get_card_image_path
from telegram_bot.formatting import (
    build_follow_up_question_confirmation,
    build_question_confirmation,
    clean_telegram_text,
    format_telegram_section_headings,
    split_telegram_message,
)
from telegram_bot.keyboards import (
    follow_up_result_keyboard,
    follow_up_retry_keyboard,
    get_spread_by_callback_id,
    get_mode_display_label,
    get_spread_display_label,
    main_menu_keyboard,
    menu_button_keyboard,
    physical_orientation_keyboard,
    reading_result_keyboard,
    spread_selection_keyboard,
    virtual_deck_keyboard,
)
from telegram_bot.state import PhysicalCardEntry, get_flow, reset_flow

router = Router()
logger = logging.getLogger(__name__)

START_TEXT = (
    "🌙 Arcana Whisper ✨\n\n"
    "Твой мягкий помощник в понимании себя через символы таро.\n\n"
    "Выбери способ работы с картами:\n\n"
    "🌙 Виртуальная колода — ты выбираешь закрытые карты сама.\n"
    "🕯 Физическая колода — ты вводишь карты из своей реальной колоды.\n"
    "✨ Автовыбор карт — бот сам вытягивает карты для выбранного расклада."
)

QUESTION_PROMPT = (
    "Напиши вопрос или тему для расклада.\n\n"
    "Лучше формулировать про себя, своё состояние, выбор или следующий бережный шаг.\n\n"
    "Например:\n"
    "— Что мне важно понять в этой ситуации?\n"
    "— На что обратить внимание сегодня?\n"
    "— Как бережнее пройти через этот период?"
)

PHYSICAL_PREPARATION_TEXT = (
    "🕯 Физическая колода\n\n"
    "Перед раскладом дай себе минуту тишины.\n\n"
    "Сделай несколько спокойных вдохов и выдохов. Сформулируй вопрос так, "
    "чтобы он был про тебя, твоё состояние, выбор или следующий бережный шаг.\n\n"
    "Перемешай колоду привычным способом и вытяни карты по позициям расклада.\n\n"
    "Я буду просить вводить карты по одной."
)

FOLLOW_UP_PROMPT = (
    "💬 Напиши уточняющий вопрос по этому раскладу.\n\n"
    "Например:\n"
    "— Что здесь главное для моего следующего шага?\n"
    "— На что мне стоит обратить внимание в этой карте?\n"
    "— Как мягче пройти через эту ситуацию?"
)

FOLLOW_UP_QUESTION_GENTLE_STEP = (
    "Какой следующий бережный шаг можно увидеть в этом раскладе? "
    "Ответь кратко, практично и без фатализма."
)

FOLLOW_UP_QUESTION_MAIN = (
    "Что самое главное в этом раскладе? Сформулируй кратко, без повторения всей интерпретации."
)


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
    message = callback.message
    if message is not None:
        try:
            await message.edit_reply_markup(reply_markup=None)
        except TelegramBadRequest:
            pass
        await message.answer(
            START_TEXT,
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
    else:
        await callback.answer("Меню открыто. Отправь /start, если новое сообщение не появилось.", show_alert=True)
    await callback.answer()


@router.callback_query(F.data == "m:v")
async def handle_virtual_mode(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    reset_flow(user_id, selected_mode="virtual")
    logger.info("selected mode user_id=%s mode=virtual", user_id)
    await _confirm_callback_selection(
        callback,
        f"✅ Выбран способ работы: {get_mode_display_label('virtual')}",
    )
    await _answer_or_notify(
        callback,
        "Выбери расклад для виртуальной колоды:",
        reply_markup=spread_selection_keyboard("v"),
    )
    await callback.answer()


@router.callback_query(F.data == "m:q")
async def handle_quick_mode(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    reset_flow(user_id, selected_mode="quick_draw")
    logger.info("selected mode user_id=%s mode=quick_draw", user_id)
    await _confirm_callback_selection(
        callback,
        f"✅ Выбран способ работы: {get_mode_display_label('quick_draw')}",
    )
    await _answer_or_notify(
        callback,
        "Выбери расклад для автовыбора карт:",
        reply_markup=spread_selection_keyboard("q"),
    )
    await callback.answer()


@router.callback_query(F.data == "m:p")
async def handle_physical_mode(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    reset_flow(user_id, selected_mode="physical_deck")
    logger.info("selected mode user_id=%s mode=physical_deck", user_id)
    await _confirm_callback_selection(
        callback,
        f"✅ Выбран способ работы: {get_mode_display_label('physical_deck')}",
    )
    await _answer_or_notify(
        callback,
        "Выбери расклад для физической колоды:",
        reply_markup=spread_selection_keyboard("p"),
    )
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

    selected_mode = _mode_from_callback_id(mode_callback_id)
    if selected_mode is None:
        await callback.answer("Этот режим пока недоступен.", show_alert=True)
        return

    flow = get_flow(user_id)
    flow.selected_mode = selected_mode
    flow.selected_spread_slug = spread.slug
    flow.user_question = None
    flow.awaiting_question = True
    flow.awaiting_follow_up_question = False
    flow.follow_up_reading_id = None
    flow.follow_up_prompt_message_id = None
    flow.awaiting_virtual_selection = False
    flow.awaiting_physical_card_name = False
    flow.awaiting_physical_orientation = False
    flow.question_received = False
    flow.virtual_deck_draft = None
    flow.selected_indices = []
    flow.last_drawn_cards = None
    flow.current_card_position_index = 0
    flow.pending_physical_card_name = None
    flow.pending_physical_card_slug = None
    flow.physical_cards = []
    logger.info(
        "selected spread user_id=%s spread_slug=%s mode=%s",
        user_id,
        spread.slug,
        selected_mode,
    )
    await _confirm_callback_selection(
        callback,
        f"✅ Выбран расклад: {get_spread_display_label(spread.slug)}",
    )
    prompt_message = await _answer_or_notify(
        callback,
        QUESTION_PROMPT,
        reply_markup=menu_button_keyboard(),
    )
    flow.question_prompt_message_id = prompt_message.message_id if prompt_message is not None else None

    await callback.answer()


@router.callback_query(F.data.startswith("c:"))
async def handle_card_selection(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    flow = get_flow(user_id)
    draft = flow.virtual_deck_draft
    if flow.selected_mode != "virtual" or not flow.awaiting_virtual_selection or draft is None:
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
    user_id = callback.from_user.id
    flow = get_flow(user_id)
    draft = flow.virtual_deck_draft
    if flow.selected_mode != "virtual" or draft is None:
        await callback.answer("Начни выбор заново через /start.", show_alert=True)
        return
    if len(flow.selected_indices) != draft.required_count:
        await callback.answer("Сначала выбери все карты расклада.", show_alert=True)
        return
    question_text = (flow.user_question or "").strip()
    if not question_text:
        reset_flow(user_id)
        await callback.answer("Не удалось найти вопрос расклада. Начни заново.", show_alert=True)
        return

    message = await _editable_message_or_answer(callback)
    if message is None:
        return

    draw = create_draw_from_virtual_selection(draft, flow.selected_indices)
    logger.info("reveal virtual cards user_id=%s count=%s", user_id, len(draw.drawn_cards))
    await message.edit_text(_virtual_revealed_cards_text(draw), reply_markup=menu_button_keyboard())
    await _send_card_images(message, draw, user_id=user_id)
    loading_message = await message.answer(
        "✨ Готовлю интерпретацию…",
        reply_markup=menu_button_keyboard(),
    )
    persist = _telegram_persist_readings_enabled()
    try:
        reading = await asyncio.to_thread(
            create_reading_from_drawn_cards,
            draw=draw,
            user_question=question_text,
            persist=persist,
        )
    except Exception:
        try:
            await loading_message.delete()
        except TelegramBadRequest:
            pass
        logger.exception(
            "Tarot interpretation failed user_id=%s mode=%s spread_slug=%s",
            user_id,
            flow.selected_mode,
            flow.selected_spread_slug,
        )
        reset_flow(user_id)
        await message.answer(
            "Не получилось подготовить интерпретацию. Похоже, временно недоступна модель "
            "или соединение. Можно попробовать ещё раз.",
            reply_markup=menu_button_keyboard(),
        )
        await callback.answer()
        return

    flow.last_reading_id = str(reading.reading_id) if reading.reading_id is not None else None
    flow.last_drawn_cards = draw
    saved_reading_id = flow.last_reading_id
    reset_flow(user_id)
    if saved_reading_id:
        get_flow(user_id).last_reading_id = saved_reading_id
    logger.info(
        "virtual interpretation completed user_id=%s spread_slug=%s count=%s persist=%s",
        user_id,
        draw.spread.slug,
        len(reading.cards),
        persist,
    )
    await _send_auto_draw_reading(message, reading, loading_message=loading_message)
    await callback.answer()


@router.callback_query(F.data.startswith("phys_orient:"))
async def handle_physical_orientation(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    flow = get_flow(user_id)
    if flow.selected_mode != "physical_deck" or not flow.awaiting_physical_orientation:
        await callback.answer("Начни выбор заново через /start.", show_alert=True)
        return

    orientation = (callback.data or "").split(":", maxsplit=1)[-1]
    if orientation not in ("upright", "reversed"):
        await callback.answer("Не удалось распознать положение карты.", show_alert=True)
        return

    message = await _editable_message_or_answer(callback)
    if message is None:
        return

    spread_slug = flow.selected_spread_slug
    card_name = (flow.pending_physical_card_name or "").strip()
    card_slug = (flow.pending_physical_card_slug or "").strip()
    if not spread_slug or not card_name or not card_slug:
        reset_flow(user_id)
        await callback.answer("Не удалось сохранить карту. Начни заново.", show_alert=True)
        return

    spread = get_spread(spread_slug)
    position_index = flow.current_card_position_index
    if position_index >= len(spread.positions):
        reset_flow(user_id)
        await callback.answer("Расклад уже заполнен. Открой меню заново.", show_alert=True)
        return

    position = spread.positions[position_index]
    entry = PhysicalCardEntry(
        position_index=position.index,
        position_name_ru=position.name_ru,
        card_name=card_name,
        card_slug=card_slug,
        orientation=orientation,
    )
    flow.physical_cards.append(entry)
    flow.pending_physical_card_name = None
    flow.pending_physical_card_slug = None
    flow.awaiting_physical_orientation = False

    logger.info(
        "physical orientation selected user_id=%s position_index=%s orientation=%s",
        user_id,
        position.index,
        orientation,
    )

    accepted_text = _physical_card_accepted_text(entry, len(flow.physical_cards), len(spread.positions))
    if len(flow.physical_cards) >= len(spread.positions):
        logger.info("physical cards completed user_id=%s count=%s", user_id, len(flow.physical_cards))
        summary = _physical_cards_summary_text(flow.physical_cards)
        await message.edit_text(
            f"{accepted_text}\n\n{summary}",
        )
        loading_message = await message.answer(
            "✨ Готовлю интерпретацию…",
            reply_markup=menu_button_keyboard(),
        )
        persist = _telegram_persist_readings_enabled()
        question_text = (flow.user_question or "").strip()
        if not question_text:
            try:
                await loading_message.delete()
            except TelegramBadRequest:
                pass
            reset_flow(user_id)
            await message.answer(
                "Не удалось найти вопрос расклада. Начни заново через меню.",
                reply_markup=main_menu_keyboard(),
            )
            await callback.answer()
            return
        try:
            draw = create_draw_from_physical_cards(
                spread_slug,
                [
                    PhysicalDrawCard(
                        card=CARD_BY_SLUG[card.card_slug],
                        orientation=card.orientation,
                    )
                    for card in flow.physical_cards
                ],
            )
            reading = await asyncio.to_thread(
                create_reading_from_drawn_cards,
                draw=draw,
                user_question=question_text,
                persist=persist,
            )
        except Exception:
            try:
                await loading_message.delete()
            except TelegramBadRequest:
                pass
            logger.exception(
                "Tarot interpretation failed user_id=%s mode=%s spread_slug=%s",
                user_id,
                flow.selected_mode,
                spread_slug,
            )
            reset_flow(user_id)
            await message.answer(
                "Не получилось подготовить интерпретацию. Похоже, временно недоступна модель "
                "или соединение. Можно попробовать ещё раз.",
                reply_markup=menu_button_keyboard(),
            )
            await callback.answer()
            return

        flow.last_reading_id = str(reading.reading_id) if reading.reading_id is not None else None
        flow.last_drawn_cards = draw
        saved_reading_id = flow.last_reading_id
        reset_flow(user_id)
        if saved_reading_id:
            get_flow(user_id).last_reading_id = saved_reading_id
        logger.info(
            "physical interpretation completed user_id=%s spread_slug=%s count=%s persist=%s",
            user_id,
            spread_slug,
            len(reading.cards),
            persist,
        )
        await _send_auto_draw_reading(message, reading, loading_message=loading_message)
    else:
        flow.current_card_position_index += 1
        flow.awaiting_physical_card_name = True
        await message.edit_text(accepted_text)
        await message.answer(_physical_card_prompt(spread, flow.current_card_position_index))

    await callback.answer()


@router.callback_query(F.data.startswith("fup:"))
async def handle_reading_follow_up(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    message = await _editable_message_or_answer(callback, text="Не смогла найти это сообщение.")
    if message is None:
        return

    parts = (callback.data or "").split(":", maxsplit=2)
    if len(parts) != 3:
        await callback.answer("Не удалось распознать уточнение.", show_alert=True)
        return

    _, action, reading_id = parts
    if not reading_id.strip():
        await callback.answer("Не смогла найти этот расклад.", show_alert=True)
        return

    flow = get_flow(user_id)
    flow.last_reading_id = reading_id

    if action == "ask":
        _clear_follow_up_state(flow)
        flow.awaiting_follow_up_question = True
        flow.follow_up_reading_id = reading_id
        try:
            await message.edit_reply_markup(reply_markup=None)
        except TelegramBadRequest:
            pass
        prompt_message = await message.answer(
            FOLLOW_UP_PROMPT,
            reply_markup=menu_button_keyboard(),
        )
        flow.follow_up_prompt_message_id = prompt_message.message_id
        await callback.answer()
        return

    if action == "step":
        await _start_preset_follow_up(
            callback,
            message=message,
            reading_id=reading_id,
            question=FOLLOW_UP_QUESTION_GENTLE_STEP,
        )
        return

    if action == "main":
        await _start_preset_follow_up(
            callback,
            message=message,
            reading_id=reading_id,
            question=FOLLOW_UP_QUESTION_MAIN,
        )
        return

    await callback.answer("Не удалось распознать уточнение.", show_alert=True)


@router.callback_query()
async def handle_unknown_callback(callback: CallbackQuery) -> None:
    logger.warning(
        "unknown callback user_id=%s callback_data=%r",
        callback.from_user.id,
        callback.data,
    )
    await callback.answer("Не удалось распознать действие. Открой меню заново.", show_alert=True)


@router.message(F.text)
async def handle_text_message(message: Message) -> None:
    user_id = message.from_user.id
    text = (message.text or "").strip()
    flow = get_flow(user_id)

    if text.startswith("/"):
        await message.answer("Открой меню через /start или /menu.")
        return

    if flow.awaiting_question:
        await _handle_question_text(message, text)
        return

    if flow.awaiting_follow_up_question:
        await _handle_follow_up_question_text(message, text)
        return

    if flow.awaiting_physical_card_name:
        await _handle_physical_card_name_text(message, text)
        return

    if flow.awaiting_physical_orientation:
        await message.answer(
            "Выбери положение карты кнопкой ниже.",
            reply_markup=physical_orientation_keyboard(),
        )
        return

    if not flow.selected_mode:
        await message.answer(
            "Я пока не жду текст для расклада. Открой меню и выбери формат.",
            reply_markup=main_menu_keyboard(),
        )
        return

    await message.answer(
        "Продолжи текущий расклад через кнопки или вернись в меню.",
        reply_markup=menu_button_keyboard(),
    )


def _virtual_selection_text(spread_slug: str, selected_count: int) -> str:
    spread = get_spread(spread_slug)
    required_count = len(spread.positions)
    return (
        "Прислушайся к себе и выбери карты для расклада.\n\n"
        f"Выбрано карт: {selected_count}/{required_count}"
    )


async def _handle_question_text(message: Message, text: str) -> None:
    user_id = message.from_user.id
    flow = get_flow(user_id)
    spread_slug = flow.selected_spread_slug
    mode = flow.selected_mode

    if not text:
        await message.answer("Напиши вопрос или тему одним сообщением.")
        return

    if not spread_slug or mode is None:
        reset_flow(user_id)
        logger.warning("question received without complete state user_id=%s mode=%s", user_id, mode)
        await message.answer(
            "Не смогла найти выбранный расклад. Вернись в меню и выбери расклад заново.",
            reply_markup=main_menu_keyboard(),
        )
        return

    flow.awaiting_question = False
    flow.user_question = text
    flow.question_received = True
    logger.info("question received user_id=%s mode=%s spread_slug=%s", user_id, mode, spread_slug)
    await _confirm_question_prompt(message, flow, text)

    if mode == "virtual":
        flow.awaiting_virtual_selection = True
        flow.virtual_deck_draft = create_virtual_deck_draft(spread_slug)
        flow.selected_indices = []
        await message.answer(
            _virtual_selection_text(spread_slug, 0),
            reply_markup=virtual_deck_keyboard(
                [],
                card_count=len(flow.virtual_deck_draft.cards),
                ready_to_open=False,
            ),
        )
        return

    if mode == "physical_deck":
        flow.awaiting_physical_card_name = True
        flow.awaiting_physical_orientation = False
        flow.current_card_position_index = 0
        flow.pending_physical_card_name = None
        flow.pending_physical_card_slug = None
        flow.physical_cards = []
        spread = get_spread(spread_slug)
        await message.answer(PHYSICAL_PREPARATION_TEXT, reply_markup=menu_button_keyboard())
        await message.answer(_physical_card_prompt(spread, 0))
        return

    if mode == "quick_draw":
        draw = draw_virtual_spread(spread_slug)
        flow.last_drawn_cards = draw
        await message.answer(_auto_draw_cards_preview_text(draw))
        loading_message = await message.answer(
            "✨ Готовлю интерпретацию…",
            reply_markup=menu_button_keyboard(),
        )
        persist = _telegram_persist_readings_enabled()
        try:
            reading = await asyncio.to_thread(
                create_reading_from_drawn_cards,
                draw=draw,
                user_question=text,
                persist=persist,
            )
        except Exception:
            try:
                await loading_message.delete()
            except TelegramBadRequest:
                pass
            logger.exception(
                "Tarot interpretation failed user_id=%s mode=%s spread_slug=%s",
                user_id,
                mode,
                spread_slug,
            )
            reset_flow(user_id)
            await message.answer(
                "Не получилось подготовить интерпретацию. Похоже, временно недоступна модель "
                "или соединение. Можно попробовать ещё раз.",
                reply_markup=menu_button_keyboard(),
            )
            return

        flow.last_reading_id = str(reading.reading_id) if reading.reading_id is not None else None
        flow.last_drawn_cards = None
        saved_reading_id = flow.last_reading_id
        reset_flow(user_id)
        if saved_reading_id:
            get_flow(user_id).last_reading_id = saved_reading_id
        logger.info(
            "auto draw interpretation completed user_id=%s spread_slug=%s count=%s persist=%s",
            user_id,
            spread_slug,
            len(reading.cards),
            persist,
        )
        await _send_auto_draw_reading(message, reading, loading_message=loading_message)
        return

    await message.answer("Этот режим пока недоступен.", reply_markup=menu_button_keyboard())


async def _handle_physical_card_name_text(message: Message, text: str) -> None:
    user_id = message.from_user.id
    flow = get_flow(user_id)
    spread_slug = flow.selected_spread_slug
    card_name = text.strip()

    if not card_name:
        await message.answer("Введи название карты одним сообщением.")
        return
    if not spread_slug:
        reset_flow(user_id)
        await message.answer(
            "Не смогла найти выбранный расклад. Вернись в меню и выбери расклад заново.",
            reply_markup=main_menu_keyboard(),
        )
        return

    spread = get_spread(spread_slug)
    if flow.current_card_position_index >= len(spread.positions):
        reset_flow(user_id)
        await message.answer("Расклад уже заполнен. Открой меню заново.", reply_markup=main_menu_keyboard())
        return

    resolved_card = resolve_card_by_name(card_name)
    if resolved_card is None:
        await message.answer(
            "Не смогла найти такую карту. Попробуй ввести название ещё раз, например: "
            "Девятка Кубков или The World."
        )
        return

    flow.pending_physical_card_name = resolved_card.display_name_ru
    flow.pending_physical_card_slug = resolved_card.slug
    flow.awaiting_physical_card_name = False
    flow.awaiting_physical_orientation = True
    position = spread.positions[flow.current_card_position_index]
    logger.info(
        "physical card name received user_id=%s position_index=%s",
        user_id,
        position.index,
    )
    await message.answer(
        f"Выбери положение карты:\n\nНазвание карты: {resolved_card.display_name_ru}",
        reply_markup=physical_orientation_keyboard(),
    )


def _mode_from_callback_id(mode_callback_id: str):
    return {
        "v": "virtual",
        "p": "physical_deck",
        "q": "quick_draw",
    }.get(mode_callback_id)


def _draw_result_text(draw: StructuredSpreadDraw) -> str:
    lines = [
        draw.spread.title_ru,
        _spread_description_text(draw.spread.slug, draw.spread.description_ru),
        "",
        "Карты:",
    ]
    for drawn in draw.drawn_cards:
        lines.append(
            (
                f"{drawn.position.name_ru}: {drawn.card.display_name_ru} — "
                f"{_orientation_text(drawn.orientation)}"
            )
        )

    return "\n".join(lines)


def _virtual_revealed_cards_text(draw: StructuredSpreadDraw) -> str:
    return _cards_preview_text("🎴 Выбранные карты", draw)


def _auto_draw_reading_text(reading: StructuredReadingResult) -> str:
    cleaned_answer = clean_telegram_text(reading.answer)
    lines = [
        "✨ Расклад готов",
        "",
        f"Расклад: {_telegram_spread_title(reading.spread.slug, reading.spread.title_ru)}",
        "",
        "Карты:",
    ]

    for index, card in enumerate(reading.cards, start=1):
        lines.extend(
            [
                f"{index}. {card.position_name_ru}",
                f"Название карты: {card.card_name_ru}",
                f"Положение: {_orientation_text(card.orientation)}",
                "",
            ]
        )

    lines.extend(["Интерпретация:", cleaned_answer])
    if reading.reading_id is not None:
        lines.extend(["", f"ID расклада: {reading.reading_id}"])
    return "\n".join(lines)


def _auto_draw_cards_preview_text(draw: StructuredSpreadDraw) -> str:
    return _cards_preview_text("🎴 Вытянутые карты", draw)


def _cards_preview_text(title: str, draw: StructuredSpreadDraw) -> str:
    lines = [
        title,
        "",
    ]
    for index, drawn in enumerate(draw.drawn_cards, start=1):
        lines.extend(
            [
                f"{index}. {drawn.position.name_ru}",
                f"Название карты: {drawn.card.display_name_ru}",
                f"Положение: {_orientation_text(drawn.orientation)}",
                "",
            ]
        )
    return "\n".join(lines).strip()


async def _send_card_images(message: Message, draw: StructuredSpreadDraw, *, user_id: int) -> None:
    for drawn in draw.drawn_cards:
        image_path = get_card_image_path(drawn.card.slug)
        if image_path is None:
            logger.info("card image asset missing user_id=%s slug=%s", user_id, drawn.card.slug)
            continue

        caption = (
            f"{drawn.position.name_ru} — {drawn.card.display_name_ru} — "
            f"{_orientation_text(drawn.orientation)}"
        )
        await message.answer_photo(FSInputFile(image_path), caption=caption)
        logger.info("card image sent user_id=%s slug=%s", user_id, drawn.card.slug)


def _spread_description_text(spread_slug: str, fallback: str) -> str:
    descriptions = {
        "one_card": "Один символический фокус для вопроса, состояния или дня.",
        "three_card_past_present_future": (
            "Что повлияло раньше, что происходит сейчас и куда ситуация может двигаться."
        ),
        "three_card_situation_obstacle_outcome": (
            "Что происходит, что мешает и какой бережный ориентир можно увидеть."
        ),
        "three_card_relationships": (
            "Твой фокус, фокус другого человека и динамика между вами — "
            "без утверждений о чужих мыслях как факте."
        ),
        "three_card_choice": "Два варианта и то, что важно учесть перед выбором.",
        "five_card_deep_reading": (
            "Более подробный разбор ситуации, ресурсов, препятствий и следующего шага."
        ),
    }
    return descriptions.get(spread_slug, fallback)


async def _send_auto_draw_reading(
    message: Message,
    reading: StructuredReadingResult,
    *,
    loading_message: Message | None = None,
) -> None:
    formatted_text = format_telegram_section_headings(_auto_draw_reading_text(reading))
    chunks = split_telegram_message(formatted_text)
    if not chunks:
        await message.answer(
            "Не получилось подготовить текст интерпретации.",
            reply_markup=menu_button_keyboard(),
        )
        return

    if loading_message is not None and len(chunks) == 1:
        try:
            await loading_message.edit_text(
                chunks[0],
                reply_markup=reading_result_keyboard(
                    reading_id=str(reading.reading_id) if reading.reading_id is not None else None
                ),
                parse_mode="HTML",
            )
            return
        except TelegramBadRequest:
            pass

    if loading_message is not None:
        try:
            await loading_message.delete()
        except TelegramBadRequest:
            pass

    for index, chunk in enumerate(chunks):
        reply_markup = None
        if index == len(chunks) - 1:
            reply_markup = reading_result_keyboard(
                reading_id=str(reading.reading_id) if reading.reading_id is not None else None
            )
        await message.answer(chunk, reply_markup=reply_markup, parse_mode="HTML")


def _telegram_spread_title(spread_slug: str, fallback: str) -> str:
    labels = {
        "one_card": "🎯 Одна карта — фокус момента",
        "three_card_past_present_future": "🕰 Три карты — прошлое / сейчас / возможный вектор",
        "three_card_situation_obstacle_outcome": "🧭 Три карты — ситуация / препятствие / ориентир",
        "three_card_relationships": "🤝 Три карты — я / другой / динамика",
        "three_card_choice": "⚖️ Три карты — вариант A / вариант B / что учесть",
        "five_card_deep_reading": "🔎 Пять карт — глубокий разбор",
    }
    return labels.get(spread_slug, fallback)


def _database_url_is_configured() -> bool:
    return bool((os.getenv("DATABASE_URL") or "").strip())


def _telegram_persist_readings_enabled() -> bool:
    value = (os.getenv("TELEGRAM_PERSIST_READINGS") or "").strip().lower()
    if value not in {"1", "true", "yes", "on"}:
        return False

    if _database_url_is_configured():
        return True

    logger.warning(
        "TELEGRAM_PERSIST_READINGS=true but DATABASE_URL is missing; using persist=False"
    )
    return False


def _orientation_text(orientation: str) -> str:
    if orientation == "reversed":
        return "перевёрнутое положение"
    return "прямое положение"


def _physical_card_prompt(spread, position_index: int) -> str:
    position = spread.positions[position_index]
    return (
        f"Карта {position_index + 1}/{len(spread.positions)}\n"
        f"Позиция: {position.name_ru}\n\n"
        "Введи название карты.\n"
        "Например: Девятка Кубков"
    )


def _physical_card_accepted_text(
    card: PhysicalCardEntry,
    entered_count: int,
    required_count: int,
) -> str:
    return (
        "Карта принята.\n\n"
        f"{entered_count}/{required_count}\n"
        f"Позиция: {card.position_name_ru}\n"
        f"Название карты: {card.card_name}\n"
        f"Положение: {_orientation_text(card.orientation)}"
    )


def _physical_cards_summary_text(cards: list[PhysicalCardEntry]) -> str:
    lines = ["Карты внесены:"]
    for index, card in enumerate(cards, start=1):
        lines.extend(
            [
                "",
                f"{index}. {card.position_name_ru}",
                f"Название карты: {card.card_name}",
                f"Положение: {_orientation_text(card.orientation)}",
            ]
        )
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


async def _confirm_callback_selection(callback: CallbackQuery, confirmation_text: str) -> None:
    message = callback.message
    if message is None:
        return
    await message.edit_text(confirmation_text)


async def _answer_or_notify(
    callback: CallbackQuery,
    text: str,
    *,
    reply_markup=None,
) -> None:
    if callback.message is not None:
        return await callback.message.answer(text, reply_markup=reply_markup)

    if callback.message is None:
        await callback.answer("Выбор сохранён. Продолжаем следующим сообщением.", show_alert=True)
    return None


async def _confirm_question_prompt(message: Message, flow, question_text: str) -> None:
    confirmation = build_question_confirmation(question_text)
    prompt_message_id = flow.question_prompt_message_id
    flow.question_prompt_message_id = None

    if prompt_message_id is not None:
        try:
            await message.bot.edit_message_text(
                confirmation,
                chat_id=message.chat.id,
                message_id=prompt_message_id,
            )
            return
        except TelegramBadRequest:
            pass

    await message.answer(confirmation)


async def _handle_follow_up_question_text(message: Message, text: str) -> None:
    user_id = message.from_user.id
    flow = get_flow(user_id)
    reading_id = (flow.follow_up_reading_id or "").strip()
    if not text:
        await message.answer("Напиши уточняющий вопрос одним сообщением.")
        return
    if not reading_id:
        _clear_follow_up_state(flow)
        await message.answer(
            "Не смогла найти этот расклад. Вернись в меню и сделай новый расклад.",
            reply_markup=menu_button_keyboard(),
        )
        return

    flow.awaiting_follow_up_question = False
    await _confirm_follow_up_prompt(message, flow, text)
    loading_message = await message.answer(
        "✨ Готовлю уточнение...",
        reply_markup=menu_button_keyboard(),
    )
    try:
        result = await asyncio.to_thread(answer_follow_up, reading_id, text)
    except Exception as exc:
        await _handle_follow_up_error(
            message,
            flow=flow,
            loading_message=loading_message,
            reading_id=reading_id,
            user_id=user_id,
            exc=exc,
        )
        return

    flow.last_reading_id = reading_id
    flow.follow_up_reading_id = reading_id
    logger.info("follow-up completed user_id=%s reading_id=%s", user_id, reading_id)
    await _send_follow_up_result(message, result, loading_message=loading_message)


async def _start_preset_follow_up(
    callback: CallbackQuery,
    *,
    message: Message,
    reading_id: str,
    question: str,
) -> None:
    user_id = callback.from_user.id
    flow = get_flow(user_id)
    _clear_follow_up_state(flow)
    flow.last_reading_id = reading_id
    flow.follow_up_reading_id = reading_id
    try:
        await message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass
    loading_message = await message.answer(
        "✨ Готовлю уточнение...",
        reply_markup=menu_button_keyboard(),
    )
    try:
        result = await asyncio.to_thread(answer_follow_up, reading_id, question)
    except Exception as exc:
        await _handle_follow_up_error(
            message,
            flow=flow,
            loading_message=loading_message,
            reading_id=reading_id,
            user_id=user_id,
            exc=exc,
        )
        await callback.answer()
        return

    logger.info("preset follow-up completed user_id=%s reading_id=%s", user_id, reading_id)
    await _send_follow_up_result(message, result, loading_message=loading_message)
    await callback.answer()


async def _handle_follow_up_error(
    message: Message,
    *,
    flow,
    loading_message: Message,
    reading_id: str,
    user_id: int,
    exc: Exception,
) -> None:
    try:
        await loading_message.delete()
    except TelegramBadRequest:
        pass

    flow.awaiting_follow_up_question = False
    flow.follow_up_prompt_message_id = None

    if isinstance(exc, ValueError) and "Reading session not found" in str(exc):
        _clear_follow_up_state(flow)
        await message.answer(
            "Не смогла найти этот расклад. Вернись в меню и сделай новый расклад.",
            reply_markup=menu_button_keyboard(),
        )
        return

    logger.exception(
        "Tarot follow-up failed user_id=%s reading_id=%s",
        user_id,
        reading_id,
    )
    flow.follow_up_reading_id = reading_id
    await message.answer(
        "Не получилось подготовить уточнение. Можно попробовать ещё раз.",
        reply_markup=follow_up_retry_keyboard(reading_id),
    )


async def _send_follow_up_result(
    message: Message,
    result: FollowUpReadingResult,
    *,
    loading_message: Message | None = None,
) -> None:
    formatted_text = format_telegram_section_headings(_follow_up_result_text(result))
    chunks = split_telegram_message(formatted_text)
    if not chunks:
        await message.answer(
            "Не получилось подготовить текст уточнения.",
            reply_markup=menu_button_keyboard(),
        )
        return

    if loading_message is not None and len(chunks) == 1:
        try:
            await loading_message.edit_text(
                chunks[0],
                reply_markup=follow_up_result_keyboard(str(result.reading_id)),
                parse_mode="HTML",
            )
            return
        except TelegramBadRequest:
            pass

    if loading_message is not None:
        try:
            await loading_message.delete()
        except TelegramBadRequest:
            pass

    for index, chunk in enumerate(chunks):
        reply_markup = None
        if index == len(chunks) - 1:
            reply_markup = follow_up_result_keyboard(str(result.reading_id))
        await message.answer(chunk, reply_markup=reply_markup, parse_mode="HTML")


def _follow_up_result_text(result: FollowUpReadingResult) -> str:
    cleaned_answer = clean_telegram_text(result.answer)
    return "\n".join(["💬 Уточнение по раскладу", "", cleaned_answer])


async def _confirm_follow_up_prompt(message: Message, flow, question_text: str) -> None:
    confirmation = build_follow_up_question_confirmation(question_text)
    prompt_message_id = flow.follow_up_prompt_message_id
    flow.follow_up_prompt_message_id = None

    if prompt_message_id is not None:
        try:
            await message.bot.edit_message_text(
                confirmation,
                chat_id=message.chat.id,
                message_id=prompt_message_id,
            )
            return
        except TelegramBadRequest:
            pass

    await message.answer(confirmation)


def _clear_follow_up_state(flow) -> None:
    flow.awaiting_follow_up_question = False
    flow.follow_up_reading_id = None
    flow.follow_up_prompt_message_id = None
