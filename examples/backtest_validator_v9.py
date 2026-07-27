"""
Backtest Validator V9 - HIGH PROBABILITY MOMENTUM

V8 RESULTS:
- Overall: 50.8% WR, +17.8% P&L
- SHORT: 60% WR (excellent!)
- LONG: 48% WR (needs improvement)

V9 GOAL: 60%+ win rate on ALL trades

V9 STRATEGY - "Double Confirmation":

1. STRICTER RSI FILTERS
   - LONG: RSI must be < 30 (deeply oversold)
   - SHORT: RSI must be > 70 (deeply overbought)
   - This ensures we're catching extremes

2. PATTERN CONFIRMATION REQUIRED
   - LONG: Must have bullish engulfing
   - SHORT: Must have bearish engulfing
   - No pattern = No trade

3. VOLUME CONFIRMATION REQUIRED
   - Volume must be 1.2x above average
   - Confirms institutional interest

4. TREND ALIGNMENT
   - LONG: Must be above SMA200 (uptrend)
   - SHORT: Must be below SMA200 (downtrend)

5. EQUAL RISK/REWARD (1:1)
   - Stop: 0.5x ATR
   - Target: 0.5x ATR

This should give us 60%+ win rate on the highest probability setups.

Usage:
    python examples/backtest_validator_v9.py --symbol META AAPL MSFT GOOGL
"""

import argparse
from dataclasses import dataclass
from datetime import datetime
from typing import List
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
    def calculate_sma(prices: List[float], period: int) -> float:
        if len(prices) < period:
            return prices[-1] if prices else 0
        return float(np.mean(prices[-period:]))
    
    @staticmethod
    def calculate_avg_volume(candles: List[Candle], period: int = 20) -> float:
        if len(candles) < period:
            return candles[-1].volume if candles else 0
        return float(np.mean([c.volume for c in candles[-period:]]))
    
    @staticmethod
    def is_volume_surge(candles: List[Candle], threshold: float = 1.2) -> bool:
        if len(candles) < 20:
            return False
        avg_vol = TechnicalAnalysis.calculate_avg_volume(candles[:-1], 20)
        return candles[-1].volume > avg_vol * threshold


class CandlestickPatterns:
    @staticmethod
    def is_bullish_engulfing(candles: List[Candle]) -> bool:
        if len(candles) < 2:
            return False
        c1, c2 = candles[-2], candles[-1]
        body1, body2 = c1.close - c1.open, c2.close - c2.open
        return (body1 < 0 and body2 > 0 and
                c2.open < c1.close and c2.close > c1.open)
    
    @staticmethod
    def is_bearish_engulfing(candles: List[Candle]) -> bool:
        if len(candles) < 2:
            return False
        c1, c2 = candles[-2], candles[-1]
        body1, body2 = c1.close - c1.open, c2.close - c2.open
        return (body1 > 0 and body2 < 0 and
                c2.open > c1.close and c2.close < c1.open)


def fetch_data(symbol: str, days: int = 730) -> List[Candle]:
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period=f"{days}d", interval="1d")
    return [Candle(idx, float(r["Open"]), float(r["High"]), float(r["Low"]),
             float(r["Close"]), float(r["Volume"]) if "Volume" in r else 0)
            for idx, r in hist.iterrows()]


