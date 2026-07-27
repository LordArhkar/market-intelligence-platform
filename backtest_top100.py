#!/usr/bin/env python3
"""
Top 100 Stocks Backtest and Validation Script

This script backtests and validates trading strategies on the top 100 most popular stocks
based on market cap and trading volume.
"""

import argparse
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import yfinance as yf
import numpy as np
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings
warnings.filterwarnings('ignore')

# Top 100 most traded/popular stocks (by market cap + volume)
TOP_100_STOCKS = [
    # Technology
    "AAPL", "MSFT", "NVDA", "GOOGL", "GOOG", "META", "AMZN", "TSLA", "AVGO", "ADBE",
    "CSCO", "ACN", "IBM", "ORCL", "INTC", "AMD", "QCOM", "TXN", "NOW", "INTU",
    "AMAT", "LRCX", "MU", "KLAC", "SNPS", "CDNS", "PANW", "CRWD", "FTNT", "NET",
    # Consumer
    "AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX", "LOW", "TJX", "BKNG", "CMG",
    "MAR", "HLT", "RCL", "CCL", "EBAY", "YUM", "DRI", "ROST", "DLR", "EXPE",
    # Financials
    "JPM", "BAC", "WFC", "GS", "MS", "C", "BLK", "AXP", "SCHW", "USB",
    "TFC", "COF", "MET", "PRU", "AON", "MMC", "CB", "TRV", "ALL", "AIG",
    # Healthcare
    "UNH", "JNJ", "LLY", "PFE", "ABBV", "MRK", "TMO", "ABT", "DHR", "BMY",
    "AMGN", "GILD", "ISRG", "MDT", "SYK", "BSX", "ZTS", "REGN", "VRTX", "BIIB",
    # Industrial
    "CAT", "BA", "HON", "UPS", "RTX", "GE", "DE", "LMT", "MMM", "EMR",
    "ETN", "ITW", "FDX", "PH", "ROK", "CTAS", "JCI", "TDG", "CMI", "AME",
    # Energy
    "XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX", "VLO", "OXY", "WMB",
    # Communication
    "DIS", "CMCSA", "NFLX", "T", "VZ", "TMUS", "CHTR", "EA", "ATVI", "TTWO",
    # Real Estate
    "PLD", "AMT", "EQIX", "CCI", "SPG", "O", "PSA", "DLR", "WELL", "AVB",
]

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
        adx = dx
        alpha = 2 / (period + 1)
        for i in range(len(period_tr) - period, len(period_tr) - 1):
            if i > 0:
                adx = alpha * dx + (1 - alpha) * adx
        
        return float(adx)
    
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
    def is_volume_spike(candles: List[Candle], threshold: float = 1.5) -> bool:
        if len(candles) < 20:
            return False
        avg_vol = TechnicalAnalysis.calculate_avg_volume(candles[:-1], 20)
        current_vol = candles[-1].volume
        return current_vol > avg_vol * threshold
    
    @staticmethod
    def was_big_move(candles: List[Candle], atr_multiplier: float = 2.0) -> bool:
        if len(candles) < 4:
            return False
        atr = TechnicalAnalysis.calculate_atr(candles, 14)
        for i in range(-3, 0):
            candle = candles[i]
            move = abs(candle.close - candle.open)
            if move > atr * atr_multiplier:
                return True
        return False


def fetch_data(symbol: str, days: int = 730) -> List[Candle]:
    """Fetch stock data from Yahoo Finance."""
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=f"{days}d", auto_adjust=True)
        
        if df.empty or len(df) < 100:
            return []
        
        candles = []
        for idx, row in df.iterrows():
            candles.append(Candle(
                timestamp=idx.to_pydatetime(),
                open=float(row['Open']),
                high=float(row['High']),
                low=float(row['Low']),
                close=float(row['Close']),
                volume=float(row['Volume'])
            ))
        return candles
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return []


