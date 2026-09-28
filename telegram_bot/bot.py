from __future__ import annotations

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

from app_core.readings.storage import init_db
from telegram_bot.handlers import router, telegram_persist_readings_enabled

logger = logging.getLogger(__name__)


def _presence(value: str | None) -> str:
    return "set" if (value or "").strip() else "missing"


def _flag_state(value: str | None) -> str:
    if value is None or not value.strip():
        return "missing"
    if value.strip().lower() in {"1", "true", "yes", "on"}:
        return "enabled"
    return "disabled"


def log_env_diagnostics() -> None:
    load_dotenv()
    logger.info(
        "Telegram env diagnostics DATABASE_URL=%s OPENAI_API_KEY=%s OPENAI_BASE_URL=%s "
        "OPENAI_MODEL=%s RAG_USE_CACHE=%s RAG_CACHE_DB_PATH=%s LLM_API_KEY=%s "
        "LLM_BASE_URL=%s RAG_CHAT_MODEL=%s TELEGRAM_PERSIST_READINGS=%s",
        _presence(os.getenv("DATABASE_URL")),
        _presence(os.getenv("OPENAI_API_KEY")),
        _presence(os.getenv("OPENAI_BASE_URL")),
        _presence(os.getenv("OPENAI_MODEL")),
        _presence(os.getenv("RAG_USE_CACHE")),
        _presence(os.getenv("RAG_CACHE_DB_PATH")),
        _presence(os.getenv("LLM_API_KEY")),
        _presence(os.getenv("LLM_BASE_URL")),
        _presence(os.getenv("RAG_CHAT_MODEL")),
        _flag_state(os.getenv("TELEGRAM_PERSIST_READINGS")),
    )


def ensure_reading_storage_ready() -> None:
    """Initialize the PostgreSQL reading schema if persistence is enabled.

    No-op (and no PostgreSQL dependency) when persistence is disabled.
    Schema initialization failures are re-raised so startup fails fast
    instead of surfacing on the first reading a user tries to save.
    """
    if not telegram_persist_readings_enabled():
        return

    try:
        init_db()
    except Exception:
        logger.critical(
            "Failed to initialize PostgreSQL reading storage schema while "
            "TELEGRAM_PERSIST_READINGS is enabled. Check DATABASE_URL and "
            "PostgreSQL availability.",
            exc_info=True,
        )
        raise


def get_bot_token() -> str:
    load_dotenv()
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    if not token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is not set. Add it to your environment or .env file."
        )
    return token


def configure_logging() -> None:
    load_dotenv()
    level_name = (os.getenv("LOG_LEVEL") or "INFO").strip().upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


async def main() -> None:
    log_env_diagnostics()
    ensure_reading_storage_ready()
    bot = Bot(token=get_bot_token())
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    try:
        logger.info("Starting Telegram bot polling")
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()
        logger.info("Telegram bot stopped")


if __name__ == "__main__":
    configure_logging()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Telegram bot stopped")
