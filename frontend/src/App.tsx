import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { DashboardPage } from './pages/DashboardPage'
import { SignalsPage } from './pages/SignalsPage'
import { TradesPage } from './pages/TradesPage'
import { RiskPage } from './pages/RiskPage'
import { SelfHealingPage } from './pages/SelfHealingPage'
import { SchedulerPage } from './pages/SchedulerPage'
import { ChartPage } from './pages/ChartPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchInterval: 30_000, // 30s auto-refresh
      retry: 2,
    },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<DashboardPage />} />
            <Route path="chart" element={<ChartPage />} />
            <Route path="signals" element={<SignalsPage />} />
            <Route path="trades" element={<TradesPage />} />
            <Route path="risk" element={<RiskPage />} />
            <Route path="self-healing" element={<SelfHealingPage />} />
            <Route path="scheduler" element={<SchedulerPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
