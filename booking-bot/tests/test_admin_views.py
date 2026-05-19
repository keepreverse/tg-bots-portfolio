"""Tests for the paginated admin upcoming view."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from booking_bot.db import Booking
from booking_bot.views import ADMIN_UPCOMING_PAGE_SIZE, admin_upcoming_screen


def _b(i: int, when: datetime) -> Booking:
    return Booking(
        id=i,
        user_tg_id=42,
        user_full_name=f"Клиент {i}",
        user_phone="+79991112233",
        user_username=None,
        service_id=1,
        start_at_utc=when,
        end_at_utc=when + timedelta(minutes=60),
        service_duration_minutes_snapshot=60,
        service_price_rub_snapshot=5000,
        service_name_snapshot="Тату-минимал",
        service_emoji_snapshot="🖤",
        status="confirmed",
        created_at_utc=datetime(2026, 5, 1, tzinfo=UTC),
    )


def _bookings(n: int) -> list[Booking]:
    base = datetime(2026, 5, 19, 9, 0, tzinfo=UTC)
    return [_b(i, base + timedelta(hours=i)) for i in range(1, n + 1)]


def test_admin_upcoming_empty() -> None:
    text, kb = admin_upcoming_screen(bookings=[], page=1, tz_name="Europe/Moscow")
    assert "Ближайших записей нет" in text
    # Only the back-to-admin row should be there.
    flat = [btn.text for row in kb.inline_keyboard for btn in row]
    assert "◀ В админ-меню" in flat


def test_admin_upcoming_first_page_shows_page_size() -> None:
    text, kb = admin_upcoming_screen(
        bookings=_bookings(8), page=1, tz_name="Europe/Moscow",
    )
    # First page shows up to PAGE_SIZE bookings.
    assert text.count("#") >= ADMIN_UPCOMING_PAGE_SIZE
    assert "стр. 1/" in text
    # Pagination row: page indicator + ▶ (no ◀ on first page).
    flat = [btn.text for row in kb.inline_keyboard for btn in row]
    assert any("1/" in t for t in flat)
    assert "▶" in flat
    assert "◀" not in flat


def test_admin_upcoming_second_page_shows_back_button() -> None:
    text, kb = admin_upcoming_screen(
        bookings=_bookings(8), page=2, tz_name="Europe/Moscow",
    )
    assert "стр. 2/" in text
    flat = [btn.text for row in kb.inline_keyboard for btn in row]
    assert "◀" in flat
    # 8 bookings, page size 5 → 2 pages, so no ▶ on last page.
    assert "▶" not in flat


def test_admin_upcoming_page_overflow_clamped() -> None:
    text, _ = admin_upcoming_screen(
        bookings=_bookings(3), page=99, tz_name="Europe/Moscow",
    )
    assert "стр. 1/1" in text


def test_admin_upcoming_card_has_client_and_phone() -> None:
    text, _ = admin_upcoming_screen(
        bookings=_bookings(1), page=1, tz_name="Europe/Moscow",
    )
    assert "Клиент 1" in text
    assert "+79991112233" in text
    assert "Тату-минимал" in text
    assert "5 000" in text or "5 000 ₽" in text
