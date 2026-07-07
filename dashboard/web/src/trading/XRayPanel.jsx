// XRayPanel.jsx — the Upstox Stock X-Ray (Dark Pro UI). One fused per-stock snapshot from
// GET /api/trading/xray: multi-TF indicators, circuit bands, depth imbalance, demand/supply
// zones, summary. Honest — every value comes from the real OpenAlgo/free-eyes capture; nothing
// is fabricated. Type a symbol + X-Ray to capture fresh; auto-captured snapshots (on trade-open)
// show in Recent.
import { useEffect, useRef, useState } from 'react'
import { T } from './theme.js'

const XRAY_URL = '/api/trading/xray'

async function getJSON(url) {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json()
}

const num = (v, d = 2) => {
  const n = Number(v)
  return Number.isFinite(n) ? n.toFixed(d) : '—'
}

function Stat({ label, value, color }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 92 }}>
      <span style={{ fontSize: 10, color: T.muted, textTransform: 'uppercase', letterSpacing: 0.4 }}>{label}</span>
      <span style={{ fontSize: 15, fontWeight: 700, color: color || T.text }}>{value}</span>
    </div>
  )
}

export default function XRayPanel() {
  const [sym, setSym] = useState('RELIANCE')
  const [x, setX] = useState(null)
  const [recent, setRecent] = useState([])
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  const timer = useRef(null)

  const loadRecent = () => getJSON(XRAY_URL).then((d) => setRecent(d.recent || [])).catch(() => {})

  const capture = (s, refresh) => {
    const q = (s || sym || '').trim().toUpperCase()
    if (!q) return
    setBusy(true); setErr(null)
    getJSON(`${XRAY_URL}?symbol=${encodeURIComponent(q)}${refresh ? '&refresh=1' : ''}`)
      .then((d) => { if (d.error) setErr(d.error); else setX(d); loadRecent() })
      .catch((e) => setErr(String(e.message || e)))
      .finally(() => setBusy(false))
  }

  useEffect(() => {
    loadRecent(); capture('RELIANCE', false)
    timer.current = setInterval(loadRecent, 8000)
    return () => clearInterval(timer.current)
  }, [])

  const q = x?.quote || {}
  const c = x?.circuit || {}
  const dep = x?.depth || {}
  const sm = x?.summary || {}
  const tfs = x?.timeframes || {}
  const zones = x?.zones || {}
  const chg = Number(q.change_pct)
  const chgColor = Number.isFinite(chg) ? (chg >= 0 ? T.good : T.bad) : T.muted

  return (
    <div style={{ background: T.panel, border: `1px solid ${T.border}`, borderRadius: 10, padding: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 15, fontWeight: 800, color: T.text }}>🔬 Stock X-Ray</span>
        <span style={{ fontSize: 11, color: T.muted }}>fused: OpenAlgo + free-eyes (multi-TF · circuit · depth · zones)</span>
        <div style={{ flex: 1 }} />
        <input value={sym} onChange={(e) => setSym(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && capture(sym, true)}
          placeholder="SYMBOL" style={{
            background: T.bg, border: `1px solid ${T.border}`, color: T.text, borderRadius: 6,
            padding: '6px 10px', fontSize: 13, width: 140, textTransform: 'uppercase' }} />
        <button onClick={() => capture(sym, true)} disabled={busy} style={{
          background: T.accent, color: '#fff', border: 'none', borderRadius: 6, padding: '6px 14px',
          fontSize: 13, fontWeight: 700, cursor: busy ? 'wait' : 'pointer', opacity: busy ? 0.6 : 1 }}>
          {busy ? '…' : 'X-Ray'}
        </button>
      </div>

      {err && <div style={{ color: T.bad, fontSize: 12, marginBottom: 8 }}>⚠ {err}</div>}

      {x && (
        <>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 12, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 22, fontWeight: 800, color: T.text }}>{x.symbol}</span>
            <span style={{ fontSize: 18, fontWeight: 700, color: T.text }}>{num(q.ltp)}</span>
            <span style={{ fontSize: 14, fontWeight: 700, color: chgColor }}>
              {Number.isFinite(chg) ? `${chg >= 0 ? '+' : ''}${chg}%` : '—'}
            </span>
            <span style={{ fontSize: 11, color: T.muted }}>{x.exchange} · {x.segment} · {(x.sources || []).join(', ') || 'no data'}</span>
          </div>

          <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap', marginBottom: 14 }}>
            <Stat label="Upper Circuit" value={num(c.upper_circuit)} color={T.good} />
            <Stat label="Lower Circuit" value={num(c.lower_circuit)} color={T.bad} />
            <Stat label="Depth Imbal." value={num(dep.imbalance, 3)}
              color={dep.imbalance > 0 ? T.good : dep.imbalance < 0 ? T.bad : T.muted} />
            <Stat label="Day Range" value={sm.day_range_position_pct != null ? `${sm.day_range_position_pct}%` : '—'} />
            <Stat label="Volume" value={q.volume != null ? Number(q.volume).toLocaleString() : '—'} />
            <Stat label="OI" value={x.open_interest != null ? Number(x.open_interest).toLocaleString() : '—'} />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <div>
              <div style={{ fontSize: 11, color: T.muted, textTransform: 'uppercase', marginBottom: 6 }}>Multi-Timeframe</div>
              <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
                <thead><tr style={{ color: T.muted, textAlign: 'left' }}>
                  <th>TF</th><th>RSI</th><th>Regime</th><th>Bars</th></tr></thead>
                <tbody>
                  {['1m', '5m', '15m', '1h', '1d'].map((tf) => {
                    const ind = tfs[tf]?.indicators || {}
                    const rsi = Number(ind.rsi)
                    return (
                      <tr key={tf} style={{ borderTop: `1px solid ${T.border}`, color: T.text }}>
                        <td style={{ fontWeight: 700 }}>{tf}</td>
                        <td style={{ color: rsi >= 70 ? T.bad : rsi <= 30 ? T.good : T.text }}>{num(rsi, 1)}</td>
                        <td style={{ color: T.muted }}>{ind.regime || '—'}</td>
                        <td style={{ color: T.muted }}>{tfs[tf]?.n ?? 0}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <div>
              <div style={{ fontSize: 11, color: T.muted, textTransform: 'uppercase', marginBottom: 6 }}>Demand / Supply Zones</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                {(zones.supply || []).slice(0, 3).map((z, i) => (
                  <div key={`s${i}`} style={{ fontSize: 12, color: T.bad, display: 'flex', justifyContent: 'space-between' }}>
                    <span>⬆ supply {num(z.level)}</span><span style={{ color: T.muted }}>{z.dist_pct}% · {z.touches}×</span>
                  </div>
                ))}
                {(zones.demand || []).slice(0, 3).map((z, i) => (
                  <div key={`d${i}`} style={{ fontSize: 12, color: T.good, display: 'flex', justifyContent: 'space-between' }}>
                    <span>⬇ demand {num(z.level)}</span><span style={{ color: T.muted }}>{z.dist_pct}% · {z.touches}×</span>
                  </div>
                ))}
                {!(zones.supply || []).length && !(zones.demand || []).length &&
                  <span style={{ fontSize: 12, color: T.muted }}>—</span>}
              </div>
            </div>
          </div>
        </>
      )}

      {recent.length > 0 && (
        <div style={{ marginTop: 14, borderTop: `1px solid ${T.border}`, paddingTop: 10 }}>
          <div style={{ fontSize: 11, color: T.muted, textTransform: 'uppercase', marginBottom: 6 }}>
            Recent captures (auto on trade-open)
          </div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {recent.slice(0, 16).map((r) => (
              <button key={r.symbol} onClick={() => { setSym(r.symbol); capture(r.symbol, false) }} style={{
                background: T.bg, border: `1px solid ${T.border}`, color: T.text, borderRadius: 5,
                padding: '3px 9px', fontSize: 12, cursor: 'pointer' }}>
                {r.symbol}
                <span style={{ color: Number(r.summary?.change_pct) >= 0 ? T.good : T.bad, marginLeft: 6 }}>
                  {r.summary?.change_pct != null ? `${r.summary.change_pct}%` : ''}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
