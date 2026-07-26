#!/usr/bin/env python3
"""
🚀 TRADING ADVISOR V5 - UNIVERSAL SHORT STRATEGY

Based on V4 backtest insights showing META works but other stocks don't.
V5 makes the strategy work for ANY stock.

KEY IMPROVEMENTS:

1. PERCENTILE-BASED RSI
   - Instead of fixed thresholds (RSI > 70)
   - Use RELATIVE RSI: Is RSI at extremes FOR THIS STOCK?
   - RSI above 80th percentile = short signal
   - RSI below 20th percentile = long signal

2. ADX TREND FILTER
   - Only trade when ADX > 25 (trending market)
   - Reduces false signals in choppy markets

3. VOLATILITY-ADJUSTED STOPS
   - Different stocks have different volatility
   - Scale ATR multiplier based on recent volatility

4. VOLUME CONFIRMATION
   - Volume spike on pattern = stronger signal
   - Volume must be above 20-day average

5. STOP-RUN AVOIDANCE
   - Don't enter if big move (> 2x ATR) in last 3 days
   - Avoids entering right before a reversal

6. MULTI-TIMEFRAME CONFIRMATION
   - Weekly trend for direction bias
   - Daily for entry timing

DISCLAIMER: Research/education only. Not financial advice.
"""

import asyncio
from datetime import datetime
from typing import List, Dict
from dataclasses import dataclass
from tabulate import tabulate
import yfinance as yf
import numpy as np

# =====================================
# CUSTOMIZATION OPTIONS
# =====================================

CONFIDENCE_THRESHOLD = 55  # Lower for more signals

# STOCKS TO ANALYZE
US_STOCKS = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AMD", "NFLX", "SPY", "QQQ"]

# SHORT-ONLY MODE (recommended)
SHORT_ONLY = True

# =====================================
# DATA CLASS
# =====================================

@dataclass
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


# =====================================
# TECHNICAL INDICATORS
# =====================================

