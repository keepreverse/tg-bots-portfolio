"""Handler routers, wired into the dispatcher in `bot.py`."""

from __future__ import annotations

from aiogram import Router

from ..quiz_engine import QuizConfig
from .admin import build_admin_router
from .menu import build_fallback_router, build_menu_router
from .quiz import build_quiz_router


def build_all_routers(*, config: QuizConfig) -> list[Router]:
    """Order matters — quiz/admin must see callbacks before the fallback."""
    return [
        build_menu_router(config=config),
        build_quiz_router(config=config),
        build_admin_router(config=config),
        build_fallback_router(config=config),
    ]
