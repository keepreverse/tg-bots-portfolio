"""SQLite schema, migrations and repositories.

All datetimes are stored in UTC as ISO-8601 strings via `aiosqlite`.
The slot generator works with real (un-padded) `end_at_utc`; the 30-min buffer
is applied only when checking for overlaps (see `BookingsRepo.create_with_overlap_check`
and `slots.available_starts`).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import aiosqlite

SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL CHECK (category IN ('tattoo','piercing')),
    emoji TEXT NOT NULL DEFAULT '',
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    duration_minutes INTEGER NOT NULL
        CHECK (duration_minutes >= 30 AND duration_minutes % 30 = 0),
    price_rub INTEGER NOT NULL CHECK (price_rub >= 0),
    sort_order INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS working_hours (
    weekday INTEGER PRIMARY KEY CHECK (weekday BETWEEN 0 AND 6),
    start_hour INTEGER,
    end_hour INTEGER,
    CHECK (
        (start_hour IS NULL AND end_hour IS NULL)
        OR (start_hour BETWEEN 0 AND 23 AND end_hour BETWEEN 1 AND 24 AND end_hour > start_hour)
    )
);

CREATE TABLE IF NOT EXISTS day_overrides (
    date_local TEXT PRIMARY KEY,
    start_hour INTEGER,
    end_hour INTEGER,
    note TEXT NOT NULL DEFAULT '',
    CHECK (
        (start_hour IS NULL AND end_hour IS NULL)
        OR (start_hour BETWEEN 0 AND 23 AND end_hour BETWEEN 1 AND 24 AND end_hour > start_hour)
    )
);

CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_tg_id INTEGER NOT NULL,
    user_full_name TEXT NOT NULL,
    user_phone TEXT,
    user_username TEXT,
    service_id INTEGER NOT NULL REFERENCES services(id),
    start_at_utc TEXT NOT NULL,
    end_at_utc TEXT NOT NULL,
    service_duration_minutes_snapshot INTEGER NOT NULL,
    service_price_rub_snapshot INTEGER NOT NULL,
    service_name_snapshot TEXT NOT NULL,
    service_emoji_snapshot TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL CHECK (status IN ('confirmed','cancelled','completed','no_show')),
    created_at_utc TEXT NOT NULL,
    cancelled_at_utc TEXT,
    completed_at_utc TEXT
);

CREATE INDEX IF NOT EXISTS idx_bookings_user_tg_id ON bookings(user_tg_id);
CREATE INDEX IF NOT EXISTS idx_bookings_start_at_utc ON bookings(start_at_utc);
CREATE INDEX IF NOT EXISTS idx_bookings_status_start ON bookings(status, start_at_utc);

CREATE TABLE IF NOT EXISTS reminders_sent (
    booking_id INTEGER NOT NULL REFERENCES bookings(id),
    kind TEXT NOT NULL CHECK (kind IN ('24h','2h')),
    sent_at_utc TEXT NOT NULL,
    PRIMARY KEY (booking_id, kind)
);
"""


DEFAULT_WORKING_HOURS: dict[int, tuple[int, int] | None] = {
    0: None,        # Пн
    1: (12, 20),    # Вт
    2: None,        # Ср
    3: (12, 20),    # Чт
    4: None,        # Пт
    5: (12, 20),    # Сб
    6: (12, 20),    # Вс
}


@dataclass(frozen=True)
class Service:
    id: int
    slug: str
    category: str
    emoji: str
    name: str
    description: str
    duration_minutes: int
    price_rub: int
    sort_order: int
    active: bool


@dataclass(frozen=True)
class Booking:
    id: int
    user_tg_id: int
    user_full_name: str
    user_phone: str | None
    user_username: str | None
    service_id: int
    start_at_utc: datetime
    end_at_utc: datetime
    service_duration_minutes_snapshot: int
    service_price_rub_snapshot: int
    service_name_snapshot: str
    service_emoji_snapshot: str
    status: str
    created_at_utc: datetime


class SlotConflict(Exception):
    """Raised when overlap-recheck inside BEGIN IMMEDIATE finds a conflicting booking."""


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat()


def _parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s).astimezone(UTC)


