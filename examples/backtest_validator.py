"""
Backtest Validator - Test strategies on historical data

This script validates the trading advisor's signals by testing them
on historical data to see if they would have been profitable.

Usage:
    python examples/backtest_validator.py --symbol AAPL
    python examples/backtest_validator.py --symbol AAPL MSFT GOOGL
    python examples/backtest_validator.py --all
"""

import sys
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import yfinance as yf
import numpy as np

# Import patterns from trading advisor pro
sys.path.insert(0, str(__file__).rsplit('/', 2)[0])
from examples.trading_advisor_pro import (
    CandlestickPatterns, TrapDetection, TechnicalAnalysis, Candle
)


def fetch_historical_data(symbol: str, days: int = 365) -> List[Candle]:
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


def generate_historical_signals(candles: List[Candle]) -> List[Dict]:
    """Generate signals at each point in time (simulating live trading)."""
    signals = []
    
    for i in range(50, len(candles)):  # Need 50 candles for patterns
        current_candles = candles[:i]
        current = current_candles[-1]
        
        prices = [c.close for c in current_candles]
        highs = [c.high for c in current_candles]
        lows = [c.low for c in current_candles]
        volumes = [c.volume for c in current_candles]
        
        # Calculate indicators
        rsi = TechnicalAnalysis.calculate_rsi(prices)
        atr = TechnicalAnalysis.calculate_atr(current_candles)
        bb_upper, bb_middle, bb_lower = TechnicalAnalysis.calculate_bollinger(prices)
        
        # Detect patterns
        patterns = CandlestickPatterns.detect_all_patterns(current_candles)
        traps = TrapDetection.detect_all_traps(current_candles)
        
        # Score bullish/bearish
        bullish_score = 0
        bearish_score = 0
        reasons = []
        
        # Pattern scoring
        for pattern, confidence in patterns.items():
            if any(x in pattern for x in ["Bullish", "Hammer", "Morning", "Dragonfly", "White"]):
                bullish_score += confidence
                reasons.append(f"{pattern}(+{confidence:.0f})")
            elif any(x in pattern for x in ["Bearish", "Shooting", "Evening", "Gravestone", "Black"]):
                bearish_score += confidence
                reasons.append(f"{pattern}(-{confidence:.0f})")
        
        # Trap scoring
        for trap, confidence in traps.items():
            if trap in ["Bull Trap", "Bear Trap"]:
                # Traps reverse
                if trap == "Bull Trap":
                    bearish_score += confidence
                    reasons.append(f"{trap}(-{confidence:.0f})")
                else:
                    bullish_score += confidence
                    reasons.append(f"{trap}(+{confidence:.0f})")
        
        # RSI scoring
        if rsi < 35:
            bullish_score += 15
            reasons.append(f"RSI_Oversold(+15)")
        elif rsi > 65:
            bearish_score += 15
            reasons.append(f"RSI_Overbought(-15)")
        
        # Determine signal
        total = bullish_score + bearish_score
        if total > 0:
            if bullish_score > bearish_score * 1.2:  # Need 20% more bullish
                direction = "LONG"
                confidence = min(bullish_score / total * 100, 95)
            elif bearish_score > bullish_score * 1.2:
                direction = "SHORT"
                confidence = min(bearish_score / total * 100, 95)
            else:
                continue  # No clear signal
            
            # Calculate stop and target based on ATR
            if direction == "LONG":
                stop = current.close - (atr * 1.5)
                target = current.close + (atr * 3)
            else:
                stop = current.close + (atr * 1.5)
                target = current.close - (atr * 3)
            
            signals.append({
                'date': current.timestamp,
                'price': current.close,
                'direction': direction,
                'confidence': confidence,
                'stop': stop,
                'target': target,
                'atr': atr,
                'reasons': reasons
            })
    
    return signals


