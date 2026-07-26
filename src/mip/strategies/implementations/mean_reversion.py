"""
Mean reversion strategy implementation.

Hypothesis: Prices that deviate significantly from their mean will
eventually revert to the mean.
"""

from datetime import datetime
from typing import Any

import polars as pl
from ta.volatility import BollingerBands, AverageTrueRange

from mip.core.models.signal import Signal, SignalDirection, SignalStatus, SignalType
from mip.strategies.base import BaseStrategy, StrategyResult


class MeanReversionStrategy(BaseStrategy):
    """
    Mean reversion strategy using Bollinger Bands.
    
    Parameters:
        bb_period: Bollinger Bands period (default: 20)
        bb_std: Number of standard deviations (default: 2.0)
        entry_threshold: Z-score threshold for entry (default: 2.0)
        exit_threshold: Z-score threshold for exit (default: 0.5)
        lookback_period: Period for mean calculation (default: 50)
    """
    
    @property
    def name(self) -> str:
        return "mean_reversion"
    
    @property
    def category(self) -> str:
        return "MEAN_REVERSION"
    
    def _validate_parameters(self) -> None:
        """Validate strategy parameters."""
        bb_std = self.params.get("bb_std", 2.0)
        if bb_std < 0.5 or bb_std > 4.0:
            raise ValueError("bb_std must be between 0.5 and 4.0")
        
        entry = self.params.get("entry_threshold", 2.0)
        if entry < 1.0 or entry > 4.0:
            raise ValueError("entry_threshold must be between 1.0 and 4.0")
    
    async def calculate_indicators(
        self,
        data: pl.DataFrame
    ) -> pl.DataFrame:
        """Calculate mean reversion indicators."""
        df = data.clone()
        
        bb_period = self.params.get("bb_period", 20)
        bb_std = self.params.get("bb_std", 2.0)
        lookback = self.params.get("lookback_period", 50)
        
        # Bollinger Bands
        bb = BollingerBands(df["close"], window=bb_period, window_dev=bb_std)
        df = df.with_columns(
            pl.Series("bb_upper", bb.bollinger_hband()),
            pl.Series("bb_middle", bb.bollinger_mavg()),
            pl.Series("bb_lower", bb.bollinger_lband()),
        )
        
        # Calculate Z-score of price vs mean
        rolling_mean = df["close"].rolling_mean(lookback)
        rolling_std = df["close"].rolling_std(lookback)
        
        df = df.with_columns(
            (pl.col("close") - rolling_mean)
            .alias("z_score")
        )
        df = df.with_columns(
            (pl.col("z_score") / rolling_std.replace(0, 1))
            .alias("z_score_normalized")
        )
        
        # ATR for stops
        atr = AverageTrueRange(df["high"], df["low"], df["close"])
        df = df.with_columns(
            pl.Series("atr", atr.average_true_range())
        )
        
        # Position from mean
        df = df.with_columns(
            ((pl.col("close") - pl.col("bb_middle")) / pl.col("bb_upper"))
            .alias("deviation_from_mean")
        )
        
        return df
    
    async def generate_signals(
        self,
        data: pl.DataFrame,
        context: dict[str, Any]
    ) -> StrategyResult:
        """Generate mean reversion trading signals."""
        start_time = datetime.utcnow()
        signals = []
        errors = []
        
        try:
            # Calculate indicators
            df = await self.calculate_indicators(data)
            
            if len(df) < 60:
                errors.append("Insufficient data for mean reversion analysis")
                return StrategyResult(
                    signals=[],
                    errors=errors,
                    execution_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                )
            
            # Get latest values
            latest = df.tail(1)
            
            bb_period = self.params.get("bb_period", 20)
            entry_threshold = self.params.get("entry_threshold", 2.0)
            
            z_score = latest["z_score_normalized"][0] if "z_score_normalized" in latest else 0.0
            bb_upper = latest["bb_upper"][0] if "bb_upper" in latest else 0.0
            bb_middle = latest["bb_middle"][0] if "bb_middle" in latest else 0.0
            bb_lower = latest["bb_lower"][0] if "bb_lower" in latest else 0.0
            close = latest["close"][0]
            atr = latest["atr"][0] if "atr" in latest else 0.0
            volume = latest["volume"][0] if "volume" in latest else 0
            
            symbol = context.get("symbol", "UNKNOWN")
            timeframe = context.get("timeframe", "1d")
            data_ts = latest["timestamp"][0]
            
            # Calculate average volume
            avg_volume = df.tail(20)["volume"].mean() if "volume" in df else 1
            
            # Strategy logic
            supporting_evidence = []
            contradicting_evidence = []
            
            # Mean reversion signals
            # Long when price is below lower band (oversold)
            # Short when price is above upper band (overbought)
            
            if close <= bb_lower:
                # Price at or below lower band - oversold, expect bounce
                direction = SignalDirection.LONG
                signal_type = SignalType.ENTER_NOW
                
                # Check if this is an extreme move
                z_magnitude = abs(z_score)
                if z_magnitude > 3:
                    signal_type = SignalType.WATCH  # Too extreme, wait for confirmation
                
                supporting_evidence.append(f"Price at lower BB: ${close:.2f} vs ${bb_lower:.2f}")
                supporting_evidence.append(f"Z-score: {z_score:.2f}")
                supporting_evidence.append(f"Deviation: {latest['deviation_from_mean'][0]:.2%}")
                
                if volume > avg_volume:
                    supporting_evidence.append(f"Volume spike: {volume/avg_volume:.1f}x avg")
                else:
                    contradicting_evidence.append("Volume not confirming")
                
            elif close >= bb_upper:
                # Price at or above upper band - overbought, expect drop
                direction = SignalDirection.SHORT
                signal_type = SignalType.ENTER_NOW
                
                z_magnitude = abs(z_score)
                if z_magnitude > 3:
                    signal_type = SignalType.WATCH
                
                supporting_evidence.append(f"Price at upper BB: ${close:.2f} vs ${bb_upper:.2f}")
                supporting_evidence.append(f"Z-score: {z_score:.2f}")
                supporting_evidence.append(f"Deviation: {latest['deviation_from_mean'][0]:.2%}")
                
                if volume > avg_volume:
                    supporting_evidence.append(f"Volume spike: {volume/avg_volume:.1f}x avg")
                else:
                    contradicting_evidence.append("Volume not confirming")
                
            elif close < bb_middle:
                # Price below mean but not extreme
                direction = SignalDirection.LONG
                signal_type = SignalType.WATCH
                
                supporting_evidence.append(f"Price below mean: ${close:.2f} vs ${bb_middle:.2f}")
                contradicting_evidence.append("Not at extreme - waiting for better entry")
                
            elif close > bb_middle:
                # Price above mean but not extreme
                direction = SignalDirection.SHORT
                signal_type = SignalType.WATCH
                
                supporting_evidence.append(f"Price above mean: ${close:.2f} vs ${bb_middle:.2f}")
                contradicting_evidence.append("Not at extreme - waiting for better entry")
                
            else:
                # Price at or near mean
                direction = SignalDirection.NEUTRAL
                signal_type = SignalType.NO_TRADE
                contradicting_evidence.append("Price at mean - no edge")
            
            # Calculate stops and targets
            if direction == SignalDirection.LONG:
                stop_loss = bb_lower - atr * 0.5  # Stop just below lower band
                take_profit = bb_middle  # Target is the mean
            elif direction == SignalDirection.SHORT:
                stop_loss = bb_upper + atr * 0.5
                take_profit = bb_middle
            else:
                stop_loss = None
                take_profit = None
            
            # Calculate confidence
            confidence = self._calculate_confidence(
                z_score=z_score,
                volume_ratio=volume/avg_volume if avg_volume > 0 else 1,
                close=close,
                bb_upper=bb_upper,
                bb_lower=bb_lower,
            )
            
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
                    expected_reward_risk=1.5 if close < bb_middle else 1.5,
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
    
    def _calculate_confidence(
        self,
        z_score: float,
        volume_ratio: float,
        close: float,
        bb_upper: float,
        bb_lower: float,
    ) -> float:
        """Calculate signal confidence score (0-100)."""
        confidence = 50.0
        
        # Z-score contribution (up to 30 points)
        z_magnitude = abs(z_score)
        if 2.0 <= z_magnitude <= 3.0:
            confidence += 30  # Sweet spot
        elif z_magnitude > 3.0:
            confidence += 15  # Extreme but risky
        elif z_magnitude >= 1.5:
            confidence += 15
        else:
            confidence -= 20
        
        # Volume contribution (up to 10 points)
        if volume_ratio >= 1.5:
            confidence += 10
        elif volume_ratio >= 1.0:
            confidence += 5
        
        # Position in band contribution (up to 10 points)
        band_range = bb_upper - bb_lower
        if band_range > 0:
            position = (close - bb_lower) / band_range
            # Extremes are better
            if position <= 0.1 or position >= 0.9:
                confidence += 10
            elif position <= 0.2 or position >= 0.8:
                confidence += 5
        
        return max(0, min(100, confidence))
    
    def get_parameter_space(self) -> dict[str, list]:
        """Get parameter space for optimization."""
        return {
            "bb_period": [15, 20, 25],
            "bb_std": [1.5, 2.0, 2.5],
            "entry_threshold": [1.5, 2.0, 2.5],
            "lookback_period": [30, 50, 100],
        }
