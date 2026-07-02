// CoinDetailPanel.jsx — Binance-style coin detail: multi-timeframe candlesticks (lightweight-charts)
// + MA/EMA/VOL indicators + live order-book depth (asks/bids). Opens when a market row is clicked.
import { useEffect, useRef, useState } from 'react'
import { createChart, CandlestickSeries, HistogramSeries, LineSeries } from 'lightweight-charts'
import { T } from './theme.js'

const TFS = ['1m', '5m', '15m', '30m', '1h', '4h', '1d']     // ccxt/binance also: 3m,2h,6h,8h,12h,3d,1w,1M
const enc = (s) => encodeURIComponent(s)
const fmt = (v) => (v == null ? '—' : Number(v).toLocaleString(undefined, { maximumFractionDigits: v < 1 ? 6 : 2 }))

function sma(data, n) {
  const out = []
  for (let i = 0; i < data.length; i++) {
    if (i < n - 1) continue
    let s = 0; for (let j = i - n + 1; j <= i; j++) s += data[j].close
    out.push({ time: data[i].time, value: s / n })
  }
  return out
}
function ema(data, n) {
  const out = []; const k = 2 / (n + 1); let prev = null
  for (let i = 0; i < data.length; i++) { prev = prev == null ? data[i].close : data[i].close * k + prev * (1 - k); out.push({ time: data[i].time, value: prev }) }
  return out
}

