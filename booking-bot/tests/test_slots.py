"""Test matrix from playbook §2.11.

All cases use:
- master_tz = Europe/Moscow
- date_local = 2026-05-19 (Tuesday, a working day)
- working_window = (12, 20) unless explicitly different
- slot_step_minutes = 60, buffer_after_minutes = 30 unless explicitly different

`now_utc` is set far in the past (start of 2026-05-12 UTC) so past-filtering does
not affect any test except #6, which overrides it.
"""

from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from booking_bot.slots import available_starts

MSK = ZoneInfo("Europe/Moscow")
UTC = ZoneInfo("UTC")

D = date(2026, 5, 19)              # Tuesday — a working day
NOW = datetime(2026, 5, 12, 0, 0, tzinfo=UTC)  # before D, all slots are future


def _local(h: int, m: int = 0) -> datetime:
    """Build a UTC datetime from local (D, h:m) MSK."""
    return datetime(D.year, D.month, D.day, h, m, tzinfo=MSK).astimezone(UTC)


def _t(h: int, m: int = 0) -> time:
    return time(h, m)


def _call(
    *,
    duration_minutes: int = 60,
    buffer_minutes: int = 30,
    step_minutes: int = 60,
    working_window: tuple[int, int] | None = (12, 20),
    bookings: list[tuple[datetime, datetime]] | None = None,
    now: datetime = NOW,
) -> list[time]:
    return available_starts(
        date_local=D,
        working_window=working_window,
        slot_step_minutes=step_minutes,
        service_duration_minutes=duration_minutes,
        buffer_after_minutes=buffer_minutes,
        existing_bookings_utc=bookings or [],
        master_tz=MSK,
        now_utc=now,
    )


def test_case_01_free_day_60min_full_grid() -> None:
    """Empty day, 60-min service, shift 12-20 → 8 starts."""
    got = _call(duration_minutes=60)
    assert got == [_t(h) for h in range(12, 20)]


def test_case_02_free_day_240min_five_starts() -> None:
    """Empty day, 240-min (4h) service, shift 12-20 → 12,13,14,15,16."""
    got = _call(duration_minutes=240)
    assert got == [_t(12), _t(13), _t(14), _t(15), _t(16)]


def test_case_03_4h_busy_14_to_15_only_16() -> None:
    """240-min service; busy 14:00-15:00 (effective_end 15:30) → only 16 fits."""
    got = _call(
        duration_minutes=240,
        bookings=[(_local(14), _local(15))],
    )
    assert got == [_t(16)]


def test_case_04_60min_busy_14_to_16_five_starts() -> None:
    """60-min service; busy 14:00-16:00 (effective_end 16:30) → 12,13,17,18,19.

    16:00 is blocked by the buffer (one grid step skipped after the 2h booking).
    """
    got = _call(
        duration_minutes=60,
        bookings=[(_local(14), _local(16))],
    )
    assert got == [_t(12), _t(13), _t(17), _t(18), _t(19)]


def test_case_05_buffer_after_60min_skip_one_step() -> None:
    """60-min service after a 1h booking 15:00-16:00 → 16:00 blocked, 17:00 free."""
    got = _call(
        duration_minutes=60,
        bookings=[(_local(15), _local(16))],
    )
    assert got == [_t(12), _t(13), _t(14), _t(17), _t(18), _t(19)]


def test_case_06_now_15_30_filters_past() -> None:
    """Today is the queried date and it's already 15:30 local → only future starts."""
    now_local = datetime(D.year, D.month, D.day, 15, 30, tzinfo=MSK)
    got = _call(
        duration_minutes=60,
        now=now_local.astimezone(UTC),
    )
    assert got == [_t(16), _t(17), _t(18), _t(19)]


def test_case_07_day_off_returns_empty() -> None:
    """working_window=None (day off) → empty list."""
    got = _call(working_window=None)
    assert got == []


def test_case_08_300min_5h_four_starts() -> None:
    """300-min service in 12-20 → 12,13,14,15 (last ends at 20:00 sharp)."""
    got = _call(duration_minutes=300)
    assert got == [_t(12), _t(13), _t(14), _t(15)]


def test_case_09_540min_9h_empty() -> None:
    """540-min service does not fit any start in an 8-hour window."""
    got = _call(duration_minutes=540)
    assert got == []


def test_case_10_cancelled_not_blocking_treated_as_no_booking() -> None:
    """If the repo filters out cancelled rows, the slot generator should see
    them as 'no booking' — and grant all slots. This is the slot side: we
    just don't pass the cancelled booking in `existing_bookings_utc`."""
    got = _call(duration_minutes=60, bookings=[])
    assert got == [_t(h) for h in range(12, 20)]


def test_case_11_30min_full_day_eight_starts() -> None:
    """30-min service on an empty day with a 1h step → 8 starts (12..19)."""
    got = _call(duration_minutes=30)
    assert got == [_t(h) for h in range(12, 20)]


def test_case_12_30min_after_30min_no_step_skipped() -> None:
    """30-min booking at 12:00 (effective_end 13:00). 30-min candidate at 13:00 is FREE."""
    got = _call(
        duration_minutes=30,
        bookings=[(_local(12), _local(12, 30))],
    )
    assert got == [_t(h) for h in range(13, 20)]


def test_case_13_4h_after_30min_booking_four_starts() -> None:
    """Busy 30 min at 12:00; looking for a 4h slot → 13,14,15,16."""
    got = _call(
        duration_minutes=240,
        bookings=[(_local(12), _local(12, 30))],
    )
    assert got == [_t(13), _t(14), _t(15), _t(16)]


def test_case_14_30min_after_2h_booking_buffer_blocks_14() -> None:
    """Busy 12:00-14:00 (2h, effective_end 14:30). Looking for 30 min → 15..19."""
    got = _call(
        duration_minutes=30,
        bookings=[(_local(12), _local(14))],
    )
    assert got == [_t(15), _t(16), _t(17), _t(18), _t(19)]


def test_case_15_two_30min_in_a_row_third_is_free_at_14() -> None:
    """Busy 12:00-12:30 AND 13:00-13:30 → 30-min candidate at 14:00 free."""
    got = _call(
        duration_minutes=30,
        bookings=[
            (_local(12), _local(12, 30)),
            (_local(13), _local(13, 30)),
        ],
    )
    assert got == [_t(14), _t(15), _t(16), _t(17), _t(18), _t(19)]


def test_case_16_zero_buffer_allows_touching_at_14() -> None:
    """With buffer=0, booking 12:00-14:00 + 60-min candidate at 14:00 is OK."""
    got = _call(
        duration_minutes=60,
        buffer_minutes=0,
        bookings=[(_local(12), _local(14))],
    )
    assert got == [_t(14), _t(15), _t(16), _t(17), _t(18), _t(19)]
