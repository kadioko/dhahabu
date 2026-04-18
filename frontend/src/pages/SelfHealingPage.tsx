import { useQuery } from '@tanstack/react-query'
import {
  fetchBacktestRuns,
  fetchWalkForwardRuns,
  fetchMonteCarloRuns,
  fetchOverfitFlags,
  fetchPromotions,
} from '../lib/api'
import { Badge } from '../components/Badge'
import { format } from 'date-fns'
import clsx from 'clsx'

// Visual flow node component
function FlowNode({
  label,
  status,
  count,
  active,
}: {
  label: string
  status?: 'pass' | 'fail' | 'running' | null
  count?: number
  active?: boolean
}) {
  return (
    <div
      className={clsx(
        'rounded-lg border px-4 py-3 text-center text-xs font-medium transition-colors min-w-[110px]',
        active ? 'border-yellow-500/60 bg-yellow-500/10 text-yellow-300' :
        status === 'pass' ? 'border-green-500/40 bg-green-500/5 text-green-400' :
        status === 'fail' ? 'border-red-500/40 bg-red-500/5 text-red-400' :
        'border-gray-700 bg-gray-900 text-gray-400'
      )}
    >
      <div>{label}</div>
      {count != null && (
        <div className="text-[10px] mt-0.5 opacity-60">{count} runs</div>
      )}
    </div>
  )
}

function Arrow({ label }: { label?: string }) {
  return (
    <div className="flex flex-col items-center gap-0.5 text-gray-700 px-1">
      <div className="text-[10px] text-gray-600">{label}</div>
      <div className="text-base">↓</div>
    </div>
  )
}

function DiamondDecision({
  label,
  yesLabel,
  noLabel,
}: {
  label: string
  yesLabel: string
  noLabel: string
}) {
  return (
    <div className="flex flex-col items-center">
      <div className="border border-yellow-500/40 bg-yellow-500/5 text-yellow-400 rounded-lg px-4 py-2 text-xs font-semibold text-center rotate-0">
        ◆ {label}?
      </div>
      <div className="flex items-start gap-8 mt-0 relative">
        <div className="flex flex-col items-center">
          <div className="text-gray-700 text-sm mt-1">↙</div>
          <div className="text-[10px] text-red-400 mt-0.5">YES → {yesLabel}</div>
        </div>
        <div className="flex flex-col items-center">
          <div className="text-gray-700 text-sm mt-1">↘</div>
          <div className="text-[10px] text-green-400 mt-0.5">NO → {noLabel}</div>
        </div>
      </div>
    </div>
  )
}

const STRATEGIES = ['liquidity_sweeps', 'trend_continuation', 'breakout_expansion', 'ema_momentum']

