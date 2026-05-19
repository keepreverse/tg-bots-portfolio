"""Render-layer tests: progress bar formatting, screen builders, keyboards."""

from __future__ import annotations

from pathlib import Path

from quiz_bot.keyboards import (
    CB_ADMIN,
    CB_ADMIN_FUNNEL,
    CB_ANSWER,
    CB_BACK,
    CB_CANCEL,
    CB_MAIN_MENU,
    CB_PICK_CAT,
    CB_RESTART,
    CB_RESULT_CTA,
    CB_START_QUIZ,
    CB_WARMUP_GO,
    CB_WARMUP_SKIP,
    admin_leads_kb,
)
from quiz_bot.quiz_engine import QuizProgress, calculate_price, load_quiz_config
from quiz_bot.views import (
    about_view,
    admin_funnel_picker_view,
    admin_funnel_view,
    admin_leads_view,
    admin_menu_view,
    admin_stats_view,
    ask_name_view,
    ask_phone_view,
    category_intro_view,
    category_picker_view,
    lead_done_view,
    main_menu_view,
    progress_bar,
    question_view,
    result_view,
    warmup_view,
)

# ---------------------------------------------------------------------------
# Progress bar
# ---------------------------------------------------------------------------


def test_progress_bar_first_step() -> None:
    s = progress_bar(0, 6)
    assert s.startswith("▰▱▱▱▱▱")
    assert "Шаг 1 из 6" in s


def test_progress_bar_last_step() -> None:
    s = progress_bar(5, 6)
    assert s.startswith("▰▰▰▰▰▰")
    assert "Шаг 6 из 6" in s


def test_progress_bar_overflow_clamped() -> None:
    s = progress_bar(10, 6)
    assert "Шаг 6 из 6" in s


# ---------------------------------------------------------------------------
# Main menu
# ---------------------------------------------------------------------------


def test_main_menu_multi_categories_has_start_button(seed_quiz_path: Path) -> None:
    cfg = load_quiz_config(seed_quiz_path)
    view = main_menu_view(config=cfg, business_name="X", is_admin=False)
    rendered = view.markup.inline_keyboard
    cb_data = [b.callback_data for row in rendered for b in row]
    assert f"{CB_START_QUIZ}:0" in cb_data


def test_main_menu_single_category_skips_picker() -> None:
    """When only one category exists, the start button enters it directly."""
    cfg = load_quiz_config(Path(__file__).resolve().parents[1] / "data" / "seed_quiz.json")
    # Synthesize a single-category config.
    from quiz_bot.quiz_engine import QuizConfig
    single = QuizConfig(
        version=cfg.version,
        currency_label=cfg.currency_label,
        categories=(cfg.categories[0],),
    )
    view = main_menu_view(config=single, business_name="Solo", is_admin=False)
    cb_data = [b.callback_data for row in view.markup.inline_keyboard for b in row]
    assert any(d.startswith(f"{CB_PICK_CAT}:") for d in cb_data)


def test_main_menu_admin_button_only_for_admin(seed_quiz_path: Path) -> None:
    cfg = load_quiz_config(seed_quiz_path)
    view_admin = main_menu_view(config=cfg, business_name="X", is_admin=True)
    view_user = main_menu_view(config=cfg, business_name="X", is_admin=False)
    cb_admin = [b.callback_data for row in view_admin.markup.inline_keyboard for b in row]
    cb_user = [b.callback_data for row in view_user.markup.inline_keyboard for b in row]
    assert f"{CB_ADMIN}:0" in cb_admin
    assert f"{CB_ADMIN}:0" not in cb_user


# ---------------------------------------------------------------------------
# Category picker / intro
# ---------------------------------------------------------------------------


def test_category_picker_has_button_per_category(seed_quiz_path: Path) -> None:
    cfg = load_quiz_config(seed_quiz_path)
    view = category_picker_view(cfg)
    cb_data = [b.callback_data for row in view.markup.inline_keyboard for b in row]
    assert f"{CB_PICK_CAT}:renovation" in cb_data
    assert f"{CB_PICK_CAT}:tutor" in cb_data
    assert f"{CB_MAIN_MENU}:0" in cb_data


def test_category_intro_has_go_button(seed_quiz_path: Path) -> None:
    cfg = load_quiz_config(seed_quiz_path)
    view = category_intro_view(cfg.categories[0], allow_back=True)
    cb_data = [b.callback_data for row in view.markup.inline_keyboard for b in row]
    assert any(d.startswith(f"{CB_PICK_CAT}:") and d.endswith(":go") for d in cb_data)
    assert f"{CB_BACK}:0" in cb_data
    assert f"{CB_CANCEL}:0" in cb_data


