"""Helpers for editing the bot's main per-user message in place.

The pattern: each user has a single 'main message' that the bot keeps editing
as the user navigates through screens. The message_id is stored in FSM state
under the key MAIN_MSG_KEY. If editing fails (e.g. user deleted it), we send
a new message and update the saved id.
"""

from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext

from .views import View

log = logging.getLogger(__name__)

MAIN_MSG_KEY = "main_msg_id"
PHONE_AUX_MSG_KEY = "phone_aux_msg_id"


async def render(
    bot: Bot,
    chat_id: int,
    state: FSMContext,
    view: View,
) -> int:
    """Edit the main message in place; fall back to sending a new one if needed.

    Returns the message_id of the rendered main message.
    """
    data = await state.get_data()
    msg_id = data.get(MAIN_MSG_KEY)
    if msg_id is not None:
        try:
            await bot.edit_message_text(
                text=view.text,
                chat_id=chat_id,
                message_id=msg_id,
                reply_markup=view.markup,
                parse_mode="HTML",
            )
            return msg_id
        except TelegramBadRequest as exc:
            # "message is not modified" is harmless — the screen already matches.
            if "message is not modified" in str(exc).lower():
                return msg_id
            log.info("edit_message_text failed (%s) — will send new message", exc)
        except Exception as exc:
            log.warning("edit_message_text raised unexpected error: %s", exc)

    sent = await bot.send_message(
        chat_id=chat_id,
        text=view.text,
        reply_markup=view.markup,
        parse_mode="HTML",
    )
    await state.update_data({MAIN_MSG_KEY: sent.message_id})
    return sent.message_id


async def remove_phone_aux(bot: Bot, chat_id: int, state: FSMContext) -> None:
    """Clean up the temporary phone-share reply keyboard message, if any."""
    data = await state.get_data()
    aux_id = data.get(PHONE_AUX_MSG_KEY)
    if aux_id is None:
        return
    try:
        await bot.delete_message(chat_id=chat_id, message_id=aux_id)
    except Exception as exc:
        log.info("delete phone aux msg failed: %s", exc)
    await state.update_data({PHONE_AUX_MSG_KEY: None})
