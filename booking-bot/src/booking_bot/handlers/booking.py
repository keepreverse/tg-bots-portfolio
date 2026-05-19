"""Booking flow: category → service → date → time → name → phone → confirm.

Lead-bot UX:
- Single "main" message edited in place across steps (`render.MAIN_MSG_KEY`).
- Each prompt shows a progress bar + a filled-block of already-collected fields.
- ◀ Назад at every step pops the most-recently-collected field and goes back.
- ✕ Отмена abandons the flow and returns to main menu.
- Text inputs (name) are deleted after the bot consumes them.
- Phone is delivered via a one-time `request_contact` reply keyboard hosted in a
  small auxiliary message that gets cleaned up.
- URL/link guard on `name` & free-text `phone` (entity-based + regex).
"""

from __future__ import annotations

import re
from contextlib import suppress
from datetime import UTC, date, datetime, timedelta

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from .. import texts
from ..config import Settings, get_settings
from ..db import BookingsRepo, ServicesRepo, SlotConflict, WorkingHoursRepo
from ..keyboards import (
    CB_BOOK_BACK,
    CB_BOOK_CANCEL,
    CB_CAL_NEXT,
    CB_CAL_PREV,
    CB_CAT,
    CB_CONFIRM,
    CB_DATE,
    CB_NEW,
    CB_SERVICE,
    CB_TIME,
    phone_reply_kb,
)
from ..render import (
    MAIN_MSG_KEY,
    PHONE_AUX_MSG_KEY,
    clear_reply_keyboard,
    remove_phone_aux,
    render,
    render_callback,
)
from ..slots import available_starts
from ..states import BookingFlow
from ..timez import to_utc
from ..validators import message_contains_link
from ..views import (
    booking_ask_name,
    booking_ask_phone,
    booking_category,
    booking_confirm,
    booking_date_picker,
    booking_service_list,
    booking_summary,
    booking_time_picker,
    main_menu,
)

_PHONE_RX = re.compile(r"^\+?\d{10,15}$")


def _normalise_phone(raw: str) -> str | None:
    digits = re.sub(r"[^\d+]", "", raw)
    if _PHONE_RX.match(digits):
        return digits
    return None


def _is_admin(user_id: int | None, settings: Settings) -> bool:
    return user_id is not None and user_id == settings.ADMIN_CHAT_ID


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


