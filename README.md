# Dhahabu — XAUUSD Trading Intelligence Platform

Production-grade, AI-assisted algorithmic trading platform for XAUUSD.

## Architecture

```text
dhahabu/
├── backend/
│   ├── api/                     # FastAPI routes + Pydantic schemas
│   ├── core/                    # Config, logging, constants
│   ├── db/                      # SQLAlchemy models + async engine
│   ├── scheduler/               # APScheduler job orchestration
│   ├── services/
│   │   ├── broker/              # Broker abstraction layer
│   │   │   ├── base.py          #   Abstract BrokerClient interface
│   │   │   ├── paper.py         #   Simulation (default)
│   │   │   ├── oanda.py         #   OANDA v20 REST API
│   │   │   ├── ctrader.py       #   cTrader Open API (Twisted/protobuf)
│   │   │   └── __init__.py      #   Factory — reads BROKER_MODE env var
│   │   ├── market_data/         # Twelve Data ingestion
│   │   ├── volatility_regime/   # ATR-based regime detection
│   │   ├── position_sizing/     # Risk-adjusted lot sizing
│   │   ├── risk_guardian/       # Central risk state + trading brain
│   │   ├── trade_lifecycle/     # Candle-driven execution + broker dispatch
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
│   ├── static/                  # Built frontend (served by FastAPI in production)
│   └── telegram/                # Signal + alert delivery
├── frontend/                    # React + TradingView Lightweight Charts
├── alembic/                     # Database migrations
├── tests/                       # Pytest unit tests
└── scripts/                     # Bootstrap utilities
```

## Tech Stack

| Layer | Technology |
| ----- | ---------- |
| API | FastAPI + Pydantic |
| Database | PostgreSQL + SQLAlchemy (async) |
| Migrations | Alembic |
| Scheduling | APScheduler |
| Market Data | Twelve Data API |
| Broker Layer | Paper (default) / OANDA v20 / cTrader Open API |
| Notifications | Telegram Bot API |
| Charts | TradingView Lightweight Charts |
| Frontend | React + TypeScript + Recharts |
| Deploy | Railway (backend) + Vercel (frontend) / Docker |

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
- Dispatches live orders to the configured broker (OANDA or cTrader) when `BROKER_MODE` is not `paper`

### Broker Layer

The broker layer is controlled by the `BROKER_MODE` environment variable and selected at startup by the factory in `backend/services/broker/__init__.py`.

| Mode | Description |
| ---- | ----------- |
| `paper` | Default. Orders are simulated against incoming candles. No external connections. |
| `oanda` | Live or practice execution via the OANDA v20 REST API. |
| `ctrader` | Live or demo execution via the cTrader Open API (Pepperstone, IC Markets, FXPro, etc.). Uses TCP/protobuf via a Twisted reactor running in a background daemon thread. |

All broker implementations satisfy the same `BrokerClient` interface (`place_order`, `get_position`, `close_position`, `get_account_balance`). The `broker_order_id` column on the `trades` table stores the broker-assigned position/order ID when live execution is enabled.

#### OANDA Setup

1. Create a free practice account at <https://fxpractice.oanda.com>
2. Go to Manage Funds → API Access → Generate Token
3. Copy your Account ID from the dashboard
4. Set `BROKER_MODE=oanda`, `OANDA_API_KEY`, `OANDA_ACCOUNT_ID`, and `OANDA_ENVIRONMENT=practice` (or `live`)

#### cTrader Setup (Pepperstone / IC Markets / any cTrader broker)

**Step 1 — Register a developer application (free):**
Go to <https://openapi.ctrader.com> → "Create Application". You receive `CTRADER_CLIENT_ID` and `CTRADER_CLIENT_SECRET`.

**Step 2 — Authorise your trading account (OAuth flow):**
Open this URL in your browser (replace `YOUR_CLIENT_ID`):

```text
https://connect.spotware.com/apps/YOUR_CLIENT_ID/auth
  ?redirect_uri=https://localhost
  &scope=trading
  &response_type=code
```

Log in with your cTrader ID. You receive an auth code in the redirect URL query string.

**Step 3 — Exchange the auth code for an access token:**

```bash
curl -X POST https://connect.spotware.com/apps/token \
  -d "grant_type=authorization_code" \
  -d "code=<auth_code>" \
  -d "redirect_uri=https://localhost" \
  -d "client_id=<YOUR_CLIENT_ID>" \
  -d "client_secret=<YOUR_CLIENT_SECRET>"
```

