import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || ''

export const api = axios.create({
  baseURL: BASE_URL,
  timeout: 15000,
})

export type Signal = {
  id: string
  strategy_name: string
  symbol: string
  timeframe: string
  direction: 'long' | 'short'
  entry: number
  stop_loss: number
  take_profit: number
  confidence: number
  brain_score: number | null
  approval_status: string
  suppression_reason: string | null
  rationale_json: Record<string, unknown> | null
  risk_metadata_json: Record<string, unknown> | null
  created_at: string
}

export type Trade = {
  id: string
  signal_id: string
  status: string
  entry_time: string | null
  exit_time: string | null
  entry_price: number | null
  exit_price: number | null
  stop_loss: number
  take_profit: number
  position_size: number
  pnl: number | null
  pnl_pct: number | null
  closed_reason: string | null
  consecutive_loss_seq_snapshot: number
  created_at: string
}

export type RiskState = {
  daily_realized_pnl: number
  daily_realized_pnl_pct: number
  daily_loss_cap_hit: boolean
  trading_blocked: boolean
  shutdown_active: boolean
  shutdown_reason: string | null
  shutdown_ends_at: string | null
  shutdown_cooldown_remaining_hours: number | null
  open_trade_count: number
  open_trades_long: number
  open_trades_short: number
  estimated_open_exposure_pct: number
  consecutive_sl_hits: number
  can_trade: boolean
  block_reason: string | null
  timestamp: string
}

export type DashboardSummary = {
  timestamp: string
  trading_mode: 'active' | 'shutdown'
  shutdown: {
    active: boolean
    reason: string | null
    ends_at: string | null
  }
  pnl_today: {
    realized_pnl: number
    realized_pnl_pct: number
    trading_blocked: boolean
    trade_count: number
    win_count: number
    loss_count: number
  }
  open_trades: number
  active_signals: number
  live_strategies: number
  system_health: {
    healthy_components: number
    total_components: number
    health_pct: number
  }
}

export type Candle = {
  timestamp: string
  open: number
  high: number
  low: number
  close: number
  volume: number | null
}

export type BacktestRun = {
  id: string
  strategy_name: string
  parameter_set_id: string
  window_days: number
  start_at: string
  end_at: string
  total_trades: number
  win_rate: number | null
  profit_factor: number | null
  sharpe_score: number | null
  expectancy: number | null
  max_drawdown: number | null
  created_at: string
}

export type WalkForwardRun = {
  id: string
  strategy_name: string
  parameter_set_id: string
  oos_degradation_score: number | null
  overfit_flag: boolean
  train_metrics_json: Record<string, unknown> | null
  test_metrics_json: Record<string, unknown> | null
  oos_collapse_details: Record<string, unknown> | null
  created_at: string
}

export type MonteCarloRun = {
  id: string
  strategy_name: string
  robustness_score: number
  random_beats_original: number
  pass_flag: boolean
  simulation_count: number
  distribution_json: Record<string, unknown> | null
  created_at: string
}

export type SchedulerJob = {
  job_name: string
  started_at: string
  finished_at: string | null
  status: string
  details_json?: Record<string, unknown> | null
  error_message: string | null
}

export type SystemComponent = {
  id: string
  component_name: string
  status: string
  health_score: number | null
  last_run_at: string | null
  last_error: string | null
  metadata_json?: Record<string, unknown> | null
  updated_at: string
}

export type SystemOverview = {
  timestamp: string
  latest_candle_at: string | null
  candle_counts: Record<string, number>
  component_count: number
  latest_successful_job: {
    job_name: string
    started_at: string
    finished_at: string | null
    status: string
  } | null
  latest_failed_job: {
    job_name: string
    started_at: string
    finished_at: string | null
    status: string
    error_message: string | null
  } | null
  latest_market_data_run: {
    job_name: string
    started_at: string
    finished_at: string | null
    status: string
    details_json?: Record<string, unknown> | null
    error_message: string | null
  } | null
}

// API functions
export const fetchDashboardSummary = () =>
  api.get<DashboardSummary>('/dashboard/summary').then(r => r.data)

export const fetchRiskState = () =>
  api.get<RiskState>('/risk/state').then(r => r.data)

export const fetchActiveSignals = (symbol = 'XAU/USD') =>
  api.get<Signal[]>('/signals/active', { params: { symbol } }).then(r => r.data)

export const fetchSignals = (params?: Record<string, unknown>) =>
  api.get<Signal[]>('/signals', { params }).then(r => r.data)

export const fetchOpenTrades = () =>
  api.get<Trade[]>('/trades/open').then(r => r.data)

export const fetchTradeHistory = (params?: Record<string, unknown>) =>
  api.get<Trade[]>('/trades/history', { params }).then(r => r.data)

export const fetchCandles = (symbol: string, timeframe: string, limit = 200) =>
  api.get<{ candles: Candle[]; symbol: string; timeframe: string }>(
    '/candles/latest',
    { params: { symbol, timeframe, limit } }
  ).then(r => r.data)

export const fetchStrategyRankings = () =>
  api.get('/strategies/rankings').then(r => r.data)

export const fetchBacktestRuns = (params?: Record<string, unknown>) =>
  api.get<BacktestRun[]>('/validation/backtests', { params }).then(r => r.data)

export const fetchWalkForwardRuns = (params?: Record<string, unknown>) =>
  api.get<WalkForwardRun[]>('/validation/walk-forward', { params }).then(r => r.data)

export const fetchMonteCarloRuns = (params?: Record<string, unknown>) =>
  api.get<MonteCarloRun[]>('/validation/monte-carlo', { params }).then(r => r.data)

export const fetchOverfitFlags = () =>
  api.get('/validation/overfit-flags').then(r => r.data)

export const fetchPromotions = () =>
  api.get('/validation/promotions').then(r => r.data)

export const fetchSchedulerJobs = () =>
  api.get<{ jobs: SchedulerJob[] }>('/scheduler/jobs/latest').then(r => r.data)

export const fetchSystemState = () =>
  api.get<SystemComponent[]>('/system/state').then(r => r.data)

export const fetchSystemOverview = () =>
  api.get<SystemOverview>('/system/overview').then(r => r.data)

export const triggerSchedulerJob = (jobName: string) =>
  api.post(`/scheduler/jobs/${jobName}/run`).then(r => r.data)

export const fetchDailyPnL = (days = 30) =>
  api.get('/pnl/daily', { params: { days } }).then(r => r.data)