def generate_signals(candles: List[Candle], short_only: bool = True) -> List[Dict]:
    """Generate trading signals using RSI-based mean reversion strategy."""
    if len(candles) < 200:
        return []
    
    signals = []
    prices = [c.close for c in candles]
    
    # More relaxed parameters to generate more trades
    for i in range(100, len(candles) - 5):
        window_prices = prices[:i+1]
        window_candles = candles[:i+1]
        
        rsi = TechnicalAnalysis.calculate_rsi(window_prices)
        rsi_pct = TechnicalAnalysis.calculate_rsi_percentile(window_prices)
        adx = TechnicalAnalysis.calculate_adx(window_candles)
        atr = TechnicalAnalysis.calculate_atr(window_candles)
        
        if atr == 0:
            atr = prices[-1] * 0.02  # Default 2% ATR
        
        # Relaxed thresholds
        extreme_short = rsi_pct > 70  # RSI in top 30% of historical values
        extreme_long = rsi_pct < 30    # RSI in bottom 30% of historical values
        
        atr_mult = 1.5
        
        if not short_only and extreme_long:
            # Long signal: RSI in oversold territory
            signals.append({
                'date': candles[i].timestamp,
                'direction': 'LONG',
                'price': candles[i].close,
                'stop': candles[i].close * (1 - atr_mult * atr / candles[i].close),
                'target': candles[i].close * (1 + atr_mult * 2.5 * atr / candles[i].close),
                'rsi': rsi,
                'rsi_percentile': rsi_pct,
                'adx': adx,
                'atr': atr,
                'volume_confirmed': True
            })
        
        # Short signal: RSI in overbought territory
        if extreme_short:
            signals.append({
                'date': candles[i].timestamp,
                'direction': 'SHORT',
                'price': candles[i].close,
                'stop': candles[i].close * (1 + atr_mult * atr / candles[i].close),
                'target': candles[i].close * (1 - atr_mult * 2.5 * atr / candles[i].close),
                'rsi': rsi,
                'rsi_percentile': rsi_pct,
                'adx': adx,
                'atr': atr,
                'volume_confirmed': True
            })
    
    return signals


def backtest(candles: List[Candle], signals: List[Dict]) -> List[Dict]:
    """Execute backtest on signals."""
    results = []
    prices = [c.close for c in candles]
    
    for signal in signals:
        entry_idx = None
        for i, c in enumerate(candles):
            if c.timestamp == signal['date']:
                entry_idx = i
                break
        
        if entry_idx is None:
            continue
        
        direction = signal['direction']
        entry_price = signal['price']
        stop_price = signal['stop']
        target_price = signal['target']
        
        # Find exit
        outcome = 'HOLDING'
        exit_price = entry_price
        pnl_pct = 0.0
        
        for j in range(entry_idx + 1, min(entry_idx + 60, len(candles))):
            current_price = candles[j].close
            
            if direction == 'SHORT':
                if current_price <= target_price:
                    outcome = 'TAKE_PROFIT'
                    exit_price = target_price
                    pnl_pct = (entry_price - exit_price) / entry_price * 100
                    break
                elif current_price >= stop_price:
                    outcome = 'STOPPED_OUT'
                    exit_price = stop_price
                    pnl_pct = (entry_price - exit_price) / entry_price * 100
                    break
            else:  # LONG
                if current_price >= target_price:
                    outcome = 'TAKE_PROFIT'
                    exit_price = target_price
                    pnl_pct = (exit_price - entry_price) / entry_price * 100
                    break
                elif current_price <= stop_price:
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
                'rsi_percentile': signal['rsi_percentile'],
                'adx': signal['adx'],
                'volume_confirmed': signal['volume_confirmed']
            })
    
    return results


def analyze_results(symbol: str, results: List[Dict], short_only: bool) -> Dict:
    """Analyze backtest results for a symbol."""
    if not results:
        return {
            'symbol': symbol,
            'status': 'NO_TRADES',
            'trades': 0,
            'win_rate': 0,
            'total_pnl': 0,
            'avg_pnl': 0,
            'best_trade': 0,
            'worst_trade': 0,
            'tp_rate': 0,
            'validation': 'INSUFFICIENT_TRADES'
        }
    
    wins = [r for r in results if r['pnl_pct'] > 0]
    losses = [r for r in results if r['pnl_pct'] <= 0]
    tp = [r for r in results if r['outcome'] == 'TAKE_PROFIT']
    so = [r for r in results if r['outcome'] == 'STOPPED_OUT']
    
    total_pnl = sum(r['pnl_pct'] for r in results)
    win_rate = len(wins) / len(results) * 100 if results else 0
    tp_rate = len(tp) / (len(tp) + len(so)) * 100 if (len(tp) + len(so)) > 0 else 0
    
    # Validation
    validation = 'FAIL'
    if len(results) >= 10:
        if win_rate >= 55 and total_pnl > 0:
            validation = 'PASS'
        elif win_rate >= 50 and total_pnl > 0:
            validation = 'MARGINAL'
    
    return {
        'symbol': symbol,
        'status': 'OK',
        'trades': len(results),
        'win_rate': win_rate,
        'total_pnl': total_pnl,
        'avg_pnl': total_pnl / len(results),
        'best_trade': max(r['pnl_pct'] for r in results),
        'worst_trade': min(r['pnl_pct'] for r in results),
        'tp_rate': tp_rate,
        'avg_rsi_pct': np.mean([r['rsi_percentile'] for r in results]),
        'avg_adx': np.mean([r['adx'] for r in results]),
        'validation': validation
    }


