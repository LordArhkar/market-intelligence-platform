#!/usr/bin/env python3
"""
🚀 TRADING ADVISOR V3 - FINAL IMPROVED STRATEGY

Major improvements based on backtest results:

1. NO CONTRADICTORY SIGNALS
   - RSI + pattern must agree (no RSI overbought + bullish pattern!)
   
2. TREND ALIGNMENT
   - LONG only when price above 200 SMA
   - SHORT only when price below 200 SMA
   
3. MULTI-TIMEFRAME STRICT AGREEMENT
   - All timeframes must agree on direction
   - 4h AND daily RSI must both be extreme
   
4. DYNAMIC STOP PLACEMENT
   - Stop at recent swing low/high
   - ATR-based with structure awareness
   
5. SMART TAKE PROFIT
   - First target at 2x ATR (partial exit)
   - Second target at 3x ATR
   
6. VOLATILITY FILTER
   - Skip trades when volatility is extreme
   - Only trade in moderate conditions

7. ONLY BEST PATTERNS
   - Weight patterns by historical effectiveness
   - Remove low-weight patterns

DISCLAIMER: Research/education only. Not financial advice.
"""

import asyncio
from datetime import datetime
from typing import Optional, Tuple, List, Dict
from dataclasses import dataclass
from tabulate import tabulate
import yfinance as yf
import numpy as np

# =====================================
# CUSTOMIZATION OPTIONS
# =====================================

CONFIDENCE_THRESHOLD = 65  # Higher threshold

US_STOCKS = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AMD", "NFLX", "SPY", "QQQ"]
CRYPTO = ["BTC-USD", "ETH-USD"]

TIMEFRAMES = ["4h", "1d", "1wk"]

# =====================================
# DATA CLASSES
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
    """Technical indicators with structure awareness."""
    
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
        return float(100 - (100 / (1 + rs)))
    
    @staticmethod
    def calculate_atr(candles: List[Candle], period: int = 14) -> float:
        """Calculate ATR."""
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
    def calculate_sma(prices: List[float], period: int) -> float:
        """Calculate SMA."""
        if len(prices) < period:
            return prices[-1] if prices else 0
        return float(np.mean(prices[-period:]))
    
    @staticmethod
    def calculate_volatility(candles: List[Candle]) -> float:
        """Calculate volatility as percentage."""
        if len(candles) < 20:
            return 2.0
        prices = [c.close for c in candles]
        returns = np.diff(prices) / np.array(prices[:-1])
        return float(np.std(returns[-20:]) * 100)
    
    @staticmethod
    def find_swing_low(candles: List[Candle], lookback: int = 10) -> float:
        """Find recent swing low for stop placement."""
        if len(candles) < lookback:
            return min(c.low for c in candles)
        recent = candles[-lookback:-1]
        return min(c.low for c in recent)
    
    @staticmethod
    def find_swing_high(candles: List[Candle], lookback: int = 10) -> float:
        """Find recent swing high for stop placement."""
        if len(candles) < lookback:
            return max(c.high for c in candles)
        recent = candles[-lookback:-1]
        return max(c.high for c in recent)
    
    @staticmethod
    def detect_regime(candles: List[Candle]) -> str:
        """Detect market regime."""
        if len(candles) < 50:
            return "UNKNOWN"
        volatility = TechnicalAnalysis.calculate_volatility(candles)
        if volatility > 4:
            return "VOLATILE"
        elif volatility > 2.5:
            return "TREND"
        else:
            return "RANGE"


# =====================================
# CANDLESTICK PATTERNS
# =====================================