export default function CoinDetailPanel({ symbol, onClose }) {
  const [tf, setTf] = useState('15m')
  const [ind, setInd] = useState({ MA: true, EMA: false, VOL: true })
  const [ob, setOb] = useState(null)
  const [meta, setMeta] = useState({})
  const chartEl = useRef(null)
  const chartRef = useRef(null)
  const seriesRef = useRef({})
  const alive = useRef(true)

  // build chart once
  useEffect(() => {
    if (!chartEl.current) return
    const chart = createChart(chartEl.current, {
      autoSize: true, layout: { background: { color: 'transparent' }, textColor: T.muted, fontFamily: 'Inter, system-ui' },
      grid: { vertLines: { color: T.gridline }, horzLines: { color: T.gridline } },
      rightPriceScale: { borderColor: T.border }, timeScale: { borderColor: T.border, timeVisible: true },
      crosshair: { mode: 0 },
    })
    chartRef.current = chart
    seriesRef.current.candle = chart.addSeries(CandlestickSeries, {
      upColor: T.good, downColor: T.bad, borderUpColor: T.good, borderDownColor: T.bad,
      wickUpColor: T.good, wickDownColor: T.bad,
    })
    seriesRef.current.vol = chart.addSeries(HistogramSeries, { priceScaleId: 'vol', priceFormat: { type: 'volume' } })
    chart.priceScale('vol').applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } })
    seriesRef.current.ma7 = chart.addSeries(LineSeries, { color: '#f0b90b', lineWidth: 1 })
    seriesRef.current.ma25 = chart.addSeries(LineSeries, { color: '#e84393', lineWidth: 1 })
    seriesRef.current.ma99 = chart.addSeries(LineSeries, { color: '#8e7cff', lineWidth: 1 })
    seriesRef.current.ema = chart.addSeries(LineSeries, { color: '#00d4ff', lineWidth: 1 })
    return () => { chart.remove(); chartRef.current = null }
  }, [])

  // load candles on tf/symbol change
  const loadCandles = async () => {
    try {
      const r = await fetch(`/api/trading/candles?symbol=${enc(symbol)}&market=CRYPTO&tf=${tf}`)
      const j = await r.json(); const c = j.candles || []
      if (!alive.current || !seriesRef.current.candle || c.length === 0) return
      seriesRef.current.candle.setData(c)
      seriesRef.current.vol.setData(ind.VOL ? c.map((b) => ({ time: b.time, value: b.volume, color: b.close >= b.open ? 'rgba(14,203,129,.5)' : 'rgba(246,70,93,.5)' })) : [])
      seriesRef.current.ma7.setData(ind.MA ? sma(c, 7) : [])
      seriesRef.current.ma25.setData(ind.MA ? sma(c, 25) : [])
      seriesRef.current.ma99.setData(ind.MA ? sma(c, 99) : [])
      seriesRef.current.ema.setData(ind.EMA ? ema(c, 21) : [])
      const last = c[c.length - 1], first = c[0]
      setMeta({ last: last.close, chg: ((last.close - first.open) / first.open) * 100 })
      chartRef.current && chartRef.current.timeScale().fitContent()
    } catch { /* keep */ }
  }
  useEffect(() => { alive.current = true; loadCandles(); const t = setInterval(loadCandles, 8000); return () => { alive.current = false; clearInterval(t) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbol, tf, ind])

  // order book poll
  useEffect(() => {
    let on = true
    const load = async () => { try { const r = await fetch(`/api/trading/orderbook?symbol=${enc(symbol)}&market=CRYPTO`); const j = await r.json(); if (on) setOb(j) } catch { /* */ } }
    load(); const t = setInterval(load, 3000); return () => { on = false; clearInterval(t) }
  }, [symbol])

  const asks = (ob?.asks || []).slice(0, 12)
  const bids = (ob?.bids || []).slice(0, 12)
  const maxSz = Math.max(1, ...asks.map((a) => a[1]), ...bids.map((b) => b[1]))
  const bidVol = bids.reduce((a, b) => a + b[1], 0), askVol = asks.reduce((a, b) => a + b[1], 0)
  const bidPct = (bidVol + askVol) ? (bidVol / (bidVol + askVol)) * 100 : 50

  const tabS = (a) => ({ padding: '4px 11px', borderRadius: 7, fontSize: 12, fontWeight: 700, cursor: 'pointer', transition: 'all .15s',
    border: `1px solid ${a ? T.accent : T.border}`, color: a ? (T.bg || '#0a0e14') : T.muted, background: a ? T.accent : 'transparent' })

  return (
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.6)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', animation: 'fadeIn .18s ease' }}>
      <div onClick={(e) => e.stopPropagation()} style={{ width: 'min(1100px, 95vw)', maxHeight: '92vh', overflow: 'auto', background: T.bg, border: `1px solid ${T.border}`, borderRadius: 14, padding: 16, color: T.text, fontFamily: 'Inter, system-ui', animation: 'popIn .2s cubic-bezier(.2,.8,.2,1)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
          <span style={{ fontSize: 20, fontWeight: 800, letterSpacing: 0.3 }}>{symbol.replace('/', '')}</span>
          <span style={{ fontSize: 18, fontWeight: 700, color: meta.chg >= 0 ? T.good : T.bad }}>{fmt(meta.last)}</span>
          <span style={{ fontSize: 13, fontWeight: 700, color: meta.chg >= 0 ? T.good : T.bad }}>{meta.chg >= 0 ? '+' : ''}{(meta.chg ?? 0).toFixed(2)}%</span>
          <div style={{ flex: 1 }} />
          <button onClick={onClose} style={{ background: T.panel2, color: T.muted, border: `1px solid ${T.border}`, borderRadius: 8, padding: '6px 12px', cursor: 'pointer', fontWeight: 700 }}>✕ Close</button>
        </div>
        {/* timeframe + indicators */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
          {TFS.map((t) => <span key={t} onClick={() => setTf(t)} style={tabS(tf === t)}>{t}</span>)}
          <div style={{ width: 12 }} />
          {['MA', 'EMA', 'VOL'].map((k) => <span key={k} onClick={() => setInd((s) => ({ ...s, [k]: !s[k] }))} style={{ ...tabS(ind[k]), padding: '3px 9px', fontSize: 11 }}>{k}</span>)}
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '3fr 1fr', gap: 12 }}>
          {/* chart */}
          <div ref={chartEl} style={{ height: 460, background: T.panel, border: `1px solid ${T.border}`, borderRadius: 10 }} />
          {/* order book */}
          <div style={{ background: T.panel, border: `1px solid ${T.border}`, borderRadius: 10, padding: 8, fontSize: 11 }}>
            <div style={{ color: T.muted, textTransform: 'uppercase', fontSize: 10, letterSpacing: 0.4, marginBottom: 4 }}>Order Book · Price / Size</div>
            {asks.slice().reverse().map((a, i) => (
              <div key={'a' + i} style={{ position: 'relative', display: 'flex', justifyContent: 'space-between', padding: '1px 4px' }}>
                <div style={{ position: 'absolute', right: 0, top: 0, bottom: 0, width: `${(a[1] / maxSz) * 100}%`, background: 'rgba(246,70,93,.14)' }} />
                <span style={{ color: T.bad, zIndex: 1 }}>{fmt(a[0])}</span><span style={{ color: T.muted, zIndex: 1 }}>{a[1]?.toFixed(3)}</span>
              </div>
            ))}
            <div style={{ textAlign: 'center', fontWeight: 800, color: meta.chg >= 0 ? T.good : T.bad, padding: '4px 0', fontSize: 14 }}>{fmt(ob?.mid || meta.last)}</div>
            {bids.map((b, i) => (
              <div key={'b' + i} style={{ position: 'relative', display: 'flex', justifyContent: 'space-between', padding: '1px 4px' }}>
                <div style={{ position: 'absolute', right: 0, top: 0, bottom: 0, width: `${(b[1] / maxSz) * 100}%`, background: 'rgba(14,203,129,.14)' }} />
                <span style={{ color: T.good, zIndex: 1 }}>{fmt(b[0])}</span><span style={{ color: T.muted, zIndex: 1 }}>{b[1]?.toFixed(3)}</span>
              </div>
            ))}
            {/* buy/sell ratio */}
            <div style={{ display: 'flex', height: 6, borderRadius: 3, overflow: 'hidden', marginTop: 6 }}>
              <div style={{ width: `${bidPct}%`, background: T.good }} /><div style={{ width: `${100 - bidPct}%`, background: T.bad }} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 2 }}><span style={{ color: T.good }}>{bidPct.toFixed(1)}%</span><span style={{ color: T.bad }}>{(100 - bidPct).toFixed(1)}%</span></div>
          </div>
        </div>
        <div style={{ fontSize: 11, color: T.muted, marginTop: 8 }}>MA(7) gold · MA(25) pink · MA(99) violet · EMA(21) cyan · {TFS.length} timeframes (binance supports 16: 1m–1M)</div>
      </div>
    </div>
  )
}
