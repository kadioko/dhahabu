import clsx from 'clsx'
import type { ReactNode } from 'react'
import {
  ArrowDownRight,
  ArrowUpRight,
  CheckCircle2,
  PauseCircle,
  PlayCircle,
  ShieldAlert,
  ShieldCheck,
  TriangleAlert,
  XCircle,
} from 'lucide-react'

interface BadgeProps {
  children: ReactNode
  variant?: 'green' | 'red' | 'yellow' | 'blue' | 'gray' | 'orange'
  size?: 'sm' | 'xs'
}

const VARIANTS = {
  green: 'border-emerald-500/20 bg-emerald-500/10 text-emerald-300',
  red: 'border-red-500/20 bg-red-500/10 text-red-300',
  yellow: 'border-amber-500/20 bg-amber-500/10 text-amber-200',
  blue: 'border-cyan-500/20 bg-cyan-500/10 text-cyan-200',
  gray: 'border-slate-500/20 bg-slate-500/10 text-slate-300',
  orange: 'border-orange-500/20 bg-orange-500/10 text-orange-300',
}

export function Badge({ children, variant = 'gray', size = 'sm' }: BadgeProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center rounded-full border font-medium',
        VARIANTS[variant],
        size === 'sm' ? 'px-2.5 py-1 text-xs' : 'px-2 py-0.5 text-[10px]'
      )}
    >
      {children}
    </span>
  )
}

export function directionBadge(direction: string) {
  return direction === 'long' ? (
    <Badge variant="green">
      <ArrowUpRight className="mr-1 h-3.5 w-3.5" />
      LONG
    </Badge>
  ) : (
    <Badge variant="red">
      <ArrowDownRight className="mr-1 h-3.5 w-3.5" />
      SHORT
    </Badge>
  )
}

export function statusBadge(status: string) {
  const map: Record<string, [string, BadgeProps['variant'], ReactNode | null]> = {
    approved: ['APPROVED', 'green', <CheckCircle2 className="mr-1 h-3.5 w-3.5" key="icon" />],
    suppressed: ['SUPPRESSED', 'red', <ShieldAlert className="mr-1 h-3.5 w-3.5" key="icon" />],
    downgraded: ['DOWNGRADED', 'orange', <TriangleAlert className="mr-1 h-3.5 w-3.5" key="icon" />],
    pending: ['PENDING', 'yellow', <PauseCircle className="mr-1 h-3.5 w-3.5" key="icon" />],
    open: ['OPEN', 'blue', <PlayCircle className="mr-1 h-3.5 w-3.5" key="icon" />],
    tp_hit: ['TP HIT', 'green', <CheckCircle2 className="mr-1 h-3.5 w-3.5" key="icon" />],
    sl_hit: ['SL HIT', 'red', <XCircle className="mr-1 h-3.5 w-3.5" key="icon" />],
    expired: ['EXPIRED', 'gray', null],
    cancelled: ['CANCELLED', 'gray', null],
    triggered: ['TRIGGERED', 'blue', <PlayCircle className="mr-1 h-3.5 w-3.5" key="icon" />],
    healthy: ['HEALTHY', 'green', <ShieldCheck className="mr-1 h-3.5 w-3.5" key="icon" />],
    degraded: ['DEGRADED', 'orange', <TriangleAlert className="mr-1 h-3.5 w-3.5" key="icon" />],
    down: ['DOWN', 'red', <XCircle className="mr-1 h-3.5 w-3.5" key="icon" />],
    unknown: ['UNKNOWN', 'gray', null],
    success: ['SUCCESS', 'green', <CheckCircle2 className="mr-1 h-3.5 w-3.5" key="icon" />],
    failed: ['FAILED', 'red', <XCircle className="mr-1 h-3.5 w-3.5" key="icon" />],
    started: ['RUNNING', 'blue', <PlayCircle className="mr-1 h-3.5 w-3.5" key="icon" />],
  }

  const [label, variant, icon] = map[status] || [status.toUpperCase(), 'gray', null]
  return <Badge variant={variant as BadgeProps['variant']}>{icon}{label}</Badge>
}
