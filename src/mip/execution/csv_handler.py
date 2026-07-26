"""
CSV import/export handler for manual trade execution.

This module provides CSV-based import/export for manual trade execution
when automated API access is not available.
"""

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from mip.core.models.signal import Signal, SignalDirection, SignalStatus, SignalType


@dataclass
class CSVTradeRecord:
    """Standardized trade record for CSV export."""
    
    # Identification
    signal_id: str
    timestamp: str
    
    # Instrument
    symbol: str
    asset_class: str
    
    # Trade details
    action: str  # BUY, SELL, CLOSE
    quantity: float
    price: float
    
    # Risk
    stop_loss: Optional[float]
    take_profit: Optional[float]
    
    # Strategy attribution
    strategy: str
    confidence: float
    
    # Status
    status: str
    notes: str = ""
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "signal_id": self.signal_id,
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "asset_class": self.asset_class,
            "action": self.action,
            "quantity": self.quantity,
            "price": self.price,
            "stop_loss": self.stop_loss or "",
            "take_profit": self.take_profit or "",
            "strategy": self.strategy,
            "confidence": self.confidence,
            "status": self.status,
            "notes": self.notes,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "CSVTradeRecord":
        """Create from dictionary."""
        return cls(
            signal_id=data["signal_id"],
            timestamp=data["timestamp"],
            symbol=data["symbol"],
            asset_class=data.get("asset_class", "US_EQUITY"),
            action=data["action"],
            quantity=float(data["quantity"]),
            price=float(data["price"]),
            stop_loss=float(data["stop_loss"]) if data.get("stop_loss") else None,
            take_profit=float(data["take_profit"]) if data.get("take_profit") else None,
            strategy=data.get("strategy", "unknown"),
            confidence=float(data.get("confidence", 50)),
            status=data.get("status", "PENDING"),
            notes=data.get("notes", ""),
        )


@dataclass
class CSVTradeImport:
    """Imported trade data from UpsideOnly or manual entry."""
    
    symbol: str
    action: str  # BUY or SELL
    quantity: float
    price: float
    timestamp: str
    trade_id: Optional[str] = None
    pnl: Optional[float] = None
    notes: str = ""
    
    @classmethod
    def from_dict(cls, data: dict) -> "CSVTradeImport":
        """Create from dictionary."""
        return cls(
            symbol=data["symbol"],
            action=data["action"].upper(),
            quantity=float(data["quantity"]),
            price=float(data["price"]),
            timestamp=data["timestamp"],
            trade_id=data.get("trade_id", data.get("id")),
            pnl=float(data["pnl"]) if data.get("pnl") else None,
            notes=data.get("notes", ""),
        )


