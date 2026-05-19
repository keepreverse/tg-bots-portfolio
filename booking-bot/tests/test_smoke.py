"""Top-level smoke checks: the dispatcher assembles, scheduler builds, config parses."""

from __future__ import annotations

from pathlib import Path

import pytest

from booking_bot.bot import build_dispatcher
from booking_bot.config import Settings


def _fake_env(tmp_path: Path) -> dict[str, str]:
    return {
        "BOT_TOKEN": "0:TEST_TOKEN_ABCDEFGHIJ",
        "ADMIN_CHAT_ID": "111",
        "MASTER_TZ": "Europe/Moscow",
        "SLOT_STEP_MINUTES": "60",
        "BOOKING_BUFFER_AFTER_MINUTES": "30",
        "BOOKING_HORIZON_DAYS": "30",
        "REMINDER_OFFSETS_HOURS": "24,2",
        "DB_PATH": str(tmp_path / "smoke.db"),
    }


def test_settings_parse_minimum(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for k, v in _fake_env(tmp_path).items():
        monkeypatch.setenv(k, v)
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.SLOT_STEP_MINUTES == 60
    assert s.BOOKING_BUFFER_AFTER_MINUTES == 30
    assert s.BOOKING_HORIZON_DAYS == 30
    assert s.reminder_offsets_hours == [24, 2]
    assert s.master_tz.key == "Europe/Moscow"


def test_settings_rejects_step_other_than_60(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    env = _fake_env(tmp_path)
    env["SLOT_STEP_MINUTES"] = "30"
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    with pytest.raises(Exception, match="SLOT_STEP_MINUTES"):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_settings_rejects_negative_buffer(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    env = _fake_env(tmp_path)
    env["BOOKING_BUFFER_AFTER_MINUTES"] = "-30"
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    with pytest.raises(Exception, match="BOOKING_BUFFER_AFTER_MINUTES"):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_dispatcher_builds(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for k, v in _fake_env(tmp_path).items():
        monkeypatch.setenv(k, v)
    # Force settings cache reset
    import booking_bot.config as cfg
    cfg._settings = None  # type: ignore[attr-defined]
    dp = build_dispatcher()
    # 4 routers registered (menu, booking, my_bookings, admin)
    assert len(dp.sub_routers) == 4


def test_env_example_exists() -> None:
    repo = Path(__file__).resolve().parents[1]
    assert (repo / ".env.example").is_file()
    assert (repo / "data" / "seed_services.json").is_file()


def test_pyproject_has_console_script() -> None:
    repo = Path(__file__).resolve().parents[1]
    content = (repo / "pyproject.toml").read_text(encoding="utf-8")
    assert "booking-bot = " in content
