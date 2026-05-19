# tg-bots-portfolio — каталог Telegram-ботов под коммерческие заказы

[![lead-bot CI](https://github.com/keepreverse/tg-bots-portfolio/actions/workflows/lead-bot-ci.yml/badge.svg)](https://github.com/keepreverse/tg-bots-portfolio/actions/workflows/lead-bot-ci.yml)
[![booking-bot CI](https://github.com/keepreverse/tg-bots-portfolio/actions/workflows/booking-bot-ci.yml/badge.svg)](https://github.com/keepreverse/tg-bots-portfolio/actions/workflows/booking-bot-ci.yml)
[![quiz-bot CI](https://github.com/keepreverse/tg-bots-portfolio/actions/workflows/quiz-bot-ci.yml/badge.svg)](https://github.com/keepreverse/tg-bots-portfolio/actions/workflows/quiz-bot-ci.yml)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![aiogram](https://img.shields.io/badge/aiogram-3.x-2CA5E0.svg)](https://docs.aiogram.dev/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)

Портфолио рабочих Telegram-ботов под коммерческие заказы.
Каждый бот — самостоятельный проект, готовый к развёртыванию на VPS, Railway или Render.

## Боты

| Бот | Описание | Статус |
| --- | --- | --- |
| [lead-bot](./lead-bot) | Сбор заявок: FSM-анкета с прогресс-баром → SQLite → уведомление админу + экспорт CSV. Edit-in-place UX. | готов |
| [booking-bot](./booking-bot) | Запись к мастеру (тату/пирсинг/брови): часовая сетка слотов, переменные длительности 30–240 мин, защита от двойной брони, напоминания за 24 ч и 2 ч. | готов |
| [quiz-bot](./quiz-bot) | Квиз-калькулятор: задаёт вопросы, считает диапазон цены (min–max), собирает контакт лида. Multi-категория из коробки (демо: 🔨 ремонт + 🎓 репетитор). Перебрендирование = правка одного JSON. | готов |

## Стек

- Python 3.11+
- [aiogram 3](https://docs.aiogram.dev/) — async Telegram Bot API
- SQLite через `aiosqlite` (или PostgreSQL под нагрузку)
- `pydantic-settings` для конфигурации из `.env`
- `pytest` + `ruff` + GitHub Actions CI
- Docker / docker-compose / Railway one-click

## Лицензия

MIT — свободно используй как основу для коммерческих заказов.
