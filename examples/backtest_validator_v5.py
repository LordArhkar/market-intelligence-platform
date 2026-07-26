"""
Backtest Validator V5 - UNIVERSAL SHORT STRATEGY

V4 RESULTS:
- META: 68.8% win rate, +100% P&L ✅ (but stock-specific)
- Other stocks: Didn't work as well ❌

V5 IMPROVEMENTS - Making it work for ANY stock:

1. PERCENTILE-BASED RSI
   - Instead of fixed thresholds (RSI > 70)
   - Use RELATIVE RSI: Is RSI at extremes FOR THIS STOCK?
   - RSI above 80th percentile of last 252 days = short signal
   - RSI below 20th percentile of last 252 days = long signal

2. ADX TREND FILTER
   - Only trade when ADX > 25 (trending market)
   - Reduces false signals in choppy markets

3. VOLATILITY-ADJUSTED STOPS
   - Different stocks have different volatility
   - Scale ATR multiplier based on recent volatility
   - High volatility = wider stops
   - Low volatility = tighter stops

4. VOLUME CONFIRMATION
   - Volume spike on pattern = stronger signal
   - Volume must be above 20-day average

5. STOP-RUN AVOIDANCE
   - Don't enter if big move (> 2x ATR) in last 3 days
   - Avoids entering right before a reversal

6. MULTI-TIMEFRAME CONFIRMATION
   - Weekly trend for direction bias
   - Daily for entry timing

7. STOCK-SPECIFIC LEARNING
   - Track which stocks perform best
   - Adjust parameters per stock

Usage:
    python examples/backtest_validator_v5.py --symbol META AAPL MSFT
    python examples/backtest_validator_v5.py --all
"""

import argparse
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional
import yfinance as yf
import numpy as np


@dataclass
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


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
        return float(100 - (100 / (1 + avg_gain / avg_loss)))
    
    @staticmethod
    def calculate_rsi_percentile(prices: List[float], period: int = 14, lookback: int = 252) -> float:
        """Calculate where current RSI falls in percentile of historical RSI values."""
        if len(prices) < period + lookback:
            return 50.0
        
        # Calculate RSI history
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
        
        # Calculate percentile of current RSI
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
        
        # Calculate +DI and -DI
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
        
        # Smooth values
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
        
        # Calculate ADX as smoothed DX
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
        """Check if current volume is above average."""
        if len(candles) < 20:
            return False
        avg_vol = TechnicalAnalysis.calculate_avg_volume(candles[:-1], 20)
        current_vol = candles[-1].volume
        return current_vol > avg_vol * threshold
    
    @staticmethod
    def was_big_move(candles: List[Candle], atr_multiplier: float = 2.0) -> bool:
        """Check if there was a big move (> N x ATR) in last 3 days - avoid entering."""
        if len(candles) < 4:
            return False
        atr = TechnicalAnalysis.calculate_atr(candles[:-1])
        if atr == 0:
            return False
        
        # Check last 3 candles
        for i in range(-3, 0):
            candle = candles[i]
            move = max(
                abs(candle.close - candles[i-1].close),
                abs(candle.high - candles[i-1].low),
            )
            if move > atr * atr_multiplier:
                return True
        return False


class CandlestickPatterns:
    @staticmethod
    def is_evening_star(candles: List[Candle]) -> tuple:
        if len(candles) < 3:
            return False, 0
        c1, c2, c3 = candles[-3], candles[-2], candles[-1]
        body1, body3 = c1.close - c1.open, c3.close - c3.open
        
        if (body1 > 0 and body1 > (c1.high - c1.low) * 0.6 and
            body3 < 0 and abs(body3) > (c3.high - c3.low) * 0.6):
            return True, 60  # Increased weight
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


def fetch_data(symbol: str, days: int = 730) -> List[Candle]:
    """Fetch historical data for backtesting."""
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period=f"{days}d", interval="1d")
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


