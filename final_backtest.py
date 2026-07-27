#!/usr/bin/env python3
"""
FINAL BACKTEST - Find the BEST strategy for YOUR 16 assets
Test multiple strategies and identify winners
"""

import yfinance as yf
import numpy as np
from datetime import datetime
import json
import warnings
warnings.filterwarnings('ignore')

# YOUR 16 ASSETS
YOUR_ASSETS = [
    "AMZN", "AAPL", "META", "NVDA", "TSLA",  # Stocks
    "AUDUSD=X", "GBPUSD=X", "EURUSD=X", "USDJPY=X", "USDCHF=X",  # Forex
    "GC=F", "SI=F", "CL=F",  # Commodities
    "^DJI", "^N225", "^FTSE"  # Indices
]


def calc_rsi(prices, period=14):
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


def calc_rsi_pct(prices, period=14, lookback=252):
    if len(prices) < period + lookback:
        return 50.0
    rsi_hist = []
    for i in range(lookback, len(prices)):
        window = prices[i-period:i]
        deltas = np.diff(window)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)
        rsi_hist.append(100 - (100 / (1 + avg_gain / avg_loss)) if avg_loss > 0 else 100)
    if not rsi_hist:
        return 50.0
    current_rsi = calc_rsi(prices[-lookback:])
    below = sum(1 for r in rsi_hist if r < current_rsi)
    return (below / len(rsi_hist)) * 100


def calc_atr(candles, period=14):
    if len(candles) < period + 1:
        return 0
    trs = []
    for i in range(1, len(candles)):
        tr = max(
            candles[i]['high'] - candles[i]['low'],
            abs(candles[i]['high'] - candles[i-1]['close']),
            abs(candles[i]['low'] - candles[i-1]['close'])
        )
        trs.append(tr)
    return float(np.mean(trs[-period:]))


def calc_sma(prices, period):
    if len(prices) < period:
        return prices[-1]
    return float(np.mean(prices[-period:]))


def calc_adx(candles, period=14):
    if len(candles) < period * 2:
        return 20.0
    plus_dm, minus_dm, tr_list = [], [], []
    for i in range(1, len(candles)):
        high_diff = candles[i]['high'] - candles[i-1]['high']
        low_diff = candles[i-1]['low'] - candles[i]['low']
        plus_dm.append(high_diff if high_diff > low_diff and high_diff > 0 else 0)
        minus_dm.append(low_diff if low_diff > high_diff and low_diff > 0 else 0)
        tr = max(candles[i]['high'] - candles[i]['low'],
                abs(candles[i]['high'] - candles[i-1]['close']),
                abs(candles[i]['low'] - candles[i-1]['close']))
        tr_list.append(tr)
    if not tr_list:
        return 20.0
    plus_di = 100 * np.mean(plus_dm[-period:]) / np.mean(tr_list[-period:])
    minus_di = 100 * np.mean(minus_dm[-period:]) / np.mean(tr_list[-period:])
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    return float(dx)


def fetch_data(symbol, days=730):
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=f"{days}d", auto_adjust=True)
        if df.empty or len(df) < 100:
            return []
        candles = []
        for idx, row in df.iterrows():
            candles.append({
                'date': idx.to_pydatetime(),
                'open': float(row['Open']),
                'high': float(row['High']),
                'low': float(row['Low']),
                'close': float(row['Close']),
                'volume': float(row['Volume'])
            })
        return candles
    except:
        return []


