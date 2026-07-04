// MetacognitionPanel.jsx — "🎯 Metacognition (Calibrated Uncertainty — Pillar 17)"
// Surfaces trading/uq/conformal.py: the REAL calibration state of the conformal engine
// (crepes CPS over the closed-trades journal + ACI adaptation + netcal ECE), the
// reliability diagram (predicted p_up vs realized win-rate on the chronological holdout)
// and the first-class abstention log — every entry the brain REFUSED and why.
// Self-contained polling of /api/trading/brain/metacognition (~20s); honest: shows the
// fallback engine + thin-data state as-is, never fake calibration.
import { useEffect, useState } from 'react'
import { T } from './theme.js'

async function getJSON(url) {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json()
}
const num = (v) => (v == null || !Number.isFinite(Number(v)) ? null : Number(v))
const fmt = (v, d = 2) => { const n = num(v); return n == null ? '—' : n.toFixed(d) }
const pct = (v, d = 1) => { const n = num(v); return n == null ? '—' : `${(n * 100).toFixed(d)}%` }

function Stat({ label, value, color }) {
  return (
    <div style={{ minWidth: 92 }}>
      <div style={{ fontSize: 9, textTransform: 'uppercase', letterSpacing: 0.6, color: T.muted }}>{label}</div>
      <div style={{ fontSize: 15, fontWeight: 800, color: color || T.text }}>{value}</div>
    </div>
  )
}

// Reliability diagram: predicted p_up (x) vs realized win-rate (y); the diagonal is
// perfect calibration. SVG, no deps — bins come straight from the holdout evaluation.
function ReliabilityDiagram({ bins }) {
  const W = 220, H = 150, P = 26
  const filled = (bins || []).filter(b => b.n > 0 && b.predicted != null && b.realized != null)
  const x = (v) => P + v * (W - P - 8)
  const y = (v) => H - P + v * (P + 8 - H)
  return (
    <svg width={W} height={H} style={{ flexShrink: 0 }}>
      <line x1={x(0)} y1={y(0)} x2={x(1)} y2={y(1)} stroke={T.border} strokeDasharray="3 3" />
      <line x1={x(0)} y1={y(0)} x2={x(1)} y2={y(0)} stroke={T.gridline} />
      <line x1={x(0)} y1={y(0)} x2={x(0)} y2={y(1)} stroke={T.gridline} />
      {[0, 0.5, 1].map(v => (
        <g key={v}>
          <text x={x(v)} y={H - 8} fontSize={8} fill={T.muted} textAnchor="middle">{v}</text>
          <text x={P - 6} y={y(v) + 3} fontSize={8} fill={T.muted} textAnchor="end">{v}</text>
        </g>
      ))}
      {filled.map((b, i) => (
        <circle key={i} cx={x(b.predicted)} cy={y(b.realized)}
                r={Math.min(9, 3 + Math.sqrt(b.n))} fill={T.accent} opacity={0.75}>
          <title>{`p_up≈${b.predicted} → realized ${b.realized} (n=${b.n})`}</title>
        </circle>
      ))}
      <text x={W / 2} y={12} fontSize={9} fill={T.muted} textAnchor="middle">
        predicted p_up → realized win-rate
      </text>
      {!filled.length && (
        <text x={W / 2} y={H / 2} fontSize={10} fill={T.muted} textAnchor="middle">
          no holdout bins yet
        </text>
      )}
    </svg>
  )
}

export default function MetacognitionPanel() {
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => {
    let alive = true
    const load = () => getJSON('/api/trading/brain/metacognition')
      .then(d => { if (alive) { setData(d); setErr(null) } })
      .catch(e => { if (alive) setErr(String(e)) })
    load()
    const id = setInterval(load, 20000)
    return () => { alive = false; clearInterval(id) }
  }, [])

  const st = data?.status || {}
  const abst = data?.abstentions || []
  const cov = num(st.coverage_holdout_aci)
  const covColor = cov == null ? T.muted
    : Math.abs(cov - (num(st.confidence_level) ?? 0.9)) <= 0.05 ? T.good : T.warn
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 10 }}>
        <span style={{ fontSize: 10, color: T.muted }}>
          engine <b style={{ color: T.text }}>{st.engine || '…'}</b> · gate{' '}
          <b style={{ color: st.gate_enforced === false ? T.warn : T.good }}>
            {st.gate_enforced === false ? 'ADVISORY' : 'ENFORCED'}
          </b>
        </span>
      </div>
      {err && <div style={{ color: T.bad, fontSize: 11 }}>{err}</div>}
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', alignItems: 'flex-start' }}>
        <ReliabilityDiagram bins={data?.reliability} />
        <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', flex: 1, minWidth: 220 }}>
          <Stat label="Coverage (ACI)" value={pct(st.coverage_holdout_aci)} color={covColor} />
          <Stat label="Coverage (static)" value={pct(st.coverage_holdout_static)} />
          <Stat label="ECE (p_up)" value={fmt(st.ece_p_up, 3)} />
          <Stat label="p_up gate θ" value={fmt(st.p_up_min)} />
          <Stat label="Width cap" value={st.width_cap != null ? `${fmt(st.width_cap, 1)}%` : '—'} />
          <Stat label="Mean width" value={st.mean_width != null ? `${fmt(st.mean_width, 1)}%` : '—'} />
          <Stat label="Calib. trades" value={st.n_trades ?? '—'} />
          <Stat label="Abstentions" value={st.n_abstentions_logged ?? 0} color={T.warn} />
        </div>
      </div>
      <div style={{ marginTop: 10 }}>
        <div style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: 0.6,
                      color: T.muted, marginBottom: 4 }}>
          Recent abstentions — first-class decisions, not silent skips
        </div>
        {abst.length === 0 && (
          <div style={{ fontSize: 11, color: T.muted }}>none logged yet</div>
        )}
        <div style={{ maxHeight: 170, overflowY: 'auto' }}>
          {abst.map((a, i) => (
            <div key={i} style={{ display: 'flex', gap: 8, fontSize: 11, padding: '4px 2px',
                                  borderBottom: `1px solid ${T.gridline}`, alignItems: 'baseline' }}>
              <span style={{ width: 118, fontWeight: 700, color: T.text, overflow: 'hidden',
                             textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.symbol}</span>
              <span style={{ width: 44, color: a.direction === 'SHORT' ? T.bad : T.good }}>{a.direction}</span>
              <span style={{ width: 56, textAlign: 'right', color: T.warn }}>p↑ {pct(a.p_up)}</span>
              <span style={{ flex: 1, color: T.muted, overflow: 'hidden',
                             textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={a.reason}>{a.reason}</span>
              <span style={{ color: T.muted, fontSize: 9 }}>
                {a.ts ? new Date(a.ts * 1000).toLocaleTimeString() : ''}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
