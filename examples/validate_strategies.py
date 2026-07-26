#!/usr/bin/env python3
"""
Strategy validation script.

This script validates all strategies using:
1. Historical backtesting
2. Walk-forward analysis
3. Out-of-sample testing

Results are saved to the experiment registry.
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
)
from mip.strategies.backtest import BacktestEngine, BacktestConfig
from mip.strategies.registry_experiments import ExperimentRegistry


async def validate_strategies():
    """Validate all strategies on historical data."""
    
    print("=" * 70)
    print("STRATEGY VALIDATION REPORT")
    print(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # Initialize components
    connector = YahooFinanceConnector()
    engine = BacktestEngine()
    registry = ExperimentRegistry()
    
    # Test symbols
    symbols = ["AAPL", "MSFT", "SPY"]
    
    # Test configurations
    test_configs = [
        ("Momentum (Conservative)", MomentumStrategy(lookback_period=20, min_momentum=0.03)),
        ("Momentum (Aggressive)", MomentumStrategy(lookback_period=10, min_momentum=0.02)),
        ("Mean Reversion", MeanReversionStrategy(bb_period=20, bb_std=2.0)),
        ("Trend Following", TrendFollowingStrategy(fast_ma=10, slow_ma=50, adx_threshold=25)),
    ]
    
    results_table = []
    
    for symbol in symbols:
        print(f"\n{'=' * 70}")
        print(f"Testing: {symbol}")
        print("=" * 70)
        
        # Get data
        request = MarketDataRequest(
            symbol=symbol,
            start_date=datetime.utcnow() - timedelta(days=730),  # 2 years
            end_date=datetime.utcnow(),
            timeframe="1d",
        )
        
        await connector.connect()
        data = await connector.get_price_bars(request)
        await connector.disconnect()
        
        if data.is_empty():
            print(f"  No data available for {symbol}")
            continue
        
        print(f"  Data: {len(data)} bars from {data['timestamp'].min().date()} to {data['timestamp'].max().date()}")
        
        # Test each strategy
        for config_name, strategy in test_configs:
            print(f"\n  Testing: {config_name}")
            
            # Backtest configuration
            bt_config = BacktestConfig(
                initial_capital=100_000,
                symbol=symbol,
                slippage_bps=10.0,
                risk_per_trade_percent=1.0,
            )
            engine.config = bt_config
            
            # Run walk-forward analysis
            wf_result = engine.run_walk_forward(strategy, data)
            
            # Register experiment
            registry.register(
                strategy_name=strategy.name,
                experiment_type="walk_forward",
                parameters=strategy.params,
                result=type('Result', (), {
                    'total_return': wf_result.out_of_sample_return,
                    'annualized_return': wf_result.annualized_return,
                    'total_trades': wf_result.total_trades,
                    'win_rate': wf_result.win_rate,
                    'sharpe_ratio': wf_result.sharpe_ratio,
                    'max_drawdown': wf_result.max_drawdown,
                    'profit_factor': wf_result.profit_factor,
                    'expectancy': wf_result.expectancy,
                    'status': wf_result.conclusion,
                })(),
                notes=f"Symbol: {symbol}, {wf_result.conclusion}"
            )
            
            # Display results
            print(f"    OOS Return: {wf_result.out_of_sample_return:+.2f}%")
            print(f"    OOS/IS Ratio: {wf_result.oos_to_is_ratio:.2f}")
            print(f"    Win Rate: {wf_result.win_rate:.1%}")
            print(f"    Sharpe: {wf_result.sharpe_ratio:.2f}")
            print(f"    Significance: {wf_result.confidence_level}")
            print(f"    Conclusion: {wf_result.conclusion}")
            
            results_table.append({
                "Symbol": symbol,
                "Strategy": config_name,
                "OOS Return": f"{wf_result.out_of_sample_return:+.2f}%",
                "Win Rate": f"{wf_result.win_rate:.1%}",
                "Sharpe": f"{wf_result.sharpe_ratio:.2f}",
                "Significance": wf_result.confidence_level,
                "Conclusion": wf_result.conclusion,
            })
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    if results_table:
        print("\n" + tabulate(results_table, headers="keys", tablefmt="grid"))
    
    # Count validated strategies
    validated = sum(1 for r in results_table if r["Conclusion"] == "VALIDATED")
    overfitting = sum(1 for r in results_table if r["Conclusion"] == "POSSIBLE_OVERFITTING")
    not_validated = sum(1 for r in results_table if r["Conclusion"] == "NOT_VALIDATED")
    
    print(f"\nValidated: {validated}")
    print(f"Possible Overfitting: {overfitting}")
    print(f"Not Validated: {not_validated}")
    
    # Recommendations
    print("\n" + "=" * 70)
    print("RECOMMENDATIONS")
    print("=" * 70)
    
    if validated > 0:
        print("\n  Strategies showing positive out-of-sample performance:")
        for r in results_table:
            if r["Conclusion"] == "VALIDATED":
                print(f"  - {r['Strategy']} on {r['Symbol']}")
    else:
        print("\n  No strategies have demonstrated robust out-of-sample performance.")
        print("  This is expected for initial testing.")
        print("  Continue iterating on strategy parameters and hypothesis testing.")
    
    print("\n" + "=" * 70)
    print("DISCLAIMER")
    print("=" * 70)
    print("""
  Past performance does not guarantee future results.
  Backtested results may be subject to overfitting.
  Always validate with out-of-sample testing before live trading.
  The stretch objective of $1,000,000 is NOT guaranteed.
    """)


if __name__ == "__main__":
    asyncio.run(validate_strategies())
