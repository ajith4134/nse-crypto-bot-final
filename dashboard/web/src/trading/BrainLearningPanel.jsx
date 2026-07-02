// BrainLearningPanel.jsx — "🧠📚 Brain Learning & Web"
// Surfaces the autonomous learning/web layer: what the brain has READ (books/papers/articles →
// KnowledgeBrain), its live EPHEMERAL activity feed (what it did on the web + learned, clears on
// view), and PENDING login requests you answer in-panel. Controls round-trip to real endpoints.
// Polls /api/brain/learning (~6s). Inline-styled via ./theme.js.
import { useEffect, useState } from 'react'
import { T } from './theme.js'

async function getJSON(url) { const r = await fetch(url); if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() }
async function postJSON(url, body) {
  const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  return r.json()
}
function Stat({ label, value, color }) {
  return (<div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
    <span style={{ fontSize: 10, color: T.muted, textTransform: 'uppercase', letterSpacing: 0.4 }}>{label}</span>
    <span style={{ fontSize: 16, fontWeight: 700, color: color || T.text }}>{value}</span></div>)
}
const KIND_ICON = { opened: '🌐', read: '📖', learned: '💡', login_needed: '🔐', action: '⚙️', note: '•' }

export default function BrainLearningPanel({ intervalMs = 6000 }) {
  const [state, setState] = useState({ loading: true })
  const [topic, setTopic] = useState('')
  const [creds, setCreds] = useState({})       // site -> {field: value}
  const [busy, setBusy] = useState('')

  const refresh = async () => {
    try { const data = await getJSON('/api/brain/learning'); setState({ data, stamp: new Date() }) }
    catch (e) { setState({ error: String(e.message || e), stamp: new Date() }) }
  }
  useEffect(() => { refresh(); const t = setInterval(refresh, intervalMs); return () => clearInterval(t) }, [intervalMs])

  const learnTopic = async () => {
    if (!topic.trim()) return
    setBusy('learn'); await postJSON('/api/brain/learn', { op: 'topic', topic }); setTopic(''); setBusy(''); refresh()
  }
  const submitLogin = async (site, fields) => {
    setBusy(site); await postJSON('/api/trading/credentials', { op: 'submit', site, values: creds[site] || {} })
    setCreds((c) => ({ ...c, [site]: {} })); setBusy(''); refresh()
  }

  const wrap = { background: T.bg, border: `1px solid ${T.border}`, borderRadius: 12, padding: 14,
                 color: T.text, fontFamily: 'system-ui, sans-serif', boxSizing: 'border-box', width: '100%' }
  if (state.loading) return <div style={wrap}><div style={{ color: T.muted, fontSize: 13, padding: '24px 0', textAlign: 'center' }}>🧠📚<div style={{ marginTop: 8 }}>loading Brain Learning…</div></div></div>
  const d = state.data || {}
  const ks = (d.learner && d.learner.knowledge_stats) || {}
  const recent = (d.learner && d.learner.recent) || []
  const feed = d.activity || []
  const pending = d.pending_logins || []
  const inp = { background: T.panel || '#111', color: T.text, border: `1px solid ${T.gridline}`, borderRadius: 6, padding: '4px 8px', fontSize: 12 }
  const btn = (on) => ({ fontSize: 11, padding: '4px 10px', borderRadius: 6, cursor: 'pointer', border: `1px solid ${T.accent}`, background: on ? T.accent : 'transparent', color: on ? T.bg : T.accent })

  return (
    <div style={wrap}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 12 }}>
        <span style={{ fontWeight: 700, fontSize: 16 }}>🧠📚 Brain Learning &amp; Web</span>
        <span style={{ fontSize: 11, color: T.muted }}>reads · browses · self-evaluates</span>
        <div style={{ flex: 1 }} />
        {state.stamp && <span style={{ fontSize: 10, color: T.muted }}>updated {state.stamp.toLocaleTimeString()}</span>}
      </div>

      <div style={{ display: 'flex', gap: 20, marginBottom: 12, flexWrap: 'wrap' }}>
        <Stat label="documents" value={ks.docs ?? 0} color={T.accent} />
        <Stat label="chunks" value={ks.chunks ?? 0} />
        <Stat label="concepts" value={(ks.by_type && ks.by_type.concept) ?? ks.nodes ?? 0} color={T.good} />
        <Stat label="learned items" value={(d.learner && d.learner.n_learned) ?? 0} />
      </div>

      {/* learn a topic */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 12 }}>
        <input value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="teach the brain a topic (e.g. stochastic calculus)"
               style={{ ...inp, flex: 1 }} onKeyDown={(e) => e.key === 'Enter' && learnTopic()} />
        <button style={btn(busy === 'learn')} onClick={learnTopic}>{busy === 'learn' ? 'learning…' : 'Learn'}</button>
      </div>

      {/* pending login requests — answer in panel (encrypted server-side) */}
      {pending.length > 0 && (
        <div style={{ marginBottom: 12, border: `1px solid ${T.warn}`, borderRadius: 8, padding: 8 }}>
          <div style={{ fontSize: 11, color: T.warn, marginBottom: 6 }}>🔐 Brain needs a login (read-only) — values are encrypted, never shown again</div>
          {pending.map((p) => (
            <div key={p.site} style={{ marginBottom: 6 }}>
              <div style={{ fontSize: 12, marginBottom: 3 }}>{p.site} <span style={{ color: T.muted }}>— {p.note}</span></div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {(p.fields || []).map((f) => (
                  <input key={f} type={/pass|totp|secret/i.test(f) ? 'password' : 'text'} placeholder={f} style={{ ...inp, width: 130 }}
                         onChange={(e) => setCreds((c) => ({ ...c, [p.site]: { ...(c[p.site] || {}), [f]: e.target.value } }))} />
                ))}
                <button style={btn(busy === p.site)} onClick={() => submitLogin(p.site, p.fields)}>Send</button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ephemeral activity feed — what it did + learned (clears on the brain's drain) */}
      <div style={{ fontSize: 11, color: T.muted, marginBottom: 4 }}>live activity (what it opened + learned)</div>
      {feed.length ? feed.slice(0, 10).map((e) => (
        <div key={e.id} style={{ display: 'flex', gap: 8, padding: '4px 0', borderTop: `1px solid ${T.gridline}` }}>
          <span>{KIND_ICON[e.kind] || '•'}</span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 12 }}>{e.title}{e.site && <span style={{ color: T.muted }}> · {e.site}</span>}</div>
            {e.learned && <div style={{ fontSize: 11, color: T.good }}>💡 {e.learned}</div>}
          </div>
        </div>
      )) : <div style={{ color: T.muted, fontSize: 12 }}>no recent web activity</div>}

      {recent.length > 0 && (
        <div style={{ marginTop: 10 }}>
          <div style={{ fontSize: 11, color: T.muted, marginBottom: 4 }}>recently read</div>
          {recent.slice(0, 6).map((r, i) => (
            <div key={i} style={{ fontSize: 11, color: T.text }}>📄 {r.title} <span style={{ color: T.muted }}>({r.kind})</span></div>
          ))}
        </div>
      )}
    </div>
  )
}
