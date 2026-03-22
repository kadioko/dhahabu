import clsx from 'clsx'

interface BadgeProps {
  children: React.ReactNode
  variant?: 'green' | 'red' | 'yellow' | 'blue' | 'gray' | 'orange'
  size?: 'sm' | 'xs'
}

const VARIANTS = {
  green: 'bg-green-500/10 text-green-400 border-green-500/20',
  red: 'bg-red-500/10 text-red-400 border-red-500/20',
  yellow: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
  blue: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  gray: 'bg-gray-500/10 text-gray-400 border-gray-500/20',
  orange: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
}

export function Badge({ children, variant = 'gray', size = 'sm' }: BadgeProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center border font-medium rounded-md',
        VARIANTS[variant],
        size === 'sm' ? 'text-xs px-2 py-0.5' : 'text-[10px] px-1.5 py-0.5'
      )}
    >
      {children}
    </span>
  )
}

export function directionBadge(direction: string) {
  return direction === 'long'
    ? <Badge variant="green">▲ LONG</Badge>
    : <Badge variant="red">▼ SHORT</Badge>
}

export function statusBadge(status: string) {
  const map: Record<string, [string, BadgeProps['variant']]> = {
    approved: ['APPROVED', 'green'],
    suppressed: ['SUPPRESSED', 'red'],
    downgraded: ['DOWNGRADED', 'orange'],
    pending: ['PENDING', 'yellow'],
    open: ['OPEN', 'blue'],
    tp_hit: ['TP HIT ✓', 'green'],
    sl_hit: ['SL HIT ✗', 'red'],
    expired: ['EXPIRED', 'gray'],
    cancelled: ['CANCELLED', 'gray'],
    triggered: ['TRIGGERED', 'blue'],
    healthy: ['HEALTHY', 'green'],
    degraded: ['DEGRADED', 'orange'],
    down: ['DOWN', 'red'],
    unknown: ['UNKNOWN', 'gray'],
    success: ['SUCCESS', 'green'],
    failed: ['FAILED', 'red'],
    started: ['RUNNING', 'blue'],
  }
  const [label, variant] = map[status] || [status.toUpperCase(), 'gray']
  return <Badge variant={variant as BadgeProps['variant']}>{label}</Badge>
}
