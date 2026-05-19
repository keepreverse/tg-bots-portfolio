"""High-level screen builders: (text, keyboard) pairs.

Pure (no I/O, no aiogram side effects) so they can be unit-tested.
The handlers in `handlers/*` call these, then hand the result to `render.py`.
"""

from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from . import texts
from .calendar_ui import build_calendar_keyboard
from .db import Booking, Service
from .duration import format_duration
from .keyboards import (
    CB_CAL_NEXT,
    CB_CAL_PREV,
    CB_MAIN_MENU,
    TOTAL_STEPS,
    admin_menu_kb,
    admin_upcoming_kb,
    booking_details_kb,
    confirm_kb,
    main_menu_kb,
    my_bookings_kb,
    services_list_kb,
    text_step_kb,
    time_grid_kb,
)
from .money import format_price
from .timez import format_date_local, format_datetime_local, from_utc

# Total pages for paginated admin upcoming view.
ADMIN_UPCOMING_PAGE_SIZE = 5


# ---------------------------------------------------------------------------
# Booking progress + filled-block helpers
# ---------------------------------------------------------------------------


def _progress_bar(step: int) -> str:
    """`▰▰▱▱▱▱ · Шаг N из 6` (header for every booking step)."""
    filled = "▰" * step
    empty = "▱" * max(0, TOTAL_STEPS - step)
    return f"{filled}{empty} · Шаг {step} из {TOTAL_STEPS}"


def _filled_block(
    *,
    service: Service | None = None,
    date_local: date | None = None,
    time_hhmm: str | None = None,
    user_full_name: str | None = None,
    user_phone: str | None = None,
) -> str:
    """Compact summary of fields already collected, shown above each prompt.

    Lines are emitted only for non-empty values. The category itself is
    redundant once the user picks a service (every screen's header already
    states the section), so it is intentionally omitted here.
    """
    lines: list[str] = []
    if service is not None:
        lines.append(f"• Услуга: <b>{service.emoji} {service.name}</b>")
    if date_local is not None:
        lines.append(f"• Дата: <b>{_ru_date_short(date_local)}</b>")
    if time_hhmm:
        lines.append(f"• Время: <b>{time_hhmm[:2]}:{time_hhmm[2:]}</b>")
    if user_full_name:
        lines.append(f"• Имя: <b>{user_full_name}</b>")
    if user_phone:
        lines.append(f"• Телефон: <b>{user_phone}</b>")
    if not lines:
        return ""
    return "\n".join(lines) + "\n\n"


# ---------------------------------------------------------------------------
# Static screens
# ---------------------------------------------------------------------------


def render_service_card(s: Service) -> str:
    """One service shown as a compact card line."""
    return f"{s.emoji} <b>{s.name}</b> — {format_duration(s.duration_minutes)} — {format_price(s.price_rub)}"


def main_menu(business_name: str, is_admin: bool = False) -> tuple[str, object]:
    return texts.WELCOME.format(business=business_name), main_menu_kb(is_admin=is_admin)


def admin_menu() -> tuple[str, object]:
    return texts.ADMIN_PANEL_TITLE, admin_menu_kb()


def help_screen(
    *,
    business_name: str,
    address: str,
    master_handle: str,
    master_url: str,
) -> tuple[str, object]:
    from .keyboards import back_to_main_kb
    text = texts.HELP_TEXT.format(
        business=business_name,
        address=address,
        master_handle=master_handle,
        master_url=master_url,
    )
    return text, back_to_main_kb()


def services_catalog(services: list[Service]) -> tuple[str, object]:
    tattoo = [s for s in services if s.category == "tattoo"]
    piercing = [s for s in services if s.category == "piercing"]
    lines: list[str] = ["<b>🎨 Тату</b>"]
    for s in tattoo:
        lines.append("· " + render_service_card(s))
    lines.append("")
    lines.append("<b>💉 Пирсинг</b>")
    for s in piercing:
        lines.append("· " + render_service_card(s))
    return "\n".join(lines), main_menu_kb()


# ---------------------------------------------------------------------------
# Booking FSM screens — each takes the partial state already collected so the
# header can show progress + filled-block.
# ---------------------------------------------------------------------------


def booking_category() -> tuple[str, object]:
    from .keyboards import category_kb
    text = f"{_progress_bar(1)}\n\n{texts.CHOOSE_CATEGORY}"
    return text, category_kb()


def booking_service_list(
    category: str,
    services: list[Service],
) -> tuple[str, object]:
    title = (
        texts.CHOOSE_SERVICE_TATTOO
        if category == "tattoo"
        else texts.CHOOSE_SERVICE_PIERCING
    )
    text = f"{_progress_bar(2)}\n\n{title}"
    return text, services_list_kb(services)


