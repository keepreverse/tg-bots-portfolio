"""High-level screen builders: (text, keyboard) pairs.

Pure (no I/O, no aiogram side effects) so they can be unit-tested.
Handlers in `handlers/*` call these, then hand the result to `render.py`.
"""

from __future__ import annotations

from typing import NamedTuple

from aiogram.types import InlineKeyboardMarkup

from . import texts
from .keyboards import (
    admin_back_kb,
    admin_funnel_kb,
    admin_leads_kb,
    admin_menu_kb,
    back_to_main_kb,
    category_intro_kb,
    category_picker_kb,
    main_menu_kb,
    question_kb,
    result_kb,
    text_step_kb,
    warmup_kb,
)
from .money import format_price, format_range
from .quiz_engine import Category, PriceRange, Question, QuizConfig, QuizProgress, calculate_price


class View(NamedTuple):
    text: str
    markup: InlineKeyboardMarkup | None


# ---------------------------------------------------------------------------
# Progress bar
# ---------------------------------------------------------------------------


def progress_bar(step_index: int, total_steps: int) -> str:
    """`▰▰▱▱▱▱ · Шаг N из M` (header for every quiz step)."""
    step = max(0, min(total_steps, step_index + 1))
    filled = "▰" * step
    empty = "▱" * max(0, total_steps - step)
    return f"{filled}{empty} · Шаг {step} из {total_steps}"


# ---------------------------------------------------------------------------
# Static screens
# ---------------------------------------------------------------------------


def main_menu_view(
    *,
    config: QuizConfig,
    business_name: str,
    is_admin: bool,
) -> View:
    has_multi = len(config.categories) > 1
    if has_multi:
        text = texts.WELCOME_MULTI.format(business=business_name)
    else:
        # Single-category mode: welcome text mentions the niche directly.
        c = config.categories[0]
        text = texts.WELCOME_SINGLE.format(
            business=business_name,
            category=c.title,
            intro=c.intro,
        )
    kb = main_menu_kb(is_admin=is_admin, has_multiple_categories=has_multi)
    return View(text=text, markup=kb)


def about_view(*, business_name: str, master_handle: str, master_url: str) -> View:
    text = texts.ABOUT_TEXT.format(
        business=business_name,
        master_handle=master_handle,
        master_url=master_url,
    )
    return View(text=text, markup=back_to_main_kb())


def category_picker_view(config: QuizConfig) -> View:
    return View(
        text=texts.CATEGORY_PICKER_PROMPT,
        markup=category_picker_kb(list(config.categories)),
    )


def category_intro_view(category: Category, *, allow_back: bool) -> View:
    text = texts.CATEGORY_INTRO.format(
        emoji=category.emoji,
        title=category.title,
        intro=category.intro,
    )
    return View(text=text, markup=category_intro_kb(category.key, allow_back=allow_back))


# ---------------------------------------------------------------------------
# Quiz question screen
# ---------------------------------------------------------------------------


def question_view(
    category: Category,
    question: Question,
    step_index: int,
    *,
    allow_back: bool,
) -> View:
    body = (
        f"{progress_bar(step_index, category.total_steps)}\n"
        f"{category.emoji} <b>{category.title}</b>\n\n"
        f"<b>{question.title}</b>"
    )
    options = [(o.key, o.label) for o in question.options]
    return View(text=body, markup=question_kb(options, allow_back=allow_back))


# ---------------------------------------------------------------------------
# Warm-up (mid-quiz) screen
# ---------------------------------------------------------------------------


def warmup_view(
    category: Category,
    progress: QuizProgress,
    *,
    currency_label: str,
) -> View:
    pr = calculate_price(category, progress)
    range_str = format_range(
        pr.min_total,
        pr.max_total,
        currency=currency_label,
        unit_suffix=category.price_unit_label,
    )
    template = category.warmup_template or "Уже примерно <b>{min}–{max}</b>. Осталось пара уточнений."
    body = template.format(
        min=format_price(pr.min_total, currency=currency_label, unit_suffix=""),
        max=format_price(pr.max_total, currency=currency_label, unit_suffix=category.price_unit_label),
        range=range_str,
    )
    text = (
        f"{category.emoji} <b>{category.title}</b>\n\n"
        f"{body}\n\n<i>{texts.WARMUP_FOOTER}</i>"
    )
    return View(text=text, markup=warmup_kb())


# ---------------------------------------------------------------------------
# Result screen
# ---------------------------------------------------------------------------


