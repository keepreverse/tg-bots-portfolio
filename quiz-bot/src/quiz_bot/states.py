"""FSM states for the quiz flow."""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class QuizFlow(StatesGroup):
    """The quiz-bot FSM.

    States are intentionally coarse-grained — within `answering` the bot
    keeps the per-question step number / category key in `state.data` rather
    than enumerating one state per question (would explode for big quizzes).
    """

    pick_category = State()   # showing the category picker
    answering = State()       # cycling through quiz questions
    show_result = State()     # showing the calculated price range + CTA
    ask_name = State()        # collecting the lead's name
    ask_phone = State()       # collecting the lead's phone
