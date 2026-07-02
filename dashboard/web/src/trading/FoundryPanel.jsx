// FoundryPanel.jsx — "🏭 Strategy Foundry (institutional catalog + keep-the-best)"
// Surfaces trading/strategy/foundry.py: the brain DISCOVERS/creates ultra-advanced strategies
// per segment (each with a UNIQUE ID), backtests + tracks their real performance, and promotes
// the best. Self-contained: polls /api/trading/foundry (~8s), inline-styled via ./theme.js.
import { useEffect, useState } from 'react'
import { T, scoreColor } from './theme.js'

async function getJSON(url) {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json()
}
function num(v) { const n = v == null ? null : Number(v); return Number.isFinite(n) ? n : null }
function fmt(v, d = 2) { const n = num(v); return n == null ? '—' : n.toFixed(d) }

const STATUS_COLOR = (s) => (s === 'promoted' ? T.good : s === 'executable' ? T.accent
  : s === 'data_gated' ? T.warn : T.muted)

function Badge({ text, color }) {
  return <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: 0.4, color,
    border: `1px solid ${color}`, borderRadius: 4, padding: '1px 5px',
    textTransform: 'uppercase', whiteSpace: 'nowrap' }}>{text}</span>
}
function Stat({ label, value, color }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <span style={{ fontSize: 10, color: T.muted, textTransform: 'uppercase', letterSpacing: 0.4 }}>{label}</span>
      <span style={{ fontSize: 16, fontWeight: 700, color: color || T.text }}>{value}</span>
    </div>
  )
}
function Empty({ note }) { return <div style={{ color: T.muted, fontSize: 12, padding: '6px 0' }}>{note || 'no data'}</div> }

// One strategy row: unique id + name + segment/family + status + tracked score + source repo.
function StratRow({ s }) {
  const score = num(s.best_score)
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 0',
                  borderTop: `1px solid ${T.gridline}` }}>
      <span style={{ width: 96, fontSize: 10, color: T.muted, fontFamily: 'monospace' }}>{s.sid}</span>
      <span style={{ flex: 1, fontSize: 12, color: T.text, minWidth: 0, overflow: 'hidden',
                     textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={s.reference}>{s.name}</span>
      <span style={{ width: 88, fontSize: 10, color: T.muted }}>{s.segment}</span>
      <span style={{ width: 78, fontSize: 10, color: T.muted }}>{s.family}</span>
      <Badge text={s.status} color={STATUS_COLOR(s.status)} />
      <span style={{ width: 52, textAlign: 'right', fontSize: 11, fontWeight: 600,
                     color: score == null ? T.muted : scoreColor(Math.max(0, Math.min(1, (score + 1) / 4))) }}>
        {score == null ? '—' : (score > 0 ? '+' : '') + fmt(score, 2)}
      </span>
    </div>
  )
}

export default function FoundryPanel({ intervalMs = 8000 }) {
  const [state, setState] = useState({ loading: true })
  const [seg, setSeg] = useState('all')
  useEffect(() => {
    let alive = true
    const tick = async () => {
      try { const data = await getJSON('/api/trading/foundry'); if (alive) setState({ data, stamp: new Date() }) }
      catch (e) { if (alive) setState({ error: String(e.message || e), stamp: new Date() }) }
    }
    tick(); const timer = setInterval(tick, intervalMs)
    return () => { alive = false; clearInterval(timer) }
  }, [intervalMs])

  const wrap = { background: T.bg, border: `1px solid ${T.border}`, borderRadius: 12,
                 padding: 14, color: T.text, fontFamily: 'system-ui, sans-serif',
                 boxSizing: 'border-box', width: '100%' }
  if (state.loading) {
    return <div style={wrap}><div style={{ color: T.muted, fontSize: 13, padding: '24px 0',
            textAlign: 'center' }}>🏭<div style={{ marginTop: 8 }}>loading Strategy Foundry…</div></div></div>
  }
  const d = state.data
  const bySeg = (d && d.by_segment) || {}
  const board = (d && d.leaderboard) || []
  const segs = Object.keys(bySeg).sort()
  const rows = seg === 'all' ? board : board.filter((r) => r.segment === seg)
  const nPromoted = Object.values(bySeg).reduce((a, s) => a + (s.promoted || 0), 0)
  const nResearch = Object.values(bySeg).reduce((a, s) => a + (s.research || 0), 0)
  return (
    <div style={wrap}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 12 }}>
        <span style={{ fontWeight: 700, fontSize: 16, color: T.text }}>🏭 Strategy Foundry</span>
        <span style={{ fontSize: 11, color: T.muted }}>discover · track · keep-the-best</span>
        <div style={{ flex: 1 }} />
        {state.stamp && <span style={{ fontSize: 10, color: T.muted }}>updated {state.stamp.toLocaleTimeString()}</span>}
      </div>
      {state.error || !d || d.available === false ? (
        <Empty note={state.error || (d && d.error) || 'foundry unavailable'} />
      ) : (
        <>
          <div style={{ display: 'flex', gap: 20, marginBottom: 12, flexWrap: 'wrap' }}>
            <Stat label="strategies" value={d.n_specs ?? '—'} color={T.accent} />
            <Stat label="promoted" value={nPromoted} color={T.good} />
            <Stat label="discovered online" value={nResearch} color={T.warn} />
            <Stat label="segments" value={segs.length} />
          </div>

          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
            {['all', ...segs].map((s) => (
              <button key={s} onClick={() => setSeg(s)} style={{
                fontSize: 10, padding: '2px 8px', borderRadius: 6, cursor: 'pointer',
                border: `1px solid ${seg === s ? T.accent : T.gridline}`,
                background: seg === s ? T.accent : 'transparent',
                color: seg === s ? T.bg : T.muted }}>
                {s}{s !== 'all' && bySeg[s] ? ` ${bySeg[s].total}` : ''}
              </button>
            ))}
          </div>

          <div style={{ display: 'flex', gap: 8, fontSize: 9, color: T.muted, textTransform: 'uppercase',
                        letterSpacing: 0.4, padding: '2px 0' }}>
            <span style={{ width: 96 }}>unique id</span><span style={{ flex: 1 }}>strategy</span>
            <span style={{ width: 88 }}>segment</span><span style={{ width: 78 }}>family</span>
            <span style={{ width: 60 }}>status</span><span style={{ width: 52, textAlign: 'right' }}>score</span>
          </div>
          {rows.length ? rows.map((s, i) => <StratRow key={s.sid || i} s={s} />)
            : <Empty note="no strategies in this segment yet" />}
          <div style={{ marginTop: 10, fontSize: 10, color: T.muted, lineHeight: 1.5 }}>
            The brain researches new institutional strategies online, gives each a unique id,
            backtests + tracks live performance, and promotes the best per segment.
          </div>
        </>
      )}
    </div>
  )
}
