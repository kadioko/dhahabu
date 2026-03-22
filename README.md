# Dhahabu — XAUUSD Trading Intelligence Platform

Production-grade, AI-assisted algorithmic trading platform for XAUUSD.

## Architecture

```
dhahabu/
├── backend/
│   ├── api/                     # FastAPI routes + Pydantic schemas
│   ├── core/                    # Config, logging, constants
│   ├── db/                      # SQLAlchemy models + async engine
│   ├── scheduler/               # APScheduler job orchestration
│   ├── services/
│   │   ├── market_data/         # Twelve Data ingestion
│   │   ├── volatility_regime/   # ATR-based regime detection
│   │   ├── position_sizing/     # Risk-adjusted lot sizing
│   │   ├── risk_guardian/       # Central risk state + trading brain
│   │   ├── trade_lifecycle/     # Candle-driven execution simulation
│   │   ├── pnl/                 # Daily PnL tracking
│   │   ├── backtest/            # Backtesting engine
│   │   ├── self_healing/        # Full validation + optimization cycle
│   │   ├── system_health/       # Component health monitoring
│   │   └── ...                  # 20+ service modules
│   ├── strategies/
│   │   ├── liquidity_sweeps/    # Stop hunt / liquidity grab detection
│   │   ├── trend_continuation/  # Pullback entries with HTF bias
│   │   ├── breakout_expansion/  # Range compression + breakout
│   │   └── ema_momentum/        # Multi-EMA alignment momentum
│   └── telegram/                # Signal + alert delivery
├── frontend/                    # React + TradingView Lightweight Charts
├── alembic/                     # Database migrations
├── tests/                       # Pytest unit tests
└── scripts/                     # Bootstrap utilities
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI + Pydantic |
| Database | PostgreSQL + SQLAlchemy (async) |
| Migrations | Alembic |
| Scheduling | APScheduler |
| Market Data | Twelve Data API |
| Notifications | Telegram Bot API |
| Charts | TradingView Lightweight Charts |
| Frontend | React + TypeScript + Recharts |
| Deploy | Railway + Docker |

## Core Features

### Trading Brain (every 30 min)
- Ingests M15/H1/H4/D1 candles
- Computes volatility + market regime
- Runs all 4 strategies
- Scores signals with composite metric (confidence × live performance × regime fit × R:R)
- Applies risk guards: daily loss cap, shutdown check, exposure limits, dedup
- Adjusts position sizing by volatility regime
- Persists every decision with full audit trail
- Sends approved signals to Telegram

### Self-Healing Engine (every 4-6h)

**Backtest Loop:**
```
every 4h → Re-Backtest (7d/14d/30d/60d) → Walk-Forward (80/20) → Overfit?
  YES → Flag Overfitted + suppress live signals
  NO  → Continue
```

**Optimize Loop:**
```
every 6h → Parameter Search (80 combos/strategy) → Monte Carlo (1000 sims) → Random wins?
  YES → Throw Away
  NO  → Promote Live (demote old)
```

**Circuit Breaker:**
```
always on → track consecutive SL hits → ≥8 in a row?
  YES → 24h shutdown + Telegram alert
```

### Risk Management
- Max daily loss: 3% (configurable)
- Volatility-adjusted position sizing
- Max simultaneous trades cap
- Duplicate directional exposure blocking
- Walk-forward overfit suppression
- Monte Carlo robustness gate

## Quick Start

```bash
# 1. Copy and configure environment
cp .env.example .env
# Edit .env with your API keys

# 2. Start PostgreSQL
docker run -d -p 5432:5432 -e POSTGRES_DB=dhahabu -e POSTGRES_PASSWORD=password postgres:16

# 3. Install dependencies
pip install -e ".[dev]"

# 4. Run migrations
alembic upgrade head

# 5. Seed default strategy parameters
python scripts/init_live_params.py

# 6. Start the platform
uvicorn backend.main:app --reload --port 8000

# 7. Start the frontend (dev)
cd frontend && npm install && npm run dev
```

## Railway Deployment

1. Connect the GitHub repo to Railway
2. Add a PostgreSQL plugin in Railway
3. Set environment variables from `.env.example`
4. Railway auto-deploys via `Dockerfile`
5. The `CMD` runs `alembic upgrade head` then starts uvicorn

## API Reference

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Liveness probe |
| `GET /dashboard/summary` | Dashboard aggregated KPIs |
| `GET /signals/active` | Approved signals (last 4h) |
| `GET /signals` | Signal history with filters |
| `GET /trades/open` | Open trades |
| `GET /trades/history` | Closed trade history |
| `GET /risk/state` | Current risk state |
| `GET /risk/events` | Risk event log |
| `GET /risk/shutdown` | Shutdown events |
| `GET /pnl/daily` | Daily PnL snapshots |
| `GET /pnl/today` | Today's PnL |
| `GET /strategies/rankings` | Live strategy leaderboard |
| `GET /validation/backtests` | Backtest run history |
| `GET /validation/walk-forward` | Walk-forward results |
| `GET /validation/monte-carlo` | Monte Carlo results |
| `GET /validation/overfit-flags` | Currently flagged strategies |
| `GET /validation/promotions` | Live promotion history |
| `GET /scheduler/jobs/latest` | Latest scheduler job status |
| `GET /system/state` | Component health |

## Tests

```bash
pytest tests/ -v --tb=short
```

## Environment Variables

See `.env.example` for all configuration options.

Key variables:
- `DATABASE_URL` — async PostgreSQL URL
- `TWELVE_DATA_API_KEY` — market data
- `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` — signal delivery
- `ACCOUNT_BALANCE` — for position sizing
- `MAX_DAILY_LOSS_PCT` — circuit breaker threshold (default: 0.03)
- `CONSECUTIVE_STOP_LOSSES_LIMIT` — shutdown trigger (default: 8)

---

Built with Claude Code · Dhahabu (Swahili for "gold")
