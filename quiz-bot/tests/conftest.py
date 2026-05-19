"""Shared fixtures."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Make pydantic-settings happy in tests — supply dummy BOT_TOKEN & ADMIN_CHAT_ID.
os.environ.setdefault("BOT_TOKEN", "123456789:dummy-token-for-tests-AAAAAAAAAAAA")
os.environ.setdefault("ADMIN_CHAT_ID", "1")
os.environ.setdefault("BUSINESS_NAME", "Quiz Calculator")
os.environ.setdefault("MASTER_HANDLE", "keepmaster")
os.environ.setdefault("QUIZ_PATH", "data/seed_quiz.json")

# Make `src/` importable without `pip install -e` for ad-hoc runs.
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture
def seed_quiz_path() -> Path:
    return ROOT / "data" / "seed_quiz.json"
