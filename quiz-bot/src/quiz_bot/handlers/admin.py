"""Admin panel: stats, paginated recent leads, CSV export, per-category funnel."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from .. import texts
from ..config import Settings, get_settings
from ..db import EventsRepo, LeadsRepo, leads_to_csv
from ..keyboards import (
    CB_ADMIN,
    CB_ADMIN_EXPORT,
    CB_ADMIN_FUNNEL,
    CB_ADMIN_LEADS,
    CB_ADMIN_STATS,
    admin_back_kb,
)
from ..money import format_range
from ..quiz_engine import QuizConfig
from ..render import render, render_callback
from ..views import (
    admin_funnel_picker_view,
    admin_funnel_view,
    admin_leads_view,
    admin_menu_view,
    admin_stats_view,
)

LEADS_PAGE_SIZE = 5


def _is_admin(user_id: int | None, settings: Settings) -> bool:
    return user_id is not None and user_id == settings.ADMIN_CHAT_ID


def _leads_word(n: int) -> str:
    """Russian pluralization for 'лид': 1 лид, 2 лида, 5 лидов."""
    n_abs = abs(n) % 100
    if 11 <= n_abs <= 14:
        return "лидов"
    last = n_abs % 10
    if last == 1:
        return "лид"
    if 2 <= last <= 4:
        return "лида"
    return "лидов"


def build_admin_router(*, config: QuizConfig) -> Router:
    router = Router(name="admin")

    @router.message(Command("admin"))
    async def admin_cmd(msg: Message, state: FSMContext) -> None:
        s = get_settings()
        if not _is_admin(msg.from_user.id if msg.from_user else None, s):
            await msg.answer(texts.NO_RIGHTS)
            return
        view = admin_menu_view()
        await render(msg.bot, msg.chat.id, state, view.text, view.markup)

    @router.callback_query(F.data == f"{CB_ADMIN}:0")
    async def admin_main(cq: CallbackQuery, state: FSMContext) -> None:
        s = get_settings()
        if not _is_admin(cq.from_user.id, s):
            await cq.answer(texts.NO_RIGHTS, show_alert=True)
            return
        view = admin_menu_view()
        await render_callback(cq, state, view.text, view.markup)

    @router.callback_query(F.data == f"{CB_ADMIN_STATS}:0")
    async def admin_stats(cq: CallbackQuery, state: FSMContext) -> None:
        s = get_settings()
        if not _is_admin(cq.from_user.id, s):
            await cq.answer(texts.NO_RIGHTS, show_alert=True)
            return
        repo = EventsRepo(s.db_path_abs)
        stats = await repo.overall_stats()
        view = admin_stats_view(
            starts=stats["starts"],
            completed=stats["completed"],
            leads=stats["leads"],
        )
        await render_callback(cq, state, view.text, view.markup)

    @router.callback_query(F.data.startswith(f"{CB_ADMIN_LEADS}:"))
    async def admin_leads(cq: CallbackQuery, state: FSMContext) -> None:
        s = get_settings()
        if not _is_admin(cq.from_user.id, s):
            await cq.answer(texts.NO_RIGHTS, show_alert=True)
            return
        try:
            page = max(1, int((cq.data or "").split(":", 1)[1]))
        except (ValueError, IndexError):
            page = 1
        repo = LeadsRepo(s.db_path_abs)
        offset = (page - 1) * LEADS_PAGE_SIZE
        leads, total = await repo.list_recent(limit=LEADS_PAGE_SIZE, offset=offset)
        total_pages = max(1, (total + LEADS_PAGE_SIZE - 1) // LEADS_PAGE_SIZE)
        cards: list[str] = []
        for lead in leads:
            price_str = format_range(
                lead.price_min,
                lead.price_max,
                currency=config.currency_label,
                unit_suffix=lead.price_unit_label,
            )
            cat = config.category_by_key(lead.category_key)
            emoji = cat.emoji if cat else "•"
            cards.append(texts.LEAD_CARD.format(
                id=lead.id,
                created_local=lead.created_at_utc.strftime("%d.%m %H:%M UTC"),
                emoji=emoji,
                category=lead.category_title,
                price=price_str,
                name=lead.full_name,
                phone=lead.phone,
            ))
        view = admin_leads_view(page=page, total_pages=total_pages, cards=cards)
        await render_callback(cq, state, view.text, view.markup)

    @router.callback_query(F.data == f"{CB_ADMIN_EXPORT}:0")
    async def admin_export(cq: CallbackQuery, state: FSMContext) -> None:
        s = get_settings()
        if not _is_admin(cq.from_user.id, s):
            await cq.answer(texts.NO_RIGHTS, show_alert=True)
            return
        repo = LeadsRepo(s.db_path_abs)
        leads = await repo.export_all()
        if not leads:
            await render_callback(cq, state, texts.LEADS_EMPTY, admin_back_kb())
            return
        csv_bytes = leads_to_csv(leads)
        await cq.bot.send_document(
            chat_id=cq.from_user.id,
            document=BufferedInputFile(csv_bytes, filename="quiz_leads.csv"),
            caption=f"📥 Экспорт: {len(leads)} {_leads_word(len(leads))}",
        )
        # Render the admin menu again so the user can keep navigating.
        view = admin_menu_view()
        await render_callback(cq, state, view.text, view.markup)

    @router.callback_query(F.data == f"{CB_ADMIN_FUNNEL}:_all")
    async def admin_funnel_picker(cq: CallbackQuery, state: FSMContext) -> None:
        s = get_settings()
        if not _is_admin(cq.from_user.id, s):
            await cq.answer(texts.NO_RIGHTS, show_alert=True)
            return
        if len(config.categories) == 1:
            # Single category — skip the picker.
            await _show_funnel_for(cq, state, config.categories[0].key)
            return
        view = admin_funnel_picker_view(list(config.categories))
        await render_callback(cq, state, view.text, view.markup)

    @router.callback_query(F.data.startswith(f"{CB_ADMIN_FUNNEL}:"))
    async def admin_funnel(cq: CallbackQuery, state: FSMContext) -> None:
        s = get_settings()
        if not _is_admin(cq.from_user.id, s):
            await cq.answer(texts.NO_RIGHTS, show_alert=True)
            return
        cat_key = (cq.data or "").split(":", 1)[1]
        if cat_key == "_all":
            return
        await _show_funnel_for(cq, state, cat_key)

    async def _show_funnel_for(cq: CallbackQuery, state: FSMContext, cat_key: str) -> None:
        s = get_settings()
        cat = config.category_by_key(cat_key)
        if cat is None:
            return
        repo = EventsRepo(s.db_path_abs)
        # Need the start count for THIS category.
        import aiosqlite
        async with aiosqlite.connect(s.db_path_abs) as db:
            cur = await db.execute(
                "SELECT COUNT(DISTINCT user_tg_id) FROM quiz_events"
                " WHERE category_key = ? AND event_kind = 'start'",
                (cat_key,),
            )
            row = await cur.fetchone()
            starts = int(row[0]) if row else 0
        per_step = await repo.funnel(cat_key, cat.total_steps)
        view = admin_funnel_view(category=cat, starts=starts, per_step=per_step)
        await render_callback(cq, state, view.text, view.markup)

    return router
