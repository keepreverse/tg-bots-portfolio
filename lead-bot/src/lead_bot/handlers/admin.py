"""Admin panel handlers: edit-in-place dashboard with stats / export / recent / ping."""

from __future__ import annotations

import logging
import math
from datetime import UTC, datetime, timedelta

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from .. import views
from ..config import Settings
from ..db import LeadsRepo, leads_to_csv
from ..render import render
from ..texts import lead_short

log = logging.getLogger(__name__)
router = Router(name="admin")

RECENT_PAGE_SIZE = 5


# --- access control --------------------------------------------------------

def _is_admin_user(user_id: int | None, settings: Settings) -> bool:
    return user_id is not None and user_id == settings.admin_chat_id


def _is_admin_message(message: Message, settings: Settings) -> bool:
    return message.from_user is not None and _is_admin_user(message.from_user.id, settings)


def _is_admin_call(call: CallbackQuery, settings: Settings) -> bool:
    return _is_admin_user(call.from_user.id if call.from_user else None, settings)


# --- dashboard rendering ---------------------------------------------------

async def _render_panel(
    bot: Bot,
    chat_id: int,
    state: FSMContext,
    settings: Settings,
    repo: LeadsRepo,
) -> None:
    total = await repo.count()
    week_ago = (datetime.now(UTC) - timedelta(days=7)).isoformat(timespec="seconds")
    last_week = await repo.count_since(week_ago)
    view = views.admin_panel(
        business=settings.business_name,
        total=total,
        last_week=last_week,
    )
    await render(bot, chat_id, state, view)


async def _render_recent(
    bot: Bot,
    chat_id: int,
    state: FSMContext,
    repo: LeadsRepo,
    page: int,
) -> None:
    leads = await repo.all()
    leads = list(reversed(leads))  # newest first
    total_pages = max(1, math.ceil(len(leads) / RECENT_PAGE_SIZE))
    page = max(1, min(page, total_pages))
    start = (page - 1) * RECENT_PAGE_SIZE
    chunk = leads[start : start + RECENT_PAGE_SIZE]
    lines = [
        lead_short(
            lead_id=lead.id,
            name=lead.name,
            phone=lead.phone,
            service=lead.service,
            created_at=lead.created_at,
        )
        for lead in chunk
    ]
    view = views.admin_recent(page=page, total_pages=total_pages, lines=lines)
    await render(bot, chat_id, state, view)


# --- /menu command + a:open ------------------------------------------------

@router.message(Command("admin"))
@router.message(Command("panel"))
async def cmd_admin_panel(
    message: Message, state: FSMContext, settings: Settings, repo: LeadsRepo, bot: Bot
) -> None:
    if not _is_admin_message(message, settings):
        return
    await _render_panel(bot, message.chat.id, state, settings, repo)


@router.callback_query(F.data == "a:open")
async def cb_open_panel(
    call: CallbackQuery, state: FSMContext, settings: Settings, repo: LeadsRepo, bot: Bot
) -> None:
    if not _is_admin_call(call, settings):
        await call.answer("Доступно только админу", show_alert=True)
        return
    if call.message is None:
        await call.answer()
        return
    await _render_panel(bot, call.message.chat.id, state, settings, repo)
    await call.answer()


@router.callback_query(F.data == "a:refresh")
async def cb_refresh(
    call: CallbackQuery, state: FSMContext, settings: Settings, repo: LeadsRepo, bot: Bot
) -> None:
    if not _is_admin_call(call, settings):
        await call.answer("Доступно только админу", show_alert=True)
        return
    if call.message is None:
        await call.answer()
        return
    await _render_panel(bot, call.message.chat.id, state, settings, repo)
    await call.answer("Обновлено")


# --- recent leads (paginated) ----------------------------------------------

@router.callback_query(F.data.regexp(r"^a:recent:\d+$"))
async def cb_recent(
    call: CallbackQuery, state: FSMContext, settings: Settings, repo: LeadsRepo, bot: Bot
) -> None:
    if not _is_admin_call(call, settings):
        await call.answer("Доступно только админу", show_alert=True)
        return
    if call.message is None or call.data is None:
        await call.answer()
        return
    page = int(call.data.split(":")[-1])
    await _render_recent(bot, call.message.chat.id, state, repo, page)
    await call.answer()


@router.callback_query(F.data == "a:noop")
async def cb_noop(call: CallbackQuery) -> None:
    await call.answer()


# --- export CSV ------------------------------------------------------------

@router.callback_query(F.data == "a:export")
async def cb_export(
    call: CallbackQuery, settings: Settings, repo: LeadsRepo, bot: Bot
) -> None:
    if not _is_admin_call(call, settings):
        await call.answer("Доступно только админу", show_alert=True)
        return
    if call.message is None:
        await call.answer()
        return
    leads = await repo.all()
    if not leads:
        await call.answer("Пока нет ни одной заявки", show_alert=True)
        return
    payload = leads_to_csv(leads)
    filename = f"leads-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}.csv"
    await bot.send_document(
        chat_id=call.message.chat.id,
        document=BufferedInputFile(payload, filename=filename),
        caption=f"📥 Экспорт: <b>{len(leads)}</b> заявок",
        parse_mode="HTML",
    )
    await call.answer("Файл отправлен")


@router.message(Command("export"))
async def cmd_export(
    message: Message, settings: Settings, repo: LeadsRepo, bot: Bot
) -> None:
    if not _is_admin_message(message, settings):
        return
    leads = await repo.all()
    if not leads:
        await message.answer("Пока нет ни одной заявки.")
        return
    payload = leads_to_csv(leads)
    filename = f"leads-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}.csv"
    await message.answer_document(
        BufferedInputFile(payload, filename=filename),
        caption=f"📥 Экспорт: <b>{len(leads)}</b> заявок",
        parse_mode="HTML",
    )


# --- ping ------------------------------------------------------------------

@router.callback_query(F.data == "a:ping")
async def cb_ping(call: CallbackQuery, settings: Settings) -> None:
    if not _is_admin_call(call, settings):
        await call.answer("Доступно только админу", show_alert=True)
        return
    await call.answer("🏓 pong — бот живой", show_alert=True)


@router.message(Command("ping"))
async def cmd_ping(message: Message, settings: Settings) -> None:
    if not _is_admin_message(message, settings):
        return
    await message.answer("🏓 pong")


# --- legacy /stats (still works for power-users) ---------------------------

@router.message(Command("stats"))
async def cmd_stats(
    message: Message, settings: Settings, repo: LeadsRepo
) -> None:
    if not _is_admin_message(message, settings):
        return
    total = await repo.count()
    week_ago = (datetime.now(UTC) - timedelta(days=7)).isoformat(timespec="seconds")
    last_week = await repo.count_since(week_ago)
    await message.answer(
        f"📊 <b>Статистика</b>\n\n"
        f"Всего: <b>{total}</b>\n"
        f"За последние 7 дней: <b>{last_week}</b>",
        parse_mode="HTML",
    )