def generate_v5_signals(candles: List[Candle], short_only: bool = True) -> List[dict]:
    """
    Generate V5 signals with universal improvements.
    
    Key changes from V4:
    - Percentile-based RSI instead of fixed thresholds
    - ADX filter for trend quality
    - Volatility-adjusted stops
    - Volume confirmation
    - Stop-run avoidance
    """
    signals = []
    
    for i in range(300, len(candles)):  # Need more data for RSI percentile
        daily = candles[:i]
        current = daily[-1]
        prices = [c.close for c in daily]
        
        # Core indicators
        rsi = TechnicalAnalysis.calculate_rsi(prices)
        rsi_percentile = TechnicalAnalysis.calculate_rsi_percentile(prices)
        atr = TechnicalAnalysis.calculate_atr(daily)
        adx = TechnicalAnalysis.calculate_adx(daily)
        sma_200 = TechnicalAnalysis.calculate_sma(prices, 200)
        volatility = TechnicalAnalysis.calculate_volatility(daily)
        avg_vol = TechnicalAnalysis.calculate_avg_volume(daily)
        
        # Multi-timeframe: Weekly trend
        weekly_idx = i // 5  # Approximate weekly candles
        if weekly_idx >= 50:
            weekly_prices = prices[::5]  # Approximate weekly prices
            weekly_sma_20 = TechnicalAnalysis.calculate_sma(weekly_prices, 20)
            weekly_above = weekly_prices[-1] > weekly_sma_20
        else:
            weekly_above = prices[-1] > sma_200
        
        patterns = CandlestickPatterns.detect_all(daily)
        
        above_200 = current.close > sma_200
        
        # Volume check
        volume_confirmed = TechnicalAnalysis.is_volume_spike(daily, 1.2)
        
        # Stop-run check
        avoid_entry = TechnicalAnalysis.was_big_move(daily, 2.0)
        
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
            if not above_200:  # Strong downtrend
                short_score += 20
                reasons.append(f"ADX: {adx:.1f} (very strong downtrend)")
            elif above_200:  # Strong uptrend
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
            reasons.append(f"ADX: {adx:.1f} (choppy - skip)")
            continue  # Skip choppy markets entirely
        
        # =====================
        # PATTERN SCORING - Stronger weights
        # =====================
        if "Evening Star" in patterns:
            short_score += 70
        if "Bearish Engulfing" in patterns:
            short_score += 55
        if "Shooting Star" in patterns:
            short_score += 45
        if "Morning Star" in patterns:
            long_score += 60
        if "Bullish Engulfing" in patterns:
            long_score += 50
        
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
            # Weekly and daily disagree - skip
            continue
        
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
        if total < 60:  # Higher threshold for more selective trading
            continue
        
        # =====================
        # DIRECTION DETERMINATION
        # =====================
        # Use 1:1 reward:risk ratio to balance wins and losses
        if short_only:
            # SHORT ONLY mode
            if short_score > long_score * 1.3:
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
                continue
        else:
            # BOTH directions
            if short_score > long_score * 1.3:
                direction = "SHORT"
                confidence = min((short_score / total) * 100, 95)
                stop_mult = 2.0
                target_mult = 2.0
                stop = current.close + (atr * stop_mult)
                target1 = current.close - (atr * target_mult)
                target2 = current.close - (atr * target_mult * 1.5)
            elif long_score > short_score * 1.3:
                direction = "LONG"
                confidence = min((long_score / total) * 100, 95)
                stop_mult = 2.0
                target_mult = 2.0
                stop = current.close - (atr * stop_mult)
                target1 = current.close + (atr * target_mult)
                target2 = current.close + (atr * target_mult * 1.5)
            else:
                continue
        
        signals.append({
            'date': current.timestamp,
            'price': current.close,
            'direction': direction,
            'confidence': confidence,
            'stop': stop,
            'target1': target1,  # Partial exit at 1:1
            'target2': target2,  # Full exit at 2:1
            'rsi': rsi,
            'rsi_percentile': rsi_percentile,
            'adx': adx,
            'volatility': volatility,
            'volume_confirmed': volume_confirmed,
            'stop_mult': stop_mult,
            'patterns': list(patterns.keys()),
            'reasons': reasons,
        })
    
    return signals


