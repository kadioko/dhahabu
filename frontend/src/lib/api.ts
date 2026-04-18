import axios from 'axios'

export const API_BASE_URL = (import.meta.env.VITE_API_URL || '/api').replace(/\/+$/, '')

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
})

function describeType(value: unknown): string {
  if (Array.isArray(value)) return 'array'
  if (value === null) return 'null'
  return typeof value
}

function assertNotHtml(data: unknown, endpoint: string): void {
  if (typeof data === 'string' && data.trim().startsWith('<!doctype html')) {
    throw new Error(`Expected JSON from ${endpoint} but received HTML. Check the API proxy or deploy rewrites.`)
  }
}

function expectArray<T>(data: unknown, endpoint: string): T[] {
  assertNotHtml(data, endpoint)
  if (!Array.isArray(data)) {
    throw new Error(`Expected array from ${endpoint} but received ${describeType(data)}.`)
  }
  return data as T[]
}

function expectObject<T extends object>(data: unknown, endpoint: string): T {
  assertNotHtml(data, endpoint)
  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    throw new Error(`Expected object from ${endpoint} but received ${describeType(data)}.`)
  }
  return data as T
}

api.interceptors.response.use(
  (response) => {
    const contentType = String(response.headers['content-type'] || '')
    if (contentType.includes('text/html')) {
      throw new Error(
        `Expected JSON from ${response.config.url ?? 'request'} but received HTML. Check Vercel proxy routing and API_BASE_URL.`
      )
    }
    return response
  },
  (error) => Promise.reject(error)
)

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

export type StrategyRanking = {
  rank: number
  strategy_name: string
  parameter_set_id: string
  score: number | null
  overfit_flag: boolean
  suppressed_flag: boolean
  promoted_at: string | null
  status: string
}

export type StrategyRankingsResponse = {
  rankings: StrategyRanking[]
  total: number
}

export type OverfitFlag = {
  id: string
  strategy_name: string
  score: number | null
  suppressed_flag: boolean
  status: string
}

export type OverfitFlagsResponse = {
  overfit_sets: OverfitFlag[]
}

export type PromotionRecord = {
  id: string
  strategy_name: string
  score: number | null
  promoted_at?: string | null
  discarded_at?: string | null
  discard_reason?: string | null
  status: string
}

export type PromotionsResponse = {
  promoted: PromotionRecord[]
  discarded: PromotionRecord[]
}

export const fetchDashboardSummary = () =>
  api.get('/dashboard/summary').then((r) => expectObject<DashboardSummary>(r.data, '/dashboard/summary'))

export const fetchRiskState = () =>
  api.get('/risk/state').then((r) => expectObject<RiskState>(r.data, '/risk/state'))

export const fetchActiveSignals = (symbol = 'XAU/USD') =>
  api
    .get('/signals/active', { params: { symbol } })
    .then((r) => expectArray<Signal>(r.data, '/signals/active'))

export const fetchSignals = (params?: Record<string, unknown>) =>
  api.get('/signals', { params }).then((r) => expectArray<Signal>(r.data, '/signals'))

export const fetchOpenTrades = () =>
  api.get('/trades/open').then((r) => expectArray<Trade>(r.data, '/trades/open'))

export const fetchTradeHistory = (params?: Record<string, unknown>) =>
  api.get('/trades/history', { params }).then((r) => expectArray<Trade>(r.data, '/trades/history'))

export const fetchCandles = (symbol: string, timeframe: string, limit = 200) =>
  api
    .get('/candles/latest', { params: { symbol, timeframe, limit } })
    .then((r) => {
      const data = expectObject<{ candles: unknown; symbol: string; timeframe: string }>(r.data, '/candles/latest')
      return {
        ...data,
        candles: expectArray<Candle>(data.candles, '/candles/latest candles'),
      }
    })

export const fetchStrategyRankings = () =>
  api
    .get('/strategies/rankings')
    .then((r) => {
      const data = expectObject<{ rankings: unknown; total: unknown }>(r.data, '/strategies/rankings')
      return {
        rankings: expectArray<StrategyRanking>(data.rankings, '/strategies/rankings rankings'),
        total: Number(data.total ?? 0),
      } satisfies StrategyRankingsResponse
    })

export const fetchBacktestRuns = (params?: Record<string, unknown>) =>
  api
    .get('/validation/backtests', { params })
    .then((r) => expectArray<BacktestRun>(r.data, '/validation/backtests'))

export const fetchWalkForwardRuns = (params?: Record<string, unknown>) =>
  api
    .get('/validation/walk-forward', { params })
    .then((r) => expectArray<WalkForwardRun>(r.data, '/validation/walk-forward'))

export const fetchMonteCarloRuns = (params?: Record<string, unknown>) =>
  api
    .get('/validation/monte-carlo', { params })
    .then((r) => expectArray<MonteCarloRun>(r.data, '/validation/monte-carlo'))

export const fetchOverfitFlags = () =>
  api
    .get('/validation/overfit-flags')
    .then((r) => {
      const data = expectObject<{ overfit_sets: unknown }>(r.data, '/validation/overfit-flags')
      return {
        overfit_sets: expectArray<OverfitFlag>(data.overfit_sets, '/validation/overfit-flags overfit_sets'),
      } satisfies OverfitFlagsResponse
    })

export const fetchPromotions = () =>
  api
    .get('/validation/promotions')
    .then((r) => {
      const data = expectObject<{ promoted: unknown; discarded: unknown }>(r.data, '/validation/promotions')
      return {
        promoted: expectArray<PromotionRecord>(data.promoted, '/validation/promotions promoted'),
        discarded: expectArray<PromotionRecord>(data.discarded, '/validation/promotions discarded'),
      } satisfies PromotionsResponse
    })

export const fetchSchedulerJobs = () =>
  api
    .get('/scheduler/jobs/latest')
    .then((r) => {
      const data = expectObject<{ jobs: unknown }>(r.data, '/scheduler/jobs/latest')
      return { jobs: expectArray<SchedulerJob>(data.jobs, '/scheduler/jobs/latest jobs') }
    })

export const fetchSystemState = () =>
  api.get('/system/state').then((r) => expectArray<SystemComponent>(r.data, '/system/state'))

export const fetchSystemOverview = () =>
  api.get('/system/overview').then((r) => expectObject<SystemOverview>(r.data, '/system/overview'))

export const triggerSchedulerJob = (jobName: string) =>
  api.post(`/scheduler/jobs/${jobName}/run`).then((r) => expectObject<Record<string, unknown>>(r.data, `/scheduler/jobs/${jobName}/run`))

export const fetchDailyPnL = (days = 30) =>
  api.get('/pnl/daily', { params: { days } }).then((r) => expectArray<Record<string, any>>(r.data, '/pnl/daily'))
