"""Tests for the `format_duration` helper from booking_bot.duration."""

from __future__ import annotations

import pytest

from booking_bot.duration import format_duration


@pytest.mark.parametrize(
    ("minutes", "expected"),
    [
        (0, "0 мин"),
        (-15, "0 мин"),
        (15, "15 мин"),
        (30, "30 мин"),
        (45, "45 мин"),
        (60, "1 ч"),
        (90, "1 ч 30 мин"),
        (120, "2 ч"),
        (150, "2 ч 30 мин"),
        (180, "3 ч"),
        (240, "4 ч"),
        (300, "5 ч"),
        (450, "7 ч 30 мин"),
    ],
)
def test_format_duration(minutes: int, expected: str) -> None:
    assert format_duration(minutes) == expected
