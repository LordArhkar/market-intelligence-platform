#!/usr/bin/env python3
"""
Basic usage example for the Market Intelligence Platform.

This script demonstrates the core functionality:
1. Getting market data
2. Generating signals with strategies
3. Running paper trading simulation
4. Exporting signals for UpsideOnly
"""

import asyncio
from datetime import datetime, timedelta

from mip.core.config import get_settings
from mip.data.connectors import YahooFinanceConnector
from mip.strategies.implementations import (
    MomentumStrategy,
    MeanReversionStrategy,
    TrendFollowingStrategy,
)
from mip.risk import RiskManager, RiskLimits
from mip.execution import PaperTradingSimulator, CSVHandler
from mip.core.models.signal import SignalDirection


async def main():
    """Run basic example."""
    print("=" * 60)
    print("Market Intelligence Platform - Basic Example")
    print("=" * 60)
    
    # 1. Configuration
    print("\n1. Configuration")
    settings = get_settings()
    print(f"   App: {settings.app_name}")
    print(f"   Mode: {settings.operating_mode}")
    print(f"   Initial Capital: ${settings.execution.initial_capital:,.2f}")
    
    # 2. Data Retrieval
    print("\n2. Market Data")
    connector = YahooFinanceConnector()
    await connector.connect()
    
    # Get AAPL data
    from mip.data.connectors.base import MarketDataRequest
    
    request = MarketDataRequest(
        symbol="AAPL",
        start_date=datetime.utcnow() - timedelta(days=365),
        end_date=datetime.utcnow(),
        timeframe="1d",
    )
    
    df = await connector.get_price_bars(request)
    print(f"   Retrieved {len(df)} price bars for AAPL")
    
    if not df.is_empty():
        print(f"   Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    
    await connector.disconnect()
    
    # 3. Strategy Signals
    print("\n3. Strategy Signals")
    
    context = {
        "symbol": "AAPL",
        "asset_class": "US_EQUITY",
        "timeframe": "1d",
        "regime": "TREND",
    }
    
    # Momentum Strategy
    momentum = MomentumStrategy(
        lookback_period=20,
        rsi_oversold=30,
        rsi_overbought=70,
        min_momentum=0.02,
    )
    momentum_result = await momentum.generate_signals(df, context)
    print(f"   Momentum: {len(momentum_result.signals)} signals generated")
    
    # Mean Reversion Strategy
    mean_rev = MeanReversionStrategy(
        bb_period=20,
        bb_std=2.0,
    )
    mean_rev_result = await mean_rev.generate_signals(df, context)
    print(f"   Mean Reversion: {len(mean_rev_result.signals)} signals generated")
    
    # Trend Following Strategy
    trend = TrendFollowingStrategy(
        fast_ma=10,
        slow_ma=50,
        trend_ma=200,
        adx_threshold=25,
    )
    trend_result = await trend.generate_signals(df, context)
    print(f"   Trend Following: {len(trend_result.signals)} signals generated")
    
    # 4. Risk Management
    print("\n4. Risk Management")
    risk_manager = RiskManager(RiskLimits())
    
    all_signals = (
        momentum_result.signals +
        mean_rev_result.signals +
        trend_result.signals
    )
    
    approved_signals = []
    for signal in all_signals:
        if signal.direction != SignalDirection.NEUTRAL:
            # Use current price for simulation
            current_price = df.tail(1)["close"][0]
            result = risk_manager.check_signal(signal, current_price)
            
            if result.approved:
                approved_signals.append(signal)
                print(f"   OK {signal.strategy_name}: {signal.direction.value} {signal.symbol}")
            else:
                print(f"   REJECTED {signal.strategy_name}: {result.reason}")
    
    # 5. Paper Trading Simulation
    print("\n5. Paper Trading Simulation")
    simulator = PaperTradingSimulator()
    
    print(f"   Initial Capital: ${simulator.initial_capital:,.2f}")
    
    # Execute approved signals
    for signal in approved_signals[:2]:  # Limit to 2 for demo
        current_price = df.tail(1)["close"][0]
        success, message = simulator.execute_signal(signal, current_price)
        print(f"   {message}")
    
    # Update positions with latest prices
    positions = {}
    for pos in simulator.positions.values():
        positions[pos.symbol] = df.tail(1)["close"][0]
    
    simulator.update_prices(positions)
    
    summary = simulator.get_summary()
    print(f"\n   Current Equity: ${summary['current_equity']:,.2f}")
    print(f"   Open Positions: {summary['open_positions']}")
    print(f"   Total Trades: {summary['total_trades']}")
    print(f"   Win Rate: {summary['win_rate']:.1%}")
    
    # 6. CSV Export
    print("\n6. CSV Export")
    csv_handler = CSVHandler()
    
    # Export signals for UpsideOnly
    filepath = csv_handler.export_signals(approved_signals)
    print(f"   Signals exported to: {filepath}")
    
    # Export trade sheet with position sizing
    trade_sheet = csv_handler.export_trade_sheet(
        approved_signals,
        simulator.get_summary()["current_equity"]
    )
    print(f"   Trade sheet exported to: {trade_sheet}")
    
    print("\n" + "=" * 60)
    print("Example completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
