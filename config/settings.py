"""
Application configuration module using Pydantic Settings.
Loads configuration from environment variables and .env file.
"""

from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Application
    app_name: str = Field(default="CLICK", description="Application name")
    app_version: str = Field(default="1.0.0", description="Application version")
    environment: str = Field(default="development", description="Environment (development/production)")
    debug: bool = Field(default=True, description="Debug mode")

    # API
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8000, description="API port")
    api_prefix: str = Field(default="/api/v1", description="API prefix")

    # Telegram Bot
    bot_token: str = Field(..., description="Telegram bot token")
    admin_ids: str = Field(default="", description="Comma-separated admin IDs")
    moderation_chat_id: Optional[int] = Field(default=None, description="Telegram group ID for moderation")

    # MongoDB
    mongodb_url: str = Field(default="mongodb://localhost:27017", description="MongoDB connection URL")
    mongodb_db_name: str = Field(default="click_db", description="MongoDB database name")
    mongodb_min_pool_size: int = Field(default=10, description="MongoDB min pool size")
    mongodb_max_pool_size: int = Field(default=100, description="MongoDB max pool size")

    # Redis
    redis_host: str = Field(default="localhost", description="Redis host")
    redis_port: int = Field(default=6379, description="Redis port")
    redis_db: int = Field(default=0, description="Redis database number")
    redis_password: Optional[str] = Field(default=None, description="Redis password")
    redis_fsm_ttl_hours: int = Field(default=48, description="FSM state TTL in hours (default 48h)")

    # Celery
    celery_broker_url: str = Field(default="redis://localhost:6379/1", description="Celery broker URL")
    celery_result_backend: str = Field(default="redis://localhost:6379/2", description="Celery result backend")

    # Security
    secret_key: str = Field(..., description="Secret key for JWT")
    algorithm: str = Field(default="HS256", description="JWT algorithm")
    access_token_expire_minutes: int = Field(default=30, description="Access token expiration time")

    # Telegram Channels for Vacancies
    channel_vacancies_barmen: str = Field(default="@horeca_msk1", description="Channel for barmen vacancies")
    channel_vacancies_waiters: str = Field(default="@horeca_msk2", description="Channel for waiter vacancies")
    channel_vacancies_cooks: str = Field(default="@horeca_povara1", description="Channel for cook vacancies")
    channel_vacancies_barista: str = Field(default="@horeca_barista", description="Channel for barista vacancies")
    channel_vacancies_admin: str = Field(default="@horeca_admin_man", description="Channel for management vacancies")
    channel_vacancies_support: str = Field(default="@horeca5", description="Channel for support staff vacancies")
    channel_vacancies_other: str = Field(default="@horeca4", description="Channel for other vacancies")
    channel_vacancies_general: str = Field(default="@HoReCaMBA", description="General vacancies channel")

    # Telegram Channels for Resumes
    channel_resumes_barmen: str = Field(default="@horeca_msk1", description="Channel for barmen resumes")
    channel_resumes_waiters: str = Field(default="@horeca_msk2", description="Channel for waiter resumes")
    channel_resumes_cooks: str = Field(default="@horeca_povara1", description="Channel for cook resumes")
    channel_resumes_barista: str = Field(default="@horeca_barista", description="Channel for barista resumes")
    channel_resumes_admin: str = Field(default="@horeca_admin_man", description="Channel for management resumes")
    channel_resumes_support: str = Field(default="@horeca5", description="Channel for support staff resumes")
    channel_resumes_other: str = Field(default="@horeca4", description="Channel for other resumes")
    channel_resumes_general: str = Field(default="@HoReCaMBA", description="General resumes channel")

    # Google Sheets
    google_credentials_file: Optional[str] = Field(default="credentials.json")
    google_sheet_id_kolosova: str = Field(default="15Tw2zNqitwIdgtWy3ClirI2HW6_9a9aEteots-Nzng0")
    google_sheet_id_belousov: Optional[str] = Field(default=None)

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_file: str = Field(default="logs/app.log", description="Log file path")

    @field_validator("admin_ids")
    @classmethod
    def parse_admin_ids(cls, v: str) -> List[int]:
        """Parse comma-separated admin IDs into list of integers."""
        if not v:
            return []
        try:
            return [int(id_.strip()) for id_ in v.split(",") if id_.strip()]
        except ValueError:
            raise ValueError("admin_ids must be comma-separated integers")

    @property
    def redis_url(self) -> str:
        """Construct Redis URL from components."""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment.lower() == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.environment.lower() == "development"

    # Backend host for API connection
    backend_host: str = Field(default="backend", description="Backend service hostname")

    @property
    def api_url(self) -> str:
        """Construct API URL from components."""
        # Use backend_host from env var (defaults to 'backend' for Docker Compose)
        # For local dev outside Docker, set BACKEND_HOST=localhost in .env
        return f"http://{self.backend_host}:{self.api_port}{self.api_prefix}"


# Global settings instance
settings = Settings()
