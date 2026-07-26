"""
Backtest Validator V4 - SHORT-PREFERRED strategy

Based on V3 results showing SHORT preference:
- SHORT: 50% win rate, +33% P&L ✅
- LONG: 35% win rate, -14% P&L ❌

V4 Changes:
✅ WIDER STOPS (3x ATR instead of 2x)
✅ SHORT-PREFERRED MODE
✅ STOCKS ONLY
✅ STRICTER LONG requirements

Usage:
    python examples/backtest_validator_v4.py --symbol AAPL MSFT
    python examples/backtest_validator_v4.py --all
"""

import argparse
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict
import yfinance as yf
import numpy as np

SHORT_PREFERRED = True

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
    def calculate_rsi(prices, period=14):
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
    def calculate_atr(candles, period=14):
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
    def calculate_sma(prices, period):
        if len(prices) < period:
            return prices[-1] if prices else 0
        return float(np.mean(prices[-period:]))
    
    @staticmethod
    def calculate_volatility(candles):
        if len(candles) < 20:
            return 2.0
        prices = [c.close for c in candles]
        returns = np.diff(prices) / np.array(prices[:-1])
        return float(np.std(returns[-20:]) * 100)


class CandlestickPatterns:
    @staticmethod
    def is_evening_star(candles):
        if len(candles) < 3:
            return False, 0
        c1, c2, c3 = candles[-3], candles[-2], candles[-1]
        body1, body3 = c1.close - c1.open, c3.close - c3.open
        if (body1 > 0 and body1 > (c1.high - c1.low) * 0.6 and
            body3 < 0 and abs(body3) > (c3.high - c3.low) * 0.6):
            return True, 55
        return False, 0
    
    @staticmethod
    def is_bearish_engulfing(candles):
        if len(candles) < 2:
            return False, 0
        c1, c2 = candles[-2], candles[-1]
        body1, body2 = c1.close - c1.open, c2.close - c2.open
        if body1 > 0 and body2 < 0:
            if c2.open > c1.close and c2.close < c1.open:
                if abs(body2) > abs(body1) * 1.1:
                    return True, 45
        return False, 0
    
    @staticmethod
    def is_morning_star(candles):
        if len(candles) < 3:
            return False, 0
        c1, c2, c3 = candles[-3], candles[-2], candles[-1]
        body1, body3 = c1.close - c1.open, c3.close - c3.open
        if (body1 < 0 and abs(body1) > (c1.high - c1.low) * 0.6 and
            body3 > 0 and abs(body3) > (c3.high - c3.low) * 0.6):
            return True, 50
        return False, 0
    
    @staticmethod
    def detect_all(candles):
        patterns = {}
        patterns["Evening Star"] = CandlestickPatterns.is_evening_star(candles)[1]
        patterns["Bearish Engulfing"] = CandlestickPatterns.is_bearish_engulfing(candles)[1]
        patterns["Morning Star"] = CandlestickPatterns.is_morning_star(candles)[1]
        return {k: v for k, v in patterns.items() if v > 0}


def fetch_data(symbol, days=365):
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


def generate_v4_signals(candles):
    """Generate SHORT-preferred signals with wider stops."""
    signals = []
    
    for i in range(220, len(candles)):  # Need 200+ for SMA
        daily = candles[:i]
        current = daily[-1]
        prices = [c.close for c in daily]
        
        rsi = TechnicalAnalysis.calculate_rsi(prices)
        atr = TechnicalAnalysis.calculate_atr(daily)
        sma_200 = TechnicalAnalysis.calculate_sma(prices, 200)
        volatility = TechnicalAnalysis.calculate_volatility(daily)
        patterns = CandlestickPatterns.detect_all(daily)
        
        above_200 = current.close > sma_200
        
        short_score = 0
        long_score = 0
        
        # SHORT signals
        if rsi > 70:
            short_score += 35
        elif rsi > 60:
            short_score += 20
        
        if not above_200:
            short_score += 25
        
        if "Evening Star" in patterns:
            short_score += 55
        if "Bearish Engulfing" in patterns:
            short_score += 45
        
        if above_200:
            short_score -= 15
        
        # LONG signals (stricter)
        if rsi < 25:
            long_score += 40
        elif rsi < 30:
            long_score += 25
        
        if above_200:
            long_score += 25
        
        if "Morning Star" in patterns:
            long_score += 50
        
        if not above_200:
            long_score -= 15
        
        # SHORT-PREFERRED boost
        if SHORT_PREFERRED:
            short_score *= 1.2
            if long_score > 60:
                long_score *= 0.8
        
        # Volatility filter
        if volatility > 5:
            continue
        if volatility > 3:
            short_score *= 0.85
            long_score *= 0.85
        
        total = short_score + long_score
        if total < 40:
            continue
        
        # Direction
        if SHORT_PREFERRED:
            if short_score > long_score * 1.2:
                direction = "SHORT"
                confidence = min((short_score / total) * 100, 95)
                stop = current.close + (atr * 3)  # WIDER STOP
                target = current.close - (atr * 3)
            elif long_score > short_score * 1.5:
                direction = "LONG"
                confidence = min((long_score / total) * 100, 95)
                stop = current.close - (atr * 3)
                target = current.close + (atr * 3)
            else:
                continue
        else:
            if short_score > long_score * 1.2:
                direction = "SHORT"
                confidence = min((short_score / total) * 100, 95)
                stop = current.close + (atr * 3)
                target = current.close - (atr * 3)
            elif long_score > short_score * 1.2:
                direction = "LONG"
                confidence = min((long_score / total) * 100, 95)
                stop = current.close - (atr * 3)
                target = current.close + (atr * 3)
            else:
                continue
        
        signals.append({
            'date': current.timestamp,
            'price': current.close,
            'direction': direction,
            'confidence': confidence,
            'stop': stop,
            'target': target,
            'rsi': rsi,
            'above_200': above_200,
        })
    
    return signals


