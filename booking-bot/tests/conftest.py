"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio

from booking_bot.db import init_db, seed_services


@pytest_asyncio.fixture
async def db_path(tmp_path: Path) -> AsyncIterator[Path]:
    """Initialise an empty SQLite database with the booking-bot schema."""
    p = tmp_path / "booking.db"
    await init_db(p)
    yield p


@pytest_asyncio.fixture
async def seeded_db_path(db_path: Path) -> AsyncIterator[Path]:
    """SQLite DB with the schema AND the 12-service seed loaded."""
    seed_json = Path(__file__).resolve().parents[1] / "data" / "seed_services.json"
    await seed_services(db_path, seed_json)
    yield db_path