# ---------------------------------------------------------------------------
# Question screen
# ---------------------------------------------------------------------------


def test_question_view_renders_progress_and_buttons(seed_quiz_path: Path) -> None:
    cfg = load_quiz_config(seed_quiz_path)
    cat = cfg.categories[0]
    view = question_view(cat, cat.question_at(0), step_index=0, allow_back=False)
    assert "Шаг 1 из 6" in view.text
    cb_data = [b.callback_data for row in view.markup.inline_keyboard for b in row]
    # Each option becomes one button.
    for o in cat.question_at(0).options:
        assert f"{CB_ANSWER}:{o.key}" in cb_data
    # No back button on the first step.
    assert f"{CB_BACK}:0" not in cb_data
    assert f"{CB_CANCEL}:0" in cb_data


def test_question_view_back_button_on_second_step(seed_quiz_path: Path) -> None:
    cfg = load_quiz_config(seed_quiz_path)
    cat = cfg.categories[0]
    view = question_view(cat, cat.question_at(1), step_index=1, allow_back=True)
    cb_data = [b.callback_data for row in view.markup.inline_keyboard for b in row]
    assert f"{CB_BACK}:0" in cb_data


# ---------------------------------------------------------------------------
# Warmup screen
# ---------------------------------------------------------------------------


def test_warmup_view_shows_current_range(seed_quiz_path: Path) -> None:
    cfg = load_quiz_config(seed_quiz_path)
    cat = cfg.categories[0]  # renovation
    progress = (
        QuizProgress(category_key=cat.key)
        .with_answer("type", "cosmetic")
        .with_answer("area", "to40")
        .with_answer("condition", "new")
    )
    view = warmup_view(cat, progress, currency_label=cfg.currency_label)
    # cosmetic * to40 = 4500*35 .. 7000*35 = 157_500 .. 245_000
    assert "157 500" in view.text
    assert "245 000" in view.text
    cb = [b.callback_data for row in view.markup.inline_keyboard for b in row]
    assert f"{CB_WARMUP_GO}:0" in cb
    # New: the warmup screen also exposes a "skip to result" shortcut.
    assert f"{CB_WARMUP_SKIP}:0" in cb


def test_warmup_skip_button_lower_priority_than_continue(seed_quiz_path: Path) -> None:
    """Continue must visually win — render it ABOVE the skip-to-result button."""
    cfg = load_quiz_config(seed_quiz_path)
    cat = cfg.categories[0]
    progress = QuizProgress(category_key=cat.key).with_answer("type", "cosmetic")
    view = warmup_view(cat, progress, currency_label=cfg.currency_label)
    rows = view.markup.inline_keyboard
    # Find the row index of each button.
    go_row = next(i for i, row in enumerate(rows) if any(
        b.callback_data == f"{CB_WARMUP_GO}:0" for b in row))
    skip_row = next(i for i, row in enumerate(rows) if any(
        b.callback_data == f"{CB_WARMUP_SKIP}:0" for b in row))
    assert go_row < skip_row, "Continue must be above Skip"
    # Skip uses a more muted glyph so it doesn't compete with the primary CTA.
    skip_btn = next(b for row in rows for b in row if b.callback_data == f"{CB_WARMUP_SKIP}:0")
    assert "⏭" in skip_btn.text


# ---------------------------------------------------------------------------
# Result screen
# ---------------------------------------------------------------------------


def test_result_view_shows_full_calc(seed_quiz_path: Path) -> None:
    cfg = load_quiz_config(seed_quiz_path)
    cat = cfg.category_by_key("tutor")
    progress = (
        QuizProgress(category_key=cat.key)
        .with_answer("subject", "english")
        .with_answer("level", "ege")
        .with_answer("frequency", "2x")
        .with_answer("duration", "60")
        .with_answer("format", "online")
        .with_answer("start", "soon")
    )
    view = result_view(cat, progress, currency_label=cfg.currency_label)
    assert "Английский" in view.text
    assert "ЕГЭ" in view.text
    assert " / мес" in view.text
    cb = [b.callback_data for row in view.markup.inline_keyboard for b in row]
    assert f"{CB_RESULT_CTA}:0" in cb
    assert f"{CB_RESTART}:0" in cb
    assert f"{CB_MAIN_MENU}:0" in cb


