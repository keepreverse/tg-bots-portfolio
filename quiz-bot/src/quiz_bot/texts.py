"""Bot copy. Russian, formal «Вы»-form throughout.

Style guide:
- Single addressee → respectful «Вы» with capital V (Вы, Вам, Вас, Ваш).
- No role-specific nouns in client-facing copy («мастер», «менеджер», …) —
  the bot is multi-niche, copy must work for renovation, tutor, photographer,
  legal advisor, etc. Prefer passive voice: «с Вами свяжутся».
- Admin-facing copy is impersonal/technical.
"""

from __future__ import annotations

WELCOME_MULTI = (
    "<b>👋 {business}</b>\n\n"
    "Это бот-калькулятор. Ответьте на пару коротких вопросов — "
    "и сразу увидите примерную цену.\n\n"
    "Выберите, что рассчитываем:"
)

WELCOME_SINGLE = (
    "<b>👋 {business}</b>\n\n"
    "Это бот-калькулятор «{category}».\n\n"
    "{intro}"
)

MENU_START_QUIZ = "🚀 Начать расчёт"
MENU_ABOUT = "💬 Подробнее"
MENU_ADMIN = "🛠 Админ-панель"

NAV_BACK = "◀ Назад"
NAV_CANCEL = "✕ В меню"
NAV_TO_MAIN = "🏠 В меню"

CATEGORY_INTRO = (
    "<b>{emoji} {title}</b>\n\n"
    "{intro}"
)
CATEGORY_INTRO_GO = "🚀 Поехали"

ABOUT_TEXT = (
    "<b>💬 О сервисе {business}</b>\n\n"
    "Бот считает примерный диапазон цены по нескольким вопросам. "
    "Итоговую сумму уточняем при обсуждении деталей.\n\n"
    "Хотите связаться напрямую: <a href=\"{master_url}\">{master_handle}</a>"
)

INVALID_NAME_SHORT = "⚠️ Имя слишком короткое. Введите минимум 2 символа."
INVALID_NAME_LONG = "⚠️ Имя слишком длинное. Не больше 100 символов."
INVALID_NAME_LINK = (
    "⚠️ Ссылки и упоминания в имени мы не принимаем. "
    "Введите, пожалуйста, имя обычным текстом."
)
INVALID_PHONE = (
    "⚠️ Не похоже на телефон. Используйте формат "
    "<code>+79991234567</code> или нажмите кнопку «📱 Поделиться номером»."
)
INVALID_PHONE_LINK = (
    "⚠️ В телефоне обнаружена ссылка — её отправлять нельзя. "
    "Введите, пожалуйста, номер цифрами или нажмите «📱 Поделиться номером»."
)

ASK_NAME = "Как к Вам обращаться? Напишите имя одной строкой."
ASK_PHONE = (
    "Оставьте, пожалуйста, телефон — с Вами свяжутся в ближайшие рабочие часы.\n\n"
    "Нажмите кнопку <b>«📱 Поделиться номером»</b> ниже или введите вручную "
    "(например <code>+79991234567</code>)."
)
PHONE_BUTTON = "📱 Поделиться номером"

LEAD_DONE = (
    "✅ <b>Спасибо!</b>\n\n"
    "Ваш ориентир по цене:\n<b>{price}</b>\n\n"
    "Заявка принята — с Вами свяжутся в ближайшие рабочие часы.\n\n"
    "Если удобнее связаться напрямую: <a href=\"{master_url}\">{master_handle}</a>."
)

ADMIN_LEAD_DM = (
    "🟢 <b>Новая заявка #{id}</b>\n\n"
    "{summary}\n\n"
    "📊 Расчёт: <b>{price}</b>\n"
    "👤 Клиент: {name}\n"
    "📞 Телефон: {phone}\n"
    "🆔 Telegram: {tg_link}"
)
ADMIN_LEAD_REPLY = "✍️ Написать клиенту"

ADMIN_PANEL_TITLE = (
    "<b>🛠 Админ-панель</b>\n\n"
    "Статистика, последние лиды, экспорт и воронка по шагам."
)
ADMIN_STATS = "📊 Статистика"
ADMIN_LEADS = "📋 Последние лиды"
ADMIN_EXPORT_CSV = "⬇️ Экспорт CSV"
ADMIN_FUNNEL = "📈 Воронка"
ADMIN_BACK = "◀ В админ-меню"

STATS_TPL = (
    "<b>📊 Статистика</b>\n\n"
    "Стартов квиза: <b>{starts}</b>\n"
    "Доведено до результата: <b>{completed}</b>\n"
    "Лидов (с телефоном): <b>{leads}</b>\n"
    "Конверсия (старт → лид): <b>{conv_leads:.1f}%</b>\n"
    "Конверсия (результат → лид): <b>{conv_phone:.1f}%</b>"
)

LEADS_PAGE_TITLE = "<b>📋 Последние лиды</b> · стр. {page}/{total_pages}"
LEADS_EMPTY = "Заявок пока нет."

LEAD_CARD = (
    "─────────────\n"
    "<b>#{id}</b> · {created_local}\n"
    "{emoji} <b>{category}</b>\n"
    "📊 {price}\n"
    "👤 {name}\n"
    "📞 {phone}"
)

FUNNEL_PICKER = "Воронка по какой категории?"
FUNNEL_HEADER = "<b>📈 Воронка ({category})</b>\n"
FUNNEL_LINE = "{idx}. {title}: <b>{percent:.0f}%</b> ({passed}/{started})"
FUNNEL_EMPTY = "Пока недостаточно данных для воронки."

WARMUP_FOOTER = "Если устали — можно остановиться сейчас, цифра уже близка к итоговой."

RESULT_TITLE = "<b>✅ Готово!</b>"
RESULT_PRICE = "<b>Ваш расчёт: {price}</b>"
RESULT_DETAILS_TITLE = "<b>Вы выбрали:</b>"
RESULT_DETAILS_LINE = "• {q_title}: <b>{opt_label}</b>"
RESULT_CTA = "📞 Записаться на консультацию"
RESULT_RESTART = "🔄 Пройти ещё раз"

CATEGORY_PICKER_PROMPT = "Что рассчитываем?"

PHONE_AUX_HINT = "📱 Нажмите кнопку ниже или введите номер вручную."

UNKNOWN_COMMAND = "Не понял. Открываю меню."
NO_RIGHTS = "Нет прав."
