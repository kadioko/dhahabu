import { QueryObserverResult } from '@tanstack/react-query'
import clsx from 'clsx'
import { formatDistanceToNow } from 'date-fns'
import { AlertTriangle, CheckCircle2, LoaderCircle, RefreshCw } from 'lucide-react'

type StatusTone = 'ok' | 'warn' | 'error' | 'loading'

interface StatusItem {
  label: string
  value: string
  tone: StatusTone
  detail?: string
}

interface ApiStatusPanelProps {
  title?: string
  endpointLabel: string
  query: Pick<
    QueryObserverResult<unknown, unknown>,
    'isLoading' | 'isFetching' | 'isError' | 'error' | 'dataUpdatedAt'
  >
  items: StatusItem[]
  onRefresh?: () => void
}

const toneStyles: Record<StatusTone, string> = {
  ok: 'border-emerald-500/20 bg-emerald-500/10 text-emerald-200',
  warn: 'border-amber-500/20 bg-amber-500/10 text-amber-200',
  error: 'border-red-500/20 bg-red-500/10 text-red-200',
  loading: 'border-cyan-500/20 bg-cyan-500/10 text-cyan-200',
}

function getQueryState(
  query: ApiStatusPanelProps['query']
): { label: string; tone: StatusTone; icon: JSX.Element } {
  if (query.isError) {
    return {
      label: 'API error',
      tone: 'error',
      icon: <AlertTriangle className="h-4 w-4" />,
    }
  }

  if (query.isLoading || query.isFetching) {
    return {
      label: 'Refreshing',
      tone: 'loading',
      icon: <LoaderCircle className="h-4 w-4 animate-spin" />,
    }
  }

  return {
    label: 'Connected',
    tone: 'ok',
    icon: <CheckCircle2 className="h-4 w-4" />,
  }
}

export function ApiStatusPanel({
  title = 'Live API status',
  endpointLabel,
  query,
  items,
  onRefresh,
}: ApiStatusPanelProps) {
  const state = getQueryState(query)
  const errorText =
    query.error instanceof Error ? query.error.message : query.isError ? 'Unknown request failure' : null

  return (
    <section className="rounded-[2rem] border border-white/10 bg-slate-950/80 p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="text-[11px] uppercase tracking-[0.28em] text-slate-500">{title}</div>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <span className={clsx('inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs', toneStyles[state.tone])}>
              {state.icon}
              {state.label}
            </span>
            <span className="text-sm text-slate-400">{endpointLabel}</span>
          </div>
        </div>
        {onRefresh && (
          <button
            onClick={onRefresh}
            className="inline-flex items-center gap-2 rounded-full border border-white/10 px-3 py-2 text-xs font-medium text-slate-300 transition hover:border-white/20 hover:bg-white/5"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh
          </button>
        )}
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-3">
        {items.map((item) => (
          <div key={item.label} className="rounded-2xl border border-white/10 bg-white/5 p-4">
            <div className="text-[11px] uppercase tracking-[0.22em] text-slate-500">{item.label}</div>
            <div
              className={clsx(
                'mt-2 text-sm font-medium',
                item.tone === 'error'
                  ? 'text-red-200'
                  : item.tone === 'warn'
                  ? 'text-amber-200'
                  : item.tone === 'loading'
                  ? 'text-cyan-200'
                  : 'text-slate-100'
              )}
            >
              {item.value}
            </div>
            {item.detail && <div className="mt-1 text-xs text-slate-500">{item.detail}</div>}
          </div>
        ))}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3 text-xs text-slate-500">
        <span>
          Last update:{' '}
          {query.dataUpdatedAt
            ? formatDistanceToNow(new Date(query.dataUpdatedAt), { addSuffix: true })
            : 'not yet'}
        </span>
        {errorText && <span className="text-red-300/80">Error: {errorText}</span>}
      </div>
    </section>
  )
}
