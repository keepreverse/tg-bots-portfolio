"""Inline keyboard builders. Compact callback data encoded as `prefix:payload`."""

from __future__ import annotations

from datetime import date, time
from zoneinfo import ZoneInfo

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from . import texts
from .db import Booking, Service
from .timez import from_utc

# --- callback prefixes ----------------------------------------------------

CB_MAIN_MENU = "main"
CB_NEW = "new"
CB_CAT = "cat"
CB_SERVICE = "svc"
CB_DATE = "date"
CB_TIME = "time"
CB_CAL_PREV = "calp"
CB_CAL_NEXT = "caln"
CB_CONFIRM = "confirm"
CB_EDIT = "edit"
CB_PHONE_SKIP = "pskip"
CB_MY = "my"
CB_VIEW = "view"
CB_CANCEL_ASK = "cancq"
CB_CANCEL_YES = "cancy"
CB_CANCEL_NO = "cancn"
CB_SHOW_SERVICES = "showsvc"
CB_HELP = "help"
CB_ADMIN = "adm"
CB_ADMIN_STATS = "adm_stats"
CB_ADMIN_TODAY = "adm_today"
CB_ADMIN_UPCOMING = "adm_upc"      # carries page in `adm_upc:<page>`
CB_ADMIN_EXPORT = "adm_csv"
CB_NOOP = "noop"

# Back-nav prefixes inside booking FSM (matches lead-bot's `s:back`).
CB_BOOK_BACK = "bback"
CB_BOOK_CANCEL = "bcancel"

# Steps shown in the booking progress bar.
TOTAL_STEPS = 6  # category, service, date, time, name, phone (confirm = summary)


# --- main menu / nav primitives -------------------------------------------


def main_menu_kb(is_admin: bool = False) -> InlineKeyboardMarkup:
    """Main menu. When `is_admin` is True, adds the 🛠 Админ-панель row."""
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text=texts.MENU_NEW_BOOKING, callback_data=f"{CB_NEW}:0")],
        [
            InlineKeyboardButton(text=texts.MENU_SHOW_SERVICES, callback_data=f"{CB_SHOW_SERVICES}:0"),
            InlineKeyboardButton(text=texts.MENU_MY_BOOKINGS, callback_data=f"{CB_MY}:0"),
        ],
        [InlineKeyboardButton(text=texts.MENU_HELP, callback_data=f"{CB_HELP}:0")],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton(text=texts.MENU_ADMIN, callback_data=f"{CB_ADMIN}:0")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_to_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=texts.NAV_TO_MAIN, callback_data=f"{CB_MAIN_MENU}:0"),
    ]])


def _booking_nav_row(allow_back: bool) -> list[InlineKeyboardButton]:
    """Back / Cancel row used inside the booking FSM."""
    row: list[InlineKeyboardButton] = []
    if allow_back:
        row.append(InlineKeyboardButton(text=texts.NAV_BACK, callback_data=f"{CB_BOOK_BACK}:0"))
    row.append(InlineKeyboardButton(text=texts.NAV_CANCEL, callback_data=f"{CB_BOOK_CANCEL}:0"))
    return row


# --- booking screens ------------------------------------------------------


def category_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=texts.CAT_TATTOO, callback_data=f"{CB_CAT}:tattoo"),
            InlineKeyboardButton(text=texts.CAT_PIERCING, callback_data=f"{CB_CAT}:piercing"),
        ],
        _booking_nav_row(allow_back=False),
    ])


