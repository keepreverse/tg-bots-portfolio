"""Tests for db.py: schema seed, repos, race-condition protection with buffer."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from booking_bot.db import (
    BookingsRepo,
    ServicesRepo,
    SlotConflict,
    WorkingHoursRepo,
    bookings_to_csv,
)


async def test_working_hours_seed_default_is_tue_thu_sat_sun(db_path: Path) -> None:
    """Default seed: Mon/Wed/Fri are off; Tue/Thu/Sat/Sun are 12-20."""
    repo = WorkingHoursRepo(db_path)
    # Anchor on 2026-05 dates so the weekday math is unambiguous:
    # Mon=4, Tue=5, Wed=6, Thu=7, Fri=8, Sat=9, Sun=10
    assert await repo.get_window_for_date(date(2026, 5, 4)) is None       # Mon
    assert await repo.get_window_for_date(date(2026, 5, 5)) == (12, 20)   # Tue
    assert await repo.get_window_for_date(date(2026, 5, 6)) is None       # Wed
    assert await repo.get_window_for_date(date(2026, 5, 7)) == (12, 20)   # Thu
    assert await repo.get_window_for_date(date(2026, 5, 8)) is None       # Fri
    assert await repo.get_window_for_date(date(2026, 5, 9)) == (12, 20)   # Sat
    assert await repo.get_window_for_date(date(2026, 5, 10)) == (12, 20)  # Sun


async def test_services_seed_has_eleven_active(seeded_db_path: Path) -> None:
    repo = ServicesRepo(seeded_db_path)
    services = await repo.list_active()
    assert len(services) == 11
    slugs = {s.slug for s in services}
    assert "tattoo_minimal" in slugs
    assert "piercing_consult" in slugs
    minimal = next(s for s in services if s.slug == "tattoo_minimal")
    assert minimal.duration_minutes == 30
    assert minimal.price_rub == 5000
    sleeve = next(s for s in services if s.slug == "tattoo_sleeve")
    assert sleeve.duration_minutes == 240
    assert sleeve.price_rub == 25000
    consult = next(s for s in services if s.slug == "tattoo_consult")
    assert consult.price_rub == 0


async def test_services_by_category_split(seeded_db_path: Path) -> None:
    repo = ServicesRepo(seeded_db_path)
    tattoo = await repo.list_by_category("tattoo")
    piercing = await repo.list_by_category("piercing")
    assert {s.category for s in tattoo} == {"tattoo"}
    assert {s.category for s in piercing} == {"piercing"}
    assert len(tattoo) + len(piercing) == 11


async def test_booking_create_and_get_back(seeded_db_path: Path) -> None:
    services = ServicesRepo(seeded_db_path)
    minimal = await services.get_by_slug("tattoo_minimal")
    assert minimal is not None
    repo = BookingsRepo(seeded_db_path, buffer_after_minutes=30)
    start = datetime(2026, 5, 19, 9, 0, tzinfo=UTC)  # 12:00 MSK
    end = start + timedelta(minutes=minimal.duration_minutes)
    bid = await repo.create_with_overlap_check(
        user_tg_id=111,
        user_full_name="Алексей",
        user_phone="+79991112233",
        user_username="alex_user",
        service=minimal,
        start_at_utc=start,
        end_at_utc=end,
        now_utc=datetime(2026, 5, 12, 0, 0, tzinfo=UTC),
    )
    fetched = await repo.get_by_id(bid)
    assert fetched is not None
    assert fetched.status == "confirmed"
    assert fetched.service_duration_minutes_snapshot == 30
    assert fetched.service_price_rub_snapshot == 5000
    assert fetched.service_name_snapshot.startswith("Тату-минимал")


async def test_booking_overlap_within_buffer_is_rejected(seeded_db_path: Path) -> None:
    """1h booking 12:00-13:00 (effective_end 13:30) must reject another 13:00 candidate."""
    services = ServicesRepo(seeded_db_path)
    sleeve = await services.get_by_slug("tattoo_sleeve")
    minimal = await services.get_by_slug("tattoo_minimal")
    assert sleeve and minimal
    repo = BookingsRepo(seeded_db_path, buffer_after_minutes=30)
    now = datetime(2026, 5, 12, 0, 0, tzinfo=UTC)
    first_start = datetime(2026, 5, 19, 9, 0, tzinfo=UTC)  # 12:00 MSK
    # First booking: 2h tattoo medium  -> real end 14:00 MSK -> effective 14:30 MSK
    medium = await services.get_by_slug("tattoo_medium")
    assert medium
    await repo.create_with_overlap_check(
        user_tg_id=111,
        user_full_name="Алексей",
        user_phone=None,
        user_username=None,
        service=medium,
        start_at_utc=first_start,
        end_at_utc=first_start + timedelta(minutes=medium.duration_minutes),
        now_utc=now,
    )
    # Second candidate: 30 min at 14:00 MSK (== 11:00 UTC).
    # Effective_end of first = 14:30 MSK -> 30-min candidate starts at 14:00 < 14:30 -> CONFLICT.
    bad_start = datetime(2026, 5, 19, 11, 0, tzinfo=UTC)  # 14:00 MSK
    with pytest.raises(SlotConflict):
        await repo.create_with_overlap_check(
            user_tg_id=222,
            user_full_name="Бориска",
            user_phone=None,
            user_username=None,
            service=minimal,
            start_at_utc=bad_start,
            end_at_utc=bad_start + timedelta(minutes=minimal.duration_minutes),
            now_utc=now,
        )

    # Same candidate at 15:00 MSK == 12:00 UTC is FINE.
    ok_start = datetime(2026, 5, 19, 12, 0, tzinfo=UTC)
    ok_id = await repo.create_with_overlap_check(
        user_tg_id=222,
        user_full_name="Бориска",
        user_phone=None,
        user_username=None,
        service=minimal,
        start_at_utc=ok_start,
        end_at_utc=ok_start + timedelta(minutes=minimal.duration_minutes),
        now_utc=now,
    )
    assert ok_id > 0


async def test_booking_30min_neighbour_is_allowed(seeded_db_path: Path) -> None:
    """Two 30-min bookings back-to-back at hourly grid (12:00 and 13:00) is allowed."""
    services = ServicesRepo(seeded_db_path)
    minimal = await services.get_by_slug("tattoo_minimal")
    assert minimal
    repo = BookingsRepo(seeded_db_path, buffer_after_minutes=30)
    now = datetime(2026, 5, 12, 0, 0, tzinfo=UTC)
    start_12 = datetime(2026, 5, 19, 9, 0, tzinfo=UTC)   # 12:00 MSK
    start_13 = datetime(2026, 5, 19, 10, 0, tzinfo=UTC)  # 13:00 MSK
    await repo.create_with_overlap_check(
        user_tg_id=111, user_full_name="A", user_phone=None, user_username=None,
        service=minimal, start_at_utc=start_12,
        end_at_utc=start_12 + timedelta(minutes=30), now_utc=now,
    )
    bid = await repo.create_with_overlap_check(
        user_tg_id=222, user_full_name="B", user_phone=None, user_username=None,
        service=minimal, start_at_utc=start_13,
        end_at_utc=start_13 + timedelta(minutes=30), now_utc=now,
    )
    assert bid > 0


async def test_cancel_releases_slot(seeded_db_path: Path) -> None:
    services = ServicesRepo(seeded_db_path)
    medium = await services.get_by_slug("tattoo_medium")
    minimal = await services.get_by_slug("tattoo_minimal")
    assert medium and minimal
    repo = BookingsRepo(seeded_db_path, buffer_after_minutes=30)
    now = datetime(2026, 5, 12, 0, 0, tzinfo=UTC)
    start = datetime(2026, 5, 19, 9, 0, tzinfo=UTC)
    bid = await repo.create_with_overlap_check(
        user_tg_id=111, user_full_name="A", user_phone=None, user_username=None,
        service=medium, start_at_utc=start,
        end_at_utc=start + timedelta(minutes=medium.duration_minutes), now_utc=now,
    )
    assert await repo.cancel(bid) is True
    # Now the previously conflicting slot must succeed.
    bad_start = datetime(2026, 5, 19, 11, 0, tzinfo=UTC)
    bid2 = await repo.create_with_overlap_check(
        user_tg_id=222, user_full_name="B", user_phone=None, user_username=None,
        service=minimal, start_at_utc=bad_start,
        end_at_utc=bad_start + timedelta(minutes=minimal.duration_minutes), now_utc=now,
    )
    assert bid2 > 0


async def test_list_confirmed_in_range_returns_real_ends(seeded_db_path: Path) -> None:
    services = ServicesRepo(seeded_db_path)
    medium = await services.get_by_slug("tattoo_medium")
    assert medium
    repo = BookingsRepo(seeded_db_path, buffer_after_minutes=30)
    now = datetime(2026, 5, 12, 0, 0, tzinfo=UTC)
    start = datetime(2026, 5, 19, 9, 0, tzinfo=UTC)
    end = start + timedelta(minutes=medium.duration_minutes)
    await repo.create_with_overlap_check(
        user_tg_id=111, user_full_name="A", user_phone=None, user_username=None,
        service=medium, start_at_utc=start, end_at_utc=end, now_utc=now,
    )
    rows = await repo.list_confirmed_in_range(
        datetime(2026, 5, 19, 0, 0, tzinfo=UTC),
        datetime(2026, 5, 20, 0, 0, tzinfo=UTC),
    )
    assert rows == [(start, end)]


async def test_bookings_to_csv_has_header_and_one_row(seeded_db_path: Path) -> None:
    services = ServicesRepo(seeded_db_path)
    minimal = await services.get_by_slug("tattoo_minimal")
    assert minimal
    repo = BookingsRepo(seeded_db_path, buffer_after_minutes=30)
    now = datetime(2026, 5, 12, 0, 0, tzinfo=UTC)
    start = datetime(2026, 5, 19, 9, 0, tzinfo=UTC)
    await repo.create_with_overlap_check(
        user_tg_id=111, user_full_name="Алексей", user_phone="+79991112233", user_username="alex",
        service=minimal, start_at_utc=start,
        end_at_utc=start + timedelta(minutes=minimal.duration_minutes), now_utc=now,
    )
    bookings, _total = await repo.list_admin(limit=100, offset=0)
    csv_text = bookings_to_csv(bookings, "Europe/Moscow")
    lines = csv_text.strip().splitlines()
    assert lines[0].startswith("id,status,start_local,end_local")
    assert "Алексей" in lines[1]
    assert "30" in lines[1]
    assert "5000" in lines[1]


async def test_stats_basic(seeded_db_path: Path) -> None:
    services = ServicesRepo(seeded_db_path)
    minimal = await services.get_by_slug("tattoo_minimal")
    assert minimal
    repo = BookingsRepo(seeded_db_path, buffer_after_minutes=30)
    now = datetime(2026, 5, 12, 0, 0, tzinfo=UTC)
    # Upcoming
    start_future = datetime(2026, 5, 19, 9, 0, tzinfo=UTC)
    await repo.create_with_overlap_check(
        user_tg_id=111, user_full_name="A", user_phone=None, user_username=None,
        service=minimal, start_at_utc=start_future,
        end_at_utc=start_future + timedelta(minutes=30), now_utc=now,
    )
    s = await repo.stats(now_utc=now)
    assert s["confirmed_upcoming"] == 1
    assert s["completed_total"] == 0
    assert s["cancelled_total"] == 0
    assert s["revenue_completed_rub"] == 0
