"""Time-zone helpers: store everything in UTC, render in MASTER_TZ."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

UTC = ZoneInfo("UTC")


def to_utc(dt_local: datetime, tz: ZoneInfo) -> datetime:
    """Attach the local tz to a naive datetime (or convert aware one) and return UTC."""
    if dt_local.tzinfo is None:
        dt_local = dt_local.replace(tzinfo=tz)
    return dt_local.astimezone(UTC)


def from_utc(dt_utc: datetime, tz: ZoneInfo) -> datetime:
    """Convert a UTC datetime to the local tz."""
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=UTC)
    return dt_utc.astimezone(tz)


_RU_MONTHS_GENITIVE = (
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)

_RU_WEEKDAYS_SHORT = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")


def format_date_local(dt_local: datetime) -> str:
    """Format a local datetime as `«16 мая, Сб»`."""
    return f"{dt_local.day} {_RU_MONTHS_GENITIVE[dt_local.month - 1]}, {_RU_WEEKDAYS_SHORT[dt_local.weekday()]}"


def format_time_local(dt_local: datetime) -> str:
    """Format a local datetime as `«14:00»`."""
    return f"{dt_local.hour:02d}:{dt_local.minute:02d}"


def format_datetime_local(dt_local: datetime) -> str:
    """Format as `«16 мая, Сб · 14:00»`."""
    return f"{format_date_local(dt_local)} · {format_time_local(dt_local)}"
