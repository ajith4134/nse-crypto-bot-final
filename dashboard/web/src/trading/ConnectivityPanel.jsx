// ConnectivityPanel.jsx — the self-healing wiring watchdog. Flags NEW orphan modules / dead API
// endpoints since the accepted baseline (a regression = something that WAS wired came unwired), so
// nothing silently disconnects. Backlog shown for reference. Green = no new regressions. Honest:
// heuristic early-warning; the grimp-based /independent-audit is the source of truth.
import { useEffect, useRef, useState } from 'react'
import { T } from './theme.js'

const API = '/api/trading/connectivity'
async function getJSON() { const r = await fetch(API); if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() }
async function post(b) { const r = await fetch(API, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }); return r.json() }

export default function ConnectivityPanel({ intervalMs = 20000 }) {
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)
  const [msg, setMsg] = useState('')
  const alive = useRef(true)

  const refresh = async () => { try { const d = await getJSON(); if (alive.current) { setData(d); setErr(null) } } catch (e) { if (alive.current) setErr(String(e.message || e)) } }
  useEffect(() => { alive.current = true; refresh(); const t = setInterval(refresh, intervalMs); return () => { alive.current = false; clearInterval(t) } }, [intervalMs])

  const rebaseline = async () => { const r = await post({ op: 'rebaseline' }); setMsg(r.rebaselined ? `✅ Baseline updated (${r.orphans_baselined} modules).` : 'error'); refresh() }

  const card = { background: T.panel, border: `1px solid ${T.border}`, borderRadius: 12, padding: 14 }
  if (err) return <div style={{ ...card, color: T.bad || '#ff6b6b' }}>Connectivity: {err}</div>
  if (!data) return <div style={{ ...card, color: T.muted }}>Loading connectivity…</div>

  const healthy = data.healthy
  const newO = data.new_orphans || []
  const newD = data.new_dead_endpoints || []
  const dot = healthy ? (T.good || '#3ecf8e') : (T.bad || '#ff6b6b')

  return (
    <div style={card}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
        <div style={{ fontSize: 14, fontWeight: 800, color: T.text }}>
          <span style={{ color: dot }}>●</span> Wiring watchdog — {healthy ? 'all connected' : 'regression!'}
        </div>
        <button onClick={rebaseline} style={{ background: T.panel2 || '#1a1f2b', color: T.accent, border: `1px solid ${T.accent}`, borderRadius: 8, padding: '5px 11px', cursor: 'pointer', fontSize: 12, fontWeight: 700 }}>Accept as baseline</button>
      </div>
      <div style={{ fontSize: 11, color: T.muted, marginBottom: 10 }}>
        Watches for a module/endpoint that WAS wired coming unwired. {data.module_count} modules · backlog {data.backlog_orphans} orphans / {data.backlog_dead_endpoints} idle endpoints (baselined, not regressions).
      </div>
      {healthy
        ? <div style={{ fontSize: 12, color: (T.good || '#3ecf8e') }}>✓ No new disconnections since baseline — everything that was wired is still wired.</div>
        : (
          <div>
            {newO.length > 0 && <div style={{ fontSize: 12, color: (T.bad || '#ff6b6b'), marginBottom: 4 }}>NEW orphan modules: {newO.join(', ')}</div>}
            {newD.length > 0 && <div style={{ fontSize: 12, color: (T.bad || '#ff6b6b') }}>NEW dead endpoints: {newD.join(', ')}</div>}
          </div>
        )}
      {msg && <div style={{ marginTop: 8, fontSize: 12, color: T.accent }}>{msg}</div>}
    </div>
  )
}