async def init_db(db_path: Path) -> None:
    """Create the schema and seed working_hours if it doesn't exist yet."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(SCHEMA_SQL)
        cur = await db.execute("SELECT COUNT(*) FROM working_hours")
        row = await cur.fetchone()
        assert row is not None
        if row[0] == 0:
            await db.executemany(
                "INSERT INTO working_hours(weekday, start_hour, end_hour) VALUES (?, ?, ?)",
                [
                    (wd, w[0] if w else None, w[1] if w else None)
                    for wd, w in DEFAULT_WORKING_HOURS.items()
                ],
            )
        await db.commit()


async def seed_services(db_path: Path, seed_json: Path) -> int:
    """Insert services from the JSON seed if the table is empty. Returns count inserted."""
    if not seed_json.exists():
        return 0
    async with aiosqlite.connect(db_path) as db:
        cur = await db.execute("SELECT COUNT(*) FROM services")
        row = await cur.fetchone()
        assert row is not None
        if row[0] > 0:
            return 0
        with seed_json.open("r", encoding="utf-8") as f:
            services = json.load(f)
        await db.executemany(
            """INSERT INTO services
                 (slug, category, emoji, name, description, duration_minutes, price_rub, sort_order, active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
            [
                (
                    s["slug"],
                    s["category"],
                    s.get("emoji", ""),
                    s["name"],
                    s.get("description", ""),
                    int(s["duration_minutes"]),
                    int(s["price_rub"]),
                    int(s.get("sort_order", 0)),
                )
                for s in services
            ],
        )
        await db.commit()
        return len(services)


class ServicesRepo:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    async def list_active(self) -> list[Service]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM services WHERE active = 1 ORDER BY sort_order, id",
            )
            rows = await cur.fetchall()
            return [self._row(r) for r in rows]

    async def list_by_category(self, category: str) -> list[Service]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM services WHERE active = 1 AND category = ? ORDER BY sort_order, id",
                (category,),
            )
            rows = await cur.fetchall()
            return [self._row(r) for r in rows]

    async def get_by_id(self, service_id: int) -> Service | None:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM services WHERE id = ?", (service_id,))
            r = await cur.fetchone()
            return self._row(r) if r else None

    async def get_by_slug(self, slug: str) -> Service | None:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM services WHERE slug = ?", (slug,))
            r = await cur.fetchone()
            return self._row(r) if r else None

    @staticmethod
    def _row(r: aiosqlite.Row) -> Service:
        return Service(
            id=r["id"],
            slug=r["slug"],
            category=r["category"],
            emoji=r["emoji"],
            name=r["name"],
            description=r["description"],
            duration_minutes=r["duration_minutes"],
            price_rub=r["price_rub"],
            sort_order=r["sort_order"],
            active=bool(r["active"]),
        )


class WorkingHoursRepo:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    async def get_window_for_date(self, date_local: date) -> tuple[int, int] | None:
        """Return (start_hour, end_hour) or None if the day is off.

        `day_overrides` takes precedence over `working_hours` if present.
        """
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT start_hour, end_hour FROM day_overrides WHERE date_local = ?",
                (date_local.isoformat(),),
            )
            r = await cur.fetchone()
            if r is not None:
                if r["start_hour"] is None or r["end_hour"] is None:
                    return None
                return (int(r["start_hour"]), int(r["end_hour"]))

            cur = await db.execute(
                "SELECT start_hour, end_hour FROM working_hours WHERE weekday = ?",
                (date_local.weekday(),),
            )
            r = await cur.fetchone()
            if r is None or r["start_hour"] is None or r["end_hour"] is None:
                return None
            return (int(r["start_hour"]), int(r["end_hour"]))


