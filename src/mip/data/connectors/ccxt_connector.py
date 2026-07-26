"""
CCXT connector for cryptocurrency data.

Provides access to multiple crypto exchanges through a unified interface.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Optional

import ccxt
import polars as pl

from mip.core.config import get_settings
from mip.data.connectors.base import (
    DataConnector,
    DataSourceInfo,
    MarketDataRequest,
)


class CCXTConnector(DataConnector):
    """
    CCXT connector for cryptocurrency exchange data.
    
    Supports 100+ exchanges including:
    - Binance
    - Coinbase
    - Kraken
    - Bybit
    - OKX
    
    Note: Rate limits and data availability vary by exchange.
    """
    
    SUPPORTED_EXCHANGES = [
        "binance",
        "coinbase",
        "kraken",
        "bybit",
        "okx",
        "kucoin",
        "huobi",
    ]
    
    def __init__(self, exchange: str = "binance"):
        if exchange not in self.SUPPORTED_EXCHANGES:
            raise ValueError(
                f"Exchange '{exchange}' not supported. "
                f"Supported: {self.SUPPORTED_EXCHANGES}"
            )
        
        self._settings = get_settings()
        self._exchange_name = exchange
        self._exchange: Optional[ccxt.Exchange] = None
        self._connected = False
        self._rate_limiter = asyncio.Semaphore(5)
    
    @property
    def name(self) -> str:
        return f"ccxt_{self._exchange_name}"
    
    @property
    def info(self) -> DataSourceInfo:
        return DataSourceInfo(
            name=f"CCXT ({self._exchange_name.title()})",
            provider="CCXT",
            asset_classes=["CRYPTO"],
            has_realtime=True,  # Most exchanges support WebSocket
            has_delayed=False,
            has_historical=True,
            delay_minutes=0,
            rate_limit_per_minute=1200,  # Varies by exchange
            requires_auth=False,  # Public endpoints only
            notes=f"Access to {self._exchange_name} exchange via CCXT library",
        )
    
    async def connect(self) -> None:
        """Initialize connection to exchange."""
        if self._exchange is None:
            self._exchange = getattr(ccxt, self._exchange_name)({
                "enableRateLimit": True,
                "options": {"defaultType": "spot"},
            })
        self._connected = True
    
    async def disconnect(self) -> None:
        """Close the connector."""
        self._connected = False
        self._exchange = None
    
    async def get_price_bars(
        self,
        request: MarketDataRequest
    ) -> pl.DataFrame:
        """
        Retrieve OHLCV price bars from the exchange.
        
        Returns DataFrame with columns:
        - timestamp: datetime
        - open: float
        - high: float
        - low: float
        - close: float
        - volume: float
        """
        request.validate()
        
        if self._exchange is None:
            await self.connect()
        
        # Map timeframe to CCXT format
        timeframe = self._map_timeframe(request.timeframe)
        
        # Convert datetime to timestamp (milliseconds for CCXT)
        since_ms = int(request.start_date.timestamp() * 1000)
        limit = self._calculate_limit(
            request.start_date,
            request.end_date,
            request.timeframe
        )
        
        async with self._rate_limiter:
            loop = asyncio.get_event_loop()
            
            ohlcv = await loop.run_in_executor(
                None,
                lambda: self._exchange.fetch_ohlcv(
                    request.symbol,
                    timeframe,
                    since=since_ms,
                    limit=limit
                )
            )
        
        if not ohlcv:
            return pl.DataFrame()
        
        # Convert to DataFrame
        df = pl.DataFrame(
            ohlcv,
            schema=[
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
            ]
        )
        
        # Convert timestamp to datetime
        df = df.with_columns(
            (pl.col("timestamp") / 1000)
            .cast(pl.Datetime)
            .alias("timestamp")
        )
        
        # Filter to requested end date
        df = df.filter(pl.col("timestamp") <= request.end_date)
        
        # Add source column
        df = df.with_columns(pl.lit(self.name).alias("source"))
        
        return df.sort("timestamp")
    
    async def get_multiple_prices(
        self,
        symbols: list[str]
    ) -> dict[str, float]:
        """Get current prices for multiple symbols."""
        prices = {}
        
        if self._exchange is None:
            await self.connect()
        
        async with self._rate_limiter:
            loop = asyncio.get_event_loop()
            
            for symbol in symbols:
                try:
                    ticker = await loop.run_in_executor(
                        None,
                        lambda s=symbol: self._exchange.fetch_ticker(s)
                    )
                    prices[symbol] = ticker["last"]
                except Exception:
                    prices[symbol] = None
        
        return prices
    
    async def get_order_book(
        self,
        symbol: str,
        limit: int = 100
    ) -> Optional[dict[str, Any]]:
        """Get order book for a symbol."""
        if self._exchange is None:
            await self.connect()
        
        try:
            loop = asyncio.get_event_loop()
            order_book = await loop.run_in_executor(
                None,
                lambda: self._exchange.fetch_order_book(symbol, limit)
            )
            return order_book
        except Exception:
            return None
    
    async def search_symbols(
        self,
        query: str,
        asset_class: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """Search for trading pairs."""
        if self._exchange is None:
            await self.connect()
        
        results = []
        query_upper = query.upper()
        
        # Load markets if not already loaded
        if not self._exchange.markets:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self._exchange.load_markets()
            )
        
        for symbol, market in self._exchange.markets.items():
            if query_upper in symbol.upper():
                results.append({
                    "symbol": symbol,
                    "base": market.get("base", ""),
                    "quote": market.get("quote", ""),
                    "type": market.get("type", "spot"),
                    "active": market.get("active", True),
                    "exchange": self._exchange_name,
                })
                
                if len(results) >= 20:  # Limit results
                    break
        
        return results
    
    async def get_exchange_info(self) -> Optional[dict[str, Any]]:
        """Get exchange information."""
        if self._exchange is None:
            await self.connect()
        
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self._exchange.load_markets()
            )
            
            return {
                "id": self._exchange.id,
                "name": self._exchange.name,
                "countries": self._exchange.countries,
                "symbols": len(self._exchange.markets),
                "has": self._exchange.has,
                "timeframes": self._exchange.timeframes,
            }
        except Exception:
            return None
    
    async def health_check(self) -> dict[str, Any]:
        """Check connector health."""
        try:
            loop = asyncio.get_event_loop()
            start = loop.time()
            
            # Simple API test
            await loop.run_in_executor(
                None,
                lambda: self._exchange.fetch_ticker("BTC/USDT")
            )
            
            latency_ms = (loop.time() - start) * 1000
            
            return {
                "connector": self.name,
                "status": "healthy",
                "latency_ms": round(latency_ms, 2),
                "exchange": self._exchange_name,
                "last_check": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            return {
                "connector": self.name,
                "status": "unhealthy",
                "error": str(e),
                "last_check": datetime.utcnow().isoformat(),
            }
    
    @staticmethod
    def _map_timeframe(tf: str) -> str:
        """Map our timeframe to CCXT format."""
        mapping = {
            "1m": "1m",
            "5m": "5m",
            "15m": "15m",
            "30m": "30m",
            "1h": "1h",
            "4h": "4h",
            "1d": "1d",
            "1w": "1w",
            "1M": "1M",
        }
        return mapping.get(tf, "1h")
    
    @staticmethod
    def _calculate_limit(
        start: datetime,
        end: datetime,
        timeframe: str
    ) -> int:
        """Calculate appropriate limit for fetch request."""
        delta = end - start
        
        # Approximate number of bars
        minutes_per_bar = {
            "1m": 1,
            "5m": 5,
            "15m": 15,
            "30m": 30,
            "1h": 60,
            "4h": 240,
            "1d": 1440,
            "1w": 10080,
        }.get(timeframe, 60)
        
        estimated_bars = int(delta.total_seconds() / (minutes_per_bar * 60))
        # Add buffer and cap at exchange limits
        return min(estimated_bars + 100, 1000)
