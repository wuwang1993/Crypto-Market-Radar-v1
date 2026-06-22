"""Pydantic configuration models.

Phase 1: skeleton — full field definitions will be filled in as each
config section is wired up in later phases.
"""

from __future__ import annotations

from pydantic import BaseModel


class ExchangeConfig(BaseModel):
    """Exchange configuration.  Filled in phase 2."""
    name: str = "binance"


class TelegramConfig(BaseModel):
    """Telegram settings.  Phase 1 already reads token/chat_id from
    file + env; this model will be used once we integrate the YAML
    config path."""
    bot_token: str = ""
    chat_id: str = ""


class SchedulerConfig(BaseModel):
    """Scheduler intervals.  Filled in phase 6."""
    summary_interval_min: int = 30
    heatmap_interval_min: int = 60
    daily_report_time: str = "09:00"


class StorageConfig(BaseModel):
    """Storage settings.  Filled in phase 5."""
    alert_retention_days: int = 90


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: str = "INFO"
    app_log: str = "logs/app.log"
    error_log: str = "logs/error.log"


class SystemConfig(BaseModel):
    """System-level tuning."""
    warmup_kline_count: int = 20
    warmup_timeout_sec: int = 60
    health_check_interval_sec: int = 30
    data_stale_threshold_sec: int = 10


class AppConfig(BaseModel):
    """Root configuration model."""
    exchange: ExchangeConfig = ExchangeConfig()
    telegram: TelegramConfig = TelegramConfig()
    scheduler: SchedulerConfig = SchedulerConfig()
    storage: StorageConfig = StorageConfig()
    logging: LoggingConfig = LoggingConfig()
    system: SystemConfig = SystemConfig()
