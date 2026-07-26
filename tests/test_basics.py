"""
Basic tests for the Market Intelligence Platform.

These tests verify core functionality without external dependencies.
"""

import pytest
from datetime import datetime

from mip.core.models.instrument import Instrument, AssetClass, Exchange
from mip.core.models.price_bar import PriceBar, TimeFrame
from mip.core.models.signal import Signal, SignalDirection, SignalStatus, SignalType
from mip.core.models.position import Position, PositionSide, Trade
from mip.risk.config import RiskLimits


class TestInstrument:
    """Tests for Instrument model."""
    
    def test_create_instrument(self):
        """Test creating an instrument."""
        instrument = Instrument(
            symbol="AAPL",
            name="Apple Inc.",
            asset_class=AssetClass.US_EQUITY,
            exchange=Exchange.NASDAQ,
        )
        
        assert instrument.symbol == "AAPL"
        assert instrument.asset_class == AssetClass.US_EQUITY
        assert instrument.is_active is True
    
    def test_is_options(self):
        """Test options detection."""
        stock = Instrument(
            symbol="AAPL",
            name="Apple Inc.",
            asset_class=AssetClass.US_EQUITY,
            exchange=Exchange.NASDAQ,
        )
        
        assert stock.is_options() is False
    
    def test_get_symbol_for_provider(self):
        """Test getting symbol for different providers."""
        instrument = Instrument(
            symbol="BTC-USD",
            name="Bitcoin",
            asset_class=AssetClass.CRYPTO,
            exchange=Exchange.BINANCE,
            aliases={"yfinance": "BTC-USD", "ccxt": "BTC/USDT"},
        )
        
        assert instrument.get_symbol_for_provider("yfinance") == "BTC-USD"
        assert instrument.get_symbol_for_provider("ccxt") == "BTC/USDT"
        assert instrument.get_symbol_for_provider("unknown") == "BTC-USD"


class TestPriceBar:
    """Tests for PriceBar model."""
    
    def test_bullish_bar(self):
        """Test bullish bar identification."""
        bar = PriceBar(
            symbol="AAPL",
            timeframe=TimeFrame.DAY_1,
            timestamp=datetime(2024, 1, 15),
            open=100.0,
            high=105.0,
            low=99.0,
            close=104.0,
            volume=1000000,
        )
        
        assert bar.is_bullish is True
        assert bar.is_bearish is False
        assert bar.change_percent == 4.0
    
    def test_bearish_bar(self):
        """Test bearish bar identification."""
        bar = PriceBar(
            symbol="AAPL",
            timeframe=TimeFrame.DAY_1,
            timestamp=datetime(2024, 1, 15),
            open=105.0,
            high=106.0,
            low=98.0,
            close=100.0,
            volume=1000000,
        )
        
        assert bar.is_bearish is True
        assert bar.is_bullish is False
        assert bar.change_percent == pytest.approx(-4.76, 0.1)
    
    def test_doji_identification(self):
        """Test doji identification."""
        bar = PriceBar(
            symbol="AAPL",
            timeframe=TimeFrame.DAY_1,
            timestamp=datetime(2024, 1, 15),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.01,
            volume=500000,
        )
        
        assert bar.is_doji is True


class TestSignal:
    """Tests for Signal model."""
    
    def test_create_signal(self):
        """Test creating a trading signal."""
        signal = Signal(
            symbol="AAPL",
            asset_class="US_EQUITY",
            direction=SignalDirection.LONG,
            strategy_name="momentum",
            strategy_version="1.0",
            market_regime="TREND",
            timeframe="1d",
            entry_type=SignalType.ENTER_NOW,
            entry_price=150.0,
            stop_loss=145.0,
            take_profit_1=160.0,
            position_risk_percent=1.0,
            confidence=75.0,
            data_timestamp=datetime.utcnow(),
            supporting_evidence=["RSI oversold", "Volume spike"],
            contradicting_evidence=["Weak trend"],
        )
        
        assert signal.symbol == "AAPL"
        assert signal.direction == SignalDirection.LONG
        assert signal.confidence == 75.0
        assert signal.is_buy is True
        assert signal.is_sell is False
    
    def test_signal_invalidation(self):
        """Test signal invalidation."""
        signal = Signal(
            symbol="AAPL",
            asset_class="US_EQUITY",
            direction=SignalDirection.LONG,
            strategy_name="momentum",
            timeframe="1d",
            entry_type=SignalType.ENTER_NOW,
            entry_price=150.0,
            confidence=50.0,
            data_timestamp=datetime.utcnow(),
        )
        
        signal.invalidate("Price moved against thesis")
        
        assert signal.status == SignalStatus.INVALIDATED
        assert signal.invalidation_reason == "Price moved against thesis"