class CSVHandler:
    """
    Handler for CSV import/export operations.
    
    Supports:
    - Export signals for manual entry in UpsideOnly
    - Import executed trades from UpsideOnly
    - Trade reconciliation
    """
    
    EXPORT_COLUMNS = [
        "signal_id",
        "timestamp",
        "symbol",
        "asset_class",
        "action",
        "quantity",
        "price",
        "stop_loss",
        "take_profit",
        "strategy",
        "confidence",
        "status",
        "notes",
    ]
    
    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or Path("./output")
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def export_signals(
        self,
        signals: list[Signal],
        filename: Optional[str] = None
    ) -> Path:
        """
        Export signals to CSV for manual execution.
        
        Creates a CSV file that can be imported into UpsideOnly
        or used as a trade sheet for manual execution.
        """
        if filename is None:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"signals_{timestamp}.csv"
        
        filepath = self.output_dir / filename
        
        records = []
        for signal in signals:
            # Determine action based on direction
            if signal.direction == SignalDirection.LONG:
                action = "BUY"
            elif signal.direction == SignalDirection.SHORT:
                action = "SELL"
            else:
                continue
            
            record = CSVTradeRecord(
                signal_id=signal.id,
                timestamp=signal.created_at.isoformat(),
                symbol=signal.symbol,
                asset_class=signal.asset_class,
                action=action,
                quantity=0,  # To be filled in manually
                price=signal.entry_price or 0,
                stop_loss=signal.stop_loss,
                take_profit=signal.take_profit_1,
                strategy=signal.strategy_name,
                confidence=signal.confidence,
                status=signal.status.value,
                notes=f"Risk: {signal.position_risk_percent}% | R:R: {signal.expected_reward_risk or 'N/A'}",
            )
            records.append(record)
        
        with open(filepath, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.EXPORT_COLUMNS)
            writer.writeheader()
            for record in records:
                writer.writerow(record.to_dict())
        
        return filepath
    
    def export_trade_sheet(
        self,
        signals: list[Signal],
        portfolio_value: float,
        filename: Optional[str] = None
    ) -> Path:
        """
        Export a formatted trade sheet for manual execution.
        
        Includes position sizing calculations and all necessary information.
        """
        if filename is None:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"trade_sheet_{timestamp}.csv"
        
        filepath = self.output_dir / filename
        
        rows = []
        for signal in signals:
            # Calculate position size
            risk_amount = portfolio_value * signal.position_risk_percent / 100
            
            if signal.stop_loss and signal.entry_price:
                if signal.direction == SignalDirection.LONG:
                    risk_per_share = signal.entry_price - signal.stop_loss
                else:
                    risk_per_share = signal.stop_loss - signal.entry_price
                
                if risk_per_share > 0:
                    quantity = risk_amount / risk_per_share
                else:
                    quantity = 0
            else:
                quantity = 0
            
            rows.append({
                "PRIORITY": "HIGH" if signal.confidence > 70 else "MEDIUM" if signal.confidence > 50 else "LOW",
                "SYMBOL": signal.symbol,
                "DIRECTION": signal.direction.value,
                "ACTION": "BUY" if signal.direction == SignalDirection.LONG else "SELL",
                "QUANTITY": f"{quantity:.0f}" if quantity > 0 else "CALCULATE",
                "LIMIT_PRICE": f"{signal.entry_price:.2f}" if signal.entry_price else "MARKET",
                "STOP_LOSS": f"{signal.stop_loss:.2f}" if signal.stop_loss else "NONE",
                "TAKE_PROFIT": f"{signal.take_profit_1:.2f}" if signal.take_profit_1 else "NONE",
                "RISK_AMOUNT": f"${risk_amount:.2f}",
                "RISK_PERCENT": f"{signal.position_risk_percent}%",
                "CONFIDENCE": f"{signal.confidence:.0f}%",
                "STRATEGY": signal.strategy_name,
                "VALID_UNTIL": signal.expires_at.strftime("%Y-%m-%d %H:%M") if signal.expires_at else "EOD",
                "NOTES": f"{'; '.join(signal.supporting_evidence[:2])}",
            })
        
        if rows:
            with open(filepath, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
        
        return filepath
    
    def import_trades(
        self,
        filepath: Path
    ) -> list[CSVTradeImport]:
        """
        Import executed trades from CSV.
        
        This can be used to reconcile UpsideOnly trades with our signals.
        """
        trades = []
        
        with open(filepath, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    trade = CSVTradeImport.from_dict(row)
                    trades.append(trade)
                except Exception as e:
                    # Skip invalid rows
                    print(f"Skipping invalid row: {e}")
                    continue
        
        return trades
    
    def create_reconciliation_report(
        self,
        our_signals: list[Signal],
        their_trades: list[CSVTradeImport]
    ) -> dict:
        """
        Create a reconciliation report comparing our signals with executed trades.
        
        Returns a dictionary with:
        - matched: List of matched signals/trades
        - unmatched_signals: Signals with no corresponding trade
        - unmatched_trades: Trades with no corresponding signal
        """
        matched = []
        unmatched_signals = []
        unmatched_trades = list(their_trades)
        
        # Build lookup for their trades
        trade_by_symbol = {}
        for trade in their_trades:
            if trade.symbol not in trade_by_symbol:
                trade_by_symbol[trade.symbol] = []
            trade_by_symbol[trade.symbol].append(trade)
        
        # Match with our signals
        for signal in our_signals:
            if signal.symbol in trade_by_symbol:
                trades = trade_by_symbol[signal.symbol]
                if trades:
                    matched.append({
                        "signal": signal,
                        "trade": trades[0],
                        "match_type": "symbol",
                    })
                    unmatched_trades.remove(trades[0])
                else:
                    unmatched_signals.append(signal)
            else:
                unmatched_signals.append(signal)
        
        return {
            "total_signals": len(our_signals),
            "total_trades": len(their_trades),
            "matched": len(matched),
            "unmatched_signals": len(unmatched_signals),
            "unmatched_trades": len(unmatched_trades),
            "match_details": matched,
            "unmatched_signal_ids": [s.id for s in unmatched_signals],
            "unmatched_trade_records": [
                {"symbol": t.symbol, "action": t.action, "price": t.price}
                for t in unmatched_trades
            ],
        }
    
    def export_performance_summary(
        self,
        simulator_data: dict,
        filename: Optional[str] = None
    ) -> Path:
        """Export performance summary to CSV."""
        if filename is None:
            timestamp = datetime.utcnow().strftime("%Y%m%d")
            filename = f"performance_{timestamp}.csv"
        
        filepath = self.output_dir / filename
        
        rows = [{
            "date": datetime.utcnow().strftime("%Y-%m-%d"),
            "initial_capital": simulator_data.get("initial_capital", 0),
            "current_equity": simulator_data.get("current_equity", 0),
            "cash": simulator_data.get("cash", 0),
            "open_positions": simulator_data.get("open_positions", 0),
            "total_trades": simulator_data.get("total_trades", 0),
            "winning_trades": simulator_data.get("winning_trades", 0),
            "losing_trades": simulator_data.get("losing_trades", 0),
            "win_rate": f"{simulator_data.get('win_rate', 0):.2%}",
            "total_commission": f"${simulator_data.get('total_commission', 0):.2f}",
            "total_slippage": f"${simulator_data.get('total_slippage', 0):.2f}",
            "max_drawdown": f"{simulator_data.get('max_drawdown', 0):.2f}%",
            "daily_pnl": f"${simulator_data.get('daily_pnl', 0):.2f}",
            "return": f"{((simulator_data.get('current_equity', 0) / simulator_data.get('initial_capital', 1) - 1) * 100):.2f}%",
        }]
        
        with open(filepath, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        
        return filepath
