// GoalOpsPanel.jsx — "🎯 Goal & Rails (owner goal 2026-07-07)"
// Surfaces the W1-W8 evidence spine with REAL data only:
//   goal scoreboard (/api/trading/goal)      — per-segment verdicts vs goal.yaml
//   evidence lane  (/api/trading/evidence)   — autonomy gates + watchdog alarms
//   surface rails  (/api/trading/surface)    — optimizer modes + last rule changes
//   scouts         (/api/trading/scouts)     — consensus events (Sophie/Ross)
//   track record   (/api/trading/track_record) — top actors by runs
//   ui_data        (/api/trading/ui_data)    — eyes' capture coverage + UI-only mode
//   briefing       (/api/trading/briefing)   — today's morning-brief stance
// Poll ~10s; every number comes straight from its endpoint. No fabricated values.
import { useEffect, useState } from 'react'
import { T } from './theme.js'

async function getJSON(url) {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json()
}

const VERDICT_COLOR = {
  'goal-met': T.good, 'toward-goal': T.good, 'off-track': T.warn || '#d9a441',
  'failing': T.bad, 'drawdown-breach': T.bad, 'no-data': T.muted,
}

function Badge({ text, color }) {
  return <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: 0.5, color,
    border: `1px solid ${color}`, borderRadius: 4, padding: '1px 6px',
    textTransform: 'uppercase', whiteSpace: 'nowrap' }}>{text}</span>
}
function Card({ title, hint, children }) {
  return (
    <div style={{ background: T.panel, border: `1px solid ${T.border}`, borderRadius: 10,
                  padding: 12, minWidth: 0, boxSizing: 'border-box' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 8 }}>
        <span style={{ fontWeight: 600, fontSize: 13, color: T.text }}>{title}</span>
        {hint && <span style={{ color: T.muted, fontSize: 11 }}>{hint}</span>}
      </div>
      {children}
    </div>
  )
}
function Row({ k, v, color }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, padding: '2px 0' }}>
      <span style={{ color: T.muted, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis' }}>{k}</span>
      <span style={{ color: color || T.text, fontWeight: 600, whiteSpace: 'nowrap' }}>{v}</span>
    </div>
  )
}
function Empty({ note }) { return <div style={{ color: T.muted, fontSize: 12 }}>{note || 'no data yet'}</div> }

