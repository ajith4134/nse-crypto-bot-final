// OcularCortexPanel.jsx — the brain's ultra-advanced eyes + visual memory (Dark Pro UI).
// HONEST view of the Ocular Cortex: which FREE vision providers are online (no GPU, no paid
// API), how many broker screens were perceived / were novel / got a free-VLM read, the
// consolidated LayoutMemory (golden paths + known data kinds per page, iconic→working→habit),
// the captured internal endpoints (network interception registry) + live data kinds, and how
// many trade decisions have a linked visual frame. Self-fetching: GET /api/trading/ocular ~8s.
import { useEffect, useRef, useState } from 'react'
import { T } from './theme.js'

const URL_ = '/api/trading/ocular'

async function getJSON(url) {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json()
}

async function postJSON(url, body) {
  const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json()
}

function Stat({ label, value, color }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <span style={{ fontSize: 10, color: T.muted, textTransform: 'uppercase', letterSpacing: 0.4 }}>{label}</span>
      <span style={{ fontSize: 15, fontWeight: 700, color: color || T.text }}>{value}</span>
    </div>
  )
}

const CONSOLID = { consolidated: T.good || '#3ecf8e', working: T.accent || '#5b9dff', iconic: T.muted }

function Chip({ text, color }) {
  return (
    <span style={{
      fontSize: 10, fontWeight: 600, color: color || T.muted, border: `1px solid ${color || T.border}`,
      borderRadius: 6, padding: '1px 6px', marginRight: 4, marginBottom: 4, display: 'inline-block',
      whiteSpace: 'nowrap' }}>{text}</span>
  )
}

