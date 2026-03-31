import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { createChart, IChartApi } from 'lightweight-charts'
import { fetchCandles, fetchActiveSignals } from '../lib/api'
import { Badge, directionBadge } from '../components/Badge'

const TIMEFRAMES = [
  { label: 'M15', value: '15min' },
  { label: 'H1', value: '1h' },
  { label: 'H4', value: '4h' },
  { label: 'D1', value: '1day' },
]

export function ChartPage() {
  const chartRef = useRef<HTMLDivElement>(null)
  const chartApi = useRef<IChartApi | null>(null)
  const [timeframe, setTimeframe] = useState('1h')

  const { data: candleData, isLoading, isFetching } = useQuery({
    queryKey: ['candles', timeframe],
    queryFn: () => fetchCandles('XAU/USD', timeframe, 300),
    refetchInterval: 60_000,
  })

  const { data: signals } = useQuery({
    queryKey: ['signals-active'],
    queryFn: () => fetchActiveSignals('XAU/USD'),
  })

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
      const chartData = candleData.candles.map((c) => ({
        time: (new Date(c.timestamp).getTime() / 1000) as any,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
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
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-100">XAU/USD Chart</h1>
          {latestPrice && (
            <p className="text-2xl font-bold text-yellow-400 font-mono mt-1">
              ${latestPrice.toFixed(2)}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {TIMEFRAMES.map(({ label, value }) => (
            <button
              key={value}
              onClick={() => setTimeframe(value)}
              className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                timeframe === value
                  ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30'
                  : 'text-gray-400 hover:text-gray-100 hover:bg-gray-800 border border-transparent'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
        <div className="relative min-h-[480px]">
          <div ref={chartRef} className="w-full h-[480px]" />
          {(isLoading || isFetching) && (
            <div className="absolute inset-0 flex items-center justify-center rounded-lg bg-gray-950/50 text-sm text-gray-400">
              Loading candles...
            </div>
          )}
          {!isLoading && !isFetching && !hasCandles && (
            <div className="absolute inset-0 flex items-center justify-center rounded-lg border border-dashed border-gray-700 bg-gray-950/30 text-sm text-gray-500">
              No candle data available yet
            </div>
          )}
        </div>
        <div className="mt-3 flex items-center justify-between text-xs text-gray-500">
          <span>{hasCandles ? `${candleCount} candles loaded` : 'Waiting for initial market data bootstrap'}</span>
          <span>{timeframe}</span>
        </div>
      </div>

      {signals && signals.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <div className="text-sm font-medium text-gray-400 mb-3">
            Active Signals on Chart
          </div>
          <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
            {signals.map(s => (
              <div key={s.id} className="bg-gray-800/50 rounded-lg p-3">
                <div className="flex items-center justify-between mb-2">
                  {directionBadge(s.direction)}
                  <span className="text-xs text-gray-500">{s.timeframe}</span>
                </div>
                <div className="space-y-1 text-xs font-mono">
                  <div className="flex justify-between">
                    <span className="text-gray-500">Entry</span>
                    <span className="text-gray-200">{s.entry.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">SL</span>
                    <span className="text-red-400">{s.stop_loss.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">TP</span>
                    <span className="text-green-400">{s.take_profit.toFixed(2)}</span>
                  </div>
                </div>
                <div className="mt-2 text-[10px] text-gray-600">
                  {s.strategy_name.replace(/_/g, ' ').toUpperCase()}
                  {' · '}{(s.confidence * 100).toFixed(0)}% conf
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