def booking_date_picker(
    *,
    category: str,
    service: Service,
    month_anchor: date,
    today: date,
    horizon_days: int,
    is_working_day,
) -> tuple[str, object]:
    title, kb = build_calendar_keyboard(
        month_anchor=month_anchor,
        today=today,
        horizon_days=horizon_days,
        is_working_day=is_working_day,
        callback_factory=lambda d: f"date:{d.isoformat()}",
        nav_prev_callback=f"{CB_CAL_PREV}:{month_anchor.isoformat()}",
        nav_next_callback=f"{CB_CAL_NEXT}:{month_anchor.isoformat()}",
        cancel_callback=f"{CB_MAIN_MENU}:0",
    )
    filled = _filled_block(service=service)
    text = (
        f"{_progress_bar(3)}\n\n"
        f"{filled}{texts.CHOOSE_DATE}\n\n"
        f"<b>{title}</b>"
    )
    return text, kb


def booking_time_picker(
    *,
    category: str,
    service: Service,
    date_local: date,
    slots: list[time],
) -> tuple[str, object]:
    filled = _filled_block(
        service=service,
        date_local=date_local,
    )
    if not slots:
        return f"{_progress_bar(4)}\n\n{filled}{texts.DAY_FULL}", main_menu_kb()
    date_human = _ru_date_short(date_local)
    body = texts.CHOOSE_TIME.format(date_human=date_human)
    text = f"{_progress_bar(4)}\n\n{filled}{body}"
    return text, time_grid_kb(date_local, slots)


def booking_ask_name(
    *,
    category: str,
    service: Service,
    date_local: date,
    time_hhmm: str,
) -> tuple[str, object]:
    filled = _filled_block(
        service=service,
        date_local=date_local,
        time_hhmm=time_hhmm,
    )
    text = f"{_progress_bar(5)}\n\n{filled}{texts.ASK_NAME}\n<i>{texts.ASK_NAME_HINT}</i>"
    return text, text_step_kb()


def booking_ask_phone(
    *,
    category: str,
    service: Service,
    date_local: date,
    time_hhmm: str,
    user_full_name: str,
) -> tuple[str, object]:
    filled = _filled_block(
        service=service,
        date_local=date_local,
        time_hhmm=time_hhmm,
        user_full_name=user_full_name,
    )
    text = f"{_progress_bar(6)}\n\n{filled}{texts.ASK_PHONE}"
    return text, text_step_kb()


def booking_confirm(
    *,
    service: Service,
    start_at_local: datetime,
    end_at_local: datetime,
    user_full_name: str,
    user_phone: str | None,
) -> tuple[str, object]:
    summary = booking_summary(
        service=service,
        start_at_local=start_at_local,
        end_at_local=end_at_local,
    )
    lines = [
        texts.CONFIRM_TITLE,
        "",
        summary,
        "",
        f"👤 Имя: <b>{user_full_name}</b>",
        f"📞 Телефон: {user_phone or '—'}",
    ]
    return "\n".join(lines), confirm_kb()


def booking_summary(
    *,
    service: Service,
    start_at_local: datetime,
    end_at_local: datetime,
) -> str:
    return (
        f"{service.emoji} <b>{service.name}</b>\n"
        f"🗓 {format_date_local(start_at_local)}\n"
        f"🕒 {start_at_local.strftime('%H:%M')} – {end_at_local.strftime('%H:%M')} "
        f"({format_duration(service.duration_minutes)})\n"
        f"💰 {format_price(service.price_rub)}"
    )


def booking_summary_text(
    *,
    emoji: str,
    name: str,
    duration_minutes: int,
    price_rub: int,
    start_at_local: datetime,
    end_at_local: datetime,
) -> str:
    return (
        f"{emoji} <b>{name}</b>\n"
        f"🗓 {format_date_local(start_at_local)}\n"
        f"🕒 {start_at_local.strftime('%H:%M')} – {end_at_local.strftime('%H:%M')} "
        f"({format_duration(duration_minutes)})\n"
        f"💰 {format_price(price_rub)}"
    )


# ---------------------------------------------------------------------------
# My bookings + booking details + admin views
# ---------------------------------------------------------------------------


def my_bookings_screen(bookings: list[Booking], tz_name: str) -> tuple[str, object]:
    if not bookings:
        return texts.MY_BOOKINGS_EMPTY, main_menu_kb()
    tz = ZoneInfo(tz_name)
    lines: list[str] = [texts.MY_BOOKINGS_TITLE, ""]
    for b in bookings:
        start = from_utc(b.start_at_utc, tz)
        end = from_utc(b.end_at_utc, tz)
        status_human = _status_human(b.status)
        lines.append(
            f"{b.service_emoji_snapshot} <b>{b.service_name_snapshot}</b>\n"
            f"🗓 {format_date_local(start)} · "
            f"🕒 {start.strftime('%H:%M')}–{end.strftime('%H:%M')}\n"
            f"{status_human}"
        )
        lines.append("")
    if lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines), my_bookings_kb(bookings, tz_name)


