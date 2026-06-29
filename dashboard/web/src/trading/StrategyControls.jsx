// StrategyControls.jsx — compact position-sizing / risk control card (Dark Pro UI)
// Presentational + a single onAction callback (props-only; the parent owns the POST).
// Shows the loop's current config as input defaults; "Apply" emits one
// {action:'set_strategy', ...five values} body and flashes "applied ✓" feedback.
// Inline-styled via ./theme.js, robust to missing config (optional chaining).
import { useEffect, useState } from 'react'
import { T } from './theme.js'

const METHODS = [
  { value: 'atr_risk', label: 'ATR risk' },
  { value: 'kelly', label: 'Kelly' },
  { value: 'vol_target', label: 'Vol target' },
  { value: 'ai_meta', label: 'AI meta' },
  { value: 'auto', label: 'Auto (kelly+atr)' },
]

// Best-effort numeric parse; returns null when blank/invalid.
function num(v) {
  if (v == null || v === '') return null
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? n : null
}

function Field({ label, children, hint }) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0 }}>
      <span style={{ fontSize: 10, color: T.muted, textTransform: 'uppercase', letterSpacing: 0.4 }}>
        {label}
      </span>
      {children}
      {hint && <span style={{ fontSize: 9.5, color: T.muted }}>{hint}</span>}
    </label>
  )
}

const inputStyle = {
  background: T.panel2,
  color: T.text,
  border: `1px solid ${T.border}`,
  borderRadius: 8,
  padding: '7px 10px',
  fontSize: 13,
  width: '100%',
  boxSizing: 'border-box',
}

export default function StrategyControls({ config, onAction }) {
  const cfg = config || {}

  const [method, setMethod] = useState('auto')
  const [maxRisk, setMaxRisk] = useState('')
  const [maxPos, setMaxPos] = useState('')
  const [trailAtr, setTrailAtr] = useState('')
  const [kelly, setKelly] = useState('')
  const [applied, setApplied] = useState(false)
  const [busy, setBusy] = useState(false)

  // Re-seed inputs from the live config whenever it changes (current values as defaults).
  useEffect(() => {
    if (cfg.sizing_method != null) setMethod(String(cfg.sizing_method))
    if (cfg.max_risk_pct != null) setMaxRisk(String(cfg.max_risk_pct))
    if (cfg.max_position_pct != null) setMaxPos(String(cfg.max_position_pct))
    if (cfg.trail_atr_mult != null) setTrailAtr(String(cfg.trail_atr_mult))
    if (cfg.kelly_fraction != null) setKelly(String(cfg.kelly_fraction))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cfg.sizing_method, cfg.max_risk_pct, cfg.max_position_pct, cfg.trail_atr_mult, cfg.kelly_fraction])

  const apply = async () => {
    if (busy) return
    setBusy(true)
    try {
      await onAction?.({
        action: 'set_strategy',
        sizing_method: method,
        max_risk_pct: num(maxRisk),
        max_position_pct: num(maxPos),
        trail_atr_mult: num(trailAtr),
        kelly_fraction: num(kelly),
      })
      setApplied(true)
      setTimeout(() => setApplied(false), 2200)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div
      style={{
        background: T.panel,
        border: `1px solid ${T.border}`,
        borderRadius: 10,
        padding: 12,
        color: T.text,
        fontFamily: 'system-ui, sans-serif',
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        boxSizing: 'border-box',
        width: '100%',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <span style={{ fontWeight: 700, fontSize: 14, color: T.text }}>Strategy & Sizing</span>
        <span style={{ fontSize: 11, color: T.muted }}>position-sizing · risk · trailing</span>
      </div>

      <Field label="Sizing method">
        <select value={method} onChange={(e) => setMethod(e.target.value)} style={inputStyle}>
          {METHODS.map((m) => (
            <option key={m.value} value={m.value}>{m.label}</option>
          ))}
        </select>
      </Field>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 10 }}>
        <Field label="Risk % / trade" hint="max_risk_pct">
          <input type="number" step="0.1" min="0" value={maxRisk}
            onChange={(e) => setMaxRisk(e.target.value)} placeholder="—" style={inputStyle} />
        </Field>
        <Field label="Max position %" hint="max_position_pct">
          <input type="number" step="0.1" min="0" value={maxPos}
            onChange={(e) => setMaxPos(e.target.value)} placeholder="—" style={inputStyle} />
        </Field>
        <Field label="Trailing ATR ×" hint="trail_atr_mult">
          <input type="number" step="0.1" min="0" value={trailAtr}
            onChange={(e) => setTrailAtr(e.target.value)} placeholder="—" style={inputStyle} />
        </Field>
        <Field label="Kelly fraction" hint="0–1">
          <input type="number" step="0.05" min="0" max="1" value={kelly}
            onChange={(e) => setKelly(e.target.value)} placeholder="—" style={inputStyle} />
        </Field>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <button
          onClick={apply}
          disabled={busy}
          style={{
            background: T.panel2,
            color: busy ? T.muted : T.accent,
            border: `1px solid ${busy ? T.border : T.accent}`,
            borderRadius: 8,
            padding: '8px 18px',
            cursor: busy ? 'not-allowed' : 'pointer',
            fontSize: 13,
            fontWeight: 700,
            opacity: busy ? 0.6 : 1,
          }}
        >
          Apply
        </button>
        {applied && (
          <span style={{ fontSize: 12, fontWeight: 700, color: T.good }}>applied ✓</span>
        )}
      </div>
    </div>
  )
}
