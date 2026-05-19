"""High-level handler wiring smoke tests.

Validates that the routers can be built and the dispatcher contains the
expected route count, that callback data shapes line up with handler filters,
and that the admin DM body is well-formed.
"""

from __future__ import annotations

from types import SimpleNamespace

from quiz_bot.bot import build_dispatcher
from quiz_bot.handlers import build_all_routers
from quiz_bot.handlers.admin import _leads_word
from quiz_bot.handlers.quiz import build_lead_summary_for_admin
from quiz_bot.quiz_engine import QuizProgress, load_quiz_config


def test_routers_constructable(seed_quiz_path) -> None:
    cfg = load_quiz_config(seed_quiz_path)
    routers = build_all_routers(config=cfg)
    names = [r.name for r in routers]
    assert names == ["menu", "quiz", "admin", "fallback"]


def test_dispatcher_can_be_built(seed_quiz_path) -> None:
    cfg = load_quiz_config(seed_quiz_path)
    dp = build_dispatcher(cfg)
    # Each sub-router should be included.
    sub_names = sorted(r.name for r in dp.sub_routers)
    assert "menu" in sub_names
    assert "quiz" in sub_names
    assert "admin" in sub_names
    assert "fallback" in sub_names


def test_lead_summary_renders_known_answers(seed_quiz_path) -> None:
    cfg = load_quiz_config(seed_quiz_path)
    cat = cfg.category_by_key("renovation")
    progress = (
        QuizProgress(category_key=cat.key)
        .with_answer("type", "capital")
        .with_answer("area", "40_60")
    )
    body = build_lead_summary_for_admin(cat, progress)
    assert "Ремонт" in body
    assert "Капитальный" in body
    assert "40–60" in body


def test_lead_summary_skips_unknown_answers(seed_quiz_path) -> None:
    """If somebody hand-edits FSM state, unknown q/opt keys must be ignored."""
    cfg = load_quiz_config(seed_quiz_path)
    cat = cfg.category_by_key("renovation")
    progress = (
        QuizProgress(category_key=cat.key)
        .with_answer("unknown", "bogus")
        .with_answer("type", "cosmetic")
    )
    body = build_lead_summary_for_admin(cat, progress)
    assert "bogus" not in body
    assert "Косметический" in body


def test_lead_summary_empty_progress(seed_quiz_path) -> None:
    cfg = load_quiz_config(seed_quiz_path)
    cat = cfg.category_by_key("renovation")
    body = build_lead_summary_for_admin(cat, QuizProgress(category_key=cat.key))
    # Just the category header, no answer lines.
    assert body.count("\n") == 0
    assert "Ремонт" in body


def test_pluralisation_of_leads_word() -> None:
    assert _leads_word(0) == "лидов"
    assert _leads_word(1) == "лид"
    assert _leads_word(2) == "лида"
    assert _leads_word(3) == "лида"
    assert _leads_word(4) == "лида"
    assert _leads_word(5) == "лидов"
    assert _leads_word(11) == "лидов"
    assert _leads_word(12) == "лидов"
    assert _leads_word(13) == "лидов"
    assert _leads_word(14) == "лидов"
    assert _leads_word(21) == "лид"
    assert _leads_word(22) == "лида"
    assert _leads_word(25) == "лидов"
    assert _leads_word(101) == "лид"


def test_money_format_range_same_value() -> None:
    from quiz_bot.money import format_range
    s = format_range(100, 100, currency="₽", unit_suffix="")
    assert "100" in s
    assert " — " not in s


def test_money_format_range_distinct() -> None:
    from quiz_bot.money import format_range
    s = format_range(1500, 3000, currency="₽", unit_suffix=" / мес")
    assert "1 500" in s
    assert "3 000" in s
    assert " / мес" in s


def test_money_format_price_thin_space_thousands() -> None:
    """We want NBSP/thin-space-as-thousands-sep (not '1,500')."""
    from quiz_bot.money import format_price
    s = format_price(1_500_000, currency="₽", unit_suffix="")
    assert "1 500 000" in s or "1\u00a0500\u00a0000" in s


def test_config_settings_load_from_env(monkeypatch) -> None:
    from quiz_bot.config import Settings
    monkeypatch.setenv("BOT_TOKEN", "987654321:ABCDEFGHIJKLMNOPQRSTUVWXYZ123456")
    monkeypatch.setenv("ADMIN_CHAT_ID", "777")
    monkeypatch.setenv("BUSINESS_NAME", "X")
    monkeypatch.setenv("MASTER_HANDLE", "@boss")
    s = Settings()
    assert s.ADMIN_CHAT_ID == 777
    assert s.BUSINESS_NAME == "X"
    # Leading @ should be stripped/preserved consistently — check the helper.
    assert s.master_handle_username == "boss"
    assert s.master_telegram_url == "https://t.me/boss"


def test_callback_prefixes_unique() -> None:
    """Sanity guard: the set of CB_* constants must be unique strings."""
    from quiz_bot import keyboards as kbs
    cb_values = [
        v for k, v in vars(kbs).items()
        if k.startswith("CB_") and isinstance(v, str)
    ]
    assert len(cb_values) == len(set(cb_values))


def test_quiz_states_have_expected_names() -> None:
    from quiz_bot.states import QuizFlow
    names = {s.state for s in QuizFlow.__states__}
    assert "QuizFlow:answering" in names
    assert "QuizFlow:ask_name" in names
    assert "QuizFlow:ask_phone" in names
    assert "QuizFlow:show_result" in names


# A tiny standalone check: when we have no `from_user`, helper still works.
def test_is_admin_with_none_user() -> None:
    from quiz_bot.handlers.menu import is_admin
    settings = SimpleNamespace(ADMIN_CHAT_ID=1)
    assert is_admin(None, settings) is False  # type: ignore[arg-type]
    assert is_admin(1, settings) is True       # type: ignore[arg-type]
    assert is_admin(2, settings) is False      # type: ignore[arg-type]
