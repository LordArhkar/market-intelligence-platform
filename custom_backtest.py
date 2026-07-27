#!/usr/bin/env python3
"""
Custom Backtest Script - Your Specific Assets
Stocks, Forex, Commodities, Indices
"""

import sys
import yfinance as yf
import numpy as np
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# Your custom watchlist
SYMBOLS = [
    # Stocks
    "AMZN",   # Amazon
    "AAPL",   # Apple
    "META",   # Meta
    "NVDA",   # Nvidia
    "TSLA",   # Tesla
    
    # Forex ( Forex pairs in Yahoo Finance format)
    "AUDUSD=X",  # Australian Dollar / USD
    "GBPUSD=X",  # British Pound / USD
    "EURUSD=X",  # Euro / USD
    "USDJPY=X",  # USD / Japanese Yen
    "USDCHF=X",  # USD / Swiss Franc
    
    # Commodities
    "GC=F",   # Gold Futures
    "SI=F",   # Silver Futures
    "CL=F",   # Crude Oil (WTI)
    
    # Indices
    "^DJI",   # Dow Jones Industrial
    "^N225",  # Nikkei 225 (Japan)
    "^FTSE",  # FTSE 100 (UK)
]

# Extended watchlist for 100+ trades
EXTENDED_SYMBOLS = SYMBOLS + [
    # More stocks
    "MSFT", "GOOGL", "GOOG", "AMZN", "AVGO", "ADBE",
    "CSCO", "ACN", "IBM", "ORCL", "INTC", "AMD", "QCOM",
    "TXN", "NOW", "INTU", "AMAT", "LRCX", "MU", "KLAC",
    "SNPS", "CDNS", "PANW", "CRWD", "FTNT", "NET",
    "HD", "MCD", "NKE", "SBUX", "LOW", "TJX", "BKNG",
    "CMG", "MAR", "HLT", "RCL", "CCL", "EBAY", "YUM",
    "JPM", "BAC", "WFC", "GS", "MS", "C", "BLK",
    "UNH", "JNJ", "LLY", "PFE", "ABBV", "MRK", "TMO",
    "XOM", "CVX", "COP", "CAT", "BA", "HON", "GE",
    
    # More forex/commodities
    "USDCAD=X", "USDGBP=X", "EURGBP=X", "AUDJPY=X",
    "HG=F",   # Copper
    "NG=F",   # Natural Gas
    "PL=F",   # Platinum
    "PA=F",   # Palladium
    
    # More indices
    "^SPX",   # S&P 500
    "^IXIC",  # Nasdaq
    "^RUT",   # Russell 2000
    "^GDAXI", # DAX (Germany)
    "^CAC40", # CAC 40 (France)
]


class TechnicalAnalysis:
    @staticmethod
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
    
    @staticmethod
    def calc_rsi_percentile(prices, period=14, lookback=200):
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
        current_rsi = TechnicalAnalysis.calc_rsi(prices[-lookback:])
        below = sum(1 for r in rsi_hist if r < current_rsi)
        return (below / len(rsi_hist)) * 100
    
    @staticmethod
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
    
    @staticmethod
    def calc_sma(prices, period):
        if len(prices) < period:
            return prices[-1]
        return float(np.mean(prices[-period:]))
    
    @staticmethod
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
        plus_di = 100 * np.mean(plus_dm[-period:]) / np.mean(tr_list[-period:]) if np.mean(tr_list[-period:]) > 0 else 0
        minus_di = 100 * np.mean(minus_dm[-period:]) / np.mean(tr_list[-period:]) if np.mean(tr_list[-period:]) > 0 else 0
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di) if (plus_di + minus_di) > 0 else 0
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
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return []


def generate_signals(candles):
    if len(candles) < 200:
        return []
    
    signals = []
    prices = [c['close'] for c in candles]
    ta = TechnicalAnalysis()
    
    for i in range(200, len(candles) - 5):
        rsi = ta.calc_rsi(prices[:i+1])
        rsi_pct = ta.calc_rsi_percentile(prices[:i+1], lookback=200)
        adx = ta.calc_adx(candles[:i+1])
        atr = ta.calc_atr(candles[:i+1])
        sma_50 = ta.calc_sma(prices[:i+1], 50)
        current_price = candles[i]['close']
        
        if atr == 0:
            atr = current_price * 0.02
        
        atr_mult = 2.0
        
        # LONG signal
        if rsi_pct < 25 and rsi < 45 and adx > 20 and current_price > sma_50:
            signals.append({
                'date': candles[i]['date'],
                'direction': 'LONG',
                'price': current_price,
                'stop': round(current_price * (1 - atr_mult * atr / current_price), 4),
                'target': round(current_price * (1 + atr_mult * 2 * atr / current_price), 4),
                'rsi': rsi,
                'rsi_pct': rsi_pct,
                'adx': adx
            })
        
        # SHORT signal
        if rsi_pct > 75 and rsi > 55 and adx > 20 and current_price < sma_50:
            signals.append({
                'date': candles[i]['date'],
                'direction': 'SHORT',
                'price': current_price,
                'stop': round(current_price * (1 + atr_mult * atr / current_price), 4),
                'target': round(current_price * (1 - atr_mult * 2 * atr / current_price), 4),
                'rsi': rsi,
                'rsi_pct': rsi_pct,
                'adx': adx
            })
    
    return signals


