"""
Backtest Validator V11 - LONG ONLY HIGH PROBABILITY

V10 ISSUE: SHORT trades only 30% WR, dragging down overall performance
V11 SOLUTION: Focus ONLY on LONG trades (which have 58%+ WR)

V11 TARGET: 60%+ WIN RATE on LONG ONLY trades

V11 STRATEGY:
- ONLY LONG trades (no shorts)
- RSI < 35 (oversold)
- Above SMA200 (confirmed uptrend)
- Volume surge or bullish pattern
- Stop: 0.5x ATR
- Target: 0.5x ATR (1:1 ratio)

Usage:
    python examples/backtest_validator_v11.py --symbol META AAPL MSFT GOOGL
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
    def is_volume_surge(candles: List[Candle], threshold: float = 1.1) -> bool:
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


def fetch_data(symbol: str, days: int = 730) -> List[Candle]:
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period=f"{days}d", interval="1d")
    return [Candle(idx, float(r["Open"]), float(r["High"]), float(r["Low"]),
             float(r["Close"]), float(r["Volume"]) if "Volume" in r else 0)
            for idx, r in hist.iterrows()]


def generate_v11_signals(candles: List[Candle]) -> List[dict]:
    """
    V11: LONG ONLY strategy.
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
        
        above_200 = current.close > sma_200
        
        # V11: LONG ONLY requirements
        # RSI < 35 + Above SMA200 + (Volume OR Pattern)
        if (rsi < 35 and above_200 and (volume_surge or bullish_pattern)):
            atr_mult = 0.5
            stop = current.close - (atr * atr_mult)
            target = current.close + (atr * atr_mult)
            
            signals.append({
                'date': current.timestamp,
                'price': current.close,
                'direction': 'LONG',
                'confidence': 80,
                'stop': stop,
                'target': target,
                'rsi': rsi,
                'volume_surge': volume_surge,
                'pattern': bullish_pattern,
                'atr_mult': atr_mult,
                'reasons': [
                    f"RSI oversold ({rsi:.0f})",
                    "Above SMA200",
                    "Volume surge" if volume_surge else "Bullish pattern"
                ],
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
        
        if outcome == "HOLDING":
            last = future[-1]
            exit_price = last.close
            pnl_pct = ((exit_price - entry) / entry) * 100
        
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
    
    print(f"\n{'='*70}")
    print(f"📊 V11 LONG ONLY BACKTEST {f'for {symbol}' if symbol else ''}")
    print(f"{'='*70}")
    
    print(f"\n📈 TRADE STATISTICS")
    print(f"  Total Trades:     {len(results)}")
    print(f"  Wins:           {len(wins)} ({len(wins)/len(results)*100:.1f}%)")
    print(f"  Losses:         {len(losses)} ({len(losses)/len(results)*100:.1f}%)")
    
    print(f"\n💰 P&L ANALYSIS")
    print(f"  Total P&L:      {total_pnl:+.2f}%")
    print(f"  Avg P&L/Trade: {total_pnl/len(results):+.2f}%")
    if wins:
        print(f"  Avg Win:        +{sum(r['pnl_pct'] for r in wins)/len(wins):.2f}%")
    if losses:
        print(f"  Avg Loss:        {sum(r['pnl_pct'] for r in losses)/len(losses):.2f}%")
    
    # Validation
    wr = len(wins) / len(results) * 100
    
    print(f"\n{'='*70}")
    print(f"🔍 VALIDATION")
    print(f"{'='*70}")
    
    if wr >= 70:
        print(f"  ✅✅✅ WIN RATE {wr:.1f}% - EXCEPTIONAL!")
    elif wr >= 60:
        print(f"  ✅✅ WIN RATE {wr:.1f}% - TARGET ACHIEVED!")
    elif wr >= 50:
        print(f"  ✅ WIN RATE {wr:.1f}% - Acceptable")
    else:
        print(f"  ❌ WIN RATE {wr:.1f}% - Below target")
    
    if total_pnl > 0:
        print(f"  ✅ P&L ({total_pnl:+.2f}%) is positive")
    else:
        print(f"  ❌ P&L ({total_pnl:+.2f}%) is negative")
    
    print(f"\n{'='*70}")
    if wr >= 60 and total_pnl > 0:
        print(f"✅✅ TARGET ACHIEVED: {wr:.1f}% WIN RATE!")
    elif wr >= 50 and total_pnl > 0:
        print(f"✅ STRATEGY VALIDATED")
    else:
        print(f"❌ NEEDS IMPROVEMENT")
    print(f"{'='*70}")
    
    # Recent trades
    print(f"\n📋 RECENT TRADES (Last 10)")
    for r in sorted(results, key=lambda x: x['date'], reverse=True)[:10]:
        emoji = "🟢" if r['pnl_pct'] > 0 else "🔴"
        vol = "📊" if r.get('volume_surge') else "  "
        pat = "📐" if r.get('pattern') else "  "
        print(f"  {emoji}{vol}{pat} {r['date'].strftime('%Y-%m-%d')} "
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
    print(f"🚀 V11 LONG ONLY HIGH PROBABILITY BACKTEST")
    print(f"{'='*70}")
    print(f"TARGET: 60%+ WIN RATE (LONG ONLY)")
    print(f"\nRequirements:")
    print(f"  - RSI < 35 (oversold)")
    print(f"  - Above SMA200 (confirmed uptrend)")
    print(f"  - Volume surge OR bullish pattern")
    print(f"  - Stop/Target: 0.5x ATR (1:1 ratio)")
    print(f"{'='*70}")
    
    all_results = []
    symbol_results = {}
    
    for symbol in symbols:
        print(f"\n{'='*70}")
        print(f"🔍 V11 BACKTEST: {symbol}")
        print(f"{'='*70}")
        
        candles = fetch_data(symbol, 730)
        if len(candles) < 200:
            print(f"⚠️  Not enough data")
            continue
        
        signals = generate_v11_signals(candles)
        print(f"Generated {len(signals)} LONG signals")
        
        if not signals:
            print(f"⚠️  No signals")
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
