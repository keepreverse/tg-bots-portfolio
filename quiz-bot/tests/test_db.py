"""DB layer tests: schema, leads CRUD, funnel events, CSV export."""

from __future__ import annotations

from pathlib import Path

import pytest

from quiz_bot.db import EventsRepo, LeadsRepo, init_db, leads_to_csv


@pytest.fixture
async def db_path(tmp_path: Path) -> Path:
    p = tmp_path / "quiz.db"
    await init_db(p)
    return p


async def test_init_db_creates_tables(db_path: Path) -> None:
    import aiosqlite
    async with aiosqlite.connect(db_path) as db:
        cur = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        names = sorted(r[0] for r in await cur.fetchall())
        assert "leads" in names
        assert "quiz_events" in names


async def test_events_log_persists(db_path: Path) -> None:
    repo = EventsRepo(db_path)
    rid = await repo.log(
        user_tg_id=42,
        category_key="renovation",
        event_kind="start",
    )
    assert rid > 0


async def test_overall_stats_counts_distinct_users(db_path: Path) -> None:
    repo = EventsRepo(db_path)
    # 2 users, 2 starts (one of them duplicated), 1 result, 1 lead
    await repo.log(user_tg_id=10, category_key="x", event_kind="start")
    await repo.log(user_tg_id=10, category_key="x", event_kind="start")
    await repo.log(user_tg_id=20, category_key="x", event_kind="start")
    await repo.log(user_tg_id=10, category_key="x", event_kind="result")
    await repo.log(user_tg_id=10, category_key="x", event_kind="lead")
    stats = await repo.overall_stats()
    assert stats["starts"] == 2
    assert stats["completed"] == 1
    assert stats["leads"] == 1


async def test_funnel_counts_per_step(db_path: Path) -> None:
    repo = EventsRepo(db_path)
    # 3 users start, 2 reach step 2, 1 reaches step 3.
    for uid in (1, 2, 3):
        await repo.log(user_tg_id=uid, category_key="r", event_kind="start")
        await repo.log(user_tg_id=uid, category_key="r", event_kind="step", step_index=0)
    for uid in (1, 2):
        await repo.log(user_tg_id=uid, category_key="r", event_kind="step", step_index=1)
        await repo.log(user_tg_id=uid, category_key="r", event_kind="step", step_index=2)
    await repo.log(user_tg_id=1, category_key="r", event_kind="step", step_index=3)
    funnel = await repo.funnel(category_key="r", total_steps=4)
    assert funnel[0]["passed"] == 3
    assert funnel[1]["passed"] == 2
    assert funnel[2]["passed"] == 2
    assert funnel[3]["passed"] == 1


async def test_leads_create_and_list(db_path: Path) -> None:
    repo = LeadsRepo(db_path)
    rid = await repo.create(
        user_tg_id=1001,
        user_username="alice",
        category_key="renovation",
        category_title="Ремонт квартиры под ключ",
        answers=[("type", "Тип", "capital", "Капитальный")],
        price_min=100_000,
        price_max=200_000,
        price_unit_label="",
        full_name="Алиса",
        phone="+79991112233",
    )
    assert rid > 0
    leads, total = await repo.list_recent(limit=5, offset=0)
    assert total == 1
    assert len(leads) == 1
    assert leads[0].id == rid
    assert leads[0].full_name == "Алиса"
    assert leads[0].price_max == 200_000


async def test_leads_pagination(db_path: Path) -> None:
    repo = LeadsRepo(db_path)
    for i in range(7):
        await repo.create(
            user_tg_id=i,
            user_username=None,
            category_key="x",
            category_title="X",
            answers=[],
            price_min=i,
            price_max=i + 10,
            price_unit_label="",
            full_name=f"name{i}",
            phone=f"+7999000000{i}",
        )
    page1, total1 = await repo.list_recent(limit=5, offset=0)
    page2, total2 = await repo.list_recent(limit=5, offset=5)
    assert total1 == total2 == 7
    assert len(page1) == 5
    assert len(page2) == 2


async def test_leads_recent_sorted_desc(db_path: Path) -> None:
    repo = LeadsRepo(db_path)
    ids = []
    for i in range(3):
        rid = await repo.create(
            user_tg_id=i,
            user_username=None,
            category_key="x",
            category_title="X",
            answers=[],
            price_min=0,
            price_max=0,
            price_unit_label="",
            full_name=f"n{i}",
            phone=f"+7999000000{i}",
        )
        ids.append(rid)
    leads, _ = await repo.list_recent(limit=10, offset=0)
    # Most recently inserted should come first.
    assert leads[0].id == ids[-1]


async def test_leads_to_csv_has_utf8_bom(db_path: Path) -> None:
    repo = LeadsRepo(db_path)
    await repo.create(
        user_tg_id=1,
        user_username="alice",
        category_key="x",
        category_title="X",
        answers=[("q", "Q", "a", "A")],
        price_min=100,
        price_max=200,
        price_unit_label="",
        full_name="Алиса",
        phone="+79991112233",
    )
    leads = await repo.export_all()
    csv_bytes = leads_to_csv(leads)
    assert csv_bytes.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM
    decoded = csv_bytes.decode("utf-8")
    assert "Алиса" in decoded
    assert "+79991112233" in decoded


async def test_leads_export_all_empty(db_path: Path) -> None:
    repo = LeadsRepo(db_path)
    leads = await repo.export_all()
    assert leads == []


async def test_leads_csv_includes_answers_json(db_path: Path) -> None:
    repo = LeadsRepo(db_path)
    await repo.create(
        user_tg_id=1,
        user_username=None,
        category_key="tutor",
        category_title="Репетитор",
        answers=[("subject", "Предмет", "english", "🇬🇧 Английский")],
        price_min=10_000,
        price_max=20_000,
        price_unit_label=" / мес",
        full_name="Ученик",
        phone="+79991234567",
    )
    leads = await repo.export_all()
    csv_text = leads_to_csv(leads).decode("utf-8")
    assert "🇬🇧" in csv_text
    assert "english" in csv_text
    assert " / мес" in csv_text


async def test_funnel_empty_category_returns_zero_counts(db_path: Path) -> None:
    repo = EventsRepo(db_path)
    funnel = await repo.funnel(category_key="empty", total_steps=3)
    assert [row["passed"] for row in funnel] == [0, 0, 0]
