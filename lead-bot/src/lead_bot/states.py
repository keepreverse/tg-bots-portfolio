from aiogram.fsm.state import State, StatesGroup


class Survey(StatesGroup):
    """States of the lead-collection FSM."""

    name = State()
    phone = State()
    service = State()
    comment = State()
    confirm = State()


# Steps shown to the user in the progress bar.
# Order matches the visual flow.
SURVEY_STEPS = ("name", "phone", "service", "comment", "confirm")


def step_index(state_name: str | None) -> int:
    """Return the 1-based index of a Survey state, or 0 if not a survey state."""
    if state_name is None:
        return 0
    short = state_name.split(":", 1)[-1]
    try:
        return SURVEY_STEPS.index(short) + 1
    except ValueError:
        return 0
