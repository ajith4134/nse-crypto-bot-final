// PnlStrip.jsx — CANON-56 (RBT-09/11): per-trade P&L strip + P&L distribution
// histogram. Pure SVG, presentational, real data only: pass `trades` as an
// ordered array of numbers (per-trade P&L) or {pnl} objects. When empty it says
// so honestly — it never fabricates a distribution.
import { T } from './theme.js'

function pnls(trades) {
  return (trades || [])
    .map((t) => (typeof t === 'number' ? t
      : Number(t?.net_pnl ?? t?.realized_pnl ?? t?.pnl ?? t?.profit_abs ?? t?.live_pnl ?? t?.profit)))
    .filter((x) => Number.isFinite(x))
}

// Per-trade P&L strip: one vertical bar per closed trade, green up / red down,
// height ∝ |pnl| (RBT-09 "per-trade P&L strip").
function Strip({ values, h = 60 }) {
  const max = Math.max(1e-9, ...values.map((v) => Math.abs(v)))
  const w = Math.max(1.5, Math.min(8, 640 / values.length))
  return (
    <svg viewBox={`0 0 ${values.length * w} ${h}`} preserveAspectRatio="none"
      style={{ width: '100%', height: h }}>
      <line x1="0" y1={h / 2} x2={values.length * w} y2={h / 2} stroke={T.gridline} strokeWidth="0.5" />
      {values.map((v, i) => {
        const bh = (Math.abs(v) / max) * (h / 2 - 2)
        return <rect key={i} x={i * w + 0.3} width={Math.max(0.8, w - 0.6)}
          y={v >= 0 ? h / 2 - bh : h / 2} height={Math.max(0.5, bh)}
          fill={v >= 0 ? T.good : T.bad} opacity="0.85" />
      })}
    </svg>
  )
}

// P&L distribution histogram (RBT-11 "P&L distribution histogram").
function Histogram({ values, bins = 21, h = 90 }) {
  const min = Math.min(...values), max = Math.max(...values)
  const span = (max - min) || 1
  const counts = new Array(bins).fill(0)
  values.forEach((v) => {
    const b = Math.min(bins - 1, Math.floor(((v - min) / span) * bins))
    counts[b] += 1
  })
  const cmax = Math.max(1, ...counts)
  const zeroBin = Math.min(bins - 1, Math.floor(((0 - min) / span) * bins))
  const bw = 100 / bins
  return (
    <svg viewBox={`0 0 100 ${h}`} preserveAspectRatio="none" style={{ width: '100%', height: h }}>
      {counts.map((c, i) => {
        const bh = (c / cmax) * (h - 4)
        return <rect key={i} x={i * bw + 0.2} width={bw - 0.4} y={h - bh} height={bh}
          fill={i < zeroBin ? T.bad : T.good} opacity="0.8" />
      })}
    </svg>
  )
}

export default function PnlStrip({ trades, title = 'Per-trade P&L' }) {
  const values = pnls(trades)
  const wins = values.filter((v) => v > 0).length
  const wrap = { background: T.panel, border: `1px solid ${T.border}`, borderRadius: 8,
    color: T.text, fontFamily: 'system-ui, sans-serif', padding: '8px 12px' }
  const lab = { fontSize: 10, color: T.muted, textTransform: 'uppercase', letterSpacing: 0.6 }
  if (!values.length) {
    return <div style={wrap}><span style={{ fontWeight: 600 }}>{title}</span>
      <div style={{ fontSize: 12, color: T.muted, marginTop: 4 }}>
        no closed trades yet — the strip + histogram appear once trades close (never fabricated).</div></div>
  }
  const total = values.reduce((a, b) => a + b, 0)
  return (
    <div style={wrap}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <span style={{ fontWeight: 600 }}>{title}</span>
        <span style={{ fontSize: 12, fontFamily: 'ui-monospace, Menlo, monospace' }}>
          {values.length} trades · {((wins / values.length) * 100).toFixed(0)}% win ·
          <b style={{ color: total >= 0 ? T.good : T.bad }}> {total >= 0 ? '+' : '−'}{Math.abs(total).toFixed(2)}</b>
        </span>
      </div>
      <div style={{ ...lab, marginTop: 8 }}>per-trade P&amp;L strip</div>
      <Strip values={values} />
      <div style={{ ...lab, marginTop: 8 }}>P&amp;L distribution</div>
      <Histogram values={values} />
    </div>
  )
}
