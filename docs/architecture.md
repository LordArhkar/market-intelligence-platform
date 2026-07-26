# Market Intelligence and Paper Trading Platform - Architecture

## System Overview

A modular, production-grade platform for analyzing financial market data and generating rigorously validated paper-trading signals. The system operates independently of UpsideOnly for signal generation, with manual CSV-based synchronization for trade execution.

---

## Architecture Principles

1. **Modularity** - Each component has a single, well-defined responsibility
2. **Testability** - All trading logic is deterministic and testable
3. **Auditability** - Every decision is logged with timestamps and evidence
4. **Security** - Secrets management, no credential embedding, encrypted storage
5. **Resilience** - Graceful degradation, data validation, failure handling

---

## Core Modules

### 1. Data Layer

```
┌─────────────────────────────────────────────────────────────────┐
│                     Market Data Ingestion                        │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌────────┐ │
│  │US Equities│ │Forex    │  │Crypto   │  │Canadian │  │Options │ │
│  │Connector │  │Connector│  │Connector│  │Connector│  │Connector│ │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘  └───┬────┘ │
│       │             │            │             │            │       │
│       └─────────────┴─────────────┴─────────────┴────────────┘     │
│                              │                                     │
│                    ┌─────────▼─────────┐                           │
│                    │ Data Abstraction │                           │
│                    │     Layer        │                           │
│                    └─────────┬─────────┘                           │
└──────────────────────────────┼──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Historical Data Storage                        │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ Price/Candle │  │ Corporate    │  │ Order Book / Level 2 │  │
│  │ Database     │  │ Actions      │  │ Data (if available)  │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 2. Feature Computation

```
┌─────────────────────────────────────────────────────────────────┐
│                    Feature Computation                           │
├─────────────────────────────────────────────────────────────────┤
│  Technical    │ Candlestick  │ Market    │ Volume   │ Fundamental│
│  Indicators   │ Patterns     │ Regime    │ Profile  │ Features   │
├───────────────┼──────────────┼───────────┼──────────┼────────────┤
│  SMA/EMA      │ Engulfing    │ Trend     │ VWAP     │ P/E Ratio  │
│  RSI          │ Hammer       │ Range     │ Delta    │ Revenue    │
│  MACD         │ Doji         │ Volatility│ Volume   │ Growth     │
│  Bollinger    │ Morning Star │ Breakout  │ Absorption│ Earnings   │
│  ATR          │ etc.         │ etc.      │ etc.     │ etc.       │
└───────────────┴──────────────┴───────────┴──────────┴────────────┘
```

### 3. Strategy Research

```
┌─────────────────────────────────────────────────────────────────┐
│                    Strategy Research Engine                       │
├─────────────────────────────────────────────────────────────────┤
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────────┐ │
│  │ Strategy       │  │ Backtesting    │  │ Walk-Forward       │ │
│  │ Registry       │  │ Engine         │  │ Validation         │ │
│  └───────┬────────┘  └───────┬────────┘  └─────────┬──────────┘ │
│          │                   │                      │            │
│          └───────────────────┼──────────────────────┘            │
│                              ▼                                    │
│                    ┌────────────────────┐                        │
│                    │ Experiment         │                        │
│                    │ Tracker            │                        │
│                    └────────────────────┘                        │
└─────────────────────────────────────────────────────────────────┘
```

### 4. Signal Generation

```
┌─────────────────────────────────────────────────────────────────┐
│                    Signal Generation Pipeline                     │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────────────────┐│
│  │ Strategy    │   │ Risk        │   │ Signal                  ││
│  │ Ensemble    │──▶│ Manager     │──▶│ Aggregator              ││
│  │ Agent       │   │ Agent       │   │                         ││
│  └─────────────┘   └─────────────┘   └───────────┬─────────────┘│
│                                                   │              │
│                                                   ▼              │
│                    ┌────────────────────────────────────────────┐│
│                    │         Opportunity Cards (10+)            ││
│                    │  ENTER_NOW │ WATCH │ HOLD │ REDUCE │ EXIT  ││
│                    └────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

### 5. Portfolio Management

```
┌─────────────────────────────────────────────────────────────────┐
│                    Portfolio Construction                         │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │ Position    │  │ Portfolio   │  │ Correlation │            │
│  │ Sizing      │  │ Optimizer   │  │ Analyzer    │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │ Exposure    │  │ Sector      │  │ Leverage    │            │
│  │ Monitor     │  │ Limits      │  │ Controller  │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

### 6. Execution Layer (Manual with CSV)

```
┌─────────────────────────────────────────────────────────────────┐
│                    Execution Layer                               │
├─────────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐      ┌──────────────────────────────┐   │
│  │ Internal         │      │ UpsideOnly                   │   │
│  │ Paper Trading    │◀────▶│ Manual Entry                 │   │
│  │ Simulator        │ CSV  │ (Human Operator)             │   │
│  └────────┬─────────┘ Import/  └──────────────────────────────┘   │
│           │           Export                                    │
│           │                                                   │
│           ▼                                                   │
│  ┌──────────────────┐                                        │
│  │ Execution         │                                        │
│  │ Adapter           │  [DISABLED - API UNAUTHORIZED]        │
│  │ (Stub)            │                                        │
│  └──────────────────┘                                        │
└─────────────────────────────────────────────────────────────────┘
```

### 7. Monitoring and Reporting

```
┌─────────────────────────────────────────────────────────────────┐
│                    Monitoring and Reporting                       │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐│
│  │ Performance │  │ Data Health │  │ Agent Health             ││
│  │ Dashboard   │  │ Monitor     │  │ Monitor                  ││
│  └─────────────┘  └─────────────┘  └─────────────────────────┘│
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐│
│  │ Morning     │  │ Intraday    │  │ End-of-Day               ││
│  │ Report      │  │ Alert       │  │ Report                   ││
│  └─────────────┘  └─────────────┘  └─────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

