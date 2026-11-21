from typing import Optional, Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./decidr.db"

    LLM_PROVIDER: str = "gemini"
    LLM_MODE: str = "cache"
    LLM_MODEL: str = "gemini-1.5-pro"
    ANTHROPIC_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None

    GITHUB_TOKEN: Optional[str] = None
    GITHUB_REPO: Optional[str] = None
    TRACKER: Literal["mock", "github"] = "mock"

    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: str = "decidr@example.com"

    DEMO_MODE: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