class BookingsRepo:
    def __init__(self, db_path: Path, buffer_after_minutes: int) -> None:
        self._db_path = db_path
        self._buffer = timedelta(minutes=buffer_after_minutes)

    async def list_confirmed_in_range(
        self, start_utc: datetime, end_utc: datetime,
    ) -> list[tuple[datetime, datetime]]:
        """Return `[(start_at_utc, end_at_utc)]` of confirmed bookings whose
        REAL window intersects `[start_utc, end_utc)`."""
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """SELECT start_at_utc, end_at_utc FROM bookings
                   WHERE status = 'confirmed'
                     AND start_at_utc < ?
                     AND end_at_utc > ?
                   ORDER BY start_at_utc""",
                (_iso(end_utc), _iso(start_utc)),
            )
            rows = await cur.fetchall()
            return [(_parse_iso(r["start_at_utc"]), _parse_iso(r["end_at_utc"])) for r in rows]

    async def list_for_user(self, user_tg_id: int, limit: int = 20) -> list[Booking]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """SELECT * FROM bookings
                   WHERE user_tg_id = ?
                   ORDER BY start_at_utc DESC
                   LIMIT ?""",
                (user_tg_id, limit),
            )
            rows = await cur.fetchall()
            return [self._row(r) for r in rows]

    async def list_admin(self, limit: int, offset: int) -> tuple[list[Booking], int]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT COUNT(*) AS c FROM bookings")
            cnt_row = await cur.fetchone()
            total = int(cnt_row["c"]) if cnt_row else 0
            cur = await db.execute(
                """SELECT * FROM bookings
                   ORDER BY start_at_utc DESC
                   LIMIT ? OFFSET ?""",
                (limit, offset),
            )
            rows = await cur.fetchall()
            return [self._row(r) for r in rows], total

    async def get_by_id(self, booking_id: int) -> Booking | None:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,))
            r = await cur.fetchone()
            return self._row(r) if r else None

    async def stats(self, now_utc: datetime | None = None) -> dict[str, int]:
        """Return {confirmed_upcoming, completed_total, cancelled_total, no_show_total, revenue_completed_rub}.

        `now_utc` is injectable for deterministic tests; production callers omit
        it and we fall back to the real wall clock.
        """
        now_iso = _iso(now_utc if now_utc is not None else datetime.now(UTC))
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            res: dict[str, int] = {}
            cur = await db.execute(
                "SELECT COUNT(*) AS c FROM bookings WHERE status = 'confirmed' AND start_at_utc >= ?",
                (now_iso,),
            )
            r = await cur.fetchone()
            res["confirmed_upcoming"] = int(r["c"]) if r else 0

            for key, sql in (
                ("completed_total", "SELECT COUNT(*) AS c FROM bookings WHERE status = 'completed'"),
                ("cancelled_total", "SELECT COUNT(*) AS c FROM bookings WHERE status = 'cancelled'"),
                ("no_show_total", "SELECT COUNT(*) AS c FROM bookings WHERE status = 'no_show'"),
            ):
                cur = await db.execute(sql)
                r = await cur.fetchone()
                res[key] = int(r["c"]) if r else 0

            cur = await db.execute(
                "SELECT COALESCE(SUM(service_price_rub_snapshot),0) AS s FROM bookings WHERE status = 'completed'"
            )
            r = await cur.fetchone()
            res["revenue_completed_rub"] = int(r["s"]) if r else 0
            return res

    async def create_with_overlap_check(
        self,
        *,
        user_tg_id: int,
        user_full_name: str,
        user_phone: str | None,
        user_username: str | None,
        service: Service,
        start_at_utc: datetime,
        end_at_utc: datetime,
        now_utc: datetime,
    ) -> int:
        """Insert a booking inside `BEGIN IMMEDIATE`, rechecking overlaps WITH the
        30-min buffer applied to existing bookings. Raises `SlotConflict` on conflict.

        The overlap check is done in Python (not SQL) so we can reuse the exact
        semi-open interval math from `slots.available_starts` and avoid SQLite
        datetime() corner cases with timezone-suffixed ISO strings.
        """
        async with aiosqlite.connect(self._db_path, isolation_level=None) as db:
            db.row_factory = aiosqlite.Row
            try:
                await db.execute("BEGIN IMMEDIATE")
                cur = await db.execute(
                    """SELECT id, start_at_utc, end_at_utc FROM bookings
                       WHERE status = 'confirmed'
                       ORDER BY start_at_utc""",
                )
                rows = await cur.fetchall()
                for r in rows:
                    b_start = _parse_iso(r["start_at_utc"])
                    b_end = _parse_iso(r["end_at_utc"])
                    if start_at_utc < (b_end + self._buffer) and end_at_utc > b_start:
                        await db.execute("ROLLBACK")
                        raise SlotConflict(f"Slot conflict with booking #{r['id']}")

                cur = await db.execute(
                    """INSERT INTO bookings(
                            user_tg_id, user_full_name, user_phone, user_username,
                            service_id, start_at_utc, end_at_utc,
                            service_duration_minutes_snapshot, service_price_rub_snapshot,
                            service_name_snapshot, service_emoji_snapshot,
                            status, created_at_utc
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'confirmed', ?)""",
                    (
                        user_tg_id, user_full_name, user_phone, user_username,
                        service.id, _iso(start_at_utc), _iso(end_at_utc),
                        service.duration_minutes, service.price_rub,
                        service.name, service.emoji,
                        _iso(now_utc),
                    ),
                )
                booking_id = cur.lastrowid
                assert booking_id is not None
                await db.execute("COMMIT")
                return int(booking_id)
            except sqlite3.OperationalError:
                try:
                    await db.execute("ROLLBACK")
                except sqlite3.OperationalError:
                    pass
                raise

    async def cancel(self, booking_id: int) -> bool:
        async with aiosqlite.connect(self._db_path) as db:
            cur = await db.execute(
                """UPDATE bookings
                   SET status = 'cancelled', cancelled_at_utc = ?
                   WHERE id = ? AND status = 'confirmed'""",
                (_iso(datetime.now(UTC)), booking_id),
            )
            await db.commit()
            return (cur.rowcount or 0) > 0

    async def mark_completed(self, booking_id: int) -> bool:
        async with aiosqlite.connect(self._db_path) as db:
            cur = await db.execute(
                """UPDATE bookings
                   SET status = 'completed', completed_at_utc = ?
                   WHERE id = ? AND status = 'confirmed'""",
                (_iso(datetime.now(UTC)), booking_id),
            )
            await db.commit()
            return (cur.rowcount or 0) > 0

    async def mark_no_show(self, booking_id: int) -> bool:
        async with aiosqlite.connect(self._db_path) as db:
            cur = await db.execute(
                """UPDATE bookings
                   SET status = 'no_show'
                   WHERE id = ? AND status = 'confirmed'""",
                (booking_id,),
            )
            await db.commit()
            return (cur.rowcount or 0) > 0

    async def list_due_reminders(self, kind: str, offset_hours: int) -> list[Booking]:
        """Confirmed bookings whose start is within `offset_hours` from now and
        for which no `kind` reminder has been sent yet."""
        now = datetime.now(UTC)
        cutoff = now + timedelta(hours=offset_hours)
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """SELECT b.* FROM bookings b
                   WHERE b.status = 'confirmed'
                     AND b.start_at_utc > ?
                     AND b.start_at_utc <= ?
                     AND NOT EXISTS (
                         SELECT 1 FROM reminders_sent r
                         WHERE r.booking_id = b.id AND r.kind = ?
                     )
                   ORDER BY b.start_at_utc""",
                (_iso(now), _iso(cutoff), kind),
            )
            rows = await cur.fetchall()
            return [self._row(r) for r in rows]

    async def mark_reminder_sent(self, booking_id: int, kind: str) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO reminders_sent(booking_id, kind, sent_at_utc) VALUES (?, ?, ?)",
                (booking_id, kind, _iso(datetime.now(UTC))),
            )
            await db.commit()

    @staticmethod
    def _row(r: aiosqlite.Row) -> Booking:
        return Booking(
            id=r["id"],
            user_tg_id=r["user_tg_id"],
            user_full_name=r["user_full_name"],
            user_phone=r["user_phone"],
            user_username=r["user_username"],
            service_id=r["service_id"],
            start_at_utc=_parse_iso(r["start_at_utc"]),
            end_at_utc=_parse_iso(r["end_at_utc"]),
            service_duration_minutes_snapshot=r["service_duration_minutes_snapshot"],
            service_price_rub_snapshot=r["service_price_rub_snapshot"],
            service_name_snapshot=r["service_name_snapshot"],
            service_emoji_snapshot=r["service_emoji_snapshot"],
            status=r["status"],
            created_at_utc=_parse_iso(r["created_at_utc"]),
        )


def bookings_to_csv(bookings: list[Booking], tz_name: str) -> str:
    """Render a CSV with bookings sorted by start_at_utc desc."""
    from csv import writer
    from io import StringIO
    from zoneinfo import ZoneInfo

    from .timez import from_utc

    buf = StringIO()
    w = writer(buf)
    w.writerow([
        "id", "status", "start_local", "end_local",
        "service", "duration_min", "price_rub",
        "user_full_name", "user_phone", "user_username",
        "created_local",
    ])
    tz = ZoneInfo(tz_name)
    for b in bookings:
        start_local = from_utc(b.start_at_utc, tz)
        end_local = from_utc(b.end_at_utc, tz)
        created_local = from_utc(b.created_at_utc, tz)
        w.writerow([
            b.id, b.status,
            start_local.strftime("%Y-%m-%d %H:%M"),
            end_local.strftime("%Y-%m-%d %H:%M"),
            b.service_name_snapshot,
            b.service_duration_minutes_snapshot,
            b.service_price_rub_snapshot,
            b.user_full_name,
            b.user_phone or "",
            b.user_username or "",
            created_local.strftime("%Y-%m-%d %H:%M"),
        ])
    return buf.getvalue()