def generate_v9_signals(candles: List[Candle]) -> List[dict]:
    """
    Generate V9 signals - HIGH PROBABILITY setups only.
    
    Requirements for LONG:
    - RSI < 30 (deeply oversold)
    - Bullish engulfing pattern
    - Volume surge
    - Above SMA200 (uptrend)
    
    Requirements for SHORT:
    - RSI > 70 (deeply overbought)
    - Bearish engulfing pattern
    - Volume surge
    - Below SMA200 (downtrend)
    """
    signals = []
    
    for i in range(200, len(candles)):
        daily = candles[:i]
        current = daily[-1]
        prices = [c.close for c in daily]
        
        rsi = TechnicalAnalysis.calculate_rsi(prices)
        atr = TechnicalAnalysis.calculate_atr(daily)
        sma_200 = TechnicalAnalysis.calculate_sma(prices, 200)
        volume_surge = TechnicalAnalysis.is_volume_surge(daily)
        bullish_pattern = CandlestickPatterns.is_bullish_engulfing(daily)
        bearish_pattern = CandlestickPatterns.is_bearish_engulfing(daily)
        
        above_200 = current.close > sma_200
        direction = None
        reasons = []
        
        # V9: STRICTER REQUIREMENTS
        
        # LONG: Need RSI < 30 + pattern + volume + uptrend
        if (rsi < 30 and bullish_pattern and volume_surge and above_200):
            direction = "LONG"
            reasons.append(f"RSI deeply oversold ({rsi:.0f})")
            reasons.append("Bullish engulfing")
            reasons.append("Volume surge")
            reasons.append("Above SMA200")
        
        # SHORT: Need RSI > 70 + pattern + volume + downtrend
        elif (rsi > 70 and bearish_pattern and volume_surge and not above_200):
            direction = "SHORT"
            reasons.append(f"RSI deeply overbought ({rsi:.0f})")
            reasons.append("Bearish engulfing")
            reasons.append("Volume surge")
            reasons.append("Below SMA200")
        
        if not direction:
            continue
        
        # Equal risk/reward (1:1)
        atr_mult = 0.5
        if direction == "LONG":
            stop = current.close - (atr * atr_mult)
            target = current.close + (atr * atr_mult)
        else:
            stop = current.close + (atr * atr_mult)
            target = current.close - (atr * atr_mult)
        
        signals.append({
            'date': current.timestamp,
            'price': current.close,
            'direction': direction,
            'confidence': 85,
            'stop': stop,
            'target': target,
            'rsi': rsi,
            'volume_surge': volume_surge,
            'atr_mult': atr_mult,
            'reasons': reasons,
        })
    
    return signals


def backtest(candles: List[Candle], signals: List[dict], max_days: int = 10) -> List[dict]:
    results = []
    
    for signal in signals:
        signal_date = signal['date']
        direction = signal['direction']
        entry = signal['price']
        stop = signal['stop']
        target = signal['target']
        
        future = [c for c in candles if c.timestamp > signal_date][:max_days]
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
            else:
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
            pnl_pct = ((exit_price - entry) / entry * 100 if direction == "LONG" 
                       else (entry - exit_price) / entry * 100)
        
        results.append({**signal, 'exit_price': exit_price, 'outcome': outcome, 
                       'pnl_pct': pnl_pct, 'holding_days': len(future)})
    
    return results