def test_strategy(candles, strategy_type):
    """Test a specific strategy type"""
    if len(candles) < 200:
        return []
    
    signals = []
    prices = [c['close'] for c in candles]
    
    for i in range(200, len(candles) - 5):
        rsi = calc_rsi(prices[:i+1])
        rsi_pct = calc_rsi_pct(prices[:i+1], lookback=252)
        adx = calc_adx(candles[:i+1])
        atr = calc_atr(candles[:i+1])
        sma_20 = calc_sma(prices[:i+1], 20)
        sma_50 = calc_sma(prices[:i+1], 50)
        current_price = candles[i]['close']
        
        if atr == 0:
            atr = current_price * 0.02
        
        # STRATEGY 1: STRICT MEAN REVERSION (Original - best for commodities)
        if strategy_type == "STRICT_MR":
            atr_mult = 2.0
            # Only take trades when ALL conditions are perfect
            if rsi_pct < 20 and rsi < 35 and adx > 25 and current_price > sma_50:
                signals.append({
                    'direction': 'LONG',
                    'price': current_price,
                    'stop': current_price * (1 - atr_mult * atr / current_price),
                    'target': current_price * (1 + atr_mult * 2.5 * atr / current_price)
                })
            if rsi_pct > 80 and rsi > 65 and adx > 25 and current_price < sma_50:
                signals.append({
                    'direction': 'SHORT',
                    'price': current_price,
                    'stop': current_price * (1 + atr_mult * atr / current_price),
                    'target': current_price * (1 - atr_mult * 2.5 * atr / current_price)
                })
        
        # STRATEGY 2: MOMENTUM BREAKOUT (for trending stocks)
        elif strategy_type == "MOMENTUM":
            atr_mult = 2.5
            mom_10 = (prices[i] - prices[i-10]) / prices[i-10] if i >= 10 else 0
            # Long only when strong uptrend
            if current_price > sma_20 and current_price > sma_50 and rsi > 45 and rsi < 70 and adx > 30 and mom_10 > 0.03:
                signals.append({
                    'direction': 'LONG',
                    'price': current_price,
                    'stop': current_price * (1 - atr_mult * atr / current_price),
                    'target': current_price * (1 + atr_mult * 3 * atr / current_price)
                })
        
        # STRATEGY 3: RSI ONLY (Simple mean reversion)
        elif strategy_type == "RSI_ONLY":
            atr_mult = 1.5
            if rsi < 30:  # Oversold
                signals.append({
                    'direction': 'LONG',
                    'price': current_price,
                    'stop': current_price * (1 - atr_mult * atr / current_price),
                    'target': current_price * (1 + atr_mult * 3 * atr / current_price)
                })
            if rsi > 70:  # Overbought
                signals.append({
                    'direction': 'SHORT',
                    'price': current_price,
                    'stop': current_price * (1 + atr_mult * atr / current_price),
                    'target': current_price * (1 - atr_mult * 3 * atr / current_price)
                })
        
        # STRATEGY 4: ADX FILTERED (Trend confirmation)
        elif strategy_type == "ADX_FILTER":
            atr_mult = 2.0
            if rsi < 35 and adx > 20:
                signals.append({
                    'direction': 'LONG',
                    'price': current_price,
                    'stop': current_price * (1 - atr_mult * atr / current_price),
                    'target': current_price * (1 + atr_mult * 2 * atr / current_price)
                })
            if rsi > 65 and adx > 20:
                signals.append({
                    'direction': 'SHORT',
                    'price': current_price,
                    'stop': current_price * (1 + atr_mult * atr / current_price),
                    'target': current_price * (1 - atr_mult * 2 * atr / current_price)
                })
        
        # STRATEGY 5: LONG ONLY (Skip shorts entirely)
        elif strategy_type == "LONG_ONLY":
            atr_mult = 2.0
            if rsi_pct < 25 and rsi < 40 and adx > 20:
                signals.append({
                    'direction': 'LONG',
                    'price': current_price,
                    'stop': current_price * (1 - atr_mult * atr / current_price),
                    'target': current_price * (1 + atr_mult * 2.5 * atr / current_price)
                })
    
    return signals


def backtest(candles, signals):
    results = []
    for signal in signals:
        entry_idx = None
        for i, c in enumerate(candles):
            if c['date'] == candles[i]['date']:
                entry_idx = i
                break
        if entry_idx is None:
            for i, c in enumerate(candles):
                if abs(c['close'] - signal['price']) < signal['price'] * 0.01:
                    entry_idx = i
                    break
        
        if entry_idx is None or entry_idx >= len(candles) - 1:
            continue
        
        direction = signal['direction']
        entry_price = signal['price']
        stop = signal['stop']
        target = signal['target']
        pnl_pct = 0.0
        outcome = 'HOLDING'
        
        for j in range(entry_idx + 1, min(entry_idx + 60, len(candles))):
            cp = candles[j]['close']
            if direction == 'SHORT':
                if cp <= target:
                    outcome = 'TAKE_PROFIT'
                    pnl_pct = (entry_price - target) / entry_price * 100
                    break
                elif cp >= stop:
                    outcome = 'STOPPED_OUT'
                    pnl_pct = (entry_price - stop) / entry_price * 100
                    break
            else:
                if cp >= target:
                    outcome = 'TAKE_PROFIT'
                    pnl_pct = (target - entry_price) / entry_price * 100
                    break
                elif cp <= stop:
                    outcome = 'STOPPED_OUT'
                    pnl_pct = (stop - entry_price) / entry_price * 100
                    break
        
        if outcome != 'HOLDING':
            results.append({'pnl_pct': pnl_pct, 'outcome': outcome})
    
    return results