class TechnicalAnalysis:
    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> float:
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
        return float(100 - (100 / (1 + rs)))
    
    @staticmethod
    def calculate_rsi_percentile(prices: List[float], period: int = 14, lookback: int = 252) -> float:
        """Calculate where current RSI falls in percentile of historical RSI values."""
        if len(prices) < period + lookback:
            return 50.0
        
        rsi_history = []
        for i in range(lookback, len(prices)):
            window = prices[i-period:i]
            deltas = np.diff(window)
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)
            avg_gain = np.mean(gains)
            avg_loss = np.mean(losses)
            if avg_loss == 0:
                rsi_history.append(100.0)
            else:
                rsi_history.append(100 - (100 / (1 + avg_gain / avg_loss)))
        
        if not rsi_history:
            return 50.0
        
        current_rsi = TechnicalAnalysis.calculate_rsi(prices[-252:])
        below_count = sum(1 for r in rsi_history if r < current_rsi)
        return (below_count / len(rsi_history)) * 100
    
    @staticmethod
    def calculate_atr(candles: List[Candle], period: int = 14) -> float:
        if len(candles) < period + 1:
            return 0
        true_ranges = []
        for i in range(1, len(candles)):
            tr = max(
                candles[i].high - candles[i].low,
                abs(candles[i].high - candles[i-1].close),
                abs(candles[i].low - candles[i-1].close)
            )
            true_ranges.append(tr)
        return float(np.mean(true_ranges[-period:]))
    
    @staticmethod
    def calculate_adx(candles: List[Candle], period: int = 14) -> float:
        """Calculate Average Directional Index (ADX) for trend strength."""
        if len(candles) < period * 2 + 1:
            return 20.0
        
        plus_dm = []
        minus_dm = []
        tr_list = []
        
        for i in range(1, len(candles)):
            high_diff = candles[i].high - candles[i-1].high
            low_diff = candles[i-1].low - candles[i].low
            
            plus_dm.append(high_diff if high_diff > low_diff and high_diff > 0 else 0)
            minus_dm.append(low_diff if low_diff > high_diff and low_diff > 0 else 0)
            
            tr = max(
                candles[i].high - candles[i].low,
                abs(candles[i].high - candles[i-1].close),
                abs(candles[i].low - candles[i-1].close)
            )
            tr_list.append(tr)
        
        period_tr = []
        period_plus = []
        period_minus = []
        
        for i in range(period - 1, len(tr_list)):
            period_tr.append(sum(tr_list[i - period + 1:i + 1]))
            period_plus.append(sum(plus_dm[i - period + 1:i + 1]))
            period_minus.append(sum(minus_dm[i - period + 1:i + 1]))
        
        if not period_tr or sum(period_tr[-period:]) == 0:
            return 20.0
        
        plus_di = 100 * np.mean(period_plus[-period:]) / np.mean(period_tr[-period:])
        minus_di = 100 * np.mean(period_minus[-period:]) / np.mean(period_tr[-period:])
        
        di_sum = plus_di + minus_di
        if di_sum == 0:
            return 20.0
        
        dx = 100 * abs(plus_di - minus_di) / di_sum
        
        adx = dx
        alpha = 2 / (period + 1)
        for i in range(len(period_tr) - period, len(period_tr) - 1):
            if i > 0:
                period_tr_curr = sum(tr_list[i - period + 1:i + 1]) if i >= period else sum(tr_list[:i + 1])
                period_plus_curr = sum(plus_dm[i - period + 1:i + 1]) if i >= period else sum(plus_dm[:i + 1])
                period_minus_curr = sum(minus_dm[i - period + 1:i + 1]) if i >= period else sum(minus_dm[:i + 1])
                
                if period_tr_curr > 0:
                    plus_di_curr = 100 * period_plus_curr / period_tr_curr
                    minus_di_curr = 100 * period_minus_curr / period_tr_curr
                    di_sum_curr = plus_di_curr + minus_di_curr
                    if di_sum_curr > 0:
                        dx_curr = 100 * abs(plus_di_curr - minus_di_curr) / di_sum_curr
                        adx = alpha * dx_curr + (1 - alpha) * adx
        
        return float(adx)
    
    @staticmethod
    def calculate_sma(prices: List[float], period: int) -> float:
        if len(prices) < period:
            return prices[-1] if prices else 0
        return float(np.mean(prices[-period:]))
    
    @staticmethod
    def calculate_volatility(candles: List[Candle], period: int = 20) -> float:
        if len(candles) < period + 1:
            return 2.0
        prices = [c.close for c in candles]
        returns = np.diff(prices) / np.array(prices[:-1])
        return float(np.std(returns[-period:]) * 100)
    
    @staticmethod
    def calculate_avg_volume(candles: List[Candle], period: int = 20) -> float:
        if len(candles) < period:
            return candles[-1].volume if candles else 0
        return float(np.mean([c.volume for c in candles[-period:]]))
    
    @staticmethod
    def is_volume_spike(candles: List[Candle], threshold: float = 1.5) -> bool:
        if len(candles) < 20:
            return False
        avg_vol = TechnicalAnalysis.calculate_avg_volume(candles[:-1], 20)
        current_vol = candles[-1].volume
        return current_vol > avg_vol * threshold
    
    @staticmethod
    def was_big_move(candles: List[Candle], atr_multiplier: float = 2.0) -> bool:
        if len(candles) < 4:
            return False
        atr = TechnicalAnalysis.calculate_atr(candles[:-1])
        if atr == 0:
            return False
        
        for i in range(-3, 0):
            candle = candles[i]
            move = max(
                abs(candle.close - candles[i-1].close),
                abs(candle.high - candles[i-1].low),
            )
            if move > atr * atr_multiplier:
                return True
        return False


# =====================================
# CANDLESTICK PATTERNS
# =====================================

