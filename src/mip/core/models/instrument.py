"""
Instrument model - Security master for all tradeable instruments.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class AssetClass(str, Enum):
    """Asset class classification."""
    US_EQUITY = "US_EQUITY"
    CANADIAN_EQUITY = "CANADIAN_EQUITY"
    FOREX = "FOREX"
    CRYPTO = "CRYPTO"
    INDEX = "INDEX"
    US_OPTIONS = "US_OPTIONS"


class Exchange(str, Enum):
    """Exchange where instrument is listed."""
    NYSE = "NYSE"
    NASDAQ = "NASDAQ"
    AMEX = "AMEX"
    TSX = "TSX"
    TSXV = "TSXV"
    CSE = "CSE"
    OANDA = "OANDA"
    FOREXCOM = "FOREXCOM"
    BINANCE = "BINANCE"
    COINBASE = "COINBASE"
    KROKEN = "KRAKEN"
    CUSTOM = "CUSTOM"


class Instrument(BaseModel):
    """
    Represents a tradeable instrument with all relevant metadata.
    
    This is the security master record - one record per unique instrument.
    """
    id: Optional[int] = Field(default=None, description="Database ID")
    symbol: str = Field(..., description="Ticker symbol (e.g., AAPL, BTC/USD)")
    name: str = Field(..., description="Full name of the instrument")
    asset_class: AssetClass = Field(..., description="Asset class")
    exchange: Exchange = Field(..., description="Primary listing exchange")
    
    # Contract details (for options)
    strike_price: Optional[float] = Field(default=None, description="Strike price for options")
    expiration_date: Optional[datetime] = Field(default=None, description="Expiry for options/futures")
    option_type: Optional[str] = Field(default=None, description="'call' or 'put' for options")
    
    # Multi-exchange support
    aliases: dict[str, str] = Field(
        default_factory=dict,
        description="Symbol aliases for different data providers"
    )
    
    # Corporate actions
    adjustment_factor: float = Field(
        default=1.0,
        description="Cumulative adjustment factor for corporate actions"
    )
    last_split_date: Optional[datetime] = Field(default=None)
    last_split_ratio: Optional[float] = Field(default=None)
    
    # Status
    is_active: bool = Field(default=True, description="Whether instrument is tradeable")
    added_date: datetime = Field(default_factory=datetime.utcnow)
    removed_date: Optional[datetime] = Field(default=None)
    
    # Metadata
    sector: Optional[str] = Field(default=None, description="Industry sector")
    industry: Optional[str] = Field(default=None, description="Industry group")
    market_cap: Optional[float] = Field(default=None, description="Market capitalization")
    base_currency: str = Field(default="USD", description="Quote currency")
    
    model_config = ConfigDict(from_attributes=True)
    
    def get_symbol_for_provider(self, provider: str) -> str:
        """Get the appropriate symbol for a specific data provider."""
        return self.aliases.get(provider, self.symbol)
    
    def is_options(self) -> bool:
        """Check if this instrument is an options contract."""
        return self.asset_class == AssetClass.US_OPTIONS
    
    def options_key(self) -> str:
        """Generate a unique key for options contracts."""
        if not self.is_options():
            return self.symbol
        return f"{self.symbol}:{self.expiration_date.strftime('%Y%m%d')}:{self.strike_price}:{self.option_type}"
