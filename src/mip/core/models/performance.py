"""
Performance tracking models.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PerformanceRecord(BaseModel):
    """
    Daily performance snapshot for a portfolio or strategy.
    """
    id: Optional[int] = Field(default=None)
    
    # Date
    date: datetime = Field(..., description="Trading date")
    
    # Portfolio values
    equity: float = Field(..., description="Total equity at end of day")
    cash: float = Field(default=0.0, description="Cash balance")
    positions_value: float = Field(default=0.0, description="Value of open positions")
    
    # Daily P&L
    daily_pnl: float = Field(default=0.0, description="Realized + unrealized P&L for day")
    realized_pnl: float = Field(default=0.0, description="Closed trade P&L")
    unrealized_pnl: float = Field(default=0.0, description="Open position P&L")
    
    # Returns
    daily_return: float = Field(default=0.0, description="Daily return percentage")
    cumulative_return: float = Field(default=0.0, description="Return since inception")
    
    # Risk metrics
    daily_volatility: Optional[float] = Field(default=None)
    portfolio_var_95: Optional[float] = Field(default=None, description="95% Value at Risk")
    
    # Drawdown
    peak_equity: float = Field(..., description="Highest equity achieved")
    current_drawdown: float = Field(default=0.0, description="Current drawdown percentage")
    max_drawdown: float = Field(default=0.0, description="Maximum drawdown this period")
    
    # Activity
    trades_opened: int = Field(default=0)
    trades_closed: int = Field(default=0)
    new_signals: int = Field(default=0)
    signals_invalidated: int = Field(default=0)
    
    # Operating mode
    mode: str = Field(default="VALIDATION", description="VALIDATION or TOURNAMENT")
    
    # Attribution
    strategy_pnl: dict[str, float] = Field(
        default_factory=dict,
        description="P&L by strategy"
    )
    asset_class_pnl: dict[str, float] = Field(
        default_factory=dict,
        description="P&L by asset class"
    )
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        from_attributes = True
    
    @property
    def leverage(self) -> float:
        """Current leverage being used."""
        if self.equity == 0:
            return 0.0
        return (self.cash + self.positions_value) / self.equity
    
    @property
    def exposure_percent(self) -> float:
        """Percentage of equity in positions."""
        if self.equity == 0:
            return 0.0
        return (self.positions_value / self.equity) * 100


class PortfolioSnapshot(BaseModel):
    """
    Point-in-time snapshot of portfolio state.
    """
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Values
    total_equity: float
    cash: float
    positions_value: float
    
    # Open positions
    positions: list[dict] = Field(default_factory=list)
    
    # Pending orders/signals
    pending_signals: int = Field(default=0)
    active_signals: int = Field(default=0)
    
    # Risk limits
    risk_utilization: float = Field(default=0.0)
    exposure_utilization: float = Field(default=0.0)
    
    # Performance
    today_pnl: float = Field(default=0.0)
    streak_days: int = Field(default=0)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "equity": self.total_equity,
            "cash": self.cash,
            "positions_value": self.positions_value,
            "positions_count": len(self.positions),
            "pending_signals": self.pending_signals,
            "active_signals": self.active_signals,
            "risk_utilization": f"{self.risk_utilization:.1f}%",
            "today_pnl": self.today_pnl,
        }
