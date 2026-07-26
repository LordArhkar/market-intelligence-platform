"""
Risk limits and configuration.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RiskLimits:
    """
    Configurable risk limits for the trading system.
    
    These limits define the boundaries within which the system can operate.
    All trading decisions must pass through these limits.
    """
    
    # Position risk limits
    max_position_risk_percent: float = 2.0
    min_position_risk_percent: float = 0.1
    
    # Portfolio risk limits
    max_portfolio_risk_percent: float = 6.0
    max_daily_loss_percent: float = 3.0
    max_weekly_loss_percent: float = 6.0
    max_drawdown_percent: float = 15.0
    
    # Exposure limits
    max_leverage: float = 1.0
    max_sector_exposure_percent: float = 30.0
    max_asset_class_exposure_percent: float = 60.0
    max_single_position_percent: float = 10.0
    
    # Correlation limits
    max_correlated_exposure: float = 0.7
    max_correlated_positions: int = 3
    
    # Timing limits
    max_holding_hours: int = 168  # 1 week
    min_holding_minutes: int = 5
    
    # Capital requirements
    min_capital_per_trade: float = 100.0
    min_portfolio_value: float = 1000.0
    
    # Prohibited practices
    allow_martingale: bool = False
    allow_averaging_down: bool = False
    allow_short_positions: bool = True
    
    # Signal validity
    max_signal_age_minutes: int = 60
    max_spread_bps: float = 50.0  # Max spread in basis points
    
    # Override capability (for emergency use)
    allow_limit_override: bool = False
    
    def validate(self) -> list[str]:
        """Validate limits configuration."""
        errors = []
        
        if self.max_position_risk_percent > 10:
            errors.append("max_position_risk_percent too high (max 10%)")
        
        if self.min_position_risk_percent < 0:
            errors.append("min_position_risk_percent cannot be negative")
        
        if self.max_position_risk_percent < self.min_position_risk_percent:
            errors.append("max_position_risk_percent must be >= min_position_risk_percent")
        
        if self.max_leverage < 1.0:
            errors.append("max_leverage must be >= 1.0")
        
        if self.max_drawdown_percent > 50:
            errors.append("max_drawdown_percent dangerously high (max 50%)")
        
        return errors


@dataclass
class RiskMetrics:
    """
    Current state of risk metrics for the portfolio.
    """
    portfolio_value: float
    cash: float
    
    # Risk metrics
    current_risk_percent: float = 0.0
    daily_pnl: float = 0.0
    weekly_pnl: float = 0.0
    current_drawdown: float = 0.0
    max_drawdown: float = 0.0
    
    # Position metrics
    open_positions: int = 0
    long_exposure: float = 0.0
    short_exposure: float = 0.0
    
    # Sector exposure
    sector_exposure: dict[str, float] = field(default_factory=dict)
    
    # Asset class exposure
    asset_class_exposure: dict[str, float] = field(default_factory=dict)
    
    # Consecutive losses
    consecutive_losses: int = 0
    winning_streak: int = 0
    
    @property
    def total_exposure(self) -> float:
        """Total exposure (long + short)."""
        return self.long_exposure + self.short_exposure
    
    @property
    def net_exposure(self) -> float:
        """Net exposure (long - short)."""
        return self.long_exposure - self.short_exposure
    
    @property
    def leverage(self) -> float:
        """Current leverage."""
        if self.portfolio_value == 0:
            return 0.0
        return self.total_exposure / self.portfolio_value
    
    @property
    def exposure_percent(self) -> float:
        """Exposure as percentage of portfolio."""
        if self.portfolio_value == 0:
            return 0.0
        return (self.total_exposure / self.portfolio_value) * 100
