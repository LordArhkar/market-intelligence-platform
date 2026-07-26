#!/usr/bin/env python3
"""
Simple backtest demo - demonstrates trading with actual signals.
"""

import asyncio
from datetime import datetime, timedelta

from mip.data.connectors import YahooFinanceConnector
from mip.data.connectors.base import MarketDataRequest
from mip.execution import PaperTradingSimulator


async def simple_momentum_strategy(data, symbol, lookback=20):
    """Simple momentum strategy - buy when price crosses above SMA."""
    signals = []
    
    closes = data["close"].to_list()
    timestamps = data["timestamp"].to_list()
    
    for i in range(lookback, len(closes) - 1):
        current_price = closes[i]
        sma = sum(closes[i - lookback:i]) / lookback
        prev_sma = sum(closes[i - lookback - 1:i - 1]) / lookback
        
        if prev_sma is None or sma is None:
            continue
        
        # Golden cross - price crosses above SMA
        if prev_sma <= sma * 0.99 and current_price > sma:
            signals.append({
                "bar": i,
                "timestamp": timestamps[i],
                "price": current_price,
                "direction": "LONG",
                "stop": current_price * 0.97,
            })
        # Death cross - price crosses below SMA
        elif prev_sma >= sma * 1.01 and current_price < sma:
            signals.append({
                "bar": i,
                "timestamp": timestamps[i],
                "price": current_price,
                "direction": "SHORT",
                "stop": current_price * 1.03,
            })
    
    return signals


async def run_backtest():
    """Run a simple backtest demo."""
    
    print("=" * 60)
    print("BACKTEST DEMO - Simple Momentum Strategy")
    print("=" * 60)
    
    # Get data
    connector = YahooFinanceConnector()
    await connector.connect()
    
    request = MarketDataRequest(
        symbol="AAPL",
        start_date=datetime.utcnow() - timedelta(days=365),
        end_date=datetime.utcnow(),
        timeframe="1d",
    )
    
    data = await connector.get_price_bars(request)
    await connector.disconnect()
    
    print(f"\nData: {len(data)} bars")
    print(f"Period: {data['timestamp'].min().date()} to {data['timestamp'].max().date()}")
    
    # Generate signals
    signals = await simple_momentum_strategy(data, "AAPL")
    print(f"\nSignals generated: {len(signals)}")
    
    # Run simulation
    simulator = PaperTradingSimulator()
    print(f"\nInitial Capital: ${simulator.initial_capital:,.2f}")
    
    # Execute signals directly
    for signal in signals[:10]:  # Limit to 10 for demo
        # Create a position directly in the simulator
        price = signal['price']
        direction = signal['direction']
        
        # Calculate position size
        risk_amount = simulator.cash * 0.01  # 1% risk
        stop_distance = price * 0.03  # 3% stop
        shares = int(risk_amount / stop_distance)
        
        if shares > 0:
            # Simulate entry
            cost = shares * price
            if cost <= simulator.cash:
                # Create position
                from mip.core.models.position import Position, PositionSide, PositionStatus
                position = Position(
                    symbol='AAPL',
                    asset_class='US_EQUITY',
                    side=PositionSide.LONG if direction == 'LONG' else PositionSide.SHORT,
                    quantity=shares,
                    average_entry_price=price,
                    current_price=price,
                    stop_loss=signal['stop'],
                    strategy_name='simple_momentum',
                )
                simulator.positions['AAPL'] = position
                simulator.cash -= cost
                print(f"  Entry: {direction} {shares} shares at ${price:.2f}")
                
                # Simulate exit at next bar (if available)
                if signal['bar'] + 1 < len(data):
                    exit_price = data["close"][signal['bar'] + 1]
                    if position.check_stop_loss(exit_price):
                        success, msg = simulator.close_position('AAPL', exit_price, "STOP_LOSS")
                        print(f"    Exit (stop): ${exit_price:.2f} - {msg}")
                    else:
                        success, msg = simulator.close_position('AAPL', exit_price, "TIME_EXIT")
                        print(f"    Exit: ${exit_price:.2f} - {msg}")
    
    # Update positions
    prices = {"AAPL": data["close"][-1]}
    simulator.update_prices(prices)
    
    # Summary
    summary = simulator.get_summary()
    
    print(f"\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Final Equity:     ${summary['current_equity']:,.2f}")
    print(f"Open Positions:   {summary['open_positions']}")
    print(f"Total Trades:      {summary['total_trades']}")
    print(f"Winning Trades:    {summary['winning_trades']}")
    print(f"Losing Trades:    {summary['losing_trades']}")
    print(f"Win Rate:         {summary['win_rate']:.1%}")
    print(f"Max Drawdown:      {summary['max_drawdown']:.2f}%")
    print(f"Total Commission:  ${summary['total_commission']:.2f}")
    print(f"Total Slippage:    ${summary['total_slippage']:.2f}")
    
    # Calculate return
    total_return = (summary['current_equity'] - summary['initial_capital']) / summary['initial_capital'] * 100
    print(f"\nTotal Return:      {total_return:+.2f}%")
    
    print("\n" + "=" * 60)
    print("IMPORTANT NOTES")
    print("=" * 60)
    print("""
1. This is a simple demonstration with basic signals
2. Real trading requires rigorous validation
3. Past performance does not guarantee future results
4. Transaction costs are modeled but may not reflect reality
5. No strategy has been validated as having a statistical edge
    """)


if __name__ == "__main__":
    asyncio.run(run_backtest())
