import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchSchedulerJobs, fetchSystemOverview, fetchSystemState, triggerSchedulerJob } from '../lib/api'
import { Badge, statusBadge } from '../components/Badge'
import { formatDistanceToNow } from 'date-fns'

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

const MANUAL_JOBS = [
  { jobName: 'market_data_ingest', label: 'Run market ingest' },
  { jobName: 'health_check', label: 'Run health check' },
  { jobName: 'trading_brain', label: 'Run trading brain' },
  { jobName: 'self_healing_backtest', label: 'Run self-healing' },
]

export function SchedulerPage() {
  const queryClient = useQueryClient()
  const { data: jobs } = useQuery({ queryKey: ['scheduler-jobs'], queryFn: fetchSchedulerJobs })
  const { data: components } = useQuery({ queryKey: ['system-state'], queryFn: fetchSystemState })
  const { data: overview } = useQuery({ queryKey: ['system-overview'], queryFn: fetchSystemOverview })

  const triggerJob = useMutation({
    mutationFn: triggerSchedulerJob,
    onSuccess: async () => {
      // Small delay to let the background job write its initial DB record
      await new Promise(r => setTimeout(r, 1500))
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['scheduler-jobs'] }),
        queryClient.invalidateQueries({ queryKey: ['system-state'] }),
        queryClient.invalidateQueries({ queryKey: ['system-overview'] }),
      ])
    },
  })

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-xl font-semibold text-gray-100">Scheduler Health</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <div className="text-xs uppercase tracking-widest text-gray-500 mb-2">Latest Candle</div>
          <div className="text-sm text-gray-100">
            {overview?.latest_candle_at ? formatDistanceToNow(new Date(overview.latest_candle_at), { addSuffix: true }) : 'No candles yet'}
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {Object.entries(overview?.candle_counts ?? {}).map(([tf, count]) => `${tf}: ${count}`).join(' · ') || 'No timeframe counts yet'}
          </div>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <div className="text-xs uppercase tracking-widest text-gray-500 mb-2">Latest Success</div>
          <div className="text-sm text-gray-100">{overview?.latest_successful_job?.job_name ?? 'No successful jobs yet'}</div>
          <div className="text-xs text-gray-500 mt-1">
            {overview?.latest_successful_job?.started_at ? formatDistanceToNow(new Date(overview.latest_successful_job.started_at), { addSuffix: true }) : 'Waiting for first completed run'}
          </div>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <div className="text-xs uppercase tracking-widest text-gray-500 mb-2">Market Data Run</div>
          <div className="text-sm text-gray-100">{overview?.latest_market_data_run?.status ?? 'Not run yet'}</div>
          <div className="text-xs text-gray-500 mt-1">
            {overview?.latest_market_data_run?.started_at ? formatDistanceToNow(new Date(overview.latest_market_data_run.started_at), { addSuffix: true }) : 'Run market ingest to seed data'}
          </div>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <div className="text-xs uppercase tracking-widest text-gray-500 mb-2">Tracked Components</div>
          <div className="text-sm text-gray-100">{overview?.component_count ?? 0}</div>
          <div className="text-xs text-gray-500 mt-1">System state rows currently persisted</div>
        </div>
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <h2 className="font-medium text-gray-100">Manual Admin Triggers</h2>
            <div className="text-sm text-gray-500 mt-1">Use these to validate the production pipeline without waiting for the next interval.</div>
          </div>
          {triggerJob.isSuccess && <Badge variant="green">Job started</Badge>}
          {triggerJob.isError && <Badge variant="red">Trigger failed</Badge>}
        </div>
        <div className="flex flex-wrap gap-2">
          {MANUAL_JOBS.map(({ jobName, label }) => (
            <button
              key={jobName}
              onClick={() => triggerJob.mutate(jobName)}
              disabled={triggerJob.isPending}
              className="px-3 py-2 rounded-lg border border-gray-700 text-sm text-gray-200 hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {triggerJob.isPending && triggerJob.variables === jobName ? 'Running...' : label}
            </button>
          ))}
        </div>
      </div>

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
                {!!j.details_json && (
                  <div className="text-xs text-gray-500 mt-2 font-mono">
                    {j.details_json.result && 'Latest result captured'}
                    {typeof j.details_json.duration_seconds === 'number' && ` · ${j.details_json.duration_seconds.toFixed(1)}s`}
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
                  {typeof c.metadata_json?.duration_seconds === 'number' && (
                    <div className="text-xs text-gray-500 mt-0.5">
                      Last duration {c.metadata_json.duration_seconds.toFixed(1)}s
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
