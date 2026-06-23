from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class HorizonMode(str, Enum):
    INTRADAY = "intraday"
    SWING = "swing"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Environment
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://quanta:quanta@localhost:5432/quanta"
    database_url_sync: str = "postgresql://quanta:quanta@localhost:5432/quanta"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    secret_key: str = "change-me-to-a-random-secret"
    session_expire_minutes: int = 1440
    # Bootstrap owner account — seeded once on first startup if set and no user exists
    owner_email: str = ""
    owner_password: str = ""

    # LLM (never in execution path)
    ollama_base_url: str = "http://localhost:11434"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    aws_bedrock_region: str = ""

    # Market data (leave blank to use the synthetic SampleDataProvider)
    polygon_api_key: str = ""
    polygon_base_url: str = "https://api.polygon.io"
    databento_api_key: str = ""

    # Scan configuration
    scan_universe_cap: int = 500
    polygon_calls_per_minute: int = 5
    scan_bar_lookback_days: int = 100
    scan_liquidity_window: int = 20

    # Broker (execution scope only)
    ibkr_host: str = "127.0.0.1"
    ibkr_port: int = 4002
    ibkr_client_id: int = 1

    # Trading
    horizon_mode: HorizonMode = HorizonMode.SWING

    # Notifications
    ses_region: str = ""
    ses_from_email: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Paths
    config_dir: Path = Field(default_factory=lambda: Path("config"))

    @property
    def is_production(self) -> bool:
        return self.environment == Environment.PRODUCTION


settings = Settings()
