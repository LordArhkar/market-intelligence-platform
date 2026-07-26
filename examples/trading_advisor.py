#!/usr/bin/env python3
"""
Trading Advisor - Live Market Analysis Tool

Generates actionable trading recommendations based on live market data.
Use these as ideas for manual trading on UpsideOnly.com

DISCLAIMER: This is research/education only. Not financial advice.
Past performance does not guarantee future results.
"""

import asyncio
from datetime import datetime
from tabulate import tabulate

from mip.data.connectors import YahooFinanceConnector, CCXTConnector
from mip.data.connectors.base import MarketDataRequest
from mip.strategies.implementations import (
    MomentumStrategy,
    MeanReversionStrategy,
    TrendFollowingStrategy,
    BreakoutStrategy,
    VolatilityStrategy,
)


# Trading symbols - edit this list to add/remove symbols
US_STOCKS = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AMD", "NFLX", "SPY"]
CRYPTO = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "DOGE/USDT", "XRP/USDT"]


async def analyze_stock(connector: YahooFinanceConnector, symbol: str) -> dict:
    """Analyze a single stock with all strategies."""
    result = {
        "symbol": symbol,
        "asset_class": "US STOCK",
        "recommendations": [],
        "current_price": None,
        "change_pct": None,
    }
    
    try:
        request = MarketDataRequest(
            symbol=symbol,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow(),
            timeframe="1d",
        )
        data = await connector.get_price_bars(request)
        
        if data is None or data.is_empty():
            return result
        
        # Get current price
        result["current_price"] = data["close"][-1]
        if len(data) > 1:
            result["change_pct"] = ((data["close"][-1] / data["close"][-2]) - 1) * 100
        
        # Get historical for strategies
        hist_request = MarketDataRequest(
            symbol=symbol,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow(),
            timeframe="1d",
        )
        hist_data = await connector.get_price_bars(hist_request)
        
        # Fetch more history
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="6mo")
        
        if len(hist) < 30:
            return result
        
        # Convert to polars
        import polars as pl
        df = pl.DataFrame({
            "timestamp": hist.index.tolist(),
            "open": hist["Open"].tolist(),
            "high": hist["High"].tolist(),
            "low": hist["Low"].tolist(),
            "close": hist["Close"].tolist(),
            "volume": hist["Volume"].tolist(),
        })
        
        context = {
            "symbol": symbol,
            "asset_class": "US_EQUITY",
            "timeframe": "1d",
            "regime": "TREND",
        }
        
        strategies = [
            ("Momentum", MomentumStrategy()),
            ("Mean Reversion", MeanReversionStrategy()),
            ("Trend Following", TrendFollowingStrategy()),
            ("Breakout", BreakoutStrategy()),
            ("Volatility", VolatilityStrategy()),
        ]
        
        for name, strategy in strategies:
            sig_result = await strategy.generate_signals(df, context)
            
            if sig_result.signals:
                signal = sig_result.signals[0]
                if signal.direction.value != "NEUTRAL":
                    result["recommendations"].append({
                        "strategy": name,
                        "direction": signal.direction.value,
                        "confidence": signal.confidence,
                        "entry": signal.entry_price,
                        "stop": signal.stop_loss,
                        "target": signal.take_profit_1,
                        "evidence": signal.supporting_evidence[:2] if signal.supporting_evidence else [],
                    })
    
    except Exception as e:
        print(f"  Error analyzing {symbol}: {e}")
    
    return result


