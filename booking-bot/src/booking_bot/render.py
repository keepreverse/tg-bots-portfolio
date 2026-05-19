"""Edit-in-place screen rendering helpers.

Lifted from `lead-bot/render.py`. Every screen returns a `(text, kb)` pair
from `views.py`; this module knows how to deliver it.

Design:
- Each user has a single "main message" — the bot keeps editing it in place
  as the user navigates between screens. Its `message_id` is stored in FSM
  state under `MAIN_MSG_KEY`.
- If editing fails (e.g. the user deleted the message), we send a fresh one
  and update the saved id.
- `PHONE_AUX_MSG_KEY` tracks a tiny auxiliary message that hosts the
  request-contact reply keyboard, so it can be cleaned up later.
"""

from __future__ import annotations

import logging
from contextlib import suppress

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardRemove,
)

log = logging.getLogger(__name__)

MAIN_MSG_KEY = "main_msg_id"
PHONE_AUX_MSG_KEY = "phone_aux_msg_id"


async def render(
    bot: Bot,
    chat_id: int,
    state: FSMContext,
    text: str,
    kb: InlineKeyboardMarkup | None = None,
) -> int:
    """Edit the main message in place; fall back to sending a new one.

    Returns the message_id of the rendered main message.
    """
    data = await state.get_data()
    msg_id = data.get(MAIN_MSG_KEY)
    if msg_id is not None:
        try:
            await bot.edit_message_text(
                text=text,
                chat_id=chat_id,
                message_id=msg_id,
                reply_markup=kb,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            return msg_id
        except TelegramBadRequest as exc:
            if "message is not modified" in str(exc).lower():
                return msg_id
            log.info("edit_message_text failed (%s) — sending new message", exc)
        except Exception as exc:  # pragma: no cover — defensive
            log.warning("edit_message_text raised unexpected error: %s", exc)

    sent = await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=kb,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    await state.update_data({MAIN_MSG_KEY: sent.message_id})
    return sent.message_id


async def render_callback(
    cq: CallbackQuery,
    state: FSMContext,
    text: str,
    kb: InlineKeyboardMarkup | None = None,
) -> None:
    """Edit-in-place for callback queries — defers to `render()` then `cq.answer()`."""
    if cq.message is None:
        await cq.answer()
        return
    await render(cq.bot, cq.message.chat.id, state, text, kb)
    await cq.answer()


async def render_message(
    message: Message,
    state: FSMContext,
    text: str,
    kb: InlineKeyboardMarkup | None = None,
) -> None:
    """Edit-in-place response to a `Message` (e.g. after the user typed input).

    Also deletes the user's just-sent message so the chat stays tidy — exactly
    the trick that makes lead-bot's UX feel clean.
    """
    with suppress(TelegramBadRequest, Exception):
        await message.delete()
    await render(message.bot, message.chat.id, state, text, kb)


async def remove_phone_aux(bot: Bot, chat_id: int, state: FSMContext) -> None:
    """Delete the temporary phone-share reply keyboard message, if any."""
    data = await state.get_data()
    aux_id = data.get(PHONE_AUX_MSG_KEY)
    if aux_id is None:
        return
    with suppress(Exception):
        await bot.delete_message(chat_id=chat_id, message_id=aux_id)
    await state.update_data({PHONE_AUX_MSG_KEY: None})


async def clear_reply_keyboard(bot: Bot, chat_id: int) -> None:
    """Send-and-immediately-delete trick to drop a one-time reply keyboard.

    Telegram clients don't always auto-hide one-time keyboards; sending a
    `ReplyKeyboardRemove` and then deleting the helper message clears it
    without leaving chat clutter.
    """
    with suppress(Exception):
        ack = await bot.send_message(chat_id=chat_id, text="✓", reply_markup=ReplyKeyboardRemove())
        await bot.delete_message(chat_id=chat_id, message_id=ack.message_id)
