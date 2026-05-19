"""Admin panel: stats, today, upcoming (paginated), CSV export."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from io import BytesIO

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from .. import texts
from ..config import Settings, get_settings
from ..db import BookingsRepo, bookings_to_csv
from ..keyboards import (
    CB_ADMIN,
    CB_ADMIN_EXPORT,
    CB_ADMIN_STATS,
    CB_ADMIN_TODAY,
    CB_ADMIN_UPCOMING,
    admin_back_kb,
)
from ..money import format_price
from ..render import render, render_callback
from ..timez import format_datetime_local, from_utc
from ..views import admin_menu, admin_upcoming_screen


def _is_admin(user_id: int | None, settings: Settings) -> bool:
    return user_id is not None and user_id == settings.ADMIN_CHAT_ID


def _records_word(n: int) -> str:
    """Russian pluralization for 'запись': 1 запись, 2 записи, 5 записей."""
    n_abs = abs(n) % 100
    if 11 <= n_abs <= 14:
        return "записей"
    last = n_abs % 10
    if last == 1:
        return "запись"
    if 2 <= last <= 4:
        return "записи"
    return "записей"


def build_admin_router() -> Router:
    router = Router(name="admin")

    @router.message(Command("admin"))
    async def admin_cmd(msg: Message, state: FSMContext) -> None:
        s = get_settings()
        if not _is_admin(msg.from_user.id if msg.from_user else None, s):
            await msg.answer("Нет прав на админ-панель.")
            return
        text, kb = admin_menu()
        await render(msg.bot, msg.chat.id, state, text, kb)

    @router.callback_query(F.data == f"{CB_ADMIN}:0")
    async def admin_main(cq: CallbackQuery, state: FSMContext) -> None:
        s = get_settings()
        if not _is_admin(cq.from_user.id, s):
            await cq.answer("Нет прав.", show_alert=True)
            return
        text, kb = admin_menu()
        await render_callback(cq, state, text, kb)

    @router.callback_query(F.data == f"{CB_ADMIN_STATS}:0")
    async def admin_stats(cq: CallbackQuery, state: FSMContext) -> None:
        s = get_settings()
        if not _is_admin(cq.from_user.id, s):
            await cq.answer("Нет прав.", show_alert=True)
            return
        repo = BookingsRepo(s.db_path_abs, s.BOOKING_BUFFER_AFTER_MINUTES)
        stats = await repo.stats()
        text = texts.STATS_TPL.format(
            confirmed_upcoming=stats["confirmed_upcoming"],
            completed_total=stats["completed_total"],
            cancelled_total=stats["cancelled_total"],
            no_show_total=stats["no_show_total"],
            revenue=format_price(stats["revenue_completed_rub"]),
        )
        await render_callback(cq, state, text, admin_back_kb())

    @router.callback_query(F.data == f"{CB_ADMIN_TODAY}:0")
    async def admin_today(cq: CallbackQuery, state: FSMContext) -> None:
        s = get_settings()
        if not _is_admin(cq.from_user.id, s):
            await cq.answer("Нет прав.", show_alert=True)
            return
        repo = BookingsRepo(s.db_path_abs, s.BOOKING_BUFFER_AFTER_MINUTES)
        today_local = datetime.now(s.master_tz).date()
        start_utc = datetime(today_local.year, today_local.month, today_local.day, 0, 0, tzinfo=s.master_tz).astimezone(UTC)
        end_utc = start_utc + timedelta(days=1)
        ranges = await repo.list_confirmed_in_range(start_utc, end_utc)
        if not ranges:
            await render_callback(cq, state, texts.ADMIN_TODAY_EMPTY, admin_back_kb())
            return
        lines: list[str] = ["<b>📆 Сегодня</b>", ""]
        for start, end in ranges:
            lines.append(
                f"🕒 {from_utc(start, s.master_tz).strftime('%H:%M')}–"
                f"{from_utc(end, s.master_tz).strftime('%H:%M')}"
            )
        await render_callback(cq, state, "\n".join(lines), admin_back_kb())

    @router.callback_query(F.data.startswith(f"{CB_ADMIN_UPCOMING}:"))
    async def admin_upcoming(cq: CallbackQuery, state: FSMContext) -> None:
        s = get_settings()
        if not _is_admin(cq.from_user.id, s):
            await cq.answer("Нет прав.", show_alert=True)
            return
        try:
            page = max(1, int(cq.data.split(":", 1)[1]))
        except (ValueError, IndexError):
            page = 1
        repo = BookingsRepo(s.db_path_abs, s.BOOKING_BUFFER_AFTER_MINUTES)
        # All upcoming confirmed, sorted ascending by start_at_utc.
        now_utc = datetime.now(UTC)
        far_future = now_utc + timedelta(days=400)
        ranges = await repo.list_confirmed_in_range(now_utc, far_future)
        # We need full Booking records for the cards.
        all_bookings, _ = await repo.list_admin(limit=1000, offset=0)
        upcoming = sorted(
            (b for b in all_bookings if b.status == "confirmed" and b.start_at_utc > now_utc),
            key=lambda b: b.start_at_utc,
        )
        _ = ranges  # kept for parity with list_confirmed_in_range filter semantics
        text, kb = admin_upcoming_screen(
            bookings=upcoming,
            page=page,
            tz_name=s.MASTER_TZ,
        )
        await render_callback(cq, state, text, kb)

    @router.callback_query(F.data == f"{CB_ADMIN_EXPORT}:0")
    async def admin_export(cq: CallbackQuery) -> None:
        s = get_settings()
        if not _is_admin(cq.from_user.id, s) or cq.message is None:
            await cq.answer("Нет прав.", show_alert=True)
            return
        repo = BookingsRepo(s.db_path_abs, s.BOOKING_BUFFER_AFTER_MINUTES)
        all_bookings, _total = await repo.list_admin(limit=10_000, offset=0)
        csv_text = bookings_to_csv(all_bookings, s.MASTER_TZ)
        file = BufferedInputFile(
            BytesIO(("\ufeff" + csv_text).encode("utf-8")).getvalue(),
            filename=f"bookings_{datetime.now(s.master_tz).strftime('%Y%m%d_%H%M')}.csv",
        )
        n = len(all_bookings)
        caption = f"📥 Экспорт: {n} {_records_word(n)}"
        await cq.message.answer_document(file, caption=caption)
        await cq.answer()

    return router


# Helper kept for parity with the previous module API even though it isn't
# used by the router anymore.
def format_admin_booking_line(b, tz) -> str:
    start = from_utc(b.start_at_utc, tz)
    return (
        f"#{b.id} · {b.service_emoji_snapshot} {b.service_name_snapshot}\n"
        f"   👤 {b.user_full_name} ({b.user_phone or '—'})\n"
        f"   🗓 {format_datetime_local(start)}"
    )
