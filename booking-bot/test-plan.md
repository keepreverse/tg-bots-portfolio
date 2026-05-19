# booking-bot E2E test plan — PR #5

Scope: validate the 4 user-visible items added/changed in PR #5 + happy-path booking.
Bot under test: `@keepreverse_book_demo_bot` (running locally on Devin VM, polling).
Admin user: my own Telegram account (`ADMIN_CHAT_ID` matches).

## Source-code paths informing the plan

- `booking-bot/src/booking_bot/handlers/menu.py:23-86` — `is_admin()` + `main_menu(is_admin=...)`.
- `booking-bot/src/booking_bot/handlers/booking.py:109-125` — back-step dispatcher per FSM state.
- `booking-bot/src/booking_bot/handlers/booking.py:228-260` — name input → URL guard via `message_contains_link()`.
- `booking-bot/src/booking_bot/handlers/booking.py:275-296` — phone-text input → URL guard.
- `booking-bot/src/booking_bot/validators.py:1-68` — URL guard logic (regex + TG entities).
- `booking-bot/src/booking_bot/render.py:37-76` — edit-in-place; user replies are deleted (`render_message`).
- `booking-bot/src/booking_bot/views.py:_progress_bar`, `_filled_block` — progress bar + filled-block on every step.
- `booking-bot/src/booking_bot/views.py:admin_upcoming_screen` — slice by `ADMIN_UPCOMING_PAGE_SIZE = 5`.
- `booking-bot/src/booking_bot/handlers/admin.py:94-120` — `CB_ADMIN_UPCOMING:<page>` handler.

## Pre-conditions (set up before recording)

- Bot process is running locally on the VM via `python -m booking_bot` with secrets injected via `.env`.
- DB seeded with the standard 12 services (auto via `seed_services` on boot).
- For pagination test: 6 confirmed bookings pre-inserted via tiny SQL script (`INSERT INTO bookings ...`) at future times today/tomorrow.
- Bot is opened in Chrome on `https://web.telegram.org/` against `@keepreverse_book_demo_bot`.
- All previous test messages cleared from chat.

## T1 — Happy-path booking (primary, end-to-end)

Steps and per-step assertions:

1. Send `/start`.
   - **Expect**: a single message with text starting with `<b>Tattoo & Piercing</b>` (or "Tattoo & Piercing" bold), and 4 inline rows. Last row contains `🛠 Админ-панель`. **Fail** if the row is missing, or any "@your_master_username" placeholder appears.
2. Click `📅 Записаться`.
   - **Expect**: the **same** message is **edited in place** (same message id, no new message appended below). Text contains `▰▱▱▱▱▱ · Шаг 1 из 6`. Two category buttons: `🎨 Тату`, `💉 Пирсинг`. Footer row: `[✕ Отмена]` only (no `◀ Назад` at step 1). **Fail** if a new message appears below.
3. Click `🎨 Тату`.
   - **Expect**: edit-in-place to step 2 picker. Text contains `▰▰▱▱▱▱ · Шаг 2 из 6` and a bold header `🎨 Тату`. **No** `• Раздел:` line in the filled-block (redundant with the header). Service buttons list contains `Тату-минимал`. Footer row: `[◀ Назад] [✕ Отмена]`.
4. Click `Тату средний · 2 ч · 14 000 ₽`.
   - **Expect**: step 3 (date picker). Text contains `▰▰▰▱▱▱ · Шаг 3 из 6`, filled-block has 1 line: `Услуга: Тату средний`. Calendar grid is shown; today's date is selectable if working hours allow.
5. Click any future working day (e.g. next Monday).
   - **Expect**: step 4 (time picker). Text contains `▰▰▰▰▱▱ · Шаг 4 из 6`, filled-block now has 2 lines: `Услуга: …`, `Дата: 19 мая, Пн`. At least one time button (`HH:MM`) visible OR the message reads "На этот день не осталось свободного времени".
6. Click first available time.
   - **Expect**: step 5 (ask name). Text contains `▰▰▰▰▰▱ · Шаг 5 из 6`, filled-block has 3 lines incl. `Время: HH:MM`. Bot asks for name. Footer: `[◀ Назад] [✕ Отмена]`.
7. Send `Devin Test`.
   - **Expect**: my user message disappears. Main message is edited to step 6 (ask phone). Text contains `▰▰▰▰▰▰ · Шаг 6 из 6`, filled-block has `Имя: Devin Test`. A small *auxiliary* reply-keyboard message appears below offering `📱 Поделиться номером`.
8. Send `+79991234567` as text.
   - **Expect**: my user message disappears, the aux phone message disappears. Main message edited to the confirm screen. Text contains the booking summary (service, date range `HH:MM – HH:MM`, duration `N ч`, price). Buttons: `✓ Подтвердить`, `◀ Назад`, `✕ Отмена`.
