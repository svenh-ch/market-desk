import { useEffect, useRef } from 'react'
import { createChart, CrosshairMode, LineStyle } from 'lightweight-charts'
import type { OHLCV, Indicator } from '../../types'

interface Props {
  candles: OHLCV[]
  indicators: Indicator[]
  height?: number
}

const INDICATOR_COLORS: Record<string, string> = {
  SMA20:  '#3b82f6',
  SMA50:  '#f59e0b',
  SMA200: '#ef4444',
  EMA12:  '#06b6d4',
  EMA26:  '#8b5cf6',
}

export default function CandlestickChart({ candles, indicators, height = 420 }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<ReturnType<typeof createChart> | null>(null)

  useEffect(() => {
    if (!containerRef.current || !candles.length) return

    // Defer until the browser has laid out the container so clientWidth > 0
    const init = () => {
      const el = containerRef.current
      if (!el) return

      const w = el.clientWidth || el.getBoundingClientRect().width || 800

      const chart = createChart(el, {
        width: w,
        height,
        layout: {
          background: { color: '#0d1117' },
          textColor:  '#6b7280',
          fontFamily: '"SF Mono", Menlo, monospace',
          fontSize:   11,
        },
        grid: {
          vertLines: { color: '#1c2333', style: LineStyle.Dotted },
          horzLines: { color: '#1c2333', style: LineStyle.Dotted },
        },
        crosshair: {
          mode: CrosshairMode.Normal,
          vertLine: { color: '#f59e0b55', labelBackgroundColor: '#f59e0b' },
          horzLine: { color: '#f59e0b55', labelBackgroundColor: '#f59e0b' },
        },
        rightPriceScale: {
          borderColor: '#1c2333',
        },
        timeScale: {
          borderColor: '#1c2333',
          timeVisible: true,
          secondsVisible: false,
        },
      })

      chartRef.current = chart

      // Deduplicate candles by timestamp (keep last occurrence)
      const seen = new Map<number, OHLCV>()
      for (const c of candles) seen.set(c.time as number, c)
      const deduped = Array.from(seen.values()).sort((a, b) => (a.time as number) - (b.time as number))

      const candleSeries = chart.addCandlestickSeries({
        upColor:         '#10b981',
        downColor:       '#ef4444',
        borderUpColor:   '#10b981',
        borderDownColor: '#ef4444',
        wickUpColor:     '#10b98180',
        wickDownColor:   '#ef444480',
      })

      candleSeries.setData(deduped.map(c => ({
        time:  c.time as unknown as import('lightweight-charts').Time,
        open:  c.open,
        high:  c.high,
        low:   c.low,
        close: c.close,
      })))

      const displayIndicators = ['SMA20', 'SMA50', 'SMA200']
      indicators
        .filter(ind => displayIndicators.includes(ind.name))
        .forEach(ind => {
          const line = chart.addLineSeries({
            color: INDICATOR_COLORS[ind.name] ?? '#ffffff40',
            lineWidth: 1,
            priceLineVisible: false,
            lastValueVisible: false,
            crosshairMarkerVisible: false,
          })
          // Deduplicate indicator values too
          const indSeen = new Map<number, number>()
          // Nur den sichtbaren Zeitraum zeichnen (Indikatoren werden aus längerer Historie berechnet)
          const firstTime = deduped[0].time as number
          for (const v of ind.values) if ((v.time as number) >= firstTime) indSeen.set(v.time as number, v.value)
          const indDeduped = Array.from(indSeen.entries())
            .sort((a, b) => a[0] - b[0])
            .map(([time, value]) => ({ time: time as number, value }))
          line.setData(indDeduped as unknown as import('lightweight-charts').LineData[])
        })

      chart.timeScale().fitContent()

      const observer = new ResizeObserver(() => {
        if (containerRef.current) {
          chart.applyOptions({ width: containerRef.current.clientWidth })
        }
      })
      observer.observe(el)

      return () => {
        observer.disconnect()
        chart.remove()
        chartRef.current = null
      }
    }

    // Erst nach dem Layout zeichnen (sonst ist die Breite 0); beim Aufräumen
    // den Chart wirklich entfernen, damit sich beim Zeitraumwechsel keine Charts stapeln
    let cleanup: (() => void) | undefined
    const raf = requestAnimationFrame(() => { cleanup = init() })
    return () => { cancelAnimationFrame(raf); cleanup?.() }
  }, [candles, indicators, height])

  return <div ref={containerRef} style={{ height }} className="w-full" />
}
