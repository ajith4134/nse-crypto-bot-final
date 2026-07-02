// WorldModelPanel.jsx — "🌀 Imagination (World-Model + MuZero)"
// Surfaces trading/brain/worldmodel.py: a LEARNED market dynamics model the brain
// rolls forward with MCTS to plan entry/direction/stoploss/profit-trailing in imagined
// R-multiples BEFORE acting. Adapted reuse-first from vendor/muzero_general.
// Self-contained: owns its own polling of /api/brain/worldmodel (~5s), degrades
// gracefully on error, inline-styled via ./theme.js (no chart libs).
import { useEffect, useState } from 'react'
import { T, scoreColor } from './theme.js'

async function getJSON(url) {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json()
}

function num(v) {
  if (v == null) return null
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? n : null
}
function fmt(v, d = 2) {
  const n = num(v)
  return n == null ? '—' : n.toFixed(d)
}
function actionColor(a) {
  const s = String(a || '').toUpperCase()
  if (/(ENTER_LONG|LONG|BUY|SCALE)/.test(s)) return T.good
  if (/(ENTER_SHORT|SHORT|SELL|EXIT)/.test(s)) return T.bad
  if (/TIGHTEN/.test(s)) return T.warn
  return T.muted
}
// R-multiple color: positive green, negative red.
function rColor(r) {
  const n = num(r)
  if (n == null) return T.muted
  return n > 0 ? T.good : n < 0 ? T.bad : T.muted
}

function Card({ title, hint, children, span }) {
  return (
    <div style={{ background: T.panel, border: `1px solid ${T.border}`, borderRadius: 10,
                  padding: 12, gridColumn: span ? `span ${span}` : undefined,
                  boxSizing: 'border-box', minWidth: 0 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 10 }}>
        <span style={{ fontWeight: 600, fontSize: 13, color: T.text, letterSpacing: 0.3 }}>{title}</span>
        {hint && <span style={{ color: T.muted, fontSize: 11 }}>{hint}</span>}
      </div>
      {children}
    </div>
  )
}
function Badge({ text, color }) {
  return (
    <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: 0.5, color,
                   border: `1px solid ${color}`, borderRadius: 4, padding: '1px 6px',
                   textTransform: 'uppercase', whiteSpace: 'nowrap' }}>{text}</span>
  )
}
function Empty({ note }) {
  return <div style={{ color: T.muted, fontSize: 12, padding: '6px 0' }}>{note || 'no data'}</div>
}

// A horizontal bar of the MCTS visit-policy (which action the search preferred).
function PolicyBars({ policy, imaginedR }) {
  const entries = Object.entries(policy || {}).sort((a, b) => b[1] - a[1])
  if (!entries.length) return <Empty note="no policy" />
  const max = Math.max(...entries.map(([, v]) => v)) || 1
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
      {entries.map(([a, v]) => {
        const r = imaginedR ? imaginedR[a] : null
        return (
          <div key={a} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11 }}>
            <span style={{ width: 92, color: actionColor(a), fontWeight: 700 }}>{a}</span>
            <div style={{ flex: 1, height: 8, background: T.gridline, borderRadius: 4, overflow: 'hidden' }}>
              <div style={{ width: `${(v / max) * 100}%`, height: '100%',
                            background: actionColor(a), opacity: 0.7 }} />
            </div>
            <span style={{ width: 40, textAlign: 'right', color: T.muted }}>{(v * 100).toFixed(0)}%</span>
            <span style={{ width: 52, textAlign: 'right', color: rColor(r), fontWeight: 600 }}>
              {r != null ? `${num(r) > 0 ? '+' : ''}${fmt(r, 2)}R` : ''}
            </span>
          </div>
        )
      })}
    </div>
  )
}

function DecisionCard({ title, plan, hint }) {
  if (!plan) return <Card title={title}><Empty /></Card>
  const action = plan.action
  const expR = num(plan.expected_R)
  return (
    <Card title={title} hint={hint}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10 }}>
        <span style={{ fontWeight: 800, fontSize: 18, color: actionColor(action) }}>{action}</span>
        <span style={{ fontSize: 13, fontWeight: 700, color: rColor(expR) }}>
          imagined {expR != null && expR > 0 ? '+' : ''}{fmt(expR, 2)}R
        </span>
      </div>
      <PolicyBars policy={plan.policy} imaginedR={plan.imagined_R} />
    </Card>
  )
}

// The most-visited imagined path = the brain's plan, step by step.
function TrajectoryCard({ plan }) {
  const traj = (plan && plan.imagined_trajectory) || []
  return (
    <Card title="🔮 Imagined Trajectory" hint="most-visited MCTS path" span={2}>
      {traj.length === 0 ? <Empty note="no rollout" /> : (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center' }}>
          {traj.map((s, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
                <Badge text={s.action} color={actionColor(s.action)} />
                <span style={{ fontSize: 10, color: rColor(s.value_R) }}>{fmt(s.value_R, 2)}R</span>
              </div>
              {i < traj.length - 1 && <span style={{ color: T.muted }}>→</span>}
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

export default function WorldModelPanel({ intervalMs = 5000 }) {
  const [state, setState] = useState({ loading: true })

  useEffect(() => {
    let alive = true
    const tick = async () => {
      try {
        const data = await getJSON('/api/brain/worldmodel')
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
            textAlign: 'center' }}>🌀<div style={{ marginTop: 8 }}>loading Imagination…</div></div></div>
  }
  const d = state.data
  return (
    <div style={wrap}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 12 }}>
        <span style={{ fontWeight: 700, fontSize: 16, color: T.text }}>🌀 Imagination · World-Model</span>
        {d && <Badge text={`${d.backend} backend`} color={d.backend === 'torch' ? T.good : T.accent} />}
        {d && d.demo && <Badge text="demo series" color={T.warn} />}
        <div style={{ flex: 1 }} />
        {state.stamp && <span style={{ fontSize: 10, color: T.muted }}>updated {state.stamp.toLocaleTimeString()}</span>}
      </div>

      {state.error || !d ? (
        <Empty note={state.error || 'world-model unavailable'} />
      ) : d.available === false ? (
        <Empty note={d.error || 'world-model unavailable'} />
      ) : (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 12 }}>
            <DecisionCard title="🎯 Entry / Direction" plan={d.entry_decision} hint="flat book" />
            <DecisionCard title="🛡 Manage Open Long" plan={d.manage_decision} hint="exit · stop · trail" />
            <TrajectoryCard plan={d.entry_decision} />
          </div>
          <div style={{ marginTop: 10, fontSize: 10, color: T.muted, lineHeight: 1.5 }}>
            MuZero MCTS over a learned market dynamics model · imagined_R = search value in
            R-multiples · adapted from vendor/muzero_general. {d.note ? '' : ''}
          </div>
        </>
      )}
    </div>
  )
}
