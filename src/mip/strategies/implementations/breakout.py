"""
Breakout strategy implementation.

Hypothesis: When price breaks above resistance or below support,
the move will continue in the breakout direction.
"""

from datetime import datetime
from typing import Any

import polars as pl
from ta.volatility import AverageTrueRange

from mip.core.models.signal import Signal, SignalDirection, SignalStatus, SignalType
from mip.strategies.base import BaseStrategy, StrategyResult


class BreakoutStrategy(BaseStrategy):
    """
    Breakout strategy using support/resistance detection.
    
    Parameters:
        lookback_period: Period to find swing highs/lows (default: 20)
        atr_multiplier: ATR multiplier for stop (default: 2.0)
        volume_multiplier: Volume must be this multiple of average (default: 1.5)
        min_breakout_pct: Minimum breakout percentage (default: 0.5%)
    """
    
    @property
    def name(self) -> str:
        return "breakout"
    
    @property
    def category(self) -> str:
        return "BREAKOUT"
    
    def _validate_parameters(self) -> None:
        """Validate strategy parameters."""
        lookback = self.params.get("lookback_period", 20)
        if lookback < 5:
            raise ValueError("lookback_period must be >= 5")
    
    async def calculate_indicators(self, data: pl.DataFrame) -> pl.DataFrame:
        """Calculate breakout indicators."""
        df = data.clone()
        
        lookback = self.params.get("lookback_period", 20)
        atr_mult = self.params.get("atr_multiplier", 2.0)
        
        # Rolling high/low for support/resistance
        df = df.with_columns(
            pl.col("high").rolling_max(lookback).alias("swing_high"),
            pl.col("low").rolling_min(lookback).alias("swing_low"),
        )
        
        # ATR for volatility
        atr = AverageTrueRange(df["high"], df["low"], df["close"])
        df = df.with_columns(
            pl.Series("atr", atr.average_true_range())
        )
        
        # Volume confirmation
        df = df.with_columns(
            pl.col("volume").rolling_mean(20).alias("avg_volume")
        )
        
        # Identify breakouts
        df = df.with_columns(
            (pl.col("close") > pl.col("swing_high").shift(1)).cast(pl.Int8).alias("bullish_breakout"),
            (pl.col("close") < pl.col("swing_low").shift(1)).cast(pl.Int8).alias("bearish_breakout"),
        )
        
        # Breakout strength
        df = df.with_columns(
            ((pl.col("close") - pl.col("swing_high").shift(1)) / pl.col("swing_high").shift(1) * 100)
            .alias("breakout_strength"),
        )
        
        return df
    
    async def generate_signals(
        self,
        data: pl.DataFrame,
        context: dict[str, Any]
    ) -> StrategyResult:
        """Generate breakout trading signals."""
        start_time = datetime.utcnow()
        signals = []
        errors = []
        
        try:
            df = await self.calculate_indicators(data)
            
            if len(df) < 50:
                errors.append("Insufficient data for breakout analysis")
                return StrategyResult(signals=[], errors=errors)
            
            latest = df.tail(1)
            prev = df.tail(2).head(1)
            
            close = latest["close"][0]
            atr = latest["atr"][0] if "atr" in latest else 0
            volume = latest["volume"][0] if "volume" in latest else 0
            avg_volume = latest["avg_volume"][0] if "avg_volume" in latest else 1
            swing_high = latest["swing_high"][0] if "swing_high" in latest else close
            swing_low = latest["swing_low"][0] if "swing_low" in latest else close
            breakout_strength = latest["breakout_strength"][0] if "breakout_strength" in latest else 0
            
            bullish_breakout = int(latest["bullish_breakout"][0]) if "bullish_breakout" in latest else 0
            bearish_breakout = int(latest["bearish_breakout"][0]) if "bearish_breakout" in latest else 0
            
            min_breakout = self.params.get("min_breakout_pct", 0.5)
            vol_mult = self.params.get("volume_multiplier", 1.5)
            
            symbol = context.get("symbol", "UNKNOWN")
            timeframe = context.get("timeframe", "1d")
            data_ts = latest["timestamp"][0]
            
            supporting_evidence = []
            contradicting_evidence = []
            
            # Bullish breakout
            if bullish_breakout and breakout_strength >= min_breakout:
                direction = SignalDirection.LONG
                signal_type = SignalType.ENTER_NOW
                
                supporting_evidence.append(f"Breakout strength: {breakout_strength:.2f}%")
                supporting_evidence.append(f"Above swing high: ${swing_high:.2f}")
                
                if volume >= avg_volume * vol_mult:
                    supporting_evidence.append(f"Volume confirming: {volume/avg_volume:.1f}x avg")
                else:
                    contradicting_evidence.append("Volume weak on breakout")
                
                stop_loss = swing_low - atr * 0.5
                take_profit = close + atr * 2
                confidence = min(40 + breakout_strength * 10, 85)
                
                if volume >= avg_volume * vol_mult:
                    confidence += 10
                
            # Bearish breakout
            elif bearish_breakout and breakout_strength >= min_breakout:
                direction = SignalDirection.SHORT
                signal_type = SignalType.ENTER_NOW
                
                supporting_evidence.append(f"Breakout strength: {abs(breakout_strength):.2f}%")
                supporting_evidence.append(f"Below swing low: ${swing_low:.2f}")
                
                if volume >= avg_volume * vol_mult:
                    supporting_evidence.append(f"Volume confirming: {volume/avg_volume:.1f}x avg")
                else:
                    contradicting_evidence.append("Volume weak on breakout")
                
                stop_loss = swing_high + atr * 0.5
                take_profit = close - atr * 2
                confidence = min(40 + abs(breakout_strength) * 10, 85)
                
                if volume >= avg_volume * vol_mult:
                    confidence += 10
                    
            # Near breakout - watch for confirmation
            elif close > swing_high * 0.98:
                direction = SignalDirection.LONG
                signal_type = SignalType.WATCH
                supporting_evidence.append(f"Near resistance: ${close:.2f} vs ${swing_high:.2f}")
                contradicting_evidence.append("Waiting for confirmed breakout")
                stop_loss = close * 0.97
                take_profit = close + atr * 2
                confidence = 40
                
            elif close < swing_low * 1.02:
                direction = SignalDirection.SHORT
                signal_type = SignalType.WATCH
                supporting_evidence.append(f"Near support: ${close:.2f} vs ${swing_low:.2f}")
                contradicting_evidence.append("Waiting for confirmed breakout")
                stop_loss = close * 1.03
                take_profit = close - atr * 2
                confidence = 40
                
            else:
                direction = SignalDirection.NEUTRAL
                signal_type = SignalType.NO_TRADE
                contradicting_evidence.append("No breakout detected")
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
            "lookback_period": [10, 15, 20, 30],
            "atr_multiplier": [1.5, 2.0, 2.5],
            "volume_multiplier": [1.0, 1.5, 2.0],
            "min_breakout_pct": [0.3, 0.5, 1.0],
        }
