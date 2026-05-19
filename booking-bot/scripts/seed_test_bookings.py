"""Seed 6 future confirmed bookings to exercise admin pagination (5 + 1)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from booking_bot.config import get_settings
from booking_bot.db import BookingsRepo, ServicesRepo, init_db, seed_services


async def main() -> None:
    s = get_settings()
    await init_db(s.db_path_abs)
    from pathlib import Path
    seed_path = Path(__file__).resolve().parents[1] / "data" / "seed_services.json"
    await seed_services(s.db_path_abs, seed_path)
    services_repo = ServicesRepo(s.db_path_abs)
    services = await services_repo.list_active()
    if not services:
        raise SystemExit("no services seeded")
    minimal = next(svc for svc in services if svc.slug == "tattoo_minimal")
    bookings_repo = BookingsRepo(s.db_path_abs, s.BOOKING_BUFFER_AFTER_MINUTES)

    # 6 bookings, 1 every 3 hours starting 25 hours from now.
    base = datetime.now(UTC) + timedelta(hours=25)
    base = base.replace(minute=0, second=0, microsecond=0)
    for i in range(6):
        start = base + timedelta(hours=3 * i)
        end = start + timedelta(minutes=minimal.duration_minutes)
        await bookings_repo.create_with_overlap_check(
            user_tg_id=10000 + i,
            user_full_name=f"Test Client {i + 1}",
            user_phone=f"+7999111{2200 + i:04d}",
            user_username=None,
            service=minimal,
            start_at_utc=start,
            end_at_utc=end,
            now_utc=datetime.now(UTC),
        )
        print(f"seeded #{i + 1} at {start.isoformat()}")


if __name__ == "__main__":
    asyncio.run(main())
