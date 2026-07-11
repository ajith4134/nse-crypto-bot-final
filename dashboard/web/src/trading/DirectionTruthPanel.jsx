// DirectionTruthPanel.jsx — "🎯 Direction Truth (Pillar 27)"
// D1 of the Direction Accuracy Program: REAL measured direction accuracy per signal
// source × regime × horizon, Wilson-CI-bounded, from /api/trading/direction/truth
// (state-file read of direction_truth.json — every number is a labeled outcome of an
// actual decision; no_data horizons are excluded, never guessed).
import { useEffect, useState } from 'react'
import { T } from './theme.js'

async function getJSON(url) {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json()
}
function num(v) { const n = v == null ? null : Number(v); return Number.isFinite(n) ? n : null }
function pct(v, digits = 1) { const n = num(v); return n == null ? '—' : `${(n * 100).toFixed(digits)}%` }

function accColor(rate, n) {
  if (rate == null || !n) return T.muted
  if (rate >= 0.55) return T.good
  if (rate >= 0.45) return T.warn
  return T.bad
}

function Stat({ label, value, sub, color }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 90 }}>
      <span style={{ fontSize: 10, color: T.muted, textTransform: 'uppercase', letterSpacing: 0.4 }}>{label}</span>
      <span style={{ fontSize: 16, fontWeight: 700, color: color || T.text }}>{value}</span>
      {sub ? <span style={{ fontSize: 9, color: T.muted }}>{sub}</span> : null}
    </div>
  )
}

// One source row: name | regime | horizon | n | accuracy bar with CI whiskers | verdict
function SourceRow({ r }) {
  const c = accColor(r.rate, r.n)
  const verdict = r.ci_high < 0.45 ? 'INVERT-CANDIDATE' : r.ci_low > 0.55 ? 'TRUSTED' : 'UNPROVEN'
  const vc = verdict === 'TRUSTED' ? T.good : verdict === 'INVERT-CANDIDATE' ? T.bad : T.muted
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 0',
                  borderTop: `1px solid ${T.gridline}` }}>
      <span style={{ width: 140, fontSize: 11, color: T.text, fontFamily: 'monospace',
                     overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
            title={`${r.source} · regime=${r.regime}`}>{r.source}</span>
      <span style={{ width: 52, fontSize: 10, color: T.muted }}>{r.regime}</span>
      <span style={{ width: 30, fontSize: 10, color: T.muted }}>{r.horizon}</span>
      <span style={{ width: 40, fontSize: 11, color: T.text, textAlign: 'right' }} title="labeled decisions">{r.n}</span>
      <div style={{ flex: 1, minWidth: 70, position: 'relative' }} title={`CI ${pct(r.ci_low)}–${pct(r.ci_high)}`}>
        <div style={{ height: 6, background: T.panel2, borderRadius: 3, overflow: 'hidden' }}>
          <div style={{ height: '100%', width: `${(r.rate || 0) * 100}%`, background: c }} />
        </div>
        {/* Wilson CI whiskers — honesty visualized: thin n = wide whiskers */}
        <div style={{ position: 'absolute', top: -2, left: `${(r.ci_low || 0) * 100}%`,
                      width: `${Math.max(0, (r.ci_high - r.ci_low)) * 100}%`, height: 10,
                      borderLeft: `1px solid ${T.muted}`, borderRight: `1px solid ${T.muted}`, opacity: 0.7 }} />
      </div>
      <span style={{ width: 46, fontSize: 12, fontWeight: 700, color: c, textAlign: 'right' }}>{pct(r.rate, 0)}</span>
      <span style={{ width: 104, fontSize: 8.5, fontWeight: 700, letterSpacing: 0.3, color: vc,
                     border: `1px solid ${vc}`, borderRadius: 4, padding: '1px 4px',
                     textAlign: 'center', whiteSpace: 'nowrap' }}>{verdict}</span>
    </div>
  )
}

export default function DirectionTruthPanel() {
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    let alive = true
    const load = () => getJSON('/api/trading/direction/truth')
      .then(d => { if (alive) { setData(d); setErr(null) } })
      .catch(e => { if (alive) setErr(String(e)) })
    load()
    const t = setInterval(load, 15000)
    return () => { alive = false; clearInterval(t) }
  }, [])

  if (err) return <div style={{ color: T.bad, fontSize: 12 }}>direction truth: {err}</div>
  if (!data) return <div style={{ color: T.muted, fontSize: 12 }}>loading direction truth…</div>
  if (data.available === false) return <div style={{ color: T.bad, fontSize: 12 }}>direction truth: {data.error}</div>

  const roll = data.rollups || {}
  const taken = roll['taken|taken|1h'] || roll['taken|taken|exit'] || {}
  const skipped = roll['taken|skipped|1h'] || {}
  const long1h = roll['direction|LONG|1h'] || {}
  const short1h = roll['direction|SHORT|1h'] || {}
  const worst = data.worst_sources || []
  const best = data.best_sources || []

  return (
    <div>
      <div style={{ display: 'flex', gap: 18, flexWrap: 'wrap', marginBottom: 8 }}>
        <Stat label="taken acc (1h)" value={pct(taken.rate)} color={accColor(taken.rate, taken.n)}
              sub={taken.n ? `n=${taken.n} · CI ${pct(taken.ci_low, 0)}–${pct(taken.ci_high, 0)}` : 'no labels yet'} />
        <Stat label="skipped acc (1h)" value={pct(skipped.rate)} color={accColor(skipped.rate, skipped.n)}
              sub={skipped.n ? `n=${skipped.n}` : 'no labels yet'} />
        <Stat label="LONG (1h)" value={pct(long1h.rate)} color={accColor(long1h.rate, long1h.n)} sub={long1h.n ? `n=${long1h.n}` : ''} />
        <Stat label="SHORT (1h)" value={pct(short1h.rate)} color={accColor(short1h.rate, short1h.n)} sub={short1h.n ? `n=${short1h.n}` : ''} />
        <Stat label="pending labels" value={num(data.pending) ?? 0} color={T.text} sub="awaiting horizon" />
        <Stat label="buckets" value={num(data.n_buckets) ?? 0} color={T.text} sub="source×regime×horizon" />
      </div>
      <div style={{ fontSize: 10, color: T.muted, margin: '6px 0 2px' }}>WORST SOURCES (n≥10) — invert candidates for the Mirror Gate</div>
      {worst.length === 0 && <div style={{ fontSize: 11, color: T.muted, padding: '4px 0' }}>no buckets with n≥10 yet — labels accrue as horizons mature</div>}
      {worst.map((r, i) => <SourceRow key={`w${i}`} r={r} />)}
      <div style={{ fontSize: 10, color: T.muted, margin: '10px 0 2px' }}>BEST SOURCES (n≥10)</div>
      {best.map((r, i) => <SourceRow key={`b${i}`} r={r} />)}
      <div style={{ fontSize: 9, color: T.muted, marginTop: 8 }}>{data.honest_note}</div>
    </div>
  )
}
