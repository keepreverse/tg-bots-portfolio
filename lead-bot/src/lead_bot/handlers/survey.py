"""Survey FSM handlers: edit-in-place flow with back / cancel on every step."""

from __future__ import annotations

import logging
import re

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from .. import keyboards as kb
from .. import views
from ..config import Settings
from ..db import LeadsRepo
from ..render import (
    MAIN_MSG_KEY,
    PHONE_AUX_MSG_KEY,
    remove_phone_aux,
    render,
)
from ..states import Survey
from ..texts import (
    INVALID_NAME,
    INVALID_PHONE,
    PHONE_KB_HINT,
    admin_notification,
)

log = logging.getLogger(__name__)
router = Router(name="survey")

# Accept Russian/international phones with 10-15 digits, optional +, spaces, dashes, parens.
PHONE_RE = re.compile(r"^\+?[\d\s\-\(\)]{10,20}$")


def _normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return raw.strip()
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    if 10 <= len(digits) <= 15:
        return "+" + digits
    return raw.strip()


# --- helpers for stepping forward/back ------------------------------------

async def _go_to_name(bot: Bot, chat_id: int, state: FSMContext) -> None:
    await state.set_state(Survey.name)
    data = await state.get_data()
    await render(bot, chat_id, state, views.survey_name(data))


async def _go_to_phone(bot: Bot, chat_id: int, state: FSMContext) -> None:
    await state.set_state(Survey.phone)
    data = await state.get_data()
    await render(bot, chat_id, state, views.survey_phone(data))
    # Emit the request_contact reply keyboard as a small auxiliary message
    # (it's the only way to get a one-tap phone share in Telegram).
    await remove_phone_aux(bot, chat_id, state)
    aux = await bot.send_message(
        chat_id=chat_id,
        text=PHONE_KB_HINT,
        reply_markup=kb.phone_share_kb(),
    )
    await state.update_data({PHONE_AUX_MSG_KEY: aux.message_id})


async def _go_to_service(
    bot: Bot, chat_id: int, state: FSMContext, settings: Settings
) -> None:
    await state.set_state(Survey.service)
    await remove_phone_aux(bot, chat_id, state)
    data = await state.get_data()
    await render(bot, chat_id, state, views.survey_service(data, settings.services))


async def _go_to_comment(bot: Bot, chat_id: int, state: FSMContext) -> None:
    await state.set_state(Survey.comment)
    data = await state.get_data()
    await render(bot, chat_id, state, views.survey_comment(data))


async def _go_to_confirm(bot: Bot, chat_id: int, state: FSMContext) -> None:
    await state.set_state(Survey.confirm)
    data = await state.get_data()
    await render(bot, chat_id, state, views.survey_confirm(data))


async def _clear_reply_keyboard(bot: Bot, chat_id: int) -> None:
    """Send a tiny invisible-ish message with ReplyKeyboardRemove and delete it.

    This is the only way to clear a one-time reply keyboard if Telegram client
    didn't auto-hide it. The chat stays clean because we delete the helper
    message right after.
    """
    try:
        ack = await bot.send_message(chat_id=chat_id, text="✓", reply_markup=kb.remove_reply_kb())
        await bot.delete_message(chat_id=chat_id, message_id=ack.message_id)
    except Exception as exc:
        log.info("clear reply keyboard failed: %s", exc)


# --- start / restart / cancel ---------------------------------------------

