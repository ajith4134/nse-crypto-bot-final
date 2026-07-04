// PsychologyPanel.jsx — "🧠 Trader Psychology (Order-Book Depth)"
// Surfaces trading/brain/psychology.py: LIVE crowd sentiment computed from real order-book
// depth (bid/ask ladders) per open-position symbol — OBI, OFI, Stoikov microprice drift,
// depth-slope, whale walls, spread/λ/VPIN fear and the composite score the brain uses as an
// entry signal and learns from (journal columns + TradeOutcomeNet features). Stitched
// reuse-first from vendor/lob_regime_scanner + microprice + crypto_whale_watching +
// lob_deep_learning. Self-contained polling of /api/trading/psychology (~6s); honest:
// empty state = no open positions / no depth, never fake rows.
import { useEffect, useState } from 'react'
import { T } from './theme.js'

async function getJSON(url) {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json()
}
const num = (v) => (v == null || !Number.isFinite(Number(v)) ? null : Number(v))
const fmt = (v, d = 2) => { const n = num(v); return n == null ? '—' : n.toFixed(d) }

const LABEL_COLOR = {
  euphoric: T.good, greedy: T.good, optimistic: '#7bd88f',
  balanced: T.muted, anxious: T.warn, fearful: T.bad, capitulation: T.bad,
}
const scoreCol = (s) => { const n = num(s); return n == null ? T.muted : n > 0.1 ? T.good : n < -0.1 ? T.bad : T.muted }

function Bar({ value, min = -1, max = 1 }) {
  const n = num(value) ?? 0
  const pct = ((n - min) / (max - min)) * 100
  return (
    <div style={{ position: 'relative', flex: 1, height: 8, background: T.gridline, borderRadius: 4 }}>
      <div style={{ position: 'absolute', left: '50%', top: -2, bottom: -2, width: 1, background: T.border }} />
      <div style={{ position: 'absolute', left: `${Math.min(50, pct)}%`, width: `${Math.abs(pct - 50)}%`,
                    height: '100%', background: scoreCol(n), opacity: 0.75, borderRadius: 4 }} />
    </div>
  )
}

function Row({ r }) {
  const [open, setOpen] = useState(false)
  const label = r.psych_label || '—'
  const walls = [...(r.bid_walls || []).map(w => ({ ...w, side: 'BID' })),
                 ...(r.ask_walls || []).map(w => ({ ...w, side: 'ASK' }))]
  return (
    <div style={{ borderBottom: `1px solid ${T.gridline}` }}>
      <div onClick={() => setOpen(!open)}
           style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '7px 4px',
                    cursor: 'pointer', fontSize: 12 }}>
        <span style={{ width: 130, fontWeight: 700, color: T.text, overflow: 'hidden',
                       textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {r.symbol}
          <span style={{ color: T.muted, fontWeight: 400, fontSize: 10 }}> {r.market}{r.segment ? `·${r.segment}` : ''}</span>
        </span>
        <span style={{ width: 46, textAlign: 'right', fontWeight: 800, color: scoreCol(r.trader_psychology) }}>
          {num(r.trader_psychology) > 0 ? '+' : ''}{fmt(r.trader_psychology)}
        </span>
        <Bar value={r.trader_psychology} />
        <span style={{ width: 84, fontSize: 10, fontWeight: 700, textTransform: 'uppercase',
                       letterSpacing: 0.5, color: LABEL_COLOR[label] || T.muted, textAlign: 'right' }}>{label}</span>
        <span style={{ width: 60, textAlign: 'right', color: T.warn, fontSize: 11 }}>fear {fmt(r.psych_fear)}</span>
        <span style={{ color: T.muted, fontSize: 10 }}>{open ? '▾' : '▸'}</span>
      </div>
      {open && (
        <div style={{ padding: '2px 4px 10px 12px', fontSize: 11, color: T.muted,
                      display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0,1fr))', gap: 6 }}>
          <span>OBI (top): <b style={{ color: scoreCol(r.psych_obi) }}>{fmt(r.psych_obi)}</b></span>
          <span>OBI (L1): <b style={{ color: scoreCol(r.psych_obi_l1) }}>{fmt(r.psych_obi_l1)}</b></span>
          <span>OFI z: <b style={{ color: scoreCol(r.psych_ofi_z) }}>{fmt(r.psych_ofi_z)}</b></span>
          <span>μprice drift: <b style={{ color: scoreCol(r.psych_microprice_drift_bps) }}>{fmt(r.psych_microprice_drift_bps)} bps</b></span>
          <span>spread: <b>{fmt(r.psych_spread_bps, 1)} bps</b></span>
          <span>depth slope: <b style={{ color: scoreCol(r.psych_depth_slope_bias) }}>{fmt(r.psych_depth_slope_bias)}</b></span>
          <span>wall bias: <b style={{ color: scoreCol(r.psych_wall_bias) }}>{fmt(r.psych_wall_bias)}</b></span>
          <span>VPIN: <b>{fmt(r.psych_vpin)}</b></span>
          <span>DeepLOB P(up): <b>{r.psych_deeplob_prob_up == null ? 'training data accumulating' : fmt(r.psych_deeplob_prob_up)}</b></span>
          <span>snapshots: <b>{r.n_snapshots}</b></span>
          {walls.length > 0 && (
            <span style={{ gridColumn: 'span 2' }}>
              walls: {walls.slice(0, 4).map((w, i) => (
                <span key={i} style={{ color: w.side === 'BID' ? T.good : T.bad, marginRight: 8 }}>
                  {w.side} {fmt(w.price, 2)} ({(w.frac * 100).toFixed(0)}%)
                </span>
              ))}
            </span>
          )}
        </div>
      )}
    </div>
  )
}

