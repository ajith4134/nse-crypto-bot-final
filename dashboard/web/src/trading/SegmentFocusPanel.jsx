// SegmentFocusPanel.jsx — the GLOBAL segment-focus control. One switchboard for BOTH markets
// (crypto: futures/spot/options/prediction · NSE: equity/futures/options/commodities). Turning a
// segment OFF here makes the WHOLE brain stop focusing on it — the crypto brain-loop, the
// Broker-Sense funnel, the broker built-in pickers, and the strategy foundry all read the same
// active_segments gate. Honest: the "applies to" list shows exactly which brain features honor it.
import { useEffect, useRef, useState } from 'react'
import { T } from './theme.js'

const API = '/api/trading/segments'
async function getJSON() { const r = await fetch(API); if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() }
async function post(b) { const r = await fetch(API, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }); return r.json() }

function Toggle({ on, label, onClick }) {
  const c = on ? (T.good || '#3ecf8e') : (T.muted || '#7a8699')
  return (
    <button onClick={onClick} style={{
      background: on ? 'rgba(62,207,142,0.12)' : (T.panel2 || '#1a1f2b'), color: c,
      border: `1px solid ${c}`, borderRadius: 8, padding: '6px 12px', cursor: 'pointer',
      fontSize: 12, fontWeight: 700, minWidth: 96, textAlign: 'left' }}>
      {on ? '● ' : '○ '}{label}
    </button>
  )
}

export default function SegmentFocusPanel({ intervalMs = 7000 }) {
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)
  const alive = useRef(true)

  const refresh = async () => { try { const d = await getJSON(); if (alive.current) { setData(d); setErr(null) } } catch (e) { if (alive.current) setErr(String(e.message || e)) } }
  useEffect(() => { alive.current = true; refresh(); const t = setInterval(refresh, intervalMs); return () => { alive.current = false; clearInterval(t) } }, [intervalMs])

  const toggleSeg = async (market, segment, on) => { await post({ market, segment, on: !on }); refresh() }
  const toggleAll = async (market, on) => { await post({ market, all: on }); refresh() }

  const card = { background: T.panel, border: `1px solid ${T.border}`, borderRadius: 12, padding: 14 }
  if (err) return <div style={{ ...card, color: T.bad || '#ff6b6b' }}>Segment focus: {err}</div>
  if (!data) return <div style={{ ...card, color: T.muted }}>Loading segment focus…</div>

  const markets = data.markets || {}
  return (
    <div style={card}>
      <div style={{ fontSize: 14, fontWeight: 800, color: T.text, marginBottom: 4 }}>🎯 Segment focus — gates the whole brain</div>
      <div style={{ fontSize: 11, color: T.muted, marginBottom: 12 }}>
        Turn a segment off and the brain stops focusing on it everywhere — entries, screening, broker pickers, and strategy research all obey this.
      </div>
      {Object.entries(markets).map(([mk, m]) => {
        const allOn = (m.segments || []).every((s) => s.active)
        return (
          <div key={mk} style={{ marginBottom: 14 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
              <span style={{ fontSize: 13, fontWeight: 800, color: T.text }}>{mk}</span>
              <button onClick={() => toggleAll(mk, !allOn)} style={{ background: 'transparent', color: T.accent, border: `1px solid ${T.accent}`, borderRadius: 6, padding: '2px 8px', cursor: 'pointer', fontSize: 11, fontWeight: 700 }}>
                {allOn ? 'Turn ALL off' : 'Turn ALL on'}
              </button>
              <span style={{ fontSize: 11, color: T.muted }}>{(m.active || []).length}/{(m.segments || []).length} active</span>
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {(m.segments || []).map((s) => (
                <Toggle key={s.name} on={s.active} label={s.name} onClick={() => toggleSeg(mk, s.name, s.active)} />
              ))}
            </div>
          </div>
        )
      })}
      <div style={{ borderTop: `1px solid ${T.border}`, paddingTop: 8, marginTop: 4 }}>
        <span style={{ fontSize: 11, color: T.muted }}>applies to: </span>
        {(data.applies_to || []).map((f, i) => <span key={i} style={{ fontSize: 10, color: (T.good || '#3ecf8e'), marginRight: 8 }}>✓ {f}</span>)}
      </div>
    </div>
  )
}
