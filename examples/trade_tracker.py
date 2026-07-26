"""
Trade Tracker - Track and validate your paper trades

This script helps you:
1. Log your trades from the trading advisor
2. Track entry/exit prices
3. Calculate P&L
4. Generate performance statistics

Usage:
    python examples/trade_tracker.py --log AAPL,LONG,333.02,321.25,356.57
    python examples/trade_tracker.py --view
    python examples/trade_tracker.py --stats
"""

import csv
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

TRADE_FILE = Path(__file__).parent.parent / "data" / "trades.csv"


def init_tracker():
    """Initialize the trade tracker file."""
    TRADE_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    if not TRADE_FILE.exists():
        with open(TRADE_FILE, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'id', 'symbol', 'direction', 'signal_date', 'entry_price',
                'stop_loss', 'take_profit', 'exit_price', 'exit_date',
                'status', 'pnl_pct', 'pnl_amount', 'confidence',
                'strategy', 'timeframe', 'notes'
            ])
        print(f"✅ Trade tracker initialized at {TRADE_FILE}")


def log_trade(
    symbol: str,
    direction: str,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    confidence: int = 0,
    strategy: str = "Advisor",
    timeframe: str = "1d"
) -> int:
    """Log a new trade."""
    init_tracker()
    
    with open(TRADE_FILE, 'r') as f:
        reader = csv.reader(f)
        rows = list(reader)
        trade_id = len(rows)  # Next ID
    
    with open(TRADE_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            trade_id,
            symbol.upper(),
            direction.upper(),
            datetime.now().strftime('%Y-%m-%d'),
            entry_price,
            stop_loss,
            take_profit,
            '',  # exit_price (empty until closed)
            '',  # exit_date
            'OPEN',  # status
            '',  # pnl_pct
            '',  # pnl_amount
            confidence,
            strategy,
            timeframe,
            ''  # notes
        ])
    
    print(f"✅ Trade logged: {symbol} {direction} @ ${entry_price}")
    print(f"   Stop: ${stop_loss} | Target: ${take_profit}")
    return trade_id


