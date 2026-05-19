# booking-bot — Telegram-бот для записи к мастеру

[![CI](https://github.com/keepreverse/tg-bots-portfolio/actions/workflows/booking-bot-ci.yml/badge.svg?branch=main)](https://github.com/keepreverse/tg-bots-portfolio/actions/workflows/booking-bot-ci.yml)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![aiogram](https://img.shields.io/badge/aiogram-3.x-2CA5E0.svg)](https://docs.aiogram.dev/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](../LICENSE)

Telegram-бот-расписание для соло-мастера (тату, пирсинг, бровист и т. п.):
часовая сетка слотов, переменные длительности услуг (от 30 минут до 4 часов),
**встроенный 30-минутный буфер между клиентами**, защита от двойной брони,
напоминания за 24 и 2 часа.

UX, как у lead-bot:
- одно главное сообщение, которое **редактируется в месте**, а не флудит чат;
- календарь и сетка слотов — большими тапабельными кнопками;
- мастер видит сегодняшние, ближайшие и все записи в админ-панели плюс
  получает мгновенный пинг при новой записи.

## Как пользователь видит флоу

```
🗓 Записаться
      ↓
  🎨 Тату / 💉 Пирсинг
      ↓
  список услуг (длительность + цена)
      ↓
  календарь — активны только рабочие дни (по умолчанию Вт, Чт, Сб, Вс)
      ↓
  свободные часовые слоты на выбранный день
      ↓
  «как к вам обращаться?» → телефон (по кнопке или вручную)
      ↓
  карточка-подтверждение → ✅ Подтвердить
      ↓
  «✅ Записал. 📍 Адрес. 👨‍🎨 Мастер. Напомню за 24 ч и 2 ч.»
```

Мастер в это же время получает в личку:

```
🔔 Новая запись #42
🎨 Тату средний — 2 ч — 14 000 ₽
🗓 19 мая, Вт · 14:00–16:00
👤 Алексей · +79991112233 · @alex_user
```

## Ключевые архитектурные решения

1. **Часовой шаг сетки**, и точка. `SLOT_STEP_MINUTES = 60` зашит в код, в `.env`
   менять нельзя — `config.py` упадёт при старте. Никаких 30-минутных слотов в UI:
   30-минутные услуги всё равно занимают целый часовой слот, остаток времени —
   и есть тот самый «буфер для подготовки».
2. **30-минутный буфер между бронированиями.** Реализован **в момент проверки
   перекрытия**: при сравнении интервалов конец каждой существующей брони
   раздувается на `BOOKING_BUFFER_AFTER_MINUTES` (по умолчанию 30 минут).
   В БД хранится «настоящий» `end_at_utc` без padding'а — буфер существует
   только в логике, не в данных.

   Следствия (см. `tests/test_slots.py`):
   - 12:00–14:00 (2 ч) → следующая свободная **15:00**, а не 14:00 (один шаг пропуска).
   - 12:00–12:30 (30 мин) → следующая свободная **13:00** (естественный пробел из сетки).
   - 12:00–16:00 (4 ч) → следующая свободная **17:00**.
3. **Race-condition защита.** Запись создаётся в `BEGIN IMMEDIATE`-транзакции
   с **повторной** проверкой перекрытия (с тем же буфером) непосредственно перед
   `INSERT`. Если за это время кто-то успел занять время — пользователь
   видит «😔 Кто-то уже занял, выберите другой слот».
4. **Хранение в UTC, рендер в `MASTER_TZ`.** Все границы дня, неделя, рабочее окно,
   `now_utc` приводятся через `zoneinfo`.
5. **APScheduler-ремайндеры** запускаются раз в 5 минут (`interval`) и шлют
   тем, для кого подошло 24 ч / 2 ч; повторы исключены через таблицу
   `reminders_sent (booking_id, kind)`.

## Услуги (seed)

11 услуг в `data/seed_services.json`:

**🎨 Тату**
- 🖤 Тату-минимал (до 5×5 см) — 30 мин — 5 000 ₽
- 🎨 Тату средний (до 15×15 см) — 2 ч — 14 000 ₽
- 🌹 Тату крупный (рукав, сессия) — 4 ч — 25 000 ₽
- 🔁 Перекрытие старой тату (сессия) — 3 ч — 18 000 ₽
- 📐 Консультация эскиза — 30 мин — бесплатно

**💉 Пирсинг**
- 👂 Прокол мочки уха — 30 мин — 2 000 ₽
- 👂 Прокол хряща уха (хеликс / трагус) — 30 мин — 3 000 ₽
- 👃 Прокол крыла носа — 30 мин — 2 500 ₽
- 👃 Прокол септума — 30 мин — 3 500 ₽
- 💋 Прокол губы — 30 мин — 3 500 ₽
- 📐 Консультация по пирсингу — 30 мин — бесплатно

Чтобы заменить список под конкретного клиента — отредактируйте JSON и удалите
файл `data/booking.db` (или сделайте `DROP TABLE services`); при следующем
старте бот пере-seed-ит таблицу.

## Структура проекта

```
booking-bot/
├── .env.example
├── Dockerfile
├── README.md
├── data/
│   └── seed_services.json
├── docker-compose.yml
├── pyproject.toml
├── railway.json
├── src/booking_bot/
│   ├── __init__.py
│   ├── __main__.py        # entry-point
│   ├── bot.py             # Dispatcher + APScheduler bootstrap
│   ├── calendar_ui.py     # month-grid keyboard
│   ├── config.py          # pydantic-settings, hard checks on slot step / buffer
│   ├── db.py              # SQLite schema, ServicesRepo, BookingsRepo, WorkingHoursRepo
│   ├── duration.py        # format_duration(30) -> "30 мин"
│   ├── handlers/          # aiogram3 routers
│   │   ├── __init__.py
│   │   ├── admin.py
│   │   ├── booking.py
│   │   ├── menu.py
│   │   └── my_bookings.py
│   ├── keyboards.py       # inline & reply keyboards
│   ├── money.py           # format_price(2000) -> "2 000 ₽"
│   ├── render.py          # edit-in-place helper
│   ├── scheduler.py       # 24h/2h reminders via APScheduler
│   ├── slots.py           # available_starts(...) — pure, fully unit-tested
│   ├── states.py          # FSM
│   ├── texts.py           # all UI copy
│   ├── timez.py           # UTC<->MASTER_TZ helpers
│   └── views.py           # (text, keyboard) builders, no I/O
└── tests/
    ├── conftest.py
    ├── test_db.py         # schema, repos, overlap-with-buffer
    ├── test_duration.py
    ├── test_slots.py      # 16 cases — full matrix from playbook §2.11
    ├── test_smoke.py      # config + Dispatcher boot
    └── test_views.py      # screens render expected text
```

## Быстрый старт локально

```bash
git clone https://github.com/keepreverse/tg-bots-portfolio.git
cd tg-bots-portfolio/booking-bot

python -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

cp .env.example .env
# отредактируйте .env (минимум BOT_TOKEN и ADMIN_CHAT_ID — id админа в TG)

booking-bot                       # или: python -m booking_bot
```

База создаётся автоматически в `data/booking.db`, services — из `data/seed_services.json`.

## Тесты и линтер

```bash
ruff check .
pytest -v
```

82 юнит-теста, прогон ~2 сек. Покрываются:
- 16 кейсов slot-генератора (буфер, длительности, рабочее окно, прошлое, выходные);
- 13 кейсов `format_duration`;
- 10 кейсов БД (seed, перекрытие с буфером, отмена, статистика, CSV);
- 20 кейсов URL-guard и валидации имени/телефона;
- 17 view-тестов (экраны рендерятся правильным текстом, админ-карточки);
- 6 smoke (валидация config, сборка Dispatcher).

## Деплой

Файлы готовы:
- `Dockerfile` — собирает образ, на старте `booking-bot` (console_script);
- `docker-compose.yml` — `restart: unless-stopped`, volume `./data`;
- `railway.json` — Railway сразу подхватит при подключении репо.

### Railway

1. Зарегистрируйся на [railway.com](https://railway.com), вход через GitHub.
2. `New Project → Deploy from GitHub repo → keepreverse/tg-bots-portfolio`.
3. `Settings → Root Directory = booking-bot`.
4. `Variables` — впиши `BOT_TOKEN`, `ADMIN_CHAT_ID`, `BUSINESS_NAME`, …
5. Railway соберёт Docker и поднимет.
   Цена: ~$5/мес после $5 стартовых кредитов.

### Synology NAS (или любая Linux-машина)

```bash
ssh ваш-NAS
mkdir -p /volume1/docker/booking-bot && cd /volume1/docker/booking-bot
git clone https://github.com/keepreverse/tg-bots-portfolio.git src
ln -s src/booking-bot/docker-compose.yml docker-compose.yml
cp src/booking-bot/.env.example .env  # отредактируйте
docker-compose up -d --build
```

Бот пишет SQLite в `./data/booking.db` (volume в compose), при апдейте репо:
`git -C src pull && docker-compose up -d --build` — данные сохранятся.

## Что можно подкрутить под клиента

| Что | Где |
|---|---|
| Услуги, цены, длительности | `data/seed_services.json` + удалить `data/booking.db` |
| Рабочие дни / часы | На лету: SQL `UPDATE working_hours …`. Дефолт в `db.py: DEFAULT_WORKING_HOURS`. |
| Закрытие конкретного дня | INSERT в `day_overrides(date_local, NULL, NULL)` |
| Текст приветствия / название салона | `.env: BUSINESS_NAME`, тексты — `texts.py` |
| Буфер между клиентами | `.env: BOOKING_BUFFER_AFTER_MINUTES` (по умолчанию 30; кратно 30) |
| Горизонт записи | `.env: BOOKING_HORIZON_DAYS` |
| Часовой пояс | `.env: MASTER_TZ` (`Europe/Moscow`, `Asia/Yekaterinburg`, …) |

## Anti-patterns (чтоб случайно не сломать архитектуру)

- ❌ **Не делай `SLOT_STEP_MINUTES = 30`**. UI спроектирован под часовой ритм;
  тестовая матрица — тоже. Если очень надо — обсудим отдельно.
- ❌ **Не сохраняй буфер в `bookings.end_at_utc`**. Это сломает `Мои записи`
  («у меня тату на 14:00–15:30 — что за 15:30??»). Буфер — только в логике.
- ❌ **Не округляй 30-минутные услуги до часа в БД** — потеряется суть прайса
  (например, прокол мочки за 2 000 ₽ != тату-минимал за 5 000 ₽, оба 30 мин).
- ❌ **Не дублируй проверку перекрытия только в slots.py** — обязательно
  recheck в `BEGIN IMMEDIATE` (без него гонкой пройдёт двойная бронь).

## Лицензия

[MIT](../LICENSE) — можно использовать как угодно (включая коммерчески).
