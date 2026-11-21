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
    RESEND_API_KEY: Optional[str] = None
    SLACK_WEBHOOK_URL: Optional[str] = None
    TIMEZONE: str = "UTC"

    DEMO_MODE: bool = True

    # Authentication & Security
    JWT_SECRET_KEY: str = "decidr-super-secure-jwt-secret-key-change-in-production-2026"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours standard
    REMEMBER_ME_EXPIRE_DAYS: int = 30  # 30 days for remember-me
    VERIFICATION_TOKEN_EXPIRE_HOURS: int = 24
    PASSWORD_RESET_TOKEN_EXPIRE_HOURS: int = 2
    MAX_VERIFICATION_ATTEMPTS: int = 5
    MAX_RESET_ATTEMPTS: int = 5

    # Google OAuth
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None

    # Multi-user & Project Authorization
    AUTH_ENFORCED: bool = True


    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
