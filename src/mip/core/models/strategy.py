"""
Strategy and experiment models - Research tracking.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class StrategyStatus(str, Enum):
    """Status of a strategy."""
    HYPOTHESIS = "HYPOTHESIS"  # Not yet tested
    TESTING = "TESTING"        # In development/testing
    VALIDATING = "VALIDATING"  # Being validated out-of-sample
    ACTIVE = "ACTIVE"          # Generating live signals
    SUSPENDED = "SUSPENDED"    # Temporarily disabled
    RETIRED = "RETIRED"        # No longer in use
    REJECTED = "REJECTED"      # Failed validation


class StrategyCategory(str, Enum):
    """Category of trading strategy."""
    TREND_FOLLOWING = "TREND_FOLLOWING"
    MOMENTUM = "MOMENTUM"
    MEAN_REVERSION = "MEAN_REVERSION"
    BREAKOUT = "BREAKOUT"
    SCALPING = "SCALPING"
    SWING = "SWING"
    POSITIONAL = "POSITIONAL"
    PAIRS = "PAIRS"
    STATISTICAL = "STATISTICAL"
    EVENT_DRIVEN = "EVENT_DRIVEN"
    VOLATILITY = "VOLATILITY"


class Strategy(BaseModel):
    """
    Represents a trading strategy definition.
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(..., description="Strategy name")
    version: str = Field(default="1.0", description="Strategy version")
    
    # Classification
    category: StrategyCategory = Field(..., description="Strategy category")
    asset_classes: list[str] = Field(
        default_factory=list,
        description="Supported asset classes"
    )
    timeframes: list[str] = Field(
        default_factory=list,
        description="Supported timeframes"
    )
    
    # Description
    description: str = Field(..., description="Strategy description")
    hypothesis: str = Field(
        ...,
        description="Falsifiable hypothesis the strategy tests"
    )
    
    # Parameters
    parameters: dict = Field(
        default_factory=dict,
        description="Strategy parameters"
    )
    
    # Status
    status: StrategyStatus = Field(default=StrategyStatus.HYPOTHESIS)
    status_reason: Optional[str] = Field(default=None)
    status_updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Performance (from last evaluation)
    observation_count: int = Field(default=0)
    win_rate: Optional[float] = Field(default=None)
    profit_factor: Optional[float] = Field(default=None)
    sharpe_ratio: Optional[float] = Field(default=None)
    max_drawdown: Optional[float] = Field(default=None)
    expectancy: Optional[float] = Field(default=None)
    
    # Validation requirements
    min_observations: int = Field(default=100)
    min_win_rate: float = Field(default=0.45)
    min_profit_factor: float = Field(default=1.1)
    max_drawdown_limit: float = Field(default=20.0)
    min_sharpe: float = Field(default=0.5)
    
    # Promotion requirements
    can_generate_signals: bool = Field(default=False)
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str = Field(default="system")
    
    class Config:
        from_attributes = True
    
    @property
    def is_active(self) -> bool:
        """Strategy can generate signals."""
        return self.status == StrategyStatus.ACTIVE and self.can_generate_signals
    
    def update_performance(self, **metrics) -> None:
        """Update performance metrics."""
        for key, value in metrics.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = datetime.utcnow()
    
    def can_be_promoted(self) -> tuple[bool, list[str]]:
        """
        Check if strategy meets promotion requirements.
        Returns (can_promote, list_of_missing_requirements).
        """
        missing = []
        
        if self.observation_count < self.min_observations:
            missing.append(f"Observations: {self.observation_count} < {self.min_observations}")
        
        if self.win_rate is not None and self.win_rate < self.min_win_rate:
            missing.append(f"Win rate: {self.win_rate:.1%} < {self.min_win_rate:.1%}")
        
        if self.profit_factor is not None and self.profit_factor < self.min_profit_factor:
            missing.append(f"Profit factor: {self.profit_factor:.2f} < {self.min_profit_factor:.2f}")
        
        if self.max_drawdown is not None and self.max_drawdown > self.max_drawdown_limit:
            missing.append(f"Max drawdown: {self.max_drawdown:.1f}% > {self.max_drawdown_limit:.1f}%")
        
        if self.sharpe_ratio is not None and self.sharpe_ratio < self.min_sharpe:
            missing.append(f"Sharpe: {self.sharpe_ratio:.2f} < {self.min_sharpe:.2f}")
        
        return len(missing) == 0, missing
    
    def promote(self) -> bool:
        """Attempt to promote strategy to active."""
        can_promote, missing = self.can_be_promoted()
        if can_promote:
            self.status = StrategyStatus.ACTIVE
            self.can_generate_signals = True
            self.status_reason = "Promoted after meeting all requirements"
        else:
            self.status_reason = f"Cannot promote: {'; '.join(missing)}"
        self.status_updated_at = datetime.utcnow()
        return can_promote
    
    def suspend(self, reason: str) -> None:
        """Suspend strategy from generating signals."""
        self.status = StrategyStatus.SUSPENDED
        self.can_generate_signals = False
        self.status_reason = reason
        self.status_updated_at = datetime.utcnow()


