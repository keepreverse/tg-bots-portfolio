"""Tests for the URL/link guard validator."""

from __future__ import annotations

import pytest

from booking_bot.validators import (
    entities_contain_link,
    message_contains_link,
    text_contains_link,
)


class _Ent:
    """Mimics aiogram's `MessageEntity` (just the `.type` attribute)."""

    def __init__(self, t: str) -> None:
        self.type = t


@pytest.mark.parametrize(
    "raw",
    [
        "https://example.com",
        "HTTPS://example.com",
        "http://t.me/foo",
        "t.me/foo",
        "telegram.me/keepmaster",
        "Заходите на www.example.com",
        "tg://resolve?domain=foo",
        "ping @somebody про дизайн",
        "[click here](https://example.com)",
    ],
)
def test_text_contains_link_positive(raw: str) -> None:
    assert text_contains_link(raw)


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "Алексей",
        "Анна-Мария",
        "Просто текст без ссылок",
        "Telegram@home — мне нравится",   # not a TG @handle, has @ but no username after
        "Цена 5 000 ₽",
    ],
)
def test_text_contains_link_negative(raw: str) -> None:
    assert not text_contains_link(raw)


def test_entities_url() -> None:
    assert entities_contain_link([_Ent("url")])
    assert entities_contain_link([_Ent("text_link")])
    assert entities_contain_link([_Ent("mention")])
    assert entities_contain_link([_Ent("text_mention")])


def test_entities_no_links() -> None:
    assert not entities_contain_link(None)
    assert not entities_contain_link([])
    assert not entities_contain_link([_Ent("bold"), _Ent("italic")])


def test_combined_detection_text_only() -> None:
    assert message_contains_link("https://x.test", None)


def test_combined_detection_entities_only() -> None:
    assert message_contains_link("Алексей", [_Ent("text_link")])


def test_combined_clean() -> None:
    assert not message_contains_link("Алексей", [_Ent("bold")])
