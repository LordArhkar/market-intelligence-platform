"""
Trend following strategy implementation.

Hypothesis: The trend is your friend - trade in the direction of
established trends until they show signs of reversal.
"""

from datetime import datetime
from typing import Any

import polars as pl
from ta.trend import MACD, ADXIndicator, EMAIndicator as EMA, SMAIndicator as SMA
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange

from mip.core.models.signal import Signal, SignalDirection, SignalStatus, SignalType
from mip.strategies.base import BaseStrategy, StrategyResult


class TrendFollowingStrategy(BaseStrategy):
    """
    Trend following strategy using multiple moving averages and ADX.
    
    Parameters:
        fast_ma: Fast moving average period (default: 10)
        slow_ma: Slow moving average period (default: 50)
        trend_ma: Trend confirmation MA (default: 200)
        adx_period: ADX period (default: 14)
        adx_threshold: Minimum ADX for trend (default: 25)
    """
    
    @property
    def name(self) -> str:
        return "trend_following"
    
    @property
    def category(self) -> str:
        return "TREND_FOLLOWING"
    
    def _validate_parameters(self) -> None:
        """Validate strategy parameters."""
        fast = self.params.get("fast_ma", 10)
        slow = self.params.get("slow_ma", 50)
        if fast >= slow:
            raise ValueError("fast_ma must be less than slow_ma")
    
    async def calculate_indicators(
        self,
        data: pl.DataFrame
    ) -> pl.DataFrame:
        """Calculate trend following indicators."""
        df = data.clone()
        
        fast_period = self.params.get("fast_ma", 10)
        slow_period = self.params.get("slow_ma", 50)
        trend_period = self.params.get("trend_ma", 200)
        adx_period = self.params.get("adx_period", 14)
        
        # Moving averages
        df = df.with_columns(
            pl.Series("ema_fast", EMA(df["close"], window=fast_period)),
            pl.Series("sma_fast", SMA(df["close"], window=fast_period)),
            pl.Series("sma_slow", SMA(df["close"], window=slow_period)),
            pl.Series("sma_trend", SMA(df["close"], window=trend_period)),
        )
        
        # MACD
        macd = MACD(df["close"])
        df = df.with_columns(
            pl.Series("macd", macd.macd()),
            pl.Series("macd_signal", macd.macd_signal()),
            pl.Series("macd_diff", macd.macd_diff()),
        )
        
        # ADX for trend strength
        adx = ADXIndicator(df["high"], df["low"], df["close"], window=adx_period)
        df = df.with_columns(
            pl.Series("adx", adx.adx()),
            pl.Series("adx_pos", adx.adx_pos()),
            pl.Series("adx_neg", adx.adx_neg()),
        )
        
        # RSI
        rsi = RSIIndicator(df["close"], window=14)
        df = df.with_columns(
            pl.Series("rsi", rsi.rsi())
        )
        
        # ATR for position sizing
        atr = AverageTrueRange(df["high"], df["low"], df["close"])
        df = df.with_columns(
            pl.Series("atr", atr.average_true_range())
        )
        
        # Trend direction indicators
        df = df.with_columns(
            (pl.col("sma_fast") > pl.col("sma_slow")).cast(pl.Int8).alias("bullish_cross"),
            (pl.col("close") > pl.col("sma_trend")).cast(pl.Int8).alias("above_trend"),
            (pl.col("macd") > pl.col("macd_signal")).cast(pl.Int8).alias("macd_bullish"),
        )
        
        return df
    
    async def generate_signals(
        self,
        data: pl.DataFrame,
        context: dict[str, Any]
    ) -> StrategyResult:
        """Generate trend following trading signals."""
        start_time = datetime.utcnow()
        signals = []
        errors = []
        
        try:
            # Calculate indicators
            df = await self.calculate_indicators(data)
            
            if len(df) < 250:
                errors.append("Insufficient data for trend following (need 250+ bars)")
                return StrategyResult(
                    signals=[],
                    errors=errors,
                    execution_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                )
            
            # Get latest and previous values
            latest = df.tail(1)
            prev = df.tail(2).head(1)
            
            adx_threshold = self.params.get("adx_threshold", 25)
            
            # Extract values
            close = latest["close"][0]
            ema_fast = latest["ema_fast"][0] if "ema_fast" in latest else close
            sma_fast = latest["sma_fast"][0] if "sma_fast" in latest else close
            sma_slow = latest["sma_slow"][0] if "sma_slow" in latest else close
            sma_trend = latest["sma_trend"][0] if "sma_trend" in latest else close
            adx = latest["adx"][0] if "adx" in latest else 0
            adx_pos = latest["adx_pos"][0] if "adx_pos" in latest else 0
            adx_neg = latest["adx_neg"][0] if "adx_neg" in latest else 0
            macd_val = latest["macd"][0] if "macd" in latest else 0
            macd_signal = latest["macd_signal"][0] if "macd_signal" in latest else 0
            rsi = latest["rsi"][0] if "rsi" in latest else 50
            atr = latest["atr"][0] if "atr" in latest else 0
            volume = latest["volume"][0] if "volume" in latest else 0
            
            # Get previous bar for crossover detection
            prev_fast = prev["sma_fast"][0] if "sma_fast" in prev else close
            prev_slow = prev["sma_slow"][0] if "sma_slow" in prev else close
            
            symbol = context.get("symbol", "UNKNOWN")
            timeframe = context.get("timeframe", "1d")
            data_ts = latest["timestamp"][0]
            
            # Calculate average volume
            avg_volume = df.tail(20)["volume"].mean() if "volume" in df else 1
            
            # Strategy logic
            supporting_evidence = []
            contradicting_evidence = []
            
            # Check for golden/death cross
            golden_cross = (
                sma_fast > sma_slow and
                prev_fast <= prev_slow
            )
            death_cross = (
                sma_fast < sma_slow and
                prev_fast >= prev_slow
            )
            
            # Trend strength determination
            strong_uptrend = (
                adx > adx_threshold and
                adx_pos > adx_neg and
                close > sma_trend
            )
            strong_downtrend = (
                adx > adx_threshold and
                adx_neg > adx_pos and
                close < sma_trend
            )
            
            # Weak trend conditions
            weak_uptrend = (
                close > sma_slow and
                close > sma_trend
            )
            weak_downtrend = (
                close < sma_slow and
                close < sma_trend
            )
            
            if strong_uptrend or golden_cross:
                direction = SignalDirection.LONG
                signal_type = SignalType.ENTER_NOW if golden_cross else SignalType.WATCH
                
                supporting_evidence.append(f"ADX: {adx:.1f} (strong trend)")
                supporting_evidence.append(f"Price above trend MA: ${close:.2f} > ${sma_trend:.2f}")
                
                if adx_pos > adx_neg:
                    supporting_evidence.append("+DI > -DI (bullish momentum)")
                
                if golden_cross:
                    supporting_evidence.append("Golden cross detected")
                
                if volume > avg_volume:
                    supporting_evidence.append(f"Volume confirming: {volume/avg_volume:.1f}x avg")
                else:
                    contradicting_evidence.append("Volume weak")
                    
            elif strong_downtrend or death_cross:
                direction = SignalDirection.SHORT
                signal_type = SignalType.ENTER_NOW if death_cross else SignalType.WATCH
                
                supporting_evidence.append(f"ADX: {adx:.1f} (strong trend)")
                supporting_evidence.append(f"Price below trend MA: ${close:.2f} < ${sma_trend:.2f}")
                
                if adx_neg > adx_pos:
                    supporting_evidence.append("-DI > +DI (bearish momentum)")
                
                if death_cross:
                    supporting_evidence.append("Death cross detected")
                
                if volume > avg_volume:
                    supporting_evidence.append(f"Volume confirming: {volume/avg_volume:.1f}x avg")
                else:
                    contradicting_evidence.append("Volume weak")
                    
            elif weak_uptrend:
                direction = SignalDirection.LONG
                signal_type = SignalType.WATCH
                
                supporting_evidence.append("Price above MAs (bullish)")
                contradicting_evidence.append(f"ADX: {adx:.1f} below threshold ({adx_threshold})")
                contradicting_evidence.append("No strong trend - wait for confirmation")
                
            elif weak_downtrend:
                direction = SignalDirection.SHORT
                signal_type = SignalType.WATCH
                
                supporting_evidence.append("Price below MAs (bearish)")
                contradicting_evidence.append(f"ADX: {adx:.1f} below threshold ({adx_threshold})")
                contradicting_evidence.append("No strong trend - wait for confirmation")
                
            else:
                # No clear trend
                direction = SignalDirection.NEUTRAL
                signal_type = SignalType.NO_TRADE
                contradicting_evidence.append(f"ADX: {adx:.1f} (no trend)")
            
            # Calculate stops and targets
            if direction == SignalDirection.LONG:
                stop_loss = close - atr * 2  # 2 ATR stop
                take_profit = close + atr * 4  # 4 ATR target (2:1 R:R)
            elif direction == SignalDirection.SHORT:
                stop_loss = close + atr * 2
                take_profit = close - atr * 4
            else:
                stop_loss = None
                take_profit = None
            
            # Calculate confidence
            confidence = self._calculate_confidence(
                adx=adx,
                adx_threshold=adx_threshold,
                adx_pos=adx_pos,
                adx_neg=adx_neg,
                rsi=rsi,
                volume_ratio=volume/avg_volume if avg_volume > 0 else 1,
                golden_cross=golden_cross,
                death_cross=death_cross,
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
    
    def _calculate_confidence(
        self,
        adx: float,
        adx_threshold: float,
        adx_pos: float,
        adx_neg: float,
        rsi: float,
        volume_ratio: float,
        golden_cross: bool,
        death_cross: bool,
    ) -> float:
        """Calculate signal confidence score (0-100)."""
        confidence = 50.0
        
        # ADX contribution (up to 30 points)
        if adx > 40:
            confidence += 30
        elif adx > adx_threshold:
            confidence += 20
        else:
            confidence -= 15
        
        # Trend alignment (up to 20 points)
        if adx_pos > adx_neg * 1.5:
            confidence += 10  # Strong bullish
        elif adx_neg > adx_pos * 1.5:
            confidence += 10  # Strong bearish
        elif abs(adx_pos - adx_neg) < 5:
            confidence -= 10  # Weak divergence
        
        # RSI contribution (up to 10 points)
        if 40 <= rsi <= 60:
            confidence += 10  # Neutral - trend not exhausted
        elif rsi > 70 or rsi < 30:
            confidence -= 10  # Overextended
        
        # Volume contribution (up to 10 points)
        if volume_ratio >= 1.5:
            confidence += 10
        elif volume_ratio >= 1.0:
            confidence += 5
        
        # Crossover bonus (up to 10 points)
        if golden_cross or death_cross:
            confidence += 10
        
        return max(0, min(100, confidence))
    
    def get_parameter_space(self) -> dict[str, list]:
        """Get parameter space for optimization."""
        return {
            "fast_ma": [5, 10, 15, 20],
            "slow_ma": [30, 50, 100],
            "trend_ma": [100, 150, 200],
            "adx_period": [10, 14, 20],
            "adx_threshold": [20, 25, 30],
        }
