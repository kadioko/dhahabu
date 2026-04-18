# Manual Admin Triggers Guide

This guide explains every manual admin trigger in Dhahabu in two ways:

- `Professional view`: what the job does in system terms
- `Plain-English view`: what it means for someone operating the platform day to day

Use these triggers from the Scheduler page when you need to warm up the system, recover from missing data, validate a deployment, or force a workflow instead of waiting for the next scheduled interval.

## Quick Rule Of Thumb

- If the chart is empty: run `market_data_ingest`
- If signals are missing: run `trading_brain`
- If health looks stale or unknown: run `health_check`
- If risk state looks outdated: run `risk_monitor`
- If trades look stale: run `trade_reconcile`
- If backtests and optimization look stale: run `self_healing_backtest` or `param_search_monte_carlo`
- If daily PnL has not rolled over: run `daily_reset`

## Trigger Reference

### `market_data_ingest`

Professional view:
- Pulls the latest XAU/USD candles from Twelve Data
- Writes fresh market data into the candle store
- Feeds the chart, trading brain, and any system components that depend on recent price history

Plain-English view:
- This is the "bring in fresh price data" button
- If your chart is empty or stale, this is usually the first thing to run

When to run it:
- After first deployment
- When candles are missing
- When the chart shows old data
- Before running `trading_brain`

What success looks like:
- Latest candle time updates
- Candle counts increase
- Chart starts rendering real candles

What can go wrong:
- Invalid `TWELVE_DATA_API_KEY`
- Rate limits from Twelve Data
- Upstream API outage

### `health_check`

Professional view:
- Recomputes service/component health states
- Updates `SystemState` rows used by the dashboard and scheduler views
- Marks components as healthy, degraded, down, or unknown based on their latest behavior

Plain-English view:
- This is the "refresh the system health scoreboard" button
- It does not create market data or signals by itself
- It tells the UI what is healthy and what is not

When to run it:
- After running other jobs
- After a deploy
- When health percentages look stale or confusing

What success looks like:
- Service Health statuses update
- Unknown components may switch to healthy after their related jobs have run

### `trading_brain`

Professional view:
- Reads recent candles across configured timeframes
- Computes market regime and risk context
- Runs all enabled strategies
- Scores and approves/suppresses candidate signals
- Persists decisions and may dispatch live orders depending on broker mode

Plain-English view:
- This is the "generate trading decisions" button
- If you want fresh signals, this is the job that produces them

When to run it:
- After `market_data_ingest`
- When Signals page is empty
- When testing the full trading pipeline

What success looks like:
- New signals appear
- Rankings may update
- Risk logic gets fresh decision context

What can go wrong:
- Not enough candles
- Risk rules block trading
- Strategies produce no valid setups

### `risk_monitor`

Professional view:
- Recalculates current risk posture
- Checks daily loss limits and shutdown conditions
- Tracks consecutive stop-loss events and system-level trading blocks

Plain-English view:
- This is the "re-check if we are allowed to trade" button
- It refreshes the risk guardrails

When to run it:
- When Risk page looks stale
- After trades close
- When the system still shows `UNKNOWN` risk state

What success looks like:
- Risk state updates
- Trading blocked/allowed status becomes current
- `risk_monitor` component moves from unknown to healthy

### `trade_reconcile`

Professional view:
- Reconciles open trade state against the latest market or broker information
- Updates trade lifecycle records, status changes, and timing metadata

Plain-English view:
- This is the "sync my open trades" button
- If trade status looks wrong or stuck, this is the first button to use

When to run it:
- When open trades look stale
- After price has moved enough that TP/SL should have been hit
- When `trade_reconcile` shows `UNKNOWN`

What success looks like:
- Open trade list updates
- Trade status changes are reflected
- `trade_reconcile` health moves to healthy

### `self_healing_backtest`

Professional view:
- Runs backtesting and walk-forward validation
- Detects overfit conditions
- Updates validation history used by the Self-Healing page

Plain-English view:
- This is the "re-test the strategies" button
- It tells you whether strategies still look credible on recent data

When to run it:
- After enough history has accumulated
- When the Self-Healing page is empty
- When validating a new deployment or setup

What success looks like:
- Backtest and walk-forward rows appear
- Overfit flags update
- Self-Healing status becomes more informative

### `param_search_monte_carlo`

Professional view:
- Searches parameter combinations
- Evaluates candidate parameter sets
- Runs Monte Carlo robustness checks
- Supports promotion or rejection of candidate live parameter sets

Plain-English view:
- This is the "look for better strategy settings" button
- It is more of an optimization task than a live-ops task

When to run it:
- After validation is working
- When you want fresh optimization results
- When strategy rankings feel outdated

What success looks like:
- Monte Carlo rows appear
- Promotions or discards update
- Rankings may eventually change

### `daily_reset`

Professional view:
- Creates the new daily PnL snapshot boundary
- Resets daily counters and starts a fresh accounting window for the new day

Plain-English view:
- This is the "start a new trading day" button
- If PnL does not look like it rolled over, this is what you run

When to run it:
- For first-time setup testing
- If the daily PnL page has no entries
- If the UTC day changed but the system still looks stuck on yesterday

What success looks like:
- New daily PnL snapshot exists
- PnL views stop looking stale

## Recommended Run Sequences

### First deployment or fresh warm-up

1. `market_data_ingest`
2. `health_check`
3. `trading_brain`
4. `risk_monitor`
5. `trade_reconcile`
6. `health_check`

### Empty chart

1. `market_data_ingest`
2. `health_check`

### No signals

1. `market_data_ingest`
2. `trading_brain`
3. `risk_monitor`

### Unknown health components

1. Run the matching job for the unknown component
2. Run `health_check`

Examples:
- `risk_monitor` unknown -> run `risk_monitor`
- `trade_reconcile` unknown -> run `trade_reconcile`

### Validation and optimization refresh

1. `self_healing_backtest`
2. `param_search_monte_carlo`
3. `health_check`

## Safety Notes

- `market_data_ingest` is generally safe and low risk
- `health_check` is informational and low risk
- `trading_brain` can affect live decision state and may place trades if live broker mode is enabled
- `trade_reconcile` can update live trade lifecycle state
- `risk_monitor` can tighten or unlock risk posture based on the latest state
- `param_search_monte_carlo` and `self_healing_backtest` are computationally heavier and may take longer

## Best Practices

- Run `market_data_ingest` before `trading_brain`
- Run `health_check` after major operational actions
- Use `risk_monitor` and `trade_reconcile` to clear unknown states
- Do not judge platform health from one widget alone; check chart data, signals, service health, and latest jobs together

## Troubleshooting Shortcuts

- `Chart empty` -> run `market_data_ingest`
- `Signals empty` -> run `trading_brain`
- `Health low because of UNKNOWN` -> run the matching job, then `health_check`
- `Trades stale` -> run `trade_reconcile`
- `Risk stale` -> run `risk_monitor`
- `PnL day missing` -> run `daily_reset`
