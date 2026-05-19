"""Render prices in rubles with a thin space between thousands."""

from __future__ import annotations


def format_price(price_rub: int) -> str:
    """Format an integer ruble amount with thin spaces and a ₽ suffix.

    Examples:
        0      -> "бесплатно"
        2000   -> "2 000 ₽"
        25000  -> "25 000 ₽"
    """
    if price_rub <= 0:
        return "бесплатно"
    s = f"{price_rub:,}".replace(",", " ")
    return f"{s} ₽"
