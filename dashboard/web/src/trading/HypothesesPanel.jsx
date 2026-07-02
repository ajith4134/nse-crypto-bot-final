// HypothesesPanel.jsx — "🔬 Hypothesis Ledger (AI-Scientist loop)"
// Surfaces trading/brain/hypothesis.py: the brain proposes testable trading hypotheses,
// split-tests them on the closed-trade journal (Bayesian A/B + Welch t), and confirms /
// refutes them — confirmed→insight notes, refuted→failure DB. Self-contained: owns its
// polling of /api/brain/hypotheses (~6s), inline-styled via ./theme.js.
import { useEffect, useState } from 'react'
import { T, scoreColor } from './theme.js'

async function getJSON(url) {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json()
}
function num(v) { const n = v == null ? null : Number(v); return Number.isFinite(n) ? n : null }
function fmt(v, d = 2) { const n = num(v); return n == null ? '—' : n.toFixed(d) }

const STATUS_COLOR = (s) => (s === 'confirmed' ? T.good : s === 'refuted' ? T.bad : T.muted)

function Badge({ text, color }) {
  return <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: 0.5, color,
    border: `1px solid ${color}`, borderRadius: 4, padding: '1px 6px',
    textTransform: 'uppercase', whiteSpace: 'nowrap' }}>{text}</span>
}
function Stat({ label, value, color }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <span style={{ fontSize: 10, color: T.muted, textTransform: 'uppercase', letterSpacing: 0.4 }}>{label}</span>
      <span style={{ fontSize: 16, fontWeight: 700, color: color || T.text }}>{value}</span>
    </div>
  )
}
function Empty({ note }) { return <div style={{ color: T.muted, fontSize: 12, padding: '6px 0' }}>{note || 'no data'}</div> }

// One hypothesis row: statement + credence bar + effect size + status.
function HypoRow({ h }) {
  const cred = num(h.credence) ?? 0.5
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 0',
                  borderTop: `1px solid ${T.gridline}` }}>
      <Badge text={h.status} color={STATUS_COLOR(h.status)} />
      <span style={{ flex: 1, fontSize: 12, color: T.text, minWidth: 0 }}>{h.statement}</span>
      <div style={{ width: 90, height: 8, background: T.gridline, borderRadius: 4, overflow: 'hidden' }}>
        <div style={{ width: `${cred * 100}%`, height: '100%', background: scoreColor(cred), opacity: 0.8 }} />
      </div>
      <span style={{ width: 40, textAlign: 'right', fontSize: 11, color: scoreColor(cred), fontWeight: 600 }}>
        {(cred * 100).toFixed(0)}%
      </span>
      <span style={{ width: 56, textAlign: 'right', fontSize: 11,
                     color: (num(h.effect_size) ?? 0) > 0 ? T.good : T.bad }}>
        {(num(h.effect_size) ?? 0) > 0 ? '+' : ''}{fmt(h.effect_size, 2)}
      </span>
      <span style={{ width: 44, textAlign: 'right', fontSize: 10, color: T.muted }}>n={h.n_cond}</span>
    </div>
  )
}

export default function HypothesesPanel({ intervalMs = 6000 }) {
  const [state, setState] = useState({ loading: true })
  useEffect(() => {
    let alive = true
    const tick = async () => {
      try { const data = await getJSON('/api/brain/hypotheses'); if (alive) setState({ data, stamp: new Date() }) }
      catch (e) { if (alive) setState({ error: String(e.message || e), stamp: new Date() }) }
    }
    tick(); const timer = setInterval(tick, intervalMs)
    return () => { alive = false; clearInterval(timer) }
  }, [intervalMs])

  const wrap = { background: T.bg, border: `1px solid ${T.border}`, borderRadius: 12,
                 padding: 14, color: T.text, fontFamily: 'system-ui, sans-serif',
                 boxSizing: 'border-box', width: '100%' }
  if (state.loading) {
    return <div style={wrap}><div style={{ color: T.muted, fontSize: 13, padding: '24px 0',
            textAlign: 'center' }}>🔬<div style={{ marginTop: 8 }}>loading Hypothesis Ledger…</div></div></div>
  }
  const d = state.data
  const led = d && d.ledger
  const insights = (d && d.summary && d.summary.insights) || []
  return (
    <div style={wrap}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 12 }}>
        <span style={{ fontWeight: 700, fontSize: 16, color: T.text }}>🔬 Hypothesis Ledger</span>
        <span style={{ fontSize: 11, color: T.muted }}>AI-Scientist loop</span>
        {d && d.demo && <Badge text="demo journal" color={T.warn} />}
        <div style={{ flex: 1 }} />
        {state.stamp && <span style={{ fontSize: 10, color: T.muted }}>updated {state.stamp.toLocaleTimeString()}</span>}
      </div>
      {state.error || !led ? (
        <Empty note={state.error || (d && d.error) || 'ledger unavailable'} />
      ) : (
        <>
          <div style={{ display: 'flex', gap: 20, marginBottom: 12, flexWrap: 'wrap' }}>
            <Stat label="hypotheses" value={led.n_hypotheses ?? '—'} color={T.accent} />
            <Stat label="confirmed" value={led.confirmed ?? 0} color={T.good} />
            <Stat label="refuted" value={led.refuted ?? 0} color={T.bad} />
            <Stat label="open" value={led.open ?? 0} color={T.muted} />
            <Stat label="trades" value={d.n_trades ?? '—'} />
          </div>

          <div style={{ fontSize: 11, color: T.muted, marginBottom: 4 }}>ranked hypotheses</div>
          {Array.isArray(led.top) && led.top.length ? led.top.map((h, i) => <HypoRow key={i} h={h} />)
            : <Empty note="no hypotheses yet" />}

          {insights.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <div style={{ fontSize: 11, color: T.good, marginBottom: 4 }}>✓ confirmed insights → notes</div>
              {insights.slice(0, 4).map((s, i) => (
                <div key={i} style={{ fontSize: 11, color: T.text, lineHeight: 1.5 }}>
                  <span style={{ color: T.good }}>›</span> {s}
                </div>
              ))}
            </div>
          )}

          {Array.isArray(led.failures) && led.failures.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <div style={{ fontSize: 11, color: T.bad, marginBottom: 4 }}>✗ failure database</div>
              {led.failures.slice(-3).map((f, i) => (
                <div key={i} style={{ fontSize: 11, color: T.muted, lineHeight: 1.5 }}>
                  <span style={{ color: T.bad }}>›</span> {f.statement}
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