class Experiment(BaseModel):
    """
    Represents a single backtest or validation experiment.
    
    All experiments are preserved - never delete failed experiments.
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    strategy_id: str = Field(..., description="Related strategy ID")
    experiment_type: str = Field(
        ...,
        description="backtest, walk_forward, out_of_sample, paper_forward"
    )
    
    # Configuration
    name: str = Field(..., description="Experiment name")
    description: str = Field(default="")
    
    # Time range
    start_date: datetime = Field(...)
    end_date: datetime = Field(...)
    
    # Parameters used
    parameters: dict = Field(default_factory=dict)
    
    # Results
    total_trades: int = Field(default=0)
    winning_trades: int = Field(default=0)
    losing_trades: int = Field(default=0)
    
    # Performance metrics
    total_return: float = Field(default=0.0)
    annualized_return: Optional[float] = Field(default=None)
    volatility: Optional[float] = Field(default=None)
    sharpe_ratio: Optional[float] = Field(default=None)
    sortino_ratio: Optional[float] = Field(default=None)
    max_drawdown: float = Field(default=0.0)
    max_drawdown_duration: Optional[int] = Field(default=None)  # days
    profit_factor: Optional[float] = Field(default=None)
    win_rate: Optional[float] = Field(default=None)
    expectancy: Optional[float] = Field(default=None)
    average_win: Optional[float] = Field(default=None)
    average_loss: Optional[float] = Field(default=None)
    largest_win: Optional[float] = Field(default=None)
    largest_loss: Optional[float] = Field(default=None)
    
    # Costs
    total_commission: float = Field(default=0.0)
    total_slippage: float = Field(default=0.0)
    
    # Overfitting metrics
    in_sample_score: Optional[float] = Field(default=None)
    out_of_sample_score: Optional[float] = Field(default=None)
    overfitting_ratio: Optional[float] = Field(default=None)
    
    # Probability metrics
    probability_of_ruin: Optional[float] = Field(default=None)
    statistical_significance: Optional[float] = Field(default=None)
    
    # Status
    status: str = Field(default="PENDING")
    conclusion: Optional[str] = Field(default=None)  # ACCEPT, REJECT, INCONCLUSIVE
    notes: str = Field(default="")
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = Field(default=None)
    
    class Config:
        from_attributes = True
    
    @property
    def is_profitable(self) -> bool:
        """Experiment showed positive returns."""
        return self.total_return > 0
    
    @property
    def edge_is_significant(self) -> bool:
        """Edge appears statistically significant."""
        if self.statistical_significance is None:
            return False
        return self.statistical_significance >= 0.95
    
    @property
    def oos_to_is_ratio(self) -> Optional[float]:
        """Ratio of out-of-sample to in-sample performance."""
        if self.in_sample_score and self.in_sample_score > 0:
            return self.out_of_sample_score / self.in_sample_score
        return None
    
    def to_registry_entry(self) -> dict:
        """Convert to registry format for permanent storage."""
        return {
            "experiment_id": self.id,
            "strategy_id": self.strategy_id,
            "type": self.experiment_type,
            "period": f"{self.start_date.date()} to {self.end_date.date()}",
            "trades": self.total_trades,
            "return": f"{self.total_return:.2f}%",
            "sharpe": f"{self.sharpe_ratio:.2f}" if self.sharpe_ratio else "N/A",
            "max_dd": f"{self.max_drawdown:.2f}%",
            "pf": f"{self.profit_factor:.2f}" if self.profit_factor else "N/A",
            "conclusion": self.conclusion or "PENDING",
            "timestamp": self.completed_at.isoformat() if self.completed_at else self.created_at.isoformat(),
        }
