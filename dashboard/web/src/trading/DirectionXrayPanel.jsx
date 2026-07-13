// DirectionXrayPanel.jsx — "🧭 Direction X-Ray" (owner ask 2026-07-13: what DATA decides
// each trade's direction). Reads /api/trading/direction/xray — the Direction Ledger: each
// recent decision with its winning side, p_up, and every source's MEASURED edge-weight
// (and whether it was inverted as a proven anti-signal). Honest: shows abstains + coverage.
import { useEffect, useState } from 'react'
import { T } from './theme.js'

async function getJSON(url) {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json()
}
function agefmt(s) {
  if (s == null) return ''
  const d = Date.now() / 1000 - s
  if (d < 90) return `${Math.round(d)}s`
  if (d < 5400) return `${Math.round(d / 60)}m`
  return `${(d / 3600).toFixed(1)}h`
}
const DIRCOL = { long: T.good, short: T.bad, neutral: T.muted }

export default function DirectionXrayPanel({ intervalMs = 12000 }) {
  const [state, setState] = useState({ loading: true })
  useEffect(() => {
    let alive = true
    const tick = async () => {
      try { const d = await getJSON('/api/trading/direction/xray'); if (alive) setState({ data: d, stamp: new Date() }) }
      catch (e) { if (alive) setState({ error: String(e.message || e) }) }
    }
    tick(); const t = setInterval(tick, intervalMs)
    return () => { alive = false; clearInterval(t) }
  }, [intervalMs])

  const wrap = { background: T.bg, border: `1px solid ${T.border}`, borderRadius: 12, padding: 14,
                 color: T.text, fontFamily: 'system-ui, sans-serif' }
  if (state.loading) return <div style={wrap}><div style={{ color: T.muted, fontSize: 13 }}>🧭 loading direction ledger…</div></div>
  const d = state.data || {}
  const sm = d.summary || {}
  const rows = d.recent || []
  return (
    <div style={wrap}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 8, flexWrap: 'wrap' }}>
        <span style={{ fontWeight: 700, fontSize: 16 }}>🧭 Direction X-Ray</span>
        <span style={{ fontSize: 11, color: T.muted }}>
          {sm.decisions ?? 0} decisions · driver-coverage <b style={{ color: (sm.with_driver_rate ?? 0) > 0.7 ? T.good : T.warn }}>{sm.with_driver_rate == null ? '—' : `${Math.round(sm.with_driver_rate * 100)}%`}</b> · abstain {sm.abstain_rate == null ? '—' : `${Math.round(sm.abstain_rate * 100)}%`}
          {sm.markets?.length ? ` · ${sm.markets.join(', ')}` : ''}
        </span>
        {d.model && <span style={{ fontSize: 11, color: d.model.trained ? T.accent : T.muted }}>
          model: {d.model.trained ? `${d.model.engine} AUC ${d.model.holdout_auc ?? '—'} (n${d.model.n})` : 'untrained'}</span>}
        <span style={{ fontSize: 10, color: T.muted }}>what data drove each direction — each source weighted by its MEASURED edge</span>
        <div style={{ flex: 1 }} />
        {state.stamp && <span style={{ fontSize: 10, color: T.muted }}>{state.stamp.toLocaleTimeString()}</span>}
      </div>
      {(state.error || !rows.length) && (
        <div style={{ color: T.muted, fontSize: 12 }}>
          {state.error ? `unavailable: ${state.error}` : 'no direction decisions recorded yet — fills as the funnel decides sides'}
        </div>
      )}
      <div style={{ maxHeight: 360, overflowY: 'auto' }}>
        {rows.map((r, i) => (
          <div key={i} style={{ borderBottom: `1px solid ${T.border}`, padding: '6px 0', fontSize: 11 }}>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <b style={{ minWidth: 96 }}>{r.symbol}</b>
              <span style={{ fontWeight: 800, color: DIRCOL[r.direction] || T.muted }}>{(r.direction || '?').toUpperCase()}</span>
              {r.p_up != null && <span style={{ color: T.muted }}>p_up {r.p_up}</span>}
              {r.abstained && <span style={{ color: T.warn }}>ABSTAINED</span>}
              {r.coverage && <span style={{ color: (r.coverage.n_present || 0) >= (r.coverage.n_total || 8) * 0.6 ? T.good : T.warn }}>
                collected {r.coverage.n_present}/{r.coverage.n_total} filters</span>}
              <span style={{ color: T.muted }}>{r.market}{r.regime ? ` · ${r.regime}` : ''} · {r.seam}</span>
              <div style={{ flex: 1 }} />
              <span style={{ color: T.muted, fontSize: 10 }}>{agefmt(r.ts)}</span>
            </div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 3 }}>
              {(r.drivers || []).filter((x) => (x.w || 0) > 0).map((x, j) => (
                <span key={j} style={{ fontSize: 10, border: `1px solid ${T.border}`, borderRadius: 6, padding: '1px 6px',
                                       color: x.invert ? T.warn : T.text }}>
                  {x.source} <b>w{x.w}</b>{x.rate != null ? ` @${Math.round(x.rate * 100)}%` : ''}{x.n != null ? `/n${x.n}` : ''}{x.invert ? ' ⤾inv' : ''}
                </span>
              ))}
              {!(r.drivers || []).some((x) => (x.w || 0) > 0) &&
                <span style={{ fontSize: 10, color: T.muted }}>no source had a proven edge → {r.abstained ? 'abstained' : 'explore'}</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
