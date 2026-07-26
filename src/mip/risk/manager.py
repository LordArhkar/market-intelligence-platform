"""
Risk management engine.

Enforces risk limits and validates all trading decisions.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from mip.core.models.signal import Signal
from mip.core.models.position import Position
from mip.risk.config import RiskLimits, RiskMetrics


@dataclass
class RiskCheckResult:
    """Result of a risk check."""
    
    approved: bool
    reason: str
    risk_score: float = 0.0  # 0-100, higher = riskier
    warnings: list[str] = None
    adjustments: dict = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.adjustments is None:
            self.adjustments = {}


class RiskManager:
    """
    Risk management engine that validates trading decisions.
    
    The Risk Management Agent has final veto authority over all trades.
    """
    
    def __init__(self, limits: Optional[RiskLimits] = None):
        self.limits = limits or RiskLimits()
        self.metrics = RiskMetrics(portfolio_value=100_000, cash=100_000)
        self._approval_history = []
    
    def update_metrics(self, metrics: RiskMetrics) -> None:
        """Update current risk metrics."""
        self.metrics = metrics
    
    def check_signal(self, signal: Signal, current_price: float) -> RiskCheckResult:
        """
        Check if a signal passes risk management.
        
        This is the primary entry point for signal validation.
        """
        warnings = []
        adjustments = {}
        risk_score = 0.0
        
        # Check 1: Signal validity
        if signal.expires_at and datetime.utcnow() > signal.expires_at:
            return RiskCheckResult(
                approved=False,
                reason="Signal has expired",
                risk_score=100.0
            )
        
        # Check 2: Position risk
        if signal.position_risk_percent > self.limits.max_position_risk_percent:
            risk_score += 20
            if not self.limits.allow_limit_override:
                return RiskCheckResult(
                    approved=False,
                    reason=f"Position risk {signal.position_risk_percent}% exceeds limit {self.limits.max_position_risk_percent}%",
                    risk_score=risk_score,
                    warnings=["Position size too large"]
                )
            else:
                warnings.append(f"Position risk adjusted from {signal.position_risk_percent}% to limit")
                signal.position_risk_percent = self.limits.max_position_risk_percent
                adjustments["position_risk"] = self.limits.max_position_risk_percent
        
        # Check 3: Portfolio risk
        projected_risk = self.metrics.current_risk_percent + signal.position_risk_percent
        if projected_risk > self.limits.max_portfolio_risk_percent:
            risk_score += 30
            return RiskCheckResult(
                approved=False,
                reason=f"Portfolio risk would exceed limit: {projected_risk:.1f}% > {self.limits.max_portfolio_risk_percent}%",
                risk_score=risk_score,
                warnings=[f"Current portfolio risk: {self.metrics.current_risk_percent:.1f}%"]
            )
        
        # Check 4: Stop loss
        if signal.stop_loss is None and signal.direction.value == "LONG":
            risk_score += 10
            warnings.append("No stop loss defined - adding 2% stop")
            signal.stop_loss = current_price * 0.98
        elif signal.stop_loss is None and signal.direction.value == "SHORT":
            risk_score += 10
            warnings.append("No stop loss defined - adding 2% stop")
            signal.stop_loss = current_price * 1.02
        
        # Check 5: Drawdown limit
        if self.metrics.current_drawdown > self.limits.max_drawdown_percent * 0.8:
            risk_score += 25
            warnings.append(f"Approaching max drawdown: {self.metrics.current_drawdown:.1f}%")
            
            if self.metrics.current_drawdown >= self.limits.max_drawdown_percent:
                return RiskCheckResult(
                    approved=False,
                    reason=f"Max drawdown limit reached: {self.metrics.current_drawdown:.1f}% >= {self.limits.max_drawdown_percent}%",
                    risk_score=100.0
                )
        
        # Check 6: Daily loss limit
        if self.metrics.daily_pnl < -self.limits.max_daily_loss_percent * self.metrics.portfolio_value / 100:
            risk_score += 30
            return RiskCheckResult(
                approved=False,
                reason=f"Daily loss limit reached: ${self.metrics.daily_pnl:.2f}",
                risk_score=risk_score
            )
        
        # Check 7: Leverage
        new_leverage = self.metrics.leverage + (signal.position_risk_percent / 100)
        if new_leverage > self.limits.max_leverage:
            risk_score += 15
            return RiskCheckResult(
                approved=False,
                reason=f"Leverage would exceed limit: {new_leverage:.2f}x > {self.limits.max_leverage}x",
                risk_score=risk_score
            )
        
        # Check 8: Short selling
        if signal.direction.value == "SHORT" and not self.limits.allow_short_positions:
            return RiskCheckResult(
                approved=False,
                reason="Short selling not allowed",
                risk_score=50.0
            )
        
        # Check 9: Minimum capital
        position_value = self.metrics.portfolio_value * signal.position_risk_percent / 100
        if position_value < self.limits.min_capital_per_trade:
            return RiskCheckResult(
                approved=False,
                reason=f"Position size ${position_value:.2f} below minimum ${self.limits.min_capital_per_trade}",
                risk_score=20.0
            )
        
        # Check 10: Correlation
        if self._would_exceed_correlation(signal):
            risk_score += 20
            warnings.append("High correlation with existing positions")
        
        # Check 11: Martingale detection
        if self.limits.allow_martingale is False and self._is_martingale_pattern(signal):
            return RiskCheckResult(
                approved=False,
                reason="Martingale position sizing detected and not allowed",
                risk_score=80.0
            )
        
        return RiskCheckResult(
            approved=True,
            reason="Signal approved by risk management",
            risk_score=risk_score,
            warnings=warnings,
            adjustments=adjustments
        )
    
    def check_position_sizing(
        self,
        signal: Signal,
        current_price: float,
        stop_price: float
    ) -> float:
        """
        Calculate appropriate position size based on risk limits.
        
        Returns the dollar amount to risk on this trade.
        """
        # Risk per trade in dollars
        risk_dollars = self.metrics.portfolio_value * signal.position_risk_percent / 100
        
        # Risk per share
        risk_per_share = abs(current_price - stop_price)
        
        if risk_per_share == 0:
            return 0
        
        # Calculate shares
        shares = risk_dollars / risk_per_share
        
        # Apply portfolio risk limit
        total_portfolio_risk = self.metrics.current_risk_percent + signal.position_risk_percent
        if total_portfolio_risk > self.limits.max_portfolio_risk_percent:
            # Scale down to fit limit
            available_risk = self.limits.max_portfolio_risk_percent - self.metrics.current_risk_percent
            risk_dollars = self.metrics.portfolio_value * available_risk / 100
            shares = risk_dollars / risk_per_share
        
        # Apply single position limit
        max_position_value = self.metrics.portfolio_value * self.limits.max_single_position_percent / 100
        position_value = shares * current_price
        if position_value > max_position_value:
            shares = max_position_value / current_price
            risk_dollars = shares * risk_per_share
        
        return shares
    
    def calculate_stop_loss(
        self,
        entry_price: float,
        direction: str,
        atr: Optional[float] = None
    ) -> float:
        """
        Calculate appropriate stop loss based on volatility.
        """
        if atr is not None:
            atr_multiplier = self.limits.max_position_risk_percent / 100 * 50
            stop_distance = atr * atr_multiplier
        else:
            stop_distance = entry_price * self.limits.max_position_risk_percent / 100
        
        if direction == "LONG":
            return entry_price - stop_distance
        else:
            return entry_price + stop_distance
    
    def _would_exceed_correlation(self, signal: Signal) -> bool:
        """Check if adding this signal would exceed correlation limits."""
        # Simplified check - in production would use actual correlation data
        return False
    
    def _is_martingale_pattern(self, signal: Signal) -> bool:
        """Detect potential martingale position sizing."""
        # Check if recent losses would suggest doubling down
        if self.metrics.consecutive_losses >= 3:
            # Would need more sophisticated check
            return False
        return False
    
    def get_portfolio_risk_status(self) -> dict:
        """Get current portfolio risk status."""
        return {
            "portfolio_value": self.metrics.portfolio_value,
            "cash": self.metrics.cash,
            "current_risk_percent": self.metrics.current_risk_percent,
            "leverage": self.metrics.leverage,
            "exposure_percent": self.metrics.exposure_percent,
            "daily_pnl": self.metrics.daily_pnl,
            "current_drawdown": self.metrics.current_drawdown,
            "max_drawdown": self.metrics.max_drawdown,
            "consecutive_losses": self.metrics.consecutive_losses,
            "limits": {
                "max_portfolio_risk": self.limits.max_portfolio_risk_percent,
                "max_leverage": self.limits.max_leverage,
                "max_drawdown": self.limits.max_drawdown_percent,
                "max_daily_loss": self.limits.max_daily_loss_percent,
            }
        }
    
    def record_approval(self, signal_id: str, approved: bool, result: RiskCheckResult) -> None:
        """Record approval decision for audit trail."""
        self._approval_history.append({
            "timestamp": datetime.utcnow(),
            "signal_id": signal_id,
            "approved": approved,
            "risk_score": result.risk_score,
            "reason": result.reason,
        })
    
    def get_approval_history(self, limit: int = 100) -> list[dict]:
        """Get recent approval history."""
        return self._approval_history[-limit:]
