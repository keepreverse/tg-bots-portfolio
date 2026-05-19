"""Validators for user-supplied free-text fields (name / phone).

Telegram parses URLs, mentions and `text_link` entities in incoming messages.
We never want links inside the lead's name or free-text phone — links there
are almost always spam / phishing.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

_LINK_TOKEN_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"https?://", re.IGNORECASE),
    re.compile(r"\btg://", re.IGNORECASE),
    re.compile(r"\bwww\.", re.IGNORECASE),
    re.compile(r"\bt\s*\.\s*me\b", re.IGNORECASE),
    re.compile(r"\btelegram\s*\.\s*me\b", re.IGNORECASE),
    # Bare @username (≥3 chars). Not a link strictly but pulls clients into
    # a mention preview; reject anywhere inside a free-text field.
    re.compile(r"(?:^|\s)@[A-Za-z][A-Za-z0-9_]{2,}", re.IGNORECASE),
    # Markdown-style link `[text](url)`.
    re.compile(r"\]\s*\(\s*\w"),
)

_LINK_ENTITY_TYPES: frozenset[str] = frozenset(
    {"url", "text_link", "mention", "text_mention"}
)

_PHONE_RX = re.compile(r"^\+?\d{10,15}$")


def text_contains_link(text: str) -> bool:
    """Return True if `text` looks like it contains a URL / handle / TG link."""
    if not text:
        return False
    return any(p.search(text) for p in _LINK_TOKEN_PATTERNS)


def entities_contain_link(entities: Iterable[object] | None) -> bool:
    """Return True if any Telegram message entity describes a link/mention.

    Accepts a list of aiogram `MessageEntity` instances (anything with a `.type`
    attribute) so this stays import-free of aiogram for easy unit-testing.
    """
    if not entities:
        return False
    for ent in entities:
        ent_type = getattr(ent, "type", None)
        if ent_type is None:
            continue
        value = getattr(ent_type, "value", ent_type)
        if isinstance(value, str) and value in _LINK_ENTITY_TYPES:
            return True
    return False


def message_contains_link(text: str | None, entities: Iterable[object] | None = None) -> bool:
    """Combined check: entity-based + regex-based."""
    if entities_contain_link(entities):
        return True
    return text_contains_link(text or "")


def normalise_phone(raw: str) -> str | None:
    """Strip the input to digits (keeping leading '+'). Return None if shape is bad."""
    digits = re.sub(r"[^\d+]", "", raw or "")
    if _PHONE_RX.match(digits):
        return digits
    return None
