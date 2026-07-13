// PostmortemPanel.jsx — "🔬 Trade Post-Mortem & Excursion"
// The trade-outcome pattern miner (owner ask 2026-07-13): the REAL common patterns that
// separate WINNING trades from LOSING trades — mined by subgroup discovery over the entry
// context of every closed trade — plus the peak-excursion / ideal-entry-offset per symbol.
// All numbers come from /api/trading/postmortem (state-file read of postmortem_patterns.json
// + postmortem_excursion.json; the mining runs in the funnel-learn daemon, never the request).
import { useEffect, useState } from 'react'
import { T } from './theme.js'

async function getJSON(url) {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json()
}
function num(v) { const n = v == null ? null : Number(v); return Number.isFinite(n) ? n : null }
function pct(v, d = 0) { const n = num(v); return n == null ? '—' : `${(n * 100).toFixed(d)}%` }
function signed(v, d = 1) { const n = num(v); return n == null ? '—' : `${n >= 0 ? '+' : ''}${(n * 100).toFixed(d)}%` }

function Stat({ label, value, sub, color }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 96 }}>
      <span style={{ fontSize: 10, color: T.muted, textTransform: 'uppercase', letterSpacing: 0.4 }}>{label}</span>
      <span style={{ fontSize: 16, fontWeight: 700, color: color || T.text }}>{value}</span>
      {sub ? <span style={{ fontSize: 9, color: T.muted }}>{sub}</span> : null}
    </div>
  )
}

// One mined rule: the readable conjunction, its win-rate bar vs base, lift and support (n).
function RuleRow({ r, base, win }) {
  const c = win ? T.good : T.bad
  const w = Math.max(0, Math.min(1, num(r.win_rate) || 0)) * 100
  const b = Math.max(0, Math.min(1, num(base) || 0)) * 100
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 0',
                  borderTop: `1px solid ${T.gridline}` }}>
      <span style={{ flex: 1, minWidth: 150, fontSize: 11, color: T.text, fontFamily: 'monospace',
                     overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
            title={r.rule}>{r.rule}</span>
      <span style={{ width: 40, fontSize: 11, color: T.muted, textAlign: 'right' }} title="closed trades matched">n={r.n}</span>
      <div style={{ width: 110, position: 'relative' }} title={`win ${pct(r.win_rate, 1)} vs base ${pct(base, 1)}`}>
        <div style={{ height: 6, background: T.panel2, borderRadius: 3, overflow: 'hidden' }}>
          <div style={{ height: '100%', width: `${w}%`, background: c }} />
        </div>
        {/* base-rate marker — the line every rule is measured against */}
        <div style={{ position: 'absolute', top: -2, left: `${b}%`, width: 1, height: 10,
                      background: T.text, opacity: 0.8 }} title={`base ${pct(base, 1)}`} />
      </div>
      <span style={{ width: 42, fontSize: 12, fontWeight: 700, color: c, textAlign: 'right' }}>{pct(r.win_rate, 0)}</span>
      <span style={{ width: 52, fontSize: 11, fontWeight: 700, color: c, textAlign: 'right' }}
            title="lift vs base rate">{signed(r.lift)}</span>
    </div>
  )
}

// One ideal-entry-offset row: symbol|regime, how much better the entry historically was,
// the median favourable run and when it peaked (minutes after entry).
function OffsetRow({ r }) {
  const off = num(r.ideal_entry_offset_pct)
  const oc = off == null ? T.muted : off >= 1 ? T.warn : T.text
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0',
                  borderTop: `1px solid ${T.gridline}` }}>
      <span style={{ flex: 1, minWidth: 120, fontSize: 11, color: T.text, fontFamily: 'monospace',
                     overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.key}</span>
      <span style={{ width: 34, fontSize: 10, color: T.muted, textAlign: 'right' }}>n={r.n}</span>
      <span style={{ width: 72, fontSize: 12, fontWeight: 700, color: oc, textAlign: 'right' }}
            title="how much better the entry could have been">{off == null ? '—' : `${off.toFixed(2)}%`}</span>
      <span style={{ width: 66, fontSize: 11, color: T.good, textAlign: 'right' }}
            title="median favourable excursion">{r.median_mfe_pct == null ? '—' : `${Number(r.median_mfe_pct).toFixed(2)}%`}</span>
      <span style={{ width: 62, fontSize: 10, color: T.muted, textAlign: 'right' }}
            title="median minutes after entry the favourable peak occurred">
        {r.median_minutes_to_mfe == null ? '—' : `${Number(r.median_minutes_to_mfe).toFixed(0)}m`}</span>
    </div>
  )
}