async def analyze_crypto(connector: CCXTConnector, symbol: str) -> dict:
    """Analyze a single crypto with all strategies."""
    result = {
        "symbol": symbol,
        "asset_class": "CRYPTO",
        "recommendations": [],
        "current_price": None,
        "change_pct": None,
    }
    
    try:
        data = await connector.get_ohlcv(symbol, "1d", limit=180)
        
        if data is None or len(data) == 0:
            return result
        
        import polars as pl
        df = pl.DataFrame(data)
        df.columns = ["timestamp", "open", "high", "low", "close", "volume"]
        
        result["current_price"] = df["close"][-1]
        if len(df) > 1:
            result["change_pct"] = ((df["close"][-1] / df["close"][-2]) - 1) * 100
        
        context = {
            "symbol": symbol,
            "asset_class": "CRYPTO",
            "timeframe": "1d",
            "regime": "TREND",
        }
        
        strategies = [
            ("Momentum", MomentumStrategy()),
            ("Mean Reversion", MeanReversionStrategy()),
            ("Trend Following", TrendFollowingStrategy()),
            ("Breakout", BreakoutStrategy()),
            ("Volatility", VolatilityStrategy()),
        ]
        
        for name, strategy in strategies:
            sig_result = await strategy.generate_signals(df, context)
            
            if sig_result.signals:
                signal = sig_result.signals[0]
                if signal.direction.value != "NEUTRAL":
                    result["recommendations"].append({
                        "strategy": name,
                        "direction": signal.direction.value,
                        "confidence": signal.confidence,
                        "entry": signal.entry_price,
                        "stop": signal.stop_loss,
                        "target": signal.take_profit_1,
                        "evidence": signal.supporting_evidence[:2] if signal.supporting_evidence else [],
                    })
    
    except Exception as e:
        print(f"  Error analyzing {symbol}: {e}")
    
    return result


