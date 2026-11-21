from typing import Optional, Literal, Union, List
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


DEV_JWT_SECRET = "development-only-secret-do-not-use-in-production"


class Settings(BaseSettings):
    ENVIRONMENT: Literal["development", "production", "test"] = "development"

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

    # Authentication and security
    JWT_SECRET_KEY: str = DEV_JWT_SECRET
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    REMEMBER_ME_EXPIRE_DAYS: int = 30
    VERIFICATION_TOKEN_EXPIRE_HOURS: int = 24
    PASSWORD_RESET_TOKEN_EXPIRE_HOURS: int = 2
    MAX_VERIFICATION_ATTEMPTS: int = 5
    MAX_RESET_ATTEMPTS: int = 5

    # Google OAuth
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None

    # Authorization
    AUTH_ENFORCED: bool = True

    # CORS
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "https://decidr-pi.vercel.app",
        "https://decidr.vercel.app",
    ]

    # Frontend URL (optional reference on backend)
    NEXT_PUBLIC_API_URL: Optional[str] = None

    # Supabase Storage (optional persistent object storage)
    SUPABASE_URL: Optional[str] = None
    SUPABASE_KEY: Optional[str] = None
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None
    SUPABASE_STORAGE_BUCKET: str = "decidr-transcripts"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Union[List[str], str]) -> List[str]:
        if isinstance(v, str):
            # Parse comma-separated origins from environment variables
            cleaned = [item.strip() for item in v.split(",") if item.strip()]
            return cleaned if cleaned else ["*"]
        return v

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_db_url(cls, v: str) -> str:
        if not isinstance(v, str):
            return v
        cleaned = v.strip()
        # Normalizes postgres:// and postgresql:// to use psycopg2 binary driver
        if cleaned.startswith("postgres://"):
            return "postgresql+psycopg2://" + cleaned[len("postgres://"):]
        if cleaned.startswith("postgresql://") and not cleaned.startswith("postgresql+"):
            return "postgresql+psycopg2://" + cleaned[len("postgresql://"):]
        return cleaned

    @model_validator(mode="after")
    def validate_production_security(self):
        if self.ENVIRONMENT == "production":
            if self.JWT_SECRET_KEY == DEV_JWT_SECRET:
                raise ValueError(
                    "A secure production JWT_SECRET_KEY must be configured (cannot use DEV_JWT_SECRET)."
                )

            if len(self.JWT_SECRET_KEY) < 32:
                raise ValueError(
                    "Production JWT_SECRET_KEY must contain at least 32 characters."
                )

            if self.DEMO_MODE:
                raise ValueError(
                    "DEMO_MODE must be set to false in production."
                )

            if self.DATABASE_URL.startswith("sqlite"):
                raise ValueError(
                    "Production requires a PostgreSQL database URL (e.g. Supabase), not SQLite."
                )

        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
