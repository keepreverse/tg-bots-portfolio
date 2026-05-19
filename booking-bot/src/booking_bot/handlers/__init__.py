"""Handler routers, wired into the dispatcher in `bot.py`."""

from __future__ import annotations

from aiogram import Router

from .admin import build_admin_router
from .booking import build_booking_router
from .menu import build_menu_router
from .my_bookings import build_my_bookings_router


def build_all_routers() -> list[Router]:
    return [
        build_menu_router(),
        build_booking_router(),
        build_my_bookings_router(),
        build_admin_router(),
    ]