export default function PostmortemPanel() {
  const [market, setMarket] = useState('CRYPTO')
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    let alive = true
    const load = () => getJSON(`/api/trading/postmortem?market=${market}`)
      .then(d => { if (alive) { setData(d); setErr(null) } })
      .catch(e => { if (alive) setErr(String(e)) })
    load()
    const t = setInterval(load, 20000)
    return () => { alive = false; clearInterval(t) }
  }, [market])

  if (err) return <div style={{ color: T.bad, fontSize: 12 }}>post-mortem: {err}</div>
  if (!data) return <div style={{ color: T.muted, fontSize: 12 }}>loading post-mortem…</div>
  if (data.available === false) return <div style={{ color: T.bad, fontSize: 12 }}>post-mortem: {data.error}</div>

  const mk = (data.markets || {})[market] || {}
  const winning = mk.winning || []
  const losing = mk.losing || []
  const offsets = mk.excursion_top || []
  const insufficient = mk.insufficient

  const Toggle = ({ id, label }) => (
    <button onClick={() => setMarket(id)}
            style={{ fontSize: 11, fontWeight: 700, padding: '3px 10px', borderRadius: 5, cursor: 'pointer',
                     background: market === id ? T.accent : 'transparent', color: market === id ? '#0b0e14' : T.muted,
                     border: `1px solid ${market === id ? T.accent : T.gridline}` }}>{label}</button>
  )

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <Toggle id="CRYPTO" label="CRYPTO" />
        <Toggle id="NSE" label="NSE" />
        <span style={{ flex: 1 }} />
        <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: 0.3, padding: '2px 6px', borderRadius: 4,
                       color: data.feedback ? T.good : T.muted, border: `1px solid ${data.feedback ? T.good : T.gridline}` }}
              title="POSTMORTEM_FEEDBACK — is the miner allowed to shrink/grow size + nudge entry?">
          {data.feedback ? 'FEEDBACK LIVE' : 'REPORT-ONLY'}
        </span>
      </div>

      <div style={{ display: 'flex', gap: 18, flexWrap: 'wrap', marginBottom: 8 }}>
        <Stat label="closed trades" value={num(mk.n_trades) ?? 0} color={T.text} sub="mined" />
        <Stat label="base win-rate" value={pct(mk.base_rate, 1)} color={T.text} sub="this market" />
        <Stat label="winning patterns" value={winning.length} color={T.good} sub="above base" />
        <Stat label="losing patterns" value={losing.length} color={T.bad} sub="below base" />
        <Stat label="method" value={mk.method === 'commonality' ? 'stats' : 'subgroup'} color={T.muted}
              sub={mk.method === 'commonality' ? 'pysubgroup absent' : 'pysubgroup+stats'} />
      </div>

      {insufficient && (
        <div style={{ fontSize: 11, color: T.muted, padding: '6px 0' }}>
          not enough closed trades in {market} yet to mine patterns — accrues with trading.
        </div>
      )}

      {!insufficient && (
        <>
          <div style={{ fontSize: 10, color: T.good, margin: '8px 0 2px', fontWeight: 700 }}>
            ✅ WINNING PATTERNS — what winners share (win-rate ▸ lift vs base)</div>
          {winning.length === 0 && <div style={{ fontSize: 11, color: T.muted, padding: '4px 0' }}>no winning subgroup cleared support yet</div>}
          {winning.map((r, i) => <RuleRow key={`w${i}`} r={r} base={mk.base_rate} win />)}

          <div style={{ fontSize: 10, color: T.bad, margin: '12px 0 2px', fontWeight: 700 }}>
            ❌ LOSING PATTERNS — what losers share (avoid / downsize)</div>
          {losing.length === 0 && <div style={{ fontSize: 11, color: T.muted, padding: '4px 0' }}>no losing subgroup cleared support yet</div>}
          {losing.map((r, i) => <RuleRow key={`l${i}`} r={r} base={mk.base_rate} win={false} />)}

          <div style={{ fontSize: 10, color: T.muted, margin: '12px 0 2px', fontWeight: 700 }}>
            🎯 IDEAL ENTRY OFFSET — how much better the entry could have been (symbol · regime)</div>
          <div style={{ display: 'flex', gap: 8, fontSize: 8.5, color: T.muted, textTransform: 'uppercase',
                        letterSpacing: 0.3, padding: '0 0 2px' }}>
            <span style={{ flex: 1, minWidth: 120 }}>symbol · regime</span>
            <span style={{ width: 34, textAlign: 'right' }}>n</span>
            <span style={{ width: 72, textAlign: 'right' }}>entry off</span>
            <span style={{ width: 66, textAlign: 'right' }}>med MFE</span>
            <span style={{ width: 62, textAlign: 'right' }}>peak @</span>
          </div>
          {offsets.length === 0 && <div style={{ fontSize: 11, color: T.muted, padding: '4px 0' }}>no excursion aggregates yet (needs local candle replay)</div>}
          {offsets.map((r, i) => <OffsetRow key={`o${i}`} r={r} />)}
        </>
      )}

      <div style={{ fontSize: 9, color: T.muted, marginTop: 10 }}>
        subgroup discovery over entry-time features only (exit-outcome fields excluded to avoid leakage);
        win = net-of-charges P&L &gt; 0; markets kept isolated.
      </div>
    </div>
  )
}
