"""
Volatility strategy implementation.

Hypothesis: Volatility contracts before expansion, and volatility
expansion tends to continue. Trade volatility breakouts.
"""

from datetime import datetime
from typing import Any

import polars as pl
from ta.volatility import BollingerBands, AverageTrueRange
from ta.momentum import RSIIndicator

from mip.core.models.signal import Signal, SignalDirection, SignalStatus, SignalType
from mip.strategies.base import BaseStrategy, StrategyResult


class VolatilityStrategy(BaseStrategy):
    """
    Volatility expansion strategy using Bollinger Band width.
    
    Parameters:
        bb_period: Bollinger Bands period (default: 20)
        bb_std: Number of standard deviations (default: 2.0)
        min_width_pct: Minimum bandwidth to trigger signal (default: 3.0)
        contraction_threshold: Bandwidth must be below this to trigger (default: 2.0)
    """
    
    @property
    def name(self) -> str:
        return "volatility"
    
    @property
    def category(self) -> str:
        return "VOLATILITY"
    
    def _validate_parameters(self) -> None:
        """Validate strategy parameters."""
        bb_period = self.params.get("bb_period", 20)
        if bb_period < 5:
            raise ValueError("bb_period must be >= 5")
    
    async def calculate_indicators(self, data: pl.DataFrame) -> pl.DataFrame:
        """Calculate volatility indicators."""
        df = data.clone()
        
        bb_period = self.params.get("bb_period", 20)
        bb_std = self.params.get("bb_std", 2.0)
        
        # Bollinger Bands
        bb = BollingerBands(df["close"], window=bb_period, window_dev=bb_std)
        df = df.with_columns(
            pl.Series("bb_upper", bb.bollinger_hband()),
            pl.Series("bb_middle", bb.bollinger_mavg()),
            pl.Series("bb_lower", bb.bollinger_lband()),
        )
        
        # Bandwidth (volatility measure)
        df = df.with_columns(
            ((pl.col("bb_upper") - pl.col("bb_lower")) / pl.col("bb_middle") * 100)
            .alias("bb_width")
        )
        
        # Rolling bandwidth for comparison
        df = df.with_columns(
            pl.col("bb_width").rolling_mean(20).alias("avg_width"),
            pl.col("bb_width").rolling_std(20).alias("width_std"),
        )
        
        # ATR for absolute volatility
        atr = AverageTrueRange(df["high"], df["low"], df["close"])
        df = df.with_columns(
            pl.Series("atr", atr.average_true_range())
        )
        
        # ATR as percentage of price
        df = df.with_columns(
            (pl.col("atr") / pl.col("close") * 100).alias("atr_pct")
        )
        
        # RSI for momentum confirmation
        rsi = RSIIndicator(df["close"])
        df = df.with_columns(
            pl.Series("rsi", rsi.rsi())
        )
        
        return df
    
    async def generate_signals(
        self,
        data: pl.DataFrame,
        context: dict[str, Any]
    ) -> StrategyResult:
        """Generate volatility-based trading signals."""
        start_time = datetime.utcnow()
        signals = []
        errors = []
        
        try:
            df = await self.calculate_indicators(data)
            
            if len(df) < 50:
                errors.append("Insufficient data for volatility analysis")
                return StrategyResult(signals=[], errors=errors)
            
            latest = df.tail(1)
            
            close = latest["close"][0]
            atr = latest["atr"][0] if "atr" in latest else 0
            atr_pct = latest["atr_pct"][0] if "atr_pct" in latest else 0
            bb_width = latest["bb_width"][0] if "bb_width" in latest else 0
            avg_width = latest["avg_width"][0] if "avg_width" in latest else 0
            rsi = latest["rsi"][0] if "rsi" in latest else 50
            
            symbol = context.get("symbol", "UNKNOWN")
            timeframe = context.get("timeframe", "1d")
            data_ts = latest["timestamp"][0]
            
            contraction_threshold = self.params.get("contraction_threshold", 2.0)
            min_width_pct = self.params.get("min_width_pct", 3.0)
            
            supporting_evidence = []
            contradicting_evidence = []
            
            # Detect volatility contraction
            is_contracting = bb_width < contraction_threshold
            was_contracting = avg_width < contraction_threshold
            
            # Detect volatility expansion
            is_expanding = bb_width > avg_width * 1.5
            expanding_rate = bb_width / avg_width if avg_width > 0 else 1
            
            # Previous bar was contracting, now expanding = breakout from compression
            if was_contracting and is_expanding:
                # Volatility breakout - trade in direction of momentum
                if rsi > 55:
                    direction = SignalDirection.LONG
                    signal_type = SignalType.ENTER_NOW
                    supporting_evidence.append(f"Volatility expansion after compression")
                    supporting_evidence.append(f"Width ratio: {expanding_rate:.2f}x")
                    supporting_evidence.append(f"RSI confirming: {rsi:.1f}")
                    contradicting_evidence.append(f"ATR%: {atr_pct:.2f}%")
                    stop_loss = close - atr * 2
                    take_profit = close + atr * 4
                    confidence = min(50 + expanding_rate * 15, 85)
                    
                elif rsi < 45:
                    direction = SignalDirection.SHORT
                    signal_type = SignalType.ENTER_NOW
                    supporting_evidence.append(f"Volatility expansion after compression")
                    supporting_evidence.append(f"Width ratio: {expanding_rate:.2f}x")
                    supporting_evidence.append(f"RSI confirming: {rsi:.1f}")
                    contradicting_evidence.append(f"ATR%: {atr_pct:.2f}%")
                    stop_loss = close + atr * 2
                    take_profit = close - atr * 4
                    confidence = min(50 + expanding_rate * 15, 85)
                    
                else:
                    # Low volatility - watch for direction
                    direction = SignalDirection.NEUTRAL
                    signal_type = SignalType.WATCH
                    supporting_evidence.append(f"Low volatility: width {bb_width:.2f}%")
                    contradicting_evidence.append("RSI neutral - waiting for direction")
                    stop_loss = None
                    take_profit = None
                    confidence = 30
                    
            # Currently in high volatility expansion
            elif is_expanding:
                if rsi > 60:
                    direction = SignalDirection.LONG
                    signal_type = SignalType.ENTER_NOW
                    supporting_evidence.append(f"High volatility: width {bb_width:.2f}%")
                    supporting_evidence.append(f"RSI bullish: {rsi:.1f}")
                    stop_loss = close - atr * 1.5
                    take_profit = close + atr * 3
                    confidence = 55
                    
                elif rsi < 40:
                    direction = SignalDirection.SHORT
                    signal_type = SignalType.ENTER_NOW
                    supporting_evidence.append(f"High volatility: width {bb_width:.2f}%")
                    supporting_evidence.append(f"RSI bearish: {rsi:.1f}")
                    stop_loss = close + atr * 1.5
                    take_profit = close - atr * 3
                    confidence = 55
                    
                else:
                    direction = SignalDirection.NEUTRAL
                    signal_type = SignalType.WATCH
                    supporting_evidence.append(f"High volatility expansion")
                    contradicting_evidence.append("RSI neutral")
                    stop_loss = None
                    take_profit = None
                    confidence = 35
                    
            # Low volatility - potential mean reversion
            elif bb_width < min_width_pct:
                direction = SignalDirection.NEUTRAL
                signal_type = SignalType.WATCH
                supporting_evidence.append(f"Very low volatility: {bb_width:.2f}%")
                supporting_evidence.append("Watch for expansion")
                contradicting_evidence.append("Waiting for volatility breakout")
                stop_loss = None
                take_profit = None
                confidence = 25
                
            else:
                direction = SignalDirection.NEUTRAL
                signal_type = SignalType.NO_TRADE
                contradicting_evidence.append(f"Normal volatility: {bb_width:.2f}%")
                stop_loss = None
                take_profit = None
                confidence = 0
            
            if direction != SignalDirection.NEUTRAL:
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
        
        return StrategyResult(
            signals=signals,
            metrics={"strategy": self.name, "data_points": len(data)},
            errors=errors,
            execution_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
        )
    
    def get_parameter_space(self) -> dict[str, list]:
        """Get parameter space for optimization."""
        return {
            "bb_period": [15, 20, 25],
            "bb_std": [1.5, 2.0, 2.5],
            "min_width_pct": [2.0, 3.0, 4.0],
            "contraction_threshold": [1.5, 2.0, 2.5],
        }