---

## Agent Architecture

| Agent | Responsibility | Key Inputs | Key Outputs |
|-------|---------------|------------|-------------|
| DataIntegrityAgent | Validate data quality | Raw market data | Validated data, quality reports |
| MarketRegimeAgent | Classify market state | Price, volume, volatility | Regime labels |
| TechnicalStructureAgent | Identify patterns | Price series, indicators | Pattern signals |
| CandlestickPatternAgent | Detect candle patterns | OHLCV data | Pattern detections |
| TrapDetectionAgent | Identify bull/bear traps | Price, volume, order flow | Trap warnings |
| FundamentalEventAgent | Process fundamental data | Earnings, news, filings | Fundamental signals |
| OptionsVolatilityAgent | Analyze options market | Options chains, IV | Volatility signals |
| StrategyResearchAgent | Test hypotheses | Historical data, features | Strategy performance |
| PortfolioConstructionAgent | Build portfolios | Signals, risk limits | Position recommendations |
| RiskManagementAgent | Enforce risk rules | Portfolio state, signals | Risk decisions |
| PaperExecutionAgent | Execute paper trades | Signals, authorization | Execution records |
| TradeReconciliationAgent | Track vs simulate | Execution records, simulated | Reconciliation reports |
| PerformanceAttributionAgent | Attribute P&L | Trade records, market data | Attribution reports |
| MonitoringAgent | System health | All system outputs | Health reports, alerts |
| OwnerReportingAgent | Generate reports | All system outputs | Dashboard, reports |

---

## Data Flow

```
Market Data ──▶ Validation ──▶ Feature Store ──▶ Strategy Engine
                                      │                 │
                                      ▼                 ▼
                              Feature Computation  Signal Generation
                                      │                 │
                                      ▼                 ▼
                              Risk Management ◀── Portfolio Builder
                                      │                 │
                                      ▼                 ▼
                              Signal Cards ◀──────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    │                 │                 │
                    ▼                 ▼                 ▼
              Internal         CSV Export          Execution
            Simulator                              Adapter
                                                          (disabled)
                    │                 │                 │
                    ▼                 ▼                 ▼
              Trade History    UpsideOnly         Future API
                                (manual)
```

---

## Operating Modes

### Validation Mode
- Conservative risk controls
- Scientifically rigorous performance tracking
- All experiments tracked in registry
- Purpose: Determine if repeatable edge exists

### Tournament Mode
- Attempt US$1,000,000 stretch objective
- Clear disclosure of increased risk
- Separate performance tracking
- Never mixed with Validation Mode results

---

## Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Language | Python 3.11+ | Quantitative finance ecosystem |
| Database | PostgreSQL + TimescaleDB | Time-series optimization |
| Cache | Redis | Low-latency feature cache |
| API | FastAPI | Async, OpenAPI documentation |
| Frontend | React + TypeScript | Dashboard, responsive UI |
| Container | Docker + Kubernetes | Reproducibility, scaling |
| Orchestration | Prefect | Workflow automation |
| ML Features | Polars + NumPy | Fast data processing |
| Visualization | Plotly + Dash | Interactive charts |
| Testing | pytest + hypothesis | Property-based testing |
| CI/CD | GitHub Actions | Automated pipelines |

---

## Database Schema (High-Level)

### Core Tables

- `instruments` - Security master
- `price_bars` - OHLCV data (1m, 5m, 15m, 1h, 4h, 1d)
- `corporate_actions` - Splits, dividends, adjustments
- `market_regimes` - Daily regime classifications
- `features` - Computed technical features
- `strategies` - Strategy definitions
- `experiments` - Backtest configurations
- `signals` - Generated trading signals
- `positions` - Current positions
- `trades` - Trade history
- `performance` - Daily P&L attribution
- `audit_log` - All system decisions

---

## Security Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Security Layer                                │
├─────────────────────────────────────────────────────────────────┤
│                                                              │
│  Secrets Management                                           │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │ HashiCorp Vault / AWS Secrets Manager                   │  │
│  │ - API Keys                                             │  │
│  │ - Database credentials                                  │  │
│  │ - No secrets in code, prompts, or logs                 │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                              │
│  Access Control                                              │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │ Role-based access                                       │  │
│  │ - Owner (read/write all)                               │  │
│  │ - System (automated operations)                        │  │
│  │ - Read-only (monitoring)                               │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                              │
│  Audit Trail                                                 │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │ Every decision logged with:                             │  │
│  │ - Timestamp                                            │  │
│  │ - Actor (owner/system/agent)                          │  │
│  │ - Action                                               │  │
│  │ - Evidence                                             │  │
│  │ - Outcome                                              │  │
│  └─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Deployment Architecture

```
                    ┌──────────────────┐
                    │   Load Balancer  │
                    └────────┬─────────┘
                             │
           ┌─────────────────┼─────────────────┐
           │                 │                 │
           ▼                 ▼                 ▼
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │  API Server  │  │  Dashboard   │  │  Background   │
    │  (FastAPI)   │  │  (React)     │  │  Workers     │
    └──────────────┘  └──────────────┘  └──────────────┘
           │                 │                 │
           └─────────────────┼─────────────────┘
                             │
                    ┌────────▼─────────┐
                    │   PostgreSQL +   │
                    │   TimescaleDB    │
                    └─────────────────┘
```

---

*Architecture Version: 1.0*  
*Last Updated: 2026-07-26*