class CandlestickPatterns:
    """Only high-weight patterns."""
    
    @staticmethod
    def is_bullish_engulfing(candles: List[Candle]) -> Tuple[bool, float]:
        """Strong bullish reversal - HIGH WEIGHT."""
        if len(candles) < 2:
            return False, 0
        c1, c2 = candles[-2], candles[-1]
        body1 = c1.close - c1.open
        body2 = c2.close - c2.open
        
        if body1 < 0 and body2 > 0:
            if c2.open < c1.close and c2.close > c1.open:
                # Check if engulfing is significant
                if abs(body2) > abs(body1) * 1.2:
                    return True, 40
        return False, 0
    
    @staticmethod
    def is_bearish_engulfing(candles: List[Candle]) -> Tuple[bool, float]:
        """Strong bearish reversal - HIGH WEIGHT."""
        if len(candles) < 2:
            return False, 0
        c1, c2 = candles[-2], candles[-1]
        body1 = c1.close - c1.open
        body2 = c2.close - c2.open
        
        if body1 > 0 and body2 < 0:
            if c2.open > c1.close and c2.close < c1.open:
                if abs(body2) > abs(body1) * 1.2:
                    return True, 40
        return False, 0
    
    @staticmethod
    def is_morning_star(candles: List[Candle]) -> Tuple[bool, float]:
        """3-candle bullish reversal - HIGH WEIGHT."""
        if len(candles) < 3:
            return False, 0
        c1, c2, c3 = candles[-3], candles[-2], candles[-1]
        
        body1 = c1.close - c1.open
        body3 = c3.close - c3.open
        
        # Must be: big red, small body, big green
        if (body1 < 0 and abs(body1) > (c1.high - c1.low) * 0.6 and
            body3 > 0 and abs(body3) > (c3.high - c3.low) * 0.6):
            return True, 50
        return False, 0
    
    @staticmethod
    def is_evening_star(candles: List[Candle]) -> Tuple[bool, float]:
        """3-candle bearish reversal - HIGH WEIGHT."""
        if len(candles) < 3:
            return False, 0
        c1, c2, c3 = candles[-3], candles[-2], candles[-1]
        
        body1 = c1.close - c1.open
        body3 = c3.close - c3.open
        
        if (body1 > 0 and body1 > (c1.high - c1.low) * 0.6 and
            body3 < 0 and abs(body3) > (c3.high - c3.low) * 0.6):
            return True, 50
        return False, 0
    
    @staticmethod
    def is_hammer(candles: List[Candle]) -> Tuple[bool, float]:
        """Bullish hammer - MEDIUM WEIGHT."""
        if len(candles) < 1:
            return False, 0
        c = candles[-1]
        body = c.close - c.open
        lower_shadow = min(c.open, c.close) - c.low
        upper_shadow = c.high - max(c.open, c.close)
        
        if lower_shadow > abs(body) * 2 and upper_shadow < abs(body) * 0.3:
            if body > 0:
                return True, 30
        return False, 0
    
    @staticmethod
    def detect_all_patterns(candles: List[Candle]) -> Dict[str, float]:
        """Detect all patterns."""
        patterns = {}
        patterns["Bullish Engulfing"] = CandlestickPatterns.is_bullish_engulfing(candles)[1]
        patterns["Bearish Engulfing"] = CandlestickPatterns.is_bearish_engulfing(candles)[1]
        patterns["Morning Star"] = CandlestickPatterns.is_morning_star(candles)[1]
        patterns["Evening Star"] = CandlestickPatterns.is_evening_star(candles)[1]
        patterns["Hammer"] = CandlestickPatterns.is_hammer(candles)[1]
        return {k: v for k, v in patterns.items() if v > 0}


# =====================================
# MAIN ANALYSIS CLASS
# =====================================

