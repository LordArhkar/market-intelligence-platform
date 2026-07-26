# Market Intelligence Platform

An institutional-grade market intelligence and paper-trading platform for analyzing financial market data and generating rigorously validated trading signals.

## Overview

This platform provides:

- **Multi-Asset Coverage**: US equities, Canadian equities, forex, cryptocurrency, and indices
- **Modular Architecture**: Clean separation of concerns across data, strategies, risk, and execution
- **Strategy Validation**: Rigorous backtesting with walk-forward validation and out-of-sample testing
- **Risk Management**: Comprehensive position sizing, drawdown controls, and exposure limits
- **Paper Trading**: Internal simulator with CSV import/export for manual UpsideOnly execution

## Important Disclaimer

**This platform is for research and paper trading only.**

- Initial paper trading capital: US$100,000
- Stretch objective: US$1,000,000 (never guaranteed, probable, or evidence of suitability)
- The primary objective is to identify strategies with repeatable, statistically defensible, positive-expectancy edges
- All strategy results must account for transaction costs, spreads, slippage, execution delay, data quality, and changing market regimes

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Market Data Layer                         │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │
│  │US Equities│ │ Forex  │ │ Crypto  │ │Canadian│           │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘           │
├─────────────────────────────────────────────────────────────┤
│                    Strategy Research                          │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐   │
│  │ Momentum    │ │Mean Rev.   │ │ Trend Following      │   │
│  └─────────────┘ └─────────────┘ └─────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│                    Risk Management                           │
│  Position Limits │ Portfolio Limits │ Correlation Controls   │
├─────────────────────────────────────────────────────────────┤
│                    Execution Layer                             │
│  Internal Simulator │ CSV Export │ Manual UpsideOnly Entry   │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"
```

### Configuration

Copy the environment template and configure:

```bash
cp .env.example .env
# Edit .env with your settings
```

### Running

```bash
# Start the API server
uvicorn mip.api.main:app --reload

# Or run the dashboard
python -m mip.dashboard.app
```

## Key Components

### Data Connectors

- `YahooFinanceConnector`: Free data for US equities, crypto, forex
- `CCXTConnector`: Cryptocurrency exchange data (Binance, Coinbase, etc.)

### Strategies

- `MomentumStrategy`: Cross-sectional momentum based on RSI and price momentum
- `MeanReversionStrategy`: Bollinger Bands mean reversion
- `TrendFollowingStrategy`: Multi-MA trend following with ADX confirmation

### Risk Management

- Position risk limits (default: 2% per trade)
- Portfolio risk limits (default: 6% total)
- Maximum drawdown limits (default: 15%)
- Leverage controls (default: 1x)
- Correlation limits

### Execution

- Internal paper trading simulator
- CSV export for manual UpsideOnly entry
- Trade reconciliation tools

## UpsideOnly Integration

**Status**: Manual execution only

See [docs/upsideonly_assessment.md](docs/upsideonly_assessment.md) for the complete assessment.

Key findings:
- No official API exists
- Programmatic trading is explicitly discouraged
- Platform uses Auth0 + Cloudflare protection
- Manual CSV-based workflow required

## Project Structure

```
mip/
├── core/               # Core models and configuration
│   ├── models/         # Data models (Signal, Position, etc.)
│   └── config/         # Settings management
├── data/               # Data layer
│   └── connectors/     # Data source connectors
├── strategies/         # Trading strategies
│   └── implementations/ # Strategy implementations
├── risk/               # Risk management
├── execution/           # Execution and simulation
├── agents/            # Specialist agents
└── api/                # API endpoints
```

## Development

### Running Tests

```bash
pytest tests/ -v
```

### Code Quality

```bash
# Format
ruff format src/

# Lint
ruff check src/

# Type check
mypy src/
```

## Documentation

- [Architecture](docs/architecture.md)
- [UpsideOnly Assessment](docs/upsideonly_assessment.md)

## License

MIT
