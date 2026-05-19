"""Pure slot generator: no I/O, fully unit-tested.

Hourly grid (slot_step_minutes=60), variable service durations in minutes
(multiples of 30), and a 30-minute buffer after every existing booking
that the master needs to disinfect and switch over.

See playbook §2.4 and §2.5 for the architecture; §2.11 for the test matrix.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

UTC = ZoneInfo("UTC")


def available_starts(
    *,
    date_local: date,
    working_window: tuple[int, int] | None,
    slot_step_minutes: int,
    service_duration_minutes: int,
    buffer_after_minutes: int,
    existing_bookings_utc: list[tuple[datetime, datetime]],
    master_tz: ZoneInfo,
    now_utc: datetime,
) -> list[time]:
    """Return the list of valid local start times for a service on `date_local`.

    Args:
        date_local: the local calendar date being queried.
        working_window: (start_hour, end_hour) in local time, or None if the day is off.
        slot_step_minutes: grid step in minutes. In production this is always 60.
        service_duration_minutes: service duration in minutes (30 / 120 / 180 / 240 …).
        buffer_after_minutes: minimum gap after each existing booking; in production 30.
        existing_bookings_utc: list of (start_utc, end_utc) for `status='confirmed'`
            bookings. `end_utc` is the REAL end of the service, without padding.
        master_tz: the master's local time zone.
        now_utc: current time in UTC (used to filter out past starts).

    Returns:
        Sorted list of local times (one per valid hourly start). Empty list if
        the day is off, or if nothing fits, or if no slot is free.

    Rules:
        - Starts always land on a full grid step (12:00, 13:00, …) within
          `working_window`.
        - A candidate `[start, start + duration)` must lie entirely inside
          `working_window` (semi-open: end == window_end_hour is OK).
        - A candidate is BLOCKED if it overlaps with any existing booking
          inflated on the right by `buffer_after_minutes`:
              start_cand < (b.end + buffer)  AND  end_cand > b.start
        - Past candidates (start <= now_utc) are filtered out.
    """
    if working_window is None:
        return []

    start_hour, end_hour = working_window
    if start_hour >= end_hour:
        return []

    starts: list[time] = []
    cur_local = datetime(
        date_local.year, date_local.month, date_local.day,
        start_hour, 0, tzinfo=master_tz,
    )
    end_local = datetime(
        date_local.year, date_local.month, date_local.day,
        end_hour, 0, tzinfo=master_tz,
    )
    duration = timedelta(minutes=service_duration_minutes)
    step = timedelta(minutes=slot_step_minutes)
    buffer = timedelta(minutes=buffer_after_minutes)

    while cur_local + duration <= end_local:
        cand_start_utc = cur_local.astimezone(UTC)
        cand_end_utc = cand_start_utc + duration

        if cand_start_utc <= now_utc:
            cur_local += step
            continue

        conflict = any(
            cand_start_utc < (b_end + buffer) and cand_end_utc > b_start
            for b_start, b_end in existing_bookings_utc
        )
        if not conflict:
            starts.append(cur_local.time())

        cur_local += step

    return starts
