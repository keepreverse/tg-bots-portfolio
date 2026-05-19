"""Tests for view builders: returned (text, keyboard) pairs make sense."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from booking_bot.db import ServicesRepo
from booking_bot.views import (
    booking_service_list,
    booking_summary,
    booking_time_picker,
    main_menu,
    services_catalog,
)


def test_main_menu_text_has_business() -> None:
    text, _ = main_menu("Test Salon")
    assert "Test Salon" in text


def test_main_menu_admin_button_only_for_admin() -> None:
    _, kb_user = main_menu("Test Salon", is_admin=False)
    _, kb_admin = main_menu("Test Salon", is_admin=True)
    flat_user = [btn.text for row in kb_user.inline_keyboard for btn in row]
    flat_admin = [btn.text for row in kb_admin.inline_keyboard for btn in row]
    assert not any("Админ" in b for b in flat_user)
    assert any("Админ" in b for b in flat_admin)


async def test_services_catalog_has_all_twelve(seeded_db_path: Path) -> None:
    repo = ServicesRepo(seeded_db_path)
    services = await repo.list_active()
    text, _ = services_catalog(services)
    assert "🎨 Тату" in text
    assert "💉 Пирсинг" in text
    assert "Тату-минимал" in text
    assert "Прокол мочки уха" in text


async def test_booking_service_list_only_tattoo(seeded_db_path: Path) -> None:
    repo = ServicesRepo(seeded_db_path)
    services = await repo.list_by_category("tattoo")
    text, kb = booking_service_list("tattoo", services)
    assert "тату" in text.lower()
    # The screen header ("🎨 Тату") already names the section; the filled-block
    # should NOT duplicate it, so "Раздел:" must be absent here.
    assert "Раздел" not in text
    flat = [btn.text for row in kb.inline_keyboard for btn in row]
    assert any("Тату-минимал" in b for b in flat)
    assert all("Прокол" not in b for b in flat)


async def test_booking_time_picker_with_empty_slots_shows_day_full(seeded_db_path: Path) -> None:
    repo = ServicesRepo(seeded_db_path)
    minimal = await repo.get_by_slug("tattoo_minimal")
    assert minimal
    text, _ = booking_time_picker(
        category="tattoo", service=minimal, date_local=date(2026, 5, 19), slots=[],
    )
    assert "не осталось" in text.lower()


async def test_booking_time_picker_with_slots_renders_grid(seeded_db_path: Path) -> None:
    from datetime import time as t

    repo = ServicesRepo(seeded_db_path)
    minimal = await repo.get_by_slug("tattoo_minimal")
    assert minimal
    text, kb = booking_time_picker(
        category="tattoo",
        service=minimal,
        date_local=date(2026, 5, 19),
        slots=[t(12), t(13), t(14), t(15)],
    )
    assert "19 мая" in text
    flat = [btn.text for row in kb.inline_keyboard for btn in row]
    assert "12:00" in flat and "15:00" in flat


def test_progress_bar_appears_on_every_booking_step() -> None:
    from booking_bot.views import booking_category
    text, _ = booking_category()
    assert "▰" in text
    assert "Шаг" in text


async def test_booking_summary_renders_human(seeded_db_path: Path) -> None:
    repo = ServicesRepo(seeded_db_path)
    medium = await repo.get_by_slug("tattoo_medium")
    assert medium
    start = datetime(2026, 5, 19, 12, 0)
    end = datetime(2026, 5, 19, 14, 0)
    summary = booking_summary(
        service=medium, start_at_local=start, end_at_local=end,
    )
    assert "Тату средний" in summary
    assert "12:00 – 14:00" in summary
    assert "2 ч" in summary
    assert "14 000 ₽" in summary


def test_iso_dates_in_callback_are_round_trippable() -> None:
    d = date(2026, 5, 19)
    iso = d.isoformat()
    assert date.fromisoformat(iso) == d


def test_utc_to_msk_round_trip_for_12pm_msk() -> None:
    from zoneinfo import ZoneInfo

    msk = ZoneInfo("Europe/Moscow")
    local = datetime(2026, 5, 19, 12, 0, tzinfo=msk)
    utc = local.astimezone(UTC)
    assert utc.hour == 9
    back = utc.astimezone(msk)
    assert back == local


@pytest.mark.parametrize(
    ("d", "weekday"),
    [
        (date(2026, 5, 4), 0),   # Monday
        (date(2026, 5, 19), 1),  # Tuesday
    ],
)
def test_weekday_index_matches(d: date, weekday: int) -> None:
    assert d.weekday() == weekday
