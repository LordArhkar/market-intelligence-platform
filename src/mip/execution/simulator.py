"""
Paper trading simulator.

Simulates trade execution with realistic costs and fills.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import uuid4

from mip.core.config import get_settings
from mip.core.models.position import Position, Trade, PositionSide, PositionStatus
from mip.core.models.signal import Signal, SignalStatus
from mip.core.models.performance import PortfolioSnapshot


@dataclass
class SimulatorConfig:
    """Configuration for the paper trading simulator."""
    
    initial_capital: float = 100_000.0
    currency: str = "USD"
    
    # Commission rates
    equity_commission_per_share: float = 0.0
    equity_commission_percent: float = 0.0
    crypto_commission_percent: float = 0.1
    forex_commission_per_lot: float = 0.0
    
    # Slippage modeling
    default_slippage_bps: float = 10.0  # 10 basis points
    
    # Fill modeling
    use_market_orders: bool = True
    fill_at_next_bar: bool = True  # For EOD strategies


@dataclass
class SimulatedFill:
    """Represents a simulated trade fill."""
    
    symbol: str
    side: str
    quantity: float
    price: float
    commission: float
    slippage: float
    timestamp: datetime
    signal_id: str
    notes: str = ""


class PaperTradingSimulator:
    """
    Paper trading simulator with realistic execution modeling.
    
    Features:
    - Position tracking
    - P&L calculation
    - Commission and slippage modeling
    - Stop loss and take profit monitoring
    - Drawdown tracking
    """
    
    def __init__(self, config: Optional[SimulatorConfig] = None):
        self.config = config or SimulatorConfig()
        
        # Portfolio state
        self.cash = self.config.initial_capital
        self.initial_capital = self.config.initial_capital
        self.positions: dict[str, Position] = {}
        self.trades: list[Trade] = []
        self.fills: list[SimulatedFill] = []
        
        # Performance tracking
        self.peak_equity = self.initial_capital
        self.max_drawdown = 0.0
        self.daily_pnl = 0.0
        self.weekly_pnl = 0.0
        
        # Statistics
        self.total_commission = 0.0
        self.total_slippage = 0.0
        self.winning_trades = 0
        self.losing_trades = 0
        self.consecutive_losses = 0
    
    def execute_signal(
        self,
        signal: Signal,
        current_price: float,
        timestamp: Optional[datetime] = None
    ) -> tuple[bool, str]:
        """
        Execute a trading signal.
        
        Returns (success, message)
        """
        ts = timestamp or datetime.utcnow()
        
        # Check if we have an existing position
        if signal.symbol in self.positions:
            position = self.positions[signal.symbol]
            
            # Check if we should close existing position
            if signal.entry_type.value in ["EXIT", "REDUCE"]:
                return self.close_position(
                    signal.symbol,
                    current_price,
                    signal.direction.value,
                    ts,
                    signal.id
                )
            
            # Already have position in same direction
            if position.side.value == signal.direction.value:
                return True, "Position already exists in same direction"
            
            # Close and reverse
            success, msg = self.close_position(
                signal.symbol,
                current_price,
                signal.direction.value,
                ts,
                signal.id
            )
            if not success:
                return False, msg
        
        # Calculate position size
        stop_loss = signal.stop_loss or self._estimate_stop(signal, current_price)
        
        # Risk per share
        if signal.direction.value == "LONG":
            risk_per_share = current_price - stop_loss
        else:
            risk_per_share = stop_loss - current_price
        
        if risk_per_share <= 0:
            return False, "Invalid risk calculation"
        
        # Position dollar risk
        risk_dollars = self.cash * signal.position_risk_percent / 100
        
        # Shares to trade
        shares = risk_dollars / risk_per_share
        
        if shares < 1:
            return False, "Position size too small"
        
        # Calculate costs
        slippage = self._calculate_slippage(current_price, signal.asset_class)
        commission = self._calculate_commission(
            shares,
            current_price,
            signal.asset_class
        )
        
        total_cost = shares * current_price + commission + slippage
        
        if total_cost > self.cash:
            return False, f"Insufficient cash: need ${total_cost:.2f}, have ${self.cash:.2f}"
        
        # Create position
        position = Position(
            id=str(uuid4()),
            symbol=signal.symbol,
            asset_class=signal.asset_class,
            side=PositionSide(signal.direction.value),
            quantity=shares,
            average_entry_price=current_price,
            current_price=current_price,
            status=PositionStatus.OPEN,
            stop_loss=stop_loss,
            take_profit=signal.take_profit_1,
            position_risk_percent=signal.position_risk_percent,
            strategy_name=signal.strategy_name,
            strategy_version=signal.strategy_version,
            entry_signal_id=signal.id,
            entry_time=ts,
        )
        
        # Create entry trade
        trade = Trade(
            id=str(uuid4()),
            position_id=position.id,
            symbol=signal.symbol,
            side=PositionSide(signal.direction.value),
            quantity=shares,
            price=current_price,
            commission=commission,
            slippage=slippage,
            executed_at=ts,
            signal_id=signal.id,
            execution_source="SIMULATOR",
        )
        
        # Update state
        self.cash -= total_cost
        self.positions[signal.symbol] = position
        self.trades.append(trade)
        self.total_commission += commission
        self.total_slippage += slippage
        
        # Record fill
        self.fills.append(SimulatedFill(
            symbol=signal.symbol,
            side=signal.direction.value,
            quantity=shares,
            price=current_price,
            commission=commission,
            slippage=slippage,
            timestamp=ts,
            signal_id=signal.id,
            notes=f"Entry: {signal.strategy_name}"
        ))
        
        signal.update_status(SignalStatus.ENTERED)
        
        return True, f"Entered {signal.direction.value} {shares:.0f} {signal.symbol} @ ${current_price:.2f}"
    
    def close_position(
        self,
        symbol: str,
        current_price: float,
        reason: str,
        timestamp: Optional[datetime] = None,
        signal_id: Optional[str] = None
    ) -> tuple[bool, str]:
        """Close an existing position."""
        ts = timestamp or datetime.utcnow()
        
        if symbol not in self.positions:
            return False, f"No position in {symbol}"
        
        position = self.positions[symbol]
        
        # Calculate costs
        slippage = self._calculate_slippage(current_price, position.asset_class)
        commission = self._calculate_commission(
            position.quantity,
            current_price,
            position.asset_class
        )
        
        # Calculate P&L
        if position.is_long:
            pnl = (current_price - position.average_entry_price) * position.quantity
        else:
            pnl = (position.average_entry_price - current_price) * position.quantity
        
        pnl -= commission + slippage
        
        # Create exit trade
        trade = Trade(
            id=str(uuid4()),
            position_id=position.id,
            symbol=symbol,
            side=PositionSide.SHORT if position.is_long else PositionSide.LONG,  # Exit opposite of entry
            quantity=position.quantity,
            price=current_price,
            commission=commission,
            slippage=slippage,
            executed_at=ts,
            signal_id=signal_id,
            execution_source="SIMULATOR",
        )
        
        # Update state
        position.current_price = current_price
        position.realized_pnl = pnl
        position.exit_time = ts
        position.exit_trade_id = trade.id
        position.exit_reason = reason
        position.status = PositionStatus.CLOSED
        
        # Return cash
        self.cash += position.quantity * current_price - commission - slippage
        self.positions.pop(symbol)
        self.trades.append(trade)
        self.total_commission += commission
        self.total_slippage += slippage
        
        # Update statistics
        if pnl > 0:
            self.winning_trades += 1
            self.consecutive_losses = 0
        else:
            self.losing_trades += 1
            self.consecutive_losses += 1
        
        self.daily_pnl += pnl
        
        # Record fill
        self.fills.append(SimulatedFill(
            symbol=symbol,
            side="CLOSE",
            quantity=position.quantity,
            price=current_price,
            commission=commission,
            slippage=slippage,
            timestamp=ts,
            signal_id=signal_id or "",
            notes=f"Exit: {reason}, P&L: ${pnl:.2f}"
        ))
        
        return True, f"Closed {symbol} @ ${current_price:.2f}, P&L: ${pnl:.2f}"
    
    def update_prices(self, prices: dict[str, float], timestamp: Optional[datetime] = None) -> list[str]:
        """
        Update prices and check for stop/take profit hits.
        
        Returns list of triggered events.
        """
        ts = timestamp or datetime.utcnow()
        events = []
        
        for symbol, price in prices.items():
            if symbol not in self.positions:
                continue
            
            position = self.positions[symbol]
            position.current_price = price
            
            # Check stop loss
            if position.check_stop_loss(price):
                success, msg = self.close_position(
                    symbol, price, "STOP_LOSS", ts
                )
                events.append(msg)
                continue
            
            # Check take profit
            if position.check_take_profit(price):
                success, msg = self.close_position(
                    symbol, price, "TAKE_PROFIT", ts
                )
                events.append(msg)
                continue
        
        # Update equity and drawdown
        self._update_equity()
        
        return events
    
    def _update_equity(self) -> None:
        """Update equity and drawdown calculations."""
        positions_value = sum(
            pos.current_price * pos.quantity
            for pos in self.positions.values()
        )
        
        equity = self.cash + positions_value
        
        # Update peak and drawdown
        if equity > self.peak_equity:
            self.peak_equity = equity
        
        drawdown = (self.peak_equity - equity) / self.peak_equity * 100
        self.max_drawdown = max(self.max_drawdown, drawdown)
    
    def _estimate_stop(
        self,
        signal: Signal,
        current_price: float
    ) -> float:
        """Estimate a stop loss based on direction."""
        stop_pct = 0.02  # Default 2%
        
        if signal.direction.value == "LONG":
            return current_price * (1 - stop_pct)
        else:
            return current_price * (1 + stop_pct)
    
    def _calculate_slippage(
        self,
        price: float,
        asset_class: str
    ) -> float:
        """Calculate expected slippage."""
        # Higher slippage for less liquid assets
        slippage_multipliers = {
            "US_EQUITY": 1.0,
            "CRYPTO": 1.5,
            "FOREX": 0.5,
            "INDEX": 1.0,
        }
        
        multiplier = slippage_multipliers.get(asset_class, 1.0)
        bps = self.config.default_slippage_bps * multiplier
        
        return price * bps / 10000
    
    def _calculate_commission(
        self,
        quantity: float,
        price: float,
        asset_class: str
    ) -> float:
        """Calculate expected commission."""
        notional = quantity * price
        
        if asset_class == "CRYPTO":
            return notional * self.config.crypto_commission_percent / 100
        else:
            # Equity: per share + percentage
            per_share = self.config.equity_commission_per_share * quantity
            percent = notional * self.config.equity_commission_percent / 100
            return per_share + percent
    
    def get_portfolio_snapshot(self) -> PortfolioSnapshot:
        """Get current portfolio state."""
        positions_value = sum(
            pos.current_price * pos.quantity
            for pos in self.positions.values()
        )
        
        unrealized_pnl = sum(
            pos.unrealized_pnl for pos in self.positions.values()
        )
        
        return PortfolioSnapshot(
            timestamp=datetime.utcnow(),
            total_equity=self.cash + positions_value,
            cash=self.cash,
            positions_value=positions_value,
            positions=[
                {
                    "symbol": pos.symbol,
                    "quantity": pos.quantity,
                    "entry_price": pos.average_entry_price,
                    "current_price": pos.current_price,
                    "pnl": pos.unrealized_pnl,
                    "side": pos.side.value,
                }
                for pos in self.positions.values()
            ],
            unrealized_pnl=unrealized_pnl,
            pending_signals=0,
            active_signals=len(self.positions),
            risk_utilization=sum(
                pos.position_risk_percent for pos in self.positions.values()
            ),
            exposure_utilization=positions_value / (self.cash + positions_value) * 100,
            today_pnl=self.daily_pnl,
        )
    
    def get_summary(self) -> dict:
        """Get trading summary."""
        total_trades = self.winning_trades + self.losing_trades
        
        return {
            "initial_capital": self.initial_capital,
            "current_equity": self.cash + sum(
                pos.current_price * pos.quantity
                for pos in self.positions.values()
            ),
            "cash": self.cash,
            "open_positions": len(self.positions),
            "total_trades": total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.winning_trades / total_trades if total_trades > 0 else 0,
            "total_commission": self.total_commission,
            "total_slippage": self.total_slippage,
            "max_drawdown": self.max_drawdown,
            "daily_pnl": self.daily_pnl,
        }
    
    def reset(self) -> None:
        """Reset simulator to initial state."""
        self.cash = self.config.initial_capital
        self.positions.clear()
        self.trades.clear()
        self.fills.clear()
        self.peak_equity = self.config.initial_capital
        self.max_drawdown = 0.0
        self.daily_pnl = 0.0
        self.weekly_pnl = 0.0
        self.total_commission = 0.0
        self.total_slippage = 0.0
        self.winning_trades = 0
        self.losing_trades = 0
        self.consecutive_losses = 0
