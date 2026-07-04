// ExchangeVenuesPanel.jsx — "🌐 Exchange Data Venues (multi-venue ban-proofing)"
// Real per-venue telemetry from the market-DATA pool (trading/crypto/exchange_pool) via
// /api/trading/venues: which of binance/bybit/okx/kucoin are serving data, their request
// budget, error count, and ban cooldown — so you can SEE the pool spreading load and backing
// off rate-limited/banned venues (mirrors the LLM Providers panel). Polls ~4s.
import { useEffect, useState } from 'react'
import { T } from './theme.js'

async function getJSON(url) { const r = await fetch(url); if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() }
function num(v) { const n = v == null ? null : Number(v); return Number.isFinite(n) ? n : null }

const ST = {
  active: { c: T.good, label: 'ACTIVE' },
  cooling: { c: T.warn, label: 'COOLING' },
  banned: { c: T.bad, label: 'BANNED' },
  idle: { c: T.muted, label: 'IDLE' },
}
function Badge({ status }) {
  const s = ST[status] || ST.idle
  return <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: 0.4, color: s.c,
    border: `1px solid ${s.c}`, borderRadius: 4, padding: '1px 5px', whiteSpace: 'nowrap' }}>{s.label}</span>
}

// One venue row: name | status | calls | errors | budget bar | cooldown
function VenueRow({ v }) {
  const cap = num(v.budget_cap) || 1
  const left = num(v.budget_left) || 0
  const frac = Math.max(0, Math.min(1, left / cap))
  const budColor = frac > 0.5 ? T.good : frac > 0.2 ? T.warn : T.bad
  const cd = num(v.cooldown_remaining) || 0
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 0', borderTop: `1px solid ${T.gridline}` }}>
      <span style={{ width: 110, fontSize: 11, color: T.text, fontFamily: 'monospace',
                     overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{v.name}</span>
      <span style={{ width: 70 }}><Badge status={v.status} /></span>
      <span style={{ width: 56, fontSize: 12, color: T.text, textAlign: 'right' }} title="calls served">{num(v.calls) ?? 0}</span>
      <span style={{ width: 46, fontSize: 11, color: v.errors ? T.bad : T.muted, textAlign: 'right' }} title="errors">{num(v.errors) ?? 0}</span>
      <div style={{ flex: 1, minWidth: 50 }} title={`request budget ${left.toFixed(0)}/${cap.toFixed(0)}`}>
        <div style={{ height: 6, background: T.panel2, borderRadius: 3, overflow: 'hidden' }}>
          <div style={{ height: '100%', width: `${frac * 100}%`, background: budColor }} />
        </div>
      </div>
      <span style={{ width: 58, fontSize: 11, textAlign: 'right', fontWeight: cd > 0 ? 700 : 400,
                     color: cd > 0 ? T.bad : T.muted }} title="ban cooldown remaining">
        {cd > 0 ? `${Math.ceil(cd)}s` : '—'}
      </span>
    </div>
  )
}

function Pool({ pool }) {
  const venues = pool.venues || []
  const active = venues.filter((v) => v.status === 'active').length
  const banned = venues.filter((v) => v.status === 'banned' || v.status === 'cooling').length
  return (
    <div style={{ marginTop: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 2 }}>
        <span style={{ fontSize: 11, fontWeight: 700, color: T.text, textTransform: 'uppercase' }}>{pool.market_type}</span>
        <span style={{ fontSize: 10, color: T.good }}>{active} active</span>
        {banned > 0 && <span style={{ fontSize: 10, color: T.bad }}>{banned} cooling/banned</span>}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '2px 0', fontSize: 9,
                    color: T.muted, textTransform: 'uppercase', letterSpacing: 0.4 }}>
        <span style={{ width: 110 }}>venue</span>
        <span style={{ width: 70 }}>status</span>
        <span style={{ width: 56, textAlign: 'right' }}>calls</span>
        <span style={{ width: 46, textAlign: 'right' }}>err</span>
        <span style={{ flex: 1, minWidth: 50 }}>budget</span>
        <span style={{ width: 58, textAlign: 'right' }}>cooldown</span>
      </div>
      {venues.map((v) => <VenueRow key={v.name} v={v} />)}
    </div>
  )
}

export default function ExchangeVenuesPanel() {
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => {
    let alive = true
    const tick = () => getJSON('/api/trading/venues')
      .then((d) => { if (alive) { setData(d); setErr(null) } })
      .catch((e) => { if (alive) setErr(String(e.message || e)) })
    tick(); const id = setInterval(tick, 4000)
    return () => { alive = false; clearInterval(id) }
  }, [])

  const pools = data?.pools || []
  return (
    <div style={{ background: T.panel, border: `1px solid ${T.gridline}`, borderRadius: 8, padding: 12,
                  display: 'flex', flexDirection: 'column', gap: 4 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: T.text }}>🌐 Exchange Data Venues</span>
        <span style={{ fontSize: 10, color: data?.enabled === false ? T.bad : T.muted }}>
          multi-venue pool {data?.enabled === false ? 'OFF (MULTI_VENUE_POOL=0)' : 'ON · ban-proof'}
        </span>
      </div>
      {err && <div style={{ color: T.bad, fontSize: 11 }}>error: {err}</div>}
      {!err && pools.length === 0 &&
        <div style={{ color: T.muted, fontSize: 12, padding: '6px 0' }}>
          no venue pool active yet — appears once the dashboard/brain reads market data through the pool.
        </div>}
      {pools.map((p) => <Pool key={p.market_type} pool={p} />)}
    </div>
  )
}
