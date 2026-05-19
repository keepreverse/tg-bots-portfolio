from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BotCommand,
    BotCommandScopeChat,
    BotCommandScopeDefault,
)

from .config import Settings
from .db import LeadsRepo
from .handlers import build_router

log = logging.getLogger(__name__)


USER_COMMANDS: list[BotCommand] = [
    BotCommand(command="start", description="Главное меню"),
    BotCommand(command="menu", description="Открыть меню"),
    BotCommand(command="survey", description="Оставить заявку"),
    BotCommand(command="cancel", description="Отменить и вернуться в меню"),
    BotCommand(command="help", description="Помощь"),
]

ADMIN_COMMANDS: list[BotCommand] = [
    *USER_COMMANDS,
    BotCommand(command="admin", description="Админ-панель"),
    BotCommand(command="stats", description="Статистика заявок"),
    BotCommand(command="export", description="Выгрузка заявок в CSV"),
    BotCommand(command="ping", description="Проверка, что бот жив"),
]


def build_bot(settings: Settings) -> Bot:
    return Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def build_dispatcher(settings: Settings, repo: LeadsRepo) -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    dp["settings"] = settings
    dp["repo"] = repo
    dp.include_router(build_router())
    return dp


async def setup_commands(bot: Bot, settings: Settings) -> None:
    """Register the / menu shown in Telegram clients for users and the admin."""
    await bot.set_my_commands(USER_COMMANDS, scope=BotCommandScopeDefault())
    try:
        await bot.set_my_commands(
            ADMIN_COMMANDS,
            scope=BotCommandScopeChat(chat_id=settings.admin_chat_id),
        )
    except Exception as exc:
        # The admin may not have started a chat with the bot yet — don't crash.
        log.warning("Could not set admin-scoped commands: %s", exc)


async def run(settings: Settings) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    )
    repo = LeadsRepo(settings.db_path)
    await repo.init()
    bot = build_bot(settings)
    dp = build_dispatcher(settings, repo)
    await setup_commands(bot, settings)
    log.info("lead-bot starting (admin_chat_id=%s)", settings.admin_chat_id)
    await dp.start_polling(bot)
