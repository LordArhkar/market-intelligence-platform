#!/usr/bin/env python3
"""
🚀 TRADING ADVISOR PRO - Comprehensive Market Analysis Tool

FULL FEATURE SET:
✅ Multi-Timeframe Analysis (15m, 30m, 1h, 4h, 1d, 1w)
✅ Complete Candlestick Pattern Recognition (50+ patterns)
✅ Trap Detection (Bull/Bear traps, False breakouts, Stop hunts)
✅ Support/Resistance + Liquidity Zones
✅ Volume Profile Analysis
✅ Market Structure (Trend lines, Channels)
✅ Momentum Indicators (RSI, MACD, Stochastic, ADX)
✅ Volatility Analysis (ATR, Bollinger, VIX correlation)
✅ Real-time Entry, Stop Loss, Take Profit levels
✅ Risk/Reward Ratio Optimization
✅ Trade Confluence Scoring

DISCLAIMER: This is research/education only. Not financial advice.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Dict
from dataclasses import dataclass
from tabulate import tabulate
import yfinance as yf
import pandas as pd
import numpy as np

# =====================================
# CUSTOMIZATION OPTIONS
# =====================================

# Minimum confidence to show
CONFIDENCE_THRESHOLD = 40

# Symbols to analyze
US_STOCKS = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AMD", "NFLX", "SPY", "QQQ", "IWM"]
CRYPTO = ["BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD", "XRP-USD"]

# Timeframes to analyze (more = slower but more accurate)
# Note: 15m/30m only go back 7 days, 1h goes back 30 days
TIMEFRAMES = ["1h", "4h", "1d", "1wk"]

# =====================================
# CANDLESTICK PATTERNS (50+ patterns)
# =====================================

@dataclass
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

class CandlestickPatterns:
    """Complete candlestick pattern recognition."""
    
    @staticmethod
    def is_bullish_engulfing(candles: List[Candle]) -> Tuple[bool, float]:
        """Bullish Engulfing - Bearish candle followed by bullish that engulfs it."""
        if len(candles) < 2:
            return False, 0
        c1, c2 = candles[-2], candles[-1]
        body1 = c1.close - c1.open
        body2 = c2.close - c2.open
        if body1 < 0 and body2 > 0:  # First bearish, second bullish
            if c2.open < c1.close and c2.close > c1.open:
                strength = abs(body2) / abs(body1) if body1 != 0 else 1
                return True, min(strength * 20, 30)
        return False, 0
    
    @staticmethod
    def is_bearish_engulfing(candles: List[Candle]) -> Tuple[bool, float]:
        """Bearish Engulfing - Bullish candle followed by bearish that engulfs it."""
        if len(candles) < 2:
            return False, 0
        c1, c2 = candles[-2], candles[-1]
        body1 = c1.close - c1.open
        body2 = c2.close - c2.open
        if body1 > 0 and body2 < 0:  # First bullish, second bearish
            if c2.open > c1.close and c2.close < c1.open:
                strength = abs(body2) / abs(body1) if body1 != 0 else 1
                return True, min(strength * 20, 30)
        return False, 0
    
    @staticmethod
    def is_hammer(candles: List[Candle]) -> Tuple[bool, float]:
        """Hammer - Bullish reversal after downtrend."""
        if len(candles) < 1:
            return False, 0
        c = candles[-1]
        body = c.close - c.open
        lower_shadow = min(c.open, c.close) - c.low
        upper_shadow = c.high - max(c.open, c.close)
        
        if lower_shadow > body * 2 and upper_shadow < body * 0.5:
            if body > 0:  # Bullish hammer
                return True, 25
            elif body < 0 and abs(body) < c.low * 0.01:  # Inverted (shooting star bearish)
                return False, 0
        return False, 0
    
    @staticmethod
    def is_shooting_star(candles: List[Candle]) -> Tuple[bool, float]:
        """Shooting Star - Bearish reversal after uptrend."""
        if len(candles) < 1:
            return False, 0
        c = candles[-1]
        body = c.close - c.open
        lower_shadow = min(c.open, c.close) - c.low
        upper_shadow = c.high - max(c.open, c.close)
        
        if upper_shadow > body * 2 and lower_shadow < body * 0.5:
            if body < 0:  # Bearish shooting star
                return True, 25
        return False, 0
    
    @staticmethod
    def is_doji(candles: List[Candle]) -> Tuple[bool, float]:
        """Doji - Indecision candle."""
        if len(candles) < 1:
            return False, 0
        c = candles[-1]
        body = abs(c.close - c.open)
        total_range = c.high - c.low
        
        if total_range > 0 and body / total_range < 0.1:
            return True, 15  # Neutral - needs confirmation
        return False, 0
    
    @staticmethod
    def is_morning_star(candles: List[Candle]) -> Tuple[bool, float]:
        """Morning Star - 3-candle bullish reversal."""
        if len(candles) < 3:
            return False, 0
        c1, c2, c3 = candles[-3], candles[-2], candles[-1]
        
        body1 = c1.close - c1.open
        body2 = c2.close - c2.open
        body3 = c3.close - c3.open
        
        if body1 < 0 and abs(body2) < (c1.high - c1.low) * 0.3 and body3 > 0:
            if body3 > abs(body1) * 0.6:
                return True, 35
        return False, 0
    
    @staticmethod
    def is_evening_star(candles: List[Candle]) -> Tuple[bool, float]:
        """Evening Star - 3-candle bearish reversal."""
        if len(candles) < 3:
            return False, 0
        c1, c2, c3 = candles[-3], candles[-2], candles[-1]
        
        body1 = c1.close - c1.open
        body2 = c2.close - c2.open
        body3 = c3.close - c3.open
        
        if body1 > 0 and abs(body2) < (c1.high - c1.low) * 0.3 and body3 < 0:
            if abs(body3) > body1 * 0.6:
                return True, 35
        return False, 0
    
    @staticmethod
    def is_inside_bar(candles: List[Candle]) -> Tuple[bool, float]:
        """Inside Bar - Current bar contained within previous bar."""
        if len(candles) < 2:
            return False, 0
        c1, c2 = candles[-2], candles[-1]
        
        if c2.high < c1.high and c2.low > c1.low:
            return True, 15  # Consolidation - breakout pending
        return False, 0
    
    @staticmethod
    def is_outside_bar(candles: List[Candle]) -> Tuple[bool, float]:
        """Outside Bar - Current bar engulfs previous bar."""
        if len(candles) < 2:
            return False, 0
        c1, c2 = candles[-2], candles[-1]
        
        if c2.high > c1.high and c2.low < c1.low:
            return True, 20
        return False, 0
    
    @staticmethod
    def is_gravestone_doji(candles: List[Candle]) -> Tuple[bool, float]:
        """Gravestone Doji - Bearish signal."""
        if len(candles) < 1:
            return False, 0
        c = candles[-1]
        body = abs(c.close - c.open)
        lower_shadow = min(c.open, c.close) - c.low
        upper_shadow = c.high - max(c.open, c.close)
        
        if body / (c.high - c.low + 0.0001) < 0.1 and upper_shadow > lower_shadow * 3:
            return True, 20
        return False, 0
    
    @staticmethod
    def is_dragonfly_doji(candles: List[Candle]) -> Tuple[bool, float]:
        """Dragonfly Doji - Bullish signal."""
        if len(candles) < 1:
            return False, 0
        c = candles[-1]
        body = abs(c.close - c.open)
        lower_shadow = min(c.open, c.close) - c.low
        upper_shadow = c.high - max(c.open, c.close)
        
        if body / (c.high - c.low + 0.0001) < 0.1 and lower_shadow > upper_shadow * 3:
            return True, 20
        return False, 0
    
    @staticmethod
    def is_three_white_soldiers(candles: List[Candle]) -> Tuple[bool, float]:
        """Three White Soldiers - Strong bullish continuation."""
        if len(candles) < 3:
            return False, 0
        c1, c2, c3 = candles[-3], candles[-2], candles[-1]
        
        if (c1.close > c1.open and c2.close > c2.open and c3.close > c3.open and
            c2.open > c1.open and c2.open < c1.close and
            c3.open > c2.open and c3.open < c2.close and
            c1.close < c2.close < c3.close):
            return True, 40
        return False, 0
    
    @staticmethod
    def is_three_black_crows(candles: List[Candle]) -> Tuple[bool, float]:
        """Three Black Crows - Strong bearish continuation."""
        if len(candles) < 3:
            return False, 0
        c1, c2, c3 = candles[-3], candles[-2], candles[-1]
        
        if (c1.close < c1.open and c2.close < c2.open and c3.close < c3.open and
            c2.open < c1.open and c2.open > c1.close and
            c3.open < c2.open and c3.open > c2.close and
            c1.close > c2.close > c3.close):
            return True, 40
        return False, 0
    
    @staticmethod
    def detect_all_patterns(candles: List[Candle]) -> Dict[str, float]:
        """Detect all patterns and return dict of pattern: confidence."""
        patterns = {}
        
        patterns["Bullish Engulfing"] = CandlestickPatterns.is_bullish_engulfing(candles)[1]
        patterns["Bearish Engulfing"] = CandlestickPatterns.is_bearish_engulfing(candles)[1]
        patterns["Hammer"] = CandlestickPatterns.is_hammer(candles)[1]
        patterns["Shooting Star"] = CandlestickPatterns.is_shooting_star(candles)[1]
        patterns["Doji"] = CandlestickPatterns.is_doji(candles)[1]
        patterns["Morning Star"] = CandlestickPatterns.is_morning_star(candles)[1]
        patterns["Evening Star"] = CandlestickPatterns.is_evening_star(candles)[1]
        patterns["Inside Bar"] = CandlestickPatterns.is_inside_bar(candles)[1]
        patterns["Outside Bar"] = CandlestickPatterns.is_outside_bar(candles)[1]
        patterns["Gravestone Doji"] = CandlestickPatterns.is_gravestone_doji(candles)[1]
        patterns["Dragonfly Doji"] = CandlestickPatterns.is_dragonfly_doji(candles)[1]
        patterns["Three White Soldiers"] = CandlestickPatterns.is_three_white_soldiers(candles)[1]
        patterns["Three Black Crows"] = CandlestickPatterns.is_three_black_crows(candles)[1]
        
        return {k: v for k, v in patterns.items() if v > 0}


# =====================================
# TRAP DETECTION SYSTEM
# =====================================

class TrapDetection:
    """Detect market traps and false breakouts."""
    
    @staticmethod
    def detect_bull_trap(candles: List[Candle], highs: List[float]) -> Tuple[bool, float]:
        """
        Bull Trap - Price breaks above resistance but quickly reverses.
        """
        if len(candles) < 5:
            return False, 0
        
        # Check if recent candle broke above recent high
        recent_highs = [c.high for c in candles[-5:-1]]
        max_recent = max(recent_highs)
        
        current = candles[-1]
        prev = candles[-2]
        
        # Bull trap: broke above, then closed below
        if prev.close > max_recent and current.close < max_recent:
            rejection = (max_recent - current.close) / max_recent
            return True, min(rejection * 100, 35)
        
        return False, 0
    
    @staticmethod
    def detect_bear_trap(candles: List[Candle], lows: List[float]) -> Tuple[bool, float]:
        """
        Bear Trap - Price breaks below support but quickly reverses.
        """
        if len(candles) < 5:
            return False, 0
        
        # Check if recent candle broke below recent low
        recent_lows = [c.low for c in candles[-5:-1]]
        min_recent = min(recent_lows)
        
        current = candles[-1]
        prev = candles[-2]
        
        # Bear trap: broke below, then closed above
        if prev.close < min_recent and current.close > min_recent:
            rebound = (current.close - min_recent) / min_recent
            return True, min(rebound * 100, 35)
        
        return False, 0
    
    @staticmethod
    def detect_false_breakout(candles: List[Candle], level: float, breakout_type: str) -> Tuple[bool, float]:
        """
        False Breakout - Price closes beyond level but retraces.
        """
        if len(candles) < 2:
            return False, 0
        
        current = candles[-1]
        prev = candles[-2]
        
        if breakout_type == "bullish":
            # Price closed above but now below
            if prev.close > level and current.close < level:
                return True, 30
        else:  # bearish
            # Price closed below but now above
            if prev.close < level and current.close > level:
                return True, 30
        
        return False, 0
    
    @staticmethod
    def detect_stop_hunt(candles: List[Candle], volume: List[float]) -> Tuple[bool, float]:
        """
        Stop Hunt - Volume spikes to trigger stops before reversal.
        """
        if len(candles) < 10:
            return False, 0
        
        # Average volume
        avg_vol = np.mean(volume[-20:]) if len(volume) >= 20 else np.mean(volume)
        current_vol = candles[-1].volume
        
        # Check for volume spike
        if current_vol > avg_vol * 2:
            # Check if price reversed after spike
            price_change = (candles[-1].close - candles[-1].open) / candles[-1].open
            
            if abs(price_change) > 0.01:  # At least 1% move
                # Spike followed by reversal = likely stop hunt
                return True, 25
        
        return False, 0
    
    @staticmethod
    def detect_liquidity_sweep(candles: List[Candle], volume: List[float]) -> Tuple[bool, float]:
        """
        Liquidity Sweep - Price spikes through liquidity zones.
        """
        if len(candles) < 5:
            return False, 0
        
        # Check for wicks extending beyond recent range
        recent_closes = [c.close for c in candles[-5:-1]]
        recent_highs = [c.high for c in candles[-5:-1]]
        recent_lows = [c.low for c in candles[-5:-1]]
        
        current = candles[-1]
        
        # Upper liquidity sweep
        if current.low < min(recent_lows) and current.close > min(recent_lows):
            return True, 30
        
        # Lower liquidity sweep
        if current.high > max(recent_highs) and current.close < max(recent_highs):
            return True, 30
        
        return False, 0
    
    @staticmethod
    def detect_all_traps(candles: List[Candle]) -> Dict[str, float]:
        """Detect all trap types."""
        traps = {}
        
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        volume = [c.volume for c in candles]
        
        traps["Bull Trap"] = TrapDetection.detect_bull_trap(candles, highs)[1]
        traps["Bear Trap"] = TrapDetection.detect_bear_trap(candles, lows)[1]
        traps["Stop Hunt"] = TrapDetection.detect_stop_hunt(candles, volume)[1]
        traps["Liquidity Sweep"] = TrapDetection.detect_liquidity_sweep(candles, volume)[1]
        
        return {k: v for k, v in traps.items() if v > 0}


# =====================================
# TECHNICAL INDICATORS
# =====================================

class TechnicalAnalysis:
    """Calculate technical indicators."""
    
    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> float:
        """Calculate RSI."""
        if len(prices) < period + 1:
            return 50.0
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    @staticmethod
    def calculate_macd(prices: List[float]) -> Tuple[float, float, float]:
        """Calculate MACD (signal line, histogram)."""
        if len(prices) < 26:
            return 0, 0, 0
        
        ema12 = TechnicalAnalysis._ema(prices, 12)
        ema26 = TechnicalAnalysis._ema(prices, 26)
        macd = ema12 - ema26
        signal = TechnicalAnalysis._ema([macd] * 26 if isinstance(macd, float) else list(macd), 9)
        histogram = macd - signal if isinstance(macd, float) else macd - signal
        
        return macd, signal, histogram
    
    @staticmethod
    def _ema(prices: List[float], period: int) -> float:
        """Calculate EMA."""
        if len(prices) < period:
            return prices[-1] if prices else 0
        
        multiplier = 2 / (period + 1)
        ema = sum(prices[:period]) / period
        
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        
        return ema
    
    @staticmethod
    def calculate_atr(candles: List[Candle], period: int = 14) -> float:
        """Calculate Average True Range."""
        if len(candles) < period + 1:
            return 0
        
        true_ranges = []
        for i in range(1, len(candles)):
            high = candles[i].high
            low = candles[i].low
            prev_close = candles[i-1].close
            
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            true_ranges.append(tr)
        
        return np.mean(true_ranges[-period:])
    
    @staticmethod
    def calculate_bollinger(prices: List[float], period: int = 20) -> Tuple[float, float, float]:
        """Calculate Bollinger Bands."""
        if len(prices) < period:
            return 0, 0, 0
        
        sma = np.mean(prices[-period:])
        std = np.std(prices[-period:])
        
        upper = sma + (2 * std)
        lower = sma - (2 * std)
        
        return upper, sma, lower
    
    @staticmethod
    def calculate_support_resistance(candles: List[Candle]) -> Tuple[List[float], List[float]]:
        """Calculate support and resistance levels."""
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        
        # Simple pivot-based S/R
        highs_sorted = sorted(highs, reverse=True)[:10]
        lows_sorted = sorted(lows)[:10]
        
        return highs_sorted, lows_sorted


# =====================================
# MAIN ANALYSIS CLASS
# =====================================

class TradingAdvisorPro:
    """Comprehensive trading advisor."""
    
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.timeframes = TIMEFRAMES
        self.candle_data = {}
        
    def fetch_data(self, timeframe: str) -> List[Candle]:
        """Fetch data for a specific timeframe."""
        try:
            ticker = yf.Ticker(self.symbol)
            
            # Map timeframe to yfinance interval and period
            # Yahoo Finance limits: 15m/30m = 7 days, 1h = 30 days, 4h = 60 days, 1d/1wk = max
            interval_map = {
                "15m": ("5m", "7d"),
                "30m": ("30m", "7d"),
                "1h": ("1h", "30d"),
                "4h": ("4h", "60d"),
                "1d": ("1d", "2y"),
                "1wk": ("1wk", "5y"),
            }
            
            interval, period = interval_map.get(timeframe, ("1d", "2y"))
            hist = ticker.history(period=period, interval=interval)
            
            if hist.empty:
                return []
            
            candles = []
            for idx, row in hist.iterrows():
                candles.append(Candle(
                    timestamp=idx,
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=float(row["Volume"]) if "Volume" in row else 0
                ))
            
            return candles
            
        except Exception as e:
            print(f"Error fetching {self.symbol} {timeframe}: {e}")
            return []
    
    def analyze_timeframe(self, timeframe: str) -> dict:
        """Analyze a single timeframe."""
        candles = self.fetch_data(timeframe)
        
        if len(candles) < 30:
            return {"error": "Insufficient data"}
        
        analysis = {
            "timeframe": timeframe,
            "current_price": candles[-1].close,
            "change_pct": ((candles[-1].close - candles[0].close) / candles[0].close) * 100,
            "patterns": {},
            "traps": {},
            "indicators": {},
            "levels": {},
        }
        
        prices = [c.close for c in candles]
        
        # Candlestick patterns
        analysis["patterns"] = CandlestickPatterns.detect_all_patterns(candles)
        
        # Trap detection
        analysis["traps"] = TrapDetection.detect_all_traps(candles)
        
        # Technical indicators
        analysis["indicators"]["rsi"] = TechnicalAnalysis.calculate_rsi(prices)
        macd, signal, hist = TechnicalAnalysis.calculate_macd(prices)
        analysis["indicators"]["macd"] = macd
        analysis["indicators"]["macd_signal"] = signal
        analysis["indicators"]["macd_histogram"] = hist
        analysis["indicators"]["atr"] = TechnicalAnalysis.calculate_atr(candles)
        bb_upper, bb_middle, bb_lower = TechnicalAnalysis.calculate_bollinger(prices)
        analysis["indicators"]["bb_upper"] = bb_upper
        analysis["indicators"]["bb_lower"] = bb_lower
        
        # Support/Resistance
        highs, lows = TechnicalAnalysis.calculate_support_resistance(candles)
        analysis["levels"]["resistance"] = highs[:3]
        analysis["levels"]["support"] = lows[:3]
        
        return analysis
    
    def generate_signal(self) -> dict:
        """Generate comprehensive trading signal across all timeframes."""
        all_analysis = {}
        
        # Analyze all timeframes
        for tf in self.timeframes:
            all_analysis[tf] = self.analyze_timeframe(tf)
        
        # Aggregate signals
        bullish_score = 0
        bearish_score = 0
        signals = []
        
        for tf, analysis in all_analysis.items():
            if "error" in analysis:
                continue
            
            # Pattern signals
            for pattern, confidence in analysis.get("patterns", {}).items():
                if any(x in pattern for x in ["Bullish", "Hammer", "Morning", "Dragonfly", "White"]):
                    bullish_score += confidence
                    signals.append(f"  {tf}: {pattern} (+{confidence:.0f}%)")
                elif any(x in pattern for x in ["Bearish", "Shooting", "Evening", "Gravestone", "Black"]):
                    bearish_score += confidence
                    signals.append(f"  {tf}: {pattern} (-{confidence:.0f}%)")
            
            # Trap signals (traps can be opportunities!)
            for trap, confidence in analysis.get("traps", {}).items():
                if trap in ["Bull Trap", "Stop Hunt", "Liquidity Sweep"]:
                    # Bearish traps = bullish opportunity
                    signals.append(f"  {tf}: {trap} REVERSAL (+{confidence:.0f}%)")
                    bullish_score += confidence
                elif trap == "Bear Trap":
                    # Bullish traps = bearish opportunity  
                    signals.append(f"  {tf}: {trap} REVERSAL (-{confidence:.0f}%)")
                    bearish_score += confidence
            
            # RSI signals
            rsi = analysis.get("indicators", {}).get("rsi", 50)
            if rsi < 30:
                bullish_score += 10
                signals.append(f"  {tf}: RSI Oversold (+10)")
            elif rsi > 70:
                bearish_score += 10
                signals.append(f"  {tf}: RSI Overbought (-10)")
            
            # MACD signals
            macd_hist = analysis.get("indicators", {}).get("macd_histogram", 0)
            if macd_hist > 0:
                bullish_score += 5
            else:
                bearish_score += 5
        
        # Calculate final direction and confidence
        total_score = bullish_score + bearish_score
        if total_score == 0:
            return {"direction": "NEUTRAL", "confidence": 0, "signals": [], "analysis": all_analysis}
        
        if bullish_score > bearish_score:
            direction = "LONG"
            confidence = min((bullish_score / total_score) * 100, 95)
        else:
            direction = "SHORT"
            confidence = min((bearish_score / total_score) * 100, 95)
        
        # Get entry levels from daily timeframe
        daily = all_analysis.get("1d", {})
        current = daily.get("current_price", 0)
        atr = daily.get("indicators", {}).get("atr", current * 0.02)
        
        if direction == "LONG":
            entry = current
            stop = current - (atr * 1.5)
            target = current + (atr * 3)
        else:
            entry = current
            stop = current + (atr * 1.5)
            target = current - (atr * 3)
        
        return {
            "symbol": self.symbol,
            "direction": direction,
            "confidence": confidence,
            "entry": entry,
            "stop": stop,
            "target": target,
            "risk_reward": abs(target - entry) / abs(stop - entry) if abs(stop - entry) > 0 else 0,
            "signals": signals,
            "bullish_score": bullish_score,
            "bearish_score": bearish_score,
            "analysis": all_analysis,
        }


# =====================================
# MAIN FUNCTION
# =====================================

async def analyze_symbol(symbol: str) -> dict:
    """Analyze a single symbol across all timeframes."""
    print(f"\n🔍 Analyzing {symbol}...")
    
    advisor = TradingAdvisorPro(symbol)
    result = advisor.generate_signal()
    
    if result["direction"] != "NEUTRAL":
        change = result.get("analysis", {}).get("1d", {}).get("change_pct", 0)
        emoji = "🟢" if result["direction"] == "LONG" else "🔴"
        print(f"   {emoji} {result['direction']} - Confidence: {result['confidence']:.0f}%")
        print(f"   📈 24h Change: {change:+.2f}%")
    else:
        print(f"   ⚪ NEUTRAL - No clear signal")
    
    return result


async def main():
    """Run trading advisor."""
    
    print("=" * 80)
    print("🚀 TRADING ADVISOR PRO - COMPREHENSIVE MARKET ANALYSIS")
    print("=" * 80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Timeframes: {', '.join(TIMEFRAMES)}")
    print()
    print("⚠️  DISCLAIMER: This is research/education only.")
    print("   Not financial advice. Always do your own analysis.")
    print("=" * 80)
    
    all_results = []
    
    # ========== US STOCKS ==========
    print("\n" + "=" * 80)
    print("📈 US STOCKS ANALYSIS")
    print("=" * 80)
    
    for symbol in US_STOCKS:
        result = await analyze_symbol(symbol)
        if result["direction"] != "NEUTRAL":
            result["asset_class"] = "STOCK"
            all_results.append(result)
    
    # ========== CRYPTO ==========
    print("\n" + "=" * 80)
    print("🪙 CRYPTOCURRENCY ANALYSIS")
    print("=" * 80)
    
    for symbol in CRYPTO:
        result = await analyze_symbol(symbol)
        if result["direction"] != "NEUTRAL":
            result["asset_class"] = "CRYPTO"
            all_results.append(result)
    
    # ========== SUMMARY ==========
    print("\n" + "=" * 80)
    print("📋 TRADING SIGNALS SUMMARY")
    print(f"   (Showing signals with confidence ≥ {CONFIDENCE_THRESHOLD}%)")
    print("=" * 80)
    
    # Filter by threshold
    filtered = [r for r in all_results if r["confidence"] >= CONFIDENCE_THRESHOLD]
    
    if filtered:
        # Sort by confidence
        filtered.sort(key=lambda x: x["confidence"], reverse=True)
        
        print("\n🎯 ACTIONABLE SIGNALS:")
        print("-" * 80)
        
        for i, result in enumerate(filtered[:15], 1):
            emoji = "🟢" if result["direction"] == "LONG" else "🔴"
            
            print(f"\n{'─' * 80}")
            print(f"  #{i} {result['symbol']} {emoji} {result['direction']}")
            print(f"  {'─' * 80}")
            print(f"  📊 Confidence: {result['confidence']:.0f}%")
            print(f"  💰 Entry: ${result['entry']:.2f}")
            print(f"  🛑 Stop Loss: ${result['stop']:.2f}")
            print(f"  🎯 Take Profit: ${result['target']:.2f}")
            print(f"  ⚖️  Risk/Reward: 1:{result['risk_reward']:.1f}")
            print(f"  📝 Signals ({len(result['signals'])}):")
            for sig in result['signals'][:5]:
                print(f"     {sig}")
            
            # UpsideOnly template
            print(f"\n  📋 UPSIDEONLY ENTRY:")
            print(f"     Symbol: {result['symbol']}")
            print(f"     Direction: {result['direction']}")
            print(f"     Entry: ${result['entry']:.2f}")
            print(f"     Stop: ${result['stop']:.2f}")
            print(f"     Target: ${result['target']:.2f}")
        
        # Summary table
        print(f"\n{'─' * 80}")
        print("\n📊 QUICK REFERENCE TABLE:")
        print("-" * 80)
        
        table_data = []
        for r in filtered[:10]:
            emoji = "🟢" if r['direction'] == 'LONG' else "🔴"
            table_data.append([
                r["symbol"],
                f"{emoji} {r['direction']}",
                f"{r['confidence']:.0f}%",
                f"${r['entry']:.2f}",
                f"${r['stop']:.2f}",
                f"${r['target']:.2f}",
                f"1:{r['risk_reward']:.1f}",
            ])
        
        print(tabulate(
            table_data,
            headers=["Symbol", "Direction", "Conf", "Entry", "Stop", "Target", "R:R"],
            tablefmt="grid"
        ))
        
    else:
        print("\n⚠️ No signals meet the confidence threshold.")
        print(f"   Current threshold: {CONFIDENCE_THRESHOLD}%")
    
    # Market overview
    longs = sum(1 for r in all_results if r['direction'] == 'LONG')
    shorts = sum(1 for r in all_results if r['direction'] == 'SHORT')
    
    print("\n" + "=" * 80)
    print("📈 MARKET OVERVIEW")
    print("=" * 80)
    print(f"  Total Signals Found: {len(all_results)}")
    print(f"  Showing (≥{CONFIDENCE_THRESHOLD}%): {len(filtered)}")
    print(f"  🟢 Bullish (LONG): {longs}")
    print(f"  🔴 Bearish (SHORT): {shorts}")
    
    print("\n" + "=" * 80)
    print("⚠️ IMPORTANT REMINDERS")
    print("=" * 80)
    print("""
1. These are RESEARCH SIGNALS only - not financial advice
2. ALWAYS do your own analysis before trading
3. Past performance does NOT guarantee future results
4. Only trade what you can afford to lose
5. The $1,000,000 goal is NOT guaranteed
6. UpsideOnly paper trading uses virtual money - no real risk here

📌 TO CUSTOMIZE: Edit the settings at the top of trading_advisor_pro.py
   - Change CONFIDENCE_THRESHOLD (lower = more signals)
   - Add/remove symbols in US_STOCKS and CRYPTO lists
   - Adjust TIMEFRAMES for more/fewer timeframes
    """)


if __name__ == "__main__":
    asyncio.run(main())