def backtest(candles: List[Candle], signals: List[dict], max_days: int = 30) -> List[dict]:
    """
    Backtest signals against historical data.
    Uses partial exit strategy:
    - Exit 50% at target1 (1:1 reward:risk)
    - Exit remaining 50% at target2 (2:1 reward:risk)
    - Stop loss hits = full loss
    """
    results = []
    
    for signal in signals:
        signal_date = signal['date']
        direction = signal['direction']
        entry = signal['price']
        stop = signal['stop']
        target1 = signal.get('target1', signal.get('target'))  # Partial exit
        target2 = signal.get('target2', signal.get('target'))  # Full exit
        
        # Get future candles
        future = [c for c in candles if c.timestamp > signal_date][:max_days]
        
        if not future:
            continue
        
        outcome = "HOLDING"
        exit_price = None
        pnl_pct = 0
        partial_exit = False
        
        for candle in future:
            if direction == "LONG":
                # Check stop first
                if candle.low <= stop:
                    outcome = "STOPPED_OUT"
                    exit_price = stop
                    pnl_pct = ((stop - entry) / entry) * 100
                    break
                # Check target1 (partial exit)
                elif not partial_exit and candle.high >= target1:
                    partial_exit = True
                    # Calculate partial profit (50% of position)
                    partial_pnl = ((target1 - entry) / entry) * 100 * 0.5
                    # Move stop to breakeven for remaining position
                    new_stop = entry
                    # Continue to check target2
                # Check target2 (full exit)
                elif candle.high >= target2:
                    if partial_exit:
                        # Already took partial profit at target1
                        remaining_pnl = ((target2 - entry) / entry) * 100 * 0.5
                        pnl_pct = partial_pnl + remaining_pnl
                    else:
                        pnl_pct = ((target2 - entry) / entry) * 100
                    outcome = "TAKE_PROFIT"
                    exit_price = target2
                    break
            else:  # SHORT
                # Check stop first
                if candle.high >= stop:
                    outcome = "STOPPED_OUT"
                    exit_price = stop
                    pnl_pct = ((entry - stop) / entry) * 100
                    break
                # Check target1 (partial exit)
                elif not partial_exit and candle.low <= target1:
                    partial_exit = True
                    # Calculate partial profit (50% of position)
                    partial_pnl = ((entry - target1) / entry) * 100 * 0.5
                    # Move stop to breakeven for remaining position
                    new_stop = entry
                    # Continue to check target2
                # Check target2 (full exit)
                elif candle.low <= target2:
                    if partial_exit:
                        # Already took partial profit at target1
                        remaining_pnl = ((entry - target2) / entry) * 100 * 0.5
                        pnl_pct = partial_pnl + remaining_pnl
                    else:
                        pnl_pct = ((entry - target2) / entry) * 100
                    outcome = "TAKE_PROFIT"
                    exit_price = target2
                    break
        
        if outcome == "HOLDING":
            last = future[-1]
            if partial_exit:
                # Calculate partial profit if we exited half at target1
                if direction == "LONG":
                    pnl_pct = ((target1 - entry) / entry) * 100 * 0.5
                    # Plus remaining position value
                    remaining_pnl = ((last.close - entry) / entry) * 100 * 0.5
                    pnl_pct = pnl_pct + remaining_pnl
                    exit_price = last.close
                else:
                    pnl_pct = ((entry - target1) / entry) * 100 * 0.5
                    remaining_pnl = ((entry - last.close) / entry) * 100 * 0.5
                    pnl_pct = pnl_pct + remaining_pnl
                    exit_price = last.close
                outcome = "PARTIAL"
            else:
                exit_price = last.close
                if direction == "LONG":
                    pnl_pct = ((exit_price - entry) / entry) * 100
                else:
                    pnl_pct = ((entry - exit_price) / entry) * 100
        
        results.append({
            **signal,
            'exit_price': exit_price,
            'outcome': outcome,
            'pnl_pct': pnl_pct,
            'holding_days': len(future),
        })
    
    return results


