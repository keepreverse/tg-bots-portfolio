"""Render service durations in minutes as human-readable Russian text."""

from __future__ import annotations


def format_duration(minutes: int) -> str:
    """Format a duration in minutes.

    Examples:
        30  -> "30 мин"
        60  -> "1 ч"
        90  -> "1 ч 30 мин"
        120 -> "2 ч"
        180 -> "3 ч"
        240 -> "4 ч"
    """
    if minutes <= 0:
        return "0 мин"
    if minutes < 60:
        return f"{minutes} мин"
    hours, rest = divmod(minutes, 60)
    if rest == 0:
        return f"{hours} ч"
    return f"{hours} ч {rest} мин"
