// FlowHealthPanel.jsx — "🔄 One Cognitive Loop" (Brain Ultra Upgrade Pillar 2, R1)
// The continuous-flow proof: perceive → recall → reason → decide → act → observe →
// reflect → learn → evolve → teach-self, rendered as a ring. Every stage's health is
// REAL: /api/trading/brain/flow measures state-file mtimes on disk (never assumptions).
// Green edge = both endpoint stages carried data within their freshness budgets.
import { useEffect, useState } from 'react'
import { T } from './theme.js'

async function getJSON(url) {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json()
}

function agefmt(s) {
  if (s == null) return 'never'
  if (s < 90) return `${Math.round(s)}s`
  if (s < 5400) return `${Math.round(s / 60)}m`
  if (s < 129600) return `${(s / 3600).toFixed(1)}h`
  return `${(s / 86400).toFixed(1)}d`
}

const ICONS = { perceive: '👁', recall: '🧠', reason: '⚖️', decide: '🎯', act: '⚡',
                observe: '📊', reflect: '🪞', learn: '📚', evolve: '🧬', teach_self: '🎓' }

function Ring({ stages, edges, onPick, picked }) {
  const W = 520, H = 340, cx = W / 2, cy = H / 2, R = 128
  const pos = {}
  stages.forEach((s, i) => {
    const a = -Math.PI / 2 + (i / stages.length) * Math.PI * 2
    pos[s.key] = { x: cx + Math.cos(a) * R, y: cy + Math.sin(a) * R }
  })
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 'auto',
         background: '#0b0f16', borderRadius: 8, border: `1px solid ${T.border}` }}>
      <defs>
        <marker id="fh-arrow-ok" markerWidth="7" markerHeight="7" refX="6" refY="3" orient="auto">
          <path d="M0,0 L6,3 L0,6 z" fill={T.good} />
        </marker>
        <marker id="fh-arrow-bad" markerWidth="7" markerHeight="7" refX="6" refY="3" orient="auto">
          <path d="M0,0 L6,3 L0,6 z" fill="#5a2733" />
        </marker>
      </defs>
      {edges.map((e, i) => {
        const a = pos[e.src], b = pos[e.dst]
        if (!a || !b) return null
        const mx = (a.x + b.x) / 2 + (cx - (a.x + b.x) / 2) * 0.18
        const my = (a.y + b.y) / 2 + (cy - (a.y + b.y) / 2) * 0.18
        return <path key={i} d={`M${a.x},${a.y} Q${mx},${my} ${b.x},${b.y}`} fill="none"
                     stroke={e.ok ? T.good : '#5a2733'} strokeWidth={e.ok ? 2 : 1.4}
                     opacity={e.ok ? 0.85 : 0.7} strokeDasharray={e.ok ? '' : '5 4'}
                     markerEnd={`url(#fh-arrow-${e.ok ? 'ok' : 'bad'})`} />
      })}
      {stages.map((s) => {
        const p = pos[s.key]
        const col = s.ok ? T.good : s.freshest_secs != null ? T.warn : T.bad
        return (
          <g key={s.key} onClick={() => onPick(picked === s.key ? null : s.key)}
             style={{ cursor: 'pointer' }}>
            <circle cx={p.x} cy={p.y} r={20} fill="#0e1420" stroke={col}
                    strokeWidth={picked === s.key ? 3 : 1.6} />
            <text x={p.x} y={p.y + 1} textAnchor="middle" dominantBaseline="middle"
                  fontSize="15">{ICONS[s.key] || '·'}</text>
            <text x={p.x} y={p.y + 33} textAnchor="middle" fontSize="9.5" fill={col}
                  fontWeight="700">{s.key.replace('_', '-')}</text>
            <text x={p.x} y={p.y + 44} textAnchor="middle" fontSize="8.5" fill={T.muted}>
              {agefmt(s.freshest_secs)}</text>
          </g>
        )
      })}
      <text x={cx} y={cy - 8} textAnchor="middle" fontSize="12" fill={T.muted}>continuous</text>
      <text x={cx} y={cy + 8} textAnchor="middle" fontSize="12" fill={T.muted}>flow (R1)</text>
    </svg>
  )
}

export default function FlowHealthPanel({ intervalMs = 15000 }) {
  const [state, setState] = useState({ loading: true })
  const [picked, setPicked] = useState(null)
  useEffect(() => {
    let alive = true
    const tick = async () => {
      try {
        const data = await getJSON('/api/trading/brain/flow')
        if (alive) setState({ data, stamp: new Date() })
      } catch (e) { if (alive) setState({ error: String(e.message || e) }) }
    }
    tick()
    const t = setInterval(tick, intervalMs)
    return () => { alive = false; clearInterval(t) }
  }, [intervalMs])

  const wrap = { background: T.bg, border: `1px solid ${T.border}`, borderRadius: 12,
                 padding: 14, color: T.text, fontFamily: 'system-ui, sans-serif' }
  if (state.loading) return <div style={wrap}><div style={{ color: T.muted, fontSize: 13 }}>🔄 loading loop health…</div></div>
  const d = state.data
  if (state.error || !d || !d.stages?.length) {
    return <div style={wrap}><div style={{ color: T.muted, fontSize: 12 }}>flow monitor unavailable: {state.error || d?.error}</div></div>
  }
  const pickedStage = d.stages.find((s) => s.key === picked)
  return (
    <div style={wrap}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 10, flexWrap: 'wrap' }}>
        <span style={{ fontWeight: 700, fontSize: 16 }}>🔄 One Cognitive Loop</span>
        <span style={{ fontSize: 12, fontWeight: 800,
                       color: d.flowing ? T.good : T.warn }}>
          {d.flowing ? 'FLOWING' : `${d.healthy_stages}/${d.total_stages} stages healthy`}
        </span>
        <span style={{ fontSize: 10, color: T.muted }}>state-file mtimes on disk — no assumptions</span>
        <div style={{ flex: 1 }} />
        {state.stamp && <span style={{ fontSize: 10, color: T.muted }}>updated {state.stamp.toLocaleTimeString()}</span>}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 3fr) minmax(0, 2fr)', gap: 12 }}>
        <Ring stages={d.stages} edges={d.edges} onPick={setPicked} picked={picked} />
        <div style={{ minWidth: 0, maxHeight: 340, overflowY: 'auto' }}>
          {(pickedStage ? [pickedStage] : d.stages).map((s) => (
            <div key={s.key} style={{ border: `1px solid ${T.border}`, borderRadius: 8,
                                      padding: 8, marginBottom: 6 }}>
              <div style={{ fontSize: 12, fontWeight: 700,
                            color: s.ok ? T.good : s.freshest_secs != null ? T.warn : T.bad }}>
                {ICONS[s.key]} {s.label}
              </div>
              <div style={{ fontSize: 10, color: T.muted, marginTop: 2 }}>
                freshest {agefmt(s.freshest_secs)} · budget {agefmt(s.budget_secs)}
              </div>
              {pickedStage && (
                <div style={{ marginTop: 6 }}>
                  {s.evidence.map((e) => (
                    <div key={e.file} style={{ fontSize: 10, color: e.exists ? T.text : T.bad }}>
                      {e.exists ? '●' : '○'} {e.file} — {agefmt(e.age_secs)}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
