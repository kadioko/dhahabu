import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { createChart, IChartApi } from 'lightweight-charts'
import { AlertTriangle } from 'lucide-react'
import { ApiStatusPanel } from '../components/ApiStatusPanel'
import { directionBadge } from '../components/Badge'
import { fetchActiveSignals, fetchCandles } from '../lib/api'

const TIMEFRAMES = [
  { label: 'M15', value: '15min' },
  { label: 'H1', value: '1h' },
  { label: 'H4', value: '4h' },
  { label: 'D1', value: '1day' },
]

const CHART_REFRESH_INTERVAL_MS = 30_000
const SIGNALS_REFRESH_INTERVAL_MS = 45_000

export function ChartPage() {
  const chartRef = useRef<HTMLDivElement>(null)
  const chartApi = useRef<IChartApi | null>(null)
  const [timeframe, setTimeframe] = useState('1h')

  const candleQuery = useQuery({
    queryKey: ['candles', timeframe],
    queryFn: () => fetchCandles('XAU/USD', timeframe, 300),
    refetchInterval: CHART_REFRESH_INTERVAL_MS,
    refetchIntervalInBackground: true,
  })

  const signalsQuery = useQuery({
    queryKey: ['signals-active', timeframe],
    queryFn: () => fetchActiveSignals('XAU/USD'),
    refetchInterval: SIGNALS_REFRESH_INTERVAL_MS,
    refetchIntervalInBackground: true,
  })

  const candleData = candleQuery.data
  const signals = signalsQuery.data
  const isLoading = candleQuery.isLoading
  const isFetching = candleQuery.isFetching
  const isError = candleQuery.isError
  const isInitialLoad = isLoading && !candleQuery.data
  const isBackgroundRefreshing = isFetching && !isInitialLoad

  useEffect(() => {
    if (!chartRef.current) return

    chartApi.current = createChart(chartRef.current, {
      layout: {
        background: { color: '#030712' },
        textColor: '#9ca3af',
      },
      grid: {
        vertLines: { color: '#1f2937' },
        horzLines: { color: '#1f2937' },
      },
      crosshair: {
        mode: 1,
      },
      rightPriceScale: {
        borderColor: '#374151',
      },
      timeScale: {
        borderColor: '#374151',
        timeVisible: true,
      },
      autoSize: true,
      height: 480,
    })

    const candleSeries = chartApi.current.addCandlestickSeries({
      upColor: '#22c55e',
      downColor: '#ef4444',
      borderUpColor: '#22c55e',
      borderDownColor: '#ef4444',
      wickUpColor: '#22c55e',
      wickDownColor: '#ef4444',
    })

    if (candleData?.candles) {
      const chartData = candleData.candles.map((candle) => ({
        time: (new Date(candle.timestamp).getTime() / 1000) as any,
        open: candle.open,
        high: candle.high,
        low: candle.low,
        close: candle.close,
      }))
      candleSeries.setData(chartData)
      chartApi.current.timeScale().fitContent()
    }

    return () => {
      chartApi.current?.remove()
      chartApi.current = null
    }
  }, [candleData, timeframe])

  const candleCount = candleData?.candles?.length ?? 0
  const hasCandles = candleCount > 0
  const latestPrice = candleData?.candles?.slice(-1)[0]?.close

  return (
    <div className="space-y-4 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-100">XAU/USD Chart</h1>
          {latestPrice && (
            <p className="mt-1 font-mono text-2xl font-bold text-yellow-400">${latestPrice.toFixed(2)}</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {TIMEFRAMES.map(({ label, value }) => (
            <button
              key={value}
              onClick={() => setTimeframe(value)}
              className={`rounded px-3 py-1.5 text-sm font-medium transition-colors ${
                timeframe === value
                  ? 'border border-yellow-500/30 bg-yellow-500/20 text-yellow-400'
                  : 'border border-transparent text-gray-400 hover:bg-gray-800 hover:text-gray-100'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="rounded-xl border border-gray-800 bg-gray-900 p-4">
        <div className="relative min-h-[480px]">
          <div ref={chartRef} className="h-[480px] w-full" />
          {isError && (
            <div className="absolute inset-0 flex items-center justify-center rounded-lg border border-red-500/20 bg-red-950/20 px-6 text-sm text-red-100">
              <div className="flex items-center gap-2 text-center">
                <AlertTriangle className="h-4 w-4 shrink-0" />
                Chart data could not be loaded. Check the live API connection and market ingest jobs.
              </div>
            </div>
          )}
          {isInitialLoad && (
            <div className="absolute inset-0 flex items-center justify-center rounded-lg bg-gray-950/50 text-sm text-gray-400">
              Loading candles...
            </div>
          )}
          {!isInitialLoad && !isFetching && !isError && !hasCandles && (
            <div className="absolute inset-0 flex items-center justify-center rounded-lg border border-dashed border-gray-700 bg-gray-950/30 text-sm text-gray-500">
              No candle data available yet
            </div>
          )}
        </div>
        <div className="mt-3 flex items-center justify-between text-xs text-gray-500">
          <span>
            {isError
              ? 'API connection failed'
              : isBackgroundRefreshing
              ? `Refreshing ${candleCount} candles in the background`
              : hasCandles
              ? `${candleCount} candles loaded`
              : 'Waiting for initial market data bootstrap'}
          </span>
          <span>{timeframe}</span>
        </div>
      </div>

      <ApiStatusPanel
        title="Chart diagnostics"
        endpointLabel={`/candles/latest?symbol=XAU/USD&timeframe=${timeframe}`}
        query={candleQuery}
        onRefresh={() => {
          void candleQuery.refetch()
          void signalsQuery.refetch()
        }}
        items={[
          {
            label: 'Candles API',
            value: isError ? 'Request failed' : hasCandles ? 'Receiving candles' : 'Connected, no candles yet',
            tone: isError ? 'error' : hasCandles ? 'ok' : 'warn',
            detail: hasCandles ? `${candleCount} candles in view` : 'Run market ingest if this stays empty',
          },
          {
            label: 'Latest price',
            value: latestPrice != null ? `$${latestPrice.toFixed(2)}` : 'Unavailable',
            tone: latestPrice != null ? 'ok' : isError ? 'error' : 'warn',
            detail: `Timeframe ${timeframe}`,
          },
          {
            label: 'Signals overlay',
            value: signalsQuery.isError ? 'Request failed' : `${signals?.length ?? 0} active signals`,
            tone: signalsQuery.isError ? 'error' : (signals?.length ?? 0) > 0 ? 'ok' : 'warn',
            detail: 'Used for the on-chart signal context cards',
          },
        ]}
      />

      {signals && signals.length > 0 && (
        <div className="rounded-xl border border-gray-800 bg-gray-900 p-4">
          <div className="mb-3 text-sm font-medium text-gray-400">Active Signals on Chart</div>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
            {signals.map((signal) => (
              <div key={signal.id} className="rounded-lg bg-gray-800/50 p-3">
                <div className="mb-2 flex items-center justify-between">
                  {directionBadge(signal.direction)}
                  <span className="text-xs text-gray-500">{signal.timeframe}</span>
                </div>
                <div className="space-y-1 font-mono text-xs">
                  <div className="flex justify-between">
                    <span className="text-gray-500">Entry</span>
                    <span className="text-gray-200">{signal.entry.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">SL</span>
                    <span className="text-red-400">{signal.stop_loss.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">TP</span>
                    <span className="text-green-400">{signal.take_profit.toFixed(2)}</span>
                  </div>
                </div>
                <div className="mt-2 text-[10px] text-gray-600">
                  {signal.strategy_name.replace(/_/g, ' ').toUpperCase()}
                  {' · '}
                  {(signal.confidence * 100).toFixed(0)}% conf
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
