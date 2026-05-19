"""APScheduler-based reminder jobs."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from . import texts
from .config import Settings
from .db import BookingsRepo
from .timez import from_utc
from .views import booking_summary_text

log = logging.getLogger(__name__)


def build_scheduler(bot: Bot, settings: Settings) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=str(UTC))
    scheduler.add_job(
        _run_due_reminders,
        trigger="interval",
        minutes=5,
        kwargs={"bot": bot, "settings": settings},
        id="reminders",
        replace_existing=True,
        next_run_time=datetime.now(UTC),
    )
    return scheduler


async def _run_due_reminders(*, bot: Bot, settings: Settings) -> None:
    repo = BookingsRepo(settings.db_path_abs, settings.BOOKING_BUFFER_AFTER_MINUTES)
    offsets = sorted(settings.reminder_offsets_hours, reverse=True)
    for hours in offsets:
        kind = "24h" if hours >= 24 else "2h"
        if hours not in (24, 2):
            continue
        try:
            due = await repo.list_due_reminders(kind, offset_hours=hours)
        except Exception:
            log.exception("reminder query failed for %s", kind)
            continue
        for b in due:
            start_local = from_utc(b.start_at_utc, settings.master_tz)
            end_local = from_utc(b.end_at_utc, settings.master_tz)
            summary = booking_summary_text(
                emoji=b.service_emoji_snapshot,
                name=b.service_name_snapshot,
                duration_minutes=b.service_duration_minutes_snapshot,
                price_rub=b.service_price_rub_snapshot,
                start_at_local=start_local,
                end_at_local=end_local,
            )
            template = texts.REMINDER_24H if kind == "24h" else texts.REMINDER_2H
            try:
                await bot.send_message(
                    b.user_tg_id,
                    template.format(summary=summary, address=settings.BUSINESS_ADDRESS),
                )
                await repo.mark_reminder_sent(b.id, kind)
            except Exception:
                log.exception("Reminder send failed for booking %s kind %s", b.id, kind)