export default function OcularCortexPanel({ intervalMs = 8000 }) {
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)
  const [sources, setSources] = useState(null)
  const [busy, setBusy] = useState(null)
  const alive = useRef(true)

  const loadSources = async () => {
    try { const s = await getJSON('/api/trading/broker_sources'); if (alive.current) setSources(s.sources || {}) } catch { /* keep last */ }
  }

  const toggleSource = async (broker, next) => {
    setBusy(broker)
    try { const r = await postJSON('/api/trading/broker_sources', { op: 'set', broker, public: next }); if (alive.current) setSources(r.sources || {}) }
    catch (e) { if (alive.current) setErr(String(e.message || e)) }
    finally { if (alive.current) setBusy(null) }
  }

  useEffect(() => {
    alive.current = true
    const refresh = async () => {
      try { const d = await getJSON(URL_); if (alive.current) { setData(d); setErr(null) } }
      catch (e) { if (alive.current) setErr(String(e.message || e)) }
      loadSources()
    }
    refresh()
    const t = setInterval(refresh, intervalMs)
    return () => { alive.current = false; clearInterval(t) }
  }, [intervalMs])

  const card = { background: T.panel, border: `1px solid ${T.border}`, borderRadius: 12, padding: 14 }

  if (err) return <div style={{ ...card, color: T.bad || '#ff6b6b' }}>Ocular Cortex: {err}</div>
  if (!data) return <div style={{ ...card, color: T.muted }}>Loading Ocular Cortex…</div>
  if (data.available === false)
    return <div style={{ ...card, color: T.muted }}>Ocular Cortex unavailable: {data.error}</div>

  const cortex = data.cortex || {}
  const stats = cortex.stats || {}
  const layouts = cortex.layouts || {}
  const interception = data.interception || {}
  const liveKinds = interception.live_kinds || {}
  const online = data.vision_online

  const BROKER_LABEL = { binance: 'Binance', angelone: 'Angel One' }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={card}>
        <div style={{ fontSize: 13, fontWeight: 700, color: T.text, marginBottom: 4 }}>Data source — public vs my account</div>
        <div style={{ fontSize: 11, color: T.muted, marginBottom: 10 }}>
          Turn a broker&apos;s PUBLIC data OFF → the brain screens from your LOGGED-IN account page instead (needs the account connected).
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
          {sources && Object.keys(sources).length > 0 ? Object.entries(sources).map(([b, s]) => (
            <div key={b} style={{ display: 'flex', alignItems: 'center', gap: 8, border: `1px solid ${T.border}`, borderRadius: 10, padding: '8px 10px' }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: T.text }}>{BROKER_LABEL[b] || b}</span>
              <button onClick={() => toggleSource(b, !s.public)} disabled={busy === b} style={{
                background: s.public ? (T.accent || '#5b9dff') : T.panel2, color: s.public ? '#fff' : (T.good || '#3ecf8e'),
                border: `1px solid ${s.public ? (T.accent || '#5b9dff') : (T.good || '#3ecf8e')}`, borderRadius: 8, padding: '5px 12px',
                cursor: busy === b ? 'wait' : 'pointer', fontSize: 12, fontWeight: 700, minWidth: 132, opacity: busy === b ? 0.6 : 1 }}>
                {s.public ? 'PUBLIC DATA: ON' : 'ACCOUNT-FIRST (public off)'}
              </button>
            </div>
          )) : <span style={{ fontSize: 12, color: T.muted }}>loading sources…</span>}
        </div>
      </div>

      <div style={card}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <div style={{ fontSize: 15, fontWeight: 800, color: T.text }}>👁️ Ocular Cortex — eyes &amp; visual memory</div>
          <span style={{ fontSize: 11, fontWeight: 700, color: online ? (T.good || '#3ecf8e') : T.muted }}>
            {online ? 'FREE VISION ONLINE' : 'no vision provider'}
          </span>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
          <Stat label="frames perceived" value={stats.frames ?? 0} />
          <Stat label="novel layouts" value={stats.novel ?? 0} color={T.accent} />
          <Stat label="free-VLM reads" value={stats.vision_reads ?? 0} />
          <Stat label="linked decisions" value={cortex.linked_decisions ?? 0} color={T.good} />
        </div>
        <div style={{ marginTop: 10 }}>
          {(data.vision_providers || []).map((p, i) => <Chip key={i} text={p} color={T.accent} />)}
        </div>
      </div>

      <div style={card}>
        <div style={{ fontSize: 13, fontWeight: 700, color: T.text, marginBottom: 8 }}>
          Layout memory — golden paths (broker/page)
        </div>
        {Object.keys(layouts).length === 0
          ? <div style={{ color: T.muted, fontSize: 12 }}>No layouts learned yet — the brain consolidates each page it sees.</div>
          : Object.entries(layouts).map(([key, m]) => (
            <div key={key} style={{ borderTop: `1px solid ${T.border}`, padding: '8px 0', display: 'flex',
              justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: T.text }}>{key}</div>
                <div style={{ marginTop: 4 }}>
                  {(m.kinds || []).map((k, i) => <Chip key={i} text={k} />)}
                </div>
              </div>
              <div style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                <div style={{ fontSize: 12, color: T.muted }}>{m.controls_known} controls · {m.n_seen}× seen</div>
                <div style={{ fontSize: 11, color: CONSOLID[m.consolidation] || T.muted, fontWeight: 700 }}>
                  {(m.consolidation || '').toUpperCase()}
                </div>
              </div>
            </div>
          ))}
      </div>

      <div style={card}>
        <div style={{ fontSize: 13, fontWeight: 700, color: T.text, marginBottom: 8 }}>
          Network interception — the app&apos;s own data ({interception.captured ?? 0} captured)
        </div>
        {Object.keys(liveKinds).length === 0
          ? <div style={{ color: T.muted, fontSize: 12 }}>No live data captured yet — opens as the brain navigates a broker app.</div>
          : <div>{Object.entries(liveKinds).map(([k, age], i) =>
              <Chip key={i} text={`${k} · ${age}s ago`} color={age < 30 ? (T.good || '#3ecf8e') : T.muted} />)}
            </div>}
        <div style={{ marginTop: 8, fontSize: 11, color: T.muted }}>
          {Object.entries(interception.registry || {}).map(([b, r], i) =>
            <span key={i} style={{ marginRight: 12 }}>{b}: {r.endpoints} endpoints ({(r.kinds || []).join(', ')})</span>)}
        </div>
      </div>
    </div>
  )
}
