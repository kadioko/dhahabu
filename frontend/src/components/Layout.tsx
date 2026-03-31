import { Link, Outlet, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchSystemOverview } from '../lib/api'
import clsx from 'clsx'

const NAV = [
  { to: '/', label: 'Dashboard', icon: '⚡' },
  { to: '/chart', label: 'Chart', icon: '📈' },
  { to: '/signals', label: 'Signals', icon: '🎯' },
  { to: '/trades', label: 'Trades', icon: '💼' },
  { to: '/pnl', label: 'PnL', icon: '💰' },
  { to: '/risk', label: 'Risk', icon: '🛡️' },
  { to: '/self-healing', label: 'Self-Healing', icon: '🔬' },
  { to: '/scheduler', label: 'Scheduler', icon: '⏱️' },
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
    ? { color: 'bg-red-400', label: 'API Offline' }
    : isLoading
    ? { color: 'bg-gray-500', label: 'Connecting...' }
    : !overview?.latest_candle_at
    ? { color: 'bg-yellow-400 animate-pulse', label: 'Warming up' }
    : { color: 'bg-green-400 animate-pulse', label: 'System Online' }

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex">
      {/* Sidebar */}
      <aside className="w-56 bg-gray-900 border-r border-gray-800 flex flex-col flex-shrink-0">
        {/* Logo */}
        <div className="px-6 py-5 border-b border-gray-800">
          <div className="text-yellow-400 font-bold text-xl tracking-tight">DHAHABU</div>
          <div className="text-gray-500 text-xs mt-0.5">XAU/USD Intelligence</div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-0.5">
          {NAV.map(({ to, label, icon }) => {
            const active = to === '/' ? pathname === '/' : pathname.startsWith(to)
            return (
              <Link
                key={to}
                to={to}
                className={clsx(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                  active
                    ? 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20'
                    : 'text-gray-400 hover:text-gray-100 hover:bg-gray-800'
                )}
              >
                <span className="text-base">{icon}</span>
                {label}
              </Link>
            )
          })}
        </nav>

        {/* Status dot */}
        <div className="px-6 py-4 border-t border-gray-800">
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <div className={clsx('w-2 h-2 rounded-full flex-shrink-0', statusDot.color)} />
            {statusDot.label}
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
