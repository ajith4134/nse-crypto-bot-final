// StrategyControls.jsx — compact position-sizing / risk control card (Dark Pro UI)
// Presentational + a single onAction callback (props-only; the parent owns the POST).
// Shows the loop's current config as input defaults; "Apply" emits one
// {action:'set_strategy', ...five values} body and flashes "applied ✓" feedback.
// Inline-styled via ./theme.js, robust to missing config (optional chaining).
import { useEffect, useRef, useState } from 'react'
import { T } from './theme.js'

// All trade-type segments (NSE + CRYPTO) for the per-segment min-open / leverage overrides.
// Segment KEYS must match live_loop's segment names exactly — the old legacy 'fno' key
// mapped to nothing after the futures/options split, so values saved under it were
// silently ignored (min-trades looked like it "saved 0").
const ALL_SEGMENTS = ['intraday', 'mtf', 'futures', 'options', 'commodities', 'spot', 'prediction']
// Built-in default leverage per segment (mirrors live_loop._LEVERAGE) — shown as placeholders.
const DEFAULT_LEV = { intraday: 5, mtf: 4, futures: 5, options: 1, commodities: 5, spot: 1, prediction: 1 }
// Live MAX leverage per segment (mirrors live_loop._MAX_LEVERAGE) — used as input caps; the
// backend also clamps. Overridden by status.leverage_limits when present.
const MAX_LEV = { intraday: 5, mtf: 5, futures: 125, options: 1, commodities: 10, spot: 5, prediction: 1 }
// Lot-based NSE segments (qty = num_lots × lot_size) + representative default lots (tunable).
const LOT_SEGMENTS = ['futures', 'options', 'commodities']
const DEFAULT_LOT = { futures: 50, options: 50, commodities: 100 }

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

