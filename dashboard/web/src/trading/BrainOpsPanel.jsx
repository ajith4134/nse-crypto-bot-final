// BrainOpsPanel.jsx — "🧠 Brain Ops"
// Wave-0 ④ (2026-07-04): surfaces the brain subsystems that HAD backend endpoints but no panel
// (independent-audit found 24 such endpoints). Shows REAL live data where cheap — boss directives,
// R&D inventions, mind event-bus stats — and an HONEST real/demo catalog of the heavier subsystems
// (each fetchable at its own path). No fabricated values. Polls /api/brain/ops (~8s), inline Dark-Pro.
import { useEffect, useState } from 'react'
import { T } from './theme.js'

async function getJSON(url) {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json()
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
function Stat({ label, value }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, padding: '2px 0' }}>
      <span style={{ color: T.muted }}>{label}</span>
      <span style={{ color: T.text, fontWeight: 600 }}>{value}</span>
    </div>
  )
}

export default function BrainOpsPanel({ intervalMs = 8000 }) {
  const [state, setState] = useState({ loading: true })

  useEffect(() => {
    let alive = true
    const tick = async () => {
      try {
        const data = await getJSON('/api/brain/ops')
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
            textAlign: 'center' }}>🧠<div style={{ marginTop: 8 }}>loading Brain Ops…</div></div></div>
  }

  const d = state.data || {}
  const live = d.live || {}
  const boss = live.boss || {}
  const rnd = live.rnd || {}
  const mind = live.mind_bus || {}
  const directives = Array.isArray(boss.directives) ? boss.directives
                     : (boss.active || boss.list || [])
  const nDirectives = boss.n != null ? boss.n : (Array.isArray(directives) ? directives.length : '—')

  return (
    <div style={wrap}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 12 }}>
        <span style={{ fontWeight: 700, fontSize: 16, color: T.text }}>🧠 Brain Ops</span>
        <span style={{ color: T.muted, fontSize: 11 }}>subsystems previously hidden from the dashboard</span>
        <div style={{ flex: 1 }} />
        {state.stamp && <span style={{ fontSize: 10, color: T.muted }}>updated {state.stamp.toLocaleTimeString()}</span>}
      </div>

      {state.error ? <Empty note={state.error} /> : (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 12 }}>
            <Card title="🎖 Boss directives" hint="live">
              <Stat label="in force" value={nDirectives} />
              {Array.isArray(directives) && directives.slice(0, 4).map((x, i) => (
                <div key={i} style={{ fontSize: 11, color: T.text, padding: '2px 0' }}>
                  • {typeof x === 'string' ? x : (x.text || x.name || x.goal || JSON.stringify(x).slice(0, 60))}
                </div>
              ))}
              {(!directives || directives.length === 0) && <Empty note="none in force" />}
            </Card>
            <Card title="🔬 R&D drive" hint="inventions">
              {Object.keys(rnd).length === 0 ? <Empty /> :
                Object.entries(rnd).slice(0, 6).map(([k, v]) => (
                  <Stat key={k} label={k} value={typeof v === 'object' ? (Array.isArray(v) ? v.length : Object.keys(v).length) : String(v)} />
                ))}
            </Card>
            <Card title="🌊 Mind event bus" hint="live, ephemeral">
              <Stat label="events" value={mind.n != null ? mind.n : '—'} />
              <Stat label="last id" value={mind.last_id != null ? mind.last_id : '—'} />
              {mind.by_kind && Object.entries(mind.by_kind).slice(0, 4).map(([k, v]) => (
                <Stat key={k} label={k} value={v} />
              ))}
            </Card>
          </div>

          <div style={{ marginTop: 12, fontSize: 12, fontWeight: 600, color: T.muted }}>
            Subsystem endpoints ({(d.subsystems || []).length}) — honest real/demo status:
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
                        gap: 8, marginTop: 8 }}>
            {(d.subsystems || []).map((s) => (
              <div key={s.key} style={{ background: T.panel, border: `1px solid ${T.border}`,
                     borderRadius: 8, padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: 4 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontSize: 12, fontWeight: 600, color: T.text }}>{s.label}</span>
                  <Badge text={s.real ? 'real' : 'demo'} color={s.real ? T.good : T.warn} />
                </div>
                <span style={{ fontSize: 10, color: T.muted, fontFamily: 'monospace' }}>{s.path}</span>
              </div>
            ))}
          </div>
          {d.error && <div style={{ marginTop: 8 }}><Empty note={`live: ${d.error}`} /></div>}
          <div style={{ marginTop: 10, fontSize: 10, color: T.muted, lineHeight: 1.5 }}>
            Recovered by the independent-audit (endpoints defined but no panel). "demo" = offline
            deterministic snapshot (real mode needs network/embedding models) — honestly labelled, never faked.
          </div>
        </>
      )}
    </div>
  )
}