export function SelfHealingPage() {
  const { data: backtests } = useQuery({ queryKey: ['backtests'], queryFn: () => fetchBacktestRuns({ days: 7 }) })
  const { data: wfRuns } = useQuery({ queryKey: ['wf-runs'], queryFn: () => fetchWalkForwardRuns({ days: 7 }) })
  const { data: mcRuns } = useQuery({ queryKey: ['mc-runs'], queryFn: () => fetchMonteCarloRuns({ days: 7 }) })
  const { data: overfitData } = useQuery({ queryKey: ['overfit-flags'], queryFn: fetchOverfitFlags })
  const { data: promos } = useQuery({ queryKey: ['promotions'], queryFn: fetchPromotions })

  const passedWF = wfRuns?.filter((r: any) => !r.overfit_flag).length ?? 0
  const failedWF = wfRuns?.filter((r: any) => r.overfit_flag).length ?? 0
  const passedMC = mcRuns?.filter((r: any) => r.pass_flag).length ?? 0
  const failedMC = mcRuns?.filter((r: any) => !r.pass_flag).length ?? 0

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-100">Self-Healing Engine</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          Automated validation, overfit detection, and parameter lifecycle management
        </p>
      </div>

      {/* Engine Flow Diagram */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
        <h2 className="font-medium text-gray-100 mb-6">Engine Flow</h2>

        <div className="flex gap-12 overflow-x-auto pb-4">
          {/* BACKTEST LOOP */}
          <div className="flex flex-col items-center gap-2 min-w-[140px]">
            <div className="text-xs text-yellow-400 font-semibold uppercase tracking-widest mb-2">
              Backtest Loop (4h)
            </div>
            <FlowNode label="Every 4h" active />
            <Arrow />
            <FlowNode label="Re-Backtest" count={backtests?.length ?? 0} status="pass" />
            <Arrow />
            <FlowNode label="Walk-Forward" count={wfRuns?.length ?? 0} status={failedWF > 0 ? 'fail' : 'pass'} />
            <Arrow />
            <DiamondDecision label="Overfit" yesLabel="Flag Overfitted" noLabel="Continue" />
            <div className="mt-2 flex gap-2">
              <div className="bg-red-500/10 border border-red-500/20 rounded px-2 py-1 text-[10px] text-red-400">
                Flag Overfitted ({failedWF})
              </div>
              <div className="bg-green-500/10 border border-green-500/20 rounded px-2 py-1 text-[10px] text-green-400">
                Continue ({passedWF})
              </div>
            </div>
          </div>

          {/* Divider */}
          <div className="w-px bg-gray-800 self-stretch" />

          {/* OPTIMIZE LOOP */}
          <div className="flex flex-col items-center gap-2 min-w-[140px]">
            <div className="text-xs text-blue-400 font-semibold uppercase tracking-widest mb-2">
              Optimize Loop (6h)
            </div>
            <FlowNode label="Every 6h" active />
            <Arrow />
            <FlowNode label="Parameter Search" status="pass" />
            <Arrow />
            <FlowNode label="Monte Carlo" count={mcRuns?.length ?? 0} status={failedMC > 0 ? 'fail' : 'pass'} />
            <Arrow />
            <DiamondDecision label="Random wins" yesLabel="Throw Away" noLabel="Promote Live" />
            <div className="mt-2 flex gap-2">
              <div className="bg-red-500/10 border border-red-500/20 rounded px-2 py-1 text-[10px] text-red-400">
                Throw Away ({failedMC})
              </div>
              <div className="bg-green-500/10 border border-green-500/20 rounded px-2 py-1 text-[10px] text-green-400">
                Promote Live ({passedMC})
              </div>
            </div>
          </div>

          {/* Divider */}
          <div className="w-px bg-gray-800 self-stretch" />

          {/* CIRCUIT BREAKER */}
          <div className="flex flex-col items-center gap-2 min-w-[140px]">
            <div className="text-xs text-red-400 font-semibold uppercase tracking-widest mb-2">
              Circuit Breaker (always on)
            </div>
            <FlowNode label="Loss Monitor" active />
            <Arrow />
            <FlowNode label="Track SL hits" />
            <Arrow />
            <DiamondDecision label="8 stops in a row" yesLabel="24h Shutdown" noLabel="Keep watching" />
            <div className="mt-2 flex gap-2">
              <div className="bg-red-900/30 border border-red-500/30 rounded px-2 py-1 text-[10px] text-red-400">
                🚨 24h Shutdown
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Per-strategy status */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {STRATEGIES.map(strategy => {
          const btList = backtests?.filter((b: any) => b.strategy_name === strategy) ?? []
          const wfList = wfRuns?.filter((w: any) => w.strategy_name === strategy) ?? []
          const mcList = mcRuns?.filter((m: any) => m.strategy_name === strategy) ?? []
          const isOverfit = overfitData?.overfit_sets?.some((o: any) => o.strategy_name === strategy)
          const latestBT = btList[0]
          const latestWF = wfList[0]
          const latestMC = mcList[0]

          return (
            <div key={strategy} className="bg-gray-900 border border-gray-800 rounded-xl p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-medium text-gray-200 capitalize">
                  {strategy.replace(/_/g, ' ')}
                </h3>
                {isOverfit ? (
                  <Badge variant="red">⚠ OVERFIT</Badge>
                ) : (
                  <Badge variant="green">✓ CLEAN</Badge>
                )}
              </div>

              <div className="space-y-2 text-xs">
                {/* Latest backtest */}
                <div className="flex items-center justify-between bg-gray-800/50 rounded px-3 py-2">
                  <span className="text-gray-500">Latest Backtest</span>
                  {latestBT ? (
                    <div className="text-right">
                      <span className="text-gray-300 font-mono">
                        PF: {latestBT.profit_factor?.toFixed(2) ?? '—'}
                      </span>
                      <span className="text-gray-500 ml-2">
                        WR: {latestBT.win_rate != null ? `${(latestBT.win_rate * 100).toFixed(0)}%` : '—'}
                      </span>
                    </div>
                  ) : (
                    <span className="text-gray-600">No data</span>
                  )}
                </div>

                {/* Walk-forward */}
                <div className="flex items-center justify-between bg-gray-800/50 rounded px-3 py-2">
                  <span className="text-gray-500">Walk-Forward</span>
                  {latestWF ? (
                    <div className="flex items-center gap-2">
                      {latestWF.overfit_flag ? (
                        <Badge variant="red" size="xs">OVERFIT</Badge>
                      ) : (
                        <Badge variant="green" size="xs">PASS</Badge>
                      )}
                      <span className="text-gray-500">
                        OOS: {latestWF.oos_degradation_score?.toFixed(3) ?? '—'}
                      </span>
                    </div>
                  ) : (
                    <span className="text-gray-600">No data</span>
                  )}
                </div>

                {/* Monte Carlo */}
                <div className="flex items-center justify-between bg-gray-800/50 rounded px-3 py-2">
                  <span className="text-gray-500">Monte Carlo</span>
                  {latestMC ? (
                    <div className="flex items-center gap-2">
                      {latestMC.pass_flag ? (
                        <Badge variant="green" size="xs">PASS</Badge>
                      ) : (
                        <Badge variant="red" size="xs">FAIL</Badge>
                      )}
                      <span className="text-gray-500">
                        Robustness: {(latestMC.robustness_score * 100).toFixed(0)}%
                      </span>
                    </div>
                  ) : (
                    <span className="text-gray-600">No data</span>
                  )}
                </div>
              </div>
            </div>
          )
        })}
      </div>

      {/* Promotion History */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-gray-900 border border-gray-800 rounded-xl">
          <div className="px-5 py-4 border-b border-gray-800">
            <h2 className="font-medium text-gray-100">
              ✅ Promote Live History
            </h2>
          </div>
          <div className="divide-y divide-gray-800">
            {(!promos?.promoted || promos.promoted.length === 0) && (
              <div className="px-5 py-6 text-center text-gray-600 text-sm">No promotions yet</div>
            )}
            {promos?.promoted?.map((p: any) => (
              <div key={p.id} className="px-5 py-3 flex items-center justify-between">
                <div>
                  <div className="text-sm text-gray-200 capitalize">
                    {p.strategy_name.replace(/_/g, ' ')}
                  </div>
                  <div className="text-xs text-gray-500">
                    Score: {p.score?.toFixed(3) ?? '—'}
                  </div>
                </div>
                <div className="text-xs text-gray-500">
                  {p.promoted_at ? format(new Date(p.promoted_at), 'MMM d HH:mm') : '—'}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-xl">
          <div className="px-5 py-4 border-b border-gray-800">
            <h2 className="font-medium text-gray-100">
              🗑️ Throw Away History
            </h2>
          </div>
          <div className="divide-y divide-gray-800">
            {(!promos?.discarded || promos.discarded.length === 0) && (
              <div className="px-5 py-6 text-center text-gray-600 text-sm">No discards yet</div>
            )}
            {promos?.discarded?.map((p: any) => (
              <div key={p.id} className="px-5 py-3 flex items-center justify-between">
                <div>
                  <div className="text-sm text-gray-200 capitalize">
                    {p.strategy_name.replace(/_/g, ' ')}
                  </div>
                  <div className="text-xs text-gray-500 max-w-[200px] truncate">
                    {p.discard_reason}
                  </div>
                </div>
                <div className="text-xs text-gray-500">
                  {p.discarded_at ? format(new Date(p.discarded_at), 'MMM d HH:mm') : '—'}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