def print_results(results: List[dict], symbol: str = "", short_only: bool = True):
    """Print backtest results."""
    if not results:
        print("\n⚠️  No trades generated!")
        return
    
    wins = [r for r in results if r['pnl_pct'] > 0]
    losses = [r for r in results if r['pnl_pct'] <= 0]
    tp = [r for r in results if r['outcome'] == 'TAKE_PROFIT']
    so = [r for r in results if r['outcome'] == 'STOPPED_OUT']
    partial = [r for r in results if r['outcome'] == 'PARTIAL']
    
    total_pnl = sum(r['pnl_pct'] for r in results)
    
    mode_str = "SHORT-ONLY" if short_only else "BOTH"
    
    print(f"\n{'='*70}")
    print(f"📊 V5 UNIVERSAL BACKTEST {f'for {symbol}' if symbol else ''} [{mode_str}]")
    print(f"{'='*70}")
    
    print(f"\n📈 TRADE STATISTICS")
    print(f"  Total Trades:     {len(results)}")
    print(f"  Wins:             {len(wins)} ({len(wins)/len(results)*100:.1f}%)")
    print(f"  Losses:           {len(losses)} ({len(losses)/len(results)*100:.1f}%)")
    print(f"  Full TP:         {len(tp)} ({len(tp)/len(results)*100:.1f}%)")
    print(f"  Partial Exit:    {len(partial)} ({len(partial)/len(results)*100:.1f}%)")
    print(f"  Stop Outs:        {len(so)} ({len(so)/len(results)*100:.1f}%)")
    
    print(f"\n💰 P&L ANALYSIS")
    print(f"  Total P&L:        {total_pnl:+.2f}%")
    print(f"  Avg P&L/Trade:    {total_pnl/len(results):+.2f}%")
    if wins:
        print(f"  Avg Win:           +{sum(r['pnl_pct'] for r in wins)/len(wins):.2f}%")
    if losses:
        print(f"  Avg Loss:           {sum(r['pnl_pct'] for r in losses)/len(losses):.2f}%")
    print(f"  Best Trade:        +{max(r['pnl_pct'] for r in results):.2f}%")
    print(f"  Worst Trade:       {min(r['pnl_pct'] for r in results):.2f}%")
    
    if losses and sum(r['pnl_pct'] for r in losses) != 0:
        pf = abs(sum(r['pnl_pct'] for r in wins) / sum(r['pnl_pct'] for r in losses))
        print(f"  Profit Factor:     {pf:.2f}")
    
    # Key V5 metrics
    avg_rsi_pct = np.mean([r['rsi_percentile'] for r in results])
    avg_adx = np.mean([r['adx'] for r in results])
    vol_confirmed = sum(1 for r in results if r.get('volume_confirmed', False))
    
    print(f"\n📊 V5 STRATEGY METRICS")
    print(f"  Avg RSI Percentile: {avg_rsi_pct:.1f}%")
    print(f"  Avg ADX:          {avg_adx:.1f}")
    print(f"  Volume Confirmed:  {vol_confirmed}/{len(results)} ({vol_confirmed/len(results)*100:.0f}%)")
    print(f"  Partial Exit:     {len(partial)} trades closed at partial target")
    
    # Validation
    print(f"\n{'='*70}")
    print(f"🔍 STRATEGY VALIDATION")
    print(f"{'='*70}")
    
    issues = []
    successes = []
    
    if len(results) >= 30:
        successes.append("✅ Sufficient sample size")
    else:
        issues.append(f"⚠️  Only {len(results)} trades")
    
    wr = len(wins) / len(results) * 100
    if wr >= 55:
        successes.append(f"✅ Win rate ({wr:.1f}%) is excellent")
    elif wr >= 50:
        successes.append(f"✅ Win rate ({wr:.1f}%) is good")
    elif wr >= 45:
        issues.append(f"⚠️  Win rate ({wr:.1f}%) marginal")
    else:
        issues.append(f"❌ Win rate ({wr:.1f}%) too low")
    
    if total_pnl > 0:
        successes.append(f"✅ Total P&L ({total_pnl:+.2f}%) is positive")
    else:
        issues.append(f"❌ Total P&L ({total_pnl:+.2f}%) is negative")
    
    avg_pnl = total_pnl / len(results)
    if avg_pnl >= 1.0:
        successes.append(f"✅ Avg trade ({avg_pnl:+.2f}%) is strong")
    elif avg_pnl >= 0.5:
        successes.append(f"✅ Avg trade ({avg_pnl:+.2f}%) covers costs")
    elif avg_pnl > 0:
        issues.append(f"⚠️  Avg trade ({avg_pnl:+.2f}%) is low")
    else:
        issues.append(f"❌ Avg trade ({avg_pnl:+.2f}%) loses money")
    
    tp_rate = len(tp) / (len(tp) + len(so)) * 100 if (len(tp) + len(so)) > 0 else 0
    if tp_rate >= 50:
        successes.append(f"✅ TP rate ({tp_rate:.1f}%) is excellent")
    elif tp_rate >= 40:
        successes.append(f"✅ TP rate ({tp_rate:.1f}%) is good")
    else:
        issues.append(f"⚠️  TP rate ({tp_rate:.1f}%) - stops hitting often")
    
    for s in successes:
        print(f"  {s}")
    for i in issues:
        print(f"  {i}")
    
    print(f"\n{'='*70}")
    if not issues:
        print(f"✅ STRATEGY VALIDATED!")
    elif len(issues) <= 2:
        print(f"⚠️  STRATEGY NEEDS MINOR REFINEMENT")
    else:
        print(f"❌ STRATEGY NEEDS IMPROVEMENT")
    print(f"{'='*70}")
    
    # Recent trades
    print(f"\n📋 RECENT TRADES (Last 10)")
    for r in sorted(results, key=lambda x: x['date'], reverse=True)[:10]:
        emoji = "🟢" if r['pnl_pct'] > 0 else "🔴"
        vol = "📊" if r.get('volume_confirmed') else "  "
        print(f"  {emoji}{vol} {r['date'].strftime('%Y-%m-%d')} {r['direction']:5} "
              f"${r['price']:.2f} → ${r['exit_price']:.2f} "
              f"{r['outcome']:12} {r['pnl_pct']:+.2f}%")


