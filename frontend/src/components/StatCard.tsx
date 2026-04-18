import clsx from 'clsx'
import { ArrowDownRight, ArrowRight, ArrowUpRight } from 'lucide-react'

interface StatCardProps {
  label: string
  value: string | number
  sub?: string
  trend?: 'up' | 'down' | 'neutral'
  urgent?: boolean
  className?: string
}

export function StatCard({ label, value, sub, trend, urgent, className }: StatCardProps) {
  const TrendIcon = trend === 'up' ? ArrowUpRight : trend === 'down' ? ArrowDownRight : ArrowRight

  return (
    <div
      className={clsx(
        'rounded-[1.75rem] border p-5 shadow-[0_20px_80px_-40px_rgba(15,23,42,0.95)] backdrop-blur-sm',
        urgent ? 'border-red-500/30 bg-red-950/30' : 'border-white/10 bg-slate-950/80',
        className
      )}
    >
      <div className="mb-3 text-[11px] uppercase tracking-[0.28em] text-slate-500">{label}</div>
      <div className="flex items-center gap-2">
        <div
          className={clsx(
            'text-3xl font-semibold tracking-tight tabular-nums',
            urgent
              ? 'text-red-300'
              : trend === 'up'
              ? 'text-emerald-300'
              : trend === 'down'
              ? 'text-red-300'
              : 'text-slate-50'
          )}
        >
          {value}
        </div>
        {trend && !urgent && (
          <span
            className={clsx(
              'inline-flex h-8 w-8 items-center justify-center rounded-full border',
              trend === 'up'
                ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                : trend === 'down'
                ? 'border-red-500/30 bg-red-500/10 text-red-300'
                : 'border-slate-500/30 bg-slate-500/10 text-slate-300'
            )}
          >
            <TrendIcon className="h-4 w-4" />
          </span>
        )}
      </div>
      {sub && <div className="mt-2 text-sm text-slate-400">{sub}</div>}
    </div>
  )
}
