#!/usr/bin/env python3
"""
Trading Advisor - Live Market Analysis Tool

Generates actionable trading recommendations based on live market data.
Use these as ideas for manual trading on UpsideOnly.com

DISCLAIMER: This is research/education only. Not financial advice.
Past performance does not guarantee future results.

====================================
CUSTOMIZATION OPTIONS (Edit below):
====================================
1. CONFIDENCE_THRESHOLD - Minimum confidence to show (0-100)
   Lower = more signals, higher = stricter signals
2. US_STOCKS - List of stock symbols to analyze
3. CRYPTO - List of crypto pairs to analyze
====================================
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


# =====================================
# CUSTOMIZATION OPTIONS - EDIT THESE:
# =====================================

# Minimum confidence to show (0-100)
# 40 = Shows most signals (default)
# 50 = Only medium-high confidence
# 60 = Only high confidence
# 70 = Only very high confidence
CONFIDENCE_THRESHOLD = 40

# Stock symbols to analyze (add/remove as needed)
US_STOCKS = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AMD", "NFLX", "SPY", "QQQ", "IWM"]

# Crypto pairs to analyze
CRYPTO = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "DOGE/USDT", "XRP/USDT", "ADA/USDT", "AVAX/USDT"]

# =====================================


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
        # Fetch historical data using yfinance directly (more reliable)
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="6mo")
        
        if hist is None or len(hist) < 30:
            return result
        
        # Get current price from last available bar
        result["current_price"] = float(hist["Close"].iloc[-1])
        if len(hist) > 1:
            result["change_pct"] = ((hist["Close"].iloc[-1] / hist["Close"].iloc[-2]) - 1) * 100
        
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
        # Use yfinance for crypto (more reliable than CCXT sometimes)
        import yfinance as yf
        
        # Convert BTC/USDT to BTC-USD for yfinance
        yf_symbol = symbol.replace("/USDT", "-USD").replace("/", "-")
        
        ticker = yf.Ticker(yf_symbol)
        hist = ticker.history(period="6mo")
        
        if hist is None or len(hist) < 30:
            return result
        
        result["current_price"] = float(hist["Close"].iloc[-1])
        if len(hist) > 1:
            result["change_pct"] = ((hist["Close"].iloc[-1] / hist["Close"].iloc[-2]) - 1) * 100
        
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
    print(f"   (Showing signals with confidence ≥ {CONFIDENCE_THRESHOLD}%)")
    print("=" * 70)
    
    if all_recommendations:
        # Sort by confidence
        all_recommendations.sort(key=lambda x: x["confidence"], reverse=True)
        
        # Filter by threshold
        filtered_signals = [r for r in all_recommendations if r["confidence"] >= CONFIDENCE_THRESHOLD]
        
        if filtered_signals:
            print("\n🎯 ACTIONABLE SIGNALS:")
            print("-" * 70)
            
            # Detailed trade cards
            for i, rec in enumerate(filtered_signals[:10], 1):
                direction = "🟢 BUY (LONG)" if rec["direction"] == "LONG" else "🔴 SELL (SHORT)"
                risk = (rec.get("stop") and rec.get("entry")) and abs((rec["stop"] - rec["entry"]) / rec["entry"]) * 100 if rec.get("entry") else 0
                reward = (rec.get("target") and rec.get("entry")) and abs((rec["target"] - rec["entry"]) / rec["entry"]) * 100 if rec.get("entry") else 0
                
                print(f"\n{'─' * 70}")
                print(f"  #{i} {rec['symbol']} - {direction}")
                print(f"  {'─' * 70}")
                print(f"  📊 Confidence: {rec['confidence']:.0f}% ({rec['strategy']})")
                print(f"  💰 Entry Price: ${rec['entry']:.2f}" if rec.get("entry") else f"  💰 Entry: MARKET PRICE")
                print(f"  🛑 Stop Loss: ${rec['stop']:.2f}" if rec.get("stop") else f"  🛑 Stop Loss: SET YOUR OWN")
                print(f"  🎯 Take Profit: ${rec['target']:.2f}" if rec.get("target") else f"  🎯 Take Profit: SET YOUR OWN")
                if risk > 0 and reward > 0:
                    print(f"  ⚖️  Risk/Reward: {risk:.1f}% / {reward:.1f}% (RR: 1:{reward/risk:.1f})")
                if rec.get("evidence"):
                    print(f"  📝 Why: {rec['evidence'][0]}")
                
                # UpsideOnly entry template
                print(f"\n  📋 UPSIDEONLY ENTRY:")
                print(f"     Direction: {'LONG' if rec['direction'] == 'LONG' else 'SHORT'}")
                print(f"     Entry: ${rec['entry']:.2f}" if rec.get("entry") else f"     Entry: MARKET")
                print(f"     Stop: ${rec['stop']:.2f}" if rec.get("stop") else f"     Stop: ___")
                print(f"     Target: ${rec['target']:.2f}" if rec.get("target") else f"     Target: ___")
            
            # Summary table
            print(f"\n{'─' * 70}")
            print("\n📊 QUICK REFERENCE TABLE:")
            print("-" * 70)
            table_data = []
            for rec in filtered_signals[:10]:
                direction = "🟢 LONG" if rec["direction"] == "LONG" else "🔴 SHORT"
                entry_str = f"${rec['entry']:.2f}" if rec.get("entry") else "Market"
                stop_str = f"${rec['stop']:.2f}" if rec.get("stop") else "---"
                target_str = f"${rec['target']:.2f}" if rec.get("target") else "---"
                table_data.append([
                    rec["symbol"],
                    direction,
                    f"{rec['confidence']:.0f}%",
                    entry_str,
                    stop_str,
                    target_str,
                ])
            
            print(tabulate(
                table_data,
                headers=["Symbol", "Direction", "Conf", "Entry", "Stop", "Target"],
                tablefmt="grid"
            ))
        else:
            print("\n⚠️ No signals meet the confidence threshold.")
            print(f"   Current threshold: {CONFIDENCE_THRESHOLD}%")
            print("   To see more signals, lower CONFIDENCE_THRESHOLD in the code")
    else:
        print("\n⚠️ No signals generated.")
        print("   Try lowering CONFIDENCE_THRESHOLD or adding more symbols")
    
    # Stats
    longs = sum(1 for r in all_recommendations if r['direction'] == 'LONG')
    shorts = sum(1 for r in all_recommendations if r['direction'] == 'SHORT')
    
    print("\n" + "=" * 70)
    print("📈 MARKET OVERVIEW")
    print("=" * 70)
    print(f"  Total Signals Found: {len(all_recommendations)}")
    print(f"  Showing (≥{CONFIDENCE_THRESHOLD}%): {len([r for r in all_recommendations if r['confidence'] >= CONFIDENCE_THRESHOLD])}")
    print(f"  Bullish (LONG): {longs}")
    print(f"  Bearish (SHORT): {shorts}")
    print(f"  Avg Confidence: {sum(r['confidence'] for r in all_recommendations)/len(all_recommendations):.0f}%" if all_recommendations else "  N/A")
    
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

📌 TO GET UPDATES: Run 'python examples/trading_advisor.py' daily or
   set up a cron job/scheduled task on your computer
    """)


if __name__ == "__main__":
    asyncio.run(main())
