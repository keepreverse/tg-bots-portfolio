"""Render prices in rubles with a thin space between thousands."""

from __future__ import annotations


def format_price(price_rub: int, *, currency: str = "₽", unit_suffix: str = "") -> str:
    """Format an integer ruble amount with thin spaces and a currency suffix.

    Examples:
        format_price(0)              -> "0 ₽"
        format_price(2000)           -> "2 000 ₽"
        format_price(25000)          -> "25 000 ₽"
        format_price(15000, unit_suffix=" / мес") -> "15 000 ₽ / мес"
    """
    s = f"{int(price_rub):,}".replace(",", " ")
    return f"{s} {currency}{unit_suffix}"


def format_range(
    min_price: int, max_price: int, *, currency: str = "₽", unit_suffix: str = "",
) -> str:
    """Format a price range — single number when both ends collapse."""
    if min_price == max_price:
        return format_price(min_price, currency=currency, unit_suffix=unit_suffix)
    return (
        f"{format_price(min_price, currency=currency, unit_suffix='')}"
        f" — {format_price(max_price, currency=currency, unit_suffix=unit_suffix)}"
    )
