"""/start, /menu, /cancel, main menu, services & help screens."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..config import Settings, get_settings
from ..db import ServicesRepo
from ..keyboards import CB_HELP, CB_MAIN_MENU, CB_NOOP, CB_SHOW_SERVICES
from ..render import (
    MAIN_MSG_KEY,
    PHONE_AUX_MSG_KEY,
    remove_phone_aux,
    render,
    render_callback,
)
from ..views import help_screen, main_menu, services_catalog


def is_admin(user_id: int | None, settings: Settings) -> bool:
    return user_id is not None and user_id == settings.ADMIN_CHAT_ID


async def _reset_to_main(message: Message | None, state: FSMContext, settings: Settings, user_id: int | None) -> None:
    """Shared reset: clear FSM but keep `main_msg_id` so we can edit-in-place."""
    data = await state.get_data()
    keep: dict[str, object] = {}
    if data.get(MAIN_MSG_KEY) is not None:
        keep[MAIN_MSG_KEY] = data[MAIN_MSG_KEY]
    aux_id = data.get(PHONE_AUX_MSG_KEY)
    await state.set_state(None)
    await state.set_data(keep)
    if message is not None and aux_id is not None:
        await remove_phone_aux(message.bot, message.chat.id, state)


def build_menu_router() -> Router:
    router = Router(name="menu")

    @router.message(CommandStart())
    async def on_start(msg: Message, state: FSMContext) -> None:
        s = get_settings()
        await _reset_to_main(msg, state, s, msg.from_user.id if msg.from_user else None)
        text, kb = main_menu(
            s.BUSINESS_NAME,
            is_admin=is_admin(msg.from_user.id if msg.from_user else None, s),
        )
        await render(msg.bot, msg.chat.id, state, text, kb)

    @router.message(Command("menu"))
    async def menu_cmd(msg: Message, state: FSMContext) -> None:
        s = get_settings()
        await _reset_to_main(msg, state, s, msg.from_user.id if msg.from_user else None)
        text, kb = main_menu(
            s.BUSINESS_NAME,
            is_admin=is_admin(msg.from_user.id if msg.from_user else None, s),
        )
        await render(msg.bot, msg.chat.id, state, text, kb)

    @router.message(Command("cancel"))
    async def cancel_cmd(msg: Message, state: FSMContext) -> None:
        s = get_settings()
        await _reset_to_main(msg, state, s, msg.from_user.id if msg.from_user else None)
        text, kb = main_menu(
            s.BUSINESS_NAME,
            is_admin=is_admin(msg.from_user.id if msg.from_user else None, s),
        )
        await render(msg.bot, msg.chat.id, state, text, kb)

    @router.callback_query(F.data == f"{CB_MAIN_MENU}:0")
    async def to_main(cq: CallbackQuery, state: FSMContext) -> None:
        s = get_settings()
        if cq.message is not None:
            await remove_phone_aux(cq.bot, cq.message.chat.id, state)
        # Preserve main_msg_id, drop the rest.
        data = await state.get_data()
        keep: dict[str, object] = {}
        if data.get(MAIN_MSG_KEY) is not None:
            keep[MAIN_MSG_KEY] = data[MAIN_MSG_KEY]
        await state.set_state(None)
        await state.set_data(keep)
        text, kb = main_menu(s.BUSINESS_NAME, is_admin=is_admin(cq.from_user.id, s))
        await render_callback(cq, state, text, kb)

    @router.callback_query(F.data == f"{CB_SHOW_SERVICES}:0")
    async def show_services(cq: CallbackQuery, state: FSMContext) -> None:
        s = get_settings()
        repo = ServicesRepo(s.db_path_abs)
        services = await repo.list_active()
        text, kb = services_catalog(services)
        await render_callback(cq, state, text, kb)

    @router.callback_query(F.data == f"{CB_HELP}:0")
    async def help_screen_cb(cq: CallbackQuery, state: FSMContext) -> None:
        s = get_settings()
        text, kb = help_screen(
            business_name=s.BUSINESS_NAME,
            address=s.BUSINESS_ADDRESS,
            master_handle=s.master_handle_username,
            master_url=s.master_telegram_url,
        )
        await render_callback(cq, state, text, kb)

    @router.callback_query(F.data == f"{CB_NOOP}:0")
    async def noop(cq: CallbackQuery) -> None:
        await cq.answer()

    return router