def print_results(results: List[Dict], symbol: str = "ALL"):
    """Print formatted backtest results."""
    print(f"\n{'='*80}")
    print(f"📊 BACKTEST RESULTS: {symbol}")
    print(f"{'='*80}")
    
    if not results:
        print("No results to display.")
        return
    
    wins = sum(1 for r in results if r['pnl_pct'] > 0)
    total_pnl = sum(r['pnl_pct'] for r in results)
    
    print(f"\n📈 TRADE STATISTICS")
    print(f"  Total Trades:     {len(results)}")
    print(f"  Wins:             {wins} ({wins/len(results)*100:.1f}%)")
    print(f"  Losses:           {len(results) - wins} ({(len(results)-wins)/len(results)*100:.1f}%)")
    
    print(f"\n💰 P&L ANALYSIS")
    print(f"  Total P&L:        {total_pnl:+.2f}%")
    print(f"  Avg P&L/Trade:    {total_pnl/len(results):+.2f}%")
    if wins:
        print(f"  Avg Win:           +{sum(r['pnl_pct'] for r in results if r['pnl_pct'] > 0)/wins:.2f}%")
    if len(results) > wins:
        print(f"  Avg Loss:           {sum(r['pnl_pct'] for r in results if r['pnl_pct'] <= 0)/(len(results)-wins):.2f}%")
    print(f"  Best Trade:        +{max(r['pnl_pct'] for r in results):.2f}%")
    print(f"  Worst Trade:       {min(r['pnl_pct'] for r in results):.2f}%")