def backtest_signals(candles: List[Candle], signals: List[Dict]) -> List[Dict]:
    """Backtest the signals and calculate P&L."""
    results = []
    
    for signal in signals:
        # Find where price went after signal
        signal_date = signal['date']
        direction = signal['direction']
        entry = signal['price']
        stop = signal['stop']
        target = signal['target']
        
        # Get future candles (next 20 days max)
        future_candles = [c for c in candles if c.timestamp > signal_date][:20]
        
        if not future_candles:
            continue
        
        outcome = "HOLDING"
        exit_price = None
        exit_date = None
        pnl_pct = 0
        days_held = 0
        
        for i, candle in enumerate(future_candles):
            days_held = i + 1
            
            if direction == "LONG":
                if candle.low <= stop:
                    outcome = "STOPPED_OUT"
                    exit_price = stop
                    exit_date = candle.timestamp
                    pnl_pct = ((stop - entry) / entry) * 100
                    break
                elif candle.high >= target:
                    outcome = "TAKE_PROFIT"
                    exit_price = target
                    exit_date = candle.timestamp
                    pnl_pct = ((target - entry) / entry) * 100
                    break
                    
            else:  # SHORT
                if candle.high >= stop:
                    outcome = "STOPPED_OUT"
                    exit_price = stop
                    exit_date = candle.timestamp
                    pnl_pct = ((entry - stop) / entry) * 100
                    break
                elif candle.low <= target:
                    outcome = "TAKE_PROFIT"
                    exit_price = target
                    exit_date = candle.timestamp
                    pnl_pct = ((entry - target) / entry) * 100
                    break
        
        if outcome == "HOLDING":
            # Close at last available price
            last_candle = future_candles[-1]
            exit_price = last_candle.close
            exit_date = last_candle.timestamp
            if direction == "LONG":
                pnl_pct = ((exit_price - entry) / entry) * 100
            else:
                pnl_pct = ((entry - exit_price) / entry) * 100
        
        results.append({
            'symbol': signal.get('symbol', 'UNKNOWN'),
            'date': signal_date,
            'direction': direction,
            'entry': entry,
            'stop': stop,
            'target': target,
            'exit_price': exit_price,
            'exit_date': exit_date,
            'outcome': outcome,
            'pnl_pct': pnl_pct,
            'days_held': days_held,
            'confidence': signal['confidence'],
            'reasons': signal['reasons']
        })
    
    return results


