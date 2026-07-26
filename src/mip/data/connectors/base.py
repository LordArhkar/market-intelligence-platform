"""
Base data connector interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

import polars as pl


@dataclass
class MarketDataRequest:
    """Request parameters for market data retrieval."""
    
    symbol: str
    start_date: datetime
    end_date: datetime
    timeframe: str = "1d"
    
    # Optional parameters
    adjustment: str = "all"  # "all", "splits", "none"
    include_extended_hours: bool = False
    
    def validate(self) -> None:
        """Validate request parameters."""
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be before end_date")
        if self.end_date > datetime.utcnow() + timedelta(hours=1):
            raise ValueError("end_date cannot be in the future")


@dataclass
class DataSourceInfo:
    """Information about a data source."""
    
    name: str
    provider: str
    asset_classes: list[str]
    has_realtime: bool
    has_delayed: bool
    has_historical: bool
    delay_minutes: int = 0
    rate_limit_per_minute: int = 0
    requires_auth: bool = False
    notes: str = ""


class DataConnector(ABC):
    """
    Abstract base class for market data connectors.
    
    All connectors must implement this interface for consistent data access.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Connector name."""
        pass
    
    @property
    @abstractmethod
    def info(self) -> DataSourceInfo:
        """Information about this data source."""
        pass
    
    @abstractmethod
    async def connect(self) -> None:
        """Initialize connection to data source."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to data source."""
        pass
    
    @abstractmethod
    async def get_price_bars(
        self,
        request: MarketDataRequest
    ) -> pl.DataFrame:
        """
        Retrieve price bars (OHLCV) for a symbol.
        
        Returns DataFrame with columns:
        - timestamp: datetime
        - open: float
        - high: float
        - low: float
        - close: float
        - volume: float
        """
        pass
    
    async def get_latest_price(self, symbol: str) -> Optional[float]:
        """Get the most recent price for a symbol."""
        request = MarketDataRequest(
            symbol=symbol,
            start_date=datetime.utcnow() - timedelta(days=5),
            end_date=datetime.utcnow(),
            timeframe="1d",
        )
        df = await self.get_price_bars(request)
        if df is None or df.is_empty():
            return None
        return df.sort("timestamp", descending=True).select("close").to_series()[0]
    
    @abstractmethod
    async def get_multiple_prices(
        self,
        symbols: list[str]
    ) -> dict[str, float]:
        """Get current prices for multiple symbols."""
        pass
    
    @abstractmethod
    async def search_symbols(
        self,
        query: str,
        asset_class: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """Search for symbols matching a query."""
        pass
    
    async def health_check(self) -> dict[str, Any]:
        """Check connector health status."""
        return {
            "connector": self.name,
            "status": "unknown",
            "latency_ms": None,
            "last_check": datetime.utcnow().isoformat(),
        }
    
    async def get_data_quality_report(
        self,
        request: MarketDataRequest
    ) -> dict[str, Any]:
        """
        Generate data quality report for a request.
        
        Checks for:
        - Missing bars
        - Duplicate bars
        - Outlier prices
        - Stale data
        """
        df = await self.get_price_bars(request)
        
        if df is None or df.is_empty():
            return {
                "status": "no_data",
                "symbol": request.symbol,
                "expected_bars": 0,
                "actual_bars": 0,
            }
        
        expected_bars = self._calculate_expected_bars(
            request.start_date,
            request.end_date,
            request.timeframe
        )
        
        actual_bars = len(df)
        missing_bars = expected_bars - actual_bars
        
        # Check for duplicates
        timestamps = df.select("timestamp").to_series()
        duplicates = len(timestamps) - timestamps.n_unique()
        
        # Check for price outliers (more than 50% from median)
        closes = df.select("close").to_series()
        median_price = closes.median()
        outlier_count = 0
        if median_price > 0:
            outlier_count = ((closes - median_price).abs() / median_price > 0.5).sum()
        
        return {
            "status": "ok" if missing_bars <= 0 and duplicates == 0 else "issues_found",
            "symbol": request.symbol,
            "timeframe": request.timeframe,
            "expected_bars": expected_bars,
            "actual_bars": actual_bars,
            "missing_bars": max(0, missing_bars),
            "duplicate_bars": duplicates,
            "outlier_count": outlier_count,
            "date_range": {
                "start": str(df["timestamp"].min()),
                "end": str(df["timestamp"].max()),
            },
        }
    
    @staticmethod
    def _calculate_expected_bars(
        start: datetime,
        end: datetime,
        timeframe: str
    ) -> int:
        """Calculate expected number of bars for a time period."""
        delta = end - start
        
        if timeframe == "1m":
            return int(delta.total_seconds() / 60)
        elif timeframe == "5m":
            return int(delta.total_seconds() / 300)
        elif timeframe == "15m":
            return int(delta.total_seconds() / 900)
        elif timeframe == "30m":
            return int(delta.total_seconds() / 1800)
        elif timeframe == "1h":
            return int(delta.total_seconds() / 3600)
        elif timeframe == "4h":
            return int(delta.total_seconds() / 14400)
        elif timeframe == "1d":
            return delta.days + 1
        elif timeframe == "1w":
            return int(delta.days / 7) + 1
        else:
            return delta.days + 1