export default function PsychologyPanel({ intervalMs = 6000 }) {
  const [state, setState] = useState({ loading: true })

  useEffect(() => {
    let alive = true
    const tick = async () => {
      try {
        const data = await getJSON('/api/trading/psychology')
        if (alive) setState({ data, stamp: new Date() })
      } catch (e) {
        if (alive) setState({ error: String(e.message || e), stamp: new Date() })
      }
    }
    tick()
    const timer = setInterval(tick, intervalMs)
    return () => { alive = false; clearInterval(timer) }
  }, [intervalMs])

  const wrap = { background: T.bg, border: `1px solid ${T.border}`, borderRadius: 12,
                 padding: 14, color: T.text, fontFamily: 'system-ui, sans-serif',
                 boxSizing: 'border-box', width: '100%' }
  if (state.loading) {
    return <div style={wrap}><div style={{ color: T.muted, fontSize: 13, padding: '24px 0',
            textAlign: 'center' }}>🧠<div style={{ marginTop: 8 }}>reading order books…</div></div></div>
  }
  const d = state.data
  const rows = (d && d.rows) || []
  return (
    <div style={wrap}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 10 }}>
        <span style={{ fontWeight: 700, fontSize: 16 }}>🧠 Trader Psychology · Order-Book Depth</span>
        <span style={{ fontSize: 10, color: T.muted }}>OBI · OFI · microprice · walls · fear — live signal + journal columns</span>
        <div style={{ flex: 1 }} />
        {state.stamp && <span style={{ fontSize: 10, color: T.muted }}>updated {state.stamp.toLocaleTimeString()}</span>}
      </div>
      {state.error || !d ? (
        <div style={{ color: T.muted, fontSize: 12 }}>{state.error || 'unavailable'}</div>
      ) : d.available === false ? (
        <div style={{ color: T.muted, fontSize: 12 }}>{d.error || 'unavailable'}</div>
      ) : rows.length === 0 ? (
        <div style={{ color: T.muted, fontSize: 12, padding: '6px 0' }}>
          no open positions with live depth right now — psychology is computed per symbol at
          entry time and shown here while positions are open
        </div>
      ) : (
        rows.map((r, i) => <Row key={`${r.market}:${r.symbol}:${i}`} r={r} />)
      )}
      <div style={{ marginTop: 8, fontSize: 10, color: T.muted, lineHeight: 1.5 }}>
        score ∈ [−1, +1]: crowd pressure up/down, dampened by fear (spread · Kyle λ · VPIN) ·
        stitched from lob-regime-scanner, Stoikov microprice, whale-watching, DeepLOB
      </div>
    </div>
  )
}
