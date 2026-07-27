#!/usr/bin/env python3
"""
Multi-Strategy Backtest for YOUR Specific Assets
Different strategies for different market types

COMMODITIES: Mean Reversion (works great!)
INDICES: Mean Reversion with SMA filter
FOREX: Range-bound Mean Reversion  
STOCKS: Momentum Breakout (NOT mean reversion!)
"""

import yfinance as yf
import numpy as np
from datetime import datetime
import json
import warnings
warnings.filterwarnings('ignore')

# YOUR SPECIFIC ASSETS
YOUR_ASSETS = [
    "AMZN", "AAPL", "META", "NVDA", "TSLA",
    "AUDUSD=X", "GBPUSD=X", "EURUSD=X", "USDJPY=X", "USDCHF=X",
    "GC=F", "SI=F", "CL=F",
    "^DJI", "^N225", "^FTSE"
]

EXTENDED_SYMBOLS = YOUR_ASSETS + [
    "MSFT", "GOOGL", "GOOG", "AVGO", "ADBE", "CSCO", "ACN", "IBM",
    "ORCL", "INTC", "AMD", "QCOM", "TXN", "NOW", "INTU", "AMAT",
    "LRCX", "MU", "KLAC", "SNPS", "CDNS", "PANW", "CRWD", "FTNT", "NET",
    "HD", "MCD", "NKE", "SBUX", "LOW", "TJX", "BKNG", "CMG", "MAR",
    "HLT", "RCL", "CCL", "EBAY", "YUM", "JPM", "BAC", "WFC", "GS", "MS", "C",
    "UNH", "JNJ", "LLY", "PFE", "ABBV", "MRK", "TMO", "XOM", "CVX",
    "CAT", "BA", "HON", "GE", "PL=F"
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


def calc_rsi_pct(prices, period=14, lookback=200):
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


def get_asset_type(symbol):
    if any(x in symbol for x in ['=X']):
        return 'FOREX'
    elif any(x in symbol for x in ['^DJI', '^N225', '^FTSE', '^SPX', '^IXIC']):
        return 'INDEX'
    elif any(x in symbol for x in ['GC=F', 'SI=F', 'CL=F', 'PL=F']):
        return 'COMMODITY'
    return 'STOCK'


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


def generate_signals(candles, symbol):
    if len(candles) < 200:
        return []
    
    signals = []
    prices = [c['close'] for c in candles]
    asset_type = get_asset_type(symbol)
    
    for i in range(200, len(candles) - 5):
        rsi = calc_rsi(prices[:i+1])
        rsi_pct = calc_rsi_pct(prices[:i+1], lookback=200)
        adx = calc_adx(candles[:i+1])
        atr = calc_atr(candles[:i+1])
        sma_20 = calc_sma(prices[:i+1], 20)
        sma_50 = calc_sma(prices[:i+1], 50)
        current_price = candles[i]['close']
        mom_10 = (prices[i] - prices[i-10]) / prices[i-10] if i >= 10 else 0
        
        if atr == 0:
            atr = current_price * 0.02
        
        # COMMODITY: Pure Mean Reversion
        if asset_type == 'COMMODITY':
            atr_mult = 2.0
            if rsi_pct < 25 and rsi < 35 and adx > 20:
                signals.append({
                    'date': candles[i]['date'],
                    'direction': 'LONG',
                    'price': current_price,
                    'stop': round(current_price * (1 - atr_mult * atr / current_price), 4),
                    'target': round(current_price * (1 + atr_mult * 2.5 * atr / current_price), 4),
                    'strategy': 'MEAN_REV'
                })
            if rsi_pct > 75 and rsi > 65 and adx > 20:
                signals.append({
                    'date': candles[i]['date'],
                    'direction': 'SHORT',
                    'price': current_price,
                    'stop': round(current_price * (1 + atr_mult * atr / current_price), 4),
                    'target': round(current_price * (1 - atr_mult * 2.5 * atr / current_price), 4),
                    'strategy': 'MEAN_REV'
                })
        
        # INDEX: Mean Reversion with SMA
        elif asset_type == 'INDEX':
            atr_mult = 2.0
            if rsi_pct < 25 and rsi < 40 and adx > 25 and current_price > sma_50:
                signals.append({
                    'date': candles[i]['date'],
                    'direction': 'LONG',
                    'price': current_price,
                    'stop': round(current_price * (1 - atr_mult * atr / current_price), 4),
                    'target': round(current_price * (1 + atr_mult * 2 * atr / current_price), 4),
                    'strategy': 'MEAN_REV'
                })
            if rsi_pct > 75 and rsi > 60 and adx > 25 and current_price < sma_50:
                signals.append({
                    'date': candles[i]['date'],
                    'direction': 'SHORT',
                    'price': current_price,
                    'stop': round(current_price * (1 + atr_mult * atr / current_price), 4),
                    'target': round(current_price * (1 - atr_mult * 2 * atr / current_price), 4),
                    'strategy': 'MEAN_REV'
                })
        
        # FOREX: Range-bound Mean Reversion
        elif asset_type == 'FOREX':
            atr_mult = 1.5
            if rsi < 30 and rsi_pct < 25:
                signals.append({
                    'date': candles[i]['date'],
                    'direction': 'LONG',
                    'price': current_price,
                    'stop': round(current_price * (1 - atr_mult * atr / current_price), 4),
                    'target': round(current_price * (1 + atr_mult * 2 * atr / current_price), 4),
                    'strategy': 'MEAN_REV'
                })
            if rsi > 70 and rsi_pct > 75:
                signals.append({
                    'date': candles[i]['date'],
                    'direction': 'SHORT',
                    'price': current_price,
                    'stop': round(current_price * (1 + atr_mult * atr / current_price), 4),
                    'target': round(current_price * (1 - atr_mult * 2 * atr / current_price), 4),
                    'strategy': 'MEAN_REV'
                })
        
        # STOCK: Momentum Breakout (NOT Mean Reversion!)
        else:
            atr_mult = 2.5
            # LONG: Strong momentum (not oversold!)
            if current_price > sma_20 and rsi > 50 and rsi < 70 and adx > 30 and mom_10 > 0.02:
                signals.append({
                    'date': candles[i]['date'],
                    'direction': 'LONG',
                    'price': current_price,
                    'stop': round(current_price * (1 - atr_mult * atr / current_price), 4),
                    'target': round(current_price * (1 + atr_mult * 3 * atr / current_price), 4),
                    'strategy': 'MOMENTUM'
                })
    
    return signals


def backtest(candles, signals):
    results = []
    for signal in signals:
        entry_idx = next((i for i, c in enumerate(candles) if c['date'] == signal['date']), None)
        if entry_idx is None:
            continue
        
        direction = signal['direction']
        entry_price = signal['price']
        stop_price = signal['stop']
        target_price = signal['target']
        outcome = 'HOLDING'
        exit_price = entry_price
        pnl_pct = 0.0
        
        for j in range(entry_idx + 1, min(entry_idx + 90, len(candles))):
            cp = candles[j]['close']
            if direction == 'SHORT':
                if cp <= target_price:
                    outcome = 'TAKE_PROFIT'
                    exit_price = target_price
                    pnl_pct = (entry_price - exit_price) / entry_price * 100
                    break
                elif cp >= stop_price:
                    outcome = 'STOPPED_OUT'
                    exit_price = stop_price
                    pnl_pct = (entry_price - exit_price) / entry_price * 100
                    break
            else:
                if cp >= target_price:
                    outcome = 'TAKE_PROFIT'
                    exit_price = target_price
                    pnl_pct = (exit_price - entry_price) / entry_price * 100
                    break
                elif cp <= stop_price:
                    outcome = 'STOPPED_OUT'
                    exit_price = stop_price
                    pnl_pct = (exit_price - entry_price) / entry_price * 100
                    break
        
        if outcome != 'HOLDING':
            results.append({
                'direction': direction,
                'outcome': outcome,
                'pnl_pct': pnl_pct,
                'strategy': signal['strategy']
            })
    
    return results


def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║  MULTI-STRATEGY BACKTEST - YOUR ASSETS                   ║
║  Different strategies for different market types           ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    all_results = {}
    total_trades = 0
    
    for symbol in EXTENDED_SYMBOLS:
        print(f"  {symbol}...", end=" ", flush=True)
        candles = fetch_data(symbol, 730)
        if len(candles) < 200:
            print("❌ No data")
            continue
        signals = generate_signals(candles, symbol)
        results = backtest(candles, signals)
        if results:
            wins = sum(1 for r in results if r['pnl_pct'] > 0)
            total_pnl = sum(r['pnl_pct'] for r in results)
            win_rate = wins / len(results) * 100
            validation = 'PASS' if win_rate >= 60 and total_pnl > 0 else ('MARGINAL' if win_rate >= 50 else 'FAIL')
            all_results[symbol] = {
                'symbol': symbol,
                'trades': len(results),
                'win_rate': win_rate,
                'total_pnl': total_pnl,
                'validation': validation
            }
            total_trades += len(results)
            status = "✅" if validation != 'FAIL' else "❌"
            print(f"{status} {len(results)} trades (WR: {win_rate:.0f}%, P&L: {total_pnl:+.1f}%)")
        else:
            print("❌ No trades")
    
    print(f"\n{'='*60}")
    print("RESULTS")
    print(f"{'='*60}")
    
    if all_results:
        analyses = list(all_results.values())
        total_wins = sum(a['win_rate'] * a['trades'] / 100 for a in analyses)
        avg_wr = total_wins / total_trades * 100 if total_trades > 0 else 0
        total_pnl = sum(a['total_pnl'] for a in analyses)
        
        passes = sum(1 for a in analyses if a['validation'] == 'PASS')
        marginal = sum(1 for a in analyses if a['validation'] == 'MARGINAL')
        
        print(f"\n📊 OVERALL: {len(analyses)} assets, {total_trades} trades")
        print(f"   Avg Win Rate: {avg_wr:.1f}%")
        print(f"   Total P&L: {total_pnl:+.2f}%")
        print(f"   ✅ PASS: {passes}, ⚠️ MARGINAL: {marginal}")
        
        # YOUR ASSETS
        your_results = [all_results.get(s) for s in YOUR_ASSETS if s in all_results]
        if your_results:
            print(f"\n💼 YOUR SPECIFIC ASSETS:")
            print(f"{'Symbol':<15} {'Trades':<8} {'Win Rate':<12} {'P&L':<12} {'Status'}")
            print("-" * 55)
            for a in your_results:
                status = "✅" if a['validation'] == 'PASS' else ("⚠️" if a['validation'] == 'MARGINAL' else "❌")
                print(f"{a['symbol']:<15} {a['trades']:<8} {a['win_rate']:.1f}%{'':<5} {a['total_pnl']:+.1f}%{'':<5} {status}")
        
        # Save
        with open(f"custom_backtest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", 'w') as f:
            json.dump({'results': analyses}, f, indent=2)
    
    print(f"\n{'='*60}")
    print("COMPLETE")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
