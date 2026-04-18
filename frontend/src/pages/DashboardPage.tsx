import { useQuery } from '@tanstack/react-query'
import { format, formatDistanceToNow } from 'date-fns'
import { AlertTriangle, ArrowRight, Radar, ShieldCheck, Sparkles } from 'lucide-react'
import { ApiStatusPanel } from '../components/ApiStatusPanel'
import { Badge, directionBadge, statusBadge } from '../components/Badge'
import { StatCard } from '../components/StatCard'
import {
  API_BASE_URL,
  fetchActiveSignals,
  fetchDashboardSummary,
  fetchOpenTrades,
  fetchRiskState,
  fetchStrategyRankings,
  fetchSystemOverview,
} from '../lib/api'

const CONSECUTIVE_SL_LIMIT = 8

export function DashboardPage() {
  const summaryQuery = useQuery({
    queryKey: ['dashboard'],
    queryFn: fetchDashboardSummary,
  })
  const riskQuery = useQuery({
    queryKey: ['risk'],
    queryFn: fetchRiskState,
  })
  const signalsQuery = useQuery({
    queryKey: ['signals-active'],
    queryFn: () => fetchActiveSignals(),
  })
  const openTradesQuery = useQuery({
    queryKey: ['trades-open'],
    queryFn: fetchOpenTrades,
  })
  const rankingsQuery = useQuery({
    queryKey: ['strategy-rankings'],
    queryFn: fetchStrategyRankings,
  })
  const overviewQuery = useQuery({
    queryKey: ['system-overview'],
    queryFn: fetchSystemOverview,
  })

  const summary = summaryQuery.data
  const risk = riskQuery.data
  const signals = signalsQuery.data
  const openTrades = openTradesQuery.data
  const rankings = rankingsQuery.data
  const overview = overviewQuery.data

  const isLoading = [
    summaryQuery.isLoading,
    riskQuery.isLoading,
    signalsQuery.isLoading,
    openTradesQuery.isLoading,
    rankingsQuery.isLoading,
    overviewQuery.isLoading,
  ].some(Boolean)
  const isError = [
    summaryQuery.isError,
    riskQuery.isError,
    signalsQuery.isError,
    openTradesQuery.isError,
    rankingsQuery.isError,
    overviewQuery.isError,
  ].some(Boolean)

  const isShutdown = summary?.trading_mode === 'shutdown'
  const pnlPct = summary?.pnl_today?.realized_pnl_pct ?? 0
  const pnlPositive = pnlPct >= 0
  const hasSignals = (signals?.length ?? 0) > 0
  const hasRankings = (rankings?.rankings?.length ?? 0) > 0
  const hasSystemHealth = (summary?.system_health?.total_components ?? 0) > 0
  const isInitializing = !hasSignals || !hasRankings || !hasSystemHealth
  const marketPosture = isShutdown
    ? 'Protection mode'
    : hasSignals
    ? 'Opportunity scan live'
    : 'Collecting context'

  return (
    <div className="space-y-6 p-4 md:p-6">
      <section className="overflow-hidden rounded-[2rem] border border-white/10 bg-[linear-gradient(135deg,rgba(251,191,36,0.18),rgba(15,23,42,0.85)_40%,rgba(14,116,144,0.22))] p-6 shadow-[0_30px_120px_-60px_rgba(251,191,36,0.35)]">
        <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
          <div className="max-w-2xl">
            <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-amber-300/20 bg-amber-300/10 px-3 py-1 text-xs uppercase tracking-[0.28em] text-amber-200/90">
              <Sparkles className="h-3.5 w-3.5" />
              Trading intelligence
            </div>
            <h1 className="text-3xl font-semibold tracking-tight text-white md:text-4xl">Command center</h1>
            <p className="mt-3 max-w-xl text-sm leading-6 text-slate-300 md:text-base">
              Keep the signal engine, risk posture, and live execution context in one place. This view now surfaces clearer system state even when jobs are still warming up.
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-3xl border border-white/10 bg-slate-950/55 px-4 py-4 backdrop-blur">
              <div className="text-[11px] uppercase tracking-[0.28em] text-slate-500">Market posture</div>
              <div className="mt-2 flex items-center gap-2 text-lg font-medium text-white">
                {isShutdown ? <AlertTriangle className="h-5 w-5 text-red-300" /> : <Radar className="h-5 w-5 text-cyan-300" />}
                {marketPosture}
              </div>
              <div className="mt-2 text-sm text-slate-400">
                {summary?.timestamp ? format(new Date(summary.timestamp), 'MMM d, yyyy HH:mm') : 'Waiting for first snapshot'} UTC
              </div>
            </div>
            <div className="rounded-3xl border border-white/10 bg-slate-950/55 px-4 py-4 backdrop-blur">
              <div className="text-[11px] uppercase tracking-[0.28em] text-slate-500">Protection state</div>
              <div className="mt-2 flex items-center gap-2 text-lg font-medium text-white">
                <ShieldCheck className="h-5 w-5 text-emerald-300" />
                {risk?.can_trade ? 'Trading allowed' : 'Guardrails engaged'}
              </div>
              <div className="mt-2 text-sm text-slate-400">
                {risk?.block_reason ?? 'No active block reasons'}
              </div>
            </div>
          </div>
        </div>
        <div className="mt-5 flex flex-wrap items-center gap-2">
          {overview?.latest_candle_at && (
            <Badge variant="blue">Candle {formatDistanceToNow(new Date(overview.latest_candle_at), { addSuffix: true })}</Badge>
          )}
          {isShutdown ? <Badge variant="red">24H shutdown</Badge> : <Badge variant="green">System live</Badge>}
          {summary?.system_health?.total_components ? (
            <Badge variant="gray">
              {summary.system_health.healthy_components}/{summary.system_health.total_components} components healthy
            </Badge>
          ) : null}
        </div>
      </section>

      {isError && (
        <div className="rounded-3xl border border-red-500/20 bg-red-950/30 p-4 text-sm text-red-100">
          One or more dashboard feeds failed to load. The page will keep retrying, but the API or scheduler may need attention.
        </div>
      )}

      {isLoading && !summary && (
        <div className="rounded-3xl border border-white/10 bg-slate-950/70 p-6 text-sm text-slate-400">
          Loading live dashboard state...
        </div>
      )}

      {isShutdown && (
        <div className="flex items-start gap-3 rounded-3xl border border-red-500/30 bg-red-950/50 p-4">
          <AlertTriangle className="mt-0.5 h-6 w-6 text-red-300" />
          <div>
            <div className="font-semibold text-red-300">Circuit breaker active. All trading is suspended.</div>
            <div className="mt-1 text-sm text-red-100/70">{summary?.shutdown.reason}</div>
            {summary?.shutdown.ends_at && (
              <div className="mt-1 text-xs text-slate-300/70">
                Resumes: {format(new Date(summary.shutdown.ends_at), 'MMM d HH:mm UTC')}
              </div>
            )}
          </div>
        </div>
      )}

      {isInitializing && (
        <div className="rounded-3xl border border-cyan-500/20 bg-cyan-950/20 p-4">
          <div className="font-medium text-cyan-200">System is healthy and still warming up</div>
          <div className="mt-1 text-sm text-cyan-100/70">
            Market data is connected. Signals, rankings, and component health will appear as scheduler jobs complete and strategies emit outputs.
          </div>
          <div className="mt-2 text-xs text-cyan-100/50">
            {overview?.latest_successful_job?.job_name
              ? `Latest completed job: ${overview.latest_successful_job.job_name}`
              : 'No completed scheduler jobs have been recorded yet'}
          </div>
        </div>
      )}

      <ApiStatusPanel
        endpointLabel="Dashboard, overview, and signal feeds"
        query={overviewQuery}
        onRefresh={() => {
          void summaryQuery.refetch()
          void riskQuery.refetch()
          void signalsQuery.refetch()
          void rankingsQuery.refetch()
          void openTradesQuery.refetch()
          void overviewQuery.refetch()
        }}
        items={[
          {
            label: 'Overview API',
            value: overviewQuery.isError
              ? 'Unavailable'
              : overview?.latest_candle_at
              ? 'Connected'
              : 'Connected, waiting for data',
            tone: overviewQuery.isError ? 'error' : overview?.latest_candle_at ? 'ok' : 'warn',
            detail: overview?.latest_candle_at
              ? `Latest candle ${formatDistanceToNow(new Date(overview.latest_candle_at), { addSuffix: true })}`
              : 'No candle timestamps returned yet',
          },
          {
            label: 'Signals feed',
            value: signalsQuery.isError ? 'Request failed' : `${signals?.length ?? 0} active signals`,
            tone: signalsQuery.isError ? 'error' : (signals?.length ?? 0) > 0 ? 'ok' : 'warn',
            detail: signalsQuery.isError
              ? 'Trading brain data is not loading'
              : 'Approved signals from the last 4 hours',
          },
          {
            label: 'Scheduler activity',
            value: overview?.latest_successful_job?.job_name ?? 'No successful jobs yet',
            tone: overview?.latest_successful_job?.job_name ? 'ok' : 'warn',
            detail: overview?.latest_failed_job?.error_message ?? 'Latest success is shown when jobs begin completing',
          },
          {
            label: 'API target',
            value: API_BASE_URL,
            tone: API_BASE_URL.includes('railway.app') ? 'ok' : 'warn',
            detail: 'Frontend base URL currently used for live requests',
          },
        ]}
      />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          label="Today's PnL"
          value={`${pnlPositive ? '+' : ''}${(pnlPct * 100).toFixed(2)}%`}
          sub={`$${(summary?.pnl_today?.realized_pnl ?? 0).toFixed(0)}`}
          trend={pnlPositive ? 'up' : 'down'}
          urgent={summary?.pnl_today?.trading_blocked}
        />
        <StatCard
          label="Open Trades"
          value={summary?.open_trades ?? 0}
          sub={`${risk?.open_trades_long ?? 0}L / ${risk?.open_trades_short ?? 0}S`}
        />
        <StatCard label="Active Signals" value={summary?.active_signals ?? 0} sub="last 4 hours" />
        <StatCard
          label="Consecutive SL"
          value={risk?.consecutive_sl_hits ?? 0}
          sub={`limit: ${CONSECUTIVE_SL_LIMIT}`}
          urgent={(risk?.consecutive_sl_hits ?? 0) >= CONSECUTIVE_SL_LIMIT - 2}
        />
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Live Strategies" value={summary?.live_strategies ?? 0} sub="parameter sets active" />
        <StatCard
          label="System Health"
          value={`${summary?.system_health?.health_pct ?? 0}%`}
          sub={`${summary?.system_health?.healthy_components ?? 0}/${summary?.system_health?.total_components ?? 0} healthy`}
          trend={
            (summary?.system_health?.health_pct ?? 0) >= 80
              ? 'up'
              : (summary?.system_health?.health_pct ?? 0) >= 50
              ? 'neutral'
              : 'down'
          }
        />
        <StatCard
          label="Win Rate Today"
          value={
            (summary?.pnl_today?.trade_count ?? 0) > 0
              ? `${(((summary?.pnl_today?.win_count ?? 0) / (summary?.pnl_today?.trade_count ?? 1)) * 100).toFixed(0)}%`
              : '—'
          }
          sub={`${summary?.pnl_today?.win_count ?? 0}W / ${summary?.pnl_today?.loss_count ?? 0}L`}
        />
        <StatCard
          label="Account Risk"
          value={`${((risk?.estimated_open_exposure_pct ?? 0) * 100).toFixed(2)}%`}
          sub="open exposure"
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-[2rem] border border-white/10 bg-slate-950/80">
          <div className="flex items-center justify-between border-b border-white/10 px-5 py-4">
            <h2 className="font-medium text-slate-100">Active Signals</h2>
            <Badge variant="yellow">{signals?.length ?? 0}</Badge>
          </div>
          <div className="divide-y divide-white/10">
            {(!signals || signals.length === 0) && (
              <div className="px-5 py-8 text-center text-sm text-slate-500">
                No active signals in the last 4 hours. Run the trading brain or wait for the next cycle.
              </div>
            )}
            {signals?.slice(0, 5).map((signal) => (
              <div key={signal.id} className="flex items-center justify-between px-5 py-3">
                <div>
                  <div className="mb-1 flex items-center gap-2">
                    {directionBadge(signal.direction)}
                    <span className="text-sm font-medium text-slate-200">
                      {signal.strategy_name.replace(/_/g, ' ').toUpperCase()}
                    </span>
                  </div>
                  <div className="text-xs text-slate-500">
                    Entry: <span className="text-slate-300">{signal.entry.toFixed(2)}</span>
                    {' · '}SL: <span className="text-red-400">{signal.stop_loss.toFixed(2)}</span>
                    {' · '}TP: <span className="text-emerald-400">{signal.take_profit.toFixed(2)}</span>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-xs text-slate-400">Conf: {(signal.confidence * 100).toFixed(0)}%</div>
                  <div className="text-xs text-slate-500">{signal.timeframe}</div>
                </div>
              </div>
            ))}
            {(signals?.length ?? 0) > 5 && (
              <div className="px-5 py-3 text-center text-xs text-slate-500">
                <span className="inline-flex items-center gap-1">
                  +{(signals?.length ?? 0) - 5} more
                  <ArrowRight className="h-3.5 w-3.5" />
                  view all on Signals page
                </span>
              </div>
            )}
          </div>
        </div>

        <div className="rounded-[2rem] border border-white/10 bg-slate-950/80">
          <div className="border-b border-white/10 px-5 py-4">
            <h2 className="font-medium text-slate-100">Strategy Leaderboard</h2>
          </div>
          <div className="divide-y divide-white/10">
            {(!rankings?.rankings || rankings.rankings.length === 0) && (
              <div className="px-5 py-8 text-center text-sm text-slate-500">
                No live parameter sets yet. Self-healing and optimization jobs have not promoted any strategy versions.
              </div>
            )}
            {rankings?.rankings?.map((ranking: any) => (
              <div key={ranking.parameter_set_id} className="flex items-center justify-between px-5 py-3">
                <div className="flex items-center gap-3">
                  <span className="w-4 font-mono text-sm text-slate-600">#{ranking.rank}</span>
                  <div>
                    <div className="text-sm font-medium text-slate-200">
                      {ranking.strategy_name.replace(/_/g, ' ').replace(/\b\w/g, (letter: string) => letter.toUpperCase())}
                    </div>
                    <div className="mt-0.5 flex items-center gap-2">
                      {ranking.overfit_flag && <Badge variant="red" size="xs">OVERFIT</Badge>}
                      {ranking.suppressed_flag && <Badge variant="orange" size="xs">SUPPRESSED</Badge>}
                      {!ranking.overfit_flag && !ranking.suppressed_flag && <Badge variant="green" size="xs">LIVE</Badge>}
                    </div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-mono text-sm text-amber-300">
                    {ranking.score != null ? ranking.score.toFixed(3) : '—'}
                  </div>
                  <div className="text-xs text-slate-600">score</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="rounded-[2rem] border border-white/10 bg-slate-950/80">
        <div className="border-b border-white/10 px-5 py-4">
          <h2 className="font-medium text-slate-100">Open Trades</h2>
        </div>
        {(!openTrades || openTrades.length === 0) ? (
          <div className="px-5 py-8 text-center text-sm text-slate-500">
            No open trades right now. The trade lifecycle panel will populate after approved signals trigger entries.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/10 text-xs text-slate-500">
                  <th className="px-5 py-2 text-left">Status</th>
                  <th className="px-5 py-2 text-left">Entry</th>
                  <th className="px-5 py-2 text-left">SL</th>
                  <th className="px-5 py-2 text-left">TP</th>
                  <th className="px-5 py-2 text-left">Size</th>
                  <th className="px-5 py-2 text-left">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/10">
                {openTrades.map((trade) => (
                  <tr key={trade.id} className="hover:bg-white/5">
                    <td className="px-5 py-3">{statusBadge(trade.status)}</td>
                    <td className="px-5 py-3 font-mono text-slate-300">{trade.entry_price?.toFixed(2) ?? '—'}</td>
                    <td className="px-5 py-3 font-mono text-red-400">{trade.stop_loss.toFixed(2)}</td>
                    <td className="px-5 py-3 font-mono text-emerald-400">{trade.take_profit.toFixed(2)}</td>
                    <td className="px-5 py-3 font-mono text-slate-400">{trade.position_size.toFixed(2)}</td>
                    <td className="px-5 py-3 text-xs text-slate-500">
                      {format(new Date(trade.created_at), 'HH:mm')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
