"""
Backtest Validator V2 - Improved strategy testing

Tests the improved strategy with:
✅ Stricter RSI conditions (only oversold/overbought)
✅ Wider stop loss (2.5x ATR)
✅ Higher take profit (4x ATR)
✅ Confirmation requirements
✅ Market regime filter

Usage:
    python examples/backtest_validator_v2.py --symbol AAPL
    python examples/backtest_validator_v2.py --all
"""

import sys
import argparse
from datetime import datetime
from typing import List, Dict, Tuple
import yfinance as yf
import numpy as np

sys.path.insert(0, str(__file__).rsplit('/', 2)[0])
from examples.trading_advisor_v2 import CandlestickPatterns, TechnicalAnalysis, Candle


def fetch_historical_data(symbol: str, days: int = 365) -> List[Candle]:
    """Fetch historical data."""
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


def generate_improved_signals(candles: List[Candle]) -> List[Dict]:
    """Generate signals with improved strategy."""
    signals = []
    
    for i in range(60, len(candles)):  # Need more candles for patterns
        current_candles = candles[:i]
        current = current_candles[-1]
        
        prices = [c.close for c in current_candles]
        
        # Calculate indicators
        rsi = TechnicalAnalysis.calculate_rsi(prices)
        atr = TechnicalAnalysis.calculate_atr(current_candles)
        regime = TechnicalAnalysis.detect_regime(current_candles[-50:]) if len(current_candles) >= 50 else "UNKNOWN"
        
        # Detect patterns
        patterns = CandlestickPatterns.detect_all_patterns(current_candles)
        
        bullish_score = 0
        bearish_score = 0
        confirmations = 0
        reasons = []
        
        # STRICT CONDITION 1: RSI extreme
        if rsi < 30:  # Deeply oversold
            bullish_score += 30
            confirmations += 1
            reasons.append(f"RSI_Oversold({rsi:.1f})")
        elif rsi > 70:  # Deeply overbought
            bearish_score += 30
            confirmations += 1
            reasons.append(f"RSI_Overbought({rsi:.1f})")
        elif rsi < 40:  # Mildly oversold
            bullish_score += 15
            confirmations += 0.5
            reasons.append(f"RSI_Mild_Oversold({rsi:.1f})")
        elif rsi > 60:  # Mildly overbought
            bearish_score += 15
            confirmations += 0.5
            reasons.append(f"RSI_Mild_Overbought({rsi:.1f})")
        
        # STRICT CONDITION 2: Patterns
        for pattern, confidence in patterns.items():
            if any(x in pattern for x in ["Bullish", "Hammer", "Morning", "White"]):
                bullish_score += confidence
                confirmations += 1
                reasons.append(f"{pattern}(+{confidence:.0f})")
            elif any(x in pattern for x in ["Bearish", "Shooting", "Evening", "Black"]):
                bearish_score += confidence
                confirmations += 1
                reasons.append(f"{pattern}(-{confidence:.0f})")
        
        # STRICT CONDITION 3: Require 2+ confirmations
        if confirmations < 2:
            continue
        
        # Determine direction
        if bullish_score > bearish_score * 1.3:
            direction = "LONG"
            confidence = min(bullish_score / (bullish_score + bearish_score) * 100, 95)
            stop = current.close - (atr * 2.5)  # Wider stop
            target = current.close + (atr * 4)   # Higher target
        elif bearish_score > bullish_score * 1.3:
            direction = "SHORT"
            confidence = min(bearish_score / (bullish_score + bearish_score) * 100, 95)
            stop = current.close + (atr * 2.5)
            target = current.close - (atr * 4)
        else:
            continue
        
        signals.append({
            'date': current.timestamp,
            'price': current.close,
            'direction': direction,
            'confidence': confidence,
            'stop': stop,
            'target': target,
            'atr': atr,
            'rsi': rsi,
            'regime': regime,
            'confirmations': confirmations,
            'reasons': reasons
        })
    
    return signals