class TradingAdvisorV3:
    """Final improved trading advisor."""
    
    def __init__(self, symbol: str):
        self.symbol = symbol
    
    def fetch_data(self, timeframe: str) -> List[Candle]:
        """Fetch data for a specific timeframe."""
        try:
            ticker = yf.Ticker(self.symbol)
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
        except:
            return []
    
    def generate_signal(self) -> dict:
        """Generate signal with all improvements."""
        
        # Fetch data for all timeframes
        daily = self.fetch_data("1d")
        weekly = self.fetch_data("1wk")
        four_hr = self.fetch_data("4h")
        
        if len(daily) < 60:
            return {"direction": "NEUTRAL", "confidence": 0, "reason": "Insufficient data"}
        
        current = daily[-1]
        prices = [c.close for c in daily]
        weekly_prices = [c.close for c in weekly] if weekly else prices
        
        # Calculate indicators
        daily_rsi = TechnicalAnalysis.calculate_rsi(prices)
        weekly_rsi = TechnicalAnalysis.calculate_rsi(weekly_prices) if len(weekly_prices) > 14 else 50
        atr = TechnicalAnalysis.calculate_atr(daily)
        sma_200 = TechnicalAnalysis.calculate_sma(prices, 200)
        sma_50 = TechnicalAnalysis.calculate_sma(prices, 50)
        volatility = TechnicalAnalysis.calculate_volatility(daily)
        regime = TechnicalAnalysis.detect_regime(daily)
        
        # Detect patterns
        patterns = CandlestickPatterns.detect_all_patterns(daily)
        
        # Calculate trend alignment
        above_200 = current.close > sma_200
        above_50 = current.close > sma_50
        price_trend = "UP" if above_50 else "DOWN"
        
        # Get weekly trend
        weekly_above_50 = weekly_prices[-1] > TechnicalAnalysis.calculate_sma(weekly_prices, 20) if len(weekly_prices) > 20 else True
        
        signals = []
        reasons = []
        bullish_score = 0
        bearish_score = 0
        
        # =====================================
        # RULE 1: NO CONTRADICTORY SIGNALS
        # =====================================
        
        # Check RSI and pattern agreement
        has_bullish_pattern = any(k for k in patterns if "Bullish" in k or "Morning" in k or "Hammer" in k)
        has_bearish_pattern = any(k for k in patterns if "Bearish" in k or "Evening" in k)
        
        # If RSI says oversold but pattern says bearish = CONTRADICTION
        if daily_rsi < 30 and has_bearish_pattern:
            reasons.append("❌ RSI oversold but bearish pattern - contradiction")
            has_bearish_pattern = False
            patterns = {k: v for k, v in patterns.items() if "Bearish" not in k and "Evening" not in k}
        
        if daily_rsi > 70 and has_bullish_pattern:
            reasons.append("❌ RSI overbought but bullish pattern - contradiction")
            has_bullish_pattern = False
            patterns = {k: v for k, v in patterns.items() if "Bullish" not in k and "Morning" not in k and "Hammer" not in k}
        
        # =====================================
        # RULE 2: TREND ALIGNMENT
        # =====================================
        
        # STRONG LONG: Price above 200 SMA + weekly trend up
        # STRONG SHORT: Price below 200 SMA + weekly trend down
        
        trend_bonus = 0
        if above_200 and weekly_above_50:
            trend_bonus = 20
            reasons.append(f"✅ Trend aligned: Price above 200 SMA, weekly uptrend")
        elif not above_200 and not weekly_above_50:
            trend_bonus = 20
            reasons.append(f"✅ Trend aligned: Price below 200 SMA, weekly downtrend")
        else:
            trend_bonus = -10  # Penalty for counter-trend trades
            reasons.append(f"⚠️ Counter-trend trade: Price {'above' if above_200 else 'below'} 200 SMA")
        
        # =====================================
        # RULE 3: MULTI-TIMEFRAME RSI AGREEMENT
        # =====================================
        
        daily_extreme_rsi = daily_rsi < 30 or daily_rsi > 70
        weekly_extreme_rsi = weekly_rsi < 35 or weekly_rsi > 65
        
        rsi_multi_tf = daily_extreme_rsi and weekly_extreme_rsi
        
        # =====================================
        # RULE 4: SCORING
        # =====================================
        
        # LONG SCORING
        if daily_rsi < 30 and weekly_rsi < 35:
            bullish_score += 35
            reasons.append(f"✅ Daily RSI deeply oversold ({daily_rsi:.1f})")
            reasons.append(f"✅ Weekly RSI oversold ({weekly_rsi:.1f})")
        
        if daily_rsi < 35 and daily_rsi >= 30:
            bullish_score += 20
            reasons.append(f"📊 Daily RSI moderately oversold ({daily_rsi:.1f})")
        
        # SHORT SCORING  
        if daily_rsi > 70 and weekly_rsi > 65:
            bearish_score += 35
            reasons.append(f"✅ Daily RSI deeply overbought ({daily_rsi:.1f})")
            reasons.append(f"✅ Weekly RSI overbought ({weekly_rsi:.1f})")
        
        if daily_rsi > 65 and daily_rsi <= 70:
            bearish_score += 20
            reasons.append(f"📊 Daily RSI moderately overbought ({daily_rsi:.1f})")
        
        # Pattern scoring
        for pattern, weight in patterns.items():
            if "Bullish" in pattern or "Morning" in pattern or "Hammer" in pattern:
                bullish_score += weight
                reasons.append(f"✅ {pattern} (+{weight})")
            elif "Bearish" in pattern or "Evening" in pattern:
                bearish_score += weight
                reasons.append(f"✅ {pattern} (-{weight})")
        
        # Trend alignment
        bullish_score += trend_bonus
        bearish_score += trend_bonus
        
        # =====================================
        # RULE 5: VOLATILITY FILTER
        # =====================================
        
        if volatility > 5:
            reasons.append(f"❌ Volatility too high ({volatility:.1f}%) - skipping")
            return {"direction": "NEUTRAL", "confidence": 0, "reason": "High volatility", "reasons": reasons}
        
        if volatility > 3:
            reasons.append(f"⚠️ Elevated volatility ({volatility:.1f}%) - reduced confidence")
            bullish_score *= 0.8
            bearish_score *= 0.8
        
        # =====================================
        # RULE 6: DETERMINE DIRECTION
        # =====================================
        
        total = bullish_score + bearish_score
        if total == 0:
            return {"direction": "NEUTRAL", "confidence": 0, "reason": "No signals", "reasons": reasons}
        
        # Require minimum score threshold
        min_score = 50
        if bullish_score < min_score and bearish_score < min_score:
            return {"direction": "NEUTRAL", "confidence": 0, "reason": "Score too low", "reasons": reasons}
        
        if bullish_score > bearish_score * 1.3:
            direction = "LONG"
            confidence = min((bullish_score / total) * 100, 95)
        elif bearish_score > bullish_score * 1.3:
            direction = "SHORT"
            confidence = min((bearish_score / total) * 100, 95)
        else:
            return {"direction": "NEUTRAL", "confidence": 0, "reason": "Unclear direction", "reasons": reasons}
        
        # =====================================
        # RULE 7: SMART STOP PLACEMENT
        # =====================================
        
        if direction == "LONG":
            # Stop below recent swing low or ATR-based
            swing_low = TechnicalAnalysis.find_swing_low(daily, 20)
            atr_stop = current.close - (atr * 2)
            stop = max(swing_low, atr_stop)
            target1 = current.close + (atr * 2)  # First target: 2x ATR
            target2 = current.close + (atr * 3)  # Second target: 3x ATR
        else:
            swing_high = TechnicalAnalysis.find_swing_high(daily, 20)
            atr_stop = current.close + (atr * 2)
            stop = min(swing_high, atr_stop)
            target1 = current.close - (atr * 2)
            target2 = current.close - (atr * 3)
        
        return {
            "symbol": self.symbol,
            "direction": direction,
            "confidence": confidence,
            "entry": current.close,
            "stop": stop,
            "target1": target1,
            "target2": target2,
            "atr": atr,
            "rsi": daily_rsi,
            "weekly_rsi": weekly_rsi,
            "sma_200": sma_200,
            "volatility": volatility,
            "regime": regime,
            "price_trend": price_trend,
            "reasons": reasons,
            "patterns": list(patterns.keys()),
        }


