import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Cell,
} from 'recharts'
import { fetchDailyPnL } from '../lib/api'
import { StatCard } from '../components/StatCard'
import { Badge } from '../components/Badge'

const LOOKBACK_OPTIONS = [
  { label: '7D', value: 7 },
  { label: '14D', value: 14 },
  { label: '30D', value: 30 },
  { label: '60D', value: 60 },
  { label: '90D', value: 90 },
]

export function PnLPage() {
  const [days, setDays] = useState(30)

  const { data: pnlHistory, isLoading } = useQuery({
    queryKey: ['pnl-history', days],
    queryFn: () => fetchDailyPnL(days),
  })

  const rows = Array.isArray(pnlHistory)
    ? [...(pnlHistory as any[])].reverse()
    : []

  // Cumulative equity curve
  const equityData = rows.reduce<{ date: string; equity: number }[]>((acc, d) => {
    const prev = acc.length > 0 ? acc[acc.length - 1].equity : 0
    acc.push({ date: d.date, equity: +(prev + d.realized_pnl_pct * 100).toFixed(3) })
    return acc
  }, [])

  // Daily bar data
  const barData = rows.map(d => ({
    date: d.date,
    pnl_pct: +(d.realized_pnl_pct * 100).toFixed(3),
    pnl: +d.realized_pnl.toFixed(2),
  }))

  // Summary stats
  const winDays = rows.filter(d => d.realized_pnl_pct > 0).length
  const lossDays = rows.filter(d => d.realized_pnl_pct < 0).length
  const totalTrades = rows.reduce((s, d) => s + (d.trade_count ?? 0), 0)
  const totalWins = rows.reduce((s, d) => s + (d.win_count ?? 0), 0)
  const totalLosses = rows.reduce((s, d) => s + (d.loss_count ?? 0), 0)
  const totalPnl = rows.reduce((s, d) => s + d.realized_pnl, 0)
  const totalPnlPct = rows.reduce((s, d) => s + d.realized_pnl_pct * 100, 0)
  const maxDrawdown = rows.reduce((m, d) => Math.max(m, d.max_drawdown ?? 0), 0)
  const winRate = totalTrades > 0 ? (totalWins / totalTrades) * 100 : null
  const dayWinRate = rows.length > 0 ? (winDays / rows.length) * 100 : null
  const bestDay = rows.reduce<any>((b, d) => (!b || d.realized_pnl_pct > b.realized_pnl_pct ? d : b), null)
  const worstDay = rows.reduce<any>((b, d) => (!b || d.realized_pnl_pct < b.realized_pnl_pct ? d : b), null)

  const hasData = rows.length > 0

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-semibold text-gray-100">PnL Analytics</h1>
          <p className="text-sm text-gray-500 mt-0.5">Realized performance history</p>
        </div>
        <div className="flex items-center gap-1.5">
          {LOOKBACK_OPTIONS.map(({ label, value }) => (
            <button
              key={value}
              onClick={() => setDays(value)}
              className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                days === value
                  ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30'
                  : 'text-gray-400 hover:text-gray-100 hover:bg-gray-800 border border-transparent'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {!hasData && !isLoading && (
        <div className="bg-gray-900 border border-dashed border-gray-700 rounded-xl p-10 text-center text-gray-500 text-sm">
          No PnL snapshots yet. Run the <span className="text-gray-300">daily_reset</span> and{' '}
          <span className="text-gray-300">trading_brain</span> scheduler jobs to start recording daily performance.
        </div>
      )}

      {hasData && (
        <>
          {/* KPI row */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              label={`Total PnL (${days}d)`}
              value={`${totalPnlPct >= 0 ? '+' : ''}${totalPnlPct.toFixed(2)}%`}
              sub={`$${totalPnl.toFixed(0)}`}
              trend={totalPnlPct >= 0 ? 'up' : 'down'}
            />
            <StatCard
              label="Trade Win Rate"
              value={winRate != null ? `${winRate.toFixed(1)}%` : '—'}
              sub={`${totalWins}W / ${totalLosses}L of ${totalTrades} trades`}
              trend={winRate != null ? (winRate >= 50 ? 'up' : 'down') : undefined}
            />
            <StatCard
              label="Day Win Rate"
              value={dayWinRate != null ? `${dayWinRate.toFixed(0)}%` : '—'}
              sub={`${winDays} green / ${lossDays} red days`}
              trend={dayWinRate != null ? (dayWinRate >= 50 ? 'up' : 'down') : undefined}
            />
            <StatCard
              label="Max Drawdown"
              value={`-${(maxDrawdown * 100).toFixed(2)}%`}
              sub="worst single day"
              trend="down"
            />
          </div>

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              label="Best Day"
              value={bestDay ? `+${(bestDay.realized_pnl_pct * 100).toFixed(2)}%` : '—'}
              sub={bestDay?.date ?? ''}
              trend="up"
            />
            <StatCard
              label="Worst Day"
              value={worstDay ? `${(worstDay.realized_pnl_pct * 100).toFixed(2)}%` : '—'}
              sub={worstDay?.date ?? ''}
              trend="down"
            />
            <StatCard
              label="Total Trades"
              value={totalTrades}
              sub={`avg ${rows.length > 0 ? (totalTrades / rows.length).toFixed(1) : 0}/day`}
            />
            <StatCard
              label="Days Tracked"
              value={rows.length}
              sub={`of last ${days} days`}
            />
          </div>

          {/* Equity curve */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
            <h2 className="font-medium text-gray-100 mb-4">Cumulative Return</h2>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={equityData}>
                <XAxis
                  dataKey="date"
                  tick={{ fill: '#6b7280', fontSize: 10 }}
                  tickFormatter={v => v.slice(5)}
                />
                <YAxis
                  tick={{ fill: '#6b7280', fontSize: 10 }}
                  tickFormatter={v => `${v}%`}
                />
                <Tooltip
                  contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 8 }}
                  labelStyle={{ color: '#9ca3af' }}
                  formatter={(v: number) => [`${v > 0 ? '+' : ''}${v}%`, 'Cumulative']}
                />
                <ReferenceLine y={0} stroke="#374151" strokeDasharray="3 3" />
                <Line
                  type="monotone"
                  dataKey="equity"
                  stroke="#eab308"
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Daily bar chart */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
            <h2 className="font-medium text-gray-100 mb-4">Daily PnL</h2>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={barData}>
                <XAxis
                  dataKey="date"
                  tick={{ fill: '#6b7280', fontSize: 10 }}
                  tickFormatter={v => v.slice(5)}
                />
                <YAxis
                  tick={{ fill: '#6b7280', fontSize: 10 }}
                  tickFormatter={v => `${v}%`}
                />
                <Tooltip
                  contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 8 }}
                  labelStyle={{ color: '#9ca3af' }}
                  formatter={(v: number, _name: string, p: any) => [
                    `${v > 0 ? '+' : ''}${v}% ($${p.payload.pnl})`,
                    'Daily PnL',
                  ]}
                />
                <ReferenceLine y={0} stroke="#374151" />
                <Bar dataKey="pnl_pct" radius={[2, 2, 0, 0]}>
                  {barData.map((entry, i) => (
                    <Cell key={i} fill={entry.pnl_pct >= 0 ? '#22c55e' : '#ef4444'} fillOpacity={0.75} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Per-day table */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-800">
              <h2 className="font-medium text-gray-100">Daily Breakdown</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-xs text-gray-500 border-b border-gray-800">
                    <th className="text-left px-5 py-2.5">Date</th>
                    <th className="text-right px-5 py-2.5">PnL %</th>
                    <th className="text-right px-5 py-2.5">PnL $</th>
                    <th className="text-right px-5 py-2.5">Trades</th>
                    <th className="text-right px-5 py-2.5">W / L</th>
                    <th className="text-right px-5 py-2.5">Win %</th>
                    <th className="text-right px-5 py-2.5">Max DD</th>
                    <th className="text-right px-5 py-2.5">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {[...rows].reverse().map((d: any) => {
                    const pct = d.realized_pnl_pct * 100
                    const wr = d.trade_count > 0 ? (d.win_count / d.trade_count) * 100 : null
                    return (
                      <tr key={d.id} className="hover:bg-gray-800/30">
                        <td className="px-5 py-3 font-mono text-gray-400 text-xs">{d.date}</td>
                        <td className={`px-5 py-3 text-right font-mono font-semibold ${pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {pct >= 0 ? '+' : ''}{pct.toFixed(3)}%
                        </td>
                        <td className={`px-5 py-3 text-right font-mono ${d.realized_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {d.realized_pnl >= 0 ? '+' : ''}${d.realized_pnl.toFixed(2)}
                        </td>
                        <td className="px-5 py-3 text-right text-gray-400">{d.trade_count}</td>
                        <td className="px-5 py-3 text-right text-gray-400">
                          <span className="text-green-400">{d.win_count}</span>
                          <span className="text-gray-600"> / </span>
                          <span className="text-red-400">{d.loss_count}</span>
                        </td>
                        <td className="px-5 py-3 text-right text-gray-400">
                          {wr != null ? `${wr.toFixed(0)}%` : '—'}
                        </td>
                        <td className="px-5 py-3 text-right font-mono text-gray-500 text-xs">
                          -{(d.max_drawdown * 100).toFixed(2)}%
                        </td>
                        <td className="px-5 py-3 text-right">
                          {d.trading_blocked ? (
                            <Badge variant="red" size="xs">BLOCKED</Badge>
                          ) : (
                            <Badge variant="green" size="xs">OK</Badge>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