def close_trade(trade_id: int, exit_price: float, notes: str = ""):
    """Close an open trade."""
    init_tracker()
    
    rows = []
    with open(TRADE_FILE, 'r') as f:
        reader = csv.reader(f)
        rows = list(reader)
    
    header = rows[0]
    found = False
    
    for i, row in enumerate(rows[1:], 1):
        if row[0] == str(trade_id):
            if row[9] != 'OPEN':
                print(f"⚠️  Trade {trade_id} is already closed")
                return False
            
            found = True
            entry = float(row[4])
            direction = row[2]
            
            # Calculate P&L
            if direction == 'LONG':
                pnl_pct = ((exit_price - entry) / entry) * 100
            else:  # SHORT
                pnl_pct = ((entry - exit_price) / entry) * 100
            
            # Determine status
            stop_loss = float(row[5])
            take_profit = float(row[6])
            
            if direction == 'LONG':
                if exit_price <= stop_loss:
                    status = 'STOPPED_OUT'
                elif exit_price >= take_profit:
                    status = 'TAKE_PROFIT'
                else:
                    status = 'MANUAL_EXIT'
            else:
                if exit_price >= stop_loss:
                    status = 'STOPPED_OUT'
                elif exit_price <= take_profit:
                    status = 'TAKE_PROFIT'
                else:
                    status = 'MANUAL_EXIT'
            
            row[6] = exit_price  # exit_price
            row[8] = datetime.now().strftime('%Y-%m-%d')  # exit_date
            row[9] = status
            row[10] = f"{pnl_pct:.2f}"
            row[11] = pnl_pct  # Simplified
            if notes:
                row[14] = notes
            
            print(f"✅ Trade {trade_id} closed: {status}")
            print(f"   Entry: ${entry} → Exit: ${exit_price}")
            print(f"   P&L: {pnl_pct:+.2f}%")
            break
    
    if found:
        with open(TRADE_FILE, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(rows)
        return True
    else:
        print(f"⚠️  Trade {trade_id} not found")
        return False


def view_trades(status: str = "ALL") -> List[Dict]:
    """View all trades."""
    init_tracker()
    
    trades = []
    with open(TRADE_FILE, 'r') as f:
        reader = csv.DictReader(f)
        trades = list(reader)
    
    if not trades:
        print("\n📋 No trades recorded yet.")
        print("   Use --log to add trades")
        return []
    
    if status != "ALL":
        trades = [t for t in trades if t['status'] == status]
    
    print(f"\n📋 TRADE HISTORY ({status})")
    print("=" * 100)
    print(f"{'ID':<4} {'Symbol':<8} {'Dir':<6} {'Entry':<10} {'Stop':<10} {'Target':<10} {'Exit':<10} {'Status':<15} {'P&L %':<10}")
    print("-" * 100)
    
    for t in trades:
        print(f"{t['id']:<4} {t['symbol']:<8} {t['direction']:<6} "
              f"${float(t['entry_price']):<9.2f} ${float(t['stop_loss']):<9.2f} "
              f"${float(t['take_profit']):<9.2f} {t['exit_price'] or '---':<10} "
              f"{t['status']:<15} {t['pnl_pct'] or '':<10}")
    
    return trades


def calculate_stats() -> Dict:
    """Calculate performance statistics."""
    init_tracker()
    
    trades = []
    with open(TRADE_FILE, 'r') as f:
        reader = csv.DictReader(f)
        trades = [t for t in reader if t['pnl_pct']]  # Only closed trades
    
    if not trades:
        print("\n📊 No closed trades to analyze.")
        print("   Close some trades to see statistics.")
        return {}
    
    pnls = [float(t['pnl_pct']) for t in trades]
    
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    
    stats = {
        'total_trades': len(trades),
        'wins': len(wins),
        'losses': len(losses),
        'win_rate': len(wins) / len(trades) * 100 if trades else 0,
        'avg_win': sum(wins) / len(wins) if wins else 0,
        'avg_loss': sum(losses) / len(losses) if losses else 0,
        'total_pnl': sum(pnls),
        'avg_pnl': sum(pnls) / len(pnls),
        'max_win': max(pnls) if pnls else 0,
        'max_loss': min(pnls) if pnls else 0,
        'profit_factor': abs(sum(wins) / sum(losses)) if losses and sum(losses) != 0 else 0,
    }
    
    print(f"\n📊 PERFORMANCE STATISTICS")
    print("=" * 60)
    print(f"  Total Trades:    {stats['total_trades']}")
    print(f"  Wins:            {stats['wins']}")
    print(f"  Losses:          {stats['losses']}")
    print(f"  Win Rate:        {stats['win_rate']:.1f}%")
    print(f"  Avg Win:         +{stats['avg_win']:.2f}%")
    print(f"  Avg Loss:        {stats['avg_loss']:.2f}%")
    print(f"  Total P&L:       {stats['total_pnl']:+.2f}%")
    print(f"  Avg P&L/Trade:   {stats['avg_pnl']:+.2f}%")
    print(f"  Best Trade:      +{stats['max_win']:.2f}%")
    print(f"  Worst Trade:     {stats['max_loss']:.2f}%")
    print(f"  Profit Factor:   {stats['profit_factor']:.2f}")
    print("=" * 60)
    
    # System validation
    print(f"\n🔍 SYSTEM VALIDATION")
    print("-" * 60)
    
    # Minimum 30 trades for statistical significance
    if stats['total_trades'] < 30:
        print(f"⚠️  Need {30 - stats['total_trades']} more trades for statistical significance")
    
    if stats['win_rate'] < 50:
        print(f"⚠️  Win rate ({stats['win_rate']:.1f}%) is below 50%")
        print("   Strategy may not have an edge")
    else:
        print(f"✅ Win rate ({stats['win_rate']:.1f}%) is positive")
    
    if stats['profit_factor'] < 1.0:
        print(f"⚠️  Profit factor ({stats['profit_factor']:.2f}) is below 1.0")
        print("   Strategy may not be profitable")
    else:
        print(f"✅ Profit factor ({stats['profit_factor']:.2f}) is positive")
    
    if stats['avg_pnl'] > 0:
        print(f"✅ Average trade is PROFITABLE (+{stats['avg_pnl']:.2f}%)")
    else:
        print(f"⚠️  Average trade is UNPROFITABLE ({stats['avg_pnl']:.2f}%)")
    
    return stats


def main():
    parser = argparse.ArgumentParser(description='Trade Tracker')
    parser.add_argument('--log', help='Log trade: SYMBOL,DIRECTION,ENTRY,STOP,TARGET')
    parser.add_argument('--close', help='Close trade: ID,EXIT_PRICE')
    parser.add_argument('--view', action='store_true', help='View all trades')
    parser.add_argument('--stats', action='store_true', help='Show performance stats')
    parser.add_argument('--status', default='ALL', help='Filter by status (OPEN/CLOSED/ALL)')
    
    args = parser.parse_args()
    
    if args.log:
        parts = args.log.split(',')
        if len(parts) < 5:
            print("Usage: --log SYMBOL,DIRECTION,ENTRY,STOP,TARGET")
            return
        log_trade(parts[0], parts[1], float(parts[2]), float(parts[3]), float(parts[4]))
    
    elif args.close:
        parts = args.close.split(',')
        if len(parts) < 2:
            print("Usage: --close ID,EXIT_PRICE")
            return
        notes = parts[2] if len(parts) > 2 else ""
        close_trade(int(parts[0]), float(parts[1]), notes)
    
    elif args.view:
        view_trades(args.status)
    
    elif args.stats:
        calculate_stats()
    
    else:
        parser.print_help()
        print("\n" + "=" * 60)
        print("QUICK START:")
        print("=" * 60)
        print("\n1. Log a trade from the advisor:")
        print("   python examples/trade_tracker.py --log AAPL,LONG,333.02,321.25,356.57")
        print("\n2. View open trades:")
        print("   python examples/trade_tracker.py --view")
        print("\n3. Close a trade:")
        print("   python examples/trade_tracker.py --close 1,350.00")
        print("\n4. View statistics:")
        print("   python examples/trade_tracker.py --stats")


if __name__ == "__main__":
    main()
