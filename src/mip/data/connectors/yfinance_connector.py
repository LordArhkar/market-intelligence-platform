"""
Yahoo Finance data connector.

Free data source for US equities, crypto, and forex.
"""

import asyncio
from datetime import datetime
from typing import Any, Optional

import polars as pl
import yfinance as yf

from mip.core.config import get_settings
from mip.data.connectors.base import (
    DataConnector,
    DataSourceInfo,
    MarketDataRequest,
)


class YahooFinanceConnector(DataConnector):
    """
    Yahoo Finance connector for market data.
    
    Coverage:
    - US Equities (NYSE, NASDAQ, AMEX)
    - Crypto (BTC, ETH, etc.)
    - Forex (EURUSD, etc.)
    - Some international markets
    
    Limitations:
    - 15-minute delay for US equities
    - Rate limits apply
    - Historical data depth varies by asset class
    """
    
    def __init__(self):
        self._settings = get_settings()
        self._connected = False
        self._rate_limiter = asyncio.Semaphore(2)  # Limit concurrent requests
    
    @property
    def name(self) -> str:
        return "yahoo_finance"
    
    @property
    def info(self) -> DataSourceInfo:
        return DataSourceInfo(
            name="Yahoo Finance",
            provider="Yahoo",
            asset_classes=["US_EQUITY", "CRYPTO", "FOREX"],
            has_realtime=False,
            has_delayed=True,
            has_historical=True,
            delay_minutes=15,  # Delayed quotes
            rate_limit_per_minute=2000,
            requires_auth=False,
            notes="Free tier with rate limits. Use for historical data and delayed quotes.",
        )
    
    async def connect(self) -> None:
        """Initialize the connector."""
        self._connected = True
    
    async def disconnect(self) -> None:
        """Close the connector."""
        self._connected = False
    
    async def get_price_bars(
        self,
        request: MarketDataRequest
    ) -> pl.DataFrame:
        """
        Retrieve price bars from Yahoo Finance.
        
        Returns DataFrame with columns:
        - timestamp: datetime
        - open: float
        - high: float
        - low: float
        - close: float
        - volume: float
        """
        request.validate()
        
        async with self._rate_limiter:
            # Run blocking yfinance call in executor
            loop = asyncio.get_event_loop()
            ticker = await loop.run_in_executor(
                None,
                lambda: yf.Ticker(request.symbol)
            )
            
            hist = await loop.run_in_executor(
                None,
                lambda: ticker.history(
                    start=request.start_date,
                    end=request.end_date,
                    interval=self._map_timeframe(request.timeframe),
                    auto_adjust=True,
                    back_adjust=True,
                )
            )
        
        if hist is None or hist.empty:
            return pl.DataFrame()
        
        # Convert to Polars
        df = pl.from_pandas(hist.reset_index())
        
        # Rename columns to lowercase
        column_mapping = {
            "Datetime": "timestamp",
            "Date": "timestamp",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
        df = df.rename(column_mapping)
        
        # Ensure timestamp is datetime
        if "timestamp" in df.columns:
            df = df.with_columns(pl.col("timestamp").cast(pl.Datetime))
        
        # Select and order columns
        required_cols = ["timestamp", "open", "high", "low", "close", "volume"]
        available_cols = [c for c in required_cols if c in df.columns]
        df = df.select(available_cols)
        
        # Add source column
        df = df.with_columns(pl.lit(self.name).alias("source"))
        
        return df.sort("timestamp")
    
    async def get_multiple_prices(
        self,
        symbols: list[str]
    ) -> dict[str, float]:
        """Get current prices for multiple symbols."""
        prices = {}
        
        async with self._rate_limiter:
            loop = asyncio.get_event_loop()
            
            # Download in batch for efficiency
            tickers_str = " ".join(symbols)
            data = await loop.run_in_executor(
                None,
                lambda: yf.download(
                    tickers=tickers_str,
                    period="1d",
                    progress=False,
                    auto_adjust=True,
                )
            )
        
        if data is None or data.empty:
            return prices
        
        for symbol in symbols:
            try:
                if len(symbols) == 1:
                    close_col = data["Close"]
                else:
                    close_col = data["Close"][symbol]
                
                if not close_col.empty:
                    prices[symbol] = float(close_col.iloc[-1])
            except (KeyError, IndexError):
                prices[symbol] = None
        
        return prices
    
    async def search_symbols(
        self,
        query: str,
        asset_class: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """
        Search for symbols using Yahoo Finance.
        
        Note: Yahoo Finance doesn't have a direct search API.
        This uses a basic approach - in production, consider using
        a dedicated search service.
        """
        # Basic implementation - in production, use a proper search service
        results = []
        
        # Try to get the ticker directly
        try:
            loop = asyncio.get_event_loop()
            ticker = await loop.run_in_executor(
                None,
                lambda: yf.Ticker(query)
            )
            info = await loop.run_in_executor(None, lambda: ticker.info)
            
            if info and "symbol" in info:
                results.append({
                    "symbol": info.get("symbol", query),
                    "name": info.get("longName", info.get("shortName", "")),
                    "type": info.get("quoteType", "UNKNOWN"),
                    "exchange": info.get("exchange", ""),
                    "asset_class": self._classify_asset(info),
                })
        except Exception:
            pass
        
        return results
    
    async def get_fundamentals(self, symbol: str) -> Optional[dict[str, Any]]:
        """Get fundamental data for a symbol."""
        try:
            loop = asyncio.get_event_loop()
            ticker = await loop.run_in_executor(
                None,
                lambda: yf.Ticker(symbol)
            )
            info = await loop.run_in_executor(None, lambda: ticker.info)
            return info
        except Exception:
            return None
    
    async def get_options_chain(
        self,
        symbol: str,
        date: Optional[datetime] = None
    ) -> Optional[dict[str, Any]]:
        """Get options chain for a symbol."""
        try:
            loop = asyncio.get_event_loop()
            ticker = await loop.run_in_executor(
                None,
                lambda: yf.Ticker(symbol)
            )
            options = await loop.run_in_executor(
                None,
                lambda: ticker.options
            )
            
            if not options:
                return None
            
            # Get the first expiration if none specified
            exp_date = date.strftime("%Y-%m-%d") if date else options[0]
            
            calls = await loop.run_in_executor(
                None,
                lambda: ticker.option_chain(exp_date).calls.to_dict()
            )
            puts = await loop.run_in_executor(
                None,
                lambda: ticker.option_chain(exp_date).puts.to_dict()
            )
            
            return {
                "expiration": exp_date,
                "calls": calls,
                "puts": puts,
            }
        except Exception:
            return None
    
    async def health_check(self) -> dict[str, Any]:
        """Check connector health."""
        try:
            loop = asyncio.get_event_loop()
            start = loop.time()
            
            # Quick test request
            ticker = await loop.run_in_executor(
                None,
                lambda: yf.Ticker("AAPL")
            )
            _ = await loop.run_in_executor(
                None,
                lambda: ticker.history(period="1d")
            )
            
            latency_ms = (loop.time() - start) * 1000
            
            return {
                "connector": self.name,
                "status": "healthy",
                "latency_ms": round(latency_ms, 2),
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
        """Map our timeframe to yfinance interval."""
        mapping = {
            "1m": "1m",
            "5m": "5m",
            "15m": "15m",
            "30m": "30m",
            "1h": "60m",
            "4h": "4h",
            "1d": "1d",
            "1w": "1wk",
        }
        return mapping.get(tf, "1d")
    
    @staticmethod
    def _classify_asset(info: dict) -> str:
        """Classify asset based on Yahoo Finance info."""
        quote_type = info.get("quoteType", "").upper()
        
        if quote_type == "EQUITY":
            exchange = info.get("exchange", "").upper()
            if exchange == "PCX":  # Crypto
                return "CRYPTO"
            return "US_EQUITY"
        elif quote_type == "CRYPTOCURRENCY":
            return "CRYPTO"
        elif quote_type in ["FOREX", "CURRENCY"]:
            return "FOREX"
        elif quote_type == "INDEX":
            return "INDEX"
        else:
            return quote_type
