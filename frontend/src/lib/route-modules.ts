export const loadDashboardPage = () =>
  import('../pages/DashboardPage').then((module) => ({ default: module.DashboardPage }))

export const loadChartPage = () =>
  import('../pages/ChartPage').then((module) => ({ default: module.ChartPage }))

export const loadSignalsPage = () =>
  import('../pages/SignalsPage').then((module) => ({ default: module.SignalsPage }))

export const loadTradesPage = () =>
  import('../pages/TradesPage').then((module) => ({ default: module.TradesPage }))

export const loadPnLPage = () =>
  import('../pages/PnLPage').then((module) => ({ default: module.PnLPage }))

export const loadRiskPage = () =>
  import('../pages/RiskPage').then((module) => ({ default: module.RiskPage }))

export const loadSelfHealingPage = () =>
  import('../pages/SelfHealingPage').then((module) => ({ default: module.SelfHealingPage }))

export const loadSchedulerPage = () =>
  import('../pages/SchedulerPage').then((module) => ({ default: module.SchedulerPage }))

export const preloadRouteModules = {
  dashboard: loadDashboardPage,
  chart: loadChartPage,
  signals: loadSignalsPage,
  trades: loadTradesPage,
  pnl: loadPnLPage,
  risk: loadRiskPage,
  selfHealing: loadSelfHealingPage,
  scheduler: loadSchedulerPage,
}
