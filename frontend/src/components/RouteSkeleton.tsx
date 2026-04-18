interface RouteSkeletonProps {
  title: string
  subtitle?: string
}

export function RouteSkeleton({ title, subtitle }: RouteSkeletonProps) {
  return (
    <div className="space-y-6 p-4 md:p-6">
      <div className="rounded-[2rem] border border-white/10 bg-slate-950/80 p-6">
        <div className="text-sm font-medium text-slate-300">{title}</div>
        <div className="h-8 w-64 animate-pulse rounded-xl bg-white/10" />
        <div className="mt-3 h-4 w-80 animate-pulse rounded-lg bg-white/5" />
        {subtitle && <div className="mt-2 text-sm text-slate-500">{subtitle}</div>}
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="rounded-[1.75rem] border border-white/10 bg-slate-950/80 p-5">
            <div className="h-3 w-24 animate-pulse rounded bg-white/10" />
            <div className="mt-4 h-9 w-28 animate-pulse rounded bg-white/5" />
            <div className="mt-3 h-4 w-20 animate-pulse rounded bg-white/5" />
          </div>
        ))}
      </div>

      <div className="rounded-[2rem] border border-white/10 bg-slate-950/80 p-5">
        <div className="h-5 w-40 animate-pulse rounded-lg bg-white/10" />
        <div className="mt-5 h-64 animate-pulse rounded-2xl bg-white/5" />
      </div>
    </div>
  )
}