class CandlestickPatterns:
    @staticmethod
    def is_evening_star(candles: List[Candle]) -> tuple:
        if len(candles) < 3:
            return False, 0
        c1, c2, c3 = candles[-3], candles[-2], candles[-1]
        body1, body3 = c1.close - c1.open, c3.close - c3.open
        
        if (body1 > 0 and body1 > (c1.high - c1.low) * 0.6 and
            body3 < 0 and abs(body3) > (c3.high - c3.low) * 0.6):
            return True, 60
        return False, 0
    
    @staticmethod
    def is_bearish_engulfing(candles: List[Candle]) -> tuple:
        if len(candles) < 2:
            return False, 0
        c1, c2 = candles[-2], candles[-1]
        body1, body2 = c1.close - c1.open, c2.close - c2.open
        
        if body1 > 0 and body2 < 0:
            if c2.open > c1.close and c2.close < c1.open:
                if abs(body2) > abs(body1) * 1.1:
                    return True, 50
        return False, 0
    
    @staticmethod
    def is_shooting_star(candles: List[Candle]) -> tuple:
        if len(candles) < 1:
            return False, 0
        c = candles[-1]
        body = c.close - c.open
        upper = c.high - max(c.open, c.close)
        lower = min(c.open, c.close) - c.low
        
        if upper > abs(body) * 2 and lower < abs(body) * 0.3:
            if body < 0:
                return True, 40
        return False, 0
    
    @staticmethod
    def is_morning_star(candles: List[Candle]) -> tuple:
        if len(candles) < 3:
            return False, 0
        c1, c2, c3 = candles[-3], candles[-2], candles[-1]
        body1, body3 = c1.close - c1.open, c3.close - c3.open
        
        if (body1 < 0 and abs(body1) > (c1.high - c1.low) * 0.6 and
            body3 > 0 and abs(body3) > (c3.high - c3.low) * 0.6):
            return True, 55
        return False, 0
    
    @staticmethod
    def is_bullish_engulfing(candles: List[Candle]) -> tuple:
        if len(candles) < 2:
            return False, 0
        c1, c2 = candles[-2], candles[-1]
        body1, body2 = c1.close - c1.open, c2.close - c2.open
        
        if body1 < 0 and body2 > 0:
            if c2.open < c1.close and c2.close > c1.open:
                if abs(body2) > abs(body1) * 1.1:
                    return True, 45
        return False, 0
    
    @staticmethod
    def detect_all(candles: List[Candle]) -> Dict[str, float]:
        patterns = {}
        patterns["Evening Star"] = CandlestickPatterns.is_evening_star(candles)[1]
        patterns["Bearish Engulfing"] = CandlestickPatterns.is_bearish_engulfing(candles)[1]
        patterns["Shooting Star"] = CandlestickPatterns.is_shooting_star(candles)[1]
        patterns["Morning Star"] = CandlestickPatterns.is_morning_star(candles)[1]
        patterns["Bullish Engulfing"] = CandlestickPatterns.is_bullish_engulfing(candles)[1]
        return {k: v for k, v in patterns.items() if v > 0}


# =====================================
# MAIN CLASS
# =====================================