def main():
    strategies = ["STRICT_MR", "MOMENTUM", "RSI_ONLY", "ADX_FILTER", "LONG_ONLY"]
    strategy_names = {
        "STRICT_MR": "Strict Mean Reversion",
        "MOMENTUM": "Momentum Breakout",
        "RSI_ONLY": "RSI Only",
        "ADX_FILTER": "ADX Filtered",
        "LONG_ONLY": "Long Only"
    }
    
    print("""
╔══════════════════════════════════════════════════════════════╗
║  FINDING THE BEST STRATEGY FOR YOUR 16 ASSETS              ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    all_results = {}
    
    for symbol in YOUR_ASSETS:
        print(f"\n📊 {symbol}")
        print("-" * 50)
        
        candles = fetch_data(symbol, 730)
        if len(candles) < 200:
            print("  ❌ Insufficient data")
            continue
        
        best_strategy = None
        best_score = 0
        best_results = None
        
        for strategy in strategies:
            signals = test_strategy(candles, strategy)
            results = backtest(candles, signals)
            
            if not results:
                print(f"  {strategy_names[strategy]}: No trades")
                continue
            
            wins = sum(1 for r in results if r['pnl_pct'] > 0)
            win_rate = wins / len(results) * 100
            total_pnl = sum(r['pnl_pct'] for r in results)
            
            # Score: Prefer higher win rate AND positive P&L
            score = win_rate if total_pnl > 0 else 0
            
            status = "✅" if win_rate >= 60 else ("⚠️" if win_rate >= 50 else "❌")
            print(f"  {status} {strategy_names[strategy]}: {len(results)} trades, {win_rate:.1f}% WR, {total_pnl:+.1f}% P&L")
            
            if score > best_score:
                best_score = score
                best_strategy = strategy
                best_results = {
                    'trades': len(results),
                    'win_rate': win_rate,
                    'total_pnl': total_pnl
                }
        
        if best_strategy:
            all_results[symbol] = {
                'best_strategy': strategy_names[best_strategy],
                **best_results
            }
            print(f"  ⭐ BEST: {strategy_names[best_strategy]} ({best_results['win_rate']:.1f}% WR)")
    
    # SUMMARY
    print(f"""
{'='*70}
📊 FINAL SUMMARY
{'='*70}
    """)
    
    # Count which strategy wins most
    strategy_wins = {}
    for symbol, data in all_results.items():
        s = data['best_strategy']
        strategy_wins[s] = strategy_wins.get(s, 0) + 1
    
    print("Strategy wins by asset count:")
    for strategy, count in sorted(strategy_wins.items(), key=lambda x: x[1], reverse=True):
        print(f"  {strategy}: {count}/16 assets")
    
    # Find overall best strategy
    best_overall = max(strategy_wins.items(), key=lambda x: x[1])
    print(f"\n🏆 RECOMMENDED STRATEGY: {best_overall[0]} ({best_overall[1]} assets)")
    
    # Your assets with results
    print(f"\n💼 YOUR ASSETS - BEST STRATEGY EACH:")
    print(f"{'Symbol':<15} {'Best Strategy':<25} {'Trades':<8} {'Win Rate':<12} {'P&L':<12}")
    print("-" * 70)
    
    for symbol in YOUR_ASSETS:
        if symbol in all_results:
            d = all_results[symbol]
            print(f"{symbol:<15} {d['best_strategy']:<25} {d['trades']:<8} {d['win_rate']:.1f}%{'':<5} {d['total_pnl']:+.1f}%")
        else:
            print(f"{symbol:<15} No valid strategy")
    
    # Count 60%+ win rate assets
    passes = sum(1 for d in all_results.values() if d['win_rate'] >= 60)
    marginal = sum(1 for d in all_results.values() if 50 <= d['win_rate'] < 60)
    print(f"\n📊 VALIDATION:")
    print(f"  ✅ PASS (60%+ WR): {passes} assets")
    print(f"  ⚠️  MARGINAL (50-60%): {marginal} assets")
    
    if passes + marginal >= 12:  # 75% of 16
        print(f"\n✅ RECOMMENDATION: Use {best_overall[0]} - works for {passes + marginal}/16 assets!")
    else:
        print(f"\n⚠️  No single strategy works for all assets. Consider splitting by asset type.")


if __name__ == "__main__":
    main()
