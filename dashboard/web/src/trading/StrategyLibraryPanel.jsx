// StrategyLibraryPanel.jsx — curated institutional Strategy Library (Dark Pro UI).
// Presentational / props-only. Shows: (1) coverage chips (total / executable / data-gated),
// (2) the real OOS backtest leaderboard of executable strategies, (3) data-gated families
// grouped by the data they need to unlock. Honest: data-gated rows show NO metrics.
// Evolution/mutation/creation is gated OFF — a badge makes that explicit.
import { useState } from 'react'
import { T, pnlColor } from './theme.js'

function Chip({ label, value, color }) {
  return (
    <div style={{ background: T.panel2, border: `1px solid ${T.border}`, borderRadius: 8,
      padding: '6px 12px', display: 'flex', flexDirection: 'column', minWidth: 92 }}>
      <span style={{ fontSize: 18, fontWeight: 800, color: color || T.text }}>{value}</span>
      <span style={{ fontSize: 9, color: T.muted, textTransform: 'uppercase', letterSpacing: 0.5 }}>{label}</span>
    </div>
  )
}

function pct(v) { return v == null ? '—' : `${(v * 100).toFixed(1)}%` }
function f2(v) {
  if (v == null) return '—'
  if (!Number.isFinite(v)) return '∞'
  return v.toFixed(2)
}

function Leaderboard({ rows }) {
  if (!rows || !rows.length) return <div style={{ color: T.muted, fontSize: 12 }}>backtesting library… (first build runs ~79 OOS backtests, then caches)</div>
  const th = { textAlign: 'right', padding: '4px 8px', fontSize: 10, color: T.muted, textTransform: 'uppercase', letterSpacing: 0.4, position: 'sticky', top: 0, background: T.panel }
  const td = { textAlign: 'right', padding: '3px 8px', fontSize: 12, color: T.text, whiteSpace: 'nowrap' }
  return (
    <div style={{ maxHeight: 360, overflow: 'auto', border: `1px solid ${T.border}`, borderRadius: 8 }}>
      <table style={{ borderCollapse: 'collapse', width: '100%' }}>
        <thead><tr>
          <th style={{ ...th, textAlign: 'left' }}>#</th>
          <th style={{ ...th, textAlign: 'left' }}>strategy</th>
          <th style={{ ...th, textAlign: 'left' }}>category</th>
          <th style={th}>Sharpe</th><th style={th}>return</th><th style={th}>maxDD</th>
          <th style={th}>trades</th><th style={th}>win%</th><th style={th}>PF</th>
        </tr></thead>
        <tbody>
          {rows.map((r) => {
            const m = r.metrics || {}
            return (
              <tr key={r.name} style={{ borderTop: `1px solid ${T.gridline}` }}>
                <td style={{ ...td, textAlign: 'left', color: T.muted }}>{r.rank}</td>
                <td style={{ ...td, textAlign: 'left', fontWeight: 600 }} title={r.oss_source}>{r.name}</td>
                <td style={{ ...td, textAlign: 'left', color: T.muted }}>{r.category}</td>
                <td style={{ ...td, color: pnlColor(m.sharpe) }}>{f2(m.sharpe)}</td>
                <td style={{ ...td, color: pnlColor(m.total_return) }}>{pct(m.total_return)}</td>
                <td style={{ ...td, color: T.bad }}>{pct(m.max_drawdown)}</td>
                <td style={td}>{m.n_trades ?? '—'}</td>
                <td style={td}>{m.win_rate == null ? '—' : `${m.win_rate.toFixed(0)}%`}</td>
                <td style={td}>{f2(m.profit_factor)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function DataGated({ gated }) {
  if (!gated || !gated.by_gating_need) return null
  const groups = Object.entries(gated.by_gating_need)
  return (
    <div>
      <div style={{ fontSize: 11, color: T.muted, marginBottom: 6 }}>
        {gated.total} firm-internal strategies catalogued — not backtested (need data the bar feed lacks). Honest: no fabricated metrics.
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {groups.map(([need, count]) => (
          <div key={need} title={(gated.sample?.[need] || []).join(', ')}
            style={{ background: T.panel2, border: `1px solid ${T.border}`, borderRadius: 8, padding: '5px 10px', fontSize: 11 }}>
            <span style={{ color: T.warn, fontWeight: 700 }}>{count}</span>
            <span style={{ color: T.muted }}> · needs </span>
            <span style={{ color: T.text }}>{need}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function StrategyLibraryPanel({ data }) {
  const [tab, setTab] = useState('leaderboard')
  if (!data) return <div style={{ color: T.muted, fontSize: 12 }}>loading strategy library…</div>
  if (data.error || data.available === false)
    return <div style={{ color: T.bad, fontSize: 12 }}>Strategy Library unavailable: {data.error || data.hint}</div>
  const cov = data.coverage || {}
  const cats = Object.entries(cov.by_category || {}).filter(([, v]) => v)
  const tabBtn = (id, label) => (
    <button onClick={() => setTab(id)}
      style={{ background: tab === id ? T.accent : T.panel2, color: tab === id ? '#06121f' : T.text,
        border: `1px solid ${tab === id ? T.accent : T.border}`, borderRadius: 8, padding: '5px 12px',
        cursor: 'pointer', fontSize: 12, fontWeight: 700 }}>{label}</button>
  )
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        <Chip label="total" value={cov.total ?? '—'} color={T.accent} />
        <Chip label="executable" value={cov.n_executable ?? '—'} color={T.good} />
        <Chip label="data-gated" value={cov.n_data_gated ?? '—'} color={T.warn} />
        <Chip label="backtested" value={data.n_backtested ?? '—'} />
        <div style={{ marginLeft: 'auto', background: T.panel2, border: `1px solid ${T.bad}`, color: T.bad,
          borderRadius: 8, padding: '5px 10px', fontSize: 11, fontWeight: 700 }}
          title={data.evolution_status}>⏸ evolution / mutation OFF</div>
      </div>

      <div style={{ display: 'flex', gap: 8 }}>
        {tabBtn('leaderboard', 'OOS Leaderboard')}
        {tabBtn('gated', 'Data-Gated Families')}
        {tabBtn('coverage', 'Coverage')}
      </div>

      {tab === 'leaderboard' && <Leaderboard rows={data.leaderboard} />}
      {tab === 'gated' && <DataGated gated={data.data_gated} />}
      {tab === 'coverage' && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {cats.map(([c, n]) => (
            <div key={c} style={{ background: T.panel2, border: `1px solid ${T.border}`, borderRadius: 8, padding: '5px 10px', fontSize: 11 }}>
              <span style={{ color: T.text, fontWeight: 700 }}>{n}</span>
              <span style={{ color: T.muted }}> {c.replace(/_/g, ' ')}</span>
            </div>
          ))}
        </div>
      )}
      <div style={{ fontSize: 10, color: T.muted }}>{data.note}</div>
    </div>
  )
}