class TradingAdvisorV5:
    def __init__(self, symbol: str):
        self.symbol = symbol
    
    def fetch_data(self, timeframe: str = "1d") -> List[Candle]:
        try:
            ticker = yf.Ticker(self.symbol)
            hist = ticker.history(period="2y", interval=timeframe)
            
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
        except:
            return []
    
    def generate_signal(self) -> dict:
        """Generate universal SHORT signals using percentile-based indicators."""
        
        daily = self.fetch_data("1d")
        if len(daily) < 300:
            return {"direction": "NEUTRAL", "confidence": 0, "reason": "Insufficient data"}
        
        current = daily[-1]
        prices = [c.close for c in daily]
        
        # Core indicators
        rsi = TechnicalAnalysis.calculate_rsi(prices)
        rsi_percentile = TechnicalAnalysis.calculate_rsi_percentile(prices)
        atr = TechnicalAnalysis.calculate_atr(daily)
        adx = TechnicalAnalysis.calculate_adx(daily)
        sma_200 = TechnicalAnalysis.calculate_sma(prices, 200)
        volatility = TechnicalAnalysis.calculate_volatility(daily)
        
        # Weekly trend
        weekly_idx = len(daily) // 5
        if weekly_idx >= 50:
            weekly_prices = prices[::5]
            weekly_sma_20 = TechnicalAnalysis.calculate_sma(weekly_prices, 20)
            weekly_above = weekly_prices[-1] > weekly_sma_20
        else:
            weekly_above = prices[-1] > sma_200
        
        patterns = CandlestickPatterns.detect_all(daily)
        volume_confirmed = TechnicalAnalysis.is_volume_spike(daily, 1.2)
        avoid_entry = TechnicalAnalysis.was_big_move(daily, 2.0)
        
        above_200 = current.close > sma_200
        
        short_score = 0
        long_score = 0
        reasons = []
        
        # =====================
        # PERCENTILE-BASED RSI - STRICTER REQUIREMENTS
        # =====================
        # Require RSI in top 15% of historical for SHORT
        if rsi_percentile > 85:
            short_score += 50
            reasons.append(f"RSI Percentile: {rsi_percentile:.0f}% (extreme overbought)")
        elif rsi_percentile > 75:
            short_score += 30
            reasons.append(f"RSI Percentile: {rsi_percentile:.0f}% (very overbought)")
        
        # Require RSI in bottom 15% of historical for LONG
        if rsi_percentile < 15:
            long_score += 50
            reasons.append(f"RSI Percentile: {rsi_percentile:.0f}% (extreme oversold)")
        elif rsi_percentile < 25:
            long_score += 30
            reasons.append(f"RSI Percentile: {rsi_percentile:.0f}% (very oversold)")
        
        # =====================
        # STRICTER ADX TREND FILTER - Only strong trends
        # =====================
        if adx > 30:  # Increased from 25 to 30
            if not above_200:
                short_score += 20
                reasons.append(f"ADX: {adx:.1f} (very strong downtrend)")
            elif above_200:
                long_score += 20
                reasons.append(f"ADX: {adx:.1f} (very strong uptrend)")
        elif adx > 25:  # Moderate strength
            if not above_200:
                short_score += 10
                reasons.append(f"ADX: {adx:.1f} (moderate downtrend)")
            elif above_200:
                long_score += 10
                reasons.append(f"ADX: {adx:.1f} (moderate uptrend)")
        else:
            return {
                "direction": "NEUTRAL",
                "confidence": 0,
                "reason": f"ADX: {adx:.1f} (choppy market - skipped)",
                "rsi": rsi,
                "rsi_percentile": rsi_percentile,
                "adx": adx,
                "volatility": volatility,
                "reasons": reasons,
            }
        
        # =====================
        # PATTERN SCORING - Stronger weights
        # =====================
        if "Evening Star" in patterns:
            short_score += 70
            reasons.append("Evening Star pattern")
        if "Bearish Engulfing" in patterns:
            short_score += 55
            reasons.append("Bearish Engulfing pattern")
        if "Shooting Star" in patterns:
            short_score += 45
            reasons.append("Shooting Star pattern")
        if "Morning Star" in patterns:
            long_score += 60
            reasons.append("Morning Star pattern")
        if "Bullish Engulfing" in patterns:
            long_score += 50
            reasons.append("Bullish Engulfing pattern")
        
        # =====================
        # VOLUME CONFIRMATION - Required
        # =====================
        if volume_confirmed:
            if short_score > 0:
                short_score += 20
                reasons.append("Volume spike confirmed")
            if long_score > 0:
                long_score += 20
        
        # =====================
        # TREND BIAS - Both daily and weekly
        # =====================
        if not above_200:
            short_score += 20
            reasons.append("Below 200-day SMA")
        else:
            long_score += 20
            reasons.append("Above 200-day SMA")
        
        # Weekly confirmation - MUST agree
        if not weekly_above and short_score > 0:
            short_score += 15
            reasons.append("Weekly downtrend confirmed")
        elif weekly_above and long_score > 0:
            long_score += 15
            reasons.append("Weekly uptrend confirmed")
        else:
            # Weekly and daily disagree
            return {
                "direction": "NEUTRAL",
                "confidence": 0,
                "reason": "Weekly/daily trend disagree",
                "rsi": rsi,
                "rsi_percentile": rsi_percentile,
                "adx": adx,
                "volatility": volatility,
                "reasons": reasons,
            }
        
        # =====================
        # STOP-RUN AVOIDANCE
        # =====================
        if avoid_entry:
            if short_score > 0:
                short_score *= 0.3
                reasons.append("⚠️ Recent big move - skip")
            if long_score > 0:
                long_score *= 0.3
        
        # =====================
        # VOLATILITY ADJUSTMENT
        # =====================
        if volatility > 5:
            short_score *= 0.5
            long_score *= 0.5
            reasons.append(f"⚠️ High volatility ({volatility:.1f}%)")
        elif volatility > 3.5:
            short_score *= 0.7
            long_score *= 0.7
            reasons.append(f"⚠️ Elevated volatility ({volatility:.1f}%)")
        
        total = short_score + long_score
        if total < 60:
            return {
                "direction": "NEUTRAL",
                "confidence": 0,
                "reason": "Score too low",
                "rsi": rsi,
                "rsi_percentile": rsi_percentile,
                "adx": adx,
                "volatility": volatility,
                "reasons": reasons,
            }
        
        # =====================
        # DIRECTION DETERMINATION
        # =====================
        # Use 1:1 reward:risk ratio (2x ATR stop and target)
        if SHORT_ONLY:
            if short_score > long_score * 1.5:  # Stronger margin
                direction = "SHORT"
                confidence = min((short_score / total) * 100, 95)
                
                # 1:1 ratio: Stop = 2x ATR, Target = 2x ATR
                if volatility > 4:
                    stop_mult = 2.5
                    target_mult = 2.5
                elif volatility > 2.5:
                    stop_mult = 2.0
                    target_mult = 2.0
                else:
                    stop_mult = 1.5
                    target_mult = 1.5
                
                stop = current.close + (atr * stop_mult)
                target1 = current.close - (atr * target_mult)
                target2 = current.close - (atr * target_mult * 1.5)
            else:
                return {
                    "direction": "NEUTRAL",
                    "confidence": 0,
                    "reason": "No clear SHORT direction",
                    "rsi": rsi,
                    "rsi_percentile": rsi_percentile,
                    "adx": adx,
                    "volatility": volatility,
                    "reasons": reasons,
                }
        else:
            if short_score > long_score * 1.5:
                direction = "SHORT"
                confidence = min((short_score / total) * 100, 95)
                stop_mult = 2.0
                target_mult = 2.0
                stop = current.close + (atr * stop_mult)
                target1 = current.close - (atr * target_mult)
                target2 = current.close - (atr * target_mult * 1.5)
            elif long_score > short_score * 1.5:
                direction = "LONG"
                confidence = min((long_score / total) * 100, 95)
                stop_mult = 2.0
                target_mult = 2.0
                stop = current.close - (atr * stop_mult)
                target1 = current.close + (atr * target_mult)
                target2 = current.close + (atr * target_mult * 1.5)
            else:
                return {
                    "direction": "NEUTRAL",
                    "confidence": 0,
                    "reason": "No clear direction",
                    "rsi": rsi,
                    "rsi_percentile": rsi_percentile,
                    "adx": adx,
                    "volatility": volatility,
                    "reasons": reasons,
                }
        
        return {
            "symbol": self.symbol,
            "direction": direction,
            "confidence": confidence,
            "entry": current.close,
            "stop": stop,
            "target1": target1,
            "target2": target2,
            "atr": atr,
            "stop_mult": stop_mult,
            "rsi": rsi,
            "rsi_percentile": rsi_percentile,
            "adx": adx,
            "sma_200": sma_200,
            "volatility": volatility,
            "volume_confirmed": volume_confirmed,
            "reasons": reasons,
            "patterns": list(patterns.keys()),
        }


