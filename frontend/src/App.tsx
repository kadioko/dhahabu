import { Suspense, lazy, type ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { RouteSkeleton } from './components/RouteSkeleton'
import {
  loadChartPage,
  loadDashboardPage,
  loadPnLPage,
  loadRiskPage,
  loadSchedulerPage,
  loadSelfHealingPage,
  loadSignalsPage,
  loadTradesPage,
} from './lib/route-modules'

const DashboardPage = lazy(loadDashboardPage)
const ChartPage = lazy(loadChartPage)
const SignalsPage = lazy(loadSignalsPage)
const TradesPage = lazy(loadTradesPage)
const PnLPage = lazy(loadPnLPage)
const RiskPage = lazy(loadRiskPage)
const SelfHealingPage = lazy(loadSelfHealingPage)
const SchedulerPage = lazy(loadSchedulerPage)

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchInterval: 30_000,
      retry: 2,
    },
  },
})

function withRouteFallback(element: ReactNode, title: string, subtitle?: string) {
  return <Suspense fallback={<RouteSkeleton title={title} subtitle={subtitle} />}>{element}</Suspense>
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route
              index
              element={withRouteFallback(
                <DashboardPage />,
                'Loading command center',
                'Preparing market posture, risk state, and scheduler context.'
              )}
            />
            <Route
              path="chart"
              element={withRouteFallback(
                <ChartPage />,
                'Loading chart workspace',
                'Preparing candle history and signal overlays.'
              )}
            />
            <Route
              path="signals"
              element={withRouteFallback(
                <SignalsPage />,
                'Loading signals',
                'Pulling recent approvals, suppressions, and scoring data.'
              )}
            />
            <Route
              path="trades"
              element={withRouteFallback(
                <TradesPage />,
                'Loading trades',
                'Preparing open positions and historical execution data.'
              )}
            />
            <Route
              path="pnl"
              element={withRouteFallback(
                <PnLPage />,
                'Loading PnL analytics',
                'Preparing performance history and daily snapshots.'
              )}
            />
            <Route
              path="risk"
              element={withRouteFallback(
                <RiskPage />,
                'Loading risk monitor',
                'Preparing shutdown state, drawdown, and exposure data.'
              )}
            />
            <Route
              path="self-healing"
              element={withRouteFallback(
                <SelfHealingPage />,
                'Loading self-healing engine',
                'Preparing validation, overfit, and promotion history.'
              )}
            />
            <Route
              path="scheduler"
              element={withRouteFallback(
                <SchedulerPage />,
                'Loading scheduler health',
                'Preparing job status, service health, and manual controls.'
              )}
            />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
