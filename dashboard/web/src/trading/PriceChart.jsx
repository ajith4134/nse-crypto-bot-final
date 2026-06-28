// PriceChart.jsx — Phase T6 (Dark Pro UI)
// TradingView Lightweight Charts v5 candlestick + volume pane, themed via ./theme.js.
// Presentational / props-driven. Renders fine with NO props (deterministic demo data).
import { useEffect, useRef } from 'react'
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  ColorType,
  createSeriesMarkers,
} from 'lightweight-charts'
import { T } from './theme.js'

// --- DEMO DATA (deterministic) -------------------------------------------------
// Generated only when no `candles` prop is supplied so the build/preview always
// shows something. Clearly marked as demo.
function demoCandles(n = 120) {
  const out = []
  let price = 30000
  let seed = 1337
  // tiny deterministic PRNG (mulberry32-ish) so the demo book is stable.
  const rnd = () => {
    seed |= 0
    seed = (seed + 0x6d2b79f5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
  const start = Math.floor(Date.UTC(2024, 0, 1) / 1000)
  for (let i = 0; i < n; i++) {
    const drift = (rnd() - 0.48) * 600
    const open = price
    const close = Math.max(1000, open + drift)
    const high = Math.max(open, close) + rnd() * 200
    const low = Math.min(open, close) - rnd() * 200
    out.push({
      time: start + i * 3600,
      open: round2(open),
      high: round2(high),
      low: round2(low),
      close: round2(close),
    })
    price = close
  }
  return out
}

function demoVolume(candles) {
  let seed = 4242
  const rnd = () => {
    seed |= 0
    seed = (seed + 0x6d2b79f5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
  return candles.map((c) => ({
    time: c.time,
    value: round2(50 + rnd() * 950),
    color: c.close >= c.open ? withAlpha(T.good, 0.5) : withAlpha(T.bad, 0.5),
  }))
}

function round2(v) {
  return Math.round(v * 100) / 100
}

// Convert a #rrggbb hex into an rgba() string with the given alpha.
function withAlpha(hex, a) {
  const h = hex.replace('#', '')
  const r = parseInt(h.substring(0, 2), 16)
  const g = parseInt(h.substring(2, 4), 16)
  const b = parseInt(h.substring(4, 6), 16)
  return `rgba(${r}, ${g}, ${b}, ${a})`
}

export default function PriceChart({
  symbol = 'BTCUSDT',
  candles,
  volume,
  height = 360,
  markers,
}) {
  const containerRef = useRef(null)

  const isDemo = !candles
  // Memo-free: cheap deterministic generation; recompute only when props change
  // is handled inside the effect's dependency list below.

  useEffect(() => {
    const el = containerRef.current
    if (!el) return

    const data = candles && candles.length ? candles : demoCandles()
    const vol = volume && volume.length ? volume : demoVolume(data)

    const chart = createChart(el, {
      width: el.clientWidth || 600,
      height,
      layout: {
        background: { type: ColorType.Solid, color: T.panel },
        textColor: T.text,
        fontSize: 11,
      },
      grid: {
        vertLines: { color: T.gridline },
        horzLines: { color: T.gridline },
      },
      rightPriceScale: { borderColor: T.border },
      timeScale: { borderColor: T.border, timeVisible: true, secondsVisible: false },
      crosshair: {
        vertLine: { color: T.muted, labelBackgroundColor: T.accent },
        horzLine: { color: T.muted, labelBackgroundColor: T.accent },
      },
    })

    // v5: addSeries(SeriesType, options) — replaces v4's addCandlestickSeries.
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: T.good,
      downColor: T.bad,
      borderUpColor: T.good,
      borderDownColor: T.bad,
      wickUpColor: T.good,
      wickDownColor: T.bad,
    })
    candleSeries.setData(data)

    // Volume histogram in its own overlay pane at the bottom.
    const volSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: 'vol',
    })
    volSeries.priceScale().applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    })
    volSeries.setData(vol)

    // v5 markers API.
    if (markers && markers.length) {
      createSeriesMarkers(candleSeries, markers)
    }

    chart.timeScale().fitContent()

    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const w = entry.contentRect.width
        if (w > 0) chart.applyOptions({ width: Math.floor(w) })
      }
    })
    ro.observe(el)

    return () => {
      ro.disconnect()
      chart.remove()
    }
  }, [candles, volume, markers, height])

  return (
    <div
      style={{
        background: T.panel,
        border: `1px solid ${T.border}`,
        borderRadius: 8,
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 12px',
          borderBottom: `1px solid ${T.border}`,
          color: T.text,
          fontFamily: 'system-ui, sans-serif',
        }}
      >
        <span style={{ fontWeight: 600, letterSpacing: 0.4 }}>{symbol}</span>
        {isDemo && (
          <span
            style={{
              fontSize: 10,
              color: T.warn,
              border: `1px solid ${T.warn}`,
              borderRadius: 4,
              padding: '1px 6px',
              textTransform: 'uppercase',
              letterSpacing: 0.6,
            }}
          >
            demo data
          </span>
        )}
      </div>
      <div ref={containerRef} style={{ width: '100%' }} />
    </div>
  )
}
