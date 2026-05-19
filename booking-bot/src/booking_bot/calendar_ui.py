"""Build a month-grid calendar keyboard with working-day cells active."""

from __future__ import annotations

import calendar
from collections.abc import Callable
from datetime import date, timedelta

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

_RU_MONTHS_NOMINATIVE = (
    "январь", "февраль", "март", "апрель", "май", "июнь",
    "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь",
)
_RU_WEEKDAYS_SHORT = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")


def build_calendar_keyboard(
    *,
    month_anchor: date,
    today: date,
    horizon_days: int,
    is_working_day: Callable[[date], bool],
    callback_factory: Callable[[date], str],
    nav_prev_callback: str,
    nav_next_callback: str,
    cancel_callback: str,
) -> tuple[str, InlineKeyboardMarkup]:
    """Return (title, keyboard) for the given month.

    Cells:
      - Off-month days / off days / past days / beyond-horizon days: blank-placeholder.
      - Working days within horizon: digit + tap → `callback_factory(d)`.
      - Bottom row: « prev month, today's month label, next month »
                    plus a final row with «🏠 В меню».
    """
    title = f"{_RU_MONTHS_NOMINATIVE[month_anchor.month - 1].capitalize()} {month_anchor.year}"
    horizon_last = today + timedelta(days=horizon_days - 1)

    cal = calendar.Calendar(firstweekday=0)
    weeks = list(cal.monthdatescalendar(month_anchor.year, month_anchor.month))

    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text=w, callback_data="noop") for w in _RU_WEEKDAYS_SHORT],
    ]

    for week in weeks:
        row: list[InlineKeyboardButton] = []
        for d in week:
            cell_text, cb = _cell(
                d=d,
                month=month_anchor.month,
                today=today,
                horizon_last=horizon_last,
                is_working_day=is_working_day,
                callback_factory=callback_factory,
            )
            row.append(InlineKeyboardButton(text=cell_text, callback_data=cb))
        rows.append(row)

    rows.append([
        InlineKeyboardButton(text="‹ Пред.", callback_data=nav_prev_callback),
        InlineKeyboardButton(text=" ", callback_data="noop"),
        InlineKeyboardButton(text="След. ›", callback_data=nav_next_callback),
    ])
    rows.append([InlineKeyboardButton(text="🏠 В меню", callback_data=cancel_callback)])

    return title, InlineKeyboardMarkup(inline_keyboard=rows)


def _cell(
    *,
    d: date,
    month: int,
    today: date,
    horizon_last: date,
    is_working_day: Callable[[date], bool],
    callback_factory: Callable[[date], str],
) -> tuple[str, str]:
    if d.month != month:
        return ("·", "noop")
    if d < today or d > horizon_last:
        return ("·", "noop")
    if not is_working_day(d):
        return ("·", "noop")
    label = f"{d.day}"
    if d == today:
        label = f"•{d.day}"
    return (label, callback_factory(d))


def shift_month(anchor: date, delta: int) -> date:
    """Return the first day of (anchor.month + delta)."""
    year = anchor.year
    month = anchor.month + delta
    while month < 1:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    return date(year, month, 1)