// Shows who currently controls trading: MANUAL (operator sliders + auto-open basket)
// until the brain has learned from enough closed trades, then BRAIN takes over.
function ControlBanner({ status }) {
  const ho = (status && status.handoff) || {}
  const inControl = status?.control === 'BRAIN' || ho.in_control === true
  const closed = Number(ho.closed ?? 0)
  const needed = Number(ho.needed ?? 0)
  const pct = needed > 0 ? Math.min(100, Math.round((closed / needed) * 100)) : 0
  const c = inControl ? T.good : T.warn
  return (
    <div style={{ borderTop: `1px solid ${T.gridline}`, paddingTop: 10, display: 'flex', flexDirection: 'column', gap: 6 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
        <span style={{ color: T.muted, textTransform: 'uppercase', letterSpacing: 0.4, fontSize: 10 }}>In control</span>
        <span style={{ fontWeight: 800, color: c, letterSpacing: 0.4 }}>{inControl ? 'BRAIN' : 'MANUAL'}</span>
        {!inControl && needed > 0 && (
          <span style={{ fontSize: 11, color: T.muted }}>brain takes over after {closed}/{needed} closed trades</span>
        )}
      </div>
      {!inControl && needed > 0 && (
        <div style={{ height: 6, background: T.panel2, borderRadius: 4, overflow: 'hidden' }}>
          <div style={{ width: `${pct}%`, height: '100%', background: c }} />
        </div>
      )}
    </div>
  )
}

export default function StrategyControls({ config, status, onAction }) {
  const cfg = config || {}

  const [method, setMethod] = useState('auto')
  const [maxRisk, setMaxRisk] = useState('')
  const [maxPos, setMaxPos] = useState('')
  const [trailAtr, setTrailAtr] = useState('')
  const [kelly, setKelly] = useState('')
  const [trailMode, setTrailMode] = useState('pct')
  const [trailPct, setTrailPct] = useState('')      // shown as % (3.5), stored as fraction
  const [takeProfit, setTakeProfit] = useState('')  // shown as % (7), stored as fraction
  // auto-open basket + brain handoff + screener filters
  const [autoOpen, setAutoOpen] = useState(false)
  const [topN, setTopN] = useState('')
  const [minOpen, setMinOpen] = useState('')
  const [minBySeg, setMinBySeg] = useState({})   // per-segment overrides {segment: '3'}
  const [levBySeg, setLevBySeg] = useState({})   // per-segment leverage overrides {segment: '5'}
  const [lotBySeg, setLotBySeg] = useState({})   // per-segment lot-size overrides {segment: '50'}
  const [minTotal, setMinTotal] = useState('')
  const [minCap, setMinCap] = useState('')
  const [closing, setClosing] = useState(false)
  const [handoff, setHandoff] = useState('')
  const [minPct, setMinPct] = useState('')
  const [minVol, setMinVol] = useState('')
  const [applied, setApplied] = useState(false)
  const [busy, setBusy] = useState(false)
  // Seed the form from config ONCE (the first time it arrives), then the operator owns the
  // inputs. Re-seeding on every 4s poll was clobbering edits/applied values back to defaults.
  const seededRef = useRef(false)

  useEffect(() => {
    if (seededRef.current || cfg.sizing_method == null) return   // seed once, when config arrives
    if (cfg.sizing_method != null) setMethod(String(cfg.sizing_method))
    if (cfg.max_risk_pct != null) setMaxRisk(String(cfg.max_risk_pct))
    if (cfg.max_position_pct != null) setMaxPos(String(cfg.max_position_pct))
    if (cfg.trail_atr_mult != null) setTrailAtr(String(cfg.trail_atr_mult))
    if (cfg.kelly_fraction != null) setKelly(String(cfg.kelly_fraction))
    if (cfg.trail_mode != null) setTrailMode(String(cfg.trail_mode))
    if (cfg.trail_pct != null) setTrailPct(String(+(cfg.trail_pct * 100).toFixed(3)))
    if (cfg.take_profit_pct != null) setTakeProfit(String(+(cfg.take_profit_pct * 100).toFixed(3)))
    if (cfg.enter_all != null) setAutoOpen(!!cfg.enter_all)
    if (cfg.top_n_per_segment != null) setTopN(String(cfg.top_n_per_segment))
    if (cfg.min_open_per_segment != null) setMinOpen(String(cfg.min_open_per_segment))
    if (cfg.min_open_by_segment && typeof cfg.min_open_by_segment === 'object') {
      const m = {}
      for (const k of Object.keys(cfg.min_open_by_segment)) m[k] = String(cfg.min_open_by_segment[k])
      setMinBySeg(m)
    }
    if (cfg.leverage_by_segment && typeof cfg.leverage_by_segment === 'object') {
      const m = {}
      for (const k of Object.keys(cfg.leverage_by_segment)) m[k] = String(cfg.leverage_by_segment[k])
      setLevBySeg(m)
    }
    if (cfg.lot_size_by_segment && typeof cfg.lot_size_by_segment === 'object') {
      const m = {}
      for (const k of Object.keys(cfg.lot_size_by_segment)) m[k] = String(cfg.lot_size_by_segment[k])
      setLotBySeg(m)
    }
    if (cfg.min_total_open != null) setMinTotal(String(cfg.min_total_open))
    if (cfg.min_capital_per_trade != null) setMinCap(String(cfg.min_capital_per_trade))
    if (cfg.brain_handoff_trades != null) setHandoff(String(cfg.brain_handoff_trades))
    if (cfg.screen_min_pct != null) setMinPct(String(cfg.screen_min_pct))
    if (cfg.screen_min_quote_volume != null) setMinVol(String(cfg.screen_min_quote_volume))
    seededRef.current = true                                     // done — don't reseed (no clobber)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config])

  const closeAll = async () => {
    if (closing || !onAction) return
    if (!window.confirm('Close ALL open trades now (flatten everything at last price)?')) return
    setClosing(true)
    try { await onAction({ action: 'close_all' }) } finally { setClosing(false) }
  }

  const apply = async () => {
    if (busy) return
    setBusy(true)
    try {
      const tp = num(trailPct)
      const tk = num(takeProfit)
      await onAction?.({
        action: 'set_strategy',
        sizing_method: method,
        max_risk_pct: num(maxRisk),
        max_position_pct: num(maxPos),
        trail_atr_mult: num(trailAtr),
        kelly_fraction: num(kelly),
        trail_mode: trailMode,
        trail_pct: tp != null ? tp / 100 : null,         // % → fraction
        take_profit_pct: tk != null ? tk / 100 : null,   // % → fraction
        // auto-open basket + brain handoff + screener filters
        enter_all: autoOpen,
        top_n_per_segment: num(topN),
        min_open_per_segment: num(minOpen),
        min_open_by_segment: ALL_SEGMENTS.reduce((acc, seg) => {
          const v = num(minBySeg[seg])
          if (v != null) acc[seg] = v
          return acc
        }, {}),
        leverage_by_segment: ALL_SEGMENTS.reduce((acc, seg) => {
          const v = num(levBySeg[seg])
          if (v != null) acc[seg] = v   // backend clamps to the live per-segment max
          return acc
        }, {}),
        lot_size_by_segment: LOT_SEGMENTS.reduce((acc, seg) => {
          const v = num(lotBySeg[seg])
          if (v != null) acc[seg] = v
          return acc
        }, {}),
        min_total_open: num(minTotal),
        min_capital_per_trade: num(minCap),
        brain_handoff_trades: num(handoff),
        screen_min_pct: num(minPct),
        screen_min_quote_volume: num(minVol),
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

      {/* Exit controls — wide trailing stop + far take-profit = hold trades longer */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 10 }}>
        <Field label="Trailing mode" hint="pct = wide & predictable">
          <select value={trailMode} onChange={(e) => setTrailMode(e.target.value)} style={inputStyle}>
            <option value="pct">% trail</option>
            <option value="atr">ATR ×</option>
          </select>
        </Field>
        <Field label="Trailing stop %" hint="rides up, locks gains">
          <input type="number" step="0.5" min="0" value={trailPct}
            onChange={(e) => setTrailPct(e.target.value)} placeholder="3.5" style={inputStyle}
            disabled={trailMode === 'atr'} />
        </Field>
        <Field label="Take-profit %" hint="0 = ride trail only">
          <input type="number" step="0.5" min="0" value={takeProfit}
            onChange={(e) => setTakeProfit(e.target.value)} placeholder="7" style={inputStyle} />
        </Field>
      </div>

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

      {/* ── who's in control: MANUAL (these sliders + auto-open) until the brain learns ── */}
      <ControlBanner status={status} />

      {/* ── AUTO-OPEN basket: open trades on screened candidates (temporary, manual phase) ── */}
      <div style={{ borderTop: `1px solid ${T.gridline}`, paddingTop: 10, display: 'flex', flexDirection: 'column', gap: 10 }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, fontWeight: 700, color: T.text, cursor: 'pointer' }}>
          <input type="checkbox" checked={autoOpen} onChange={(e) => setAutoOpen(e.target.checked)} />
          Auto-open screened trades
          <span style={{ fontSize: 10, fontWeight: 400, color: T.muted }}>top-N ranked + min-per-segment floor</span>
        </label>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 10 }}>
          <Field label="Top-N / segment" hint="primary: open this many ranked">
            <input type="number" step="1" min="0" value={topN}
              onChange={(e) => setTopN(e.target.value)} placeholder="2" style={inputStyle} />
          </Field>
          <Field label="Min open / segment" hint="default floor (all segments)">
            <input type="number" step="1" min="0" value={minOpen}
              onChange={(e) => setMinOpen(e.target.value)} placeholder="0" style={inputStyle} />
          </Field>
          <Field label="Min total open" hint="global floor across all segments">
            <input type="number" step="1" min="0" value={minTotal}
              onChange={(e) => setMinTotal(e.target.value)} placeholder="0" style={inputStyle} />
          </Field>
          <Field label="Min capital / trade" hint="each trade deploys ≥ this">
            <input type="number" step="100" min="0" value={minCap}
              onChange={(e) => setMinCap(e.target.value)} placeholder="0" style={inputStyle} />
          </Field>
          <Field label="Brain takes over after" hint="closed trades to learn from">
            <input type="number" step="1" min="0" value={handoff}
              onChange={(e) => setHandoff(e.target.value)} placeholder="30" style={inputStyle} />
          </Field>
        </div>
        {/* per-segment min-open OVERRIDES (blank = use the default floor above) */}
        <div>
          <span style={{ fontSize: 10, color: T.muted, textTransform: 'uppercase', letterSpacing: 0.4 }}>
            Min open per segment (override)
          </span>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 8, marginTop: 6 }}>
            {ALL_SEGMENTS.map((seg) => (
              <label key={seg} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <span style={{ fontSize: 9.5, color: T.muted }}>{seg}</span>
                <input type="number" step="1" min="0" value={minBySeg[seg] ?? ''}
                  onChange={(e) => setMinBySeg((m) => ({ ...m, [seg]: e.target.value }))}
                  placeholder="—" style={{ ...inputStyle, padding: '5px 7px', fontSize: 12 }} />
              </label>
            ))}
          </div>
        </div>

        {/* per-segment LEVERAGE overrides — capped at the live max per segment */}
        <div>
          <span style={{ fontSize: 10, color: T.muted, textTransform: 'uppercase', letterSpacing: 0.4 }}>
            Leverage per segment <span style={{ textTransform: 'none' }}>(blank = default; max shown)</span>
          </span>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 8, marginTop: 6 }}>
            {ALL_SEGMENTS.map((seg) => {
              const cap = (status?.leverage_limits || MAX_LEV)[seg] ?? MAX_LEV[seg]
              const locked = cap <= 1
              return (
                <label key={seg} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <span style={{ fontSize: 9.5, color: T.muted }}>{seg} <span style={{ color: T.accent }}>≤{cap}×</span></span>
                  <input type="number" step="0.5" min="1" max={cap} value={levBySeg[seg] ?? ''}
                    disabled={locked}
                    onChange={(e) => setLevBySeg((m) => ({ ...m, [seg]: e.target.value }))}
                    placeholder={locked ? '1' : String(DEFAULT_LEV[seg] ?? 1)}
                    style={{ ...inputStyle, padding: '5px 7px', fontSize: 12, opacity: locked ? 0.5 : 1 }} />
                </label>
              )
            })}
          </div>
        </div>

        {/* per-segment LOT SIZE (F&O / options / commodities trade in whole lots) */}
        <div>
          <span style={{ fontSize: 10, color: T.muted, textTransform: 'uppercase', letterSpacing: 0.4 }}>
            Lot size per segment <span style={{ textTransform: 'none' }}>(qty = lots × lot size; blank = default)</span>
          </span>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 8, marginTop: 6 }}>
            {LOT_SEGMENTS.map((seg) => {
              const def = (status?.lot_defaults || DEFAULT_LOT)[seg] ?? DEFAULT_LOT[seg]
              return (
                <label key={seg} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <span style={{ fontSize: 9.5, color: T.muted }}>{seg}</span>
                  <input type="number" step="1" min="1" value={lotBySeg[seg] ?? ''}
                    onChange={(e) => setLotBySeg((m) => ({ ...m, [seg]: e.target.value }))}
                    placeholder={String(def)} style={{ ...inputStyle, padding: '5px 7px', fontSize: 12 }} />
                </label>
              )
            })}
          </div>
        </div>

        <button onClick={closeAll} disabled={closing}
          style={{ alignSelf: 'flex-start', background: T.panel2, color: closing ? T.muted : T.bad,
            border: `1px solid ${T.bad}`, borderRadius: 8, padding: '7px 14px',
            cursor: closing ? 'not-allowed' : 'pointer', fontSize: 12, fontWeight: 700 }}>
          ✖ Close all open trades
        </button>
      </div>

      {/* ── screener FILTERS (narrow the candidate set) ── */}
      <div style={{ borderTop: `1px solid ${T.gridline}`, paddingTop: 10 }}>
        <span style={{ fontSize: 10, color: T.muted, textTransform: 'uppercase', letterSpacing: 0.4 }}>Screener filters</span>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 10, marginTop: 6 }}>
          <Field label="Min %change" hint="abs % move (NSE + crypto)">
            <input type="number" step="0.5" min="0" value={minPct}
              onChange={(e) => setMinPct(e.target.value)} placeholder="0" style={inputStyle} />
          </Field>
          <Field label="Min quote volume" hint="crypto (USDT vol)">
            <input type="number" step="1000000" min="0" value={minVol}
              onChange={(e) => setMinVol(e.target.value)} placeholder="0" style={inputStyle} />
          </Field>
        </div>
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
