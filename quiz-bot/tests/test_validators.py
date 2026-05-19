"""URL guard + phone normalisation tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from quiz_bot.validators import (
    message_contains_link,
    normalise_phone,
)

# ---------------------------------------------------------------------------
# Regex-based URL guard
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text", [
    "http://example.com",
    "HTTPS://EXAMPLE.COM/path",
    "посмотри https://evil.example.com",
    "tg://resolve?domain=foo",
    "пишите в t.me/foo_bar",
    "telegram.me/foo",
    "напиши @longusername",
    "www.example.com",
    "see [link](http://x)",
    "вот моя ссылка [тык](https://example.org)",
])
def test_text_contains_link_true(text: str) -> None:
    assert message_contains_link(text) is True


@pytest.mark.parametrize("text", [
    "Иван",
    "Анна-Мария",
    "Алексей Петров",
    "Маша 123",
    "Артур.Янов",
    "обычное имя без ссылок",
    "электронная почта (в названии тура)",
    "цена 100 ₽",
    "",
])
def test_text_contains_link_false(text: str) -> None:
    assert message_contains_link(text) is False


def test_entities_detected_as_link() -> None:
    ent = SimpleNamespace(type="url")
    assert message_contains_link("safe text", [ent]) is True


def test_entities_text_mention_detected() -> None:
    ent = SimpleNamespace(type=SimpleNamespace(value="text_mention"))
    assert message_contains_link("safe text", [ent]) is True


def test_entities_unknown_type_ignored() -> None:
    ent = SimpleNamespace(type="bold")
    assert message_contains_link("safe text", [ent]) is False


def test_entities_none_ok() -> None:
    assert message_contains_link("safe", None) is False


def test_none_text_safe() -> None:
    assert message_contains_link(None) is False


# ---------------------------------------------------------------------------
# Phone normalisation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("raw,expected", [
    ("+79991234567", "+79991234567"),
    ("89991234567", "89991234567"),
    ("8 999 123 45 67", "89991234567"),
    ("+7 (999) 123-45-67", "+79991234567"),
    ("  +7-999-123-45-67 ", "+79991234567"),
])
def test_phone_valid(raw: str, expected: str) -> None:
    assert normalise_phone(raw) == expected


@pytest.mark.parametrize("raw", [
    "",
    "abc",
    "+79",
    "1234567",
    "12345678901234567890",
    "+1234567890123456",  # 16 digits — out of [10, 15] range
])
def test_phone_invalid(raw: str) -> None:
    assert normalise_phone(raw) is None
