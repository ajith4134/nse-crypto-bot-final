// PriceChart.jsx — Phase T6 (Dark Pro UI)
// TradingView Lightweight Charts v5 candlestick + volume pane, themed via ./theme.js.
// Presentational / props-driven. Renders fine with NO props (deterministic demo data).
import { useEffect, useRef } from 'react'
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  ColorType,
  createSeriesMarkers,
} from 'lightweight-charts'
import { T } from './theme.js'

// ── Overlay style conventions (CANON-55 / LSTM-17, TFM-39) ────────────────────
// One codified convention so every pred-vs-real chart reads the same:
//   * real close   — solid candles (up=good, down=bad);
//   * predicted path (in-sample fit / next-bar) — SOLID accent line;
//   * forecast path (future, autoregressive rollout from trading/heads.py) —
//     DASHED warn line + a hollow marker at each forecast step;
//   * train window — a shaded background band ending at the Train→Test boundary,
//     which carries a labelled marker.
export const OVERLAY_STYLE = {
  predicted: { color: T.accent, lineWidth: 2, lineStyle: 0, title: 'predicted' },
  forecast: { color: T.warn, lineWidth: 2, lineStyle: 2, title: 'forecast' }, // 2 = dashed
  trainBand: withAlphaSafe(T.accent, 0.06),
  boundaryMarker: { color: T.warn, shape: 'arrowDown', position: 'aboveBar', text: 'Train→Test' },
}

function withAlphaSafe(hex, a) {
  try { return withAlpha(hex, a) } catch { return `rgba(77,163,255,${a})` }
}

// NO DEMO DATA: this chart renders REAL candles only (honest-wiring rule,
// user directive 2026-07-04 "truth real data, no demos"). With no candles it
// shows an explicit waiting state instead of fabricating a series.

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
  predicted,      // CANON-55: in-sample predicted path [{time,value}] → solid accent line
  forecast,       // CANON-54: future forecast path from trading/heads.py → dashed warn line
  trainSplitTime, // CANON-56: unix seconds marking the end of the train window
}) {
  const containerRef = useRef(null)

  const hasData = !!(candles && candles.length)

  useEffect(() => {
    const el = containerRef.current
    if (!el || !hasData) return

    const data = candles
    // Real candles embed `volume` per bar; map volume→value for the histogram.
    const realVol =
      candles[0].volume != null
        ? candles.map((c) => ({
            time: c.time,
            value: c.volume,
            color: c.close >= c.open ? withAlpha(T.good, 0.5) : withAlpha(T.bad, 0.5),
          }))
        : null
    const vol = volume && volume.length ? volume : realVol || []

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

    // CANON-56: shade the training window as a background band up to the
    // Train→Test boundary. Implemented as a full-height histogram overlay on a
    // hidden price scale (a supported, honest technique — real split time only).
    let allMarkers = markers ? [...markers] : []
    if (trainSplitTime != null && data.length) {
      const bandVal = Math.max(...data.map((c) => c.high)) * 1.5
      const band = chart.addSeries(HistogramSeries, {
        priceScaleId: 'trainband', priceLineVisible: false, lastValueVisible: false,
      })
      band.priceScale().applyOptions({ scaleMargins: { top: 0, bottom: 0 }, visible: false })
      band.setData(data.filter((c) => c.time <= trainSplitTime).map((c) => ({
        time: c.time, value: bandVal, color: OVERLAY_STYLE.trainBand,
      })))
      allMarkers.push({ time: trainSplitTime, ...OVERLAY_STYLE.boundaryMarker })
    }

    // CANON-55: in-sample predicted path — solid accent line.
    if (predicted && predicted.length) {
      const ps = chart.addSeries(LineSeries, {
        color: OVERLAY_STYLE.predicted.color, lineWidth: OVERLAY_STYLE.predicted.lineWidth,
        lineStyle: OVERLAY_STYLE.predicted.lineStyle, priceLineVisible: false, lastValueVisible: false,
      })
      ps.setData(predicted)
    }

    // CANON-54: future forecast path (autoregressive rollout) — dashed warn line + step markers.
    if (forecast && forecast.length) {
      const fs = chart.addSeries(LineSeries, {
        color: OVERLAY_STYLE.forecast.color, lineWidth: OVERLAY_STYLE.forecast.lineWidth,
        lineStyle: OVERLAY_STYLE.forecast.lineStyle, priceLineVisible: false, lastValueVisible: false,
      })
      fs.setData(forecast)
      forecast.forEach((p) => allMarkers.push({
        time: p.time, position: 'aboveBar', color: OVERLAY_STYLE.forecast.color,
        shape: 'circle', size: 0.5,
      }))
    }

    // v5 markers API (real trade markers + boundary + forecast steps).
    if (allMarkers.length) {
      allMarkers.sort((a, b) => a.time - b.time)
      createSeriesMarkers(candleSeries, allMarkers)
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
  }, [candles, volume, markers, height, predicted, forecast, trainSplitTime])

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
        <span style={{ fontSize: 10, color: T.muted, letterSpacing: 0.4 }}>live data only</span>
      </div>
      {hasData ? (
        <div ref={containerRef} style={{ width: '100%' }} />
      ) : (
        <div style={{ height, display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: T.muted, fontSize: 13, fontFamily: 'system-ui, sans-serif' }}>
          waiting for live candles… (no data is ever fabricated)
        </div>
      )}
    </div>
  )
}