@router.callback_query(F.data == "s:start")
async def cb_start_survey(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    if call.message is None:
        await call.answer()
        return
    data = await state.get_data()
    keep = {MAIN_MSG_KEY: data.get(MAIN_MSG_KEY) or call.message.message_id}
    await state.set_data(keep)
    await _go_to_name(bot, call.message.chat.id, state)
    await call.answer()


@router.callback_query(F.data == "s:restart")
async def cb_restart_survey(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    if call.message is None:
        await call.answer()
        return
    data = await state.get_data()
    keep = {MAIN_MSG_KEY: data.get(MAIN_MSG_KEY) or call.message.message_id}
    await state.set_data(keep)
    await _go_to_name(bot, call.message.chat.id, state)
    await call.answer("Начинаем заново")


@router.message(Command("survey"))
async def cmd_survey(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    keep = {MAIN_MSG_KEY: data.get(MAIN_MSG_KEY)} if data.get(MAIN_MSG_KEY) else {}
    await state.set_data(keep)
    await _go_to_name(bot, message.chat.id, state)


# --- back nav --------------------------------------------------------------

@router.callback_query(F.data == "s:back")
async def cb_back(
    call: CallbackQuery, state: FSMContext, settings: Settings, bot: Bot
) -> None:
    if call.message is None:
        await call.answer()
        return
    current = await state.get_state()
    chat_id = call.message.chat.id
    if current == Survey.phone.state:
        data = await state.get_data()
        data.pop("name", None)
        await state.set_data(data)
        await remove_phone_aux(bot, chat_id, state)
        await _go_to_name(bot, chat_id, state)
    elif current == Survey.service.state:
        data = await state.get_data()
        data.pop("phone", None)
        await state.set_data(data)
        await _go_to_phone(bot, chat_id, state)
    elif current == Survey.comment.state:
        data = await state.get_data()
        data.pop("service", None)
        data.pop("service_idx", None)
        await state.set_data(data)
        await _go_to_service(bot, chat_id, state, settings)
    elif current == Survey.confirm.state:
        data = await state.get_data()
        data.pop("comment", None)
        await state.set_data(data)
        await _go_to_comment(bot, chat_id, state)
    await call.answer()


@router.callback_query(F.data == "s:cancel")
async def cb_cancel(
    call: CallbackQuery, state: FSMContext, settings: Settings, bot: Bot
) -> None:
    if call.message is None:
        await call.answer()
        return
    chat_id = call.message.chat.id
    await remove_phone_aux(bot, chat_id, state)
    await _clear_reply_keyboard(bot, chat_id)
    await state.set_state(None)
    data = await state.get_data()
    keep = {MAIN_MSG_KEY: data.get(MAIN_MSG_KEY)} if data.get(MAIN_MSG_KEY) else {}
    await state.set_data(keep)
    is_admin = call.from_user is not None and call.from_user.id == settings.admin_chat_id
    await render(
        bot,
        chat_id,
        state,
        views.main_menu(business=settings.business_name, is_admin=is_admin),
    )
    await call.answer("Заявка отменена")


# --- step 1: name ----------------------------------------------------------

@router.message(Survey.name, F.text)
async def on_name(message: Message, state: FSMContext, bot: Bot) -> None:
    text = (message.text or "").strip()
    if len(text) < 2:
        data = await state.get_data()
        view = views.survey_name(data)
        await render(
            bot,
            message.chat.id,
            state,
            view._replace(text=view.text + f"\n\n⚠️ {INVALID_NAME}"),
        )
        return
    await state.update_data(name=text)
    await _go_to_phone(bot, message.chat.id, state)


# --- step 2: phone ---------------------------------------------------------

@router.message(Survey.phone, F.contact)
async def on_phone_contact(
    message: Message, state: FSMContext, settings: Settings, bot: Bot
) -> None:
    if not message.contact or not message.contact.phone_number:
        return
    phone = _normalize_phone(message.contact.phone_number)
    await state.update_data(phone=phone)
    await _clear_reply_keyboard(bot, message.chat.id)
    await _go_to_service(bot, message.chat.id, state, settings)


@router.message(Survey.phone, F.text)
async def on_phone_text(
    message: Message, state: FSMContext, settings: Settings, bot: Bot
) -> None:
    raw = (message.text or "").strip()
    if not PHONE_RE.match(raw):
        data = await state.get_data()
        view = views.survey_phone(data)
        await render(
            bot,
            message.chat.id,
            state,
            view._replace(text=view.text + f"\n\n⚠️ {INVALID_PHONE}"),
        )
        return
    phone = _normalize_phone(raw)
    await state.update_data(phone=phone)
    await _clear_reply_keyboard(bot, message.chat.id)
    await _go_to_service(bot, message.chat.id, state, settings)


# --- step 3: service -------------------------------------------------------

@router.callback_query(Survey.service, F.data.startswith("s:svc:"))
async def cb_service(
    call: CallbackQuery, state: FSMContext, settings: Settings, bot: Bot
) -> None:
    if call.message is None or call.data is None:
        await call.answer()
        return
    try:
        idx = int(call.data.split(":")[-1])
    except ValueError:
        await call.answer("Неизвестная услуга", show_alert=True)
        return
    if idx < 0 or idx >= len(settings.services):
        await call.answer("Услуга не найдена", show_alert=True)
        return
    await state.update_data(service=settings.services[idx], service_idx=idx)
    await _go_to_comment(bot, call.message.chat.id, state)
    await call.answer()


# --- step 4: comment -------------------------------------------------------

@router.message(Survey.comment, F.text)
async def on_comment(message: Message, state: FSMContext, bot: Bot) -> None:
    text = (message.text or "").strip()
    comment = None if text in {"-", "—"} or not text else text
    await state.update_data(comment=comment)
    await _go_to_confirm(bot, message.chat.id, state)


@router.callback_query(Survey.comment, F.data == "s:skip")
async def cb_skip_comment(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    if call.message is None:
        await call.answer()
        return
    await state.update_data(comment=None)
    await _go_to_confirm(bot, call.message.chat.id, state)
    await call.answer("Без комментария")


# --- step 5: confirm -------------------------------------------------------

@router.callback_query(Survey.confirm, F.data == "s:confirm")
async def cb_confirm(
    call: CallbackQuery,
    state: FSMContext,
    settings: Settings,
    repo: LeadsRepo,
    bot: Bot,
) -> None:
    if call.message is None or call.from_user is None:
        await call.answer()
        return
    data = await state.get_data()
    name = data.get("name")
    phone = data.get("phone")
    service = data.get("service")
    comment = data.get("comment")
    if not name or not phone or not service:
        await call.answer("Не все поля заполнены", show_alert=True)
        return
    lead_id = await repo.add(
        tg_user_id=call.from_user.id,
        tg_username=call.from_user.username,
        name=name,
        phone=phone,
        service=service,
        comment=comment,
    )
    # Render success screen first so the user sees confirmation immediately.
    keep = {MAIN_MSG_KEY: data.get(MAIN_MSG_KEY)} if data.get(MAIN_MSG_KEY) else {}
    await state.set_state(None)
    await state.set_data(keep)
    await render(bot, call.message.chat.id, state, views.survey_done(lead_id=lead_id))
    await call.answer("Заявка отправлена")
    # Notify admin (separate message — not the main per-user message).
    try:
        await bot.send_message(
            chat_id=settings.admin_chat_id,
            text=admin_notification(
                lead_id=lead_id,
                name=name,
                phone=phone,
                service=service,
                comment=comment,
                tg_user_id=call.from_user.id,
                tg_username=call.from_user.username,
            ),
            parse_mode="HTML",
            reply_markup=kb.admin_lead_contact_kb(
                username=call.from_user.username,
                user_id=call.from_user.id,
            ),
        )
    except Exception as exc:
        log.warning("admin notification failed: %s", exc)
