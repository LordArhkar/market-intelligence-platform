"""
Trading signal model - Standardized format for all trading signals.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class SignalDirection(str, Enum):
    """Direction of the trading signal."""
    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRAL = "NEUTRAL"


class SignalStatus(str, Enum):
    """Status of the trading signal."""
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    ENTERED = "ENTERED"
    EXITED = "EXITED"
    EXPIRED = "EXPIRED"
    INVALIDATED = "INVALIDATED"
    CANCELLED = "CANCELLED"


class SignalType(str, Enum):
    """Type of trading signal."""
    ENTER_NOW = "ENTER_NOW"
    ENTER_ON_LIMIT = "ENTER_ON_LIMIT"
    WATCH = "WATCH"
    HOLD = "HOLD"
    REDUCE = "REDUCE"
    EXIT = "EXIT"
    NO_TRADE = "NO_TRADE"


class Signal(BaseModel):
    """
    Standardized trading signal format.
    
    Every signal must contain all required fields for complete audit trail.
    """
    # Identification
    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique signal ID")
    
    # Instrument
    symbol: str = Field(..., description="Instrument symbol")
    asset_class: str = Field(..., description="Asset class")
    
    # Direction
    direction: SignalDirection = Field(..., description="Long or short")
    call_put: Optional[str] = Field(
        default=None,
        description="For options: 'call' or 'put'"
    )
    
    # Strategy attribution
    strategy_name: str = Field(..., description="Generating strategy name")
    strategy_version: str = Field(default="1.0", description="Strategy version")
    model_version: Optional[str] = Field(default=None, description="ML model version if applicable")
    
    # Market context
    market_regime: str = Field(default="UNKNOWN", description="Current market regime")
    timeframe: str = Field(..., description="Analysis timeframe")
    
    # Entry parameters
    entry_type: SignalType = Field(..., description="Signal type")
    entry_price: Optional[float] = Field(default=None, description="Target entry price")
    entry_zone_low: Optional[float] = Field(default=None, description="Lower bound of entry zone")
    entry_zone_high: Optional[float] = Field(default=None, description="Upper bound of entry zone")
    
    # Risk parameters
    stop_loss: Optional[float] = Field(default=None, description="Stop loss price")
    stop_loss_percent: Optional[float] = Field(default=None, description="Stop loss as percentage")
    take_profit_1: Optional[float] = Field(default=None, description="First take profit target")
    take_profit_2: Optional[float] = Field(default=None, description="Second take profit target")
    take_profit_3: Optional[float] = Field(default=None, description="Third take profit target")
    
    # Position sizing
    position_risk_percent: float = Field(
        default=1.0,
        description="Percentage of portfolio at risk",
        ge=0.1,
        le=10.0
    )
    expected_reward_risk: Optional[float] = Field(
        default=None,
        description="Expected reward-to-risk ratio"
    )
    
    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = Field(default=None, description="Signal expiry time")
    max_holding_period: Optional[int] = Field(
        default=None,
        description="Maximum holding period in minutes"
    )
    
    # Confidence and evidence
    confidence: float = Field(
        ...,
        description="Confidence score 0-100",
        ge=0.0,
        le=100.0
    )
    supporting_evidence: list[str] = Field(
        default_factory=list,
        description="List of supporting factors"
    )
    contradicting_evidence: list[str] = Field(
        default_factory=list,
        description="List of contradicting factors"
    )
    
    # Status tracking
    status: SignalStatus = Field(default=SignalStatus.PENDING)
    status_updated_at: datetime = Field(default_factory=datetime.utcnow)
    invalidation_reason: Optional[str] = Field(default=None)
    
    # Data provenance
    data_timestamp: datetime = Field(
        ...,
        description="Timestamp of the data used to generate signal"
    )
    source: str = Field(default="system", description="Signal generation source")
    
    # Links
    experiment_id: Optional[str] = Field(default=None, description="Related experiment ID")
    parent_signal_id: Optional[str] = Field(
        default=None,
        description="Parent signal ID for linked signals"
    )
    
    class Config:
        from_attributes = True
    
    @property
    def is_buy(self) -> bool:
        """Signal is a buy (long) signal."""
        return self.direction == SignalDirection.LONG
    
    @property
    def is_sell(self) -> bool:
        """Signal is a sell (short) signal."""
        return self.direction == SignalDirection.SHORT
    
    @property
    def is_active(self) -> bool:
        """Signal is currently actionable."""
        return self.status in [SignalStatus.PENDING, SignalStatus.ACTIVE]
    
    @property
    def is_expired(self) -> bool:
        """Signal has expired."""
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return True
        return False
    
    def invalidate(self, reason: str) -> None:
        """Mark signal as invalidated."""
        self.status = SignalStatus.INVALIDATED
        self.status_updated_at = datetime.utcnow()
        self.invalidation_reason = reason
    
    def update_status(self, status: SignalStatus) -> None:
        """Update signal status with timestamp."""
        self.status = status
        self.status_updated_at = datetime.utcnow()
    
    def to_execution_dict(self) -> dict:
        """Convert to dictionary for execution systems."""
        return {
            "signal_id": self.id,
            "symbol": self.symbol,
            "direction": self.direction.value,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit_1": self.take_profit_1,
            "position_risk_percent": self.position_risk_percent,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }
