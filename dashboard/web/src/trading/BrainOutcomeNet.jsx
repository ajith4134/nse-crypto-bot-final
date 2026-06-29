// BrainOutcomeNet — surfaces the trade-row → NEURAL-NETWORK bridge: the project node
// network (GatedMoENode over real sklearn experts) trained on the closed-trade journal
// and run on each trade row. Shows the model card (engine/skill) + the predicted-vs-actual
// replay over recent closed trades. Presentational; fed from /api/trading/brain/predict.
import React from 'react'
import { T } from './theme.js'

const pct = (v) => (v == null ? '—' : `${(v * 100).toFixed(1)}%`)

export default function BrainOutcomeNet({ data }) {
  if (!data || data.available === false) {
    return <div style={{ color: T.muted, fontSize: 12 }}>outcome net unavailable{data?.error ? `: ${data.error}` : ''}</div>
  }
  const m = data.model || {}
  const replay = data.closed_replay || []
  const open = data.open_predictions || []
  const hit = replay.length
    ? replay.filter((r) => (r.p_win != null) && ((r.p_win >= 0.5) === (r.actual === 'WIN'))).length / replay.length
    : null

  const chip = (label, val, color) => (
    <span style={{ background: T.panel2, border: `1px solid ${T.border}`, borderRadius: 6,
      padding: '3px 8px', fontSize: 12, color: color || T.text }}>{label}: <b>{val}</b></span>
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {chip('engine', m.engine, m.engine === 'gated_moe' ? T.accent : T.muted)}
        {chip('trained', String(m.trained), m.trained ? T.good : T.warn)}
        {chip('train trades', m.n_train)}
        {chip('OOF acc', pct(m.oof_accuracy), T.good)}
        {chip('base rate', pct(m.base_rate))}
        {chip('replay hit', pct(hit))}
      </div>

      {open.length > 0 && (
        <div>
          <div style={{ color: T.muted, fontSize: 12, marginBottom: 4 }}>open-trade outcome calls</div>
          {open.map((o, i) => (
            <div key={i} style={{ display: 'flex', gap: 10, fontSize: 12, padding: '2px 0' }}>
              <span style={{ width: 90 }}>{o.symbol}</span>
              <span style={{ width: 70 }}>{pct(o.p_win)}</span>
              <span style={{ color: o.verdict?.startsWith('WIN') ? T.good : o.verdict?.startsWith('LOSS') ? T.warn : T.muted }}>{o.verdict}</span>
              <span style={{ color: T.muted }}>{o.expected_R != null ? `${o.expected_R}R` : ''}</span>
            </div>
          ))}
        </div>
      )}

      <div>
        <div style={{ color: T.muted, fontSize: 12, marginBottom: 4 }}>predicted vs actual (recent closed)</div>
        {replay.length === 0 && <div style={{ color: T.muted, fontSize: 12 }}>no closed trades yet</div>}
        {replay.map((r, i) => {
          const correct = r.p_win != null && ((r.p_win >= 0.5) === (r.actual === 'WIN'))
          return (
            <div key={i} style={{ display: 'flex', gap: 10, fontSize: 12, padding: '2px 0' }}>
              <span style={{ width: 90 }}>{r.symbol}</span>
              <span style={{ width: 70 }}>{pct(r.p_win)}</span>
              <span style={{ width: 50, color: r.actual === 'WIN' ? T.good : T.warn }}>{r.actual}</span>
              <span style={{ color: correct ? T.good : T.warn }}>{correct ? '✓' : '✗'}</span>
            </div>
          )
        })}
      </div>
      {data.note && <div style={{ color: T.muted, fontSize: 11, lineHeight: 1.4 }}>{data.note}</div>}
    </div>
  )
}
