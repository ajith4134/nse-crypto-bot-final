// LLMProvidersPanel.jsx — "🛰️ LLM Providers (cloud-LLM failover telemetry)"
// Real per-provider stats from core/llm_telemetry via /api/llm/telemetry: hit rate,
// free calls used, failures, rate-limits, last latency, and cooldown ("reloading")
// countdown. Every number is a real API attempt recorded inside core.llm.chat's failover.
// Self-contained: polls /api/llm/telemetry (~4s), inline-styled via ./theme.js.
import { useEffect, useState } from 'react'
import { T } from './theme.js'

async function getJSON(url) {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json()
}
function num(v) { const n = v == null ? null : Number(v); return Number.isFinite(n) ? n : null }
function pct(v) { const n = num(v); return n == null ? '—' : `${(n * 100).toFixed(0)}%` }

const STATUS = {
  active: { c: T.good, label: 'ACTIVE' },
  cooling: { c: T.warn, label: 'RELOADING' },
  failing: { c: T.bad, label: 'FAILING' },
  idle: { c: T.muted, label: 'IDLE' },
}

function Badge({ status }) {
  const s = STATUS[status] || STATUS.idle
  return <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: 0.4, color: s.c,
    border: `1px solid ${s.c}`, borderRadius: 4, padding: '1px 5px', whiteSpace: 'nowrap' }}>{s.label}</span>
}
function Stat({ label, value, color }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <span style={{ fontSize: 10, color: T.muted, textTransform: 'uppercase', letterSpacing: 0.4 }}>{label}</span>
      <span style={{ fontSize: 15, fontWeight: 700, color: color || T.text }}>{value}</span>
    </div>
  )
}

// One provider row: name | status | calls used | hit-rate bar | failures/limits | latency | reload countdown
function ProviderRow({ p }) {
  const hr = num(p.hit_rate)
  const hrColor = hr == null ? T.muted : hr >= 0.8 ? T.good : hr >= 0.5 ? T.warn : T.bad
  const reload = num(p.reload_in_sec) || 0
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 0',
                  borderTop: `1px solid ${T.gridline}` }}>
      <span style={{ width: 118, fontSize: 11, color: T.text, fontFamily: 'monospace',
                     overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
            title={p.last_error || p.provider}>{p.provider}</span>
      <span style={{ width: 78 }}><Badge status={p.status} /></span>
      <span style={{ width: 62, fontSize: 12, color: T.text, textAlign: 'right' }}
            title="free calls used">{num(p.calls) ?? 0}</span>
      {/* hit-rate mini bar */}
      <div style={{ flex: 1, minWidth: 60 }}>
        <div style={{ height: 6, background: T.panel2, borderRadius: 3, overflow: 'hidden' }}>
          <div style={{ height: '100%', width: `${(hr || 0) * 100}%`, background: hrColor }} />
        </div>
      </div>
      <span style={{ width: 42, fontSize: 12, color: hrColor, textAlign: 'right' }}>{pct(hr)}</span>
      <span style={{ width: 58, fontSize: 10, color: T.muted, textAlign: 'right' }}
            title="failures / rate-limits">{num(p.failures) ?? 0}/{num(p.rate_limited) ?? 0}</span>
      <span style={{ width: 56, fontSize: 10, color: T.muted, textAlign: 'right' }}
            title="last latency">{p.last_latency_ms == null ? '—' : `${Math.round(p.last_latency_ms)}ms`}</span>
      <span style={{ width: 52, fontSize: 11, color: reload > 0 ? T.warn : T.muted, textAlign: 'right',
                     fontWeight: reload > 0 ? 700 : 400 }}
            title="cooldown until retry">{reload > 0 ? `${Math.ceil(reload)}s` : '—'}</span>
    </div>
  )
}

export default function LLMProvidersPanel() {
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    let alive = true
    const tick = () => getJSON('/api/llm/telemetry')
      .then((d) => { if (alive) { setData(d); setErr(null) } })
      .catch((e) => { if (alive) setErr(String(e.message || e)) })
    tick()
    const id = setInterval(tick, 4000)
    return () => { alive = false; clearInterval(id) }
  }, [])

  const providers = data?.providers || []
  const totals = data?.totals || {}

  return (
    <div style={{ background: T.panel, border: `1px solid ${T.gridline}`, borderRadius: 8,
                  padding: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: T.text }}>🛰️ LLM Providers</span>
        <span style={{ fontSize: 10, color: T.muted }}>
          failover order · cooldown {data?.cooldown_sec ? `${Math.round(data.cooldown_sec)}s` : '—'}
        </span>
      </div>

      <div style={{ display: 'flex', gap: 18 }}>
        <Stat label="Providers" value={providers.length} />
        <Stat label="Total calls" value={num(totals.calls) ?? 0} />
        <Stat label="Overall hit-rate" value={pct(totals.hit_rate)}
              color={num(totals.hit_rate) >= 0.8 ? T.good : T.warn} />
        <Stat label="Cooling" value={providers.filter((p) => p.status === 'cooling').length}
              color={T.warn} />
      </div>

      {err && <div style={{ color: T.bad, fontSize: 11 }}>error: {err}</div>}
      {!err && providers.length === 0 &&
        <div style={{ color: T.muted, fontSize: 12, padding: '6px 0' }}>
          no LLM calls yet — providers appear here once the brain makes its first cloud-LLM call.
        </div>}

      {providers.length > 0 && (
        <div>
          {/* header row */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '2px 0',
                        fontSize: 9, color: T.muted, textTransform: 'uppercase', letterSpacing: 0.4 }}>
            <span style={{ width: 118 }}>provider</span>
            <span style={{ width: 78 }}>status</span>
            <span style={{ width: 62, textAlign: 'right' }}>calls</span>
            <span style={{ flex: 1, minWidth: 60 }}>hit-rate</span>
            <span style={{ width: 42, textAlign: 'right' }}>%</span>
            <span style={{ width: 58, textAlign: 'right' }}>fail/lim</span>
            <span style={{ width: 56, textAlign: 'right' }}>latency</span>
            <span style={{ width: 52, textAlign: 'right' }}>reload</span>
          </div>
          {providers.map((p) => <ProviderRow key={p.provider} p={p} />)}
        </div>
      )}
    </div>
  )
}
