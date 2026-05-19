"""Pure render functions: each returns (text, reply_markup) for one screen.

All Telegram interaction (sending/editing messages) lives in handlers.
This module has no I/O — easy to unit-test.
"""

from __future__ import annotations

from typing import NamedTuple

from aiogram.types import InlineKeyboardMarkup

from . import keyboards as kb
from . import texts as t

# Progress bar settings — total steps shown to the user.
TOTAL_STEPS = 5  # name, phone, service, comment, confirm


class View(NamedTuple):
    text: str
    markup: InlineKeyboardMarkup


def _progress_bar(step: int, total: int = TOTAL_STEPS) -> str:
    filled = "▰" * step
    empty = "▱" * max(0, total - step)
    return filled + empty


def _filled_block(data: dict) -> str:
    """Show already-filled fields above the current prompt."""
    rows: list[str] = []
    if name := data.get("name"):
        rows.append(f"✓ <b>Имя:</b> {name}")
    if phone := data.get("phone"):
        rows.append(f"✓ <b>Телефон:</b> <code>{phone}</code>")
    if service := data.get("service"):
        rows.append(f"✓ <b>Услуга:</b> {service}")
    if "comment" in data:
        comment = data.get("comment")
        rows.append(f"✓ <b>Комментарий:</b> {comment or '—'}")
    if not rows:
        return ""
    return "\n".join(rows) + "\n\n"


# --- main menu surfaces ----------------------------------------------------

def main_menu(business: str, is_admin: bool) -> View:
    return View(
        text="<b>👋 Главное меню</b>\n\n" + t.MAIN_MENU_BODY.format(business=business),
        markup=kb.main_menu_kb(is_admin=is_admin),
    )


def about(business: str) -> View:
    return View(text=t.ABOUT_BODY.format(business=business), markup=kb.back_to_menu_kb())


def services(business: str, services_list: list[str]) -> View:
    rows = "\n".join(f"• {s}" for s in services_list)
    text = f"<b>🛠 Услуги — {business}</b>\n\n{rows}"
    return View(text=text, markup=kb.back_to_menu_kb())


def help_screen() -> View:
    return View(text=t.HELP_BODY, markup=kb.back_to_menu_kb())


# --- survey screens --------------------------------------------------------

def survey_name(data: dict) -> View:
    text = (
        f"<b>📝 Заявка</b> · {_progress_bar(1)} · Шаг 1 из {TOTAL_STEPS}\n\n"
        f"{_filled_block(data)}"
        f"{t.ASK_NAME_PROMPT}"
    )
    return View(text=text, markup=kb.survey_text_step_kb(allow_back=False))


def survey_phone(data: dict) -> View:
    text = (
        f"<b>📝 Заявка</b> · {_progress_bar(2)} · Шаг 2 из {TOTAL_STEPS}\n\n"
        f"{_filled_block(data)}"
        f"{t.ASK_PHONE_PROMPT}"
    )
    return View(text=text, markup=kb.survey_text_step_kb(allow_back=True))


def survey_service(data: dict, services_list: list[str]) -> View:
    text = (
        f"<b>📝 Заявка</b> · {_progress_bar(3)} · Шаг 3 из {TOTAL_STEPS}\n\n"
        f"{_filled_block(data)}"
        "Выберите услугу:"
    )
    return View(text=text, markup=kb.survey_service_kb(services_list))


def survey_comment(data: dict) -> View:
    text = (
        f"<b>📝 Заявка</b> · {_progress_bar(4)} · Шаг 4 из {TOTAL_STEPS}\n\n"
        f"{_filled_block(data)}"
        f"{t.ASK_COMMENT_PROMPT}"
    )
    return View(text=text, markup=kb.survey_comment_kb())


def survey_confirm(data: dict) -> View:
    text = (
        f"<b>📝 Заявка — проверьте данные</b> · {_progress_bar(5)} · Шаг 5 из {TOTAL_STEPS}\n\n"
        f"{_filled_block(data)}"
        "Если всё верно — нажмите «✅ Отправить»."
    )
    return View(text=text, markup=kb.survey_confirm_kb())


def survey_done(lead_id: int) -> View:
    return View(text=t.THANKS_BODY.format(lead_id=lead_id), markup=kb.survey_done_kb())


# --- admin screens ---------------------------------------------------------

def admin_panel(business: str, total: int, last_week: int) -> View:
    return View(
        text=t.admin_dashboard_body(total=total, last_week=last_week, business=business),
        markup=kb.admin_panel_kb(),
    )


def admin_recent(
    page: int,
    total_pages: int,
    lines: list[str],
) -> View:
    return View(
        text=t.admin_recent_body(page=page, total_pages=total_pages, lines=lines),
        markup=kb.admin_recent_kb(page=page, total_pages=total_pages),
    )
