// DecisionMemoryPanel.jsx — "📔 Decision Memory (episodes · attribution · reflections)"
// Surfaces trading/brain/decision_memory.py (FinMem layered episodes + TradingAgents
// outcome-closure reflections + SHAP attribution, 2026-07-03). HONEST wiring: every value
// comes from GET /api/trading/brain/decisions; the recall box runs a REAL layered recall
// (?symbol=/&q=) against the persisted episode store — never canned rows.
import { useEffect, useState } from 'react'
import { T } from './theme.js'

async function getJSON(url) {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json()
}

const LAYER_COLOR = { shallow: T.muted, mid: T.warn, deep: T.good }

function Badge({ text, color }) {
  return (
    <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: 0.5, color,
                   border: `1px solid ${color}`, borderRadius: 4, padding: '1px 6px',
                   textTransform: 'uppercase', whiteSpace: 'nowrap' }}>{text}</span>
  )
}

function Stat({ k, v, color }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', minWidth: 70 }}>
      <span style={{ color: T.muted, fontSize: 10, textTransform: 'uppercase', letterSpacing: 0.5 }}>{k}</span>
      <span style={{ color: color || T.text, fontSize: 15, fontWeight: 700 }}>{v ?? '—'}</span>
    </div>
  )
}

export default function DecisionMemoryPanel() {
  const [d, setD] = useState(null)
  const [err, setErr] = useState(null)
  const [q, setQ] = useState('')

  const load = async (query = '') => {
    try {
      const j = await getJSON(`/api/trading/brain/decisions${query ? `?q=${encodeURIComponent(query)}` : ''}`)
      setD(j); setErr(j.available ? null : (j.error || 'unavailable'))
    } catch (e) { setErr(String(e)) }
  }
  useEffect(() => {
    load()
    const t = setInterval(() => load(), 30000)   // slow tier: episodes change on open/close
    return () => clearInterval(t)
  }, [])

  const st = (d && d.stats) || {}
  const eps = (d && d.episodes) || []
  return (
    <div style={{ background: T.panel, border: `1px solid ${T.border}`, borderRadius: 10, padding: 12 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
        <span style={{ fontWeight: 600, fontSize: 13, color: T.text }}>📔 Decision Memory</span>
        <span style={{ color: T.muted, fontSize: 11 }}>
          FinMem layered episodes · SHAP attribution · reflections at close — what the brain
          considered, which data drove it, what it learned
        </span>
      </div>
      {err && <div style={{ color: T.warn, fontSize: 12 }}>decision memory: {err}</div>}

      <div style={{ display: 'flex', gap: 18, marginBottom: 10, flexWrap: 'wrap' }}>
        <Stat k="episodes" v={st.episodes} />
        <Stat k="pending" v={st.pending} color={T.warn} />
        <Stat k="resolved" v={st.resolved} />
        <Stat k="win rate" v={st.win_rate != null ? `${(st.win_rate * 100).toFixed(1)}%` : '—'}
              color={st.win_rate > 0.5 ? T.good : T.bad} />
        <Stat k="reflections" v={st.reflections} />
        <Stat k="layers" v={st.by_layer ? `${st.by_layer.shallow || 0}/${st.by_layer.mid || 0}/${st.by_layer.deep || 0}` : '—'} />
      </div>

      <div style={{ display: 'flex', gap: 6, marginBottom: 10 }}>
        <input value={q} onChange={(e) => setQ(e.target.value)}
               onKeyDown={(e) => e.key === 'Enter' && load(q)}
               placeholder="recall: symbol or free text (e.g. BTC short funding)…"
               style={{ flex: 1, background: T.bg, border: `1px solid ${T.border}`, borderRadius: 6,
                        color: T.text, fontSize: 12, padding: '6px 8px' }} />
        <button onClick={() => load(q)}
                style={{ background: T.bg, border: `1px solid ${T.border}`, borderRadius: 6,
                         color: T.text, fontSize: 12, padding: '6px 12px', cursor: 'pointer' }}>
          Recall
        </button>
      </div>

      <div style={{ maxHeight: 320, overflowY: 'auto' }}>
        {eps.length === 0 && !err && (
          <div style={{ color: T.muted, fontSize: 12 }}>
            No episodes yet — they are recorded at each entry and resolved at close.
          </div>
        )}
        {eps.map((e) => {
          const pnl = e.outcome ? Number(e.outcome.net_pnl) : null
          return (
            <div key={e.episode_id}
                 style={{ borderTop: `1px solid ${T.border}`, padding: '7px 0', fontSize: 12 }}>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                <span style={{ color: T.text, fontWeight: 700 }}>{e.symbol}</span>
                <span style={{ color: e.direction === 'LONG' ? T.good : T.bad, fontWeight: 700 }}>{e.direction}</span>
                <span style={{ color: T.muted }}>@{e.entry_price ?? '—'}</span>
                <span style={{ color: T.muted }}>{e.strategy || ''}</span>
                <Badge text={e.layer} color={LAYER_COLOR[e.layer] || T.muted} />
                <Badge text={e.engine} color={T.muted} />
                {e.pending
                  ? <Badge text="pending" color={T.warn} />
                  : <span style={{ color: pnl > 0 ? T.good : T.bad, fontWeight: 700 }}>
                      {pnl > 0 ? '+' : ''}{pnl?.toFixed(4)}
                      {e.outcome.r_multiple != null && ` (R ${Number(e.outcome.r_multiple).toFixed(2)})`}
                    </span>}
                <span style={{ color: T.muted, marginLeft: 'auto' }}>
                  imp {Number(e.importance).toFixed(0)}
                </span>
              </div>
              {(e.attribution_top || []).length > 0 && (
                <div style={{ color: T.muted, marginTop: 2 }}>
                  drivers: {e.attribution_top.slice(0, 4).map((a) =>
                    `${a.feature} ${a.impact > 0 ? '+' : ''}${Number(a.impact).toFixed(3)}`).join(' · ')}
                </div>
              )}
              {e.reflection && (
                <div style={{ color: T.text, opacity: 0.85, marginTop: 3, fontStyle: 'italic' }}>
                  “{e.reflection}”
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