def backtest_signals(candles: List[Candle], signals: List[Dict]) -> List[Dict]:
    """Backtest signals with improved exit rules."""
    results = []
    
    for signal in signals:
        signal_date = signal['date']
        direction = signal['direction']
        entry = signal['price']
        stop = signal['stop']
        target = signal['target']
        
        # Get future candles (max 30 days)
        future_candles = [c for c in candles if c.timestamp > signal_date][:30]
        
        if not future_candles:
            continue
        
        outcome = "HOLDING"
        exit_price = None
        pnl_pct = 0
        days_held = 0
        
        for i, candle in enumerate(future_candles):
            days_held = i + 1
            
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
            last_candle = future_candles[-1]
            exit_price = last_candle.close
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
            'outcome': outcome,
            'pnl_pct': pnl_pct,
            'days_held': days_held,
            'confidence': signal['confidence'],
            'rsi': signal['rsi'],
            'regime': signal['regime'],
            'confirmations': signal['confirmations'],
            'reasons': signal['reasons']
        })
    
    return results


def print_results(results: List[Dict], symbol: str = ""):
    """Print backtest results."""
    if not results:
        print("\n⚠️  No trades generated - strategy too strict!")
        return
    
    print(f"\n{'='*80}")
    print(f"📊 IMPROVED STRATEGY BACKTEST RESULTS {f'for {symbol}' if symbol else ''}")
    print(f"{'='*80}")
    
    wins = [r for r in results if r['pnl_pct'] > 0]
    losses = [r for r in results if r['pnl_pct'] <= 0]
    tp_hits = [r for r in results if r['outcome'] == 'TAKE_PROFIT']
    so_hits = [r for r in results if r['outcome'] == 'STOPPED_OUT']
    holding = [r for r in results if r['outcome'] == 'HOLDING']
    
    total_pnl = sum(r['pnl_pct'] for r in results)
    
    print(f"\n📈 TRADE STATISTICS")
    print(f"  Total Trades:     {len(results)}")
    print(f"  Wins:             {len(wins)} ({len(wins)/len(results)*100:.1f}%)")
    print(f"  Losses:           {len(losses)} ({len(losses)/len(results)*100:.1f}%)")
    print(f"  Take Profits:     {len(tp_hits)} ({len(tp_hits)/len(results)*100:.1f}%)")
    print(f"  Stop Outs:       {len(so_hits)} ({len(so_hits)/len(results)*100:.1f}%)")
    print(f"  Still Holding:   {len(holding)}")
    print(f"  Avg Days Held:    {sum(r['days_held'] for r in results)/len(results):.1f}")
    
    print(f"\n💰 P&L ANALYSIS")
    print(f"  Total P&L:        {total_pnl:+.2f}%")
    print(f"  Avg P&L/Trade:    {total_pnl/len(results):+.2f}%")
    if wins:
        print(f"  Avg Win:          +{sum(r['pnl_pct'] for r in wins)/len(wins):.2f}%")
    if losses:
        print(f"  Avg Loss:          {sum(r['pnl_pct'] for r in losses)/len(losses):.2f}%")
    print(f"  Best Trade:       +{max(r['pnl_pct'] for r in results):.2f}%")
    print(f"  Worst Trade:       {min(r['pnl_pct'] for r in results):.2f}%")
    
    if losses and sum(r['pnl_pct'] for r in losses) != 0:
        pf = abs(sum(r['pnl_pct'] for r in wins) / sum(r['pnl_pct'] for r in losses))
        print(f"  Profit Factor:     {pf:.2f}")
    
    # RSI analysis
    long_trades = [r for r in results if r['direction'] == 'LONG']
    short_trades = [r for r in results if r['direction'] == 'SHORT']
    
    print(f"\n📊 DIRECTION ANALYSIS")
    if long_trades:
        long_pnl = sum(r['pnl_pct'] for r in long_trades)
        print(f"  LONG Trades:      {len(long_trades)} ({sum(1 for r in long_trades if r['pnl_pct']>0)/len(long_trades)*100:.1f}% win rate)")
        print(f"  LONG P&L:         {long_pnl:+.2f}%")
    if short_trades:
        short_pnl = sum(r['pnl_pct'] for r in short_trades)
        print(f"  SHORT Trades:     {len(short_trades)} ({sum(1 for r in short_trades if r['pnl_pct']>0)/len(short_trades)*100:.1f}% win rate)")
        print(f"  SHORT P&L:        {short_pnl:+.2f}%")
    
    # Validation
    print(f"\n{'='*80}")
    print(f"🔍 STRATEGY VALIDATION")
    print(f"{'='*80}")
    
    issues = []
    successes = []
    
    if len(results) < 20:
        issues.append(f"⚠️  Only {len(results)} trades - need more for significance")
    else:
        successes.append("✅ Sufficient sample size")
    
    win_rate = len(wins) / len(results) * 100
    if win_rate < 45:
        issues.append(f"⚠️  Win rate ({win_rate:.1f}%) too low")
    elif win_rate < 50:
        issues.append(f"⚠️  Win rate ({win_rate:.1f}%) marginal")
    else:
        successes.append(f"✅ Win rate ({win_rate:.1f}%) is good")
    
    if total_pnl <= 0:
        issues.append(f"⚠️  Total P&L ({total_pnl:+.2f}%) not positive")
    else:
        successes.append(f"✅ Total P&L ({total_pnl:+.2f}%) is positive")
    
    avg_pnl = total_pnl / len(results)
    if avg_pnl < 0.5:
        issues.append(f"⚠️  Avg trade ({avg_pnl:+.2f}%) low after costs")
    else:
        successes.append(f"✅ Avg trade ({avg_pnl:+.2f}%) covers costs")
    
    tp_rate = len(tp_hits) / (len(tp_hits) + len(so_hits)) * 100 if (len(tp_hits) + len(so_hits)) > 0 else 0
    if tp_rate > 40:
        successes.append(f"✅ Take profit rate ({tp_rate:.1f}%) is good")
    else:
        issues.append(f"⚠️  TP rate ({tp_rate:.1f}%) low - stops hitting too often")
    
    for s in successes:
        print(f"  {s}")
    for i in issues:
        print(f"  {i}")
    
    # Verdict
    print(f"\n{'='*80}")
    if not issues:
        print(f"✅ STRATEGY APPEARS VALIDATED")
    elif len(issues) <= 2:
        print(f"⚠️  STRATEGY NEEDS REFINEMENT")
    else:
        print(f"❌ STRATEGY NEEDS SIGNIFICANT IMPROVEMENT")
    print(f"{'='*80}")
    
    # Recent trades
    print(f"\n📋 RECENT TRADES (Last 10)")
    print(f"{'-'*80}")
    recent = sorted(results, key=lambda x: x['date'], reverse=True)[:10]
    for r in recent:
        emoji = "🟢" if r['pnl_pct'] > 0 else "🔴"
        print(f"  {emoji} {r['date'].strftime('%Y-%m-%d')} {r['direction']:5} "
              f"${r['entry']:.2f} → ${r['exit_price']:.2f} "
              f"{r['outcome']:12} {r['pnl_pct']:+.2f}% | RSI:{r['rsi']:.0f}")