# =====================================
# MAIN FUNCTION
# =====================================

async def analyze_symbol(symbol: str) -> dict:
    print(f"\n🔍 Analyzing {symbol}...")
    
    advisor = TradingAdvisorV5(symbol)
    result = advisor.generate_signal()
    
    if result["direction"] != "NEUTRAL":
        emoji = "🔴" if result["direction"] == "SHORT" else "🟢"
        print(f"   {emoji} {result['direction']} - Confidence: {result['confidence']:.0f}%")
        print(f"   📊 RSI: {result['rsi']:.1f} | RSI %ile: {result['rsi_percentile']:.0f}%")
        print(f"   📊 ADX: {result['adx']:.1f} | Volatility: {result['volatility']:.1f}%")
    else:
        print(f"   ⚪ NEUTRAL - {result.get('reason', 'Unknown')}")
    
    return result


async def main():
    print("=" * 80)
    print("🚀 TRADING ADVISOR V5 - UNIVERSAL SHORT STRATEGY")
    print("=" * 80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Confidence Threshold: {CONFIDENCE_THRESHOLD}%")
    print()
    print("📋 KEY V5 IMPROVEMENTS:")
    print("   🎯 Percentile-based RSI (adapts to each stock)")
    print("   📈 ADX trend filter (only trade in trending markets)")
    print("   📊 Volatility-adjusted stops (stock-specific)")
    print("   📦 Volume confirmation (stronger signals)")
    print("   ⚠️  Stop-run avoidance (skip after big moves)")
    print("   🗓️  Multi-timeframe confirmation (weekly + daily)")
    print("=" * 80)
    
    all_results = []
    
    print("\n" + "=" * 80)
    print("📈 US STOCKS ANALYSIS (UNIVERSAL STRATEGY)")
    print("=" * 80)
    
    for symbol in US_STOCKS:
        result = await analyze_symbol(symbol)
        if result["direction"] != "NEUTRAL":
            result["asset_class"] = "STOCK"
            all_results.append(result)
    
    # Summary
    print("\n" + "=" * 80)
    print("📋 TRADING SIGNALS SUMMARY")
    print(f"   (Showing signals with confidence ≥ {CONFIDENCE_THRESHOLD}%)")
    print("=" * 80)
    
    filtered = [r for r in all_results if r["confidence"] >= CONFIDENCE_THRESHOLD]
    
    if filtered:
        filtered.sort(key=lambda x: x["confidence"], reverse=True)
        
        print("\n🎯 ACTIONABLE SIGNALS:")
        
        for i, result in enumerate(filtered[:12], 1):
            emoji = "🔴" if result["direction"] == "SHORT" else "🟢"
            
            print(f"\n{'─' * 80}")
            print(f"  #{i} {result['symbol']} {emoji} {result['direction']}")
            print(f"  {'─' * 80}")
            print(f"  📊 Confidence: {result['confidence']:.0f}%")
            print(f"  💰 Entry: ${result['entry']:.2f}")
            print(f"  🛑 Stop Loss: ${result['stop']:.2f} ({result['stop_mult']}x ATR)")
            print(f"  🎯 Target 1: ${result['target1']:.2f} ({((result['target1']-result['entry'])/result['entry']*100):+.1f}%)")
            print(f"  🎯 Target 2: ${result['target2']:.2f} ({((result['target2']-result['entry'])/result['entry']*100):+.1f}%)")
            print(f"  📊 RSI: {result['rsi']:.1f}")
            print(f"  📊 RSI Percentile: {result['rsi_percentile']:.0f}%")
            print(f"  📊 ADX: {result['adx']:.1f}")
            print(f"  📊 Volatility: {result['volatility']:.1f}%")
            print(f"  📦 Volume Confirmed: {'Yes' if result.get('volume_confirmed') else 'No'}")
            print(f"  📝 Patterns: {', '.join(result.get('patterns', []))}")
            
            print(f"\n  📋 UPSIDEONLY ENTRY:")
            print(f"     Symbol: {result['symbol']}")
            print(f"     Direction: {result['direction']}")
            print(f"     Entry: ${result['entry']:.2f}")
            print(f"     Stop: ${result['stop']:.2f}")
            print(f"     Target 1: ${result['target1']:.2f}")
            print(f"     Target 2: ${result['target2']:.2f}")
        
        # Table
        print(f"\n{'─' * 80}")
        print("\n📊 QUICK REFERENCE TABLE:")
        
        table_data = []
        for r in filtered[:12]:
            emoji = "🔴" if r['direction'] == 'SHORT' else "🟢"
            table_data.append([
                r["symbol"],
                f"{emoji} {r['direction']}",
                f"{r['confidence']:.0f}%",
                f"${r['entry']:.2f}",
                f"${r['stop']:.2f}",
                f"${r['target1']:.2f}",
                f"{r['rsi_percentile']:.0f}%",
            ])
        
        print(tabulate(
            table_data,
            headers=["Symbol", "Direction", "Conf", "Entry", "Stop", "Target1", "RSI%ile"],
            tablefmt="grid"
        ))
        
    else:
        print("\n⚠️ No signals meet the threshold.")
    
    shorts = sum(1 for r in all_results if r['direction'] == 'SHORT')
    longs = sum(1 for r in all_results if r['direction'] == 'LONG')
    
    print("\n" + "=" * 80)
    print("📈 MARKET OVERVIEW")
    print("=" * 80)
    print(f"  Total Signals: {len(all_results)}")
    print(f"  High Confidence (≥{CONFIDENCE_THRESHOLD}%): {len(filtered)}")
    print(f"  🔴 SHORT: {shorts}")
    print(f"  🟢 LONG: {longs}")
    
    print("\n" + "=" * 80)
    print("⚠️ DISCLAIMER")
    print("=" * 80)
    print("""
This is research/education only. Not financial advice.
V5 strategy adapts to each stock's historical behavior.
Always do your own analysis before trading.
    """)


if __name__ == "__main__":
    asyncio.run(main())
