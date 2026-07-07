// AppSchoolPanel.jsx — "App Driving School": what the brain has LEARNED about driving each
// broker app, like a self-driving car. Shows the golden routes it discovered to each market-data
// kind (which control led there + the endpoint), goal coverage, and a button to run a learning
// pass. Honest: every route was learned from the app's OWN captured traffic. GET ~8s.
import { useEffect, useRef, useState } from 'react'
import { T } from './theme.js'

const API = '/api/trading/app_school'

async function getJSON(u) { const r = await fetch(u); if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() }
async function post(b) { const r = await fetch(API, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }); return r.json() }

function Chip({ text, color }) {
  return <span style={{ fontSize: 10, fontWeight: 600, color: color || T.muted, border: `1px solid ${color || T.border}`, borderRadius: 6, padding: '1px 6px', marginRight: 4, marginBottom: 4, display: 'inline-block' }}>{text}</span>
}

export default function AppSchoolPanel({ broker = 'binance', intervalMs = 8000 }) {
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
  const alive = useRef(true)

  useEffect(() => {
    alive.current = true
    const refresh = async () => {
      try { const d = await getJSON(API); if (alive.current) { setData(d); setErr(null) } }
      catch (e) { if (alive.current) setErr(String(e.message || e)) }
    }
    refresh(); const t = setInterval(refresh, intervalMs)
    return () => { alive.current = false; clearInterval(t) }
  }, [intervalMs])

  const learn = async () => {
    setBusy(true); setMsg('')
    try { const r = await post({ op: 'explore', broker }); setMsg(r.ok ? '🧭 Learning run started — routes will appear as it explores.' : `error: ${r.error}`) }
    catch (e) { setMsg(String(e.message || e)) } finally { if (alive.current) setBusy(false) }
  }

  const card = { background: T.panel, border: `1px solid ${T.border}`, borderRadius: 12, padding: 14 }
  if (err) return <div style={{ ...card, color: T.bad || '#ff6b6b' }}>App School: {err}</div>
  if (!data) return <div style={{ ...card, color: T.muted }}>Loading App School…</div>

  const map = data.map || {}
  const b = map[broker] || { learned: [], missing: [], pct: 0, routes: {} }
  const stats = (data.stats) || {}

  return (
    <div style={card}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <div style={{ fontSize: 14, fontWeight: 800, color: T.text }}>🧭 App Driving School — {broker}
          {/* honest market badge — explains WHY a broker isn't gaining coverage (no live feed) */}
          {b.market && <span title={b.market.note} style={{ marginLeft: 8, fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 10, verticalAlign: 'middle',
            background: b.market.open ? 'rgba(62,207,142,0.15)' : 'rgba(230,184,0,0.15)',
            color: b.market.open ? (T.good || '#3ecf8e') : (T.warn || '#e6b800'),
            border: `1px solid ${b.market.open ? (T.good || '#3ecf8e') : (T.warn || '#e6b800')}` }}>
            {b.market.open ? '● LIVE' : '○ market closed'}</span>}
        </div>
        <button onClick={learn} disabled={busy} style={{ background: T.panel2 || '#1a1f2b', color: busy ? T.muted : (T.accent || '#5b9dff'), border: `1px solid ${T.accent || '#5b9dff'}`, borderRadius: 8, padding: '6px 12px', cursor: busy ? 'wait' : 'pointer', fontSize: 12, fontWeight: 700 }}>Learn the app</button>
      </div>
      {b.market && !b.market.open && <div style={{ fontSize: 11, color: T.warn || '#e6b800', marginBottom: 8 }}>⏸ {b.market.note}</div>}
      <div style={{ fontSize: 11, color: T.muted, marginBottom: 10 }}>
        The brain explores the logged-in app read-only and learns the route to each market-data feature from its own traffic — no hardcoded pages.
      </div>

      <div style={{ display: 'flex', gap: 16, marginBottom: 10, alignItems: 'baseline', flexWrap: 'wrap' }}>
        <div><span style={{ fontSize: 22, fontWeight: 800, color: (b.pct >= 60 ? (T.good || '#3ecf8e') : T.accent) }}>{b.pct || 0}%</span> <span style={{ fontSize: 11, color: T.muted }}>features mapped</span></div>
        <div><span style={{ fontSize: 16, fontWeight: 800, color: T.text }}>{b.pages_found || 0}</span> <span style={{ fontSize: 11, color: T.muted }}>pages found</span></div>
        <div><span style={{ fontSize: 16, fontWeight: 800, color: T.text }}>{b.links_found || 0}</span> <span style={{ fontSize: 11, color: T.muted }}>links saved</span></div>
        <div style={{ fontSize: 11, color: T.muted }}>explorations {stats.explorations || 0} · clicks {stats.clicks || 0} · routes {stats.routes_learned || 0} · popups closed {stats.popups_closed || 0}</div>
      </div>

      <div style={{ fontSize: 12, fontWeight: 700, color: T.text, marginBottom: 4 }}>Learned routes</div>
      {Object.keys(b.routes || {}).length === 0
        ? <div style={{ fontSize: 12, color: T.muted }}>Nothing learned yet — click &quot;Learn the app.&quot;</div>
        : Object.entries(b.routes).map(([kind, r], i) => (
          <div key={i} style={{ borderTop: `1px solid ${T.border}`, padding: '6px 0', display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'baseline' }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: (T.good || '#3ecf8e') }}>{kind}</span>
            <span style={{ fontSize: 11, color: T.muted, textAlign: 'right', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              via <b style={{ color: T.text }}>{r.via || '—'}</b> · {(r.url || '').replace('https://', '')} {r.n ? `· seen ${r.n}×` : ''}
            </span>
          </div>
        ))}

      {b.missing && b.missing.length > 0 && (
        <div style={{ marginTop: 8 }}>
          <span style={{ fontSize: 11, color: T.muted }}>still to find: </span>
          {b.missing.map((m, i) => <Chip key={i} text={m} />)}
        </div>
      )}
      {msg && <div style={{ marginTop: 8, fontSize: 12, color: T.accent }}>{msg}</div>}
    </div>
  )
}
