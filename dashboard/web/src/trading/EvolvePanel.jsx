// EvolvePanel.jsx — "🧬 Self-Evolving Loop (lifelong)"
// Surfaces trading/strategy/self_evolve.py: DEAP NSGA-II evolves strategies, guardrail-
// passed winners are admitted into the growing SkillLibrary (Voyager-style), stale skills
// retired. Honest about the production gate (OFF for this library-first phase). Self-
// contained: polls /api/brain/evolve (~8s), inline-styled via ./theme.js, hand-rolled SVG.
import { useEffect, useState } from 'react'
import { T } from './theme.js'

async function getJSON(url) {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json()
}
function num(v) { const n = v == null ? null : Number(v); return Number.isFinite(n) ? n : null }
function fmt(v, d = 2) { const n = num(v); return n == null ? '—' : n.toFixed(d) }

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

// best-score-per-generation sparkline
function Spark({ values, color = T.good, w = 220, h = 44 }) {
  const data = (values || []).filter((v) => Number.isFinite(v))
  if (data.length < 2) return <Empty note="no generations" />
  const min = Math.min(...data), max = Math.max(...data), span = max - min || 1, pad = 3
  const stepX = (w - pad * 2) / (data.length - 1)
  const y = (v) => h - pad - ((v - min) / span) * (h - pad * 2)
  const pts = data.map((v, i) => `${(pad + i * stepX).toFixed(1)},${y(v).toFixed(1)}`)
  return (
    <svg width={w} height={h} style={{ display: 'block' }}>
      <polyline points={pts.join(' ')} fill="none" stroke={color} strokeWidth={1.5}
                strokeLinejoin="round" strokeLinecap="round" />
      {data.map((v, i) => <circle key={i} cx={pad + i * stepX} cy={y(v)} r={2} fill={color} />)}
    </svg>
  )
}

export default function EvolvePanel({ intervalMs = 8000 }) {
  const [state, setState] = useState({ loading: true })
  useEffect(() => {
    let alive = true
    const tick = async () => {
      try { const data = await getJSON('/api/brain/evolve'); if (alive) setState({ data, stamp: new Date() }) }
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
            textAlign: 'center' }}>🧬<div style={{ marginTop: 8 }}>loading Self-Evolving Loop…</div></div></div>
  }
  const d = state.data
  const run = d && d.run
  const lib = d && d.library
  const gens = (run && run.gen_history) || []
  const admitted = (run && run.admitted_skills) || []
  return (
    <div style={wrap}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 12 }}>
        <span style={{ fontWeight: 700, fontSize: 16, color: T.text }}>🧬 Self-Evolving Loop</span>
        {d && <Badge text={d.gate_enabled ? 'engine ON' : 'gated OFF · library-first'}
                     color={d.gate_enabled ? T.good : T.muted} />}
        {d && d.demo_forced && <Badge text="forced demo" color={T.warn} />}
        <div style={{ flex: 1 }} />
        {state.stamp && <span style={{ fontSize: 10, color: T.muted }}>updated {state.stamp.toLocaleTimeString()}</span>}
      </div>
      {state.error || !run ? (
        <Empty note={state.error || (d && d.error) || 'loop unavailable'} />
      ) : (
        <>
          <div style={{ display: 'flex', gap: 20, marginBottom: 10, flexWrap: 'wrap' }}>
            <Stat label="evaluated" value={run.evaluated ?? '—'} color={T.accent} />
            <Stat label="promoted" value={run.promoted ?? 0} color={T.good} />
            <Stat label="admitted" value={run.admitted ?? 0} color={T.good} />
            <Stat label="best score" value={fmt(run.best_score, 3)} color={T.good} />
            <Stat label="pbo" value={fmt(run.pbo, 2)} color={T.warn} />
            <Stat label="skills" value={lib ? lib.n_skills : '—'} color={T.accent} />
          </div>
          <div style={{ fontSize: 11, color: T.muted, marginBottom: 4 }}>best score per generation</div>
          <Spark values={gens.map((g) => num(g.best_score))} />

          {admitted.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <div style={{ fontSize: 11, color: T.good, marginBottom: 4 }}>✓ admitted into skill library</div>
              {admitted.slice(0, 5).map((s, i) => (
                <div key={i} style={{ display: 'flex', gap: 8, fontSize: 11, color: T.text }}>
                  <span style={{ color: T.good }}>•</span>
                  <span style={{ flex: 1 }}>{s.name}</span>
                  <span style={{ color: T.good, fontWeight: 600 }}>{fmt(s.metric, 3)}</span>
                  {s.improved && <Badge text="improved" color={T.accent} />}
                </div>
              ))}
            </div>
          )}
          {lib && Array.isArray(lib.top) && lib.top.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <div style={{ fontSize: 11, color: T.muted, marginBottom: 4 }}>top skills (compounded)</div>
              {lib.top.slice(0, 5).map((s, i) => (
                <div key={i} style={{ display: 'flex', gap: 8, fontSize: 11, color: T.muted }}>
                  <span>•</span><span style={{ flex: 1 }}>{s.name}</span>
                  <span>{s.market}</span><span style={{ fontWeight: 600 }}>{fmt(s.metric, 3)}</span>
                </div>
              ))}
            </div>
          )}
          <div style={{ marginTop: 10, fontSize: 10, color: T.muted, lineHeight: 1.5 }}>
            DEAP NSGA-II → guardrails (DSR/PBO) → SkillLibrary admission · gate OFF in
            production (library-first); shown here as a forced offline demo.
          </div>
        </>
      )}
    </div>
  )
}