def result_view(
    category: Category,
    progress: QuizProgress,
    *,
    currency_label: str,
) -> View:
    pr = calculate_price(category, progress)
    price_str = format_range(
        pr.min_total,
        pr.max_total,
        currency=currency_label,
        unit_suffix=category.price_unit_label,
    )
    lines = [
        texts.RESULT_TITLE,
        "",
        f"{category.emoji} <b>{category.title}</b>",
        texts.RESULT_PRICE.format(price=price_str),
        "",
        texts.RESULT_DETAILS_TITLE,
    ]
    for q_key, opt_key in progress.answers:
        q = category.question_by_key(q_key)
        if q is None:
            continue
        opt = q.option_by_key(opt_key)
        if opt is None:
            continue
        lines.append(texts.RESULT_DETAILS_LINE.format(q_title=q.title, opt_label=opt.label))
    return View(text="\n".join(lines), markup=result_kb())


def ask_name_view(*, category: Category, progress: QuizProgress, currency_label: str) -> View:
    pr = calculate_price(category, progress)
    range_str = format_range(
        pr.min_total,
        pr.max_total,
        currency=currency_label,
        unit_suffix=category.price_unit_label,
    )
    head = (
        f"{category.emoji} <b>{category.title}</b>\n"
        f"📊 Ваш расчёт: <b>{range_str}</b>\n\n"
    )
    return View(text=f"{head}{texts.ASK_NAME}", markup=text_step_kb())


def ask_phone_view(*, category: Category, progress: QuizProgress, currency_label: str) -> View:
    pr = calculate_price(category, progress)
    range_str = format_range(
        pr.min_total,
        pr.max_total,
        currency=currency_label,
        unit_suffix=category.price_unit_label,
    )
    head = (
        f"{category.emoji} <b>{category.title}</b>\n"
        f"📊 Ваш расчёт: <b>{range_str}</b>\n\n"
    )
    return View(text=f"{head}{texts.ASK_PHONE}", markup=text_step_kb())



def lead_done_view(
    *,
    category: Category,
    price: PriceRange,
    currency_label: str,
    master_handle: str,
    master_url: str,
) -> View:
    price_str = format_range(
        price.min_total,
        price.max_total,
        currency=currency_label,
        unit_suffix=category.price_unit_label,
    )
    text = texts.LEAD_DONE.format(
        price=price_str,
        master_handle=master_handle,
        master_url=master_url,
    )
    return View(text=text, markup=back_to_main_kb())


# ---------------------------------------------------------------------------
# Admin views
# ---------------------------------------------------------------------------


def admin_menu_view() -> View:
    return View(text=texts.ADMIN_PANEL_TITLE, markup=admin_menu_kb())


def admin_stats_view(
    *,
    starts: int,
    completed: int,
    leads: int,
) -> View:
    conv_leads = (leads / starts * 100.0) if starts else 0.0
    conv_phone = (leads / completed * 100.0) if completed else 0.0
    text = texts.STATS_TPL.format(
        starts=starts,
        completed=completed,
        leads=leads,
        conv_leads=conv_leads,
        conv_phone=conv_phone,
    )
    return View(text=text, markup=admin_back_kb())


def admin_leads_view(
    *,
    page: int,
    total_pages: int,
    cards: list[str],
) -> View:
    if not cards:
        return View(text=texts.LEADS_EMPTY, markup=admin_back_kb())
    title = texts.LEADS_PAGE_TITLE.format(page=page, total_pages=max(1, total_pages))
    body = "\n\n".join(cards)
    return View(
        text=f"{title}\n\n{body}",
        markup=admin_leads_kb(page=page, total_pages=total_pages),
    )


def admin_funnel_picker_view(categories: list[Category]) -> View:
    """When the user clicks 📈 Воронка we ask which category to inspect."""
    labelled = [(c.key, f"{c.emoji} {c.title}".strip()) for c in categories]
    return View(text=texts.FUNNEL_PICKER, markup=admin_funnel_kb(labelled))


def admin_funnel_view(
    *,
    category: Category,
    starts: int,
    per_step: list[dict[str, int]],
) -> View:
    if starts == 0:
        return View(text=texts.FUNNEL_EMPTY, markup=admin_back_kb())
    lines = [texts.FUNNEL_HEADER.format(category=category.title)]
    for idx, (q, row) in enumerate(zip(category.questions, per_step, strict=False), start=1):
        passed = row["passed"]
        percent = (passed / starts * 100.0) if starts else 0.0
        lines.append(
            texts.FUNNEL_LINE.format(
                idx=idx,
                title=q.title,
                percent=percent,
                passed=passed,
                started=starts,
            )
        )
    return View(text="\n".join(lines), markup=admin_back_kb())