def backtest(candles, signals):
    results = []
    for signal in signals:
        entry_idx = None
        for i, c in enumerate(candles):
            if c['date'] == signal['date']:
                entry_idx = i
                break
        if entry_idx is None:
            continue
        
        direction = signal['direction']
        entry_price = signal['price']
        stop_price = signal['stop']
        target_price = signal['target']
        outcome = 'HOLDING'
        exit_price = entry_price
        pnl_pct = 0.0
        
        for j in range(entry_idx + 1, min(entry_idx + 60, len(candles))):
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
                'date': signal['date'],
                'direction': direction,
                'price': entry_price,
                'exit_price': exit_price,
                'outcome': outcome,
                'pnl_pct': pnl_pct,
                'rsi_pct': signal['rsi_pct'],
                'adx': signal['adx']
            })
    
    return results


def analyze(symbol, results):
    if not results:
        return None
    
    wins = sum(1 for r in results if r['pnl_pct'] > 0)
    total_pnl = sum(r['pnl_pct'] for r in results)
    win_rate = wins / len(results) * 100
    avg_pnl = total_pnl / len(results)
    
    return {
        'symbol': symbol,
        'trades': len(results),
        'win_rate': win_rate,
        'total_pnl': total_pnl,
        'avg_pnl': avg_pnl,
        'validation': 'PASS' if win_rate >= 60 and total_pnl > 0 else ('MARGINAL' if win_rate >= 50 else 'FAIL')
    }


def main():
    # Use extended list for 100+ trades
    symbols = EXTENDED_SYMBOLS
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║  CUSTOM BACKTEST - YOUR ASSETS + EXTENDED WATCHLIST         ║
║  Target: 60%+ Win Rate Strategy                            ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    print(f"📊 Testing {len(symbols)} assets for 100+ trades...\n")
    
    all_results = {}
    total_trades = 0
    
    for symbol in symbols:
        print(f"  📊 {symbol}...", end=" ", flush=True)
        candles = fetch_data(symbol, 730)
        if len(candles) < 200:
            print("❌ Insufficient data")
            continue
        signals = generate_signals(candles)
        results = backtest(candles, signals)
        if results:
            analysis = analyze(symbol, results)
            if analysis:
                all_results[symbol] = analysis
                total_trades += len(results)
                status = "✅" if analysis['validation'] != 'FAIL' else "❌"
                print(f"{status} {len(results)} trades (WR: {analysis['win_rate']:.0f}%, P&L: {analysis['total_pnl']:+.1f}%)")
        else:
            print("❌ No trades")
    
    print(f"\n{'='*70}")
    print(f"📊 CUSTOM BACKTEST RESULTS")
    print(f"{'='*70}")
    
    if all_results:
        analyses = list(all_results.values())
        
        # Overall stats
        total_wins = sum(a['win_rate'] * a['trades'] / 100 for a in analyses)
        total_pnl = sum(a['total_pnl'] for a in analyses)
        avg_wr = total_wins / total_trades * 100 if total_trades > 0 else 0
        
        print(f"\n📈 OVERALL STATISTICS")
        print(f"  Assets Tested:        {len(all_results)}")
        print(f"  Total Trades:       {total_trades}")
        print(f"  Average Win Rate:   {avg_wr:.1f}%")
        print(f"  Total P&L:         {total_pnl:+.2f}%")
        
        # Validation
        passes = sum(1 for a in analyses if a['validation'] == 'PASS')
        marginal = sum(1 for a in analyses if a['validation'] == 'MARGINAL')
        
        print(f"\n🔍 VALIDATION")
        print(f"  ✅ PASS (60%+ WR):  {passes} assets")
        print(f"  ⚠️  MARGINAL:       {marginal} assets")
        print(f"  ❌ FAIL:            {len(analyses) - passes - marginal} assets")
        
        # Top performers
        print(f"\n🏆 TOP 15 PERFORMING ASSETS")
        print(f"{'Symbol':<15} {'Trades':<8} {'Win Rate':<12} {'P&L':<12} {'Status'}")
        print("-" * 60)
        for a in sorted(analyses, key=lambda x: x['total_pnl'], reverse=True)[:15]:
            status = "✅" if a['validation'] == 'PASS' else ("⚠️" if a['validation'] == 'MARGINAL' else "❌")
            print(f"{a['symbol']:<15} {a['trades']:<8} {a['win_rate']:.1f}%{'':<5} {a['total_pnl']:+.1f}%{'':<5} {status}")
        
        # Your specific assets
        your_assets = ['AMZN', 'AAPL', 'META', 'NVDA', 'TSLA', 'AUDUSD=X', 'GBPUSD=X', 
                      'EURUSD=X', 'USDJPY=X', 'USDCHF=X', 'GC=F', 'SI=F', 'CL=F', 
                      '^DJI', '^N225', '^FTSE']
        your_results = [all_results.get(s) for s in your_assets if s in all_results]
        
        if your_results:
            print(f"\n💼 YOUR SPECIFIC ASSETS")
            print(f"{'Symbol':<15} {'Trades':<8} {'Win Rate':<12} {'P&L':<12} {'Status'}")
            print("-" * 60)
            for a in your_results:
                status = "✅" if a['validation'] == 'PASS' else ("⚠️" if a['validation'] == 'MARGINAL' else "❌")
                print(f"{a['symbol']:<15} {a['trades']:<8} {a['win_rate']:.1f}%{'':<5} {a['total_pnl']:+.1f}%{'':<5} {status}")
        
        # Save results
        import json
        filename = f"custom_backtest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'total_trades': total_trades,
                'avg_win_rate': avg_wr,
                'total_pnl': total_pnl,
                'results': analyses
            }, f, indent=2)
        print(f"\n📁 Results saved to: {filename}")
    
    print(f"\n{'='*70}")
    print("✅ BACKTEST COMPLETE")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