def build_booking_router() -> Router:
    router = Router(name="booking")

    # ---- entry: «📅 Записаться» ------------------------------------------

    @router.callback_query(F.data == f"{CB_NEW}:0")
    async def start_booking(cq: CallbackQuery, state: FSMContext) -> None:
        await _start_booking_cb(cq, state)

    @router.message(Command("book"))
    async def book_cmd(msg: Message, state: FSMContext) -> None:
        await _reset_booking_state(state)
        await state.set_state(BookingFlow.pick_category)
        text, kb = booking_category()
        await render(msg.bot, msg.chat.id, state, text, kb)
        with suppress(Exception):
            await msg.delete()

    # ---- back/cancel within the booking FSM ------------------------------

    @router.callback_query(F.data == f"{CB_BOOK_CANCEL}:0")
    async def cancel_flow(cq: CallbackQuery, state: FSMContext) -> None:
        await _back_to_main(cq, state)

    @router.callback_query(F.data == f"{CB_BOOK_BACK}:0")
    async def back_step(cq: CallbackQuery, state: FSMContext) -> None:
        cur = await state.get_state()
        if cur == BookingFlow.pick_service.state:
            await _go_to_category(cq, state)
        elif cur == BookingFlow.pick_date.state:
            await _go_to_service_from_back(cq, state)
        elif cur == BookingFlow.pick_time.state:
            await _go_to_date(cq, state)
        elif cur == BookingFlow.ask_name.state:
            await _go_to_time(cq, state)
        elif cur == BookingFlow.ask_phone.state:
            await _go_to_name(cq, state)
        elif cur == BookingFlow.confirm.state:
            await _go_to_phone(cq, state)
        else:
            await _back_to_main(cq, state)

    # ---- category selection ---------------------------------------------

    @router.callback_query(F.data.startswith(f"{CB_CAT}:"))
    async def pick_category(cq: CallbackQuery, state: FSMContext) -> None:
        category = cq.data.split(":", 1)[1]
        if category not in ("tattoo", "piercing"):
            await cq.answer()
            return
        s = get_settings()
        services = await ServicesRepo(s.db_path_abs).list_by_category(category)
        await state.update_data(category=category)
        await state.set_state(BookingFlow.pick_service)
        text, kb = booking_service_list(category, services)
        await render_callback(cq, state, text, kb)

    # ---- service selection -----------------------------------------------

    @router.callback_query(F.data.startswith(f"{CB_SERVICE}:"))
    async def pick_service(cq: CallbackQuery, state: FSMContext) -> None:
        service_id = int(cq.data.split(":", 1)[1])
        s = get_settings()
        service = await ServicesRepo(s.db_path_abs).get_by_id(service_id)
        if service is None or not service.active:
            await cq.answer("Услуга не найдена.", show_alert=True)
            return
        await state.update_data(service_id=service.id)
        await state.set_state(BookingFlow.pick_date)
        today_local = datetime.now(s.master_tz).date()
        text, kb = await _build_date_picker(state, today_local)
        await render_callback(cq, state, text, kb)

    # ---- calendar navigation --------------------------------------------

    @router.callback_query(F.data.startswith(f"{CB_CAL_PREV}:"))
    @router.callback_query(F.data.startswith(f"{CB_CAL_NEXT}:"))
    async def nav_calendar(cq: CallbackQuery, state: FSMContext) -> None:
        prefix, payload = cq.data.split(":", 1)
        anchor = date.fromisoformat(payload)
        delta = -1 if prefix == CB_CAL_PREV else 1
        from ..calendar_ui import shift_month
        new_anchor = shift_month(anchor, delta)
        await state.update_data(month_anchor=new_anchor.isoformat())
        today_local = datetime.now(get_settings().master_tz).date()
        text, kb = await _build_date_picker(state, today_local, month_anchor=new_anchor)
        await render_callback(cq, state, text, kb)

    # ---- date selection (picks a date OR returns to date-picker) ---------

    @router.callback_query(F.data.startswith(f"{CB_DATE}:"))
    async def pick_date(cq: CallbackQuery, state: FSMContext) -> None:
        _, payload = cq.data.split(":", 1)
        if payload == "0":
            today_local = datetime.now(get_settings().master_tz).date()
            await state.set_state(BookingFlow.pick_date)
            text, kb = await _build_date_picker(state, today_local)
            await render_callback(cq, state, text, kb)
            return
        d = date.fromisoformat(payload)
        s = get_settings()
        working = await WorkingHoursRepo(s.db_path_abs).get_window_for_date(d)
        if working is None:
            await cq.answer(texts.DAY_OFF, show_alert=True)
            return

        data = await state.get_data()
        service = await ServicesRepo(s.db_path_abs).get_by_id(int(data["service_id"]))
        if service is None:
            await cq.answer()
            return

        existing = await BookingsRepo(s.db_path_abs, s.BOOKING_BUFFER_AFTER_MINUTES).list_confirmed_in_range(
            datetime(d.year, d.month, d.day, 0, 0, tzinfo=s.master_tz).astimezone(UTC),
            datetime(d.year, d.month, d.day, 23, 59, tzinfo=s.master_tz).astimezone(UTC) + timedelta(minutes=1),
        )
        slots = available_starts(
            date_local=d,
            working_window=working,
            slot_step_minutes=s.SLOT_STEP_MINUTES,
            service_duration_minutes=service.duration_minutes,
            buffer_after_minutes=s.BOOKING_BUFFER_AFTER_MINUTES,
            existing_bookings_utc=existing,
            master_tz=s.master_tz,
            now_utc=datetime.now(UTC),
        )
        await state.update_data(date_local=d.isoformat())
        await state.set_state(BookingFlow.pick_time)
        text, kb = booking_time_picker(
            category=str(data.get("category", "tattoo")),
            service=service,
            date_local=d,
            slots=slots,
        )
        await render_callback(cq, state, text, kb)

    # ---- time selection --------------------------------------------------

    @router.callback_query(F.data.startswith(f"{CB_TIME}:"))
    async def pick_time(cq: CallbackQuery, state: FSMContext) -> None:
        _, date_iso, hhmm = cq.data.split(":", 2)
        d = date.fromisoformat(date_iso)
        # Validate hhmm shape early.
        _ = (int(hhmm[:2]), int(hhmm[2:]))
        await state.update_data(date_local=d.isoformat(), time_local=hhmm)
        await state.set_state(BookingFlow.ask_name)
        await _show_name_step(cq, state)

    # ---- name input ------------------------------------------------------

    @router.message(BookingFlow.ask_name)
    async def receive_name(msg: Message, state: FSMContext) -> None:
        raw = (msg.text or "").strip()
        # Always delete the user's reply so the chat stays edit-in-place.
        with suppress(Exception):
            await msg.delete()
        if message_contains_link(raw, msg.entities):
            await _show_name_step_message(msg, state, error=texts.INVALID_NAME_LINK)
            return
        if len(raw) < 2:
            await _show_name_step_message(msg, state, error=texts.INVALID_NAME_SHORT)
            return
        if len(raw) > 100:
            await _show_name_step_message(msg, state, error=texts.INVALID_NAME_LONG)
            return
        await state.update_data(user_full_name=raw)
        await state.set_state(BookingFlow.ask_phone)
        await _show_phone_step_message(msg, state)

    # ---- phone input (text or contact) -----------------------------------

    @router.message(BookingFlow.ask_phone, F.contact)
    async def receive_contact(msg: Message, state: FSMContext) -> None:
        phone = msg.contact.phone_number if msg.contact else None
        with suppress(Exception):
            await msg.delete()
        await remove_phone_aux(msg.bot, msg.chat.id, state)
        await clear_reply_keyboard(msg.bot, msg.chat.id)
        if phone:
            await state.update_data(user_phone=phone)
        await state.set_state(BookingFlow.confirm)
        await _show_confirm_message(msg, state)

    @router.message(BookingFlow.ask_phone, F.text)
    async def receive_phone_text(msg: Message, state: FSMContext) -> None:
        raw = (msg.text or "").strip()
        with suppress(Exception):
            await msg.delete()
        if message_contains_link(raw, msg.entities):
            await _show_phone_step_message(msg, state, error=texts.INVALID_PHONE_LINK)
            return
        phone = _normalise_phone(raw)
        if phone is None:
            await _show_phone_step_message(msg, state, error=texts.INVALID_PHONE)
            return
        await state.update_data(user_phone=phone)
        await remove_phone_aux(msg.bot, msg.chat.id, state)
        await clear_reply_keyboard(msg.bot, msg.chat.id)
        await state.set_state(BookingFlow.confirm)
        await _show_confirm_message(msg, state)

    # ---- confirm ---------------------------------------------------------

    @router.callback_query(F.data == f"{CB_CONFIRM}:0")
    async def do_confirm(cq: CallbackQuery, state: FSMContext, bot: Bot) -> None:
        s = get_settings()
        data = await state.get_data()
        service = await ServicesRepo(s.db_path_abs).get_by_id(int(data["service_id"]))
        if service is None:
            await cq.answer()
            return
        d = date.fromisoformat(str(data["date_local"]))
        hhmm = str(data["time_local"])
        start_local = datetime(d.year, d.month, d.day, int(hhmm[:2]), int(hhmm[2:]), tzinfo=s.master_tz)
        end_local = start_local + timedelta(minutes=service.duration_minutes)
        start_utc = to_utc(start_local, s.master_tz)
        end_utc = to_utc(end_local, s.master_tz)

        repo = BookingsRepo(s.db_path_abs, s.BOOKING_BUFFER_AFTER_MINUTES)
        try:
            bid = await repo.create_with_overlap_check(
                user_tg_id=cq.from_user.id,
                user_full_name=str(data["user_full_name"]),
                user_phone=data.get("user_phone"),
                user_username=cq.from_user.username,
                service=service,
                start_at_utc=start_utc,
                end_at_utc=end_utc,
                now_utc=datetime.now(UTC),
            )
        except SlotConflict:
            await cq.answer(texts.CONFLICT_RACE, show_alert=True)
            existing = await repo.list_confirmed_in_range(
                datetime(d.year, d.month, d.day, 0, 0, tzinfo=s.master_tz).astimezone(UTC),
                datetime(d.year, d.month, d.day, 23, 59, tzinfo=s.master_tz).astimezone(UTC) + timedelta(minutes=1),
            )
            working = await WorkingHoursRepo(s.db_path_abs).get_window_for_date(d)
            slots = available_starts(
                date_local=d,
                working_window=working,
                slot_step_minutes=s.SLOT_STEP_MINUTES,
                service_duration_minutes=service.duration_minutes,
                buffer_after_minutes=s.BOOKING_BUFFER_AFTER_MINUTES,
                existing_bookings_utc=existing,
                master_tz=s.master_tz,
                now_utc=datetime.now(UTC),
            )
            await state.set_state(BookingFlow.pick_time)
            text, kb = booking_time_picker(
                category=str(data.get("category", "tattoo")),
                service=service,
                date_local=d,
                slots=slots,
            )
            await render_callback(cq, state, text, kb)
            return

        summary = booking_summary(
            service=service, start_at_local=start_local, end_at_local=end_local,
        )
        # Preserve main_msg_id for the next step, but drop FSM-collected data.
        cur_data = await state.get_data()
        keep: dict[str, object] = {}
        if cur_data.get(MAIN_MSG_KEY) is not None:
            keep[MAIN_MSG_KEY] = cur_data[MAIN_MSG_KEY]
        await state.set_state(None)
        await state.set_data(keep)

        done_text = texts.DONE_USER.format(
            summary=summary,
            address=s.BUSINESS_ADDRESS,
            master_url=s.master_telegram_url,
            master_handle=s.master_handle_username,
        )
        from ..keyboards import main_menu_kb
        await render_callback(
            cq,
            state,
            done_text,
            main_menu_kb(is_admin=_is_admin(cq.from_user.id, s)),
        )

        # Notify admin (best-effort).
        tg_link = (
            f"@{cq.from_user.username}" if cq.from_user.username else f"id:{cq.from_user.id}"
        )
        with suppress(Exception):
            await bot.send_message(
                s.ADMIN_CHAT_ID,
                texts.ADMIN_NEW_BOOKING.format(
                    id=bid,
                    summary=summary,
                    name=data["user_full_name"],
                    phone=data.get("user_phone") or "—",
                    tg_link=tg_link,
                ),
                parse_mode="HTML",
            )

    # ---- internal helpers ------------------------------------------------

    async def _start_booking_cb(cq: CallbackQuery, state: FSMContext) -> None:
        await _reset_booking_state(state)
        await state.set_state(BookingFlow.pick_category)
        text, kb = booking_category()
        await render_callback(cq, state, text, kb)

    async def _go_to_category(cq: CallbackQuery, state: FSMContext) -> None:
        data = await state.get_data()
        # Drop everything after category.
        for k in ("category", "service_id", "date_local", "time_local"):
            data.pop(k, None)
        await state.set_data(data)
        await state.set_state(BookingFlow.pick_category)
        text, kb = booking_category()
        await render_callback(cq, state, text, kb)

    async def _go_to_service_from_back(cq: CallbackQuery, state: FSMContext) -> None:
        data = await state.get_data()
        category = str(data.get("category", "tattoo"))
        for k in ("service_id", "date_local", "time_local"):
            data.pop(k, None)
        await state.set_data(data)
        await state.set_state(BookingFlow.pick_service)
        s = get_settings()
        services = await ServicesRepo(s.db_path_abs).list_by_category(category)
        text, kb = booking_service_list(category, services)
        await render_callback(cq, state, text, kb)

    async def _go_to_date(cq: CallbackQuery, state: FSMContext) -> None:
        data = await state.get_data()
        for k in ("date_local", "time_local"):
            data.pop(k, None)
        await state.set_data(data)
        await state.set_state(BookingFlow.pick_date)
        today_local = datetime.now(get_settings().master_tz).date()
        text, kb = await _build_date_picker(state, today_local)
        await render_callback(cq, state, text, kb)

    async def _go_to_time(cq: CallbackQuery, state: FSMContext) -> None:
        """User pressed ◀ from the name step — go back to time selection
        for the previously chosen date."""
        s = get_settings()
        data = await state.get_data()
        d = date.fromisoformat(str(data["date_local"]))
        service = await ServicesRepo(s.db_path_abs).get_by_id(int(data["service_id"]))
        assert service is not None
        working = await WorkingHoursRepo(s.db_path_abs).get_window_for_date(d)
        existing = await BookingsRepo(s.db_path_abs, s.BOOKING_BUFFER_AFTER_MINUTES).list_confirmed_in_range(
            datetime(d.year, d.month, d.day, 0, 0, tzinfo=s.master_tz).astimezone(UTC),
            datetime(d.year, d.month, d.day, 23, 59, tzinfo=s.master_tz).astimezone(UTC) + timedelta(minutes=1),
        )
        slots = available_starts(
            date_local=d,
            working_window=working,
            slot_step_minutes=s.SLOT_STEP_MINUTES,
            service_duration_minutes=service.duration_minutes,
            buffer_after_minutes=s.BOOKING_BUFFER_AFTER_MINUTES,
            existing_bookings_utc=existing,
            master_tz=s.master_tz,
            now_utc=datetime.now(UTC),
        )
        data.pop("time_local", None)
        await state.set_data(data)
        await state.set_state(BookingFlow.pick_time)
        text, kb = booking_time_picker(
            category=str(data.get("category", "tattoo")),
            service=service,
            date_local=d,
            slots=slots,
        )
        await render_callback(cq, state, text, kb)

    async def _go_to_name(cq: CallbackQuery, state: FSMContext) -> None:
        data = await state.get_data()
        data.pop("user_full_name", None)
        await state.set_data(data)
        await state.set_state(BookingFlow.ask_name)
        if cq.message is not None:
            await remove_phone_aux(cq.bot, cq.message.chat.id, state)
        await _show_name_step(cq, state)

    async def _go_to_phone(cq: CallbackQuery, state: FSMContext) -> None:
        data = await state.get_data()
        data.pop("user_phone", None)
        await state.set_data(data)
        await state.set_state(BookingFlow.ask_phone)
        await _show_phone_step(cq, state)

    async def _show_name_step(cq: CallbackQuery, state: FSMContext, *, error: str | None = None) -> None:
        text, kb = await _name_step_view(state, error=error)
        await render_callback(cq, state, text, kb)

    async def _show_name_step_message(msg: Message, state: FSMContext, *, error: str | None = None) -> None:
        text, kb = await _name_step_view(state, error=error)
        await render(msg.bot, msg.chat.id, state, text, kb)

    async def _name_step_view(state: FSMContext, *, error: str | None) -> tuple[str, object]:
        s = get_settings()
        data = await state.get_data()
        service = await ServicesRepo(s.db_path_abs).get_by_id(int(data["service_id"]))
        assert service is not None
        d = date.fromisoformat(str(data["date_local"]))
        text, kb = booking_ask_name(
            category=str(data.get("category", "tattoo")),
            service=service,
            date_local=d,
            time_hhmm=str(data["time_local"]),
        )
        if error:
            text = f"{error}\n\n{text}"
        return text, kb

    async def _show_phone_step(cq: CallbackQuery, state: FSMContext) -> None:
        text, kb = await _phone_step_view(state)
        await render_callback(cq, state, text, kb)
        # Emit reply keyboard for contact-sharing as a separate aux message.
        if cq.message is not None:
            await _emit_phone_aux(cq.bot, cq.message.chat.id, state)

    async def _show_phone_step_message(msg: Message, state: FSMContext, *, error: str | None = None) -> None:
        text, kb = await _phone_step_view(state, error=error)
        await render(msg.bot, msg.chat.id, state, text, kb)
        await _emit_phone_aux(msg.bot, msg.chat.id, state)

    async def _phone_step_view(state: FSMContext, *, error: str | None = None) -> tuple[str, object]:
        s = get_settings()
        data = await state.get_data()
        service = await ServicesRepo(s.db_path_abs).get_by_id(int(data["service_id"]))
        assert service is not None
        d = date.fromisoformat(str(data["date_local"]))
        text, kb = booking_ask_phone(
            category=str(data.get("category", "tattoo")),
            service=service,
            date_local=d,
            time_hhmm=str(data["time_local"]),
            user_full_name=str(data.get("user_full_name", "")),
        )
        if error:
            text = f"{error}\n\n{text}"
        return text, kb

    async def _emit_phone_aux(bot: Bot, chat_id: int, state: FSMContext) -> None:
        """(Re-)emit the small contact-share reply keyboard message."""
        data = await state.get_data()
        if data.get(PHONE_AUX_MSG_KEY) is not None:
            return
        with suppress(TelegramBadRequest):
            aux = await bot.send_message(chat_id, texts.PHONE_KB_HINT, reply_markup=phone_reply_kb())
            await state.update_data({PHONE_AUX_MSG_KEY: aux.message_id})

    async def _show_confirm_message(msg: Message, state: FSMContext) -> None:
        text, kb = await _confirm_view(state)
        await render(msg.bot, msg.chat.id, state, text, kb)

    async def _confirm_view(state: FSMContext) -> tuple[str, object]:
        s = get_settings()
        data = await state.get_data()
        service = await ServicesRepo(s.db_path_abs).get_by_id(int(data["service_id"]))
        assert service is not None
        d = date.fromisoformat(str(data["date_local"]))
        hhmm = str(data["time_local"])
        start_local = datetime(d.year, d.month, d.day, int(hhmm[:2]), int(hhmm[2:]), tzinfo=s.master_tz)
        end_local = start_local + timedelta(minutes=service.duration_minutes)
        text, kb = booking_confirm(
            service=service,
            start_at_local=start_local,
            end_at_local=end_local,
            user_full_name=str(data["user_full_name"]),
            user_phone=data.get("user_phone"),
        )
        return text, kb

    async def _back_to_main(cq: CallbackQuery, state: FSMContext) -> None:
        if cq.message is not None:
            await remove_phone_aux(cq.bot, cq.message.chat.id, state)
        await _reset_booking_state(state)
        s = get_settings()
        text, kb = main_menu(s.BUSINESS_NAME, is_admin=_is_admin(cq.from_user.id, s))
        await render_callback(cq, state, text, kb)

    async def _build_date_picker(
        state: FSMContext,
        today_local: date,
        month_anchor: date | None = None,
    ) -> tuple[str, object]:
        s = get_settings()
        data = await state.get_data()
        service = await ServicesRepo(s.db_path_abs).get_by_id(int(data["service_id"]))
        assert service is not None
        anchor = month_anchor or date(today_local.year, today_local.month, 1)
        wh_repo = WorkingHoursRepo(s.db_path_abs)

        cache: dict[date, bool] = {}

        async def is_wd_async(d: date) -> bool:
            if d in cache:
                return cache[d]
            cache[d] = (await wh_repo.get_window_for_date(d)) is not None
            return cache[d]

        from datetime import timedelta as _td
        for i in range(-7, 45):
            d = date(anchor.year, anchor.month, 1) + _td(days=i)
            await is_wd_async(d)

        return booking_date_picker(
            category=str(data.get("category", "tattoo")),
            service=service,
            month_anchor=anchor,
            today=today_local,
            horizon_days=s.BOOKING_HORIZON_DAYS,
            is_working_day=lambda d: cache.get(d, False),
        )

    async def _reset_booking_state(state: FSMContext) -> None:
        """Drop all booking-collected data, but preserve `main_msg_id`."""
        data = await state.get_data()
        keep: dict[str, object] = {}
        if data.get(MAIN_MSG_KEY) is not None:
            keep[MAIN_MSG_KEY] = data[MAIN_MSG_KEY]
        await state.set_state(None)
        await state.set_data(keep)

    return router