def print_backtest_results(results: List[Dict], symbol: str = ""):
    """Print backtest results."""
    if not results:
        print("\n⚠️  No trades to analyze")
        return
    
    print(f"\n{'='*80}")
    print(f"📊 BACKTEST RESULTS {f'for {symbol}' if symbol else ''}")
    print(f"{'='*80}")
    
    # Summary
    wins = [r for r in results if r['pnl_pct'] > 0]
    losses = [r for r in results if r['pnl_pct'] <= 0]
    tp_hits = [r for r in results if r['outcome'] == 'TAKE_PROFIT']
    so_hits = [r for r in results if r['outcome'] == 'STOPPED_OUT']
    
    total_pnl = sum(r['pnl_pct'] for r in results)
    
    print(f"\n📈 TRADE STATISTICS")
    print(f"  Total Trades:     {len(results)}")
    print(f"  Wins:             {len(wins)} ({len(wins)/len(results)*100:.1f}%)")
    print(f"  Losses:           {len(losses)} ({len(losses)/len(results)*100:.1f}%)")
    print(f"  Take Profits:     {len(tp_hits)} ({len(tp_hits)/len(results)*100:.1f}%)")
    print(f"  Stop Outs:       {len(so_hits)} ({len(so_hits)/len(results)*100:.1f}%)")
    print(f"  Avg Days Held:    {sum(r['days_held'] for r in results)/len(results):.1f}")
    
    print(f"\n💰 P&L ANALYSIS")
    print(f"  Total P&L:        {total_pnl:+.2f}%")
    print(f"  Avg P&L/Trade:    {total_pnl/len(results):+.2f}%")
    print(f"  Avg Win:          +{sum(r['pnl_pct'] for r in wins)/len(wins):.2f}%" if wins else "  Avg Win:          N/A")
    print(f"  Avg Loss:         {sum(r['pnl_pct'] for r in losses)/len(losses):.2f}%" if losses else "  Avg Loss:         N/A")
    print(f"  Best Trade:       +{max(r['pnl_pct'] for r in results):.2f}%")
    print(f"  Worst Trade:      {min(r['pnl_pct'] for r in results):.2f}%")
    
    # Profit factor
    if losses and sum(r['pnl_pct'] for r in losses) != 0:
        pf = abs(sum(r['pnl_pct'] for r in wins) / sum(r['pnl_pct'] for r in losses))
        print(f"  Profit Factor:    {pf:.2f}")
    
    # Confidence analysis
    high_conf = [r for r in results if r['confidence'] >= 70]
    low_conf = [r for r in results if r['confidence'] < 70]
    
    print(f"\n🎯 CONFIDENCE ANALYSIS")
    if high_conf:
        high_pnl = sum(r['pnl_pct'] for r in high_conf)
        print(f"  High Conf (≥70%): {len(high_conf)} trades, {high_pnl:+.2f}% P&L")
    if low_conf:
        low_pnl = sum(r['pnl_pct'] for r in low_conf)
        print(f"  Low Conf (<70%):  {len(low_conf)} trades, {low_pnl:+.2f}% P&L")
    
    # Validation verdict
    print(f"\n{'='*80}")
    print(f"🔍 STRATEGY VALIDATION")
    print(f"{'='*80}")
    
    verdict = []
    issues = []
    
    if len(results) < 30:
        issues.append(f"⚠️  Need {30 - len(results)} more trades for statistical significance")
    else:
        verdict.append("✅ Sufficient sample size")
    
    win_rate = len(wins) / len(results) * 100
    if win_rate < 45:
        issues.append(f"⚠️  Win rate ({win_rate:.1f}%) is too low - strategy may not work")
    elif win_rate < 50:
        issues.append(f"⚠️  Win rate ({win_rate:.1f}%) is marginal")
    else:
        verdict.append(f"✅ Win rate ({win_rate:.1f}%) is acceptable")
    
    if total_pnl <= 0:
        issues.append(f"⚠️  Total P&L ({total_pnl:+.2f}%) is not positive")
    else:
        verdict.append(f"✅ Total P&L ({total_pnl:+.2f}%) is positive")
    
    avg_pnl = total_pnl / len(results)
    if avg_pnl < 0.5:
        issues.append(f"⚠️  Avg trade ({avg_pnl:+.2f}%) is too low to be profitable after costs")
    else:
        verdict.append(f"✅ Avg trade ({avg_pnl:+.2f}%) covers transaction costs")
    
    for v in verdict:
        print(f"  {v}")
    for i in issues:
        print(f"  {i}")
    
    # Final verdict
    print(f"\n{'='*80}")
    if not issues and verdict:
        print(f"✅ STRATEGY APPEARS VALIDATED - Can generate signals")
    elif len(issues) <= 2:
        print(f"⚠️  STRATEGY NEEDS MORE DATA - Continue tracking")
    else:
        print(f"❌ STRATEGY NEEDS IMPROVEMENT - Do not rely on signals alone")
    print(f"{'='*80}")
    
    # Recent trades
    print(f"\n📋 RECENT TRADES (Last 10)")
    print(f"{'-'*80}")
    recent = sorted(results, key=lambda x: x['date'], reverse=True)[:10]
    for r in recent:
        emoji = "🟢" if r['pnl_pct'] > 0 else "🔴"
        print(f"  {emoji} {r['date'].strftime('%Y-%m-%d')} {r['direction']:5} "
              f"${r['entry']:.2f} → ${r['exit_price']:.2f} "
              f"{r['outcome']:12} {r['pnl_pct']:+.2f}%")


def main():
    parser = argparse.ArgumentParser(description='Backtest Validator')
    parser.add_argument('--symbol', nargs='+', help='Symbol(s) to backtest')
    parser.add_argument('--all', action='store_true', help='Backtest all default symbols')
    parser.add_argument('--days', type=int, default=365, help='Days of historical data')
    
    args = parser.parse_args()
    
    symbols = args.symbol if args.symbol else []
    if args.all:
        symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "BTC-USD", "ETH-USD"]
    
    if not symbols:
        parser.print_help()
        print("\n" + "="*60)
        print("Example usage:")
        print("  python examples/backtest_validator.py --symbol AAPL")
        print("  python examples/backtest_validator.py --symbol AAPL MSFT GOOGL")
        print("  python examples/backtest_validator.py --all")
        return
    
    all_results = []
    
    for symbol in symbols:
        print(f"\n{'='*80}")
        print(f"🔍 BACKTESTING {symbol}")
        print(f"{'='*80}")
        
        print(f"Fetching {args.days} days of historical data...")
        candles = fetch_historical_data(symbol, args.days)
        
        if len(candles) < 60:
            print(f"⚠️  Not enough data for {symbol}")
            continue
        
        print(f"Generating signals from {len(candles)} candles...")
        signals = generate_historical_signals(candles)
        
        print(f"Backtesting {len(signals)} signals...")
        for sig in signals:
            sig['symbol'] = symbol
        results = backtest_signals(candles, signals)
        
        all_results.extend(results)
        
        print_backtest_results(results, symbol)
    
    if len(symbols) > 1:
        print_backtest_results(all_results, "ALL SYMBOLS")


if __name__ == "__main__":
    main()
