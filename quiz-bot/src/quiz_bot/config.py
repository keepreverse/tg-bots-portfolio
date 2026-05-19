"""Runtime configuration loaded from environment / .env (via pydantic-settings)."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    BOT_TOKEN: str = Field(min_length=20)
    ADMIN_CHAT_ID: int

    BUSINESS_NAME: str = "Quiz Calculator"
    MASTER_HANDLE: str = "keepmaster"

    QUIZ_PATH: str = "data/seed_quiz.json"
    DB_PATH: str = "data/quiz.db"

    model_config = SettingsConfigDict(
        env_file=str(_project_root() / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @field_validator("BOT_TOKEN")
    @classmethod
    def _bot_token_shape(cls, v: str) -> str:
        if ":" not in v:
            raise ValueError("BOT_TOKEN must contain ':' (digits:secret).")
        return v

    @property
    def master_handle_username(self) -> str:
        """Telegram username without leading '@', suitable for `https://t.me/<username>`."""
        return self.MASTER_HANDLE.lstrip("@")

    @property
    def master_telegram_url(self) -> str:
        return f"https://t.me/{self.master_handle_username}"

    def _abs(self, raw: str) -> Path:
        p = Path(raw)
        if not p.is_absolute():
            p = _project_root() / p
        return p

    @property
    def db_path_abs(self) -> Path:
        return self._abs(self.DB_PATH)

    @property
    def quiz_path_abs(self) -> Path:
        return self._abs(self.QUIZ_PATH)


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()  # type: ignore[call-arg]
    return _settings
