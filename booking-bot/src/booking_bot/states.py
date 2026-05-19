"""FSM states for the booking flow."""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class BookingFlow(StatesGroup):
    pick_category = State()
    pick_service = State()
    pick_date = State()
    pick_time = State()
    ask_name = State()
    ask_phone = State()
    confirm = State()