def backtest(candles, signals):
    results = []
    
    for signal in signals:
        signal_date = signal['date']
        direction = signal['direction']
        entry = signal['price']
        stop = signal['stop']
        target = signal['target']
        
        future = [c for c in candles if c.timestamp > signal_date][:30]
        
        if not future:
            continue
        
        outcome = "HOLDING"
        exit_price = None
        pnl_pct = 0
        
        for candle in future:
            if direction == "LONG":
                if candle.low <= stop:
                    outcome = "STOPPED_OUT"
                    exit_price = stop
                    pnl_pct = ((stop - entry) / entry) * 100
                    break
                elif candle.high >= target:
                    outcome = "TAKE_PROFIT"
                    exit_price = target
                    pnl_pct = ((target - entry) / entry) * 100
                    break
            else:  # SHORT
                if candle.high >= stop:
                    outcome = "STOPPED_OUT"
                    exit_price = stop
                    pnl_pct = ((entry - stop) / entry) * 100
                    break
                elif candle.low <= target:
                    outcome = "TAKE_PROFIT"
                    exit_price = target
                    pnl_pct = ((entry - target) / entry) * 100
                    break
        
        if outcome == "HOLDING":
            last = future[-1]
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
        })
    
    return results


def print_results(results, symbol=""):
    if not results:
        print("\n⚠️  No trades generated!")
        return
    
    wins = [r for r in results if r['pnl_pct'] > 0]
    losses = [r for r in results if r['pnl_pct'] <= 0]
    tp = [r for r in results if r['outcome'] == 'TAKE_PROFIT']
    so = [r for r in results if r['outcome'] == 'STOPPED_OUT']
    
    total_pnl = sum(r['pnl_pct'] for r in results)
    
    print(f"\n{'='*70}")
    print(f"📊 V4 SHORT-PREFERRED BACKTEST {f'for {symbol}' if symbol else ''}")
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
    
    # Direction analysis
    longs = [r for r in results if r['direction'] == 'LONG']
    shorts = [r for r in results if r['direction'] == 'SHORT']
    
    print(f"\n📊 DIRECTION ANALYSIS (SHORT-PREFERRED)")
    if shorts:
        sp = sum(r['pnl_pct'] for r in shorts)
        print(f"  🔴 SHORT: {len(shorts)} trades, {sp:+.2f}% P&L ({sum(1 for r in shorts if r['pnl_pct']>0)/len(shorts)*100:.0f}% win rate)")
    if longs:
        lp = sum(r['pnl_pct'] for r in longs)
        print(f"  🟢 LONG: {len(longs)} trades, {lp:+.2f}% P&L ({sum(1 for r in longs if r['pnl_pct']>0)/len(longs)*100:.0f}% win rate)")
    
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
    if wr >= 50:
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
    if avg_pnl >= 0.5:
        successes.append(f"✅ Avg trade ({avg_pnl:+.2f}%) covers costs")
    elif avg_pnl > 0:
        issues.append(f"⚠️  Avg trade ({avg_pnl:+.2f}%) is low")
    else:
        issues.append(f"❌ Avg trade ({avg_pnl:+.2f}%) loses money")
    
    tp_rate = len(tp) / (len(tp) + len(so)) * 100 if (len(tp) + len(so)) > 0 else 0
    if tp_rate >= 40:
        successes.append(f"✅ TP rate ({tp_rate:.1f}%) is good")
    else:
        issues.append(f"⚠️  TP rate ({tp_rate:.1f}%) - stops hitting often")
    
    for s in successes:
        print(f"  {s}")
    for i in issues:
        print(f"  {i}")
    
    print(f"\n{'='*70}")
    if not issues:
        print(f"✅ STRATEGY APPEARS VALIDATED!")
    elif len(issues) <= 2:
        print(f"⚠️  STRATEGY NEEDS MINOR REFINEMENT")
    else:
        print(f"❌ STRATEGY NEEDS IMPROVEMENT")
    print(f"{'='*70}")
    
    # Recent trades
    print(f"\n📋 RECENT TRADES (Last 10)")
    for r in sorted(results, key=lambda x: x['date'], reverse=True)[:10]:
        emoji = "🟢" if r['pnl_pct'] > 0 else "🔴"
        print(f"  {emoji} {r['date'].strftime('%Y-%m-%d')} {r['direction']:5} "
              f"${r['price']:.2f} → ${r['exit_price']:.2f} "
              f"{r['outcome']:12} {r['pnl_pct']:+.2f}%")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--symbol', nargs='+')
    parser.add_argument('--all', action='store_true')
    args = parser.parse_args()
    
    symbols = args.symbol if args.symbol else []
    if args.all:
        symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
    
    if not symbols:
        parser.print_help()
        return
    
    all_results = []
    
    for symbol in symbols:
        print(f"\n{'='*70}")
        print(f"🔍 V4 SHORT-PREFERRED BACKTEST: {symbol}")
        print(f"{'='*70}")
        
        candles = fetch_data(symbol, 365)
        if len(candles) < 220:
            print(f"⚠️  Not enough data")
            continue
        
        signals = generate_v4_signals(candles)
        print(f"Generated {len(signals)} signals")
        
        results = backtest(candles, signals)
        all_results.extend(results)
        print_results(results, symbol)
    
    if len(symbols) > 1:
        print_results(all_results, "ALL SYMBOLS")


if __name__ == "__main__":
    main()
