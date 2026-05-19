"""SQLite schema + repositories for the quiz-bot.

Two main tables:

* `quiz_events` — every step the user reached. Used for the conversion-funnel
  analytics ("90% reach question 1, 75% reach question 2…"). Lightweight
  per-event row, indexed by (category_key, question_index).
* `leads` — captured contacts after the quiz, with the calculated price range
  and the answers snapshot (JSON) for the admin DM and CSV export.

`init_db()` creates both tables idempotently. There are no migrations beyond
"CREATE TABLE IF NOT EXISTS" — schema is small enough that we keep it inline.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite

SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS quiz_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_tg_id INTEGER NOT NULL,
    category_key TEXT NOT NULL,
    event_kind TEXT NOT NULL CHECK (event_kind IN ('start','step','result','lead')),
    step_index INTEGER NOT NULL DEFAULT -1,
    created_at_utc TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_quiz_events_cat
    ON quiz_events(category_key, event_kind);
CREATE INDEX IF NOT EXISTS idx_quiz_events_user
    ON quiz_events(user_tg_id, created_at_utc);

CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_tg_id INTEGER NOT NULL,
    user_username TEXT,
    category_key TEXT NOT NULL,
    category_title TEXT NOT NULL,
    answers_json TEXT NOT NULL,
    price_min INTEGER NOT NULL,
    price_max INTEGER NOT NULL,
    price_unit_label TEXT NOT NULL DEFAULT '',
    full_name TEXT NOT NULL,
    phone TEXT NOT NULL,
    created_at_utc TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_leads_created
    ON leads(created_at_utc DESC);
CREATE INDEX IF NOT EXISTS idx_leads_category
    ON leads(category_key);
"""


@dataclass(frozen=True)
class Lead:
    id: int
    user_tg_id: int
    user_username: str | None
    category_key: str
    category_title: str
    answers_json: str
    price_min: int
    price_max: int
    price_unit_label: str
    full_name: str
    phone: str
    created_at_utc: datetime


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat()


def _parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s).astimezone(UTC)


async def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(SCHEMA_SQL)
        await db.commit()


# ---------------------------------------------------------------------------
# Events repo: funnel analytics
# ---------------------------------------------------------------------------


class EventsRepo:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    async def log(
        self,
        *,
        user_tg_id: int,
        category_key: str,
        event_kind: str,
        step_index: int = -1,
    ) -> int:
        """Append a single event row. Returns the inserted row id."""
        now = _iso(datetime.now(UTC))
        async with aiosqlite.connect(self._db_path) as db:
            cur = await db.execute(
                "INSERT INTO quiz_events(user_tg_id, category_key, event_kind, step_index, created_at_utc)"
                " VALUES (?, ?, ?, ?, ?)",
                (user_tg_id, category_key, event_kind, step_index, now),
            )
            await db.commit()
            return cur.lastrowid or 0

    async def funnel(self, category_key: str, total_steps: int) -> list[dict[str, int]]:
        """Per-step counters for the funnel screen.

        Returns a list of dicts: ``[{"step_index": int, "passed": int}, ...]``
        where `passed` is how many UNIQUE users reached *at least* that step
        (i.e. logged a `step` event for that index or higher) inside the
        given category. Useful for "% reached" calculations.
        """
        result: list[dict[str, int]] = []
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            for step in range(total_steps):
                cur = await db.execute(
                    "SELECT COUNT(DISTINCT user_tg_id) AS n FROM quiz_events"
                    " WHERE category_key = ? AND event_kind = 'step' AND step_index >= ?",
                    (category_key, step),
                )
                r = await cur.fetchone()
                result.append({"step_index": step, "passed": int(r["n"]) if r else 0})
        return result

    async def overall_stats(self) -> dict[str, int]:
        """Global stats across all categories (used by /admin → 📊 Статистика)."""
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row

            def _count(kind: str) -> tuple[str, tuple[str]]:
                return (
                    "SELECT COUNT(DISTINCT user_tg_id) FROM quiz_events WHERE event_kind = ?",
                    (kind,),
                )

            starts_q, starts_p = _count("start")
            results_q, results_p = _count("result")
            leads_q, leads_p = _count("lead")
            (starts,) = (await (await db.execute(starts_q, starts_p)).fetchone()) or (0,)
            (results,) = (await (await db.execute(results_q, results_p)).fetchone()) or (0,)
            (leads,) = (await (await db.execute(leads_q, leads_p)).fetchone()) or (0,)
        return {"starts": int(starts), "completed": int(results), "leads": int(leads)}