async def main():
    """Run trading advisor."""
    
    print("=" * 70)
    print("🚀 TRADING ADVISOR - LIVE MARKET ANALYSIS")
    print("=" * 70)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    print("⚠️  DISCLAIMER: This is research/education only.")
    print("   Always do your own analysis before trading.")
    print("=" * 70)
    
    all_recommendations = []
    
    # ============ US STOCKS ============
    print("\n" + "=" * 70)
    print("📈 US STOCKS ANALYSIS")
    print("=" * 70)
    
    stock_connector = YahooFinanceConnector()
    await stock_connector.connect()
    
    for symbol in US_STOCKS:
        print(f"\n🔍 Analyzing {symbol}...")
        result = await analyze_stock(stock_connector, symbol)
        
        if result["current_price"]:
            change = f"{result['change_pct']:+.2f}%" if result['change_pct'] else "N/A"
            print(f"   Price: ${result['current_price']:.2f} ({change})")
            
            for rec in result["recommendations"]:
                rec["symbol"] = symbol
                rec["asset_class"] = "US STOCK"
                all_recommendations.append(rec)
                emoji = "🟢" if rec["direction"] == "LONG" else "🔴"
                print(f"   {emoji} {rec['strategy']}: {rec['direction']} "
                      f"(Confidence: {rec['confidence']:.0f}%)")
    
    await stock_connector.disconnect()
    
    # ============ CRYPTO ============
    print("\n" + "=" * 70)
    print("🪙 CRYPTOCURRENCY ANALYSIS")
    print("=" * 70)
    
    crypto_connector = CCXTConnector()
    await crypto_connector.connect()
    
    for symbol in CRYPTO:
        print(f"\n🔍 Analyzing {symbol}...")
        result = await analyze_crypto(crypto_connector, symbol)
        
        if result["current_price"]:
            change = f"{result['change_pct']:+.2f}%" if result['change_pct'] else "N/A"
            print(f"   Price: ${result['current_price']:.2f} ({change})")
            
            for rec in result["recommendations"]:
                rec["symbol"] = symbol
                rec["asset_class"] = "CRYPTO"
                all_recommendations.append(rec)
                emoji = "🟢" if rec["direction"] == "LONG" else "🔴"
                print(f"   {emoji} {rec['strategy']}: {rec['direction']} "
                      f"(Confidence: {rec['confidence']:.0f}%)")
    
    await crypto_connector.disconnect()
    
    # ============ SUMMARY ============
    print("\n" + "=" * 70)
    print("📋 TRADING RECOMMENDATIONS SUMMARY")
    print("=" * 70)
    
    if all_recommendations:
        # Sort by confidence
        all_recommendations.sort(key=lambda x: x["confidence"], reverse=True)
        
        # Filter high confidence
        high_conf = [r for r in all_recommendations if r["confidence"] >= 50]
        
        if high_conf:
            print("\n🎯 HIGH CONFIDENCE SIGNALS (≥50%):")
            print("-" * 70)
            
            table_data = []
            for rec in high_conf:
                stop_str = f"${rec['stop']:.2f}" if rec.get("stop") else "N/A"
                target_str = f"${rec['target']:.2f}" if rec.get("target") else "N/A"
                table_data.append([
                    rec["symbol"],
                    rec["direction"],
                    f"{rec['confidence']:.0f}%",
                    f"${rec['entry']:.2f}" if rec.get("entry") else "Market",
                    stop_str,
                    target_str,
                    rec["strategy"],
                ])
            
            print(tabulate(
                table_data,
                headers=["Symbol", "Direction", "Confidence", "Entry", "Stop Loss", "Target", "Strategy"],
                tablefmt="grid"
            ))
            
            print("\n📝 HOW TO USE FOR UPSIDEONLY:")
            print("-" * 70)
            for rec in high_conf[:5]:
                direction = "BUY" if rec["direction"] == "LONG" else "SELL"
                print(f"\n{rec['symbol']}:")
                print(f"  → Action: {direction}")
                print(f"  → Entry: ${rec['entry']:.2f}" if rec.get("entry") else "  → Entry: Market price")
                print(f"  → Stop Loss: ${rec['stop']:.2f}" if rec.get("stop") else "  → Stop Loss: Set your own")
                print(f"  → Take Profit: ${rec['target']:.2f}" if rec.get("target") else "  → Take Profit: Set your own")
                print(f"  → Confidence: {rec['confidence']:.0f}% ({rec['strategy']})")
                if rec.get("evidence"):
                    print(f"  → Why: {rec['evidence'][0]}")
        else:
            print("\n⚠️ No high-confidence signals found.")
            print("   Market conditions don't favor clear entry points.")
    
    # All signals
    print("\n" + "=" * 70)
    print("📊 ALL SIGNALS (Lower Confidence)")
    print("=" * 70)
    
    if all_recommendations:
        low_conf = [r for r in all_recommendations if r["confidence"] < 50]
        if low_conf:
            table_data = []
            for rec in low_conf:
                table_data.append([
                    rec["symbol"],
                    rec["direction"],
                    f"{rec['confidence']:.0f}%",
                    rec["strategy"],
                ])
            
            print(tabulate(
                table_data,
                headers=["Symbol", "Direction", "Confidence", "Strategy"],
                tablefmt="simple"
            ))
            print("\n💡 These signals have lower confidence - consider as ideas only")
    
    # Stats
    longs = sum(1 for r in all_recommendations)
    shorts = sum(1 for r in all_recommendations)
    
    print("\n" + "=" * 70)
    print("📈 MARKET OVERVIEW")
    print("=" * 70)
    print(f"  Total Signals: {len(all_recommendations)}")
    print(f"  Bullish (LONG): {sum(1 for r in all_recommendations if r['direction'] == 'LONG')}")
    print(f"  Bearish (SHORT): {sum(1 for r in all_recommendations if r['direction'] == 'SHORT')}")
    
    print("\n" + "=" * 70)
    print("⚠️ IMPORTANT REMINDERS")
    print("=" * 70)
    print("""
1. These are RESEARCH SIGNALS only - not financial advice
2. ALWAYS do your own analysis before trading
3. Past performance does NOT guarantee future results
4. Only trade what you can afford to lose
5. The $1,000,000 goal is NOT guaranteed
6. UpsideOnly paper trading uses virtual money - no real risk here
    """)


if __name__ == "__main__":
    asyncio.run(main())
