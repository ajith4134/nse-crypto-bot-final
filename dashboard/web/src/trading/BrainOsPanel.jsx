// BrainOsPanel.jsx — "🖥️ Brain OS" (owner ask 2026-07-13: the combined brain acts as an
// OS with its own RAM). A system-monitor 'top' for the resident kernel: uptime, a bounded
// RAM working-memory meter, an honest process table (kernel + learn-loop truth + cross-
// process lobes by state-file heartbeat), store residency, and the syscall surface.
// Everything is REAL: /api/brain/os reads live kernel state; the focus control round-trips.
import { useEffect, useState } from 'react'
import { T } from './theme.js'

async function getJSON(url) {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json()
}
async function postJSON(url, body) {
  const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' },
                               body: JSON.stringify(body) })
  return r.json()
}

function agefmt(s) {
  if (s == null) return '—'
  if (s < 90) return `${Math.round(s)}s`
  if (s < 5400) return `${Math.round(s / 60)}m`
  if (s < 129600) return `${(s / 3600).toFixed(1)}h`
  return `${(s / 86400).toFixed(1)}d`
}
function bytesfmt(b) {
  if (b == null) return '—'
  if (b < 1024) return `${b} B`
  if (b < 1048576) return `${(b / 1024).toFixed(1)} KB`
  return `${(b / 1048576).toFixed(1)} MB`
}
const STATE_COLOR = { RUNNING: T.good, SLEEPING: T.warn, STOPPED: T.muted, DEAD: T.bad }
const KIND_ICON = { kernel: '🧠', lobe: '🫀', funnel: '⚙️' }

export default function BrainOsPanel({ intervalMs = 10000 }) {
  const [state, setState] = useState({ loading: true })
  const [focus, setFocus] = useState('')
  const [busy, setBusy] = useState(false)

  const load = async () => {
    try { setState({ data: await getJSON('/api/brain/os'), stamp: new Date() }) }
    catch (e) { setState({ error: String(e.message || e) }) }
  }
  useEffect(() => {
    let alive = true
    const tick = async () => { if (alive) await load() }
    tick()
    const t = setInterval(tick, intervalMs)
    return () => { alive = false; clearInterval(t) }
  }, [intervalMs])

  const setFocusOp = async () => {
    if (!focus.trim()) return
    setBusy(true)
    try { await postJSON('/api/brain/os', { op: 'focus', segment: focus.trim() }); await load() }
    finally { setBusy(false); setFocus('') }
  }

  const wrap = { background: T.bg, border: `1px solid ${T.border}`, borderRadius: 12,
                 padding: 14, color: T.text, fontFamily: 'system-ui, sans-serif' }
  if (state.loading) return <div style={wrap}><div style={{ color: T.muted, fontSize: 13 }}>🖥️ booting Brain OS…</div></div>
  const d = state.data
  if (state.error || !d || d.warming) {
    return <div style={wrap}><div style={{ color: T.muted, fontSize: 12 }}>
      {d?.warming ? '🖥️ Brain OS kernel warming (post-restart) — RAM/process table precomputing…'
                  : `Brain OS unavailable: ${state.error || d?.error}`}</div></div>
  }
  const wm = d.working_memory || {}
  const ramPct = wm.max_bytes ? Math.min(100, (wm.bytes_used / wm.max_bytes) * 100) : 0

  return (
    <div style={wrap}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 10, flexWrap: 'wrap' }}>
        <span style={{ fontWeight: 700, fontSize: 16 }}>🖥️ Brain OS</span>
        <span style={{ fontSize: 12, fontWeight: 800, color: d.booted ? T.good : T.warn }}>
          {d.booted ? 'RESIDENT' : 'NOT BOOTED'}</span>
        <span style={{ fontSize: 11, color: T.muted }}>uptime {agefmt(d.uptime_secs)} · {d.boots} boots</span>
        <div style={{ flex: 1 }} />
        {state.stamp && <span style={{ fontSize: 10, color: T.muted }}>updated {state.stamp.toLocaleTimeString()}</span>}
      </div>

      {/* RAM working-memory meter — bounded, honest bytes */}
      <div style={{ marginBottom: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: T.muted, marginBottom: 3 }}>
          <span>RAM working memory — {wm.pinned} pinned · {wm.hot} hot · {wm.evictions} evicted</span>
          <span>{bytesfmt(wm.bytes_used)} / {bytesfmt(wm.max_bytes)}</span>
        </div>
        <div style={{ height: 10, background: '#0b0f16', borderRadius: 6, overflow: 'hidden', border: `1px solid ${T.border}` }}>
          <div style={{ width: `${ramPct}%`, height: '100%',
                        background: ramPct > 90 ? T.bad : ramPct > 60 ? T.warn : T.good }} />
        </div>
        <div style={{ fontSize: 10, color: T.muted, marginTop: 3 }}>
          store: {d.store?.neurons?.toLocaleString()} neurons RAM-resident · {d.store?.links?.toLocaleString()} links
          {wm.focus?.segment && <> · focus <b style={{ color: T.accent }}>{wm.focus.segment}</b></>}
        </div>
      </div>

      {/* process table */}
      <div style={{ border: `1px solid ${T.border}`, borderRadius: 8, overflow: 'hidden', marginBottom: 10 }}>
        {(d.processes || []).map((p) => (
          <div key={p.name} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px',
                                     borderBottom: `1px solid ${T.border}`, fontSize: 12 }}>
            <span style={{ width: 16 }}>{KIND_ICON[p.kind] || '·'}</span>
            <span style={{ flex: 1, fontWeight: 600 }}>{p.name}</span>
            <span style={{ fontSize: 10, color: T.muted, minWidth: 44, textAlign: 'right' }}>{agefmt(p.age_secs)}</span>
            <span style={{ fontSize: 10, fontWeight: 800, minWidth: 66, textAlign: 'right',
                           color: STATE_COLOR[p.state] || T.muted }}>{p.state}</span>
          </div>
        ))}
      </div>
      <div style={{ fontSize: 10, color: T.muted, marginBottom: 10 }}>
        cross-process lobes shown by state-file heartbeat (not shared memory) — honest liveness ·
        syscalls: {(d.syscalls || []).join(' · ')}
      </div>

      {/* focus control — real round-trip */}
      <div style={{ display: 'flex', gap: 6 }}>
        <input value={focus} onChange={(e) => setFocus(e.target.value)}
               placeholder="set kernel focus (segment)…"
               style={{ flex: 1, fontSize: 12, padding: '5px 8px', background: '#0b0f16',
                        color: T.text, border: `1px solid ${T.border}`, borderRadius: 6 }} />
        <button onClick={setFocusOp} disabled={busy || !focus.trim()}
                style={{ fontSize: 12, padding: '5px 12px', cursor: 'pointer', background: '#1b2433',
                         color: T.accent, border: `1px solid ${T.border}`, borderRadius: 6 }}>
          {busy ? '…' : 'focus'}</button>
      </div>
    </div>
  )
}
