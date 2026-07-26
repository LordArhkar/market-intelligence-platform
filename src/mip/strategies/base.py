"""
Base strategy class and interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

import polars as pl

from mip.core.models.signal import Signal, SignalDirection


@dataclass
class StrategyResult:
    """Result from a strategy signal generation."""
    
    signals: list[Signal] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    execution_time_ms: float = 0.0
    data_timestamp: Optional[datetime] = None
    
    @property
    def has_signals(self) -> bool:
        """Check if any signals were generated."""
        return len(self.signals) > 0
    
    @property
    def is_successful(self) -> bool:
        """Check if strategy executed without errors."""
        return len(self.errors) == 0


@dataclass
class BacktestTrade:
    """Represents a single trade in a backtest."""
    entry_time: datetime
    exit_time: datetime
    symbol: str
    side: str  # LONG or SHORT
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    pnl_percent: float
    commission: float
    slippage: float
    signal_id: str


@dataclass
class BacktestResult:
    """Result from a backtest run."""
    
    strategy_name: str
    start_date: datetime
    end_date: datetime
    
    # Trade statistics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    trades: list[BacktestTrade] = field(default_factory=list)
    
    # Performance metrics
    total_return: float = 0.0
    annualized_return: float = 0.0
    volatility: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_duration: int = 0  # days
    profit_factor: float = 0.0
    win_rate: float = 0.0
    expectancy: float = 0.0
    average_win: float = 0.0
    average_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    
    # Costs
    total_commission: float = 0.0
    total_slippage: float = 0.0
    
    # Overfitting metrics
    in_sample_score: float = 0.0
    out_of_sample_score: float = 0.0
    
    # Status
    status: str = "PENDING"
    notes: str = ""
    
    @property
    def is_profitable(self) -> bool:
        """Check if strategy was profitable."""
        return self.total_return > 0
    
    @property
    def oos_to_is_ratio(self) -> float:
        """Ratio of OOS to IS performance."""
        if self.in_sample_score == 0:
            return 0.0
        return self.out_of_sample_score / self.in_sample_score
    
    def to_metrics_dict(self) -> dict[str, Any]:
        """Convert to metrics dictionary."""
        return {
            "total_trades": self.total_trades,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "max_drawdown": self.max_drawdown,
            "total_return": self.total_return,
            "annualized_return": self.annualized_return,
            "expectancy": self.expectancy,
            "total_commission": self.total_commission,
            "total_slippage": self.total_slippage,
        }


class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies.
    
    Each strategy must implement:
    - name: Unique strategy identifier
    - generate_signals: Generate signals from market data
    - validate_parameters: Validate strategy parameters
    """
    
    def __init__(self, **params):
        """Initialize strategy with parameters."""
        self.params = params
        self._validate_parameters()
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique strategy name."""
        pass
    
    @property
    @abstractmethod
    def category(self) -> str:
        """Strategy category."""
        pass
    
    @property
    def version(self) -> str:
        """Strategy version."""
        return "1.0"
    
    @property
    def supported_asset_classes(self) -> list[str]:
        """List of supported asset classes."""
        return ["US_EQUITY", "CRYPTO", "FOREX"]
    
    @property
    def supported_timeframes(self) -> list[str]:
        """List of supported timeframes."""
        return ["1h", "4h", "1d"]
    
    @abstractmethod
    def _validate_parameters(self) -> None:
        """Validate strategy parameters. Raise ValueError if invalid."""
        pass
    
    @abstractmethod
    async def generate_signals(
        self,
        data: pl.DataFrame,
        context: dict[str, Any]
    ) -> StrategyResult:
        """
        Generate trading signals from market data.
        
        Args:
            data: DataFrame with price bars (timestamp, open, high, low, close, volume)
            context: Additional context (symbol, asset_class, etc.)
            
        Returns:
            StrategyResult with signals and metrics
        """
        pass
    
    async def calculate_indicators(
        self,
        data: pl.DataFrame
    ) -> pl.DataFrame:
        """
        Calculate technical indicators for the strategy.
        
        Override this method to add custom indicators.
        Default implementation returns input data unchanged.
        """
        return data
    
    async def backtest(
        self,
        data: pl.DataFrame,
        initial_capital: float = 100_000.0,
        commission: float = 0.0,
        slippage_bps: float = 10.0,
    ) -> BacktestResult:
        """
        Run backtest on historical data.
        
        Override this method for custom backtesting logic.
        """
        result = BacktestResult(
            strategy_name=self.name,
            start_date=data["timestamp"].min(),
            end_date=data["timestamp"].max(),
            status="COMPLETED",
        )
        
        # Basic backtest implementation
        result.total_trades = 0
        result.total_return = 0.0
        
        return result
    
    def get_parameter_space(self) -> dict[str, list]:
        """
        Get parameter space for optimization.
        
        Returns dict of parameter_name -> list of values to test.
        Override for custom parameter spaces.
        """
        return {}
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize strategy to dictionary."""
        return {
            "name": self.name,
            "category": self.category,
            "version": self.version,
            "params": self.params,
            "supported_asset_classes": self.supported_asset_classes,
            "supported_timeframes": self.supported_timeframes,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "BaseStrategy":
        """Deserialize strategy from dictionary."""
        return cls(**data.get("params", {}))