The response `access_token` is your `CTRADER_ACCESS_TOKEN`.

**Step 4 — Find your account ID:**
In the cTrader desktop app: Menu → Account Info → copy the numeric ID. Alternatively call `GET https://connect.spotware.com/apps/ACCOUNT_ID/tradeaccounts`.

**Step 5 — Set environment variables:**

```env
BROKER_MODE=ctrader
CTRADER_CLIENT_ID=...
CTRADER_CLIENT_SECRET=...
CTRADER_ACCOUNT_ID=...          # numeric
CTRADER_ACCESS_TOKEN=...
CTRADER_ENVIRONMENT=demo        # or "live"
```

### Self-Healing Engine (every 4-6h)

**Backtest Loop:**

```text
every 4h → Re-Backtest (7d/14d/30d/60d) → Walk-Forward (80/20) → Overfit?
  YES → Flag Overfitted + suppress live signals
  NO  → Continue
```

**Optimize Loop:**

```text
every 6h → Parameter Search (80 combos/strategy) → Monte Carlo (1000 sims) → Random wins?
  YES → Throw Away
  NO  → Promote Live (demote old)
```

**Circuit Breaker:**

```text
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

## Frontend Pages

| Route | Page | Description |
| ----- | ---- | ----------- |
| `/` | Dashboard | Aggregated KPIs, system health, active signals |
| `/chart` | Chart | TradingView Lightweight Charts with signal overlays (M15/H1/H4/D1) |
| `/signals` | Signals | Signal history with filters |
| `/trades` | Trades | Open and closed trade history |
| `/pnl` | PnL Analytics | Equity curve, daily bar chart, 8 KPI cards, per-day breakdown table. Lookback selector: 7D / 14D / 30D / 60D / 90D. |
| `/risk` | Risk | Current risk state, daily loss cap status, shutdown events |
| `/self-healing` | Self-Healing | Backtest results, walk-forward, Monte Carlo, overfit flags, promotions |
| `/scheduler` | Scheduler | Job status table with manual trigger buttons |

## Quick Start

```bash
# 1. Copy and configure environment
cp .env.example .env
# Edit .env — TWELVE_DATA_API_KEY and TELEGRAM_* are required for live signals.
# BROKER_MODE defaults to "paper" (safe for testing).

# 2. Start PostgreSQL
docker run -d -p 5432:5432 -e POSTGRES_DB=dhahabu -e POSTGRES_PASSWORD=password postgres:16

# 3. Install dependencies (includes ctrader-open-api and all other packages)
pip install -e ".[dev]"

# 4. Run migrations (creates tables including broker_order_id on trades)
alembic upgrade head

# 5. Seed default strategy parameters
python scripts/init_live_params.py

# 6. Start the platform
uvicorn backend.main:app --reload --port 8000

