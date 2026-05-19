"""Quiz FSM: category picker → intro → answering → warmup → result → lead capture.

The quiz progress is stored in `state.data` as:

    {
      "category_key":   "renovation",
      "answers":        [["type","capital"], ["area","40_60"], ...],  # ordered
      "step_index":     2,                  # which question is currently shown
      "warmup_shown":   True,               # set when the warm-up screen passes
      "stage":          "answering" | "result" | "ask_name" | "ask_phone",
    }

We keep the state hand-rolled (rather than one FSM state per question) because
the question count is data-driven and could vary per quiz config.
"""

from __future__ import annotations

import json
from contextlib import suppress

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from .. import texts
from ..config import Settings, get_settings
from ..db import EventsRepo, LeadsRepo
from ..keyboards import (
    CB_ANSWER,
    CB_BACK,
    CB_CANCEL,
    CB_PICK_CAT,
    CB_RESTART,
    CB_RESULT_CTA,
    CB_WARMUP_GO,
    CB_WARMUP_SKIP,
    lead_admin_dm_kb,
    phone_reply_kb,
)
from ..quiz_engine import (
    Category,
    QuizConfig,
    QuizProgress,
    calculate_price,
)
from ..render import (
    MAIN_MSG_KEY,
    PHONE_AUX_MSG_KEY,
    clear_reply_keyboard,
    remove_phone_aux,
    render,
    render_callback,
    render_message,
)
from ..states import QuizFlow
from ..validators import message_contains_link, normalise_phone
from ..views import (
    ask_name_view,
    ask_phone_view,
    category_intro_view,
    category_picker_view,
    lead_done_view,
    main_menu_view,
    question_view,
    result_view,
    warmup_view,
)

_NAME_MIN = 2
_NAME_MAX = 100


def _is_admin(user_id: int | None, settings: Settings) -> bool:
    return user_id is not None and user_id == settings.ADMIN_CHAT_ID


# ---------------------------------------------------------------------------
# Helpers for FSM state shape
# ---------------------------------------------------------------------------


async def _load_progress(state: FSMContext) -> QuizProgress | None:
    data = await state.get_data()
    cat_key = data.get("category_key")
    if not isinstance(cat_key, str):
        return None
    answers_raw = data.get("answers", [])
    if not isinstance(answers_raw, list):
        return None
    answers: list[tuple[str, str]] = []
    for pair in answers_raw:
        if isinstance(pair, (list, tuple)) and len(pair) == 2:
            answers.append((str(pair[0]), str(pair[1])))
    return QuizProgress(category_key=cat_key, answers=tuple(answers))


async def _save_progress(state: FSMContext, progress: QuizProgress) -> None:
    await state.update_data(
        category_key=progress.category_key,
        answers=[list(p) for p in progress.answers],
    )


async def _reset_quiz_state(state: FSMContext) -> None:
    """Drop quiz-specific keys while preserving the rendering id."""
    data = await state.get_data()
    keep: dict[str, object] = {}
    if data.get(MAIN_MSG_KEY) is not None:
        keep[MAIN_MSG_KEY] = data[MAIN_MSG_KEY]
    await state.set_state(None)
    await state.set_data(keep)


