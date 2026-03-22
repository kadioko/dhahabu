import { useQuery } from '@tanstack/react-query'
import { fetchSchedulerJobs, fetchSystemState } from '../lib/api'
import { Badge, statusBadge } from '../components/Badge'
import { format, formatDistanceToNow } from 'date-fns'

const JOB_DESCRIPTIONS: Record<string, string> = {
  market_data_ingest: 'Fetches XAUUSD candles from Twelve Data',
  trading_brain: 'Central decision pipeline — generates and approves signals',
  trade_reconcile: 'Updates open trade states against latest candles',
  self_healing_backtest: 'Re-backtest + walk-forward + overfit detection',
  param_search_monte_carlo: 'Parameter optimization + Monte Carlo robustness',
  risk_monitor: 'Checks consecutive losses and daily cap',
  daily_reset: 'Creates new daily PnL snapshot at midnight UTC',
  health_check: 'Updates system component health states',
  dashboard_refresh: 'Pre-computes dashboard cache',
}

export function SchedulerPage() {
  const { data: jobs } = useQuery({ queryKey: ['scheduler-jobs'], queryFn: fetchSchedulerJobs })
  const { data: components } = useQuery({ queryKey: ['system-state'], queryFn: fetchSystemState })

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-xl font-semibold text-gray-100">Scheduler Health</h1>

      {/* Scheduler jobs */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl">
        <div className="px-5 py-4 border-b border-gray-800">
          <h2 className="font-medium text-gray-100">Active Jobs (last run)</h2>
        </div>
        <div className="divide-y divide-gray-800">
          {(!jobs?.jobs || jobs.jobs.length === 0) && (
            <div className="px-5 py-8 text-center text-gray-600 text-sm">
              No job runs recorded yet
            </div>
          )}
          {jobs?.jobs?.map((j: any) => (
            <div key={j.job_name} className="px-5 py-4 flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-sm font-medium text-gray-200 font-mono">
                    {j.job_name}
                  </span>
                  {statusBadge(j.status)}
                </div>
                <div className="text-xs text-gray-500">
                  {JOB_DESCRIPTIONS[j.job_name] ?? ''}
                </div>
                {j.error_message && (
                  <div className="text-xs text-red-400/70 mt-1 font-mono bg-red-900/20 px-2 py-1 rounded max-w-lg truncate">
                    {j.error_message}
                  </div>
                )}
              </div>
              <div className="text-right ml-4 shrink-0">
                <div className="text-xs text-gray-400">
                  {j.started_at ? formatDistanceToNow(new Date(j.started_at), { addSuffix: true }) : '—'}
                </div>
                {j.finished_at && j.started_at && (
                  <div className="text-xs text-gray-600 mt-0.5">
                    {((new Date(j.finished_at).getTime() - new Date(j.started_at).getTime()) / 1000).toFixed(1)}s
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* System component health */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl">
        <div className="px-5 py-4 border-b border-gray-800">
          <h2 className="font-medium text-gray-100">Service Health</h2>
        </div>
        <div className="divide-y divide-gray-800">
          {(!components || components.length === 0) && (
            <div className="px-5 py-8 text-center text-gray-600 text-sm">
              No component health data yet
            </div>
          )}
          {components?.map(c => (
            <div key={c.id} className="px-5 py-3 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div
                  className={`w-2 h-2 rounded-full flex-shrink-0 ${
                    c.status === 'healthy' ? 'bg-green-400' :
                    c.status === 'degraded' ? 'bg-yellow-400' :
                    c.status === 'down' ? 'bg-red-400' :
                    'bg-gray-600'
                  }`}
                />
                <div>
                  <div className="text-sm text-gray-200 font-mono">{c.component_name}</div>
                  {c.last_error && (
                    <div className="text-xs text-red-400/60 mt-0.5 max-w-sm truncate">
                      {c.last_error}
                    </div>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-3">
                {c.health_score != null && (
                  <div className="text-xs text-gray-500 font-mono">
                    {(c.health_score * 100).toFixed(0)}%
                  </div>
                )}
                {statusBadge(c.status)}
                {c.last_run_at && (
                  <div className="text-xs text-gray-600">
                    {formatDistanceToNow(new Date(c.last_run_at), { addSuffix: true })}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