# 7. Start the frontend (dev)
cd frontend && npm install && npm run dev
```

> **First run:** The dashboard will show a "Warming up" state until the first scheduler jobs complete. Trigger `market_data_ingest` and `trading_brain` manually from the Scheduler page (or via API) to populate data immediately rather than waiting for the 30-minute cycle.

## Railway Deployment

1. Connect the GitHub repo to Railway
2. Add a PostgreSQL plugin in Railway
3. Set environment variables from `.env.example` (see the full table below)
4. Railway auto-deploys via `Dockerfile`
5. The `CMD` runs `alembic upgrade head` then starts uvicorn
6. The built frontend is served directly from FastAPI via `StaticFiles` at `/assets/*` with a SPA catch-all for all other paths. The Vite build must be run before the Docker image is built (the Dockerfile copies `frontend/dist` into `backend/static`).

## Vercel Deployment (frontend only)

The `frontend/vercel.json` configures Vite builds and a Vercel rewrite proxy so the frontend at `/api/*` forwards to your Railway backend URL.

1. Import the `frontend/` directory into a Vercel project
2. In the Vercel project settings → Environment Variables, add:

   ```env
   API_BASE_URL=https://your-railway-backend.railway.app
   ```

   This is read by the Vercel proxy function (`/api/[...path].js`) and is not the same as `VITE_API_URL`.

3. `VITE_API_URL` is already set to `/api` in `frontend/vercel.json` and `frontend/.env.production` — do not override it unless you want the browser to call the backend directly (cross-origin).
4. For direct cross-origin calls (no proxy), set `VITE_API_URL` to your backend URL and add your Vercel domain to `CORS_ALLOWED_ORIGINS` on the backend.

## API Reference

| Endpoint | Description |
| -------- | ----------- |
| `GET /health` | Liveness probe |
| `GET /dashboard/summary` | Dashboard aggregated KPIs |
| `GET /signals/active` | Approved signals (last 4h) |
| `GET /signals` | Signal history with filters |
| `GET /trades/open` | Open trades |
| `GET /trades/history` | Closed trade history |
| `GET /risk/state` | Current risk state |
| `GET /risk/events` | Risk event log |
| `GET /risk/shutdown` | Shutdown events |
| `GET /pnl/daily` | Daily PnL snapshots (used by PnL page) |
| `GET /pnl/today` | Today's PnL snapshot |
| `GET /strategies/rankings` | Live strategy leaderboard |
| `GET /validation/backtests` | Backtest run history |
| `GET /validation/walk-forward` | Walk-forward results |
| `GET /validation/monte-carlo` | Monte Carlo results |
| `GET /validation/overfit-flags` | Currently flagged strategies |
| `GET /validation/promotions` | Live promotion history |
| `GET /scheduler/jobs/latest` | Latest scheduler job status |
| `POST /scheduler/jobs/{job_name}/run` | Trigger a scheduler job immediately |
| `GET /system/state` | Component health |
| `GET /api/docs` | Swagger UI (FastAPI auto-generated) |
| `GET /api/redoc` | ReDoc UI |

## Tests

```bash
pytest tests/ -v --tb=short
```

## Environment Variables

See `.env.example` for all configuration options.

| Variable | Required | Default | Description |
| -------- | -------- | ------- | ----------- |
| `DATABASE_URL` | Yes | — | Async PostgreSQL URL (`postgresql+asyncpg://...`) |
| `DATABASE_SYNC_URL` | No | — | Sync PostgreSQL URL (used by Alembic) |
| `TWELVE_DATA_API_KEY` | Yes | — | Market data API key (twelvedata.com) |
| `TELEGRAM_BOT_TOKEN` | No | — | Telegram bot token for signal delivery |
| `TELEGRAM_CHAT_ID` | No | — | Telegram chat/channel ID for alerts |
| `ACCOUNT_BALANCE` | Yes | `10000.0` | Account balance in USD, used for position sizing |
| `MAX_DAILY_LOSS_PCT` | No | `0.03` | Daily loss cap that blocks new trades (3%) |
| `CONSECUTIVE_STOP_LOSSES_LIMIT` | No | `8` | Consecutive SL hits before 24h shutdown |
| `MAX_SIMULTANEOUS_TRADES` | No | `5` | Max open trades at any time |
| `BROKER_MODE` | No | `paper` | Broker to use: `paper`, `oanda`, or `ctrader` |
| `OANDA_API_KEY` | No* | — | OANDA v20 REST API key (*required when `BROKER_MODE=oanda`) |
| `OANDA_ACCOUNT_ID` | No* | — | OANDA account ID (*required when `BROKER_MODE=oanda`) |
| `OANDA_ENVIRONMENT` | No | `practice` | `practice` or `live` |
| `CTRADER_CLIENT_ID` | No* | — | cTrader developer app client ID (*required when `BROKER_MODE=ctrader`) |
| `CTRADER_CLIENT_SECRET` | No* | — | cTrader developer app client secret (*required when `BROKER_MODE=ctrader`) |
| `CTRADER_ACCOUNT_ID` | No* | — | Numeric cTrader trading account ID (*required when `BROKER_MODE=ctrader`) |
| `CTRADER_ACCESS_TOKEN` | No* | — | OAuth access token for the cTrader account (*required when `BROKER_MODE=ctrader`) |
| `CTRADER_ENVIRONMENT` | No | `demo` | `demo` or `live` |
| `CORS_ALLOWED_ORIGINS` | No | localhost + Vercel defaults | Comma-separated frontend origins allowed to call the backend in production |
| `VITE_API_URL` | No | `/api` | Frontend API base URL (baked in at build time) |
| `SECRET_KEY` | No | dev default | JWT / session secret — change in production |
| `ENVIRONMENT` | No | `development` | `development`, `staging`, or `production` |
| `LOG_LEVEL` | No | `INFO` | Logging verbosity |
| `PORT` | No | `8000` | HTTP port (Railway injects this automatically) |

## Development Notes

### Scheduler job intervals

| Job | Interval | Purpose |
| --- | -------- | ------- |
| `market_data_ingest` | Every 15 min | Pulls latest XAUUSD candles from Twelve Data |
| `trading_brain` | Every 30 min | Generates and approves signals, dispatches broker orders |
| `trade_reconcile` | Every 15 min | Updates open trade states from the broker |
| `self_healing_backtest` | Every 4h | Re-backtest + walk-forward + overfit detection |
| `param_search_monte_carlo` | Every 6h | Parameter optimization + Monte Carlo |
| `risk_monitor` | Every 15 min | Checks consecutive losses and daily cap |
| `daily_reset` | Midnight UTC | Creates new daily PnL snapshot |
| `health_check` | Every 5 min | Updates service component health |

All jobs can be triggered manually via `POST /scheduler/jobs/{job_name}/run` or the Scheduler page in the UI.

### Frontend environment

The frontend reads `VITE_API_URL` at build time.

| Context | Value | How it is set |
| ------- | ----- | ------------- |
| Local dev (Vite) | `http://localhost:8000` | `frontend/.env.local` |
| Vercel production | `/api` | `frontend/.env.production` and `frontend/vercel.json` |
| Railway (served by FastAPI) | `/api` | Default in `vercel.json`; not needed since the frontend and backend share the same origin |

### Database migrations

Alembic manages the schema. The current migration sequence:

| Revision | Description |
| -------- | ----------- |
| `0001_initial_schema` | Full initial schema |
| `0002_add_broker_order_id` | Adds `broker_order_id` column to `trades` table for live broker integration |

Run `alembic upgrade head` to apply all migrations. Alembic also runs automatically as the first step of the Docker `CMD` in production.

## Troubleshooting

**Dashboard shows "Warming up" indefinitely**
The trading brain has not run yet. Go to the Scheduler page and click "Run market ingest" then "Run trading brain". Data should appear within 30 seconds.

**No candles in chart / candle count shows 0**
`market_data_ingest` has not completed successfully. Check the Scheduler page for a failed job error message. Common causes: invalid `TWELVE_DATA_API_KEY` or rate limit exceeded (free tier: 8 calls/min).

**Chart is invisible / renders as a zero-height box on first load**
This was caused by the chart initialising with `clientWidth` before the container was laid out. The fix (now applied) is to create the chart with `autoSize: true` in `ChartPage.tsx`, which lets the TradingView library measure the container after layout.

**Frontend shows "Network Error" / API calls fail on Vercel**
Ensure `API_BASE_URL` is set in the Vercel project environment variables to your live backend URL (e.g. your Railway service URL). This is consumed by the Vercel proxy function. `VITE_API_URL` is already set to `/api` in the build config and should not need to be changed.

**Signals are being suppressed**
Check the Risk page. Trading may be blocked due to: daily loss cap hit, active 24h shutdown, or `can_trade = false`. The block reason is shown on the Risk page.

**`alembic upgrade head` fails**
Ensure `DATABASE_URL` is set and PostgreSQL is running. The URL must use the `postgresql+asyncpg://` scheme for the application and `postgresql://` (no `+asyncpg`) for `DATABASE_SYNC_URL` used by Alembic.

**Self-healing shows all strategies as "No data"**
`self_healing_backtest` has not run yet. Trigger it manually from the Scheduler page. It requires at least 7 days of candle history to backtest against.

**PnL page shows no data**
The `daily_reset` job creates a new PnL snapshot each day at midnight UTC. On the first day, trigger `daily_reset` manually from the Scheduler page. The `trading_brain` must also have run at least once to record trades against that day's snapshot.

**cTrader authentication times out on startup**
`CTraderBroker._ensure_started()` waits up to 30 seconds for the OAuth handshake via TCP. Causes of timeout: incorrect `CTRADER_CLIENT_ID` / `CTRADER_CLIENT_SECRET`, expired `CTRADER_ACCESS_TOKEN`, or the demo/live host being unreachable. Check that `CTRADER_ENVIRONMENT` matches the account type (a live account token will be rejected on the demo host).

**cTrader symbol not found error**
The platform normalises `XAU/USD` to `XAUUSD` before looking up the symbol ID. If your broker names the instrument differently in their cTrader terminal (e.g. `GOLD`), you will see a `ValueError`. Check the exact symbol name in the cTrader terminal and set `MARKET_DATA_SYMBOL` accordingly.

---

Built with Claude Code · Dhahabu (Swahili for "gold")
