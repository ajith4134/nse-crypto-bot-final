// TradeColumnsPanel.jsx — self-growing trade-table columns. The App Driving School discovers real
// data fields on the broker apps; this panel distils them (noise filtered, cross-checked vs the
// 135-col journal schema) into genuine NEW column proposals, each traced to the exact app label it
// was seen as. Accept → the column joins the trade tables. Honest: nothing decorative, real fields.
import { useEffect, useRef, useState } from 'react'
import { T } from './theme.js'

const API = '/api/trading/trade_columns'
async function getJSON() { const r = await fetch(API); if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() }
async function post(b) { const r = await fetch(API, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }); return r.json() }

export default function TradeColumnsPanel({ intervalMs = 10000 }) {
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)
  const alive = useRef(true)

  const refresh = async () => { try { const d = await getJSON(); if (alive.current) { setData(d); setErr(null) } } catch (e) { if (alive.current) setErr(String(e.message || e)) } }
  useEffect(() => { alive.current = true; refresh(); const t = setInterval(refresh, intervalMs); return () => { alive.current = false; clearInterval(t) } }, [intervalMs])

  const act = async (op, column) => { await post({ op, column }); refresh() }

  const card = { background: T.panel, border: `1px solid ${T.border}`, borderRadius: 12, padding: 14 }
  if (err) return <div style={{ ...card, color: T.bad || '#ff6b6b' }}>Trade columns: {err}</div>
  if (!data) return <div style={{ ...card, color: T.muted }}>Loading discovered columns…</div>

  const proposals = data.proposals || []
  const accepted = data.accepted || []

  return (
    <div style={card}>
      <div style={{ fontSize: 14, fontWeight: 800, color: T.text, marginBottom: 4 }}>🧬 Self-growing trade columns</div>
      <div style={{ fontSize: 11, color: T.muted, marginBottom: 10 }}>
        Genuine data fields the brain found on the broker apps that the trade tables don&apos;t track yet ({data.n_labels_scanned || 0} app labels scanned, noise filtered). Accept → it joins the open/closed tables.
      </div>

      {accepted.length > 0 && (
        <div style={{ marginBottom: 10 }}>
          <span style={{ fontSize: 11, color: T.muted }}>accepted into tables: </span>
          {accepted.map((c, i) => <span key={i} style={{ fontSize: 10, fontWeight: 700, color: (T.good || '#3ecf8e'), border: `1px solid ${T.good || '#3ecf8e'}`, borderRadius: 6, padding: '1px 6px', marginRight: 4 }}>{c}</span>)}
        </div>
      )}

      <div style={{ fontSize: 12, fontWeight: 700, color: T.text, marginBottom: 4 }}>New column proposals ({proposals.length})</div>
      {proposals.length === 0
        ? <div style={{ fontSize: 12, color: T.muted }}>None right now — as the App Driving School explores more app pages, real new fields appear here.</div>
        : proposals.map((p, i) => (
          <div key={i} style={{ borderTop: `1px solid ${T.border}`, padding: '7px 0', display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'center' }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: T.text }}>{p.column} <span style={{ fontSize: 10, color: T.muted }}>[{p.applies_to}]</span></div>
              <div style={{ fontSize: 11, color: T.muted, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.meaning} · seen as: {(p.seen_as || []).join(', ')}</div>
            </div>
            <button onClick={() => act('accept', p.column)} style={{ background: T.panel2 || '#1a1f2b', color: (T.good || '#3ecf8e'), border: `1px solid ${T.good || '#3ecf8e'}`, borderRadius: 8, padding: '5px 12px', cursor: 'pointer', fontSize: 12, fontWeight: 700 }}>Add ＋</button>
          </div>
        ))}
    </div>
  )
}