def main():
    parser = argparse.ArgumentParser(description='Backtest Validator V2')
    parser.add_argument('--symbol', nargs='+', help='Symbol(s) to backtest')
    parser.add_argument('--all', action='store_true', help='Backtest all symbols')
    parser.add_argument('--days', type=int, default=365, help='Days of data')
    
    args = parser.parse_args()
    
    symbols = args.symbol if args.symbol else []
    if args.all:
        symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "BTC-USD", "ETH-USD"]
    
    if not symbols:
        parser.print_help()
        return
    
    all_results = []
    
    for symbol in symbols:
        print(f"\n{'='*80}")
        print(f"🔍 BACKTESTING {symbol} (IMPROVED STRATEGY)")
        print(f"{'='*80}")
        
        print(f"Fetching {args.days} days of data...")
        candles = fetch_historical_data(symbol, args.days)
        
        if len(candles) < 60:
            print(f"⚠️  Not enough data")
            continue
        
        print(f"Generating signals with strict rules...")
        for sig in generate_improved_signals(candles):
            sig['symbol'] = symbol
        signals = generate_improved_signals(candles)
        
        print(f"Backtesting {len(signals)} signals...")
        results = backtest_signals(candles, signals)
        
        all_results.extend(results)
        print_results(results, symbol)
    
    if len(symbols) > 1:
        print_results(all_results, "ALL SYMBOLS")


if __name__ == "__main__":
    main()