class TestPosition:
    """Tests for Position model."""
    
    def test_long_position_pnl(self):
        """Test long position P&L calculation."""
        position = Position(
            symbol="AAPL",
            asset_class="US_EQUITY",
            side=PositionSide.LONG,
            quantity=100,
            average_entry_price=150.0,
            current_price=155.0,
            strategy_name="momentum",
        )
        position.update_price(155.0)  # Calculate PnL
        
        assert position.is_long is True
        assert position.unrealized_pnl == 500.0
        assert position.unrealized_pnl_percent == pytest.approx(3.33, 0.1)
    
    def test_short_position_pnl(self):
        """Test short position P&L calculation."""
        position = Position(
            symbol="AAPL",
            asset_class="US_EQUITY",
            side=PositionSide.SHORT,
            quantity=100,
            average_entry_price=150.0,
            current_price=145.0,
            strategy_name="momentum",
        )
        position.update_price(145.0)  # Calculate PnL
        
        assert position.is_long is False
        assert position.unrealized_pnl == 500.0
    
    def test_stop_loss_check(self):
        """Test stop loss hit detection."""
        position = Position(
            symbol="AAPL",
            asset_class="US_EQUITY",
            side=PositionSide.LONG,
            quantity=100,
            average_entry_price=150.0,
            current_price=152.0,
            stop_loss=148.0,
            strategy_name="momentum",
        )
        
        # Not hit yet
        assert position.check_stop_loss(150.0) is False
        
        # Stop hit
        assert position.check_stop_loss(147.0) is True
    
    def test_take_profit_check(self):
        """Test take profit hit detection."""
        position = Position(
            symbol="AAPL",
            asset_class="US_EQUITY",
            side=PositionSide.LONG,
            quantity=100,
            average_entry_price=150.0,
            current_price=152.0,
            take_profit=160.0,
            strategy_name="momentum",
        )
        
        # Not hit yet
        assert position.check_take_profit(158.0) is False
        
        # Take profit hit
        assert position.check_take_profit(161.0) is True


class TestRiskLimits:
    """Tests for risk limits validation."""
    
    def test_valid_limits(self):
        """Test valid risk limits."""
        limits = RiskLimits()
        errors = limits.validate()
        
        assert len(errors) == 0
    
    def test_invalid_position_risk(self):
        """Test detection of invalid position risk."""
        limits = RiskLimits(max_position_risk_percent=15.0)
        errors = limits.validate()
        
        assert len(errors) > 0
        assert any("max_position_risk_percent too high" in e for e in errors)
    
    def test_leverage_validation(self):
        """Test leverage limit validation."""
        limits = RiskLimits(max_leverage=0.5)
        errors = limits.validate()
        
        assert len(errors) > 0


class TestTrade:
    """Tests for Trade model."""
    
    def test_trade_cost_calculation(self):
        """Test total trade cost calculation."""
        trade = Trade(
            position_id="test-pos",
            symbol="AAPL",
            side=PositionSide.LONG,
            quantity=100,
            price=150.0,
            commission=1.0,
            slippage=0.5,
        )
        
        assert trade.notional_value == 15000.0
        # Long trade: price * quantity + fees
        assert trade.total_cost == pytest.approx(15001.5, 0.1)
    
    def test_short_trade_cost(self):
        """Test short trade cost calculation."""
        trade = Trade(
            position_id="test-pos",
            symbol="AAPL",
            side=PositionSide.SHORT,
            quantity=100,
            price=150.0,
            commission=1.0,
            slippage=0.5,
        )
        
        # Short trade: -(price * quantity) + fees
        assert trade.total_cost == pytest.approx(-14998.5, 0.1)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
