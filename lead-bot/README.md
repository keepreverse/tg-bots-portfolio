# lead-bot — Telegram-бот для сбора заявок

[![CI](https://github.com/keepreverse/tg-bots-portfolio/actions/workflows/lead-bot-ci.yml/badge.svg)](https://github.com/keepreverse/tg-bots-portfolio/actions/workflows/lead-bot-ci.yml)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![aiogram](https://img.shields.io/badge/aiogram-3.x-2CA5E0.svg)](https://docs.aiogram.dev/)

Готовый шаблон под коммерческие заказы вида «нужен бот, который собирает заявки с сайта/телеги и шлёт мне в ТГ».
Можно отдавать заказчику «как есть» — можно за полчаса перекрасить под конкретный бизнес.

## Что умеет

**UX современный:** одно сообщение, которое редактируется при переходах — никакого «накопления» сообщений в чате.

- **Главное меню** — inline-кнопки: 📝 «Оставить заявку», 🛠 «Услуги», ℹ️ «О компании», 💬 «Помощь», 🛠 «Админ-панель» (только для админа).
- **FSM-анкета** в 5 шагов: имя → телефон → услуга → комментарий → подтверждение.
- **Прогресс-бар** `▰▰▱▱▱ Шаг 2 из 5` и сводка уже заполненных полей сверху каждого шага.
- **«◀ Назад»** и **«✕ Отмена»** на каждом шаге.
- Телефон принимается **текстом** или нативной reply-кнопкой «📱 Поделиться номером», которая появляется ТОЛЬКО на шаге телефона и убирается сразу после ввода.
- Список услуг конфигурируется через `.env` (`SERVICES=Консультация;Заказ под ключ;…`) — не нужно лезть в код.
- Заявки лежат в SQLite (один файл — удобно бэкапить).
- **Уведомление админу** о каждой заявке с кнопкой «💬 Написать клиенту».
- **Админ-панель** (edit-in-place дашборд): 🔄 Обновить, 📥 Экспорт CSV, 📋 Последние заявки с пагинацией ◀ 1/N ▶, 🏓 Ping, ◀ В меню.
- Совместимые slash-команды: `/start`, `/menu`, `/survey`, `/cancel`, `/help`; для админа дополнительно `/admin`, `/stats`, `/export`, `/ping`.

## Стек

- Python 3.11 + [aiogram 3](https://docs.aiogram.dev/) (async)
- SQLite через [aiosqlite](https://github.com/omnilib/aiosqlite)
- [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) для конфигурации из `.env`
- `pytest` + `ruff` + GitHub Actions

## Архитектура

```
lead-bot/
├── src/lead_bot/
│   ├── __main__.py      # вход: python -m lead_bot или `lead-bot`
│   ├── bot.py           # сборка Bot / Dispatcher / Router, setMyCommands
│   ├── config.py        # настройки из .env через pydantic-settings
│   ├── db.py            # LeadsRepo: SQLite + экспорт в CSV
│   ├── states.py        # FSM-состояния (Survey)
│   ├── texts.py         # все тексты в одном файле — легко перебрендировать
│   ├── keyboards.py     # фабрики inline / reply клавиатур
│   ├── views.py         # pure render-функции: (text, markup) для каждого экрана
│   ├── render.py        # I/O helper: edit-in-place с фоллбэком на новое сообщение
│   └── handlers/
│       ├── menu.py      # /start, /menu, /help — навигация
│       ├── survey.py    # FSM-анкета (back/cancel/restart) + подтверждение
│       └── admin.py     # /admin, /stats, /export, /ping + админ-панель
├── tests/               # юнит-тесты БД + smoke
├── Dockerfile
├── docker-compose.yml
├── railway.json         # для one-click деплоя на Railway
├── pyproject.toml
└── .env.example
```

Edit-in-place реализован как: каждое состояние = pure-функция в `views.py`,
возвращающая `View(text, markup)`. `render.py` хранит `message_id` главного
сообщения в FSM-контексте и обновляет его через `edit_message_text` с фоллбэком
на `send_message`, если редактирование невозможно (например, сообщение слишком
старое).

## Запуск локально

1. **Создай бота у [@BotFather](https://t.me/BotFather):** `/newbot` → имя → username → сохрани токен.
2. **Узнай свой Telegram chat_id:** напиши `/start` боту [@userinfobot](https://t.me/userinfobot), он выдаст числовой `Id`. Это твой `ADMIN_CHAT_ID`.
3. **Настрой `.env`:**
   ```bash
   cp .env.example .env
   # отредактируй BOT_TOKEN и ADMIN_CHAT_ID
   ```
4. **Поставь зависимости и запусти:**
   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -e ".[dev]"
   lead-bot
   ```
5. Открой бота в Telegram, нажми `/start`, пройди анкету. Уведомление о новой заявке прилетит тебе же в личку.

## Запуск в Docker

```bash
cp .env.example .env  # отредактируй переменные
docker compose up -d --build
docker compose logs -f
```

База будет лежать в `./data/leads.db` — путь смонтирован в контейнер, файл переживёт перезапуск.

## Деплой на Railway (5 минут)

1. Запушь репозиторий на GitHub.
2. Зарегистрируйся на [railway.com](https://railway.com), подключи GitHub.
3. **New Project → Deploy from GitHub repo** → выбери `tg-bots-portfolio`.
4. **Settings → Root Directory** = `lead-bot`.
5. **Variables** добавь:
   - `BOT_TOKEN` — токен от @BotFather
   - `ADMIN_CHAT_ID` — твой chat_id
   - `BUSINESS_NAME` — название клиента
   - `SERVICES` — список услуг через `;`
   - `DB_PATH=data/leads.db`
6. Railway соберёт по `Dockerfile` и запустит. Готово.

Для persistence базы — Railway Volume, смонтированный в `/app/data`. На демо необязательно.

## Деплой на VPS (Ubuntu, Docker)

```bash
# на сервере
git clone https://github.com/keepreverse/tg-bots-portfolio.git /opt/tg-bots && cd /opt/tg-bots/lead-bot
cp .env.example .env && nano .env
docker compose up -d --build
```

Готово, бот переживёт перезагрузку сервера (`restart: unless-stopped` в `docker-compose.yml`).

## Деплой на Synology NAS (Container Manager)

1. В **File Station** создай папку `/docker/lead-bot/`, положи в неё `.env`.
2. В **Container Manager → Project → Create** укажи путь к `docker-compose.yml` (можно загрузить из этого репо).
3. Build → Run. База будет в `./data/leads.db` рядом с проектом.

## Кастомизация под заказчика (10-15 минут)

- **Название бизнеса и список услуг** — в `.env` (`BUSINESS_NAME`, `SERVICES`).
- **Тексты сообщений** — `src/lead_bot/texts.py` (один файл).
- **Цвета/эмодзи/прогресс-бар** — `src/lead_bot/views.py`.
- **Дополнительные поля анкеты** — добавь состояние в `states.py`, шаг в `views.py`, переход в `handlers/survey.py`, поле в `db.py`.
- **Google Sheets / amoCRM / Bitrix24 вместо SQLite** — допиши вторую реализацию `LeadsRepo` (интерфейс ~30 строк).
- **Логотип/брендинг** — добавь картинку через `message.answer_photo(...)` в `handlers/menu.py`.

## Тесты и линт

```bash
pytest -v
ruff check .
```

CI прогоняет это автоматически на каждый push/PR — см. [`.github/workflows/lead-bot-ci.yml`](../.github/workflows/lead-bot-ci.yml) в корне репо.

## Лицензия

MIT — можно отдавать клиенту без ограничений.
