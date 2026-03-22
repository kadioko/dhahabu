import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchSignals } from '../lib/api'
import { Badge, directionBadge, statusBadge } from '../components/Badge'
import { format } from 'date-fns'

const STRATEGIES = ['all', 'liquidity_sweeps', 'trend_continuation', 'breakout_expansion', 'ema_momentum']

export function SignalsPage() {
  const [stratFilter, setStratFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')

  const { data: signals, isLoading } = useQuery({
    queryKey: ['signals', stratFilter, statusFilter],
    queryFn: () => fetchSignals({
      hours: 48,
      limit: 100,
      ...(stratFilter !== 'all' ? { strategy_name: stratFilter } : {}),
      ...(statusFilter !== 'all' ? { approval_status: statusFilter } : {}),
    }),
  })

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-100">Signals</h1>
        <Badge variant="yellow">{signals?.length ?? 0} signals</Badge>
      </div>

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <div className="flex gap-1.5">
          {STRATEGIES.map(s => (
            <button
              key={s}
              onClick={() => setStratFilter(s)}
              className={`px-3 py-1.5 rounded text-xs font-medium transition-colors border ${
                stratFilter === s
                  ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20'
                  : 'text-gray-400 border-gray-700 hover:border-gray-600'
              }`}
            >
              {s === 'all' ? 'All' : s.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
            </button>
          ))}
        </div>
        <div className="flex gap-1.5">
          {['all', 'approved', 'suppressed'].map(s => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`px-3 py-1.5 rounded text-xs font-medium transition-colors border ${
                statusFilter === s
                  ? 'bg-blue-500/10 text-blue-400 border-blue-500/20'
                  : 'text-gray-400 border-gray-700 hover:border-gray-600'
              }`}
            >
              {s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-gray-500 border-b border-gray-800 bg-gray-900/50">
                <th className="text-left px-5 py-3">Strategy</th>
                <th className="text-left px-5 py-3">Direction</th>
                <th className="text-left px-5 py-3">Entry</th>
                <th className="text-left px-5 py-3">SL</th>
                <th className="text-left px-5 py-3">TP</th>
                <th className="text-left px-5 py-3">R:R</th>
                <th className="text-left px-5 py-3">Conf</th>
                <th className="text-left px-5 py-3">Score</th>
                <th className="text-left px-5 py-3">Status</th>
                <th className="text-left px-5 py-3">Time</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {isLoading && (
                <tr><td colSpan={10} className="px-5 py-8 text-center text-gray-600">Loading...</td></tr>
              )}
              {!isLoading && (!signals || signals.length === 0) && (
                <tr><td colSpan={10} className="px-5 py-8 text-center text-gray-600">No signals found</td></tr>
              )}
              {signals?.map(s => {
                const riskMeta = s.risk_metadata_json as any
                const rr = riskMeta?.risk_reward ?? 0
                return (
                  <tr key={s.id} className="hover:bg-gray-800/30 transition-colors">
                    <td className="px-5 py-3 text-gray-300 capitalize text-xs">
                      {s.strategy_name.replace(/_/g, ' ')}
                    </td>
                    <td className="px-5 py-3">{directionBadge(s.direction)}</td>
                    <td className="px-5 py-3 font-mono text-gray-200">{s.entry.toFixed(2)}</td>
                    <td className="px-5 py-3 font-mono text-red-400">{s.stop_loss.toFixed(2)}</td>
                    <td className="px-5 py-3 font-mono text-green-400">{s.take_profit.toFixed(2)}</td>
                    <td className="px-5 py-3 font-mono text-gray-400">
                      {rr > 0 ? `1:${rr.toFixed(1)}` : '—'}
                    </td>
                    <td className="px-5 py-3 text-gray-400">
                      {(s.confidence * 100).toFixed(0)}%
                    </td>
                    <td className="px-5 py-3 font-mono text-yellow-400">
                      {s.brain_score?.toFixed(1) ?? '—'}
                    </td>
                    <td className="px-5 py-3">{statusBadge(s.approval_status)}</td>
                    <td className="px-5 py-3 text-gray-500 text-xs">
                      {format(new Date(s.created_at), 'MM-dd HH:mm')}
                    </td>
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
