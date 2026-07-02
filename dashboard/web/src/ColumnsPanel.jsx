import React from 'react'

// ---------------------------------------------------------------------------
//  COLUMN NETWORK view (A·B·C·D). Honest wiring only: reads /api/state fields
//  emitted by run_columns.py — `columns` (layout), `column_weights` (learned
//  CROSS-column gate, option B) and `column_intra_weights` (learned intra-column
//  member gate, option A). Columns render left→right: same-type nodes stacked in
//  one column; the column header bar = its learned cross-column weight (how much
//  the network trusts that function per the trained router). Pruned (near-zero)
//  columns are dimmed. Nothing here is fabricated — if the fields are absent the
//  panel renders nothing.
// ---------------------------------------------------------------------------

export default function ColumnsPanel({ state }) {
  const columns = state?.columns
  if (!columns?.length) return null
  const cross = state.column_weights || {}
  const intra = state.column_intra_weights || {}
  const pruned = new Set(state.pruned_columns || [])
  const maxCross = Math.max(0.0001, ...Object.values(cross).map(Number))

  return (
    <div className="card">
      <h2>Column network — A·B·C·D {state.network_depth ? `· depth ${state.network_depth}` : ''}</h2>
      <div className="hint">
        Same-type nodes per column → intra-column gate (A) → cross-column router (B),
        grown/pruned (C), brain-gated (D). Bars = REAL learned weights.
      </div>
      <div style={{ display: 'flex', gap: 12, overflowX: 'auto', paddingBottom: 8 }}>
        {columns.map((col) => {
          const cw = Number(cross[col.key] || 0)
          const isPruned = pruned.has(col.key)
          const members = intra[col.key] || {}
          return (
            <div key={col.key}
              style={{
                minWidth: 168, flex: '0 0 auto', borderRadius: 10, padding: 10,
                background: '#0e1622', border: `1px solid ${col.color}44`,
                opacity: isPruned ? 0.4 : 1,
              }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <i style={{ width: 10, height: 10, borderRadius: 2, background: col.color }} />
                <strong style={{ fontSize: 13 }}>{col.title}</strong>
              </div>
              {/* cross-column learned weight (option B) */}
              <div style={{ marginTop: 6, height: 6, borderRadius: 3, background: '#1a2536' }}>
                <div style={{
                  height: '100%', borderRadius: 3, background: col.color,
                  width: `${Math.round((cw / maxCross) * 100)}%`,
                }} />
              </div>
              <div style={{ fontSize: 11, color: '#8ea0c0', marginTop: 2 }}>
                cross-weight {cw.toFixed(3)}{isPruned ? ' · pruned' : ''} · {col.size} nodes
              </div>
              {/* intra-column members + their learned member weights (option A) */}
              <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 3 }}>
                {(col.members || []).map((m) => {
                  const mw = Number(members[m] || 0)
                  return (
                    <div key={m} title={`${m} · ${mw.toFixed(3)}`} style={{ fontSize: 11 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ color: '#c7d2e0', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{m}</span>
                        <span style={{ color: '#6b7d99' }}>{mw ? mw.toFixed(2) : ''}</span>
                      </div>
                      {mw > 0 &&
                        <div style={{ height: 3, borderRadius: 2, background: '#1a2536' }}>
                          <div style={{ height: '100%', borderRadius: 2, background: `${col.color}aa`, width: `${Math.round(mw * 100)}%` }} />
                        </div>}
                    </div>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