def services_list_kb(services: list[Service]) -> InlineKeyboardMarkup:
    from .duration import format_duration
    from .money import format_price

    rows: list[list[InlineKeyboardButton]] = []
    for s in services:
        label = (
            f"{s.emoji} {s.name} · "
            f"{format_duration(s.duration_minutes)} · {format_price(s.price_rub)}"
        ).strip()
        rows.append([InlineKeyboardButton(text=label, callback_data=f"{CB_SERVICE}:{s.id}")])
    rows.append(_booking_nav_row(allow_back=True))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def time_grid_kb(date_local: date, slots: list[time]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for t in slots:
        row.append(InlineKeyboardButton(
            text=f"{t.hour:02d}:{t.minute:02d}",
            callback_data=f"{CB_TIME}:{date_local.isoformat()}:{t.hour:02d}{t.minute:02d}",
        ))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append(_booking_nav_row(allow_back=True))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def text_step_kb() -> InlineKeyboardMarkup:
    """Inline keyboard shown alongside text-input prompts (name)."""
    return InlineKeyboardMarkup(inline_keyboard=[_booking_nav_row(allow_back=True)])


def confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts.CONFIRM_OK, callback_data=f"{CB_CONFIRM}:0")],
        _booking_nav_row(allow_back=True),
    ])


def phone_reply_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=texts.PHONE_BUTTON, request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="+79991234567",
    )


# --- my bookings ----------------------------------------------------------


def my_bookings_kb(bookings: list[Booking], tz_name: str = "UTC") -> InlineKeyboardMarkup:
    tz = ZoneInfo(tz_name)
    rows: list[list[InlineKeyboardButton]] = []
    for b in bookings:
        start = from_utc(b.start_at_utc, tz)
        label = (
            f"{b.service_emoji_snapshot} {b.service_name_snapshot} · "
            f"{start.strftime('%d.%m %H:%M')}"
        )
        rows.append([InlineKeyboardButton(
            text=label,
            callback_data=f"{CB_VIEW}:{b.id}",
        )])
    rows.append([
        InlineKeyboardButton(text=texts.MENU_NEW_BOOKING, callback_data=f"{CB_NEW}:0"),
        InlineKeyboardButton(text=texts.NAV_TO_MAIN, callback_data=f"{CB_MAIN_MENU}:0"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def booking_details_kb(booking_id: int, can_cancel: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if can_cancel:
        rows.append([InlineKeyboardButton(text="✖️ Отменить запись", callback_data=f"{CB_CANCEL_ASK}:{booking_id}")])
    rows.append([
        InlineKeyboardButton(text=texts.NAV_BACK, callback_data=f"{CB_MY}:0"),
        InlineKeyboardButton(text=texts.NAV_TO_MAIN, callback_data=f"{CB_MAIN_MENU}:0"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cancel_confirm_kb(booking_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=texts.CANCEL_YES, callback_data=f"{CB_CANCEL_YES}:{booking_id}"),
        InlineKeyboardButton(text=texts.CANCEL_NO, callback_data=f"{CB_VIEW}:{booking_id}"),
    ]])


# --- admin -----------------------------------------------------------------


def admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts.ADMIN_STATS, callback_data=f"{CB_ADMIN_STATS}:0")],
        [
            InlineKeyboardButton(text=texts.ADMIN_TODAY, callback_data=f"{CB_ADMIN_TODAY}:0"),
            InlineKeyboardButton(text=texts.ADMIN_UPCOMING, callback_data=f"{CB_ADMIN_UPCOMING}:1"),
        ],
        [InlineKeyboardButton(text=texts.ADMIN_EXPORT_CSV, callback_data=f"{CB_ADMIN_EXPORT}:0")],
        [InlineKeyboardButton(text=texts.NAV_TO_MAIN, callback_data=f"{CB_MAIN_MENU}:0")],
    ])


def admin_back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=texts.ADMIN_BACK, callback_data=f"{CB_ADMIN}:0"),
    ]])


def admin_upcoming_kb(page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Pagination nav (◀ / page-marker / ▶) + back-to-admin row."""
    nav: list[InlineKeyboardButton] = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="◀", callback_data=f"{CB_ADMIN_UPCOMING}:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data=f"{CB_NOOP}:0"))
    if page < total_pages:
        nav.append(InlineKeyboardButton(text="▶", callback_data=f"{CB_ADMIN_UPCOMING}:{page + 1}"))
    return InlineKeyboardMarkup(inline_keyboard=[
        nav,
        [InlineKeyboardButton(text=texts.ADMIN_BACK, callback_data=f"{CB_ADMIN}:0")],
    ])
