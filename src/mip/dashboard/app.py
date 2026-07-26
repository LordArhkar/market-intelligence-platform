"""
Dashboard application for the Market Intelligence Platform.

Provides visualization and monitoring for:
- Portfolio performance
- Signal cards
- Trade history
- Strategy attribution
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional

from dash import Dash, html, dcc, callback, Output, Input
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from mip.core.config import get_settings
from mip.data.connectors import YahooFinanceConnector
from mip.data.connectors.base import MarketDataRequest
from mip.strategies.implementations import (
    MomentumStrategy,
    MeanReversionStrategy,
    TrendFollowingStrategy,
)
from mip.execution import PaperTradingSimulator


# Create Dash app
app = Dash(__name__)


def get_market_data(symbol: str, days: int = 365) -> Optional[dict]:
    """Get market data for a symbol."""
    async def fetch():
        connector = YahooFinanceConnector()
        await connector.connect()
        request = MarketDataRequest(
            symbol=symbol,
            start_date=datetime.utcnow() - timedelta(days=days),
            end_date=datetime.utcnow(),
            timeframe="1d",
        )
        data = await connector.get_price_bars(request)
        await connector.disconnect()
        
        if data is None or data.is_empty():
            return None
        
        return {
            "timestamps": data["timestamp"].to_list(),
            "opens": data["open"].to_list(),
            "highs": data["high"].to_list(),
            "lows": data["low"].to_list(),
            "closes": data["close"].to_list(),
            "volumes": data["volume"].to_list(),
        }
    
    return asyncio.run(fetch())


def generate_signals(symbol: str, strategy_name: str) -> list[dict]:
    """Generate signals for a symbol."""
    async def fetch():
        connector = YahooFinanceConnector()
        await connector.connect()
        request = MarketDataRequest(
            symbol=symbol,
            start_date=datetime.utcnow() - timedelta(days=90),
            end_date=datetime.utcnow(),
            timeframe="1d",
        )
        data = await connector.get_price_bars(request)
        await connector.disconnect()
        
        if data is None or data.is_empty():
            return []
        
        context = {
            "symbol": symbol,
            "asset_class": "US_EQUITY",
            "timeframe": "1d",
            "regime": "TREND",
        }
        
        if strategy_name == "momentum":
            strategy = MomentumStrategy()
        elif strategy_name == "mean_reversion":
            strategy = MeanReversionStrategy()
        else:
            strategy = TrendFollowingStrategy()
        
        result = await strategy.generate_signals(data, context)
        return [
            {
                "direction": s.direction.value,
                "price": s.entry_price,
                "confidence": s.confidence,
                "timestamp": str(s.data_timestamp),
                "status": s.status.value,
                "evidence": s.supporting_evidence[:2] if s.supporting_evidence else [],
            }
            for s in result.signals
        ]
    
    return asyncio.run(fetch())


# App layout
app.layout = html.Div([
    html.H1("Market Intelligence Platform", style={"textAlign": "center"}),
    html.Div([
        html.Div([
            html.Label("Symbol:"),
            dcc.Input(id="symbol-input", value="AAPL", type="text"),
        ], style={"display": "inline-block", "marginRight": "20px"}),
        html.Div([
            html.Label("Strategy:"),
            dcc.Dropdown(
                id="strategy-dropdown",
                options=[
                    {"label": "Momentum", "value": "momentum"},
                    {"label": "Mean Reversion", "value": "mean_reversion"},
                    {"label": "Trend Following", "value": "trend_following"},
                ],
                value="momentum",
            ),
        ], style={"display": "inline-block", "width": "200px"}),
        html.Button("Update", id="update-button", n_clicks=0),
    ], style={"textAlign": "center", "marginBottom": "20px"}),
    
    # Portfolio summary
    html.Div([
        html.Div([
            html.H3("Portfolio Summary"),
            html.Div(id="portfolio-summary"),
        ], style={"width": "30%", "display": "inline-block", "verticalAlign": "top"}),
        
        # Chart
        html.Div([
            dcc.Graph(id="price-chart"),
        ], style={"width": "70%", "display": "inline-block"}),
    ]),
    
    # Signals
    html.Div([
        html.H3("Active Signals"),
        html.Div(id="signals-container"),
    ], style={"marginTop": "20px"}),
    
    # Hidden store for data
    dcc.Store(id="market-data-store"),
    dcc.Interval(id="refresh-interval", interval=60000),  # Refresh every minute
], style={"maxWidth": "1200px", "margin": "0 auto", "padding": "20px"})


@callback(
    Output("price-chart", "figure"),
    Output("portfolio-summary", "children"),
    Output("signals-container", "children"),
    Input("update-button", "n_clicks"),
    Input("symbol-input", "value"),
    Input("strategy-dropdown", "value"),
)
def update_dashboard(n_clicks, symbol, strategy):
    """Update dashboard with new data."""
    # Get market data
    data = get_market_data(symbol)
    
    if data is None:
        return go.Figure(), html.P("No data available"), html.P("No signals")
    
    # Create chart
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                       vertical_spacing=0.03, row_heights=[0.7, 0.3],
                       subplot_titles=("Price", "Volume"))
    
    # Candlestick
    fig.add_trace(
        go.Candlestick(
            x=data["timestamps"],
            open=data["opens"],
            high=data["highs"],
            low=data["lows"],
            close=data["closes"],
            name="Price",
        ),
        row=1, col=1
    )
    
    # Volume
    fig.add_trace(
        go.Bar(x=data["timestamps"], y=data["volumes"], name="Volume"),
        row=2, col=1
    )
    
    fig.update_layout(
        title=f"{symbol} - {strategy.title()} Strategy",
        xaxis_rangeslider_visible=False,
        height=500,
    )
    
    # Portfolio summary (simulated)
    summary = html.Div([
        html.P(f"Symbol: {symbol}"),
        html.P(f"Current Price: ${data['closes'][-1]:.2f}"),
        html.P(f"Change: {((data['closes'][-1]/data['closes'][0])-1)*100:+.2f}%"),
        html.P(f"High: ${max(data['highs']):.2f}"),
        html.P(f"Low: ${min(data['lows']):.2f}"),
        html.P(f"Volume: {data['volumes'][-1]:,.0f}"),
    ])
    
    # Generate and display signals
    signals = generate_signals(symbol, strategy)
    
    if signals:
        signal_cards = []
        for sig in signals[:5]:  # Show top 5
            direction_color = "green" if sig["direction"] == "LONG" else "red"
            card = html.Div([
                html.Div(f"{sig['direction']} @ ${sig['price']:.2f}", 
                        style={"color": direction_color, "fontWeight": "bold"}),
                html.Div(f"Confidence: {sig['confidence']:.0f}%"),
                html.Div(f"Time: {sig['timestamp'][:10]}"),
            ], style={
                "border": "1px solid #ccc",
                "borderRadius": "5px",
                "padding": "10px",
                "margin": "5px",
                "display": "inline-block",
                "width": "150px",
            })
            signal_cards.append(card)
    else:
        signal_cards = [html.P("No signals generated")]
    
    return fig, summary, signal_cards


if __name__ == "__main__":
    print("Starting Dashboard...")
    print("Open http://127.0.0.1:8050 in your browser")
    app.run(debug=False, host="127.0.0.1", port=8050)