9. Click `✓ Подтвердить`.
   - **Expect**: main message edited to `✅ <b>Запись подтверждена</b>` (no `#N` shown to the user), address `ул. Тверская, 7`, and a hyperlink `keepmaster` (no `@`) whose URL points to `https://t.me/keepmaster`. **Admin** receives a separate DM with `🟢 <b>Новая запись #N</b>` (id IS shown to admin).

## T2 — URL guard on name + phone

T2 starts after `/start` → `📅 Записаться` → `🎨 Тату` → `Тату-минимал` → first date → first time.

1. At the name prompt, send `https://example.com`.
   - **Expect**: my user message disappears. Main message is edited and starts with the error template (`⚠️` and text mentioning "не используй ссылок/упоминания"), followed by the same name prompt. State stays at `ask_name`. **Fail** if it proceeds to the phone step.
2. Send `Алекс`.
   - **Expect**: advances to phone step. Filled-block shows `Имя: Алекс`.
3. At the phone prompt, send `t.me/keepmaster`.
   - **Expect**: my user message disappears. Main message is edited with the phone error template (about links) + phone prompt. State stays at `ask_phone`. **Fail** if it advances to confirm.
4. Send `+79991234567`.
   - **Expect**: advances to confirm screen as in T1 step 8.

Pass criteria: a working implementation rejects step 1 and step 3 with a link-specific error; a broken implementation would accept them and advance to the next step.

## T3 — ◀ Назад on every FSM step (regression of new feature)

Starting fresh `/start` → `📅 Записаться`:

1. Step 1 (category): NO `◀ Назад` button is shown; only `✕ Отмена`. **Fail** if ◀ Назад appears at step 1.
2. Click `🎨 Тату` (now step 2) → click `◀ Назад` → must be back at step 1 (category), text `Шаг 1 из 6`, no filled-block.
3. Re-do step 2, 3, 4 → arrive at time picker → click `◀ Назад` → must be back at step 3 (date picker) with the same service. Filled-block shows `Услуга` only (not `Дата`/`Время`; `Раздел` is in the header, not filled-block).
4. Re-pick date+time → at ask_name step click `◀ Назад` → must be at time picker for the *same* date.
5. Type name `Алекс` → at ask_phone step click `◀ Назад` → must be at ask_name with `Имя: Алекс` *removed* from filled-block (because it was popped).
6. Re-type name, type phone → at confirm screen click `◀ Назад` → must be at ask_phone with `Телефон` *removed* from filled-block.

Pass criteria: each back press returns to the previous prompt with the corresponding field popped from the filled-block.

## T4 — Paginated «Ближайшие записи» in admin

Before recording: seed 6 confirmed bookings via a Python one-shot using the same `BookingsRepo` so pagination yields exactly 2 pages (5 + 1).

1. `/start` → click `🛠 Админ-панель`.
   - **Expect**: edit-in-place to admin menu with rows for `📊 Статистика`, `📆 Сегодня`, `📋 Ближайшие записи`, `📥 Экспорт CSV`, `◀ В меню`.
2. Click `📋 Ближайшие записи`.
   - **Expect**: header `<b>📋 Ближайшие записи</b> · стр. 1/2`. Exactly 5 booking cards visible. Each card shows `#N`, service emoji+name, client name `Client N`, phone, date/time. Pagination row: `[1/2] [▶]` (no `◀` on page 1). Below: `[◀ В админ-меню]`.
3. Click `▶`.
   - **Expect**: header `стр. 2/2`. Exactly 1 booking card visible (the 6th). Pagination row: `[◀] [2/2]` (no `▶`).
4. Click `◀`.
   - **Expect**: returns to page 1 as in step 2.
5. Click `◀ В админ-меню`.
   - **Expect**: edit-in-place back to admin menu.

Pass criteria: pagination boundaries hide the appropriate arrow; per-page count is exactly 5 then 1; header reflects current page.

## Recording

One continuous recording covering T1 → T2 → T3 → T4 in Telegram Web (Chrome maximized).

`annotate_recording` markers:
- `setup` "Bot started, Telegram Web open"
- `test_start` "It should complete a happy-path booking end-to-end"
- assertions after each major step
- `test_start` "It should reject URLs in name and phone fields"
- `test_start` "It should support ◀ Назад on every booking step"
- `test_start` "It should paginate admin upcoming list 5/page"

## Out of scope (covered by unit tests, will note in report only)

- Non-admin user does NOT see `🛠 Админ-панель` — covered by `tests/test_views.py::test_main_menu_admin_button_only_for_admin` (passed locally).
- Slot conflict / overlap-check (`SlotConflict` path).
- Reminders at 24h / 2h (scheduler interval; not exercisable in a short recording).
