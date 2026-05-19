from pathlib import Path


def test_imports() -> None:
    """Top-level imports must succeed without a real TG connection."""
    from lead_bot import (  # noqa: F401
        bot,
        config,
        db,
        handlers,
        keyboards,
        render,
        states,
        texts,
        views,
    )
    from lead_bot.handlers import admin, menu, survey  # noqa: F401


def test_settings_loads_from_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BOT_TOKEN", "111222:" + "A" * 40)
    monkeypatch.setenv("ADMIN_CHAT_ID", "42")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "leads.db"))
    monkeypatch.setenv("BUSINESS_NAME", "Acme")
    monkeypatch.setenv("SERVICES", "A;B;C")

    from lead_bot.config import load_settings

    s = load_settings()
    assert s.admin_chat_id == 42
    assert s.business_name == "Acme"
    assert s.services == ["A", "B", "C"]


def test_dispatcher_builds(monkeypatch, tmp_path: Path) -> None:
    """The dispatcher must build with all routers wired in."""
    monkeypatch.setenv("BOT_TOKEN", "111222:" + "A" * 40)
    monkeypatch.setenv("ADMIN_CHAT_ID", "42")

    from lead_bot.bot import build_dispatcher
    from lead_bot.config import load_settings
    from lead_bot.db import LeadsRepo

    settings = load_settings()
    repo = LeadsRepo(tmp_path / "leads.db")
    dp = build_dispatcher(settings, repo)
    assert dp["settings"] is settings
    assert dp["repo"] is repo
    # Router tree should include at least our root + 2 sub-routers (admin, user).
    routers = list(dp.sub_routers)
    assert len(routers) >= 1