def _build_lead_summary_for_admin(category: Category, progress: QuizProgress) -> str:
    lines = [f"{category.emoji} <b>{category.title}</b>"]
    for q_key, opt_key in progress.answers:
        q = category.question_by_key(q_key)
        if q is None:
            continue
        opt = q.option_by_key(opt_key)
        if opt is None:
            continue
        lines.append(f"• {q.title}: {opt.label}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


def build_quiz_router(*, config: QuizConfig) -> Router:
    router = Router(name="quiz")

    # ---- entry: pick category --------------------------------------------

    @router.callback_query(F.data.startswith(f"{CB_PICK_CAT}:"))
    async def pick_category(cq: CallbackQuery, state: FSMContext) -> None:
        payload = cq.data.split(":", 2) if cq.data else []
        if len(payload) < 2:
            await cq.answer()
            return
        cat_key = payload[1]
        go_immediately = len(payload) >= 3 and payload[2] == "go"

        # Special "_only" key: single-category mode entry button.
        if cat_key == "_only":
            if len(config.categories) != 1:
                await cq.answer()
                return
            cat = config.categories[0]
        else:
            cat = config.category_by_key(cat_key)
            if cat is None:
                await cq.answer()
                return

        if go_immediately:
            await _enter_category_first_question(cq, state, cat)
            return

        view = category_intro_view(cat, allow_back=len(config.categories) > 1)
        # Mark that the user is in "answering" but haven't picked first answer yet.
        await state.set_state(QuizFlow.answering)
        await _save_progress(state, QuizProgress(category_key=cat.key, answers=()))
        await state.update_data(step_index=0, warmup_shown=False)
        # Log a "start" event for this user/category (used by funnel stats).
        s = get_settings()
        repo = EventsRepo(s.db_path_abs)
        await repo.log(
            user_tg_id=cq.from_user.id,
            category_key=cat.key,
            event_kind="start",
        )
        await render_callback(cq, state, view.text, view.markup)

    async def _enter_category_first_question(
        cq: CallbackQuery,
        state: FSMContext,
        cat: Category,
    ) -> None:
        await state.set_state(QuizFlow.answering)
        await _save_progress(state, QuizProgress(category_key=cat.key, answers=()))
        await state.update_data(step_index=0, warmup_shown=False)
        s = get_settings()
        repo = EventsRepo(s.db_path_abs)
        await repo.log(
            user_tg_id=cq.from_user.id,
            category_key=cat.key,
            event_kind="step",
            step_index=0,
        )
        view = question_view(
            cat,
            cat.question_at(0),
            step_index=0,
            allow_back=len(config.categories) > 1,
        )
        await render_callback(cq, state, view.text, view.markup)

    # ---- answer a question -----------------------------------------------

    @router.callback_query(F.data.startswith(f"{CB_ANSWER}:"))
    async def answer(cq: CallbackQuery, state: FSMContext) -> None:
        if cq.data is None:
            await cq.answer()
            return
        _, opt_key = cq.data.split(":", 1)

        progress = await _load_progress(state)
        if progress is None:
            await cq.answer()
            return
        cat = config.category_by_key(progress.category_key)
        if cat is None:
            await cq.answer()
            return

        data = await state.get_data()
        step_index = int(data.get("step_index", 0))
        question = cat.question_at(step_index)
        if question is None:
            await cq.answer()
            return
        # Validate the answer is one of the question's options.
        if question.option_by_key(opt_key) is None:
            await cq.answer()
            return

        progress = progress.with_answer(question.key, opt_key)
        await _save_progress(state, progress)

        next_step = step_index + 1
        s = get_settings()
        evts = EventsRepo(s.db_path_abs)
        # Are we done?
        if next_step >= cat.total_steps:
            await evts.log(
                user_tg_id=cq.from_user.id,
                category_key=cat.key,
                event_kind="result",
            )
            await _show_result(cq, state, cat, progress)
            return

        # Warm-up?
        warmup_shown = bool(data.get("warmup_shown"))
        if (
            not warmup_shown
            and cat.warmup_after_index is not None
            and step_index == cat.warmup_after_index
        ):
            await state.update_data(step_index=next_step, warmup_shown=True)
            view = warmup_view(cat, progress, currency_label=config.currency_label)
            await render_callback(cq, state, view.text, view.markup)
            return

        # Just advance.
        await evts.log(
            user_tg_id=cq.from_user.id,
            category_key=cat.key,
            event_kind="step",
            step_index=next_step,
        )
        await state.update_data(step_index=next_step)
        view = question_view(
            cat,
            cat.question_at(next_step),
            step_index=next_step,
            allow_back=True,
        )
        await render_callback(cq, state, view.text, view.markup)

    # ---- warm-up "go" ----------------------------------------------------

    @router.callback_query(F.data == f"{CB_WARMUP_GO}:0")
    async def warmup_go(cq: CallbackQuery, state: FSMContext) -> None:
        progress = await _load_progress(state)
        if progress is None:
            await cq.answer()
            return
        cat = config.category_by_key(progress.category_key)
        if cat is None:
            await cq.answer()
            return
        data = await state.get_data()
        step_index = int(data.get("step_index", 0))
        s = get_settings()
        evts = EventsRepo(s.db_path_abs)
        await evts.log(
            user_tg_id=cq.from_user.id,
            category_key=cat.key,
            event_kind="step",
            step_index=step_index,
        )
        view = question_view(
            cat,
            cat.question_at(step_index),
            step_index=step_index,
            allow_back=True,
        )
        await render_callback(cq, state, view.text, view.markup)

    @router.callback_query(F.data == f"{CB_WARMUP_SKIP}:0")
    async def warmup_skip(cq: CallbackQuery, state: FSMContext) -> None:
        """User wants to jump straight from warmup to the calculated result.

        We compute the price range based on already-collected answers and
        skip the remaining questions. This is intentionally a lower-priority
        button on the warmup screen — most users should answer all the
        questions so the calc is more accurate (and we collect richer leads).
        """
        progress = await _load_progress(state)
        if progress is None:
            await cq.answer()
            return
        cat = config.category_by_key(progress.category_key)
        if cat is None:
            await cq.answer()
            return
        s = get_settings()
        evts = EventsRepo(s.db_path_abs)
        await evts.log(
            user_tg_id=cq.from_user.id,
            category_key=cat.key,
            event_kind="result",
        )
        await _show_result(cq, state, cat, progress)

    # ---- back & cancel ---------------------------------------------------

    @router.callback_query(F.data == f"{CB_BACK}:0")
    async def back_step(cq: CallbackQuery, state: FSMContext) -> None:
        cur_state = await state.get_state()
        progress = await _load_progress(state)
        if progress is None:
            # No quiz to go back inside. Treat as cancel.
            await _back_to_main(cq, state)
            return

        if cur_state == QuizFlow.ask_phone.state:
            # phone → name
            await state.set_state(QuizFlow.ask_name)
            cat = config.category_by_key(progress.category_key)
            if cat is None:
                await _back_to_main(cq, state)
                return
            if cq.message is not None:
                await remove_phone_aux(cq.bot, cq.message.chat.id, state)
            view = ask_name_view(category=cat, progress=progress, currency_label=config.currency_label)
            await render_callback(cq, state, view.text, view.markup)
            return

        if cur_state == QuizFlow.ask_name.state:
            # name → result
            cat = config.category_by_key(progress.category_key)
            if cat is None:
                await _back_to_main(cq, state)
                return
            await _show_result(cq, state, cat, progress)
            return

        if cur_state == QuizFlow.show_result.state:
            # result → last answered question (works correctly both when the
            # user completed all questions AND when they skipped from warm-up).
            cat = config.category_by_key(progress.category_key)
            if cat is None:
                await _back_to_main(cq, state)
                return
            new_progress = progress.without_last()
            await _save_progress(state, new_progress)
            new_step = len(new_progress.answers)
            await state.set_state(QuizFlow.answering)
            await state.update_data(step_index=new_step, warmup_shown=True)
            view = question_view(
                cat,
                cat.question_at(new_step),
                step_index=new_step,
                allow_back=True,
            )
            await render_callback(cq, state, view.text, view.markup)
            return

        # Inside `answering`: pop last answer, decrement step_index.
        data = await state.get_data()
        step_index = int(data.get("step_index", 0))
        cat = config.category_by_key(progress.category_key)
        if cat is None:
            await _back_to_main(cq, state)
            return

        if step_index <= 0:
            # Go back to category picker (or main menu if single-category mode).
            if len(config.categories) > 1:
                await _reset_quiz_state(state)
                view = category_picker_view(config)
                await render_callback(cq, state, view.text, view.markup)
            else:
                await _back_to_main(cq, state)
            return

        new_progress = progress.without_last()
        await _save_progress(state, new_progress)
        new_step = step_index - 1
        await state.update_data(step_index=new_step)
        view = question_view(
            cat,
            cat.question_at(new_step),
            step_index=new_step,
            allow_back=True,
        )
        await render_callback(cq, state, view.text, view.markup)

    @router.callback_query(F.data == f"{CB_CANCEL}:0")
    async def cancel_quiz(cq: CallbackQuery, state: FSMContext) -> None:
        await _back_to_main(cq, state)

    async def _back_to_main(cq: CallbackQuery, state: FSMContext) -> None:
        s = get_settings()
        if cq.message is not None:
            await remove_phone_aux(cq.bot, cq.message.chat.id, state)
        await _reset_quiz_state(state)
        view = main_menu_view(
            config=config,
            business_name=s.BUSINESS_NAME,
            is_admin=_is_admin(cq.from_user.id, s),
        )
        await render_callback(cq, state, view.text, view.markup)

    # ---- result -> CTA path ----------------------------------------------

    async def _show_result(
        cq: CallbackQuery,
        state: FSMContext,
        cat: Category,
        progress: QuizProgress,
    ) -> None:
        await state.set_state(QuizFlow.show_result)
        view = result_view(cat, progress, currency_label=config.currency_label)
        await render_callback(cq, state, view.text, view.markup)

    @router.callback_query(F.data == f"{CB_RESTART}:0")
    async def restart_quiz(cq: CallbackQuery, state: FSMContext) -> None:
        await _reset_quiz_state(state)
        if len(config.categories) > 1:
            view = category_picker_view(config)
            await render_callback(cq, state, view.text, view.markup)
        else:
            cat = config.categories[0]
            await _enter_category_first_question(cq, state, cat)

    @router.callback_query(F.data == f"{CB_RESULT_CTA}:0")
    async def result_cta(cq: CallbackQuery, state: FSMContext) -> None:
        progress = await _load_progress(state)
        if progress is None:
            await cq.answer()
            return
        cat = config.category_by_key(progress.category_key)
        if cat is None:
            await cq.answer()
            return
        await state.set_state(QuizFlow.ask_name)
        view = ask_name_view(category=cat, progress=progress, currency_label=config.currency_label)
        await render_callback(cq, state, view.text, view.markup)

    # ---- ask name (text input) -------------------------------------------

    @router.message(QuizFlow.ask_name)
    async def on_name(msg: Message, state: FSMContext) -> None:
        progress = await _load_progress(state)
        if progress is None:
            return
        cat = config.category_by_key(progress.category_key)
        if cat is None:
            return
        text = (msg.text or "").strip()
        if message_contains_link(text, msg.entities):
            await _reprompt_name(msg, state, cat, progress, texts.INVALID_NAME_LINK)
            return
        if len(text) < _NAME_MIN:
            await _reprompt_name(msg, state, cat, progress, texts.INVALID_NAME_SHORT)
            return
        if len(text) > _NAME_MAX:
            await _reprompt_name(msg, state, cat, progress, texts.INVALID_NAME_LONG)
            return
        await state.update_data(full_name=text)
        await state.set_state(QuizFlow.ask_phone)
        view = ask_phone_view(category=cat, progress=progress, currency_label=config.currency_label)
        await render_message(msg, state, view.text, view.markup)
        # Show the request-contact reply keyboard as a small aux message.
        aux = await msg.bot.send_message(
            chat_id=msg.chat.id,
            text=texts.PHONE_AUX_HINT,
            reply_markup=phone_reply_kb(),
        )
        await state.update_data({PHONE_AUX_MSG_KEY: aux.message_id})

    async def _reprompt_name(
        msg: Message,
        state: FSMContext,
        cat: Category,
        progress: QuizProgress,
        warn: str,
    ) -> None:
        with suppress(Exception):
            await msg.delete()
        # Show the warning along with the prompt.
        view = ask_name_view(category=cat, progress=progress, currency_label=config.currency_label)
        text = f"{warn}\n\n{view.text}"
        await render(msg.bot, msg.chat.id, state, text, view.markup)

    # ---- ask phone -------------------------------------------------------

    @router.message(QuizFlow.ask_phone, F.contact)
    async def on_phone_contact(msg: Message, state: FSMContext) -> None:
        await _process_phone(msg, state, raw=msg.contact.phone_number if msg.contact else "")

    @router.message(QuizFlow.ask_phone)
    async def on_phone_text(msg: Message, state: FSMContext) -> None:
        if message_contains_link(msg.text, msg.entities):
            await _reprompt_phone(msg, state, texts.INVALID_PHONE_LINK)
            return
        await _process_phone(msg, state, raw=msg.text or "")

    async def _process_phone(msg: Message, state: FSMContext, *, raw: str) -> None:
        normalised = normalise_phone(raw)
        if normalised is None:
            await _reprompt_phone(msg, state, texts.INVALID_PHONE)
            return
        progress = await _load_progress(state)
        if progress is None:
            return
        cat = config.category_by_key(progress.category_key)
        if cat is None:
            return

        data = await state.get_data()
        full_name = str(data.get("full_name") or "(не указано)")

        s = get_settings()
        price = calculate_price(cat, progress)
        leads_repo = LeadsRepo(s.db_path_abs)
        evts_repo = EventsRepo(s.db_path_abs)

        # Snapshot of answers, including human-readable labels.
        snapshot: list[tuple[str, str, str, str]] = []
        for q_key, opt_key in progress.answers:
            q = cat.question_by_key(q_key)
            if q is None:
                continue
            opt = q.option_by_key(opt_key)
            if opt is None:
                continue
            snapshot.append((q.key, q.title, opt.key, opt.label))

        lead_id = await leads_repo.create(
            user_tg_id=msg.from_user.id if msg.from_user else 0,
            user_username=(msg.from_user.username if msg.from_user else None),
            category_key=cat.key,
            category_title=cat.title,
            answers=snapshot,
            price_min=price.min_total,
            price_max=price.max_total,
            price_unit_label=cat.price_unit_label,
            full_name=full_name,
            phone=normalised,
        )
        await evts_repo.log(
            user_tg_id=msg.from_user.id if msg.from_user else 0,
            category_key=cat.key,
            event_kind="lead",
        )

        # Notify admin in DM.
        await _notify_admin(
            msg.bot,
            settings=s,
            lead_id=lead_id,
            cat=cat,
            progress=progress,
            price_min=price.min_total,
            price_max=price.max_total,
            currency_label=config.currency_label,
            full_name=full_name,
            phone=normalised,
            user_tg_id=msg.from_user.id if msg.from_user else None,
            username=msg.from_user.username if msg.from_user else None,
        )

        # Clean up the temporary reply keyboard.
        await remove_phone_aux(msg.bot, msg.chat.id, state)
        await clear_reply_keyboard(msg.bot, msg.chat.id)

        view = lead_done_view(
            category=cat,
            price=price,
            currency_label=config.currency_label,
            master_handle=s.master_handle_username,
            master_url=s.master_telegram_url,
        )
        await _reset_quiz_state(state)
        await render_message(msg, state, view.text, view.markup)

    async def _reprompt_phone(msg: Message, state: FSMContext, warn: str) -> None:
        progress = await _load_progress(state)
        if progress is None:
            return
        cat = config.category_by_key(progress.category_key)
        if cat is None:
            return
        with suppress(Exception):
            await msg.delete()
        view = ask_phone_view(category=cat, progress=progress, currency_label=config.currency_label)
        text = f"{warn}\n\n{view.text}"
        await render(msg.bot, msg.chat.id, state, text, view.markup)

    @router.message(Command("quiz"))
    async def quiz_cmd(msg: Message, state: FSMContext) -> None:
        """Restart the quiz from the category picker."""
        with suppress(Exception):
            await msg.delete()
        await _reset_quiz_state(state)
        if len(config.categories) > 1:
            view = category_picker_view(config)
        else:
            view = category_intro_view(config.categories[0], allow_back=False)
            await state.set_state(QuizFlow.answering)
            await _save_progress(state, QuizProgress(category_key=config.categories[0].key, answers=()))
            await state.update_data(step_index=0, warmup_shown=False)
        await render(msg.bot, msg.chat.id, state, view.text, view.markup)

    return router


# ---------------------------------------------------------------------------
# Admin notification (extracted so it can be reused/tested)
# ---------------------------------------------------------------------------


async def _notify_admin(
    bot: Bot,
    *,
    settings: Settings,
    lead_id: int,
    cat: Category,
    progress: QuizProgress,
    price_min: int,
    price_max: int,
    currency_label: str,
    full_name: str,
    phone: str,
    user_tg_id: int | None,
    username: str | None,
) -> None:
    from ..money import format_range

    price_str = format_range(
        price_min,
        price_max,
        currency=currency_label,
        unit_suffix=cat.price_unit_label,
    )
    if username:
        tg_link = f"@{username}"
    elif user_tg_id is not None:
        tg_link = f"<a href=\"tg://user?id={user_tg_id}\">id:{user_tg_id}</a>"
    else:
        tg_link = "—"

    summary = _build_lead_summary_for_admin(cat, progress)
    body = texts.ADMIN_LEAD_DM.format(
        id=lead_id,
        summary=summary,
        price=price_str,
        name=full_name,
        phone=phone,
        tg_link=tg_link,
    )
    kb = lead_admin_dm_kb(user_tg_id, username)
    with suppress(Exception):
        await bot.send_message(
            chat_id=settings.ADMIN_CHAT_ID,
            text=body,
            reply_markup=kb,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )


# Public alias for tests.
build_admin_lead_dm = _notify_admin
build_lead_summary_for_admin = _build_lead_summary_for_admin


__all__ = [
    "build_admin_lead_dm",
    "build_lead_summary_for_admin",
    "build_quiz_router",
]

# Silence unused-import warning from `json` (kept for future schema-evolutions).
_ = json