export default function GoalOpsPanel({ intervalMs = 10000 }) {
  const [s, setS] = useState({ loading: true })

  useEffect(() => {
    let alive = true
    async function tick() {
      try {
        const [goal, evidence, surface, scouts, track, ui, brief] = await Promise.all([
          getJSON('/api/trading/goal').catch(e => ({ error: String(e) })),
          getJSON('/api/trading/evidence').catch(e => ({ error: String(e) })),
          getJSON('/api/trading/surface').catch(e => ({ error: String(e) })),
          getJSON('/api/trading/scouts').catch(e => ({ error: String(e) })),
          getJSON('/api/trading/track_record').catch(e => ({ error: String(e) })),
          getJSON('/api/trading/ui_data').catch(e => ({ error: String(e) })),
          getJSON('/api/trading/briefing').catch(e => ({ error: String(e) })),
        ])
        if (alive) setS({ loading: false, goal, evidence, surface, scouts, track, ui, brief })
      } catch (e) {
        if (alive) setS({ loading: false, error: String(e) })
      }
    }
    tick()
    const t = setInterval(tick, intervalMs)
    return () => { alive = false; clearInterval(t) }
  }, [intervalMs])

  if (s.loading) return <Empty note="loading goal & rails…" />
  const segs = Object.entries((s.goal && s.goal.segments) || {})
  const alarms = ((s.evidence || {}).watchdogs || {}).alarms || []
  const gates = Object.entries((s.evidence || {}).segments || {})
  const modes = (s.surface || {}).modes || {}
  const changes = ((s.surface || {}).recent_changes || []).slice(-4).reverse()
  const consensus = ((s.scouts || {}).recent_consensus || []).slice(-4).reverse()
  const actors = ((s.track || {}).actors || []).slice(0, 6)
  const ui = s.ui || {}
  const stance = (((s.brief || {}).sections) || {}).stance || {}

  return (
    <div style={{ display: 'grid', gap: 10,
                  gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))' }}>
      <Card title="🎯 Goal scoreboard" hint="trailing 30d vs goal.yaml">
        {segs.length === 0 ? <Empty /> : segs.map(([k, v]) => (
          <div key={k} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '3px 0' }}>
            <span style={{ flex: 1, fontSize: 12, color: T.text }}>{k}</span>
            <span style={{ fontSize: 11, color: T.muted }}>
              {v.n_trades} trades · {(v.return_window * 100).toFixed(1)}%
            </span>
            <Badge text={v.verdict} color={VERDICT_COLOR[v.verdict] || T.muted} />
          </div>
        ))}
      </Card>

      <Card title="🛡 Watchdogs & autonomy" hint="evidence lane">
        {alarms.length === 0
          ? <Row k="alarms" v="none" color={T.good} />
          : alarms.map((a, i) => <div key={i} style={{ fontSize: 11, color: T.bad, padding: '2px 0' }}>{a}</div>)}
        {gates.map(([k, v]) => (
          <Row key={k} k={`${k} autonomy`} v={v.autonomy && v.autonomy.all_pass ? 'EARNED' : 'not yet'}
               color={v.autonomy && v.autonomy.all_pass ? T.good : T.muted} />
        ))}
        {gates.length === 0 && <Empty note="gates build as cycles run" />}
      </Card>

      <Card title="📏 Rails (W2)" hint="one variable at a time">
        {Object.entries(modes).map(([k, v]) => (
          <Row key={k} k={k} v={v} color={v === 'live' ? T.good : T.muted} />
        ))}
        {changes.map((c, i) => (
          <div key={i} style={{ fontSize: 11, color: T.muted, padding: '2px 0' }}>
            v{c.version} {c.knob}: {String(c.old)} → <span style={{ color: T.text }}>{String(c.new)}</span>
          </div>
        ))}
        {changes.length === 0 && <Empty note="no rule changes yet" />}
      </Card>

      <Card title="🕵️ Smart-money consensus" hint={`≥${(s.scouts || {}).min_agree || '?'} scouts agree`}>
        {consensus.length === 0 ? <Empty note="honest quiet — no multi-scout agreement" />
          : consensus.map((c, i) => (
            <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '3px 0' }}>
              <Badge text={c.direction} color={c.direction === 'long' ? T.good : T.bad} />
              <span style={{ flex: 1, fontSize: 12, color: T.text }}>{c.symbol}</span>
              <span style={{ fontSize: 11, color: T.muted }}>{c.n_scouts} scouts</span>
            </div>
          ))}
      </Card>

      <Card title="📈 Track records" hint="trust follows the record">
        {actors.length === 0 ? <Empty /> : actors.map((a) => (
          <Row key={a.actor} k={a.actor.replace(/^.*?:/, '')}
               v={`${a.runs} runs${a.win_rate != null ? ` · ${(a.win_rate * 100).toFixed(0)}%` : ''}`}
               color={a.rule_of_three ? T.good : T.text} />
        ))}
      </Card>

      <Card title="👁 UI-only data" hint="eyes' capture coverage">
        <Row k="mode" v={ui.enabled ? 'UI-ONLY ON' : 'warming'}
             color={ui.enabled ? T.good : T.muted} />
        <Row k="symbols indexed" v={String(ui.symbols ?? '—')} />
        <Row k="payloads fed" v={String(ui.fed ?? '—')} />
        <Row k="hit rate" v={ui.hit_rate == null ? '—' : `${(ui.hit_rate * 100).toFixed(0)}%`} />
        {Object.entries(stance).slice(0, 3).map(([k, v]) => (
          <div key={k} style={{ fontSize: 11, color: T.muted, padding: '2px 0' }}>
            {k}: <span style={{ color: T.text }}>{v}</span>
          </div>
        ))}
      </Card>
    </div>
  )
}
