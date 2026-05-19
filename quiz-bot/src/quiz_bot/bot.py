"""aiogram3 bot bootstrap."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from .config import get_settings
from .db import init_db
from .handlers import build_all_routers
from .quiz_engine import QuizConfig, load_quiz_config

log = logging.getLogger("quiz_bot")


def build_dispatcher(config: QuizConfig) -> Dispatcher:
    """Wire all routers into a Dispatcher. Useful for tests / smoke checks."""
    dp = Dispatcher(storage=MemoryStorage())
    for r in build_all_routers(config=config):
        dp.include_router(r)
    return dp


async def _async_main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s | %(message)s",
    )
    settings = get_settings()
    await init_db(settings.db_path_abs)
    config = load_quiz_config(settings.quiz_path_abs)

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = build_dispatcher(config)

    log.info(
        "Quiz-bot starting... categories=%d business=%s",
        len(config.categories),
        settings.BUSINESS_NAME,
    )
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


def main() -> None:
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
