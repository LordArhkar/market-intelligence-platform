"""
Application settings and configuration.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database configuration."""
    
    url: str = Field(
        default="postgresql+asyncpg://localhost:5432/mip",
        description="Database connection URL"
    )
    pool_size: int = Field(default=10, description="Connection pool size")
    max_overflow: int = Field(default=20, description="Max overflow connections")
    echo: bool = Field(default=False, description="Echo SQL queries")


class RedisSettings(BaseSettings):
    """Redis configuration."""
    
    host: str = Field(default="localhost")
    port: int = Field(default=6379)
    db: int = Field(default=0)
    password: Optional[str] = Field(default=None)
    
    @property
    def url(self) -> str:
        """Generate Redis URL."""
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


class MarketDataSettings(BaseSettings):
    """Market data provider configuration."""
    
    # Yahoo Finance (free, US equities, crypto, forex)
    yfinance_enabled: bool = Field(default=True)
    
    # CCXT (crypto exchanges)
    ccxt_enabled: bool = Field(default=True)
    ccxt_default_exchange: str = Field(default="binance")
    
    # Alpaca (US equities with API)
    alpaca_enabled: bool = Field(default=False)
    alpaca_key: Optional[str] = Field(default=None)
    alpaca_secret: Optional[str] = Field(default=None)
    alpaca_paper: bool = Field(default=True)
    
    # Polygon (US equities, options)
    polygon_enabled: bool = Field(default=False)
    polygon_api_key: Optional[str] = Field(default=None)
    
    # Data caching
    cache_ttl_seconds: int = Field(default=60)
    price_history_days: int = Field(default=365)


class RiskSettings(BaseSettings):
    """Risk management configuration."""
    
    # Position limits
    max_position_risk_percent: float = Field(
        default=2.0,
        description="Max risk per position as % of portfolio"
    )
    max_portfolio_risk_percent: float = Field(
        default=6.0,
        description="Max total portfolio risk as % of equity"
    )
    max_daily_loss_percent: float = Field(
        default=3.0,
        description="Daily loss limit as % of equity"
    )
    max_weekly_loss_percent: float = Field(
        default=6.0,
        description="Weekly loss limit as % of equity"
    )
    max_drawdown_percent: float = Field(
        default=15.0,
        description="Maximum drawdown limit"
    )
    
    # Exposure limits
    max_leverage: float = Field(default=1.0, description="Maximum leverage")
    max_sector_exposure_percent: float = Field(
        default=30.0,
        description="Max exposure to single sector"
    )
    max_asset_class_exposure_percent: float = Field(
        default=60.0,
        description="Max exposure to single asset class"
    )
    
    # Correlation limits
    max_correlated_exposure: float = Field(
        default=0.7,
        description="Max correlation between positions"
    )
    
    # Prohibited actions
    allow_martingale: bool = Field(default=False)
    allow_averaging_down: bool = Field(default=False)


class ExecutionSettings(BaseSettings):
    """Execution configuration."""
    
    mode: str = Field(default="SIMULATOR", description="SIMULATOR, PAPER, LIVE")
    
    # Simulator settings
    initial_capital: float = Field(default=100_000.0)
    currency: str = Field(default="USD")
    
    # UpsideOnly integration
    upsideonly_enabled: bool = Field(default=False)
    upsideonly_api_key: Optional[str] = Field(default=None)
    upsideonly_csv_path: Optional[Path] = Field(default=None)
    
    # Slippage modeling
    default_slippage_bps: float = Field(
        default=10.0,
        description="Default slippage in basis points"
    )
    
    # Commission modeling
    equity_commission_per_share: float = Field(default=0.0)
    equity_commission_percent: float = Field(default=0.0)
    crypto_commission_percent: float = Field(default=0.1)
    forex_commission_per_lot: float = Field(default=0.0)


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    All secrets should be loaded from environment variables or a secrets manager.
    NEVER embed credentials in configuration files or code.
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
    )
    
    # Application
    app_name: str = Field(default="Market Intelligence Platform")
    app_version: str = Field(default="0.1.0")
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")
    
    # Environment
    environment: str = Field(default="development")
    operating_mode: str = Field(default="VALIDATION")  # VALIDATION or TOURNAMENT
    
    # Paths
    data_dir: Path = Field(default=Path("./data"))
    cache_dir: Path = Field(default=Path("./data/cache"))
    output_dir: Path = Field(default=Path("./output"))
    logs_dir: Path = Field(default=Path("./logs"))
    
    # Subsystems
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    market_data: MarketDataSettings = Field(default_factory=MarketDataSettings)
    risk: RiskSettings = Field(default_factory=RiskSettings)
    execution: ExecutionSettings = Field(default_factory=ExecutionSettings)
    
    def ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        for dir_path in [self.data_dir, self.cache_dir, self.output_dir, self.logs_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
    
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment.lower() == "production"
    
    def is_tournament_mode(self) -> bool:
        """Check if running in tournament mode."""
        return self.operating_mode.upper() == "TOURNAMENT"


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Uses lru_cache to ensure settings are only loaded once.
    """
    settings = Settings()
    settings.ensure_directories()
    return settings
