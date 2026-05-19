from pathlib import Path

import pytest

from lead_bot.db import LeadsRepo, leads_to_csv


@pytest.mark.asyncio
async def test_add_count_export(tmp_path: Path) -> None:
    repo = LeadsRepo(tmp_path / "leads.db")
    await repo.init()
    assert await repo.count() == 0

    lead_id = await repo.add(
        tg_user_id=100,
        tg_username="vasya",
        name="Вася",
        phone="+79991234567",
        service="Консультация",
        comment="Привет",
    )
    assert lead_id == 1

    lead_id2 = await repo.add(
        tg_user_id=101,
        tg_username=None,
        name="Аноним",
        phone="+79990000000",
        service="Заказ под ключ",
        comment=None,
    )
    assert lead_id2 == 2
    assert await repo.count() == 2

    leads = await repo.all()
    assert [lead.id for lead in leads] == [1, 2]
    assert leads[0].name == "Вася"
    assert leads[1].comment is None

    csv_bytes = leads_to_csv(leads)
    # BOM + header should be present, plus two data rows.
    text = csv_bytes.decode("utf-8-sig")
    lines = text.strip().splitlines()
    assert len(lines) == 3
    assert lines[0].startswith("id,")
    assert "Вася" in lines[1]
    assert "Аноним" in lines[2]


@pytest.mark.asyncio
async def test_count_since(tmp_path: Path) -> None:
    repo = LeadsRepo(tmp_path / "leads.db")
    await repo.init()
    await repo.add(
        tg_user_id=1,
        tg_username=None,
        name="X",
        phone="+70000000000",
        service="A",
        comment=None,
    )
    # Empty CSV when no leads selected via filter (manually-built window in the future).
    assert await repo.count_since("1900-01-01T00:00:00+00:00") == 1
    assert await repo.count_since("9999-01-01T00:00:00+00:00") == 0
