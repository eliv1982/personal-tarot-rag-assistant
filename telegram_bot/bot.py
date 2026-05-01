from __future__ import annotations

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

from telegram_bot.handlers import router

logger = logging.getLogger(__name__)


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
