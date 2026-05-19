"""My-bookings list and cancellation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from .. import texts
from ..config import get_settings
from ..db import BookingsRepo
from ..keyboards import (
    CB_CANCEL_ASK,
    CB_CANCEL_NO,
    CB_CANCEL_YES,
    CB_MY,
    CB_VIEW,
    back_to_main_kb,
    cancel_confirm_kb,
)
from ..render import render, render_callback
from ..views import booking_details_screen, my_bookings_screen


def build_my_bookings_router() -> Router:
    router = Router(name="my_bookings")

    @router.callback_query(F.data == f"{CB_MY}:0")
    async def list_my(cq: CallbackQuery, state: FSMContext) -> None:
        s = get_settings()
        repo = BookingsRepo(s.db_path_abs, s.BOOKING_BUFFER_AFTER_MINUTES)
        bookings = await repo.list_for_user(cq.from_user.id)
        text, kb = my_bookings_screen(bookings, s.MASTER_TZ)
        await render_callback(cq, state, text, kb)

    @router.message(Command("my"))
    async def list_my_cmd(msg: Message, state: FSMContext) -> None:
        s = get_settings()
        repo = BookingsRepo(s.db_path_abs, s.BOOKING_BUFFER_AFTER_MINUTES)
        bookings = await repo.list_for_user(msg.from_user.id) if msg.from_user else []
        text, kb = my_bookings_screen(bookings, s.MASTER_TZ)
        await render(msg.bot, msg.chat.id, state, text, kb)

    @router.callback_query(F.data.startswith(f"{CB_VIEW}:"))
    async def view_booking(cq: CallbackQuery, state: FSMContext) -> None:
        bid = int(cq.data.split(":", 1)[1])
        s = get_settings()
        repo = BookingsRepo(s.db_path_abs, s.BOOKING_BUFFER_AFTER_MINUTES)
        b = await repo.get_by_id(bid)
        if b is None or b.user_tg_id != cq.from_user.id:
            await cq.answer("Запись не найдена.", show_alert=True)
            return
        now = datetime.now(UTC)
        can_cancel = b.status == "confirmed" and b.start_at_utc - now > timedelta(hours=2)
        text, kb = booking_details_screen(b, s.MASTER_TZ, can_cancel, address=s.BUSINESS_ADDRESS)
        await render_callback(cq, state, text, kb)

    @router.callback_query(F.data.startswith(f"{CB_CANCEL_ASK}:"))
    async def ask_cancel(cq: CallbackQuery, state: FSMContext) -> None:
        bid = int(cq.data.split(":", 1)[1])
        s = get_settings()
        repo = BookingsRepo(s.db_path_abs, s.BOOKING_BUFFER_AFTER_MINUTES)
        b = await repo.get_by_id(bid)
        if b is None or b.user_tg_id != cq.from_user.id:
            await cq.answer("Запись не найдена.", show_alert=True)
            return
        await render_callback(
            cq, state, texts.CANCEL_CONFIRM, cancel_confirm_kb(b.id)
        )

    @router.callback_query(F.data.startswith(f"{CB_CANCEL_NO}:"))
    async def cancel_no(cq: CallbackQuery, state: FSMContext) -> None:
        bid = int(cq.data.split(":", 1)[1])
        s = get_settings()
        repo = BookingsRepo(s.db_path_abs, s.BOOKING_BUFFER_AFTER_MINUTES)
        b = await repo.get_by_id(bid)
        if b is None:
            await cq.answer("Запись не найдена.", show_alert=True)
            return
        now = datetime.now(UTC)
        can_cancel = b.status == "confirmed" and b.start_at_utc - now > timedelta(hours=2)
        text, kb = booking_details_screen(b, s.MASTER_TZ, can_cancel, address=s.BUSINESS_ADDRESS)
        await render_callback(cq, state, text, kb)

    @router.callback_query(F.data.startswith(f"{CB_CANCEL_YES}:"))
    async def do_cancel(cq: CallbackQuery, state: FSMContext) -> None:
        bid = int(cq.data.split(":", 1)[1])
        s = get_settings()
        repo = BookingsRepo(s.db_path_abs, s.BOOKING_BUFFER_AFTER_MINUTES)
        b = await repo.get_by_id(bid)
        if b is None or b.user_tg_id != cq.from_user.id:
            await cq.answer("Запись не найдена.", show_alert=True)
            return
        now = datetime.now(UTC)
        if b.status != "confirmed" or b.start_at_utc - now <= timedelta(hours=2):
            await render_callback(
                cq,
                state,
                texts.CANCEL_LATE.format(
                    master_handle=s.master_handle_username,
                    master_url=s.master_telegram_url,
                ),
                back_to_main_kb(),
            )
            return
        ok = await repo.cancel(b.id)
        if not ok:
            await cq.answer("Не удалось отменить запись.", show_alert=True)
            return
        await render_callback(
            cq, state, texts.CANCEL_DONE, back_to_main_kb()
        )

    return router
