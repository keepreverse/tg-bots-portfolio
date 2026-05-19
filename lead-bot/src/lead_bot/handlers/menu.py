"""Main menu handlers: /start command and navigation between menu screens."""

from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from .. import views
from ..config import Settings
from ..render import MAIN_MSG_KEY, remove_phone_aux, render

router = Router(name="menu")


def _is_admin(user_id: int | None, settings: Settings) -> bool:
    return user_id is not None and user_id == settings.admin_chat_id


async def _open_main_menu(
    bot: Bot,
    chat_id: int,
    user_id: int | None,
    state: FSMContext,
    settings: Settings,
) -> None:
    await remove_phone_aux(bot, chat_id, state)
    await state.set_state(None)
    # Preserve main_msg_id, drop survey data so the menu starts fresh.
    data = await state.get_data()
    keep = {MAIN_MSG_KEY: data.get(MAIN_MSG_KEY)} if data.get(MAIN_MSG_KEY) else {}
    await state.set_data(keep)
    view = views.main_menu(business=settings.business_name, is_admin=_is_admin(user_id, settings))
    await render(bot, chat_id, state, view)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, settings: Settings, bot: Bot) -> None:
    # On /start we want a brand new main message — don't try to reuse a stale one.
    await state.set_data({})
    await _open_main_menu(
        bot=bot,
        chat_id=message.chat.id,
        user_id=message.from_user.id if message.from_user else None,
        state=state,
        settings=settings,
    )


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext, settings: Settings, bot: Bot) -> None:
    await _open_main_menu(
        bot=bot,
        chat_id=message.chat.id,
        user_id=message.from_user.id if message.from_user else None,
        state=state,
        settings=settings,
    )


@router.callback_query(F.data == "m:open")
async def cb_open_menu(call: CallbackQuery, state: FSMContext, settings: Settings, bot: Bot) -> None:
    if call.message is None:
        await call.answer()
        return
    await _open_main_menu(
        bot=bot,
        chat_id=call.message.chat.id,
        user_id=call.from_user.id if call.from_user else None,
        state=state,
        settings=settings,
    )
    await call.answer()


@router.callback_query(F.data == "m:about")
async def cb_about(call: CallbackQuery, state: FSMContext, settings: Settings, bot: Bot) -> None:
    if call.message is None:
        await call.answer()
        return
    view = views.about(business=settings.business_name)
    await render(bot, call.message.chat.id, state, view)
    await call.answer()


@router.callback_query(F.data == "m:services")
async def cb_services(call: CallbackQuery, state: FSMContext, settings: Settings, bot: Bot) -> None:
    if call.message is None:
        await call.answer()
        return
    view = views.services(business=settings.business_name, services_list=settings.services)
    await render(bot, call.message.chat.id, state, view)
    await call.answer()


@router.callback_query(F.data == "m:help")
async def cb_help(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    if call.message is None:
        await call.answer()
        return
    view = views.help_screen()
    await render(bot, call.message.chat.id, state, view)
    await call.answer()


@router.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext, bot: Bot) -> None:
    await render(bot, message.chat.id, state, views.help_screen())


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext, settings: Settings, bot: Bot) -> None:
    await _open_main_menu(
        bot=bot,
        chat_id=message.chat.id,
        user_id=message.from_user.id if message.from_user else None,
        state=state,
        settings=settings,
    )
