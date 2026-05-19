"""User-facing texts. Keep all copy here so it's easy to rebrand per client."""

# --- short strings used by handlers as prompts/errors ----------------------

ASK_NAME_PROMPT = "Введите ваше <b>имя</b> следующим сообщением."
ASK_PHONE_PROMPT = (
    "Поделитесь телефоном через кнопку внизу либо введите вручную "
    "(например <code>+79991234567</code>)."
)
ASK_COMMENT_PROMPT = "Опишите задачу — или нажмите «Пропустить»."
INVALID_NAME = "Имя слишком короткое. Введите минимум 2 символа."
INVALID_PHONE = "Не похоже на телефон. Используйте формат +79991234567 или кнопку «Поделиться номером»."
PHONE_KB_HINT = "📱 Нажмите кнопку ниже, чтобы поделиться номером, или введите вручную."
PHONE_ACK = "✓"

# --- multi-line block titles ----------------------------------------------

MAIN_MENU_BODY = (
    "Это бот для приёма заявок компании <b>{business}</b>.\n\n"
    "Здесь вы можете:\n"
    "• оставить заявку — мы свяжемся в течение рабочего дня;\n"
    "• посмотреть список услуг;\n"
    "• получить справку."
)

ABOUT_BODY = (
    "<b>О компании {business}</b>\n\n"
    "Мы принимаем заявки через этот бот и связываемся с клиентами "
    "по телефону в течение рабочего дня.\n\n"
    "Если у вас срочный вопрос — оставьте заявку, "
    "в комментарии напишите «срочно»."
)

HELP_BODY = (
    "<b>Как пользоваться</b>\n\n"
    "1. Нажмите <b>«📝 Оставить заявку»</b> в главном меню.\n"
    "2. Заполните 4 коротких шага: имя → телефон → услуга → комментарий.\n"
    "3. На любом шаге можно вернуться кнопкой «◀ Назад» или отменить «✕».\n"
    "4. После отправки придёт подтверждение с номером вашей заявки.\n\n"
    "Если что-то пошло не так — напишите команду /start, чтобы открыть меню заново."
)

THANKS_BODY = (
    "✅ <b>Заявка №{lead_id} принята</b>\n\n"
    "Менеджер свяжется с вами в ближайшее время по указанному телефону."
)


# --- admin -----------------------------------------------------------------

def admin_dashboard_body(total: int, last_week: int, business: str) -> str:
    return (
        f"<b>🛠 Админ-панель — {business}</b>\n\n"
        f"📊 Всего заявок: <b>{total}</b>\n"
        f"📅 За последние 7 дней: <b>{last_week}</b>"
    )


def admin_recent_body(page: int, total_pages: int, lines: list[str]) -> str:
    if not lines:
        body = "Пока нет ни одной заявки."
    else:
        body = "\n\n".join(lines)
    header = f"<b>📋 Последние заявки</b> · стр. {page}/{total_pages}\n\n"
    return header + body


def lead_short(
    lead_id: int,
    name: str,
    phone: str,
    service: str,
    created_at: str,
) -> str:
    return (
        f"<b>№{lead_id}</b> · {created_at[:16].replace('T', ' ')}\n"
        f"{name} · <code>{phone}</code>\n"
        f"<i>{service}</i>"
    )


def admin_notification(
    lead_id: int,
    name: str,
    phone: str,
    service: str,
    comment: str | None,
    tg_user_id: int,
    tg_username: str | None,
) -> str:
    user_line = (
        f"@{tg_username}"
        if tg_username
        else f"<a href='tg://user?id={tg_user_id}'>профиль</a>"
    )
    return (
        f"🆕 <b>Новая заявка №{lead_id}</b>\n\n"
        f"<b>Имя:</b> {name}\n"
        f"<b>Телефон:</b> <code>{phone}</code>\n"
        f"<b>Услуга:</b> {service}\n"
        f"<b>Комментарий:</b> {comment or '—'}\n"
        f"<b>Telegram:</b> {user_line}"
    )
