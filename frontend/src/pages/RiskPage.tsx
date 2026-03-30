import { useQuery } from '@tanstack/react-query'
import { fetchRiskState, fetchDailyPnL } from '../lib/api'

const CONSECUTIVE_SL_LIMIT = 8
import { StatCard } from '../components/StatCard'
import { Badge } from '../components/Badge'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { format } from 'date-fns'

export function RiskPage() {
  const { data: risk } = useQuery({ queryKey: ['risk'], queryFn: fetchRiskState })
  const { data: pnlHistory } = useQuery({ queryKey: ['pnl-history'], queryFn: () => fetchDailyPnL(30) })

  const pnlData = Array.isArray(pnlHistory)
    ? [...pnlHistory].reverse().map((d: any) => ({
        date: d.date,
        pnl_pct: +(d.realized_pnl_pct * 100).toFixed(3),
        pnl: +d.realized_pnl.toFixed(2),
      }))
    : []

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-100">Risk Monitor</h1>
        {risk?.can_trade ? (
          <Badge variant="green">Trading Active</Badge>
        ) : (
          <Badge variant="red">Trading Blocked</Badge>
        )}
      </div>

      {/* Shutdown banner */}
      {risk?.shutdown_active && (
        <div className="bg-red-950/40 border border-red-500/30 rounded-xl p-5">
          <div className="flex items-center gap-3 mb-2">
            <span className="text-2xl">🚨</span>
            <span className="text-red-400 font-bold text-lg">24H SHUTDOWN ACTIVE</span>
          </div>
          <div className="text-red-400/70 text-sm">{risk.shutdown_reason}</div>
          {risk.shutdown_ends_at && (
            <div className="mt-2 text-sm">
              <span className="text-gray-500">Resumes: </span>
              <span className="text-gray-200 font-mono">
                {format(new Date(risk.shutdown_ends_at), 'yyyy-MM-dd HH:mm UTC')}
              </span>
              {risk.shutdown_cooldown_remaining_hours != null && (
                <span className="text-gray-500 ml-2">
                  ({risk.shutdown_cooldown_remaining_hours.toFixed(1)}h remaining)
                </span>
              )}
            </div>
          )}
        </div>
      )}

      {/* Block reason */}
      {!risk?.can_trade && !risk?.shutdown_active && (
        <div className="bg-orange-950/30 border border-orange-500/20 rounded-xl p-4">
          <span className="text-orange-400 font-medium">Trading Blocked: </span>
          <span className="text-orange-400/70 text-sm">{risk?.block_reason}</span>
        </div>
      )}

      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Daily PnL"
          value={`${(risk?.daily_realized_pnl ?? 0) >= 0 ? '+' : ''}${((risk?.daily_realized_pnl_pct ?? 0) * 100).toFixed(2)}%`}
          sub={`$${(risk?.daily_realized_pnl ?? 0).toFixed(0)}`}
          trend={(risk?.daily_realized_pnl ?? 0) >= 0 ? 'up' : 'down'}
          urgent={risk?.daily_loss_cap_hit}
        />
        <StatCard
          label="Consecutive SL"
          value={risk?.consecutive_sl_hits ?? 0}
          sub={`of ${CONSECUTIVE_SL_LIMIT} max`}
          urgent={(risk?.consecutive_sl_hits ?? 0) >= CONSECUTIVE_SL_LIMIT - 2}
        />
        <StatCard
          label="Open Exposure"
          value={`${((risk?.estimated_open_exposure_pct ?? 0) * 100).toFixed(2)}%`}
          sub={`${risk?.open_trade_count ?? 0} trades`}
        />
        <StatCard
          label="Direction Split"
          value={`${risk?.open_trades_long ?? 0}L / ${risk?.open_trades_short ?? 0}S`}
          sub="long / short"
        />
      </div>

      {/* Circuit breaker progress bar */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-medium text-gray-200">Consecutive Stop-Loss Monitor</h2>
          <span className="text-sm text-gray-400 font-mono">
            {risk?.consecutive_sl_hits ?? 0} / {CONSECUTIVE_SL_LIMIT}
          </span>
        </div>
        <div className="h-3 bg-gray-800 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${
              (risk?.consecutive_sl_hits ?? 0) >= CONSECUTIVE_SL_LIMIT - 1
                ? 'bg-red-500'
                : (risk?.consecutive_sl_hits ?? 0) >= CONSECUTIVE_SL_LIMIT - 3
                ? 'bg-orange-500'
                : 'bg-yellow-500'
            }`}
            style={{ width: `${Math.min(((risk?.consecutive_sl_hits ?? 0) / CONSECUTIVE_SL_LIMIT) * 100, 100)}%` }}
          />
        </div>
        <div className="flex justify-between text-xs text-gray-600 mt-1">
          <span>0</span>
          <span>{Math.floor(CONSECUTIVE_SL_LIMIT / 2)}</span>
          <span>{CONSECUTIVE_SL_LIMIT} → SHUTDOWN</span>
        </div>
      </div>

      {/* Daily PnL Chart */}
      {pnlData.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <h2 className="font-medium text-gray-100 mb-4">Daily PnL (30 Days)</h2>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={pnlData}>
              <XAxis
                dataKey="date"
                tick={{ fill: '#6b7280', fontSize: 10 }}
                tickFormatter={v => v.slice(5)}
              />
              <YAxis tick={{ fill: '#6b7280', fontSize: 10 }} tickFormatter={v => `${v}%`} />
              <Tooltip
                contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 8 }}
                labelStyle={{ color: '#9ca3af' }}
                formatter={(v: number) => [`${v}%`, 'Daily PnL']}
              />
              <Area
                type="monotone"
                dataKey="pnl_pct"
                stroke="#eab308"
                fill="#eab308"
                fillOpacity={0.1}
                strokeWidth={2}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