def booking_details_screen(
    b: Booking,
    tz_name: str,
    can_cancel: bool,
    *,
    address: str,
) -> tuple[str, object]:
    tz = ZoneInfo(tz_name)
    start = from_utc(b.start_at_utc, tz)
    end = from_utc(b.end_at_utc, tz)
    created = from_utc(b.created_at_utc, tz)
    summary = booking_summary_text(
        emoji=b.service_emoji_snapshot,
        name=b.service_name_snapshot,
        duration_minutes=b.service_duration_minutes_snapshot,
        price_rub=b.service_price_rub_snapshot,
        start_at_local=start,
        end_at_local=end,
    )
    body = texts.BOOKING_DETAILS.format(
        summary=summary,
        status=_status_human(b.status),
        created_local=format_datetime_local(created),
        address=address,
    )
    return body, booking_details_kb(b.id, can_cancel)


def admin_upcoming_screen(
    *,
    bookings: list[Booking],
    page: int,
    tz_name: str,
) -> tuple[str, object]:
    """Paginated `📋 Все ближайшие` view in the admin panel.

    `bookings` is the FULL list of upcoming confirmed bookings, sorted by
    start_at_utc ascending. This function slices to `ADMIN_UPCOMING_PAGE_SIZE`.
    """
    if not bookings:
        return texts.ADMIN_UPCOMING_EMPTY, _admin_back()
    total = len(bookings)
    total_pages = max(1, (total + ADMIN_UPCOMING_PAGE_SIZE - 1) // ADMIN_UPCOMING_PAGE_SIZE)
    page = max(1, min(page, total_pages))
    start_i = (page - 1) * ADMIN_UPCOMING_PAGE_SIZE
    chunk = bookings[start_i : start_i + ADMIN_UPCOMING_PAGE_SIZE]
    tz = ZoneInfo(tz_name)
    header = (
        f"{texts.ADMIN_UPCOMING_TITLE.format(page=page, total_pages=total_pages)}\n"
        f"<i>всего: {total}</i>"
    )
    parts: list[str] = [header]
    for b in chunk:
        start = from_utc(b.start_at_utc, tz)
        end = from_utc(b.end_at_utc, tz)
        tg_link = (
            f"@{b.user_username}" if b.user_username else f"id:{b.user_tg_id}"
        )
        parts.append(_admin_card(b, start, end, tg_link))
    return "\n\n".join(parts), admin_upcoming_kb(page, total_pages)


# Short divider that fits on one line on narrow mobile screens.
_ADMIN_CARD_DIVIDER = "─" * 12


def _admin_card(b: Booking, start: datetime, end: datetime, tg_link: str) -> str:
    """Booking rendered as a structured card. One field per line for readability."""
    return (
        f"{_ADMIN_CARD_DIVIDER}\n"
        f"<b>#{b.id}</b> · 🗓 <b>{format_date_local(start)}</b>\n"
        f"🕒 <b>{start.strftime('%H:%M')}–{end.strftime('%H:%M')}</b> "
        f"({format_duration(b.service_duration_minutes_snapshot)})\n"
        f"{b.service_emoji_snapshot} {b.service_name_snapshot} — "
        f"{format_price(b.service_price_rub_snapshot)}\n"
        f"👤 {b.user_full_name}\n"
        f"📞 {b.user_phone or '—'}\n"
        f"🆔 {tg_link}"
    )


# ---------------------------------------------------------------------------
# Local helpers
# ---------------------------------------------------------------------------


def _admin_back():
    from .keyboards import admin_back_kb
    return admin_back_kb()


def _cat_label(category: str) -> str:
    return texts.CAT_TATTOO if category == "tattoo" else texts.CAT_PIERCING


def _status_human(status: str) -> str:
    return {
        "confirmed": "✅ подтверждена",
        "cancelled": "❌ отменена",
        "completed": "🏁 завершена",
        "no_show": "🚫 не пришли",
    }.get(status, status)


def _ru_date_short(d: date) -> str:
    months = ("января", "февраля", "марта", "апреля", "мая", "июня",
              "июля", "августа", "сентября", "октября", "ноября", "декабря")
    weekdays = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")
    return f"{d.day} {months[d.month - 1]}, {weekdays[d.weekday()]}"