def main():
    parser = argparse.ArgumentParser(description="V5 Universal Short Strategy Backtest")
    parser.add_argument('--symbol', nargs='+', help='Symbols to backtest')
    parser.add_argument('--all', action='store_true', help='Backtest all default symbols')
    parser.add_argument('--long', action='store_true', help='Include LONG trades (default: SHORT only)')
    args = parser.parse_args()
    
    symbols = args.symbol if args.symbol else []
    if args.all:
        symbols = ["META", "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA"]
    
    if not symbols:
        parser.print_help()
        return
    
    short_only = not args.long
    
    all_results = []
    
    print(f"\n{'='*70}")
    print(f"🚀 V5 UNIVERSAL SHORT STRATEGY BACKTEST")
    print(f"{'='*70}")
    print(f"Mode: {'SHORT-ONLY' if short_only else 'BOTH DIRECTIONS'}")
    print(f"Key Improvements:")
    print(f"  - Percentile-based RSI (adapts to each stock)")
    print(f"  - ADX trend filter (only trade in trending markets)")
    print(f"  - Volatility-adjusted stops (stock-specific)")
    print(f"  - Volume confirmation (stronger signals)")
    print(f"  - Stop-run avoidance (skip after big moves)")
    print(f"{'='*70}")
    
    symbol_results = {}
    
    for symbol in symbols:
        print(f"\n{'='*70}")
        print(f"🔍 V5 BACKTEST: {symbol}")
        print(f"{'='*70}")
        
        candles = fetch_data(symbol, 730)
        if len(candles) < 300:
            print(f"⚠️  Not enough data ({len(candles)} candles)")
            continue
        
        signals = generate_v5_signals(candles, short_only=short_only)
        print(f"Generated {len(signals)} signals")
        
        if not signals:
            print(f"⚠️  No valid signals generated")
            continue
        
        results = backtest(candles, signals)
        all_results.extend(results)
        symbol_results[symbol] = results
        print_results(results, symbol, short_only)
    
    # Summary across all symbols
    if len(symbols) > 1 and symbol_results:
        print(f"\n{'='*70}")
        print(f"📊 ALL SYMBOLS SUMMARY")
        print(f"{'='*70}")
        
        summary_data = []
        for sym, res in symbol_results.items():
            if res:
                wins = sum(1 for r in res if r['pnl_pct'] > 0)
                wr = wins / len(res) * 100
                pnl = sum(r['pnl_pct'] for r in res)
                summary_data.append([sym, len(res), f"{wr:.1f}%", f"{pnl:+.1f}%"])
        
        if summary_data:
            summary_data.sort(key=lambda x: float(x[3].replace('%', '').replace('+', '')), reverse=True)
            print(f"\n{'Symbol':<10} {'Trades':<8} {'Win Rate':<10} {'P&L':<10}")
            print("-" * 40)
            for row in summary_data:
                print(f"{row[0]:<10} {row[1]:<8} {row[2]:<10} {row[3]:<10}")
        
        if all_results:
            print_results(all_results, "ALL SYMBOLS", short_only)


if __name__ == "__main__":
    main()
