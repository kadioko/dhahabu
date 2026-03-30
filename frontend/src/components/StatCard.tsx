import clsx from 'clsx'

interface StatCardProps {
  label: string
  value: string | number
  sub?: string
  trend?: 'up' | 'down' | 'neutral'
  urgent?: boolean
  className?: string
}

export function StatCard({ label, value, sub, trend, urgent, className }: StatCardProps) {
  const trendIcon = trend === 'up' ? '↑' : trend === 'down' ? '↓' : null

  return (
    <div
      className={clsx(
        'bg-gray-900 border rounded-xl p-5',
        urgent ? 'border-red-500/40' : 'border-gray-800',
        className
      )}
    >
      <div className="text-xs text-gray-500 uppercase tracking-widest mb-2">{label}</div>
      <div className="flex items-baseline gap-1.5">
        <div
          className={clsx(
            'text-2xl font-bold tabular-nums',
            urgent ? 'text-red-400' : trend === 'up' ? 'text-green-400' : trend === 'down' ? 'text-red-400' : 'text-gray-100'
          )}
        >
          {value}
        </div>
        {trendIcon && !urgent && (
          <span className={clsx(
            'text-sm font-semibold',
            trend === 'up' ? 'text-green-500' : 'text-red-500'
          )}>
            {trendIcon}
          </span>
        )}
      </div>
      {sub && <div className="text-xs text-gray-500 mt-1">{sub}</div>}
    </div>
  )
}
