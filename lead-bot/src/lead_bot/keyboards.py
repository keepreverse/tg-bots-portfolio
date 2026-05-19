"""Inline and reply keyboards, organized by screen."""

from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

# --- main menu -------------------------------------------------------------

def main_menu_kb(is_admin: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="📝 Оставить заявку", callback_data="s:start")],
        [
            InlineKeyboardButton(text="🛠 Услуги", callback_data="m:services"),
            InlineKeyboardButton(text="ℹ️ О компании", callback_data="m:about"),
        ],
        [InlineKeyboardButton(text="💬 Помощь", callback_data="m:help")],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton(text="🛠 Админ-панель", callback_data="a:open")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_to_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="◀ В меню", callback_data="m:open")]]
    )


# --- survey navigation -----------------------------------------------------

def _nav_row(allow_back: bool) -> list[InlineKeyboardButton]:
    row: list[InlineKeyboardButton] = []
    if allow_back:
        row.append(InlineKeyboardButton(text="◀ Назад", callback_data="s:back"))
    row.append(InlineKeyboardButton(text="✕ Отмена", callback_data="s:cancel"))
    return row


def survey_text_step_kb(allow_back: bool) -> InlineKeyboardMarkup:
    """Inline keyboard for steps where input is plain text (name/phone)."""
    return InlineKeyboardMarkup(inline_keyboard=[_nav_row(allow_back)])


def survey_service_kb(services: list[str]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=name, callback_data=f"s:svc:{i}")]
        for i, name in enumerate(services)
    ]
    rows.append(_nav_row(allow_back=True))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def survey_comment_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⤼ Пропустить", callback_data="s:skip")],
            _nav_row(allow_back=True),
        ]
    )


def survey_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Отправить", callback_data="s:confirm")],
            [InlineKeyboardButton(text="🔁 Начать заново", callback_data="s:restart")],
            _nav_row(allow_back=True),
        ]
    )


def survey_done_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Ещё одна заявка", callback_data="s:start")],
            [InlineKeyboardButton(text="🏠 В главное меню", callback_data="m:open")],
        ]
    )


# --- phone reply keyboard (one-time, removed after use) --------------------

def phone_share_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Поделиться номером", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="+79991234567",
    )


def remove_reply_kb() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


# --- admin -----------------------------------------------------------------

def admin_panel_kb(page_for_recent: int = 1) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Обновить", callback_data="a:refresh"),
                InlineKeyboardButton(text="📥 Экспорт CSV", callback_data="a:export"),
            ],
            [InlineKeyboardButton(text="📋 Последние заявки", callback_data=f"a:recent:{page_for_recent}")],
            [InlineKeyboardButton(text="🏓 Ping", callback_data="a:ping")],
            [InlineKeyboardButton(text="◀ В меню", callback_data="m:open")],
        ]
    )


def admin_recent_kb(page: int, total_pages: int) -> InlineKeyboardMarkup:
    nav: list[InlineKeyboardButton] = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="◀", callback_data=f"a:recent:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="a:noop"))
    if page < total_pages:
        nav.append(InlineKeyboardButton(text="▶", callback_data=f"a:recent:{page + 1}"))
    return InlineKeyboardMarkup(
        inline_keyboard=[
            nav,
            [InlineKeyboardButton(text="◀ К админ-панели", callback_data="a:open")],
        ]
    )


def admin_lead_contact_kb(username: str | None, user_id: int) -> InlineKeyboardMarkup:
    if username:
        url = f"https://t.me/{username}"
    else:
        url = f"tg://user?id={user_id}"
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="💬 Написать клиенту", url=url)]]
    )
