#!/usr/bin/env python3
"""
Multi-strategy signal generation demo.

Tests all strategies on multiple symbols and generates
a comprehensive signal report.
"""

import asyncio
from datetime import datetime, timedelta
from tabulate import tabulate

from mip.data.connectors import YahooFinanceConnector
from mip.data.connectors.base import MarketDataRequest
from mip.strategies.implementations import (
    MomentumStrategy,
    MeanReversionStrategy,
    TrendFollowingStrategy,
    BreakoutStrategy,
    VolatilityStrategy,
)
from mip.risk import RiskManager, RiskLimits


async def analyze_symbol(symbol: str) -> list[dict]:
    """Analyze a symbol with all strategies."""
    results = []
    
    connector = YahooFinanceConnector()
    await connector.connect()
    
    request = MarketDataRequest(
        symbol=symbol,
        start_date=datetime.utcnow() - timedelta(days=180),
        end_date=datetime.utcnow(),
        timeframe="1d",
    )
    data = await connector.get_price_bars(request)
    await connector.disconnect()
    
    if data is None or data.is_empty():
        return results
    
    context = {
        "symbol": symbol,
        "asset_class": "US_EQUITY",
        "timeframe": "1d",
        "regime": "TREND",
    }
    
    strategies = [
        MomentumStrategy(),
        MeanReversionStrategy(),
        TrendFollowingStrategy(),
        BreakoutStrategy(),
        VolatilityStrategy(),
    ]
    
    for strategy in strategies:
        result = await strategy.generate_signals(data, context)
        
        if result.signals:
            signal = result.signals[0]
            results.append({
                "symbol": symbol,
                "strategy": strategy.name,
                "direction": signal.direction.value,
                "confidence": signal.confidence,
                "price": signal.entry_price,
                "stop": signal.stop_loss,
                "target": signal.take_profit_1,
            })
    
    return results


async def main():
    """Run multi-strategy analysis."""
    
    print("=" * 70)
    print("MULTI-STRATEGY SIGNAL REPORT")
    print(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # Symbols to analyze
    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
    
    # Risk manager
    risk_manager = RiskManager(RiskLimits())
    
    all_signals = []
    approved_signals = []
    
    for symbol in symbols:
        print(f"\nAnalyzing {symbol}...")
        signals = await analyze_symbol(symbol)
        all_signals.extend(signals)
        
        for sig in signals:
            print(f"  {sig['strategy']:15s}: {sig['direction']:6s} "
                  f"(confidence: {sig['confidence']:.0f}%, price: ${sig['price']:.2f})")
    
    print("\n" + "=" * 70)
    print("SIGNAL SUMMARY")
    print("=" * 70)
    
    if all_signals:
        # Sort by confidence
        all_signals.sort(key=lambda x: x["confidence"], reverse=True)
        
        # Display table
        table_data = [
            [
                s["symbol"],
                s["strategy"],
                s["direction"],
                f"{s['confidence']:.0f}%",
                f"${s['price']:.2f}",
                f"${s['stop']:.2f}" if s.get("stop") else "N/A",
            ]
            for s in all_signals
        ]
        
        print("\n" + tabulate(
            table_data,
            headers=["Symbol", "Strategy", "Direction", "Confidence", "Entry", "Stop"],
            tablefmt="grid"
        ))
        
        # Filter high-confidence signals
        print("\n" + "=" * 70)
        print("HIGH-CONFIDENCE SIGNALS (>=60%)")
        print("=" * 70)
        
        high_conf = [s for s in all_signals if s["confidence"] >= 60]
        
        if high_conf:
            for sig in high_conf:
                print(f"\n{sig['symbol']} - {sig['strategy']}")
                print(f"  Direction: {sig['direction']}")
                print(f"  Confidence: {sig['confidence']:.0f}%")
                print(f"  Entry: ${sig['price']:.2f}")
                if sig.get("stop"):
                    print(f"  Stop Loss: ${sig['stop']:.2f}")
                if sig.get("target"):
                    print(f"  Target: ${sig['target']:.2f}")
                
                # Check with risk manager
                # (simplified - would need proper Signal object in production)
        else:
            print("\nNo high-confidence signals generated.")
            print("This is expected - strategies require specific conditions to trigger.")
    
    # Strategy distribution
    print("\n" + "=" * 70)
    print("STRATEGY DISTRIBUTION")
    print("=" * 70)
    
    from collections import Counter
    strategy_counts = Counter(s["strategy"] for s in all_signals)
    
    for strategy, count in strategy_counts.items():
        direction_counts = Counter(s["direction"] for s in all_signals if s["strategy"] == strategy)
        longs = direction_counts.get("LONG", 0)
        shorts = direction_counts.get("SHORT", 0)
        print(f"  {strategy:20s}: {count} signals (LONG: {longs}, SHORT: {shorts})")
    
    # Overall stats
    print("\n" + "=" * 70)
    print("OVERALL STATISTICS")
    print("=" * 70)
    
    total_signals = len(all_signals)
    long_signals = sum(1 for s in all_signals if s["direction"] == "LONG")
    short_signals = sum(1 for s in all_signals if s["direction"] == "SHORT")
    avg_confidence = sum(s["confidence"] for s in all_signals) / total_signals if total_signals > 0 else 0
    
    print(f"  Total Signals: {total_signals}")
    print(f"  Long Signals: {long_signals}")
    print(f"  Short Signals: {short_signals}")
    print(f"  Average Confidence: {avg_confidence:.1f}%")
    
    print("\n" + "=" * 70)
    print("DISCLAIMER")
    print("=" * 70)
    print("""
  These signals are generated by backtested strategies and have NOT been
  validated with out-of-sample testing.
  
  - Past performance does not guarantee future results
  - High confidence does not mean high probability of success
  - Transaction costs may significantly impact results
  - Market conditions change and strategies may stop working
  
  The stretch objective of $1,000,000 is NOT guaranteed.
  
  Paper trading with virtual money only. Not financial advice.
    """)


if __name__ == "__main__":
    asyncio.run(main())