def test_result_view_single_point_no_dash() -> None:
    """When min == max, the range collapses into a single price line."""
    from quiz_bot.quiz_engine import Category, Option, Question

    cat = Category(
        key="x",
        emoji="✨",
        title="X",
        subtitle="",
        intro="",
        price_unit_label="",
        warmup_after_index=None,
        warmup_template="",
        questions=(
            Question(key="q", title="Q", options=(
                Option(key="a", label="A", weight_min=100, weight_max=100),
            )),
        ),
    )
    progress = QuizProgress(category_key="x").with_answer("q", "a")
    view = result_view(cat, progress, currency_label="₽")
    assert " — " not in view.text  # no range dash


# ---------------------------------------------------------------------------
# Ask name / phone / done
# ---------------------------------------------------------------------------


def test_ask_name_shows_calculated_range(seed_quiz_path: Path) -> None:
    cfg = load_quiz_config(seed_quiz_path)
    cat = cfg.category_by_key("renovation")
    progress = (
        QuizProgress(category_key=cat.key)
        .with_answer("type", "cosmetic")
        .with_answer("area", "to40")
    )
    view = ask_name_view(category=cat, progress=progress, currency_label=cfg.currency_label)
    # Respectful «Вы»-form with capital V (bot voice rule).
    assert "Как к Вам обращаться" in view.text
    # Should expose the running calc.
    assert "157 500" in view.text


def test_ask_phone_shows_calculated_range(seed_quiz_path: Path) -> None:
    cfg = load_quiz_config(seed_quiz_path)
    cat = cfg.category_by_key("renovation")
    progress = (
        QuizProgress(category_key=cat.key)
        .with_answer("type", "premium")
        .with_answer("area", "over_90")
    )
    view = ask_phone_view(category=cat, progress=progress, currency_label=cfg.currency_label)
    assert "телефон" in view.text.lower()


def test_lead_done_view_renders_master_link(seed_quiz_path: Path) -> None:
    cfg = load_quiz_config(seed_quiz_path)
    cat = cfg.categories[0]
    progress = QuizProgress(category_key=cat.key).with_answer("type", "cosmetic")
    price = calculate_price(cat, progress)
    view = lead_done_view(
        category=cat,
        price=price,
        currency_label=cfg.currency_label,
        master_handle="keepmaster",
        master_url="https://t.me/keepmaster",
    )
    assert "https://t.me/keepmaster" in view.text
    assert "Спасибо" in view.text


def test_about_view_renders() -> None:
    view = about_view(business_name="Brand", master_handle="alex", master_url="https://t.me/alex")
    assert "Brand" in view.text
    assert "https://t.me/alex" in view.text


# ---------------------------------------------------------------------------
# Admin views
# ---------------------------------------------------------------------------


def test_admin_menu_view_has_all_buttons() -> None:
    view = admin_menu_view()
    cb = [b.callback_data for row in view.markup.inline_keyboard for b in row]
    assert any(d.startswith("adm_stats") for d in cb)
    assert any(d.startswith("adm_leads") for d in cb)
    assert any(d.startswith("adm_csv") for d in cb)
    assert any(d.startswith("adm_funnel") for d in cb)
    assert any(d.startswith("main:0") for d in cb)


def test_admin_stats_view_renders_conversion() -> None:
    view = admin_stats_view(starts=100, completed=60, leads=20)
    assert "100" in view.text
    assert "60" in view.text
    assert "20" in view.text
    assert "20.0%" in view.text  # 20/100
    # 20/60 ≈ 33.3
    assert "33.3%" in view.text


def test_admin_stats_view_handles_zero_starts() -> None:
    view = admin_stats_view(starts=0, completed=0, leads=0)
    assert "0.0%" in view.text


def test_admin_leads_view_empty() -> None:
    view = admin_leads_view(page=1, total_pages=1, cards=[])
    assert "пока нет" in view.text.lower() or "пуст" in view.text.lower()


def test_admin_leads_view_with_cards() -> None:
    view = admin_leads_view(page=2, total_pages=5, cards=["card1", "card2"])
    assert "2/5" in view.text
    assert "card1" in view.text
    assert "card2" in view.text


def test_admin_leads_kb_pagination_arrows() -> None:
    kb = admin_leads_kb(page=2, total_pages=5)
    cb = [b.callback_data or b.text for row in kb.inline_keyboard for b in row]
    # has previous + next + page marker + back
    assert "adm_leads:1" in cb
    assert "adm_leads:3" in cb
    texts_seen = [b.text for row in kb.inline_keyboard for b in row]
    assert "2/5" in texts_seen


