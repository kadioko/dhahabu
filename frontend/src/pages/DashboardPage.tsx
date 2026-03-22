import { useQuery } from '@tanstack/react-query'
import {
  fetchDashboardSummary,
  fetchRiskState,
  fetchActiveSignals,
  fetchOpenTrades,
  fetchStrategyRankings,
} from '../lib/api'
import { StatCard } from '../components/StatCard'
import { Badge, directionBadge, statusBadge } from '../components/Badge'
import { format } from 'date-fns'

export function DashboardPage() {
  const { data: summary } = useQuery({
    queryKey: ['dashboard'],
    queryFn: fetchDashboardSummary,
  })
  const { data: risk } = useQuery({
    queryKey: ['risk'],
    queryFn: fetchRiskState,
  })
  const { data: signals } = useQuery({
    queryKey: ['signals-active'],
    queryFn: () => fetchActiveSignals(),
  })
  const { data: openTrades } = useQuery({
    queryKey: ['trades-open'],
    queryFn: fetchOpenTrades,
  })
  const { data: rankings } = useQuery({
    queryKey: ['strategy-rankings'],
    queryFn: fetchStrategyRankings,
  })

  const isShutdown = summary?.trading_mode === 'shutdown'
  const pnlPct = summary?.pnl_today.realized_pnl_pct ?? 0
  const pnlPositive = pnlPct >= 0

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-100">Command Center</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {summary?.timestamp ? format(new Date(summary.timestamp), 'MMM d, yyyy HH:mm') : '—'} UTC
          </p>
        </div>
        <div className="flex items-center gap-2">
          {isShutdown ? (
            <Badge variant="red">🚨 24H SHUTDOWN</Badge>
          ) : (
            <Badge variant="green">● LIVE</Badge>
          )}
        </div>
      </div>

      {/* Shutdown Banner */}
      {isShutdown && (
        <div className="bg-red-950/50 border border-red-500/30 rounded-xl p-4 flex items-start gap-3">
          <span className="text-2xl">🚨</span>
          <div>
            <div className="text-red-400 font-semibold">Circuit Breaker Active — All Trading Suspended</div>
            <div className="text-red-400/70 text-sm mt-1">{summary?.shutdown.reason}</div>
            {summary?.shutdown.ends_at && (
              <div className="text-gray-400 text-xs mt-1">
                Resumes: {format(new Date(summary.shutdown.ends_at), 'MMM d HH:mm UTC')}
              </div>
            )}
          </div>
        </div>
      )}

      {/* KPI Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Today's PnL"
          value={`${pnlPositive ? '+' : ''}${(pnlPct * 100).toFixed(2)}%`}
          sub={`$${(summary?.pnl_today.realized_pnl ?? 0).toFixed(0)}`}
          trend={pnlPositive ? 'up' : 'down'}
          urgent={summary?.pnl_today.trading_blocked}
        />
        <StatCard
          label="Open Trades"
          value={summary?.open_trades ?? 0}
          sub={`${risk?.open_trades_long ?? 0}L / ${risk?.open_trades_short ?? 0}S`}
        />
        <StatCard
          label="Active Signals"
          value={summary?.active_signals ?? 0}
          sub="last 4 hours"
        />
        <StatCard
          label="Consecutive SL"
          value={risk?.consecutive_sl_hits ?? 0}
          sub={`limit: ${8}`}
          urgent={(risk?.consecutive_sl_hits ?? 0) >= 6}
        />
      </div>

      {/* Second KPI row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Live Strategies"
          value={summary?.live_strategies ?? 0}
          sub="parameter sets active"
        />
        <StatCard
          label="System Health"
          value={`${summary?.system_health.health_pct ?? 0}%`}
          sub={`${summary?.system_health.healthy_components ?? 0}/${summary?.system_health.total_components ?? 0} healthy`}
          trend={
            (summary?.system_health.health_pct ?? 0) >= 80
              ? 'up'
              : (summary?.system_health.health_pct ?? 0) >= 50
              ? 'neutral'
              : 'down'
          }
        />
        <StatCard
          label="Win Rate Today"
          value={
            (summary?.pnl_today.trade_count ?? 0) > 0
              ? `${(((summary?.pnl_today.win_count ?? 0) / (summary?.pnl_today.trade_count ?? 1)) * 100).toFixed(0)}%`
              : '—'
          }
          sub={`${summary?.pnl_today.win_count ?? 0}W / ${summary?.pnl_today.loss_count ?? 0}L`}
        />
        <StatCard
          label="Account Risk"
          value={`${((risk?.estimated_open_exposure_pct ?? 0) * 100).toFixed(2)}%`}
          sub="open exposure"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Active Signals */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl">
          <div className="px-5 py-4 border-b border-gray-800 flex items-center justify-between">
            <h2 className="font-medium text-gray-100">Active Signals</h2>
            <Badge variant="yellow">{signals?.length ?? 0}</Badge>
          </div>
          <div className="divide-y divide-gray-800">
            {(!signals || signals.length === 0) && (
              <div className="px-5 py-8 text-center text-gray-600 text-sm">
                No active signals in the last 4 hours
              </div>
            )}
            {signals?.slice(0, 5).map((s) => (
              <div key={s.id} className="px-5 py-3 flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    {directionBadge(s.direction)}
                    <span className="text-sm font-medium text-gray-200">
                      {s.strategy_name.replace('_', ' ').toUpperCase()}
                    </span>
                  </div>
                  <div className="text-xs text-gray-500">
                    Entry: <span className="text-gray-300">{s.entry.toFixed(2)}</span>
                    {' · '}SL: <span className="text-red-400">{s.stop_loss.toFixed(2)}</span>
                    {' · '}TP: <span className="text-green-400">{s.take_profit.toFixed(2)}</span>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-xs text-gray-400">Conf: {(s.confidence * 100).toFixed(0)}%</div>
                  <div className="text-xs text-gray-500">{s.timeframe}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Strategy Leaderboard */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl">
          <div className="px-5 py-4 border-b border-gray-800">
            <h2 className="font-medium text-gray-100">Strategy Leaderboard</h2>
          </div>
          <div className="divide-y divide-gray-800">
            {(!rankings?.rankings || rankings.rankings.length === 0) && (
              <div className="px-5 py-8 text-center text-gray-600 text-sm">
                No live parameter sets yet
              </div>
            )}
            {rankings?.rankings?.map((r: any) => (
              <div key={r.parameter_set_id} className="px-5 py-3 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="text-gray-600 text-sm font-mono w-4">#{r.rank}</span>
                  <div>
                    <div className="text-sm font-medium text-gray-200">
                      {r.strategy_name.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase())}
                    </div>
                    <div className="flex items-center gap-2 mt-0.5">
                      {r.overfit_flag && <Badge variant="red" size="xs">OVERFIT</Badge>}
                      {r.suppressed_flag && <Badge variant="orange" size="xs">SUPPRESSED</Badge>}
                      {!r.overfit_flag && !r.suppressed_flag && <Badge variant="green" size="xs">LIVE</Badge>}
                    </div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-sm font-mono text-yellow-400">
                    {r.score != null ? r.score.toFixed(3) : '—'}
                  </div>
                  <div className="text-xs text-gray-600">score</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Open Trades */}
      {openTrades && openTrades.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl">
          <div className="px-5 py-4 border-b border-gray-800">
            <h2 className="font-medium text-gray-100">Open Trades</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-gray-500 border-b border-gray-800">
                  <th className="text-left px-5 py-2">Status</th>
                  <th className="text-left px-5 py-2">Entry</th>
                  <th className="text-left px-5 py-2">SL</th>
                  <th className="text-left px-5 py-2">TP</th>
                  <th className="text-left px-5 py-2">Size</th>
                  <th className="text-left px-5 py-2">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {openTrades.map((t) => (
                  <tr key={t.id} className="hover:bg-gray-800/30">
                    <td className="px-5 py-3">{statusBadge(t.status)}</td>
                    <td className="px-5 py-3 font-mono text-gray-300">
                      {t.entry_price?.toFixed(2) ?? '—'}
                    </td>
                    <td className="px-5 py-3 font-mono text-red-400">{t.stop_loss.toFixed(2)}</td>
                    <td className="px-5 py-3 font-mono text-green-400">{t.take_profit.toFixed(2)}</td>
                    <td className="px-5 py-3 font-mono text-gray-400">{t.position_size.toFixed(2)}</td>
                    <td className="px-5 py-3 text-gray-500 text-xs">
                      {format(new Date(t.created_at), 'HH:mm')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
