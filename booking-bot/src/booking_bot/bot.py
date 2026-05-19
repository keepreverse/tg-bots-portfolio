"""aiogram3 bot bootstrap."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from .config import get_settings
from .db import init_db, seed_services
from .handlers import build_all_routers
from .scheduler import build_scheduler

log = logging.getLogger("booking_bot")


def build_dispatcher() -> Dispatcher:
    """Wire all routers into a Dispatcher. Useful for tests / smoke checks."""
    dp = Dispatcher(storage=MemoryStorage())
    for r in build_all_routers():
        dp.include_router(r)
    return dp


async def _async_main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s | %(message)s",
    )
    settings = get_settings()
    await init_db(settings.db_path_abs)
    seed_path = Path(__file__).resolve().parents[2] / "data" / "seed_services.json"
    await seed_services(settings.db_path_abs, seed_path)

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = build_dispatcher()
    scheduler = build_scheduler(bot, settings)
    scheduler.start()

    log.info("Booking-bot starting...")
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


def main() -> None:
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
