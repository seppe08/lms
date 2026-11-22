from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PROJECT_NAME: str = "LMS API"
    ENVIRONMENT: Literal["local", "development", "testing", "production"] = (
        "development"
    )
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: str
    SECRET_KEY: str = Field(min_length=16)
    JWT_SECRET_KEY: str = Field(min_length=16)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=15, ge=1, le=1440)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, ge=1, le=90)

    CORS_ORIGINS: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    RATE_LIMIT_ENABLED: bool = True
    AUTH_RATE_LIMIT_REQUESTS: int = Field(default=10, ge=1)
    AUTH_RATE_LIMIT_WINDOW_SECONDS: int = Field(default=60, ge=1)

    SENTRY_DSN: str | None = None
    # Fraction of traces sent to Sentry (0.0 disables new traces, 1.0 captures all).
    SENTRY_TRACES_SAMPLE_RATE: float = Field(default=0.1, ge=0.0, le=1.0)
    SENTRY_CAPTURE_LOGS: bool = True

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        if self.ENVIRONMENT == "production":
            if self.DEBUG:
                raise ValueError("DEBUG must be False in production")
            if len(self.SECRET_KEY) < 32 or len(self.JWT_SECRET_KEY) < 32:
                raise ValueError(
                    "SECRET_KEY and JWT_SECRET_KEY must be >= 32 chars in production"
                )
            if "*" in self.CORS_ORIGINS:
                raise ValueError("Wildcard CORS_ORIGINS is not allowed in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
