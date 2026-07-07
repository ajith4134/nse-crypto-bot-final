// BrokerFeaturesPanel.jsx — the broker apps' OWN built-in pickers, USED. Shows the catalog of
// every built-in screener (Upstox momentum/trending/gainers/OI, Binance movers/funding/liq…),
// each picker's LEARNED weight (how its picks actually performed = stacking), invented presets,
// and a live cross-broker regime read. "Read all pickers" fires a parallel read in a subprocess.
// Honest: every weight comes from real closed-trade outcomes; nothing decorative.
import { useEffect, useRef, useState } from 'react'
import { T } from './theme.js'

const API = '/api/trading/broker_features'
async function getJSON() { const r = await fetch(API); if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() }
async function post(b) { const r = await fetch(API, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }); return r.json() }

function Btn({ children, onClick, busy, color }) {
  const c = color || T.accent || '#5b9dff'
  return <button onClick={onClick} disabled={busy} style={{ background: T.panel2 || '#1a1f2b', color: busy ? T.muted : c, border: `1px solid ${c}`, borderRadius: 8, padding: '6px 11px', cursor: busy ? 'wait' : 'pointer', fontSize: 12, fontWeight: 700 }}>{children}</button>
}

export default function BrokerFeaturesPanel({ broker = 'binance', intervalMs = 9000 }) {
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
  const alive = useRef(true)

  useEffect(() => {
    alive.current = true
    const refresh = async () => { try { const d = await getJSON(); if (alive.current) { setData(d); setErr(null) } } catch (e) { if (alive.current) setErr(String(e.message || e)) } }
    refresh(); const t = setInterval(refresh, intervalMs)
    return () => { alive.current = false; clearInterval(t) }
  }, [intervalMs])

  const readAll = async () => { setBusy(true); setMsg(''); try { const r = await post({ op: 'read', broker }); setMsg(r.ok ? '⚡ Reading all built-in pickers in parallel — weights update as trades close.' : `error: ${r.error}`) } catch (e) { setMsg(String(e.message || e)) } finally { if (alive.current) setBusy(false) } }
  const cross = async () => { setBusy(true); try { const r = await post({ op: 'cross' }); setMsg(r.ok ? `🌐 Cross-broker regime: ${r.cross?.regime} (NSE breadth ${r.cross?.nse_breadth ?? '—'})` : `error: ${r.error}`) } catch (e) { setMsg(String(e.message || e)) } finally { if (alive.current) setBusy(false) } }

  const card = { background: T.panel, border: `1px solid ${T.border}`, borderRadius: 12, padding: 14 }
  if (err) return <div style={{ ...card, color: T.bad || '#ff6b6b' }}>Broker Features: {err}</div>
  if (!data) return <div style={{ ...card, color: T.muted }}>Loading broker features…</div>

  const catalog = (data.catalog || {})[broker] || []
  const perf = (data.perf || []).filter((p) => p.broker === broker)
  const invented = (data.invented || {})[broker] || []

  return (
    <div style={card}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <div style={{ fontSize: 14, fontWeight: 800, color: T.text }}>🧩 Broker built-in pickers — {broker}</div>
        <div style={{ display: 'flex', gap: 8 }}>
          <Btn onClick={readAll} busy={busy}>Read all pickers ⚡</Btn>
          <Btn onClick={cross} busy={busy} color={T.good || '#3ecf8e'}>Cross-broker</Btn>
        </div>
      </div>
      <div style={{ fontSize: 11, color: T.muted, marginBottom: 10 }}>
        The app already ranks these on its servers — the brain reads them (parallel) and learns which picker actually predicts winners. Read-only.
      </div>

      <div style={{ fontSize: 12, fontWeight: 700, color: T.text, marginBottom: 4 }}>Cataloged pickers ({catalog.length})</div>
      <div style={{ marginBottom: 10 }}>
        {catalog.map((f, i) => <span key={i} style={{ fontSize: 10, fontWeight: 600, color: T.muted, border: `1px solid ${T.border}`, borderRadius: 6, padding: '1px 6px', marginRight: 4, marginBottom: 4, display: 'inline-block' }}>{f}</span>)}
      </div>

      <div style={{ fontSize: 12, fontWeight: 700, color: T.text, marginBottom: 4 }}>Learned picker weights (from real closed trades)</div>
      {perf.length === 0
        ? <div style={{ fontSize: 12, color: T.muted }}>No outcomes yet — weights appear as trades sourced from these pickers close.</div>
        : perf.slice(0, 10).map((p, i) => (
          <div key={i} style={{ borderTop: `1px solid ${T.border}`, padding: '5px 0', display: 'flex', justifyContent: 'space-between', gap: 10 }}>
            <span style={{ fontSize: 13, color: (T.good || '#3ecf8e') }}>{p.feature}</span>
            <span style={{ fontSize: 11, color: T.muted }}>weight <b style={{ color: T.text }}>{p.weight}</b> · win {Math.round((p.win_rate || 0) * 100)}% · n{p.n} · pnl {p.pnl}</span>
          </div>
        ))}

      {invented.length > 0 && (
        <div style={{ marginTop: 8 }}>
          <span style={{ fontSize: 11, color: T.muted }}>invented presets: </span>
          {invented.slice(0, 8).map((n, i) => <span key={i} style={{ fontSize: 10, color: T.accent, marginRight: 6 }}>{n}</span>)}
        </div>
      )}
      {msg && <div style={{ marginTop: 8, fontSize: 12, color: T.accent }}>{msg}</div>}
    </div>
  )
}
