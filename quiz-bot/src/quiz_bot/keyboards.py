"""Inline & reply keyboards for the quiz-bot.

Callback data is encoded as compact `prefix:payload` strings. We keep payloads
short because Telegram limits callback_data to 64 bytes — the quiz tree's
category and question keys are intentionally short ASCII for that reason.
"""

from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from . import texts
from .quiz_engine import Category

# --- callback prefixes ----------------------------------------------------

CB_MAIN_MENU = "main"
CB_START_QUIZ = "start"          # entry point (no category yet)
CB_PICK_CAT = "cat"              # cat:<category_key>
CB_ANSWER = "ans"                # ans:<option_key>
CB_BACK = "back"                 # back step in quiz
CB_CANCEL = "cancel"             # cancel quiz, back to main menu
CB_WARMUP_GO = "wgo"             # proceed past warm-up screen
CB_WARMUP_SKIP = "wskip"         # skip the rest of the quiz to result
CB_RESULT_CTA = "cta"            # click "leave contact" CTA
CB_RESTART = "restart"           # restart the quiz from category picker
CB_ABOUT = "about"
CB_ADMIN = "adm"
CB_ADMIN_STATS = "adm_stats"
CB_ADMIN_LEADS = "adm_leads"     # adm_leads:<page>
CB_ADMIN_EXPORT = "adm_csv"
CB_ADMIN_FUNNEL = "adm_funnel"   # adm_funnel:<category_key>
CB_NOOP = "noop"


# --- main / nav -----------------------------------------------------------


def main_menu_kb(*, is_admin: bool, has_multiple_categories: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(
            text=texts.MENU_START_QUIZ,
            callback_data=f"{CB_START_QUIZ}:0" if has_multiple_categories else f"{CB_PICK_CAT}:_only",
        )],
        [InlineKeyboardButton(text=texts.MENU_ABOUT, callback_data=f"{CB_ABOUT}:0")],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton(text=texts.MENU_ADMIN, callback_data=f"{CB_ADMIN}:0")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_to_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=texts.NAV_TO_MAIN, callback_data=f"{CB_MAIN_MENU}:0"),
    ]])


# --- quiz navigation ------------------------------------------------------


def _quiz_nav_row(*, allow_back: bool) -> list[InlineKeyboardButton]:
    row: list[InlineKeyboardButton] = []
    if allow_back:
        row.append(InlineKeyboardButton(text=texts.NAV_BACK, callback_data=f"{CB_BACK}:0"))
    row.append(InlineKeyboardButton(text=texts.NAV_CANCEL, callback_data=f"{CB_CANCEL}:0"))
    return row


def category_picker_kb(categories: list[Category]) -> InlineKeyboardMarkup:
    """One row per category, plus a back-to-main row at the bottom."""
    rows: list[list[InlineKeyboardButton]] = []
    for c in categories:
        label = f"{c.emoji} {c.title}".strip()
        rows.append([InlineKeyboardButton(text=label, callback_data=f"{CB_PICK_CAT}:{c.key}")])
    rows.append([InlineKeyboardButton(text=texts.NAV_TO_MAIN, callback_data=f"{CB_MAIN_MENU}:0")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def category_intro_kb(category_key: str, *, allow_back: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(
            text=texts.CATEGORY_INTRO_GO,
            callback_data=f"{CB_PICK_CAT}:{category_key}:go",
        )],
        _quiz_nav_row(allow_back=allow_back),
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def question_kb(option_keys_labels: list[tuple[str, str]], *, allow_back: bool) -> InlineKeyboardMarkup:
    """One button per option (one column), plus a back/cancel row."""
    rows: list[list[InlineKeyboardButton]] = []
    for opt_key, label in option_keys_labels:
        rows.append([InlineKeyboardButton(text=label, callback_data=f"{CB_ANSWER}:{opt_key}")])
    rows.append(_quiz_nav_row(allow_back=allow_back))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def warmup_kb() -> InlineKeyboardMarkup:
    # The primary CTA is "Продолжить" — we want users to answer all the questions
    # for better lead qualification. "Сразу к расчёту" is intentionally placed
    # below it and uses a more muted glyph so it doesn't compete for attention.
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➡️ Продолжить", callback_data=f"{CB_WARMUP_GO}:0")],
        [InlineKeyboardButton(text="⏭ Сразу к расчёту", callback_data=f"{CB_WARMUP_SKIP}:0")],
        _quiz_nav_row(allow_back=True),
    ])


