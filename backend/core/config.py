"""
Central configuration for Dhahabu Trading Platform.

All environment-driven settings live here. Services import from this module
rather than reading env vars directly. This enables clean testing and
single-source-of-truth config management.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────────
    app_name: str = "Dhahabu XAUUSD Trading Platform"
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production"] = "development"
    secret_key: str = "change-me-in-production-minimum-32-chars"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = False
    port: int = 8000  # Railway uses PORT env var
    cors_allowed_origins: list[str] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:5173",
            "https://dhahabu-rose.vercel.app",
            "https://dhahabu.vercel.app",
        ]
    )

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/dhahabu"
    database_sync_url: str = "postgresql://postgres:password@localhost:5432/dhahabu"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30

    # ── Market Data ───────────────────────────────────────────────────────────
    twelve_data_api_key: str = ""
    twelve_data_base_url: str = "https://api.twelvedata.com"
    market_data_symbol: str = "XAU/USD"
    market_data_timeframes: list[str] = Field(
        default=["1min", "15min", "1h", "4h", "1day"]
    )
    market_data_ingestion_interval_minutes: int = 15

    # ── Telegram ──────────────────────────────────────────────────────────────
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_enabled: bool = True

    # ── Trading / Account ────────────────────────────────────────────────────
    account_balance: float = 10000.0
    max_daily_loss_pct: float = 0.03
    max_simultaneous_trades: int = 5
    max_account_risk_pct: float = 0.10
    default_risk_per_trade_pct: float = 0.01
    risk_free_rate: float = 0.045

    # ── Scheduler ─────────────────────────────────────────────────────────────
    brain_interval_minutes: int = 30
    backtest_interval_hours: int = 4
    param_search_interval_hours: int = 6
    trade_reconcile_interval_minutes: int = 5
    health_check_interval_minutes: int = 10
    daily_reset_cron: str = "0 0 * * *"  # midnight UTC

    # ── Backtest / Walk-Forward ───────────────────────────────────────────────
    rolling_windows_days: list[int] = Field(default=[7, 14, 30, 60])
    walk_forward_train_ratio: float = 0.80
    walk_forward_test_ratio: float = 0.20

    # ── Overfit Detection ─────────────────────────────────────────────────────
    oos_profit_factor_threshold: float = 0.70
    oos_expectancy_threshold: float = 0.60
    oos_drawdown_expansion_threshold: float = 1.50
    oos_win_rate_collapse_threshold: float = 0.60

    # ── Monte Carlo ───────────────────────────────────────────────────────────
    monte_carlo_simulations: int = 1000
    monte_carlo_robustness_threshold: float = 0.55

    # ── Parameter Search ──────────────────────────────────────────────────────
    param_search_combinations: int = 80

    # ── Circuit Breaker ───────────────────────────────────────────────────────
    consecutive_stop_losses_limit: int = 8
    shutdown_duration_hours: int = 24
    auto_reset_after_shutdown: bool = True

    # ── Broker ────────────────────────────────────────────────────────────────
    broker_mode: str = "paper"           # "paper", "oanda", or "ctrader"

    # OANDA v20
    oanda_api_key: str = ""
    oanda_account_id: str = ""
    oanda_environment: str = "practice"  # "practice" or "live"

    # cTrader Open API (Pepperstone, IC Markets, etc.)
    ctrader_client_id: str = ""
    ctrader_client_secret: str = ""
    ctrader_account_id: str = ""        # numeric account ID as string
    ctrader_access_token: str = ""      # OAuth access token for the account
    ctrader_environment: str = "demo"   # "demo" or "live"

    @field_validator("market_data_timeframes", mode="before")
    @classmethod
    def parse_timeframes(cls, v: str | list) -> list[str]:
        if isinstance(v, str):
            return [t.strip() for t in v.split(",")]
        return v

    @field_validator("rolling_windows_days", mode="before")
    @classmethod
    def parse_windows(cls, v: str | list) -> list[int]:
        if isinstance(v, str):
            return [int(w.strip()) for w in v.split(",")]
        return v

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def parse_cors_allowed_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @property
    def effective_port(self) -> int:
        """Railway injects PORT; fall back to api_port for local dev."""
        return self.port or self.api_port


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
