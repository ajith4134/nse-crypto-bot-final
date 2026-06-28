// ContextPanel.jsx — Phase T6 (Dark Pro UI), blueprint §T6.9
// Market context panel (India VIX, FII/DII flows, Fear & Greed). Presentational /
// props-only, inline-styled via ./theme.js, no styles.css dependency. HONEST: when a
// metric is not available it is greyed with a "no live feed" note; a demo value is
// shown only with an explicit muted "demo" tag — never presented as live. Fully robust
// to a missing/partial context object.
import { T } from './theme.js'

function fmtValue(v) {
  if (v == null || v === '') return '—'
  if (typeof v === 'number') {
    return Number.isFinite(v)
      ? v.toLocaleString(undefined, { maximumFractionDigits: 2 })
      : '—'
  }
  return String(v)
}

// Heuristic: a note mentioning "demo" / "sample" / "synthetic" flags non-live data.
function isDemoNote(note) {
  return /demo|sample|synthetic|mock|placeholder/i.test(String(note || ''))
}

function StatBlock({ label, metric }) {
  const m = metric || {}
  const available = m.available === true
  const demo = isDemoNote(m.note)
  const hasValue = m.value != null && m.value !== ''

  // Live + available → show value in normal text; otherwise grey it out.
  const valueColor = available ? T.text : T.muted
  const display = available || (demo && hasValue) ? fmtValue(m.value) : '—'

  return (
    <div
      style={{
        flex: '1 1 140px',
        minWidth: 0,
        background: T.panel2,
        border: `1px solid ${T.border}`,
        borderRadius: 8,
        padding: '12px 14px',
        boxSizing: 'border-box',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          fontSize: 10,
          textTransform: 'uppercase',
          letterSpacing: 0.6,
          color: T.muted,
          marginBottom: 8,
        }}
      >
        <span
          style={{
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {label}
        </span>
        {!available && demo && (
          <span
            style={{
              fontSize: 8,
              fontWeight: 700,
              color: T.warn,
              border: `1px solid ${T.warn}`,
              borderRadius: 3,
              padding: '0 4px',
              flexShrink: 0,
            }}
          >
            DEMO
          </span>
        )}
      </div>

      <div
        style={{
          fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
          fontSize: 24,
          fontWeight: 700,
          color: valueColor,
          lineHeight: 1.1,
          opacity: available ? 1 : 0.7,
        }}
      >
        {display}
      </div>

      <div style={{ fontSize: 10, color: T.muted, marginTop: 6, minHeight: 12 }}>
        {available
          ? fmtValue(m.note) === '—'
            ? ''
            : m.note
          : demo
          ? m.note
          : m.note || 'no live feed'}
      </div>
    </div>
  )
}

export default function ContextPanel({ context }) {
  const ctx = context && typeof context === 'object' ? context : {}

  const wrap = {
    background: T.panel,
    border: `1px solid ${T.border}`,
    borderRadius: 8,
    color: T.text,
    width: '100%',
    fontFamily: 'system-ui, sans-serif',
    padding: 12,
    boxSizing: 'border-box',
  }

  return (
    <div style={wrap}>
      <div
        style={{
          fontWeight: 600,
          letterSpacing: 0.4,
          marginBottom: 10,
        }}
      >
        Market Context
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        <StatBlock label="India VIX" metric={ctx.india_vix} />
        <StatBlock label="FII / DII Flows" metric={ctx.fii_dii} />
        <StatBlock label="Fear & Greed" metric={ctx.fear_greed} />
      </div>
    </div>
  )
}