def result_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts.RESULT_CTA, callback_data=f"{CB_RESULT_CTA}:0")],
        [InlineKeyboardButton(text=texts.RESULT_RESTART, callback_data=f"{CB_RESTART}:0")],
        [InlineKeyboardButton(text=texts.NAV_TO_MAIN, callback_data=f"{CB_MAIN_MENU}:0")],
    ])


def text_step_kb() -> InlineKeyboardMarkup:
    """Shown next to free-text prompts (name)."""
    return InlineKeyboardMarkup(inline_keyboard=[_quiz_nav_row(allow_back=True)])


def phone_reply_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=texts.PHONE_BUTTON, request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="+79991234567",
    )


# --- admin keyboards ------------------------------------------------------


def admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts.ADMIN_STATS, callback_data=f"{CB_ADMIN_STATS}:0")],
        [InlineKeyboardButton(text=texts.ADMIN_LEADS, callback_data=f"{CB_ADMIN_LEADS}:1")],
        [InlineKeyboardButton(text=texts.ADMIN_EXPORT_CSV, callback_data=f"{CB_ADMIN_EXPORT}:0")],
        [InlineKeyboardButton(text=texts.ADMIN_FUNNEL, callback_data=f"{CB_ADMIN_FUNNEL}:_all")],
        [InlineKeyboardButton(text=texts.NAV_TO_MAIN, callback_data=f"{CB_MAIN_MENU}:0")],
    ])


def admin_back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=texts.ADMIN_BACK, callback_data=f"{CB_ADMIN}:0"),
    ]])


def admin_leads_kb(page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Pagination nav (◀ / page-marker / ▶) + back-to-admin row."""
    nav: list[InlineKeyboardButton] = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="◀", callback_data=f"{CB_ADMIN_LEADS}:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page}/{max(1, total_pages)}", callback_data=f"{CB_NOOP}:0"))
    if page < total_pages:
        nav.append(InlineKeyboardButton(text="▶", callback_data=f"{CB_ADMIN_LEADS}:{page + 1}"))
    return InlineKeyboardMarkup(inline_keyboard=[
        nav,
        [InlineKeyboardButton(text=texts.ADMIN_BACK, callback_data=f"{CB_ADMIN}:0")],
    ])


def admin_funnel_kb(categories: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    """One button per category — funnels are per-category since flows differ.

    `categories` is a list of `(key, label)` tuples — the key is wired into
    callback_data (kept short for the 64-byte budget), and the label is what
    the admin actually sees on the button ("🔨 Ремонт квартиры под ключ").
    """
    rows: list[list[InlineKeyboardButton]] = []
    for key, label in categories:
        rows.append([InlineKeyboardButton(text=label, callback_data=f"{CB_ADMIN_FUNNEL}:{key}")])
    rows.append([InlineKeyboardButton(text=texts.ADMIN_BACK, callback_data=f"{CB_ADMIN}:0")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def lead_admin_dm_kb(user_tg_id: int | None, username: str | None) -> InlineKeyboardMarkup:
    """The keyboard attached to the admin DM notification — quick way to reply."""
    if username:
        url = f"https://t.me/{username.lstrip('@')}"
    elif user_tg_id is not None:
        url = f"tg://user?id={user_tg_id}"
    else:
        return InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=texts.ADMIN_LEAD_REPLY, callback_data=f"{CB_NOOP}:0"),
        ]])
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=texts.ADMIN_LEAD_REPLY, url=url),
    ]])
