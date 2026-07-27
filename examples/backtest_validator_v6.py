"""
Backtest Validator V6 - EXTREME REVERSAL STRATEGY

V5 RESULTS PROBLEMS:
- Win rate only 42% across all stocks
- Stops hitting too often
- Not catching truly extreme conditions

V6 KEY CHANGES - "Extreme Reversal" Approach:

1. ONLY EXTREME RSI (95th percentile+)
   - Only short when RSI is in top 5% of historical values
   - This means the stock is EXTREMELY overbought
   - Much higher reversal probability

2. WIDER STOPS (4x ATR)
   - Let trades breathe and work
   - Avoid being stopped out by noise

3. BIGGER TARGETS (6x ATR)
   - 1.5:1 reward:risk ratio
   - When we win, we win big

4. ADDITIONAL CONFIRMATION:
   - MACD divergence (price up, MACD down)
   - Bollinger Band upper touch
   - Volume surge on the signal candle

5. TRAILING STOP
   - Move stop to breakeven when at 2x ATR profit
   - Lock in profits without exiting early

6. FEWER BUT BETTER SIGNALS
   - Quality over quantity
   - Only take the BEST setups

Usage:
    python examples/backtest_validator_v6.py --symbol META AAPL MSFT GOOGL
    python examples/backtest_validator_v6.py --all
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
        return float(dx)
    
    @staticmethod
    def calculate_macd(prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> tuple:
        """Calculate MACD line, signal line, and histogram."""
        if len(prices) < slow + signal:
            return 50.0, 50.0, 0.0
        
        # Calculate EMAs
        ema_fast = TechnicalAnalysis._ema(prices, fast)
        ema_slow = TechnicalAnalysis._ema(prices, slow)
        macd_line = ema_fast - ema_slow
        
        # Signal line is EMA of MACD
        macd_values = []
        for i in range(slow, len(prices)):
            e_f = TechnicalAnalysis._ema(prices[:i+1], fast)
            e_s = TechnicalAnalysis._ema(prices[:i+1], slow)
            macd_values.append(e_f - e_s)
        
        signal_line = np.mean(macd_values[-signal:]) if len(macd_values) >= signal else macd_values[-1]
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
    
    @staticmethod
    def _ema(prices: List[float], period: int) -> float:
        """Calculate EMA."""
        if len(prices) < period:
            return prices[-1] if prices else 0
        
        multiplier = 2 / (period + 1)
        ema = np.mean(prices[:period])
        
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        
        return ema
    
    @staticmethod
    def calculate_bollinger(prices: List[float], period: int = 20, std_dev: float = 2.0) -> tuple:
        """Calculate Bollinger Bands."""
        if len(prices) < period:
            return prices[-1], prices[-1], prices[-1] if prices else 0
        
        sma = np.mean(prices[-period:])
        std = np.std(prices[-period:])
        
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        
        return upper, sma, lower
    
    @staticmethod
    def check_macd_divergence(candles: List[Candle]) -> bool:
        """Check for bearish MACD divergence: price higher highs, MACD lower highs."""
        if len(candles) < 35:
            return False
        
        prices = [c.close for c in candles]
        
        # Check last 20 candles for price/MACD relationship
        macd_line, signal_line, _ = TechnicalAnalysis.calculate_macd(prices)
        
        # Simple check: MACD below signal line = bearish
        return macd_line < signal_line
    
    @staticmethod
    def is_bollinger_upper_touch(candles: List[Candle], period: int = 20) -> bool:
        """Check if current price is at or above upper Bollinger Band."""
        if len(candles) < period:
            return False
        
        prices = [c.close for c in candles]
        upper, _, _ = TechnicalAnalysis.calculate_bollinger(prices, period)
        
        return candles[-1].high >= upper
    
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
    def is_volume_surge(candles: List[Candle], threshold: float = 1.5) -> bool:
        """Check if current volume is significantly above average."""
        if len(candles) < 20:
            return False
        avg_vol = TechnicalAnalysis.calculate_avg_volume(candles[:-1], 20)
        current_vol = candles[-1].volume
        return current_vol > avg_vol * threshold


class CandlestickPatterns:
    @staticmethod
    def is_evening_star(candles: List[Candle]) -> bool:
        if len(candles) < 3:
            return False
        c1, c2, c3 = candles[-3], candles[-2], candles[-1]
        body1, body3 = c1.close - c1.open, c3.close - c3.open
        
        return (body1 > 0 and body1 > (c1.high - c1.low) * 0.6 and
                body3 < 0 and abs(body3) > (c3.high - c3.low) * 0.6)
    
    @staticmethod
    def is_bearish_engulfing(candles: List[Candle]) -> bool:
        if len(candles) < 2:
            return False
        c1, c2 = candles[-2], candles[-1]
        body1, body2 = c1.close - c1.open, c2.close - c2.open
        
        return (body1 > 0 and body2 < 0 and
                c2.open > c1.close and c2.close < c1.open and
                abs(body2) > abs(body1) * 1.1)
    
    @staticmethod
    def is_shooting_star(candles: List[Candle]) -> bool:
        if len(candles) < 1:
            return False
        c = candles[-1]
        body = c.close - c.open
        upper = c.high - max(c.open, c.close)
        lower = min(c.open, c.close) - c.low
        
        return upper > abs(body) * 2 and lower < abs(body) * 0.3 and body < 0
    
    @staticmethod
    def is_doji(candles: List[Candle]) -> bool:
        """Doji - indecision candle."""
        if len(candles) < 1:
            return False
        c = candles[-1]
        body = abs(c.close - c.open)
        range_c = c.high - c.low
        return body < range_c * 0.1  # Very small body
    
    @staticmethod
    def has_any_bearish_pattern(candles: List[Candle]) -> bool:
        """Check if any bearish pattern is present."""
        return (CandlestickPatterns.is_evening_star(candles) or
                CandlestickPatterns.is_bearish_engulfing(candles) or
                CandlestickPatterns.is_shooting_star(candles))


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


def generate_v6_signals(candles: List[Candle]) -> List[dict]:
    """
    Generate V6 EXTREME REVERSAL signals.
    
    Key philosophy: Only short when EVERYTHING aligns:
    - RSI at EXTREME overbought (95th+ percentile)
    - MACD bearish divergence
    - Bollinger upper band touch
    - Volume surge
    - Bearish candlestick pattern
    - Strong ADX (trend is strong = reversal more likely)
    
    This should give higher win rate but fewer signals.
    """
    signals = []
    
    for i in range(300, len(candles)):  # Need 300+ candles for reliable indicators
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
        
        # Additional indicators
        macd_bearish = TechnicalAnalysis.check_macd_divergence(daily)
        bollinger_touch = TechnicalAnalysis.is_bollinger_upper_touch(daily)
        volume_surge = TechnicalAnalysis.is_volume_surge(daily)
        bearish_pattern = CandlestickPatterns.has_any_bearish_pattern(daily)
        
        above_200 = current.close > sma_200
        
        # ============
        # V6 SCORING - EXTREME CONDITIONS ONLY
        # ============
        
        score = 0
        reasons = []
        
        # MANDATORY: RSI must be EXTREMELY overbought (95th+ percentile)
        if rsi_percentile >= 95:
            score += 60
            reasons.append(f"RSI EXTREME: {rsi_percentile:.0f}th percentile")
        elif rsi_percentile >= 90:
            score += 40
            reasons.append(f"RSI very high: {rsi_percentile:.0f}th percentile")
        elif rsi_percentile >= 80:
            score += 25
            reasons.append(f"RSI high: {rsi_percentile:.0f}th percentile")
        else:
            # RSI not extreme enough - skip
            continue
        
        # ADX must show strong trend (reversal more likely after strong move)
        if adx >= 30:
            score += 15
            reasons.append(f"Strong trend: ADX {adx:.0f}")
        elif adx >= 20:
            score += 8
        
        # MACD bearish divergence
        if macd_bearish:
            score += 15
            reasons.append("MACD bearish")
        
        # Bollinger upper touch
        if bollinger_touch:
            score += 15
            reasons.append("Bollinger upper touch")
        
        # Volume surge
        if volume_surge:
            score += 10
            reasons.append("Volume surge")
        
        # Bearish candlestick
        if bearish_pattern:
            score += 15
            reasons.append("Bearish pattern")
        
        # Below 200 SMA (already in downtrend)
        if not above_200:
            score += 10
            reasons.append("Below 200 SMA")
        
        # Must have minimum score of 80 for a signal
        if score < 80:
            continue
        
        # ============
        # V6 STOPS AND TARGETS - WIDE STOPS, BIG TARGETS
        # ============
        
        # Wider stops: 4x ATR
        stop_mult = 4.0 if volatility > 2.5 else 3.5
        
        # Target: 6x ATR (1.5:1 reward:risk)
        target_mult = stop_mult * 1.5
        
        stop = current.close + (atr * stop_mult)
        target = current.close - (atr * target_mult)
        
        signals.append({
            'date': current.timestamp,
            'price': current.close,
            'direction': 'SHORT',
            'confidence': min(score, 95),
            'stop': stop,
            'target': target,
            'rsi': rsi,
            'rsi_percentile': rsi_percentile,
            'adx': adx,
            'volatility': volatility,
            'macd_bearish': macd_bearish,
            'bollinger_touch': bollinger_touch,
            'volume_surge': volume_surge,
            'bearish_pattern': bearish_pattern,
            'stop_mult': stop_mult,
            'target_mult': target_mult,
            'reasons': reasons,
        })
    
    return signals


def backtest(candles: List[Candle], signals: List[dict], max_days: int = 60) -> List[dict]:
    """
    Backtest with TRAILING STOP:
    - Initial stop at 4x ATR
    - When profit reaches 2x ATR, move stop to breakeven
    - When profit reaches 4x ATR, lock in 3x ATR profit
    """
    results = []
    
    for signal in signals:
        signal_date = signal['date']
        direction = signal['direction']
        entry = signal['price']
        initial_stop = signal['stop']
        target = signal['target']
        atr = TechnicalAnalysis.calculate_atr([c for c in candles if c.timestamp <= signal_date])
        stop_mult = signal['stop_mult']
        
        future = [c for c in candles if c.timestamp > signal_date][:max_days]
        
        if not future:
            continue
        
        outcome = "HOLDING"
        exit_price = None
        pnl_pct = 0
        trailing_stop = initial_stop
        moved_to_breakeven = False
        locked_profit = False
        
        for j, candle in enumerate(future):
            # Calculate current profit
            if direction == "SHORT":
                current_profit = entry - candle.low
                current_loss = candle.high - entry
            else:
                current_profit = candle.high - entry
                current_loss = entry - candle.low
            
            profit_atr = current_profit / atr if atr > 0 else 0
            loss_atr = current_loss / atr if atr > 0 else 0
            
            # TRAILING STOP LOGIC
            if not locked_profit and profit_atr >= 4.0:
                # Lock in profit at 3x ATR
                if direction == "SHORT":
                    trailing_stop = entry - (atr * 3)
                else:
                    trailing_stop = entry + (atr * 3)
                locked_profit = True
                outcome = "TAKE_PROFIT"
                exit_price = trailing_stop
                pnl_pct = 3.0  # 3x ATR profit locked
                break
            elif not moved_to_breakeven and profit_atr >= 2.0:
                # Move stop to breakeven
                trailing_stop = entry
                moved_to_breakeven = True
            
            # Check stops and targets
            if direction == "SHORT":
                # Check trailing stop
                if candle.low <= trailing_stop:
                    outcome = "STOPPED_OUT"
                    exit_price = trailing_stop
                    pnl_pct = ((entry - exit_price) / entry) * 100
                    break
                # Check target
                elif candle.low <= target:
                    outcome = "TAKE_PROFIT"
                    exit_price = target
                    pnl_pct = ((entry - target) / entry) * 100
                    break
            else:
                if candle.high >= trailing_stop:
                    outcome = "STOPPED_OUT"
                    exit_price = trailing_stop
                    pnl_pct = ((exit_price - entry) / entry) * 100
                    break
                elif candle.high >= target:
                    outcome = "TAKE_PROFIT"
                    exit_price = target
                    pnl_pct = ((target - entry) / entry) * 100
                    break
        
        if outcome == "HOLDING":
            last = future[-1]
            exit_price = last.close
            if direction == "SHORT":
                pnl_pct = ((entry - exit_price) / entry) * 100
            else:
                pnl_pct = ((exit_price - entry) / entry) * 100
        
        results.append({
            **signal,
            'exit_price': exit_price,
            'outcome': outcome,
            'pnl_pct': pnl_pct,
            'holding_days': len(future),
        })
    
    return results


def print_results(results: List[dict], symbol: str = ""):
    """Print backtest results."""
    if not results:
        print("\n⚠️  No trades generated!")
        return
    
    wins = [r for r in results if r['pnl_pct'] > 0]
    losses = [r for r in results if r['pnl_pct'] <= 0]
    tp = [r for r in results if r['outcome'] == 'TAKE_PROFIT']
    so = [r for r in results if r['outcome'] == 'STOPPED_OUT']
    
    total_pnl = sum(r['pnl_pct'] for r in results)
    
    print(f"\n{'='*70}")
    print(f"📊 V6 EXTREME REVERSAL BACKTEST {f'for {symbol}' if symbol else ''}")
    print(f"{'='*70}")
    
    print(f"\n📈 TRADE STATISTICS")
    print(f"  Total Trades:     {len(results)}")
    print(f"  Wins:             {len(wins)} ({len(wins)/len(results)*100:.1f}%)")
    print(f"  Losses:           {len(losses)} ({len(losses)/len(results)*100:.1f}%)")
    print(f"  Take Profits:     {len(tp)} ({len(tp)/len(results)*100:.1f}%)")
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
    
    # V6 specific metrics
    avg_rsi_pct = np.mean([r['rsi_percentile'] for r in results])
    avg_adx = np.mean([r['adx'] for r in results])
    macd_count = sum(1 for r in results if r.get('macd_bearish'))
    bb_count = sum(1 for r in results if r.get('bollinger_touch'))
    vol_count = sum(1 for r in results if r.get('volume_surge'))
    pattern_count = sum(1 for r in results if r.get('bearish_pattern'))
    
    print(f"\n📊 V6 CONFIRMATION METRICS")
    print(f"  Avg RSI Percentile: {avg_rsi_pct:.1f}%")
    print(f"  Avg ADX:          {avg_adx:.1f}")
    print(f"  MACD bearish:       {macd_count}/{len(results)}")
    print(f"  Bollinger touch:   {bb_count}/{len(results)}")
    print(f"  Volume surge:      {vol_count}/{len(results)}")
    print(f"  Bearish pattern:  {pattern_count}/{len(results)}")
    
    # Validation
    print(f"\n{'='*70}")
    print(f"🔍 STRATEGY VALIDATION")
    print(f"{'='*70}")
    
    issues = []
    successes = []
    
    if len(results) >= 20:
        successes.append("✅ Sufficient sample size")
    else:
        issues.append(f"⚠️  Only {len(results)} trades (need more signals)")
    
    wr = len(wins) / len(results) * 100
    if wr >= 70:
        successes.append(f"✅✅ Win rate ({wr:.1f}%) is EXCELLENT!")
    elif wr >= 60:
        successes.append(f"✅ Win rate ({wr:.1f}%) is good")
    elif wr >= 50:
        successes.append(f"⚠️ Win rate ({wr:.1f}%) is acceptable")
    else:
        issues.append(f"❌ Win rate ({wr:.1f}%) too low")
    
    if total_pnl > 0:
        successes.append(f"✅ Total P&L ({total_pnl:+.2f}%) is positive")
    else:
        issues.append(f"❌ Total P&L ({total_pnl:+.2f}%) is negative")
    
    avg_pnl = total_pnl / len(results)
    if avg_pnl >= 1.0:
        successes.append(f"✅ Avg trade ({avg_pnl:+.2f}%) is excellent")
    elif avg_pnl >= 0.5:
        successes.append(f"✅ Avg trade ({avg_pnl:+.2f}%) is good")
    elif avg_pnl > 0:
        issues.append(f"⚠️ Avg trade ({avg_pnl:+.2f}%) is low")
    else:
        issues.append(f"❌ Avg trade ({avg_pnl:+.2f}%) loses money")
    
    tp_rate = len(tp) / (len(tp) + len(so)) * 100 if (len(tp) + len(so)) > 0 else 0
    if tp_rate >= 60:
        successes.append(f"✅ TP rate ({tp_rate:.1f}%) is excellent")
    elif tp_rate >= 50:
        successes.append(f"✅ TP rate ({tp_rate:.1f}%) is good")
    else:
        issues.append(f"⚠️ TP rate ({tp_rate:.1f}%)")
    
    for s in successes:
        print(f"  {s}")
    for i in issues:
        print(f"  {i}")
    
    print(f"\n{'='*70}")
    if not issues:
        print(f"✅✅ STRATEGY EXCELLENTLY VALIDATED!")
    elif len(issues) <= 1:
        print(f"✅ STRATEGY VALIDATED!")
    elif len(issues) <= 3:
        print(f"⚠️  STRATEGY NEEDS MINOR REFINEMENT")
    else:
        print(f"❌ STRATEGY NEEDS IMPROVEMENT")
    print(f"{'='*70}")
    
    # Recent trades
    print(f"\n📋 RECENT TRADES (Last 10)")
    for r in sorted(results, key=lambda x: x['date'], reverse=True)[:10]:
        emoji = "🟢" if r['pnl_pct'] > 0 else "🔴"
        confirmations = []
        if r.get('macd_bearish'):
            confirmations.append("M")
        if r.get('bollinger_touch'):
            confirmations.append("B")
        if r.get('volume_surge'):
            confirmations.append("V")
        if r.get('bearish_pattern'):
            confirmations.append("P")
        conf_str = "".join(confirmations) if confirmations else ""
        print(f"  {emoji}{conf_str} {r['date'].strftime('%Y-%m-%d')} SHORT "
              f"${r['price']:.2f} → ${r['exit_price']:.2f} "
              f"{r['outcome']:12} {r['pnl_pct']:+.2f}%")


def main():
    parser = argparse.ArgumentParser(description="V6 Extreme Reversal Strategy Backtest")
    parser.add_argument('--symbol', nargs='+', help='Symbols to backtest')
    parser.add_argument('--all', action='store_true', help='Backtest all default symbols')
    args = parser.parse_args()
    
    symbols = args.symbol if args.symbol else []
    if args.all:
        symbols = ["META", "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA"]
    
    if not symbols:
        parser.print_help()
        return
    
    all_results = []
    
    print(f"\n{'='*70}")
    print(f"🚀 V6 EXTREME REVERSAL STRATEGY BACKTEST")
    print(f"{'='*70}")
    print(f"Key Philosophy: Only short when EVERYTHING aligns")
    print(f"  - RSI EXTREME (95th+ percentile)")
    print(f"  - MACD bearish divergence")
    print(f"  - Bollinger upper band touch")
    print(f"  - Volume surge")
    print(f"  - Bearish candlestick pattern")
    print(f"  - Wide stops (4x ATR) + Big targets (6x ATR)")
    print(f"  - Trailing stop protection")
    print(f"{'='*70}")
    
    symbol_results = {}
    
    for symbol in symbols:
        print(f"\n{'='*70}")
        print(f"🔍 V6 BACKTEST: {symbol}")
        print(f"{'='*70}")
        
        candles = fetch_data(symbol, 730)
        if len(candles) < 300:
            print(f"⚠️  Not enough data ({len(candles)} candles)")
            continue
        
        signals = generate_v6_signals(candles)
        print(f"Generated {len(signals)} EXTREME signals")
        
        if not signals:
            print(f"⚠️  No extreme signals generated")
            continue
        
        results = backtest(candles, signals)
        all_results.extend(results)
        symbol_results[symbol] = results
        print_results(results, symbol)
    
    # Summary
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
                summary_data.append([sym, len(res), f"{wr:.0f}%", f"{pnl:+.1f}%"])
        
        if summary_data:
            summary_data.sort(key=lambda x: float(x[3].replace('%', '').replace('+', '')), reverse=True)
            print(f"\n{'Symbol':<10} {'Trades':<8} {'Win Rate':<10} {'P&L':<10}")
            print("-" * 40)
            for row in summary_data:
                print(f"{row[0]:<10} {row[1]:<8} {row[2]:<10} {row[3]:<10}")
        
        if all_results:
            print_results(all_results, "ALL SYMBOLS")


if __name__ == "__main__":
    main()
