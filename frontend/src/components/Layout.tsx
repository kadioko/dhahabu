import { Link, Outlet, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import {
  Activity,
  BarChart3,
  BrainCircuit,
  CalendarClock,
  CandlestickChart,
  LayoutDashboard,
  Shield,
  Wallet,
} from 'lucide-react'
import { preloadRouteModules } from '../lib/route-modules'
import { fetchSystemOverview } from '../lib/api'

const NAV = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, preload: preloadRouteModules.dashboard },
  { to: '/chart', label: 'Chart', icon: CandlestickChart, preload: preloadRouteModules.chart },
  { to: '/signals', label: 'Signals', icon: Activity, preload: preloadRouteModules.signals },
  { to: '/trades', label: 'Trades', icon: BarChart3, preload: preloadRouteModules.trades },
  { to: '/pnl', label: 'PnL', icon: Wallet, preload: preloadRouteModules.pnl },
  { to: '/risk', label: 'Risk', icon: Shield, preload: preloadRouteModules.risk },
  { to: '/self-healing', label: 'Self-Healing', icon: BrainCircuit, preload: preloadRouteModules.selfHealing },
  { to: '/scheduler', label: 'Scheduler', icon: CalendarClock, preload: preloadRouteModules.scheduler },
]

export function Layout() {
  const { pathname } = useLocation()
  const { data: overview, isError, isLoading } = useQuery({
    queryKey: ['system-overview'],
    queryFn: fetchSystemOverview,
    staleTime: 30_000,
    retry: 1,
  })

  const statusDot = isError
    ? { color: 'bg-red-400', label: 'API offline' }
    : isLoading
    ? { color: 'bg-slate-500', label: 'Connecting' }
    : !overview?.latest_candle_at
    ? { color: 'bg-amber-400 animate-pulse', label: 'Warming up' }
    : { color: 'bg-emerald-400 animate-pulse', label: 'System online' }

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(245,158,11,0.18),_transparent_28%),linear-gradient(180deg,_#020617_0%,_#050816_45%,_#020617_100%)] text-slate-100 md:flex">
      <aside className="border-b border-white/10 bg-slate-950/75 backdrop-blur-xl md:min-h-screen md:w-72 md:flex-shrink-0 md:border-b-0 md:border-r">
        <div className="border-b border-white/10 px-6 py-5">
          <div className="text-xs uppercase tracking-[0.35em] text-amber-300/80">Dhahabu</div>
          <div className="mt-2 text-2xl font-semibold tracking-tight text-white">Gold command center</div>
          <div className="mt-1 text-sm text-slate-400">XAU/USD intelligence, validation, and execution oversight</div>
        </div>

        <nav className="grid gap-1 overflow-x-auto px-3 py-4 md:flex-1">
          {NAV.map(({ to, label, icon: Icon, preload }) => {
            const active = to === '/' ? pathname === '/' : pathname.startsWith(to)
            return (
              <Link
                key={to}
                to={to}
                onMouseEnter={() => void preload()}
                onFocus={() => void preload()}
                className={clsx(
                  'flex items-center gap-3 rounded-2xl px-3 py-3 text-sm font-medium transition-all',
                  active
                    ? 'border border-amber-400/30 bg-amber-400/10 text-amber-200 shadow-[0_0_0_1px_rgba(251,191,36,0.05)]'
                    : 'border border-transparent text-slate-400 hover:border-white/10 hover:bg-white/5 hover:text-slate-100'
                )}
              >
                <span className={clsx('inline-flex h-9 w-9 items-center justify-center rounded-xl', active ? 'bg-amber-300/10' : 'bg-white/5')}>
                  <Icon className="h-4 w-4" />
                </span>
                {label}
              </Link>
            )
          })}
        </nav>

        <div className="border-t border-white/10 px-6 py-4">
          <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
            <div className="flex items-center gap-2 text-xs uppercase tracking-[0.25em] text-slate-500">
              <div className={clsx('h-2 w-2 flex-shrink-0 rounded-full', statusDot.color)} />
              {statusDot.label}
            </div>
            <div className="mt-2 text-sm text-slate-300">
              {overview?.latest_successful_job?.job_name?.replace(/_/g, ' ') ?? 'Waiting for scheduler activity'}
            </div>
          </div>
        </div>
      </aside>

      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
