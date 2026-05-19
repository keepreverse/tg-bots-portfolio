"""Runtime configuration loaded from environment / .env (via pydantic-settings)."""

from __future__ import annotations

from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    BOT_TOKEN: str = Field(min_length=20)
    ADMIN_CHAT_ID: int

    BUSINESS_NAME: str = "Tattoo & Piercing"
    BUSINESS_ADDRESS: str = "ул. Тверская, 7"
    MASTER_HANDLE: str = "keepmaster"

    MASTER_TZ: str = "Europe/Moscow"
    SLOT_STEP_MINUTES: int = 60
    BOOKING_BUFFER_AFTER_MINUTES: int = 30
    BOOKING_HORIZON_DAYS: int = 30
    REMINDER_OFFSETS_HOURS_RAW: str = Field(default="24,2", validation_alias="REMINDER_OFFSETS_HOURS")

    DB_PATH: str = "data/booking.db"

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

    @field_validator("SLOT_STEP_MINUTES")
    @classmethod
    def _slot_step(cls, v: int) -> int:
        if v != 60:
            raise ValueError("SLOT_STEP_MINUTES must be 60 in this version.")
        return v

    @field_validator("BOOKING_BUFFER_AFTER_MINUTES")
    @classmethod
    def _buffer(cls, v: int) -> int:
        if v < 0 or v % 30 != 0:
            raise ValueError("BOOKING_BUFFER_AFTER_MINUTES must be >= 0 and a multiple of 30.")
        return v

    @field_validator("BOOKING_HORIZON_DAYS")
    @classmethod
    def _horizon(cls, v: int) -> int:
        if v < 1 or v > 365:
            raise ValueError("BOOKING_HORIZON_DAYS must be between 1 and 365.")
        return v

    @field_validator("REMINDER_OFFSETS_HOURS_RAW")
    @classmethod
    def _parse_offsets(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("REMINDER_OFFSETS_HOURS must contain at least one offset.")
        for chunk in v.split(","):
            chunk = chunk.strip()
            if not chunk:
                continue
            try:
                int(chunk)
            except ValueError as exc:
                raise ValueError(f"REMINDER_OFFSETS_HOURS: invalid value '{chunk}'.") from exc
        return v

    @field_validator("MASTER_TZ")
    @classmethod
    def _tz_resolves(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"MASTER_TZ '{v}' is not a known time zone.") from exc
        return v

    @property
    def master_tz(self) -> ZoneInfo:
        return ZoneInfo(self.MASTER_TZ)

    @property
    def master_handle_username(self) -> str:
        """Telegram username without leading '@', suitable for `https://t.me/<username>`."""
        return self.MASTER_HANDLE.lstrip("@")

    @property
    def master_telegram_url(self) -> str:
        return f"https://t.me/{self.master_handle_username}"

    @property
    def reminder_offsets_hours(self) -> list[int]:
        return [int(x.strip()) for x in self.REMINDER_OFFSETS_HOURS_RAW.split(",") if x.strip()]

    @property
    def db_path_abs(self) -> Path:
        p = Path(self.DB_PATH)
        if not p.is_absolute():
            p = _project_root() / p
        return p


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()  # type: ignore[call-arg]
    return _settings
