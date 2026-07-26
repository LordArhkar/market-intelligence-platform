"""
Position and trade models - Portfolio tracking.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class PositionStatus(str, Enum):
    """Status of a position."""
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    PENDING = "PENDING"


class PositionSide(str, Enum):
    """Position direction."""
    LONG = "LONG"
    SHORT = "SHORT"


class Trade(BaseModel):
    """
    Represents a single trade (entry or exit).
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    position_id: str = Field(..., description="Parent position ID")
    symbol: str = Field(..., description="Instrument symbol")
    
    # Trade details
    side: PositionSide = Field(..., description="Entry or exit side")
    quantity: float = Field(..., description="Number of units")
    price: float = Field(..., description="Execution price")
    commission: float = Field(default=0.0, description="Commission paid")
    slippage: float = Field(default=0.0, description="Slippage cost")
    
    # Fees
    fees: float = Field(default=0.0, description="Total fees")
    
    # Timing
    executed_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Links
    signal_id: Optional[str] = Field(default=None, description="Signal that triggered trade")
    order_id: Optional[str] = Field(default=None, description="Broker order ID")
    
    # Execution source
    execution_source: str = Field(default="SIMULATOR", description="Where trade was executed")
    
    @property
    def total_cost(self) -> float:
        """Total cost of the trade including fees and slippage."""
        multiplier = 1 if self.side == PositionSide.LONG else -1
        return (self.price * abs(self.quantity) * multiplier) + self.fees + self.commission + self.slippage
    
    @property
    def notional_value(self) -> float:
        """Notional value of the trade."""
        return self.price * abs(self.quantity)


class Position(BaseModel):
    """
    Represents an open or closed position.
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    symbol: str = Field(..., description="Instrument symbol")
    asset_class: str = Field(..., description="Asset class")
    
    # Position details
    side: PositionSide = Field(..., description="Long or short")
    quantity: float = Field(..., description="Current quantity")
    average_entry_price: float = Field(..., description="Average entry price")
    
    # Current state
    current_price: float = Field(default=0.0, description="Current market price")
    status: PositionStatus = Field(default=PositionStatus.OPEN)
    
    # Risk parameters (from entry signal)
    stop_loss: Optional[float] = Field(default=None)
    take_profit: Optional[float] = Field(default=None)
    position_risk_percent: float = Field(default=1.0)
    
    # Strategy attribution
    strategy_name: str = Field(..., description="Entry strategy")
    strategy_version: str = Field(default="1.0")
    
    # Entry
    entry_signal_id: Optional[str] = Field(default=None)
    entry_time: datetime = Field(default_factory=datetime.utcnow)
    entry_trade_id: Optional[str] = Field(default=None)
    
    # Exit
    exit_time: Optional[datetime] = Field(default=None)
    exit_trade_id: Optional[str] = Field(default=None)
    exit_reason: Optional[str] = Field(default=None)
    realized_pnl: Optional[float] = Field(default=None)
    
    # Running P&L
    unrealized_pnl: float = Field(default=0.0)
    
    # Trade tracking
    trades: list[Trade] = Field(default_factory=list)
    
    class Config:
        from_attributes = True
    
    @property
    def is_open(self) -> bool:
        """Position is currently open."""
        return self.status == PositionStatus.OPEN
    
    @property
    def is_long(self) -> bool:
        """Position is long."""
        return self.side == PositionSide.LONG
    
    @property
    def market_value(self) -> float:
        """Current market value of position."""
        multiplier = 1 if self.is_long else -1
        return self.current_price * abs(self.quantity) * multiplier
    
    @property
    def cost_basis(self) -> float:
        """Total cost of opening the position."""
        return self.average_entry_price * abs(self.quantity)
    
    @property
    def unrealized_pnl_percent(self) -> float:
        """Unrealized P&L as percentage of cost basis."""
        if self.cost_basis == 0:
            return 0.0
        return (self.unrealized_pnl / self.cost_basis) * 100
    
    @property
    def risk_reward_ratio(self) -> Optional[float]:
        """Current risk/reward ratio."""
        if not self.stop_loss or not self.take_profit:
            return None
        
        if self.is_long:
            profit = self.take_profit - self.average_entry_price
            loss = self.average_entry_price - self.stop_loss
        else:
            profit = self.average_entry_price - self.take_profit
            loss = self.stop_loss - self.average_entry_price
        
        if loss == 0:
            return None
        return profit / loss
    
    def update_price(self, new_price: float) -> None:
        """Update current price and recalculate unrealized P&L."""
        self.current_price = new_price
        
        if self.is_long:
            self.unrealized_pnl = (new_price - self.average_entry_price) * abs(self.quantity)
        else:
            self.unrealized_pnl = (self.average_entry_price - new_price) * abs(self.quantity)
    
    def add_trade(self, trade: Trade) -> None:
        """Add a trade to this position."""
        self.trades.append(trade)
    
    def check_stop_loss(self, current_price: float) -> bool:
        """Check if stop loss has been hit."""
        if not self.stop_loss:
            return False
        
        if self.is_long and current_price <= self.stop_loss:
            return True
        if not self.is_long and current_price >= self.stop_loss:
            return True
        return False
    
    def check_take_profit(self, current_price: float) -> bool:
        """Check if take profit has been hit."""
        if not self.take_profit:
            return False
        
        if self.is_long and current_price >= self.take_profit:
            return True
        if not self.is_long and current_price <= self.take_profit:
            return True
        return False