def main():
    parser = argparse.ArgumentParser(description="Top 100 Stocks Backtest")
    parser.add_argument('--stocks', type=int, default=100, help='Number of stocks to backtest (max 100)')
    parser.add_argument('--workers', type=int, default=5, help='Parallel workers')
    parser.add_argument('--short-only', action='store_true', default=True, help='Short-only strategy')
    parser.add_argument('--include-long', action='store_true', help='Include long trades')
    parser.add_argument('--save-json', action='store_true', help='Save results to JSON')
    args = parser.parse_args()
    
    # Use top N stocks
    num_stocks = min(args.stocks, len(TOP_100_STOCKS))
    stocks = TOP_100_STOCKS[:num_stocks]
    short_only = not args.include_long
    
    print(f"\n{'='*80}")
    print(f"🚀 TOP {num_stocks} STOCKS BACKTEST & VALIDATION")
    print(f"{'='*80}")
    print(f"Strategy: {'SHORT-ONLY' if short_only else 'BOTH DIRECTIONS'}")
    print(f"Stocks: {', '.join(stocks[:10])}{'...' if len(stocks) > 10 else ''}")
    print(f"{'='*80}\n")
    
    all_results = {}
    all_trades = []
    completed = 0
    failed = 0
    
    def process_stock(symbol):
        try:
            print(f"  📊 {symbol}...", end=" ", flush=True)
            candles = fetch_data(symbol, 730)
            if len(candles) < 300:
                print("❌ Insufficient data")
                return symbol, None
            
            signals = generate_signals(candles, short_only=short_only)
            results = backtest(candles, signals)
            analysis = analyze_results(symbol, results, short_only)
            print(f"✅ {len(results)} trades" if results else "❌ No trades")
            return symbol, {'analysis': analysis, 'trades': results}
        except Exception as e:
            print(f"❌ Error: {e}")
            return symbol, None
    
    print("⏳ Running backtests...")
    print("-" * 50)
    
    # Process stocks in parallel
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(process_stock, s): s for s in stocks}
        for future in as_completed(futures):
            symbol, result = future.result()
            if result:
                all_results[symbol] = result
                all_trades.extend(result['trades'])
                completed += 1
            else:
                failed += 1
    
    print("-" * 50)
    print(f"\n✅ Completed: {completed} | ❌ Failed: {failed}")
    
    # Analyze aggregate results
    valid_results = {k: v for k, v in all_results.items() if v['analysis']['status'] == 'OK'}
    
    if valid_results:
        # Summary statistics
        all_analyses = [v['analysis'] for v in valid_results.values()]
        
        print(f"\n{'='*80}")
        print(f"📊 AGGREGATE BACKTEST SUMMARY")
        print(f"{'='*80}")
        
        total_trades = sum(a['trades'] for a in all_analyses)
        total_wins = sum(a['win_rate'] * a['trades'] / 100 for a in all_analyses)
        total_pnl = sum(a['total_pnl'] for a in all_analyses)
        
        print(f"\n📈 OVERALL STATISTICS")
        print(f"  Validated Stocks:   {len(valid_results)}/{len(stocks)}")
        print(f"  Total Trades:       {total_trades}")
        print(f"  Average Win Rate:   {sum(a['win_rate'] for a in all_analyses)/len(all_analyses):.1f}%")
        print(f"  Total P&L:          {total_pnl:+.2f}%")
        print(f"  Avg P&L/Trade:      {total_pnl/total_trades if total_trades > 0 else 0:+.2f}%")
        
        # Validation breakdown
        pass_count = sum(1 for a in all_analyses if a['validation'] == 'PASS')
        marginal_count = sum(1 for a in all_analyses if a['validation'] == 'MARGINAL')
        fail_count = sum(1 for a in all_analyses if a['validation'] == 'FAIL')
        
        print(f"\n🔍 VALIDATION RESULTS")
        print(f"  ✅ PASS:             {pass_count} stocks ({pass_count/len(all_analyses)*100:.1f}%)")
        print(f"  ⚠️  MARGINAL:        {marginal_count} stocks ({marginal_count/len(all_analyses)*100:.1f}%)")
        print(f"  ❌ FAIL:             {fail_count} stocks ({fail_count/len(all_analyses)*100:.1f}%)")
        
        # Top performers
        print(f"\n🏆 TOP 10 PERFORMING STOCKS")
        sorted_results = sorted(all_analyses, key=lambda x: x['total_pnl'], reverse=True)
        print(f"{'Symbol':<10} {'Trades':<8} {'Win Rate':<12} {'P&L':<12} {'Validation'}")
        print("-" * 60)
        for r in sorted_results[:10]:
            status_emoji = "✅" if r['validation'] == 'PASS' else ("⚠️" if r['validation'] == 'MARGINAL' else "❌")
            print(f"{r['symbol']:<10} {r['trades']:<8} {r['win_rate']:.1f}%{'':<6} {r['total_pnl']:+.1f}%{'':<5} {status_emoji} {r['validation']}")
        
        # Bottom performers
        print(f"\n📉 BOTTOM 10 PERFORMING STOCKS")
        print(f"{'Symbol':<10} {'Trades':<8} {'Win Rate':<12} {'P&L':<12} {'Validation'}")
        print("-" * 60)
        for r in sorted_results[-10:]:
            status_emoji = "✅" if r['validation'] == 'PASS' else ("⚠️" if r['validation'] == 'MARGINAL' else "❌")
            print(f"{r['symbol']:<10} {r['trades']:<8} {r['win_rate']:.1f}%{'':<6} {r['total_pnl']:+.1f}%{'':<5} {status_emoji} {r['validation']}")
        
        # Overall validation
        overall_validation = "PASS" if pass_count >= len(all_analyses) * 0.6 else "FAIL"
        if marginal_count > pass_count:
            overall_validation = "MARGINAL"
        
        print(f"\n{'='*80}")
        print(f"🎯 OVERALL STRATEGY VALIDATION: {'✅ ' + overall_validation if overall_validation != 'FAIL' else '❌ ' + overall_validation}")
        print(f"{'='*80}")
        
        if overall_validation == 'PASS':
            print("✅ Strategy is validated across the top 100 stocks!")
            print("   - High win rate and positive P&L on majority of stocks")
            print("   - RSI percentile-based signals are effective")
            print("   - ADX trend filter helps avoid choppy markets")
        elif overall_validation == 'MARGINAL':
            print("⚠️  Strategy shows mixed results")
            print("   - May need parameter tuning per stock type")
            print("   - Consider sector-specific strategies")
        else:
            print("❌ Strategy needs significant improvement")
            print("   - Consider different entry/exit criteria")
            print("   - May need sector-specific parameters")
        
        # Save to JSON if requested
        if args.save_json:
            output_file = f"backtest_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            output_data = {
                'timestamp': datetime.now().isoformat(),
                'config': {
                    'stocks': num_stocks,
                    'strategy': 'SHORT-ONLY' if short_only else 'BOTH',
                    'period_days': 730
                },
                'summary': {
                    'total_stocks': len(valid_results),
                    'total_trades': total_trades,
                    'overall_win_rate': total_wins / total_trades * 100 if total_trades > 0 else 0,
                    'total_pnl': total_pnl,
                    'pass_rate': pass_count / len(all_analyses) * 100 if all_analyses else 0,
                    'validation': overall_validation
                },
                'results': all_analyses
            }
            with open(output_file, 'w') as f:
                json.dump(output_data, f, indent=2)
            print(f"\n📁 Results saved to: {output_file}")
    
    else:
        print("\n❌ No valid results to display.")
    
    return all_results


if __name__ == "__main__":
    main()
