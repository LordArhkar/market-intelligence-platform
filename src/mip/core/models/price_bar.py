"""
Price bar model - OHLCV data representation.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class TimeFrame(str, Enum):
    """Supported timeframes for price bars."""
    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    HOUR_1 = "1h"
    HOUR_4 = "4h"
    DAY_1 = "1d"
    DAY_1W = "1w"
    MONTH_1 = "1M"
    
    @property
    def minutes(self) -> int:
        """Convert timeframe to minutes."""
        mapping = {
            "1m": 1,
            "5m": 5,
            "15m": 15,
            "30m": 30,
            "1h": 60,
            "4h": 240,
            "1d": 1440,
            "1w": 10080,
            "1M": 43200,
        }
        return mapping[self.value]


class PriceBar(BaseModel):
    """
    Represents a single OHLCV price bar.
    
    Immutable once created - represents a point-in-time snapshot.
    """
    id: Optional[int] = Field(default=None, description="Database ID")
    
    # Identification
    symbol: str = Field(..., description="Instrument symbol")
    timeframe: TimeFrame = Field(..., description="Bar timeframe")
    timestamp: datetime = Field(..., description="Bar open time (UTC)")
    
    # OHLC
    open: float = Field(..., description="Opening price")
    high: float = Field(..., description="Highest price")
    low: float = Field(..., description="Lowest price")
    close: float = Field(..., description="Closing price")
    
    # Volume
    volume: float = Field(default=0.0, description="Trading volume")
    quote_volume: float = Field(default=0.0, description="Volume in quote currency")
    
    # Tick data (if available)
    tick_count: int = Field(default=0, description="Number of ticks in bar")
    trade_count: int = Field(default=0, description="Number of trades in bar")
    
    # VWAP
    vwap: Optional[float] = Field(default=None, description="Volume-weighted average price")
    
    # Adjustment
    adjustment_factor: float = Field(default=1.0, description="Split/dividend adjustment")
    
    # Source tracking
    source: str = Field(default="unknown", description="Data source identifier")
    received_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = ConfigDict(from_attributes=True)
    
    @property
    def is_bullish(self) -> bool:
        """Bar closed higher than it opened."""
        return self.close > self.open
    
    @property
    def is_bearish(self) -> bool:
        """Bar closed lower than it opened."""
        return self.close < self.open
    
    @property
    def is_doji(self) -> bool:
        """Minimal body - open and close are very close."""
        body = abs(self.close - self.open)
        range_ = self.high - self.low
        return body < (range_ * 0.1) if range_ > 0 else False
    
    @property
    def body_size(self) -> float:
        """Absolute difference between open and close."""
        return abs(self.close - self.open)
    
    @property
    def range(self) -> float:
        """Full range of the bar."""
        return self.high - self.low
    
    @property
    def upper_shadow(self) -> float:
        """Distance from close to high (or open to high if bearish)."""
        if self.close >= self.open:
            return self.high - self.close
        return self.high - self.open
    
    @property
    def lower_shadow(self) -> float:
        """Distance from open to low (or close to low if bearish)."""
        if self.close >= self.open:
            return self.open - self.low
        return self.close - self.low
    
    @property
    def change_percent(self) -> float:
        """Percentage change from open to close."""
        if self.open == 0:
            return 0.0
        return ((self.close - self.open) / self.open) * 100
    
    @property
    def true_range(self) -> float:
        """True range for ATR calculations."""
        return max(
            self.high - self.low,
            abs(self.high - self.close),
            abs(self.low - self.close)
        )