def test_admin_leads_kb_first_page_no_prev() -> None:
    kb = admin_leads_kb(page=1, total_pages=3)
    cb = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert "adm_leads:0" not in cb


def test_admin_leads_kb_last_page_no_next() -> None:
    kb = admin_leads_kb(page=3, total_pages=3)
    cb = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert "adm_leads:4" not in cb


def test_admin_funnel_picker_shows_human_titles(seed_quiz_path: Path) -> None:
    """Bug fix: the picker used to render raw keys ('renovation', 'tutor') —
    must render emoji+title instead, and still wire callback_data to the key."""
    cfg = load_quiz_config(seed_quiz_path)
    view = admin_funnel_picker_view(list(cfg.categories))
    # Button labels must contain the human-readable category titles.
    labels = [b.text for row in view.markup.inline_keyboard for b in row]
    label_blob = " ".join(labels)
    assert "🔨" in label_blob
    assert "Ремонт квартиры под ключ" in label_blob
    assert "🎓" in label_blob
    assert "Репетитор" in label_blob
    # The raw keys must NOT leak into button labels.
    assert "renovation" not in label_blob
    assert "tutor" not in label_blob
    # callback_data still references the key (it's the stable id).
    cb_data = [b.callback_data for row in view.markup.inline_keyboard for b in row]
    assert f"{CB_ADMIN_FUNNEL}:renovation" in cb_data
    assert f"{CB_ADMIN_FUNNEL}:tutor" in cb_data


def test_lead_done_uses_formal_vy_and_no_role_nouns() -> None:
    """Bug fix: LEAD_DONE used to say «передал заявку мастеру» (role-specific,
    weird for tutoring) and «написать сам» (grammatical / gender problem).
    Must now use respectful Вы-form and stay role-agnostic."""
    from quiz_bot import texts as t
    body = t.LEAD_DONE.format(
        price="100 ₽",
        master_handle="@x",
        master_url="https://t.me/x",
    )
    # Bot voice — no «мастер/менеджер/сам».
    forbidden = ["мастер", "менеджер", "написать сам", "написать сами"]
    for word in forbidden:
        assert word not in body.lower(), f"LEAD_DONE leaks forbidden phrase: {word!r}"
    # Должно содержать вежливое обращение Вы.
    assert "Вами" in body or "Вы " in body or "Вам" in body


def test_no_lowercase_vy_in_client_texts() -> None:
    """Audit guard: client-facing texts in texts.py must use capital «Вы/Вам/Вас»
    when addressing the user. Lowercase 'вы/вам/вас' is treated as a typo."""
    import re

    from quiz_bot import texts as t
    # Only audit client-facing constants. Admin-facing are impersonal.
    client_names = [
        "WELCOME_MULTI", "WELCOME_SINGLE", "CATEGORY_INTRO", "ABOUT_TEXT",
        "INVALID_NAME_SHORT", "INVALID_NAME_LONG", "INVALID_NAME_LINK",
        "INVALID_PHONE", "INVALID_PHONE_LINK",
        "ASK_NAME", "ASK_PHONE", "LEAD_DONE", "WARMUP_FOOTER",
        "RESULT_TITLE", "RESULT_PRICE", "RESULT_DETAILS_TITLE",
        "CATEGORY_PICKER_PROMPT", "PHONE_AUX_HINT",
    ]
    bad_pattern = re.compile(r"\b(вы|вам|вас|ваш(?:а|е|и|у|ей)?)\b")
    for name in client_names:
        value = getattr(t, name)
        match = bad_pattern.search(value)
        assert match is None, (
            f"{name} contains lowercase '{match.group(0)}' — use capital "
            f"«Вы/Вам/Вас/Ваш» when addressing a single user. Full text: {value!r}"
        )


def test_admin_funnel_view_empty() -> None:
    cfg = load_quiz_config(Path(__file__).resolve().parents[1] / "data" / "seed_quiz.json")
    cat = cfg.categories[0]
    view = admin_funnel_view(category=cat, starts=0, per_step=[])
    assert "недостаточно" in view.text.lower() or "пусто" in view.text.lower()


def test_admin_funnel_view_renders_percentages(seed_quiz_path: Path) -> None:
    cfg = load_quiz_config(seed_quiz_path)
    cat = cfg.categories[0]
    per_step = [{"step_index": i, "passed": max(0, 10 - i)} for i in range(cat.total_steps)]
    view = admin_funnel_view(category=cat, starts=10, per_step=per_step)
    # First step should be 100%, last should be lower.
    assert "100%" in view.text
