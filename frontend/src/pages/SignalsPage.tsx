import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { format } from 'date-fns'
import { AlertTriangle, Filter } from 'lucide-react'
import { Badge, directionBadge, statusBadge } from '../components/Badge'
import { fetchSignals } from '../lib/api'

const STRATEGIES = ['all', 'liquidity_sweeps', 'trend_continuation', 'breakout_expansion', 'ema_momentum']

export function SignalsPage() {
  const [stratFilter, setStratFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')

  const { data: signals, isLoading, isError } = useQuery({
    queryKey: ['signals', stratFilter, statusFilter],
    queryFn: () =>
      fetchSignals({
        hours: 48,
        limit: 100,
        ...(stratFilter !== 'all' ? { strategy_name: stratFilter } : {}),
        ...(statusFilter !== 'all' ? { approval_status: statusFilter } : {}),
      }),
  })

  return (
    <div className="space-y-4 p-4 md:p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-100">Signals</h1>
          <p className="mt-1 text-sm text-slate-400">Review recent approvals, suppressions, confidence, and strategy quality in one grid.</p>
        </div>
        <Badge variant="yellow">{signals?.length ?? 0} signals</Badge>
      </div>

      <div className="rounded-[2rem] border border-white/10 bg-slate-950/75 p-4">
        <div className="mb-3 flex items-center gap-2 text-sm font-medium text-slate-200">
          <Filter className="h-4 w-4 text-amber-300" />
          Filters
        </div>
        <div className="flex flex-wrap gap-3">
          <div className="flex flex-wrap gap-1.5">
            {STRATEGIES.map((strategy) => (
              <button
                key={strategy}
                onClick={() => setStratFilter(strategy)}
                className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                  stratFilter === strategy
                    ? 'border-amber-500/20 bg-amber-500/10 text-amber-300'
                    : 'border-slate-700 text-slate-400 hover:border-slate-500 hover:text-slate-200'
                }`}
              >
                {strategy === 'all' ? 'All' : strategy.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())}
              </button>
            ))}
          </div>
          <div className="flex gap-1.5">
            {['all', 'approved', 'suppressed'].map((status) => (
              <button
                key={status}
                onClick={() => setStatusFilter(status)}
                className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                  statusFilter === status
                    ? 'border-cyan-500/20 bg-cyan-500/10 text-cyan-300'
                    : 'border-slate-700 text-slate-400 hover:border-slate-500 hover:text-slate-200'
                }`}
              >
                {status.charAt(0).toUpperCase() + status.slice(1)}
              </button>
            ))}
          </div>
        </div>
      </div>

      {isError && (
        <div className="flex items-center gap-2 rounded-2xl border border-red-500/20 bg-red-950/30 px-4 py-3 text-sm text-red-100">
          <AlertTriangle className="h-4 w-4" />
          Signal history could not be loaded right now.
        </div>
      )}

      <div className="overflow-hidden rounded-[2rem] border border-white/10 bg-slate-950/80">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/10 bg-slate-950/50 text-xs text-slate-500">
                <th className="px-5 py-3 text-left">Strategy</th>
                <th className="px-5 py-3 text-left">Direction</th>
                <th className="px-5 py-3 text-left">Entry</th>
                <th className="px-5 py-3 text-left">SL</th>
                <th className="px-5 py-3 text-left">TP</th>
                <th className="px-5 py-3 text-left">R:R</th>
                <th className="px-5 py-3 text-left">Conf</th>
                <th className="px-5 py-3 text-left">Score</th>
                <th className="px-5 py-3 text-left">Status</th>
                <th className="px-5 py-3 text-left">Time</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/10">
              {isLoading && (
                <tr>
                  <td colSpan={10} className="px-5 py-8 text-center text-slate-500">
                    Loading signal history...
                  </td>
                </tr>
              )}
              {!isLoading && (!signals || signals.length === 0) && (
                <tr>
                  <td colSpan={10} className="px-5 py-8 text-center text-slate-500">
                    No signals found for the current filters.
                  </td>
                </tr>
              )}
              {signals?.map((signal) => {
                const riskMeta = signal.risk_metadata_json as { risk_reward?: number } | null
                const rr = riskMeta?.risk_reward ?? 0
                return (
                  <tr key={signal.id} className="transition-colors hover:bg-white/5">
                    <td className="px-5 py-3 text-xs capitalize text-slate-300">{signal.strategy_name.replace(/_/g, ' ')}</td>
                    <td className="px-5 py-3">{directionBadge(signal.direction)}</td>
                    <td className="px-5 py-3 font-mono text-slate-200">{signal.entry.toFixed(2)}</td>
                    <td className="px-5 py-3 font-mono text-red-400">{signal.stop_loss.toFixed(2)}</td>
                    <td className="px-5 py-3 font-mono text-emerald-400">{signal.take_profit.toFixed(2)}</td>
                    <td className="px-5 py-3 font-mono text-slate-400">{rr > 0 ? `1:${rr.toFixed(1)}` : '—'}</td>
                    <td className="px-5 py-3 text-slate-400">{(signal.confidence * 100).toFixed(0)}%</td>
                    <td className="px-5 py-3 font-mono text-amber-300">{signal.brain_score?.toFixed(1) ?? '—'}</td>
                    <td className="px-5 py-3">{statusBadge(signal.approval_status)}</td>
                    <td className="px-5 py-3 text-xs text-slate-500">{format(new Date(signal.created_at), 'MM-dd HH:mm')}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
