"""
Momentum strategy implementation.

Hypothesis: Assets that have performed well will continue to perform well
in the near term, and vice versa for poorly performing assets.
"""

from datetime import datetime
from typing import Any

import polars as pl
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import MACD
from ta.trend import SMAIndicator as SMA

from mip.core.models.signal import Signal, SignalDirection, SignalStatus, SignalType
from mip.strategies.base import BaseStrategy, StrategyResult


class MomentumStrategy(BaseStrategy):
    """
    Cross-sectional momentum strategy.
    
    Parameters:
        lookback_period: Number of periods for momentum calculation (default: 20)
        rsi_oversold: RSI threshold for oversold (default: 30)
        rsi_overbought: RSI threshold for overbought (default: 70)
        min_momentum: Minimum momentum score to enter (default: 0.02)
        confirmation_bars: Number of bars to confirm signal (default: 1)
    """
    
    @property
    def name(self) -> str:
        return "momentum"
    
    @property
    def category(self) -> str:
        return "MOMENTUM"
    
    def _validate_parameters(self) -> None:
        """Validate strategy parameters."""
        if self.params.get("lookback_period", 20) < 5:
            raise ValueError("lookback_period must be >= 5")
        if self.params.get("rsi_oversold", 30) >= self.params.get("rsi_overbought", 70):
            raise ValueError("rsi_oversold must be < rsi_overbought")
    
    async def calculate_indicators(
        self,
        data: pl.DataFrame
    ) -> pl.DataFrame:
        """Calculate momentum indicators."""
        df = data.clone()
        
        lookback = self.params.get("lookback_period", 20)
        rsi_period = self.params.get("rsi_period", 14)
        
        # Price momentum (rate of change)
        df = df.with_columns(
            (pl.col("close") / pl.col("close").shift(lookback) - 1)
            .alias("momentum")
        )
        
        # RSI
        rsi = RSIIndicator(df["close"], window=rsi_period)
        df = df.with_columns(
            pl.Series("rsi", rsi.rsi())
        )
        
        # Stochastic
        stoch = StochasticOscillator(
            df["high"],
            df["low"],
            df["close"],
            window=14,
            smooth_window=3
        )
        df = df.with_columns(
            pl.Series("stoch_k", stoch.stoch()),
            pl.Series("stoch_d", stoch.stoch_signal())
        )
        
        # Moving averages for trend
        df = df.with_columns(
            pl.Series("sma_20", SMA(df["close"], window=20)),
            pl.Series("sma_50", SMA(df["close"], window=50)),
        )
        
        # Relative strength vs market (if multiple assets available)
        # This would be cross-sectional in a full implementation
        
        return df
    
    async def generate_signals(
        self,
        data: pl.DataFrame,
        context: dict[str, Any]
    ) -> StrategyResult:
        """Generate momentum-based trading signals."""
        start_time = datetime.utcnow()
        signals = []
        errors = []
        
        try:
            # Calculate indicators
            df = await self.calculate_indicators(data)
            
            if len(df) < 50:
                errors.append("Insufficient data for momentum analysis")
                return StrategyResult(
                    signals=[],
                    errors=errors,
                    execution_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                )
            
            # Get latest values
            latest = df.tail(1)
            prev = df.tail(2).head(1)
            
            lookback = self.params.get("lookback_period", 20)
            min_momentum = self.params.get("min_momentum", 0.02)
            rsi_oversold = self.params.get("rsi_oversold", 30)
            rsi_overbought = self.params.get("rsi_overbought", 70)
            
            momentum = latest["momentum"][0] if "momentum" in latest else 0.0
            rsi = latest["rsi"][0] if "rsi" in latest else 50.0
            close = latest["close"][0]
            high = latest["high"][0]
            low = latest["low"][0]
            volume = latest["volume"][0] if "volume" in latest else 0
            
            # Get average volume for comparison
            avg_volume = df.tail(20)["volume"].mean() if "volume" in df else 1
            
            symbol = context.get("symbol", "UNKNOWN")
            timeframe = context.get("timeframe", "1d")
            data_ts = latest["timestamp"][0]
            
            # Strategy logic
            supporting_evidence = []
            contradicting_evidence = []
            
            # Bullish conditions
            bullish = (
                momentum > min_momentum and
                rsi < rsi_overbought and
                volume > avg_volume * 0.8
            )
            
            # Bearish conditions
            bearish = (
                momentum < -min_momentum and
                rsi > rsi_oversold and
                volume > avg_volume * 0.8
            )
            
            if bullish:
                direction = SignalDirection.LONG
                supporting_evidence.append(f"Positive momentum: {momentum:.2%}")
                supporting_evidence.append(f"RSI: {rsi:.1f} (not overbought)")
                supporting_evidence.append(f"Volume confirming: {volume/avg_volume:.1f}x avg")
                
                if momentum > 0.05:
                    signal_type = SignalType.ENTER_NOW
                else:
                    signal_type = SignalType.WATCH
                    
            elif bearish:
                direction = SignalDirection.SHORT
                supporting_evidence.append(f"Negative momentum: {momentum:.2%}")
                supporting_evidence.append(f"RSI: {rsi:.1f} (not oversold)")
                supporting_evidence.append(f"Volume confirming: {volume/avg_volume:.1f}x avg")
                
                if momentum < -0.05:
                    signal_type = SignalType.ENTER_NOW
                else:
                    signal_type = SignalType.WATCH
            else:
                direction = SignalDirection.NEUTRAL
                signal_type = SignalType.NO_TRADE
                contradicting_evidence.append(f"Momentum: {momentum:.2%} (below threshold)")
                contradicting_evidence.append(f"RSI: {rsi:.1f}")
            
            # Calculate stop loss and take profit
            atr = self._calculate_atr(df.tail(14))
            stop_loss_pct = self.params.get("stop_loss_pct", 0.02)
            
            if direction == SignalDirection.LONG:
                stop_loss = close * (1 - stop_loss_pct)
                take_profit = close * (1 + stop_loss_pct * 2)  # 2:1 R:R
            elif direction == SignalDirection.SHORT:
                stop_loss = close * (1 + stop_loss_pct)
                take_profit = close * (1 - stop_loss_pct * 2)
            else:
                stop_loss = None
                take_profit = None
            
            # Only create signal if there's a directional view
            if direction != SignalDirection.NEUTRAL:
                # Calculate confidence
                confidence = self._calculate_confidence(
                    momentum=momentum,
                    rsi=rsi,
                    volume_ratio=volume/avg_volume if avg_volume > 0 else 1,
                    min_momentum=min_momentum,
                )
                
                signal = Signal(
                    symbol=symbol,
                    asset_class=context.get("asset_class", "UNKNOWN"),
                    direction=direction,
                    strategy_name=self.name,
                    strategy_version=self.version,
                    market_regime=context.get("regime", "UNKNOWN"),
                    timeframe=timeframe,
                    entry_type=signal_type,
                    entry_price=close,
                    stop_loss=stop_loss,
                    take_profit_1=take_profit,
                    position_risk_percent=self.params.get("position_risk", 1.0),
                    expected_reward_risk=2.0,
                    confidence=confidence,
                    supporting_evidence=supporting_evidence,
                    contradicting_evidence=contradicting_evidence,
                    status=SignalStatus.PENDING,
                    data_timestamp=data_ts,
                    source=f"{self.name}_strategy",
                )
                signals.append(signal)
            
        except Exception as e:
            errors.append(f"Signal generation error: {str(e)}")
        
        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return StrategyResult(
            signals=signals,
            metrics={
                "strategy": self.name,
                "data_points": len(data),
            },
            errors=errors,
            execution_time_ms=execution_time,
        )
    
    def _calculate_atr(self, data: pl.DataFrame) -> float:
        """Calculate Average True Range."""
        if len(data) < 2:
            return 0.0
        
        high = data["high"]
        low = data["low"]
        prev_close = data["close"].shift(1)
        
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        
        tr = pl.concat([tr1, tr2, tr3], how="horizontal").max(axis=1)
        return tr.mean()
    
    def _calculate_confidence(
        self,
        momentum: float,
        rsi: float,
        volume_ratio: float,
        min_momentum: float,
    ) -> float:
        """Calculate signal confidence score (0-100)."""
        confidence = 50.0  # Base
        
        # Momentum contribution (up to 25 points)
        momentum_score = min(abs(momentum) / 0.1, 1.0) * 25
        confidence += momentum_score if momentum > 0 else -momentum_score * 0.5
        
        # RSI contribution (up to 15 points)
        if 40 <= rsi <= 60:
            confidence += 15  # Neutral zone - no extreme
        elif 30 <= rsi <= 70:
            confidence += 10
        else:
            confidence -= 10  # Too extreme
        
        # Volume contribution (up to 10 points)
        if volume_ratio >= 1.5:
            confidence += 10
        elif volume_ratio >= 1.0:
            confidence += 5
        
        return max(0, min(100, confidence))
    
    def get_parameter_space(self) -> dict[str, list]:
        """Get parameter space for optimization."""
        return {
            "lookback_period": [10, 15, 20, 30],
            "rsi_oversold": [25, 30, 35],
            "rsi_overbought": [65, 70, 75],
            "min_momentum": [0.01, 0.02, 0.03, 0.05],
            "stop_loss_pct": [0.015, 0.02, 0.025],
        }
