import { useQuery } from '@tanstack/react-query'
import { fetchOpenTrades, fetchTradeHistory } from '../lib/api'
import { Badge, statusBadge } from '../components/Badge'
import { format } from 'date-fns'
import clsx from 'clsx'

export function TradesPage() {
  const { data: openTrades } = useQuery({ queryKey: ['trades-open'], queryFn: fetchOpenTrades })
  const { data: history } = useQuery({ queryKey: ['trades-history'], queryFn: () => fetchTradeHistory({ days: 30 }) })

  const totalPnL = history?.reduce((sum: number, t: any) => sum + (t.pnl ?? 0), 0) ?? 0

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-xl font-semibold text-gray-100">Trades</h1>

      {/* Open Trades */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl">
        <div className="px-5 py-4 border-b border-gray-800 flex items-center gap-3">
          <h2 className="font-medium text-gray-100">Open Trades</h2>
          <Badge variant="blue">{openTrades?.length ?? 0}</Badge>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-gray-500 border-b border-gray-800">
                <th className="text-left px-5 py-2">Status</th>
                <th className="text-left px-5 py-2">Entry</th>
                <th className="text-left px-5 py-2">SL</th>
                <th className="text-left px-5 py-2">TP</th>
                <th className="text-left px-5 py-2">Size (lots)</th>
                <th className="text-left px-5 py-2">Seq SL</th>
                <th className="text-left px-5 py-2">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {(!openTrades || openTrades.length === 0) && (
                <tr><td colSpan={7} className="px-5 py-8 text-center text-gray-600">No open trades</td></tr>
              )}
              {openTrades?.map(t => (
                <tr key={t.id} className="hover:bg-gray-800/30">
                  <td className="px-5 py-3">{statusBadge(t.status)}</td>
                  <td className="px-5 py-3 font-mono text-gray-200">{t.entry_price?.toFixed(2) ?? '—'}</td>
                  <td className="px-5 py-3 font-mono text-red-400">{t.stop_loss.toFixed(2)}</td>
                  <td className="px-5 py-3 font-mono text-green-400">{t.take_profit.toFixed(2)}</td>
                  <td className="px-5 py-3 font-mono text-gray-400">{t.position_size.toFixed(2)}</td>
                  <td className="px-5 py-3 text-gray-500">{t.consecutive_loss_seq_snapshot}</td>
                  <td className="px-5 py-3 text-gray-500 text-xs">{format(new Date(t.created_at), 'MM-dd HH:mm')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Trade History */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl">
        <div className="px-5 py-4 border-b border-gray-800 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h2 className="font-medium text-gray-100">Trade History (30d)</h2>
            <Badge variant="gray">{history?.length ?? 0} trades</Badge>
          </div>
          <div className={clsx(
            'font-bold font-mono text-lg',
            totalPnL >= 0 ? 'text-green-400' : 'text-red-400'
          )}>
            {totalPnL >= 0 ? '+' : ''}${totalPnL.toFixed(2)}
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-gray-500 border-b border-gray-800">
                <th className="text-left px-5 py-2">Result</th>
                <th className="text-left px-5 py-2">Entry</th>
                <th className="text-left px-5 py-2">Exit</th>
                <th className="text-left px-5 py-2">SL</th>
                <th className="text-left px-5 py-2">TP</th>
                <th className="text-left px-5 py-2">PnL</th>
                <th className="text-left px-5 py-2">PnL %</th>
                <th className="text-left px-5 py-2">Reason</th>
                <th className="text-left px-5 py-2">Exit Time</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {(!history || history.length === 0) && (
                <tr><td colSpan={9} className="px-5 py-8 text-center text-gray-600">No trade history</td></tr>
              )}
              {history?.map(t => (
                <tr key={t.id} className="hover:bg-gray-800/30">
                  <td className="px-5 py-3">{statusBadge(t.status)}</td>
                  <td className="px-5 py-3 font-mono text-gray-300">{t.entry_price?.toFixed(2) ?? '—'}</td>
                  <td className="px-5 py-3 font-mono text-gray-300">{t.exit_price?.toFixed(2) ?? '—'}</td>
                  <td className="px-5 py-3 font-mono text-red-400/70">{t.stop_loss.toFixed(2)}</td>
                  <td className="px-5 py-3 font-mono text-green-400/70">{t.take_profit.toFixed(2)}</td>
                  <td className={clsx(
                    'px-5 py-3 font-mono font-semibold',
                    (t.pnl ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'
                  )}>
                    {t.pnl != null ? `${t.pnl >= 0 ? '+' : ''}$${t.pnl.toFixed(2)}` : '—'}
                  </td>
                  <td className={clsx(
                    'px-5 py-3 font-mono',
                    (t.pnl_pct ?? 0) >= 0 ? 'text-green-400/70' : 'text-red-400/70'
                  )}>
                    {t.pnl_pct != null ? `${(t.pnl_pct * 100).toFixed(3)}%` : '—'}
                  </td>
                  <td className="px-5 py-3 text-gray-500 text-xs">{t.closed_reason ?? '—'}</td>
                  <td className="px-5 py-3 text-gray-500 text-xs">
                    {t.exit_time ? format(new Date(t.exit_time), 'MM-dd HH:mm') : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
