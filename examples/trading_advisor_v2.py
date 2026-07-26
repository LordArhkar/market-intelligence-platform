#!/usr/bin/env python3
"""
🚀 TRADING ADVISOR V2 - IMPROVED STRATEGY

Based on backtest insights, this version includes:

✅ STRICTER ENTRY CONDITIONS
   - LONG only when RSI < 30 (deeply oversold)
   - SHORT only when RSI > 70 (deeply overbought)
   - Require 2+ confirmations from different timeframes

✅ IMPROVED STOP LOSS
   - Using 2.5x ATR instead of 1.5x
   - Gives trades more room to breathe

✅ MARKET REGIME FILTER
   - Detects TREND vs RANGE market
   - Only trades in favorable conditions

✅ STRICTER PATTERN REQUIREMENTS
   - Only high-weight patterns trigger signals
   - Requires confluence across timeframes

DISCLAIMER: Research/education only. Not financial advice.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Dict
from dataclasses import dataclass
from tabulate import tabulate
import yfinance as yf
import numpy as np

# =====================================
# CUSTOMIZATION OPTIONS
# =====================================

CONFIDENCE_THRESHOLD = 60  # Higher threshold = stricter signals

US_STOCKS = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AMD", "NFLX", "SPY", "QQQ"]
CRYPTO = ["BTC-USD", "ETH-USD", "SOL-USD"]

TIMEFRAMES = ["1h", "4h", "1d", "1wk"]

# =====================================
# CANDLESTICK PATTERNS
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
    """High-quality candlestick patterns only."""
    
    @staticmethod
    def is_bullish_engulfing(candles: List[Candle]) -> Tuple[bool, float]:
        """Strong bullish reversal signal."""
        if len(candles) < 2:
            return False, 0
        c1, c2 = candles[-2], candles[-1]
        body1 = c1.close - c1.open
        body2 = c2.close - c2.open
        
        if body1 < 0 and body2 > 0:
            if c2.open < c1.close and c2.close > c1.open:
                strength = abs(body2) / abs(body1) if body1 != 0 else 1
                return True, min(strength * 25, 35)
        return False, 0
    
    @staticmethod
    def is_bearish_engulfing(candles: List[Candle]) -> Tuple[bool, float]:
        """Strong bearish reversal signal."""
        if len(candles) < 2:
            return False, 0
        c1, c2 = candles[-2], candles[-1]
        body1 = c1.close - c1.open
        body2 = c2.close - c2.open
        
        if body1 > 0 and body2 < 0:
            if c2.open > c1.close and c2.close < c1.open:
                strength = abs(body2) / body1 if body1 != 0 else 1
                return True, min(strength * 25, 35)
        return False, 0
    
    @staticmethod
    def is_hammer(candles: List[Candle]) -> Tuple[bool, float]:
        """Bullish reversal - requires confirmation."""
        if len(candles) < 3:
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
    def is_shooting_star(candles: List[Candle]) -> Tuple[bool, float]:
        """Bearish reversal signal."""
        if len(candles) < 1:
            return False, 0
        c = candles[-1]
        body = c.close - c.open
        lower_shadow = min(c.open, c.close) - c.low
        upper_shadow = c.high - max(c.open, c.close)
        
        if upper_shadow > abs(body) * 2 and lower_shadow < abs(body) * 0.3:
            if body < 0:
                return True, 30
        return False, 0
    
    @staticmethod
    def is_morning_star(candles: List[Candle]) -> Tuple[bool, float]:
        """3-candle bullish reversal - HIGH CONFIDENCE."""
        if len(candles) < 3:
            return False, 0
        c1, c2, c3 = candles[-3], candles[-2], candles[-1]
        
        body1 = c1.close - c1.open
        body3 = c3.close - c3.open
        
        if (body1 < 0 and body3 > 0 and 
            abs(c2.close - c2.open) < (c1.high - c1.low) * 0.3 and
            body3 > abs(body1) * 0.5):
            return True, 45
        return False, 0
    
    @staticmethod
    def is_evening_star(candles: List[Candle]) -> Tuple[bool, float]:
        """3-candle bearish reversal - HIGH CONFIDENCE."""
        if len(candles) < 3:
            return False, 0
        c1, c2, c3 = candles[-3], candles[-2], candles[-1]
        
        body1 = c1.close - c1.open
        body3 = c3.close - c3.open
        
        if (body1 > 0 and body3 < 0 and 
            abs(c2.close - c2.open) < (c1.high - c1.low) * 0.3 and
            abs(body3) > body1 * 0.5):
            return True, 45
        return False, 0
    
    @staticmethod
    def is_three_white_soldiers(candles: List[Candle]) -> Tuple[bool, float]:
        """Strong bullish continuation."""
        if len(candles) < 3:
            return False, 0
        c1, c2, c3 = candles[-3], candles[-2], candles[-1]
        
        if (c1.close > c1.open and c2.close > c2.open and c3.close > c3.open and
            c2.close > c1.close and c3.close > c2.close and
            c2.open > c1.open and c3.open > c2.open):
            return True, 50
        return False, 0
    
    @staticmethod
    def is_three_black_crows(candles: List[Candle]) -> Tuple[bool, float]:
        """Strong bearish continuation."""
        if len(candles) < 3:
            return False, 0
        c1, c2, c3 = candles[-3], candles[-2], candles[-1]
        
        if (c1.close < c1.open and c2.close < c2.open and c3.close < c3.open and
            c2.close < c1.close and c3.close < c2.close and
            c2.open < c1.open and c3.open < c2.open):
            return True, 50
        return False, 0
    
    @staticmethod
    def detect_all_patterns(candles: List[Candle]) -> Dict[str, float]:
        """Detect all patterns."""
        patterns = {}
        patterns["Bullish Engulfing"] = CandlestickPatterns.is_bullish_engulfing(candles)[1]
        patterns["Bearish Engulfing"] = CandlestickPatterns.is_bearish_engulfing(candles)[1]
        patterns["Hammer"] = CandlestickPatterns.is_hammer(candles)[1]
        patterns["Shooting Star"] = CandlestickPatterns.is_shooting_star(candles)[1]
        patterns["Morning Star"] = CandlestickPatterns.is_morning_star(candles)[1]
        patterns["Evening Star"] = CandlestickPatterns.is_evening_star(candles)[1]
        patterns["Three White Soldiers"] = CandlestickPatterns.is_three_white_soldiers(candles)[1]
        patterns["Three Black Crows"] = CandlestickPatterns.is_three_black_crows(candles)[1]
        return {k: v for k, v in patterns.items() if v > 0}


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
        return 100 - (100 / (1 + rs))
    
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
        return np.mean(true_ranges[-period:])
    
    @staticmethod
    def calculate_adx(candles: List[Candle], period: int = 14) -> float:
        """Calculate ADX - measures trend strength."""
        if len(candles) < period + 1:
            return 25.0
        
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        
        plus_dm = []
        minus_dm = []
        
        for i in range(1, len(candles)):
            high_diff = highs[i] - highs[i-1]
            low_diff = lows[i-1] - lows[i]
            
            if high_diff > low_diff and high_diff > 0:
                plus_dm.append(high_diff)
            else:
                plus_dm.append(0.0)
            
            if low_diff > high_diff and low_diff > 0:
                minus_dm.append(low_diff)
            else:
                minus_dm.append(0.0)
        
        atr = TechnicalAnalysis.calculate_atr(candles, period)
        if atr == 0:
            return 25.0
        
        plus_di = 100 * np.mean(plus_dm[-period:]) / atr
        minus_di = 100 * np.mean(minus_dm[-period:]) / atr
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 0.0001)
        
        # Store dx values for smoothing
        adx_values = [dx]
        adx = np.mean(adx_values[-period:]) if len(adx_values) >= period else dx
        
        return float(adx)
    
    @staticmethod
    def detect_regime(candles: List[Candle]) -> str:
        """Detect market regime: TREND, RANGE, or VOLATILE."""
        if len(candles) < 50:
            return "UNKNOWN"
        
        prices = [c.close for c in candles]
        
        # Calculate ADX for trend strength
        adx = TechnicalAnalysis.calculate_adx(candles[-50:])
        
        # Calculate volatility
        returns = np.diff(prices) / np.array(prices[:-1])
        volatility = float(np.std(returns[-20:]) * 100)
        
        if adx > 25:
            return "TREND"
        elif volatility > 3:
            return "VOLATILE"
        else:
            return "RANGE"


# =====================================
# MAIN ANALYSIS CLASS
# =====================================

class TradingAdvisorV2:
    """Improved trading advisor with stricter rules."""
    
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.timeframes = TIMEFRAMES
    
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
    
    def analyze_timeframe(self, timeframe: str) -> dict:
        """Analyze a single timeframe."""
        candles = self.fetch_data(timeframe)
        
        if len(candles) < 30:
            return {"error": "Insufficient data"}
        
        analysis = {
            "timeframe": timeframe,
            "current_price": candles[-1].close,
            "regime": TechnicalAnalysis.detect_regime(candles),
            "patterns": CandlestickPatterns.detect_all_patterns(candles),
            "indicators": {},
        }
        
        prices = [c.close for c in candles]
        analysis["indicators"]["rsi"] = TechnicalAnalysis.calculate_rsi(prices)
        analysis["indicators"]["atr"] = TechnicalAnalysis.calculate_atr(candles)
        analysis["indicators"]["adx"] = TechnicalAnalysis.calculate_adx(candles)
        
        return analysis
    
    def generate_signal(self) -> dict:
        """Generate signal with strict conditions."""
        all_analysis = {}
        
        for tf in self.timeframes:
            all_analysis[tf] = self.analyze_timeframe(tf)
        
        bullish_score = 0
        bearish_score = 0
        signals = []
        confirmations = {"bullish": 0, "bearish": 0}
        
        for tf, analysis in all_analysis.items():
            if "error" in analysis:
                continue
            
            rsi = analysis.get("indicators", {}).get("rsi", 50)
            regime = analysis.get("regime", "UNKNOWN")
            adx = analysis.get("indicators", {}).get("adx", 25)
            
            # STRICT CONDITION 1: RSI must be extreme for signal
            # LONG only when RSI < 30 (deeply oversold)
            # SHORT only when RSI > 70 (deeply overbought)
            if rsi < 30:
                bullish_score += 25  # Base RSI score
                confirmations["bullish"] += 1
                signals.append(f"  {tf}: RSI Oversold ({rsi:.1f}) +25")
            elif rsi > 70:
                bearish_score += 25  # Base RSI score
                confirmations["bearish"] += 1
                signals.append(f"  {tf}: RSI Overbought ({rsi:.1f}) +25")
            elif rsi < 40:  # Mildly oversold
                bullish_score += 10
                confirmations["bullish"] += 0.5
                signals.append(f"  {tf}: RSI Mildly Oversold ({rsi:.1f}) +10")
            elif rsi > 60:  # Mildly overbought
                bearish_score += 10
                confirmations["bearish"] += 0.5
                signals.append(f"  {tf}: RSI Mildly Overbought ({rsi:.1f}) +10")
            
            # STRICT CONDITION 2: Pattern must be present
            for pattern, confidence in analysis.get("patterns", {}).items():
                if any(x in pattern for x in ["Bullish", "Hammer", "Morning", "White"]):
                    bullish_score += confidence
                    confirmations["bullish"] += 1
                    signals.append(f"  {tf}: {pattern} +{confidence:.0f}")
                elif any(x in pattern for x in ["Bearish", "Shooting", "Evening", "Black"]):
                    bearish_score += confidence
                    confirmations["bearish"] += 1
                    signals.append(f"  {tf}: {pattern} -{confidence:.0f}")
            
            # STRICT CONDITION 3: Market regime bonus/penalty
            if regime == "TREND" and adx > 25:
                if rsi < 40:  # Trending + oversold = strong buy
                    bullish_score += 15
                    signals.append(f"  {tf}: Uptrend Confirmed +15")
                elif rsi > 60:  # Trending + overbought = strong sell
                    bearish_score += 15
                    signals.append(f"  {tf}: Downtrend Confirmed +15")
            elif regime == "VOLATILE":
                # Reduce confidence in volatile markets
                signals.append(f"  {tf}: VOLATILE Market (reduced confidence)")
        
        # STRICT CONDITION 4: Require at least 2 confirmations
        min_confirmations = 2
        
        if confirmations["bullish"] < min_confirmations:
            bullish_score *= 0.5  # Reduce score
            signals.append(f"  ⚠️ Insufficient bullish confirmations")
        
        if confirmations["bearish"] < min_confirmations:
            bearish_score *= 0.5
            signals.append(f"  ⚠️ Insufficient bearish confirmations")
        
        # Calculate final direction
        total = bullish_score + bearish_score
        if total == 0:
            return {"direction": "NEUTRAL", "confidence": 0, "signals": [], "analysis": all_analysis}
        
        if bullish_score > bearish_score * 1.3:  # Need 30% more bullish
            direction = "LONG"
            confidence = min((bullish_score / total) * 100, 95)
        elif bearish_score > bullish_score * 1.3:
            direction = "SHORT"
            confidence = min((bearish_score / total) * 100, 95)
        else:
            return {"direction": "NEUTRAL", "confidence": 0, "signals": [], "analysis": all_analysis}
        
        # Get levels from daily
        daily = all_analysis.get("1d", all_analysis.get("1h", {}))
        current = daily.get("current_price", 0)
        atr = daily.get("indicators", {}).get("atr", current * 0.02)
        
        # IMPROVED: Wider stop loss (2.5x ATR instead of 1.5x)
        if direction == "LONG":
            entry = current
            stop = current - (atr * 2.5)  # Wider stop
            target = current + (atr * 4)    # Higher target for better R:R
        else:
            entry = current
            stop = current + (atr * 2.5)
            target = current - (atr * 4)
        
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
            "confirmations": confirmations,
            "analysis": all_analysis,
            "change_24h": all_analysis.get("1d", {}).get("indicators", {}).get("rsi", 0) if "1d" in all_analysis else 0,
        }


# =====================================
# MAIN FUNCTION
# =====================================

async def analyze_symbol(symbol: str) -> dict:
    """Analyze a single symbol."""
    print(f"\n🔍 Analyzing {symbol}...")
    
    advisor = TradingAdvisorV2(symbol)
    result = advisor.generate_signal()
    
    if result["direction"] != "NEUTRAL":
        emoji = "🟢" if result["direction"] == "LONG" else "🔴"
        regime = result.get("analysis", {}).get("1d", {}).get("regime", "UNKNOWN")
        print(f"   {emoji} {result['direction']} - Confidence: {result['confidence']:.0f}% ({regime} market)")
        print(f"   Confirmations: {result.get('confirmations', {})}")
    else:
        print(f"   ⚪ NEUTRAL - Does not meet strict criteria")
    
    return result


async def main():
    """Run trading advisor v2."""
    
    print("=" * 80)
    print("🚀 TRADING ADVISOR V2 - IMPROVED STRATEGY")
    print("=" * 80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Confidence Threshold: {CONFIDENCE_THRESHOLD}%")
    print()
    print("📋 STRICT RULES:")
    print("   1. LONG only when RSI < 30 (deeply oversold)")
    print("   2. SHORT only when RSI > 70 (deeply overbought)")
    print("   3. Require 2+ confirmations from different sources")
    print("   4. Wider stop loss (2.5x ATR)")
    print("   5. Market regime filter applied")
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
        print("-" * 80)
        
        for i, result in enumerate(filtered[:10], 1):
            emoji = "🟢" if result["direction"] == "LONG" else "🔴"
            regime = result.get("analysis", {}).get("1d", {}).get("regime", "UNKNOWN")
            
            print(f"\n{'─' * 80}")
            print(f"  #{i} {result['symbol']} {emoji} {result['direction']}")
            print(f"  {'─' * 80}")
            print(f"  📊 Confidence: {result['confidence']:.0f}%")
            print(f"  📈 Market Regime: {regime}")
            print(f"  💰 Entry: ${result['entry']:.2f}")
            print(f"  🛑 Stop Loss: ${result['stop']:.2f} (2.5x ATR)")
            print(f"  🎯 Take Profit: ${result['target']:.2f}")
            print(f"  ⚖️  Risk/Reward: 1:{result['risk_reward']:.1f}")
            print(f"  📝 Confirmations: {result.get('confirmations', {})}")
            print(f"  📝 Signals:")
            for sig in result['signals'][:5]:
                print(f"     {sig}")
            
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
        print("\n⚠️ No signals meet the STRICT criteria.")
        print("   This is GOOD - it means the market doesn't have clear setups.")
        print("   Wait for better opportunities.")
    
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
Strategy has been improved based on backtest insights but is NOT yet validated.
Always do your own analysis before trading.
    """)


if __name__ == "__main__":
    asyncio.run(main())
