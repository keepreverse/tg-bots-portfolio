"""/start, /menu, /cancel, main menu, about screen + unknown-message fallback."""

from __future__ import annotations

from contextlib import suppress

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..config import Settings, get_settings
from ..keyboards import (
    CB_ABOUT,
    CB_MAIN_MENU,
    CB_NOOP,
    CB_START_QUIZ,
)
from ..quiz_engine import QuizConfig
from ..render import (
    MAIN_MSG_KEY,
    PHONE_AUX_MSG_KEY,
    remove_phone_aux,
    render,
    render_callback,
)
from ..views import about_view, category_picker_view, main_menu_view


def is_admin(user_id: int | None, settings: Settings) -> bool:
    return user_id is not None and user_id == settings.ADMIN_CHAT_ID


async def reset_to_main(message: Message | None, state: FSMContext, *, also_remove_aux: bool) -> None:
    """Clear FSM but keep `main_msg_id` so we can keep editing the same message."""
    data = await state.get_data()
    keep: dict[str, object] = {}
    if data.get(MAIN_MSG_KEY) is not None:
        keep[MAIN_MSG_KEY] = data[MAIN_MSG_KEY]
    aux_id = data.get(PHONE_AUX_MSG_KEY)
    await state.set_state(None)
    await state.set_data(keep)
    if also_remove_aux and message is not None and aux_id is not None:
        await remove_phone_aux(message.bot, message.chat.id, state)


def build_menu_router(*, config: QuizConfig) -> Router:
    router = Router(name="menu")

    async def _show_main_menu(msg: Message, state: FSMContext) -> None:
        s = get_settings()
        await reset_to_main(msg, state, also_remove_aux=True)
        view = main_menu_view(
            config=config,
            business_name=s.BUSINESS_NAME,
            is_admin=is_admin(msg.from_user.id if msg.from_user else None, s),
        )
        await render(msg.bot, msg.chat.id, state, view.text, view.markup)

    @router.message(CommandStart())
    async def on_start(msg: Message, state: FSMContext) -> None:
        await _show_main_menu(msg, state)

    @router.message(Command("menu"))
    async def on_menu_cmd(msg: Message, state: FSMContext) -> None:
        await _show_main_menu(msg, state)

    @router.message(Command("cancel"))
    async def on_cancel(msg: Message, state: FSMContext) -> None:
        await _show_main_menu(msg, state)

    @router.callback_query(F.data == f"{CB_MAIN_MENU}:0")
    async def to_main(cq: CallbackQuery, state: FSMContext) -> None:
        s = get_settings()
        if cq.message is not None:
            await remove_phone_aux(cq.bot, cq.message.chat.id, state)
        # Preserve main_msg_id, drop everything else.
        data = await state.get_data()
        keep: dict[str, object] = {}
        if data.get(MAIN_MSG_KEY) is not None:
            keep[MAIN_MSG_KEY] = data[MAIN_MSG_KEY]
        await state.set_state(None)
        await state.set_data(keep)
        view = main_menu_view(
            config=config,
            business_name=s.BUSINESS_NAME,
            is_admin=is_admin(cq.from_user.id, s),
        )
        await render_callback(cq, state, view.text, view.markup)

    @router.callback_query(F.data == f"{CB_START_QUIZ}:0")
    async def start_quiz_picker(cq: CallbackQuery, state: FSMContext) -> None:
        # Multi-category mode: show the picker.
        view = category_picker_view(config)
        await render_callback(cq, state, view.text, view.markup)

    @router.callback_query(F.data == f"{CB_ABOUT}:0")
    async def about(cq: CallbackQuery, state: FSMContext) -> None:
        s = get_settings()
        view = about_view(
            business_name=s.BUSINESS_NAME,
            master_handle=s.master_handle_username,
            master_url=s.master_telegram_url,
        )
        await render_callback(cq, state, view.text, view.markup)

    @router.callback_query(F.data == f"{CB_NOOP}:0")
    async def noop(cq: CallbackQuery) -> None:
        await cq.answer()

    return router


def build_fallback_router(*, config: QuizConfig) -> Router:
    """Catch-all for unrecognized messages — opens the main menu silently.

    Registered LAST in the dispatcher so other routers see their messages first.
    """
    router = Router(name="fallback")

    @router.message()
    async def unknown(msg: Message, state: FSMContext) -> None:
        # Delete user's stray message so the chat stays tidy.
        with suppress(Exception):
            await msg.delete()
        s = get_settings()
        await reset_to_main(msg, state, also_remove_aux=True)
        view = main_menu_view(
            config=config,
            business_name=s.BUSINESS_NAME,
            is_admin=is_admin(msg.from_user.id if msg.from_user else None, s),
        )
        await render(msg.bot, msg.chat.id, state, view.text, view.markup)

    return router
