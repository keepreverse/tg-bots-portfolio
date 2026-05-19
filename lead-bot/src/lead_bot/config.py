from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings, loaded from environment variables or a .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bot_token: str = Field(..., alias="BOT_TOKEN")
    admin_chat_id: int = Field(..., alias="ADMIN_CHAT_ID")
    db_path: Path = Field(default=Path("data/leads.db"), alias="DB_PATH")
    business_name: str = Field(default="Моя компания", alias="BUSINESS_NAME")
    services_raw: str = Field(
        default="Консультация;Заказ под ключ;Доработка проекта;Другое",
        alias="SERVICES",
    )

    @field_validator("bot_token")
    @classmethod
    def _validate_token(cls, value: str) -> str:
        if ":" not in value or len(value) < 20:
            raise ValueError(
                "BOT_TOKEN looks invalid. Get a real token from @BotFather: /newbot"
            )
        return value

    @property
    def services(self) -> list[str]:
        return [s.strip() for s in self.services_raw.split(";") if s.strip()]


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
