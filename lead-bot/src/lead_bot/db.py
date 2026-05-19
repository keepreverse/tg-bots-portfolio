from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_user_id INTEGER NOT NULL,
    tg_username TEXT,
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    service TEXT NOT NULL,
    comment TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_leads_created_at ON leads(created_at);
"""


@dataclass(slots=True)
class Lead:
    id: int
    tg_user_id: int
    tg_username: str | None
    name: str
    phone: str
    service: str
    comment: str | None
    created_at: str


class LeadsRepo:
    """Tiny SQLite repository for leads. Async via aiosqlite."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    async def init(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(SCHEMA)
            await db.commit()

    async def add(
        self,
        *,
        tg_user_id: int,
        tg_username: str | None,
        name: str,
        phone: str,
        service: str,
        comment: str | None,
    ) -> int:
        created_at = datetime.now(UTC).isoformat(timespec="seconds")
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO leads (tg_user_id, tg_username, name, phone, service, comment, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (tg_user_id, tg_username, name, phone, service, comment, created_at),
            )
            await db.commit()
            return cursor.lastrowid or 0

    async def count(self) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM leads") as cur:
                row = await cur.fetchone()
                return int(row[0]) if row else 0

    async def count_since(self, since_iso: str) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT COUNT(*) FROM leads WHERE created_at >= ?", (since_iso,)
            ) as cur:
                row = await cur.fetchone()
                return int(row[0]) if row else 0

    async def all(self) -> list[Lead]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT id, tg_user_id, tg_username, name, phone, service, comment, created_at "
                "FROM leads ORDER BY id"
            ) as cur:
                rows = await cur.fetchall()
                return [
                    Lead(
                        id=row["id"],
                        tg_user_id=row["tg_user_id"],
                        tg_username=row["tg_username"],
                        name=row["name"],
                        phone=row["phone"],
                        service=row["service"],
                        comment=row["comment"],
                        created_at=row["created_at"],
                    )
                    for row in rows
                ]


def leads_to_csv(leads: list[Lead]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf, dialect="excel")
    writer.writerow(
        ["id", "tg_user_id", "tg_username", "name", "phone", "service", "comment", "created_at"]
    )
    for lead in leads:
        writer.writerow(
            [
                lead.id,
                lead.tg_user_id,
                lead.tg_username or "",
                lead.name,
                lead.phone,
                lead.service,
                lead.comment or "",
                lead.created_at,
            ]
        )
    return buf.getvalue().encode("utf-8-sig")
