// ScorecardPanel.jsx — per-segment score card (Dark Pro UI)
// One card per trading segment across NSE / CRYPTO / PREDICTION: realized ("total
// profit", closed trades) + current ("current profit", open positions) + their sum.
// Data: GET /api/trading/scorecard — computed server-side from the SAME sources as the
// unified open/closed tables (journal + live loop + Freqtrade + OpenAlgo), so the
// scores always reconcile with the tables below. Presentational / props-only.
import { T } from './theme.js'

const SEG_ICON = {
  intraday: '📈', mtf: '🏦', futures: '⚡', options: '🎯',
  commodities: '🛢️', spot: '🟢', prediction: '🔮',
}

function money(v, sym) {
  const n = Number(v) || 0
  const s = `${sym}${Math.abs(n).toLocaleString(undefined, { maximumFractionDigits: 2 })}`
  return { text: `${n >= 0 ? '+' : '−'}${s}`, color: n > 0 ? T.good : n < 0 ? T.bad : T.muted }
}

function SegCard({ card }) {
  const tot = money(card.total, card.currency)
  const real = money(card.realized, card.currency)
  const cur = money(card.unrealized, card.currency)
  const row = { display: 'flex', justifyContent: 'space-between', gap: 10, fontSize: 11.5 }
  const lab = { color: T.muted }
  return (
    <div style={{ background: T.panel2, border: `1px solid ${T.border}`, borderRadius: 8,
      padding: '8px 12px', minWidth: 170, fontFamily: 'ui-monospace, Menlo, monospace' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ fontSize: 11, color: T.text, fontWeight: 600, textTransform: 'capitalize' }}>
          {SEG_ICON[card.segment] || '•'} {card.segment}
        </span>
        <span style={{ fontSize: 15, fontWeight: 700, color: tot.color }}>{tot.text}</span>
      </div>
      <div style={row}><span style={lab}>total profit (closed ×{card.closed_count})</span>
        <b style={{ color: real.color }}>{real.text}</b></div>
      <div style={row}><span style={lab}>current profit (open ×{card.open_count})</span>
        <b style={{ color: cur.color }}>{cur.text}</b></div>
    </div>
  )
}

export default function ScorecardPanel({ scorecard }) {
  const sc = scorecard || {}
  const groups = Array.isArray(sc.groups) ? sc.groups : []
  const wrap = { background: T.panel, border: `1px solid ${T.border}`, borderRadius: 8,
    overflow: 'hidden', color: T.text, width: '100%', fontFamily: 'system-ui, sans-serif' }
  const header = { display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '8px 12px', borderBottom: `1px solid ${T.border}` }
  if (!groups.length) {
    return (
      <div style={wrap}>
        <div style={header}><span style={{ fontWeight: 600, letterSpacing: 0.4 }}>Segment Scorecard</span>
          <span style={{ fontSize: 12, color: T.muted }}>{sc.error ? 'offline' : 'loading…'}</span></div>
      </div>
    )
  }
  const grand = money(sc.grand_total_inr, '₹')
  return (
    <div style={wrap}>
      <div style={header}>
        <span style={{ fontWeight: 600, letterSpacing: 0.4 }}>Segment Scorecard</span>
        <span style={{ fontSize: 13, fontFamily: 'ui-monospace, Menlo, monospace' }}>
          <span style={{ color: T.muted, fontSize: 10, textTransform: 'uppercase',
            letterSpacing: 0.5, marginRight: 6 }}>grand total ≈ ₹</span>
          <b style={{ color: grand.color }}>{grand.text}</b>
        </span>
      </div>
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', padding: '10px 12px' }}>
        {groups.map((g) => {
          const gt = money(g.total, g.currency)
          return (
            <div key={g.market} style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10,
                fontSize: 10, color: T.muted, textTransform: 'uppercase', letterSpacing: 0.6 }}>
                <span>{g.market} ({g.currency})</span>
                <b style={{ color: gt.color, fontSize: 11 }}>{gt.text}</b>
              </div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {g.cards.map((c) => <SegCard key={`${g.market}:${c.segment}`} card={c} />)}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