# ---------------------------------------------------------------------------
# Leads repo
# ---------------------------------------------------------------------------


class LeadsRepo:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    async def create(
        self,
        *,
        user_tg_id: int,
        user_username: str | None,
        category_key: str,
        category_title: str,
        answers: list[tuple[str, str, str, str]],
        price_min: int,
        price_max: int,
        price_unit_label: str,
        full_name: str,
        phone: str,
    ) -> int:
        """Insert a new lead. `answers` is a list of
        ``(question_key, question_title, option_key, option_label)`` tuples,
        stored as JSON for traceability and later CSV export.
        """
        now = _iso(datetime.now(UTC))
        async with aiosqlite.connect(self._db_path) as db:
            cur = await db.execute(
                """INSERT INTO leads
                    (user_tg_id, user_username, category_key, category_title,
                     answers_json, price_min, price_max, price_unit_label,
                     full_name, phone, created_at_utc)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    user_tg_id,
                    user_username,
                    category_key,
                    category_title,
                    json.dumps(answers, ensure_ascii=False),
                    int(price_min),
                    int(price_max),
                    price_unit_label,
                    full_name,
                    phone,
                    now,
                ),
            )
            await db.commit()
            return cur.lastrowid or 0

    async def list_recent(self, *, limit: int, offset: int) -> tuple[list[Lead], int]:
        """Return (leads page, total count)."""
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            (total,) = (await (await db.execute("SELECT COUNT(*) FROM leads")).fetchone()) or (0,)
            cur = await db.execute(
                "SELECT * FROM leads ORDER BY datetime(created_at_utc) DESC, id DESC"
                " LIMIT ? OFFSET ?",
                (limit, offset),
            )
            rows = await cur.fetchall()
            return [self._row(r) for r in rows], int(total)

    async def export_all(self) -> list[Lead]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM leads ORDER BY datetime(created_at_utc) ASC",
            )
            rows = await cur.fetchall()
            return [self._row(r) for r in rows]

    @staticmethod
    def _row(r: aiosqlite.Row) -> Lead:
        return Lead(
            id=r["id"],
            user_tg_id=r["user_tg_id"],
            user_username=r["user_username"],
            category_key=r["category_key"],
            category_title=r["category_title"],
            answers_json=r["answers_json"],
            price_min=int(r["price_min"]),
            price_max=int(r["price_max"]),
            price_unit_label=r["price_unit_label"],
            full_name=r["full_name"],
            phone=r["phone"],
            created_at_utc=_parse_iso(r["created_at_utc"]),
        )


def leads_to_csv(leads: list[Lead]) -> bytes:
    """UTF-8 BOM CSV (so Excel doesn't mangle Cyrillic)."""
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    writer.writerow([
        "id",
        "created_at_utc",
        "category",
        "price_min",
        "price_max",
        "price_unit",
        "full_name",
        "phone",
        "user_tg_id",
        "user_username",
        "answers_json",
    ])
    for lead in leads:
        writer.writerow([
            lead.id,
            lead.created_at_utc.isoformat(),
            lead.category_title,
            lead.price_min,
            lead.price_max,
            lead.price_unit_label,
            lead.full_name,
            lead.phone,
            lead.user_tg_id,
            lead.user_username or "",
            lead.answers_json,
        ])
    return ("\ufeff" + buf.getvalue()).encode("utf-8")