def print_results(results: List[dict], symbol: str = ""):
    if not results:
        print("\n⚠️  No trades generated!")
        return
    
    wins = [r for r in results if r['pnl_pct'] > 0]
    losses = [r for r in results if r['pnl_pct'] <= 0]
    total_pnl = sum(r['pnl_pct'] for r in results)
    
    longs = [r for r in results if r['direction'] == 'LONG']
    shorts = [r for r in results if r['direction'] == 'SHORT']
    
    print(f"\n{'='*70}")
    print(f"📊 V9 HIGH PROBABILITY BACKTEST {f'for {symbol}' if symbol else ''}")
    print(f"{'='*70}")
    
    print(f"\n📈 TRADE STATISTICS")
    print(f"  Total Trades:     {len(results)}")
    print(f"  Wins:             {len(wins)} ({len(wins)/len(results)*100:.1f}%)")
    print(f"  Losses:           {len(losses)} ({len(losses)/len(results)*100:.1f}%)")
    
    if longs:
        lw = sum(1 for r in longs if r['pnl_pct'] > 0)
        lp = sum(r['pnl_pct'] for r in longs)
        print(f"\n  🟢 LONG: {len(longs)} trades, {lw/len(longs)*100:.0f}% WR, {lp:+.1f}% P&L")
    if shorts:
        sw = sum(1 for r in shorts if r['pnl_pct'] > 0)
        sp = sum(r['pnl_pct'] for r in shorts)
        print(f"  🔴 SHORT: {len(shorts)} trades, {sw/len(shorts)*100:.0f}% WR, {sp:+.1f}% P&L")
    
    print(f"\n💰 P&L ANALYSIS")
    print(f"  Total P&L:        {total_pnl:+.2f}%")
    print(f"  Avg P&L/Trade:   {total_pnl/len(results):+.2f}%")
    if wins:
        print(f"  Avg Win:          +{sum(r['pnl_pct'] for r in wins)/len(wins):.2f}%")
    if losses:
        print(f"  Avg Loss:          {sum(r['pnl_pct'] for r in losses)/len(losses):.2f}%")
    
    # Validation
    print(f"\n{'='*70}")
    print(f"🔍 STRATEGY VALIDATION")
    print(f"{'='*70}")
    
    wr = len(wins) / len(results) * 100
    
    if wr >= 70:
        print(f"  ✅✅✅ WIN RATE {wr:.1f}% - EXCEPTIONAL!")
    elif wr >= 60:
        print(f"  ✅✅ WIN RATE {wr:.1f}% - TARGET ACHIEVED!")
    elif wr >= 50:
        print(f"  ✅ WIN RATE {wr:.1f}% - Acceptable")
    else:
        print(f"  ❌ WIN RATE {wr:.1f}% - Below target")
    
    if total_pnl > 0:
        print(f"  ✅ Total P&L ({total_pnl:+.2f}%) is positive")
    else:
        print(f"  ❌ Total P&L ({total_pnl:+.2f}%) is negative")
    
    print(f"\n{'='*70}")
    if wr >= 60 and total_pnl > 0:
        print(f"✅✅ TARGET ACHIEVED: {wr:.1f}% WIN RATE!")
    elif wr >= 50 and total_pnl > 0:
        print(f"✅ STRATEGY VALIDATED")
    else:
        print(f"❌ STRATEGY NEEDS IMPROVEMENT")
    print(f"{'='*70}")
    
    # Recent trades
    print(f"\n📋 RECENT TRADES (Last 10)")
    for r in sorted(results, key=lambda x: x['date'], reverse=True)[:10]:
        emoji = "🟢" if r['pnl_pct'] > 0 else "🔴"
        vol = "📊" if r.get('volume_surge') else "  "
        dir_e = "🟢" if r['direction'] == 'LONG' else "🔴"
        print(f"  {emoji}{vol} {r['date'].strftime('%Y-%m-%d')} {dir_e} {r['direction']:5} "
              f"${r['price']:.2f} → ${r['exit_price']:.2f} "
              f"{r['outcome']:12} {r['pnl_pct']:+.2f}%")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--symbol', nargs='+')
    parser.add_argument('--all', action='store_true')
    args = parser.parse_args()
    
    symbols = args.symbol if args.symbol else []
    if args.all:
        symbols = ["META", "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA"]
    
    if not symbols:
        parser.print_help()
        return
    
    print(f"\n{'='*70}")
    print(f"🚀 V9 HIGH PROBABILITY MOMENTUM BACKTEST")
    print(f"{'='*70}")
    print(f"TARGET: 60%+ WIN RATE")
    print(f"\nRequirements:")
    print(f"  LONG: RSI<30 + Bullish engulfing + Volume surge + Above SMA200")
    print(f"  SHORT: RSI>70 + Bearish engulfing + Volume surge + Below SMA200")
    print(f"  Stop/Target: 0.5x ATR (1:1 ratio)")
    print(f"{'='*70}")
    
    all_results = []
    symbol_results = {}
    
    for symbol in symbols:
        print(f"\n{'='*70}")
        print(f"🔍 V9 BACKTEST: {symbol}")
        print(f"{'='*70}")
        
        candles = fetch_data(symbol, 730)
        if len(candles) < 200:
            print(f"⚠️  Not enough data")
            continue
        
        signals = generate_v9_signals(candles)
        print(f"Generated {len(signals)} HIGH PROBABILITY signals")
        
        if not signals:
            print(f"⚠️  No signals generated")
            continue
        
        results = backtest(candles, signals)
        all_results.extend(results)
        symbol_results[symbol] = results
        print_results(results, symbol)
    
    if len(symbols) > 1 and symbol_results:
        print(f"\n{'='*70}")
        print(f"📊 ALL SYMBOLS SUMMARY")
        print(f"{'='*70}")
        
        summary = []
        for sym, res in symbol_results.items():
            if res:
                w = sum(1 for r in res if r['pnl_pct'] > 0)
                pnl = sum(r['pnl_pct'] for r in res)
                summary.append([sym, len(res), f"{w/len(res)*100:.0f}%", f"{pnl:+.1f}%"])
        
        if summary:
            summary.sort(key=lambda x: float(x[3].replace('%','').replace('+','')), reverse=True)
            print(f"\n{'Symbol':<10} {'Trades':<8} {'Win Rate':<10} {'P&L':<10}")
            print("-" * 40)
            for row in summary:
                print(f"{row[0]:<10} {row[1]:<8} {row[2]:<10} {row[3]:<10}")
        
        if all_results:
            print_results(all_results, "ALL SYMBOLS")


if __name__ == "__main__":
    main()