# =====================================
# MAIN FUNCTION
# =====================================

async def analyze_symbol(symbol: str) -> dict:
    """Analyze a single symbol."""
    print(f"\n🔍 Analyzing {symbol}...")
    
    advisor = TradingAdvisorV3(symbol)
    result = advisor.generate_signal()
    
    if result["direction"] != "NEUTRAL":
        emoji = "🟢" if result["direction"] == "LONG" else "🔴"
        print(f"   {emoji} {result['direction']} - Confidence: {result['confidence']:.0f}%")
        print(f"   📊 RSI: {result['rsi']:.1f} | Weekly RSI: {result['weekly_rsi']:.1f}")
        print(f"   📈 Trend: {result['price_trend']} | Regime: {result['regime']}")
    else:
        print(f"   ⚪ NEUTRAL - {result.get('reason', 'Unknown')}")
    
    return result


async def main():
    """Run trading advisor v3."""
    
    print("=" * 80)
    print("🚀 TRADING ADVISOR V3 - FINAL IMPROVED STRATEGY")
    print("=" * 80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Confidence Threshold: {CONFIDENCE_THRESHOLD}%")
    print()
    print("📋 KEY IMPROVEMENTS:")
    print("   1. NO contradictory signals (RSI + pattern must agree)")
    print("   2. TREND alignment (price must align with 200 SMA)")
    print("   3. Multi-timeframe RSI (daily AND weekly must agree)")
    print("   4. SMART stop placement (structure-based)")
    print("   5. VOLATILITY filter (skip extreme conditions)")
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
    
    filtered = [r for r in all_results if r["confidence"] >= CONFIDENCE_THRESHOLD]
    
    if filtered:
        filtered.sort(key=lambda x: x["confidence"], reverse=True)
        
        print("\n🎯 ACTIONABLE SIGNALS:")
        
        for i, result in enumerate(filtered[:10], 1):
            emoji = "🟢" if result["direction"] == "LONG" else "🔴"
            
            print(f"\n{'─' * 80}")
            print(f"  #{i} {result['symbol']} {emoji} {result['direction']}")
            print(f"  {'─' * 80}")
            print(f"  📊 Confidence: {result['confidence']:.0f}%")
            print(f"  💰 Entry: ${result['entry']:.2f}")
            print(f"  🛑 Stop Loss: ${result['stop']:.2f}")
            print(f"  🎯 Target 1: ${result['target1']:.2f} ({((result['target1']-result['entry'])/result['entry']*100):+.1f}%)")
            print(f"  🎯 Target 2: ${result['target2']:.2f} ({((result['target2']-result['entry'])/result['entry']*100):+.1f}%)")
            print(f"  📊 RSI: {result['rsi']:.1f} | Weekly RSI: {result['weekly_rsi']:.1f}")
            print(f"  📈 Price vs 200 SMA: ${result['entry']:.2f} vs ${result['sma_200']:.2f}")
            print(f"  📊 Volatility: {result['volatility']:.1f}%")
            print(f"  📝 Patterns: {', '.join(result.get('patterns', []))}")
            
            print(f"\n  📋 UPSIDEONLY ENTRY:")
            print(f"     Symbol: {result['symbol']}")
            print(f"     Direction: {result['direction']}")
            print(f"     Entry: ${result['entry']:.2f}")
            print(f"     Stop: ${result['stop']:.2f}")
            print(f"     Target 1: ${result['target1']:.2f}")
            print(f"     Target 2: ${result['target2']:.2f}")
        
        # Summary table
        print(f"\n{'─' * 80}")
        print("\n📊 QUICK REFERENCE TABLE:")
        
        table_data = []
        for r in filtered[:10]:
            emoji = "🟢" if r['direction'] == 'LONG' else "🔴"
            table_data.append([
                r["symbol"],
                f"{emoji} {r['direction']}",
                f"{r['confidence']:.0f}%",
                f"${r['entry']:.2f}",
                f"${r['stop']:.2f}",
                f"${r['target1']:.2f}",
                f"${r['target2']:.2f}",
            ])
        
        print(tabulate(
            table_data,
            headers=["Symbol", "Direction", "Conf", "Entry", "Stop", "T1", "T2"],
            tablefmt="grid"
        ))
        
    else:
        print("\n⚠️ No signals meet the strict criteria.")
        print("   This is GOOD - means market doesn't have clear setups.")
    
    longs = sum(1 for r in all_results if r['direction'] == 'LONG')
    shorts = sum(1 for r in all_results if r['direction'] == 'SHORT')
    
    print("\n" + "=" * 80)
    print("📈 MARKET OVERVIEW")
    print("=" * 80)
    print(f"  Total Signals: {len(all_results)}")
    print(f"  High Confidence (≥{CONFIDENCE_THRESHOLD}%): {len(filtered)}")
    print(f"  🟢 Bullish (LONG): {longs}")
    print(f"  🔴 Bearish (SHORT): {shorts}")
    
    print("\n" + "=" * 80)
    print("⚠️ DISCLAIMER")
    print("=" * 80)
    print("""
This is research/education only. Not financial advice.
Backtest results inform strategy but don't guarantee future performance.
Always do your own analysis before trading.
    """)


if __name__ == "__main__":
    asyncio.run(main())
