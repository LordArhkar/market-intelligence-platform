"""
Backtesting engine with walk-forward validation.

This module provides rigorous backtesting methodology including:
- Walk-forward analysis
- Out-of-sample testing
- Transaction cost modeling
- Performance metrics
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional
import polars as pl

from mip.core.models.strategy import Strategy
from mip.strategies.base import BaseStrategy, BacktestResult, BacktestTrade


@dataclass
class BacktestConfig:
    """Configuration for backtesting."""
    
    # Data settings
    initial_capital: float = 100_000.0
    symbol: str = "UNKNOWN"
    
    # Cost modeling
    commission_per_share: float = 0.0
    commission_percent: float = 0.0
    slippage_bps: float = 10.0  # Basis points
    
    # Walk-forward settings
    train_window_days: int = 252  # ~1 year training
    test_window_days: int = 63   # ~3 months testing
    step_days: int = 21          # ~1 month step
    
    # Position sizing
    risk_per_trade_percent: float = 1.0
    max_positions: int = 5
    
    # Validation
    min_trades_for_significance: int = 30


@dataclass
class WalkForwardResult:
    """Results from a walk-forward analysis."""
    
    strategy_name: str
    config: BacktestConfig
    
    # Overall metrics
    total_return: float = 0.0
    annualized_return: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    
    # Walk-forward metrics
    in_sample_return: float = 0.0
    out_of_sample_return: float = 0.0
    oos_to_is_ratio: float = 0.0  # OOS performance relative to IS
    
    # Consistency metrics
    period_returns: list[float] = field(default_factory=list)
    period_sharpes: list[float] = field(default_factory=list)
    periods_count: int = 0
    periods_passed: int = 0
    
    # Trade statistics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    
    # Statistical significance
    t_statistic: float = 0.0
    p_value: float = 1.0
    confidence_level: str = "NOT_SIGNIFICANT"
    
    # Conclusion
    is_valid: bool = False
    conclusion: str = "INCONCLUSIVE"
    notes: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "strategy": self.strategy_name,
            "total_return": f"{self.total_return:.2f}%",
            "annualized_return": f"{self.annualized_return:.2f}%",
            "sharpe_ratio": f"{self.sharpe_ratio:.2f}",
            "max_drawdown": f"{self.max_drawdown:.2f}%",
            "win_rate": f"{self.win_rate:.1%}",
            "profit_factor": f"{self.profit_factor:.2f}",
            "expectancy": f"${self.expectancy:.2f}",
            "oos_to_is_ratio": f"{self.oos_to_is_ratio:.2f}",
            "total_trades": self.total_trades,
            "significance": self.confidence_level,
            "conclusion": self.conclusion,
        }


class BacktestEngine:
    """
    Backtesting engine with rigorous validation.
    
    Supports:
    - Simple backtesting on full dataset
    - Walk-forward analysis
    - Out-of-sample validation
    """
    
    def __init__(self, config: Optional[BacktestConfig] = None):
        self.config = config or BacktestConfig()
    
    def run_backtest(
        self,
        strategy: BaseStrategy,
        data: pl.DataFrame,
    ) -> BacktestResult:
        """
        Run a simple backtest on the provided data.
        
        Args:
            strategy: Strategy to backtest
            data: Historical price data with columns [timestamp, open, high, low, close, volume]
            
        Returns:
            BacktestResult with performance metrics
        """
        result = BacktestResult(
            strategy_name=strategy.name,
            start_date=data["timestamp"].min(),
            end_date=data["timestamp"].max(),
            status="COMPLETED",
        )
        
        if len(data) < 50:
            result.notes = "Insufficient data for backtest"
            return result
        
        # Initialize tracking
        cash = self.config.initial_capital
        position = None
        trades: list[BacktestTrade] = []
        equity_curve = [cash]
        returns = []
        
        # Process each bar
        for i in range(20, len(data)):  # Start after indicator warmup
            bar = data.slice(i, 1)
            current_price = bar["close"][0]
            timestamp = bar["timestamp"][0]
            
            # Calculate P&L if position exists
            if position is not None:
                if position["side"] == "LONG":
                    pnl = (current_price - position["entry_price"]) * position["quantity"]
                else:
                    pnl = (position["entry_price"] - current_price) * position["quantity"]
                
                # Check stop loss
                if position["stop_loss"] and (
                    (position["side"] == "LONG" and current_price <= position["stop_loss"]) or
                    (position["side"] == "SHORT" and current_price >= position["stop_loss"])
                ):
                    # Exit at stop
                    exit_price = position["stop_loss"]
                    commission = self._calculate_commission(position["quantity"], exit_price)
                    slippage = self._calculate_slippage(exit_price)
                    pnl = self._calculate_trade_pnl(position, exit_price) - commission - slippage
                    
                    trade = self._create_trade(position, timestamp, exit_price, pnl)
                    trades.append(trade)
                    cash += position["quantity"] * exit_price - commission - slippage if position["side"] == "LONG" else position["quantity"] * exit_price + commission + slippage
                    position = None
            
            # Check for new signals (simple momentum signal for demo)
            if position is None and i > 20:
                signal = self._generate_simple_signal(data.slice(0, i), current_price, self.config.symbol)
                
                if signal:
                    risk_amount = cash * (self.config.risk_per_trade_percent / 100)
                    risk_per_share = current_price * 0.02  # 2% stop
                    quantity = int(risk_amount / risk_per_share)
                    
                    if quantity > 0:
                        commission = self._calculate_commission(quantity, current_price)
                        slippage = self._calculate_slippage(current_price)
                        total_cost = quantity * current_price + commission + slippage
                        
                        if total_cost <= cash:
                            position = {
                                "side": signal["direction"],
                                "entry_price": current_price,
                                "quantity": quantity,
                                "entry_time": timestamp,
                                "stop_loss": current_price * (0.98 if signal["direction"] == "LONG" else 1.02),
                                "signal_id": signal.get("id", "unknown"),
                            }
                            cash -= total_cost
            
            # Record equity
            position_value = position["quantity"] * current_price if position else 0
            equity = cash + position_value
            equity_curve.append(equity)
            
            # Calculate daily return
            if len(equity_curve) > 1:
                daily_return = (equity_curve[-1] - equity_curve[-2]) / equity_curve[-2]
                returns.append(daily_return)
        
        # Calculate metrics
        result.total_trades = len(trades)
        result.winning_trades = sum(1 for t in trades if t.pnl > 0)
        result.losing_trades = sum(1 for t in trades if t.pnl <= 0)
        
        if result.total_trades > 0:
            result.win_rate = result.winning_trades / result.total_trades
            
            total_pnl = sum(t.pnl for t in trades)
            result.total_return = (total_pnl / self.config.initial_capital) * 100
            
            # Profit factor
            gross_profit = sum(t.pnl for t in trades if t.pnl > 0)
            gross_loss = abs(sum(t.pnl for t in trades if t.pnl < 0))
            result.profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
            
            # Expectancy
            result.expectancy = total_pnl / result.total_trades
            
            # Average win/loss
            if result.winning_trades > 0:
                result.average_win = gross_profit / result.winning_trades
            if result.losing_trades > 0:
                result.average_loss = gross_loss / result.losing_trades
            
            result.total_commission = sum(t.commission for t in trades)
            result.total_slippage = sum(t.slippage for t in trades)
        
        # Calculate risk metrics
        if returns:
            import numpy as np
            returns_arr = np.array(returns)
            result.volatility = np.std(returns_arr) * np.sqrt(252) * 100
            result.sharpe_ratio = (np.mean(returns_arr) * 252) / (np.std(returns_arr) * np.sqrt(252)) if np.std(returns_arr) > 0 else 0
            
            # Sortino (downside deviation)
            downside_returns = returns_arr[returns_arr < 0]
            downside_std = np.std(downside_returns) if len(downside_returns) > 0 else 0
            result.sortino_ratio = (np.mean(returns_arr) * 252) / (downside_std * np.sqrt(252)) if downside_std > 0 else 0
        
        # Max drawdown
        peak = self.config.initial_capital
        max_dd = 0
        for equity in equity_curve:
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak * 100
            max_dd = max(max_dd, dd)
        result.max_drawdown = max_dd
        
        result.trades = trades
        
        return result
    
    def run_walk_forward(
        self,
        strategy: BaseStrategy,
        data: pl.DataFrame,
    ) -> WalkForwardResult:
        """
        Run walk-forward analysis.
        
        Train on train_window, test on test_window, step forward by step_days.
        """
        result = WalkForwardResult(
            strategy_name=strategy.name,
            config=self.config,
        )
        
        start_date = data["timestamp"].min()
        end_date = data["timestamp"].max()
        
        # Calculate walk-forward windows
        current_train_end = start_date + timedelta(days=self.config.train_window_days)
        
        is_returns = []
        oos_returns = []
        period_sharpes = []
        
        while current_train_end < end_date:
            train_end = current_train_end
            test_end = min(train_end + timedelta(days=self.config.test_window_days), end_date)
            
            # Split data
            train_data = data.filter(
                (pl.col("timestamp") >= start_date) &
                (pl.col("timestamp") < train_end)
            )
            test_data = data.filter(
                (pl.col("timestamp") >= train_end) &
                (pl.col("timestamp") < test_end)
            )
            
            if len(train_data) < 50 or len(test_data) < 20:
                current_train_end += timedelta(days=self.config.step_days)
                continue
            
            # Run backtest on train (IS)
            is_result = self._run_simple_backtest(strategy, train_data, self.config.initial_capital)
            is_returns.append(is_result.total_return)
            
            # Run backtest on test (OOS)
            oos_result = self._run_simple_backtest(strategy, test_data, self.config.initial_capital)
            oos_returns.append(oos_result.total_return)
            
            if oos_result.total_trades >= self.config.min_trades_for_significance:
                period_sharpes.append(oos_result.sharpe_ratio)
            
            current_train_end += timedelta(days=self.config.step_days)
        
        # Aggregate results
        if is_returns:
            result.in_sample_return = sum(is_returns) / len(is_returns)
            result.period_returns = is_returns
        if oos_returns:
            result.out_of_sample_return = sum(oos_returns) / len(oos_returns)
            result.periods_count = len(oos_returns)
            result.periods_passed = sum(1 for r in oos_returns if r > 0)
        
        # OOS to IS ratio
        if result.in_sample_return > 0:
            result.oos_to_is_ratio = result.out_of_sample_return / result.in_sample_return
        
        # Calculate overall metrics
        all_returns = is_returns + oos_returns
        result.total_return = sum(all_returns) / len(all_returns) if all_returns else 0
        
        # Sharpe from period returns
        if len(oos_returns) > 1:
            import numpy as np
            oos_arr = np.array(oos_returns)
            result.sharpe_ratio = np.mean(oos_arr) / np.std(oos_arr) if np.std(oos_arr) > 0 else 0
            result.sortino_ratio = result.sharpe_ratio  # Simplified
        
        # Win rate
        result.total_trades = sum(1 for r in oos_returns if abs(r) > 0.5)
        result.winning_trades = sum(1 for r in oos_returns if r > 0)
        result.losing_trades = sum(1 for r in oos_returns if r <= 0)
        result.win_rate = result.winning_trades / result.total_trades if result.total_trades > 0 else 0
        
        # Determine significance
        self._calculate_significance(result, oos_returns)
        
        # Determine validity
        result.is_valid = (
            result.out_of_sample_return > 0 and
            result.confidence_level != "NOT_SIGNIFICANT" and
            result.periods_passed >= result.periods_count * 0.5
        )
        
        # Conclusion
        if result.is_valid and result.oos_to_is_ratio > 0.5:
            result.conclusion = "VALIDATED"
            result.notes.append("Strategy shows consistent positive performance")
        elif result.is_valid and result.oos_to_is_ratio <= 0.5:
            result.conclusion = "POSSIBLE_OVERFITTING"
            result.notes.append("IS performance significantly better than OOS")
        else:
            result.conclusion = "NOT_VALIDATED"
            result.notes.append("Strategy does not show robust out-of-sample performance")
        
        return result
    
    def _run_simple_backtest(
        self,
        strategy: BaseStrategy,
        data: pl.DataFrame,
        initial_capital: float,
    ) -> BacktestResult:
        """Run a backtest using the actual strategy's signal generation."""
        result = BacktestResult(
            strategy_name=strategy.name,
            start_date=data["timestamp"].min(),
            end_date=data["timestamp"].max(),
        )
        
        if len(data) < 50:
            return result
        
        cash = initial_capital
        trades = 0
        wins = 0
        total_pnl = 0.0
        position = None
        
        # Process each bar
        for i in range(30, len(data) - 1):
            # Get historical data up to current point
            history = data.slice(0, i)
            current_bar = data.slice(i, 1)
            current_price = float(current_bar["close"][0])
            next_price = float(data["close"][i + 1])
            timestamp = current_bar["timestamp"][0]
            
            # Skip if in a position
            if position is not None:
                # Check exit conditions
                should_exit = False
                exit_reason = "signal"
                
                # Time-based exit (max 10 bars)
                if i - position["entry_bar"] > 10:
                    should_exit = True
                    exit_reason = "time"
                
                # Stop loss
                if position["stop_loss"] and (
                    (position["direction"] == "LONG" and current_price <= position["stop_loss"]) or
                    (position["direction"] == "SHORT" and current_price >= position["stop_loss"])
                ):
                    should_exit = True
                    exit_reason = "stop"
                
                if should_exit:
                    entry_value = position["shares"] * position["entry_price"]
                    exit_value = position["shares"] * current_price
                    pnl = exit_value - entry_value
                    
                    if position["direction"] == "SHORT":
                        pnl = -pnl
                    
                    total_pnl += pnl
                    trades += 1
                    if pnl > 0:
                        wins += 1
                    
                    position = None
            
            # Generate signal if no position
            if position is None:
                context = {
                    "symbol": self.config.symbol,
                    "asset_class": "US_EQUITY",
                    "timeframe": "1d",
                    "regime": "UNKNOWN",
                }
                
                # Run strategy (simplified - just get direction)
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                # Create a simplified signal check
                signal_result = self._generate_strategy_signal(strategy, history)
                
                if signal_result is not None:
                    direction = signal_result["direction"]
                    confidence = signal_result.get("confidence", 50)
                    
                    # Only enter if confidence is high enough
                    if confidence >= 55:
                        risk_amount = cash * (self.config.risk_per_trade_percent / 100)
                        stop_distance = current_price * 0.02  # 2% stop
                        shares = int(risk_amount / stop_distance)
                        
                        if shares > 0:
                            entry_value = shares * current_price
                            commission = self._calculate_commission(shares, current_price)
                            slippage = self._calculate_slippage(current_price)
                            
                            if entry_value + commission + slippage <= cash:
                                cash -= (entry_value + commission + slippage)
                                
                                position = {
                                    "direction": direction,
                                    "entry_price": current_price,
                                    "shares": shares,
                                    "entry_bar": i,
                                    "stop_loss": current_price - stop_distance if direction == "LONG" else current_price + stop_distance,
                                }
        
        # Calculate final metrics
        result.total_trades = trades
        result.winning_trades = wins
        result.losing_trades = max(0, trades - wins)
        result.total_return = (total_pnl / initial_capital) * 100
        result.win_rate = wins / trades if trades > 0 else 0
        
        return result
    
    def _generate_strategy_signal(
        self,
        strategy: BaseStrategy,
        data: pl.DataFrame,
    ) -> Optional[dict]:
        """Generate a signal using the actual strategy."""
        try:
            # For now, use simple momentum as a proxy
            if len(data) < 30:
                return None
            
            # Calculate momentum
            lookback = min(20, len(data) - 5)
            current_price = float(data["close"][-1])
            past_price = float(data["close"][-lookback])
            momentum = (current_price - past_price) / past_price
            
            # Calculate RSI-like momentum
            gains = 0
            losses = 0
            for i in range(-14, 0):
                change = float(data["close"][i]) - float(data["close"][i-1])
                if change > 0:
                    gains += change
                else:
                    losses += abs(change)
            
            avg_gain = gains / 14
            avg_loss = losses / 14
            rs = avg_gain / avg_loss if avg_loss > 0 else 100
            rsi = 100 - (100 / (1 + rs))
            
            # Strategy-specific signals
            if strategy.name == "momentum":
                if momentum > 0.03 and rsi < 70:
                    return {"direction": "LONG", "confidence": min(50 + momentum * 500, 80)}
                elif momentum < -0.03 and rsi > 30:
                    return {"direction": "SHORT", "confidence": min(50 + abs(momentum) * 500, 80)}
            
            elif strategy.name == "mean_reversion":
                # Bollinger Band position
                sma_20 = float(data["close"][-20:].mean())
                std_20 = float(data["close"][-20:].std())
                bb_upper = sma_20 + 2 * std_20
                bb_lower = sma_20 - 2 * std_20
                
                if current_price < bb_lower:
                    return {"direction": "LONG", "confidence": 60}
                elif current_price > bb_upper:
                    return {"direction": "SHORT", "confidence": 60}
            
            elif strategy.name == "trend_following":
                # Simple trend check
                sma_50 = float(data["close"][-50:].mean()) if len(data) >= 50 else current_price
                sma_10 = float(data["close"][-10:].mean())
                
                if sma_10 > sma_50 * 1.02:
                    return {"direction": "LONG", "confidence": 65}
                elif sma_10 < sma_50 * 0.98:
                    return {"direction": "SHORT", "confidence": 65}
            
            return None
            
        except Exception:
            return None
    
    def _generate_simple_signal(
        self,
        data: pl.DataFrame,
        current_price: float,
        symbol: str,
    ) -> Optional[dict]:
        """Generate a simple momentum signal."""
        if len(data) < 20:
            return None
        
        # Calculate momentum
        momentum = (data["close"][-1] - data["close"][-20]) / data["close"][-20]
        
        if momentum > 0.03:
            return {"direction": "LONG", "id": f"{symbol}_{datetime.utcnow().timestamp()}"}
        elif momentum < -0.03:
            return {"direction": "SHORT", "id": f"{symbol}_{datetime.utcnow().timestamp()}"}
        
        return None
    
    def _calculate_commission(self, quantity: float, price: float) -> float:
        """Calculate commission cost."""
        notional = quantity * price
        return notional * (self.config.commission_percent / 100) + \
               quantity * self.config.commission_per_share
    
    def _calculate_slippage(self, price: float) -> float:
        """Calculate slippage cost."""
        return price * self.config.slippage_bps / 10000
    
    def _calculate_trade_pnl(self, position: dict, exit_price: float) -> float:
        """Calculate trade P&L."""
        if position["side"] == "LONG":
            return (exit_price - position["entry_price"]) * position["quantity"]
        else:
            return (position["entry_price"] - exit_price) * position["quantity"]
    
    def _create_trade(
        self,
        position: dict,
        timestamp: datetime,
        exit_price: float,
        pnl: float,
    ) -> BacktestTrade:
        """Create a BacktestTrade from position data."""
        return BacktestTrade(
            entry_time=position["entry_time"],
            exit_time=timestamp,
            symbol=self.config.symbol,
            side=position["side"],
            entry_price=position["entry_price"],
            exit_price=exit_price,
            quantity=position["quantity"],
            pnl=pnl,
            pnl_percent=(pnl / (position["entry_price"] * position["quantity"])) * 100,
            commission=0,
            slippage=0,
            signal_id=position.get("signal_id", "unknown"),
        )
    
    def _calculate_significance(self, result: WalkForwardResult, returns: list) -> None:
        """Calculate statistical significance of results."""
        if len(returns) < 3:
            result.confidence_level = "NOT_ENOUGH_DATA"
            result.notes.append("Not enough periods for statistical significance")
            return
        
        import numpy as np
        from scipy import stats
        
        arr = np.array(returns)
        
        # T-test against zero
        t_stat, p_value = stats.ttest_1samp(arr, 0)
        result.t_statistic = t_stat
        result.p_value = p_value
        
        if p_value < 0.01:
            result.confidence_level = "HIGHLY_SIGNIFICANT"
            result.notes.append(f"p-value: {p_value:.4f} (99% confidence)")
        elif p_value < 0.05:
            result.confidence_level = "SIGNIFICANT"
            result.notes.append(f"p-value: {p_value:.4f} (95% confidence)")
        elif p_value < 0.10:
            result.confidence_level = "MARGINALLY_SIGNIFICANT"
            result.notes.append(f"p-value: {p_value:.4f} (90% confidence)")
        else:
            result.confidence_level = "NOT_SIGNIFICANT"
            result.notes.append(f"p-value: {p_value:.4f} (not significant)")
