// TradeDrilldown.jsx — Phase T6 (Dark Pro UI)
// Modal/overlay single closed-trade view. Presentational / props-only, inline-styled
// via ./theme.js. `trade` null/undefined → renders nothing. Includes a self-contained
// inline-SVG "trade replay" (no chart library, no other component imports).
// Robust to missing fields (shows "—").
import { T, pnlColor } from './theme.js'

// Read the first present key from a list of candidate field names.
function pick(obj, keys) {
  for (const k of keys) {
    if (obj && obj[k] != null && obj[k] !== '') return obj[k]
  }
  return null
}

function toNumber(v) {
  if (v == null) return null
  if (typeof v === 'number') return Number.isFinite(v) ? v : null
  const cleaned = String(v).replace(/[^0-9.+-]/g, '')
  if (cleaned === '' || cleaned === '-' || cleaned === '+' || cleaned === '.') return null
  const n = Number(cleaned)
  return Number.isFinite(n) ? n : null
}

function fmt(v) {
  if (v == null || v === '') return '—'
  return String(v)
}

function fmtNum(v, dp = 2) {
  const n = toNumber(v)
  if (n == null) return '—'
  return n.toLocaleString(undefined, { minimumFractionDigits: dp, maximumFractionDigits: dp })
}

export default function TradeDrilldown({ trade, onClose }) {
  if (!trade) return null

  // --- field resolution (tolerant of varied journal column names) -------------
  const symbol = pick(trade, ['symbol', 'instrument', 'ticker'])
  const id = pick(trade, ['id', 'trade_id', 'tradeId'])
  const dir = pick(trade, ['direction', 'side'])
  const strategy = pick(trade, ['strategy', 'setup', 'strategy_name'])

  const entryPrice = pick(trade, ['entry_price', 'entryPrice', 'entry'])
  const exitPrice = pick(trade, ['exit_price', 'exitPrice', 'exit'])
  const entryTime = pick(trade, ['entry_time', 'entryTime', 'entered_at'])
  const exitTime = pick(trade, ['exit_time', 'exitTime', 'exited_at'])
  const qty = pick(trade, ['qty', 'quantity', 'size'])

  const grossPnl = pick(trade, ['gross_pnl', 'grossPnl', 'gross_p&l'])
  const charges = pick(trade, ['charges', 'fees', 'commission', 'total_charges'])
  const netPnl = pick(trade, ['net_pnl', 'netPnl', 'pnl', 'net_p&l'])
  const netPnlPct = pick(trade, ['net_pnl_pct', 'netPnlPct', 'pnl_pct', 'return_pct'])

  const mae = pick(trade, ['mae', 'MAE', 'max_adverse_excursion'])
  const mfe = pick(trade, ['mfe', 'MFE', 'max_favorable_excursion'])
  const rMultiple = pick(trade, ['r_multiple', 'rMultiple', 'r', 'rr'])
  const efficiency = pick(trade, ['efficiency', 'trade_efficiency'])

  const confidence = pick(trade, ['confidence', 'brain_confidence', 'conf'])
  const prediction = pick(trade, ['prediction', 'brain_prediction', 'predicted'])
  const correct = pick(trade, ['correct', 'brain_correct', 'was_correct'])

  const netNum = toNumber(netPnl)
  const netCol = pnlColor(netNum)

  // --- styles -----------------------------------------------------------------
  const overlay = {
    position: 'fixed',
    inset: 0,
    background: 'rgba(0,0,0,0.62)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000,
    fontFamily: 'system-ui, sans-serif',
  }
  const panel = {
    background: T.panel,
    border: `1px solid ${T.border}`,
    borderRadius: 10,
    color: T.text,
    width: 'min(720px, 94vw)',
    maxHeight: '90vh',
    overflowY: 'auto',
    boxShadow: '0 20px 60px rgba(0,0,0,0.6)',
  }

  return (
    <div style={overlay} onClick={onClose}>
      <div style={panel} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '12px 16px',
            borderBottom: `1px solid ${T.border}`,
            position: 'sticky',
            top: 0,
            background: T.panel,
            zIndex: 1,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
            <span style={{ fontWeight: 700, fontSize: 16 }}>{fmt(symbol)}</span>
            <span style={{ color: T.muted, fontSize: 12 }}>#{fmt(id)}</span>
            {dir && (
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  color: /short|sell/i.test(String(dir)) ? T.bad : T.good,
                  border: `1px solid ${/short|sell/i.test(String(dir)) ? T.bad : T.good}`,
                  borderRadius: 4,
                  padding: '1px 6px',
                  textTransform: 'uppercase',
                }}
              >
                {fmt(dir)}
              </span>
            )}
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: `1px solid ${T.border}`,
              color: T.text,
              borderRadius: 6,
              width: 28,
              height: 28,
              cursor: 'pointer',
              fontSize: 16,
              lineHeight: 1,
            }}
            aria-label="Close"
          >
            ×
          </button>
        </div>

        {/* Net P&L banner */}
        <div style={{ padding: '14px 16px', borderBottom: `1px solid ${T.gridline}` }}>
          <span style={{ color: T.muted, fontSize: 12, marginRight: 10 }}>Net P&L</span>
          <span style={{ color: netCol, fontWeight: 700, fontSize: 22 }}>{fmtNum(netPnl)}</span>
          {netPnlPct != null && (
            <span style={{ color: netCol, fontSize: 13, marginLeft: 8 }}>({fmtNum(netPnlPct)}%)</span>
          )}
        </div>

        {/* Trade replay (inline SVG) */}
        <div style={{ padding: '12px 16px', borderBottom: `1px solid ${T.gridline}` }}>
          <SectionTitle>Trade Replay</SectionTitle>
          <TradeReplay
            entryPrice={toNumber(entryPrice)}
            exitPrice={toNumber(exitPrice)}
            mae={toNumber(mae)}
            mfe={toNumber(mfe)}
            netNum={netNum}
          />
        </div>

        {/* Grouped fields */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))',
            gap: 12,
            padding: 16,
          }}
        >
          <Group title="Identity">
            <Field label="Symbol" value={fmt(symbol)} />
            <Field label="Trade ID" value={fmt(id)} />
            <Field label="Direction" value={fmt(dir)} />
            <Field label="Strategy" value={fmt(strategy)} />
            <Field label="Quantity" value={fmt(qty)} />
          </Group>

          <Group title="Execution">
            <Field label="Entry price" value={fmtNum(entryPrice)} />
            <Field label="Entry time" value={fmt(entryTime)} />
            <Field label="Exit price" value={fmtNum(exitPrice)} />
            <Field label="Exit time" value={fmt(exitTime)} />
          </Group>

          <Group title="P&L">
            <Field label="Gross" value={fmtNum(grossPnl)} color={pnlColor(toNumber(grossPnl))} />
            <Field label="Charges" value={fmtNum(charges)} />
            <Field label="Net" value={fmtNum(netPnl)} color={netCol} />
            <Field label="Net %" value={netPnlPct == null ? '—' : fmtNum(netPnlPct) + '%'} color={netCol} />
          </Group>

          <Group title="Quality">
            <Field label="MAE" value={fmtNum(mae)} />
            <Field label="MFE" value={fmtNum(mfe)} />
            <Field label="R-multiple" value={fmtNum(rMultiple)} color={pnlColor(toNumber(rMultiple))} />
            <Field label="Efficiency" value={fmt(efficiency)} />
          </Group>

          <Group title="Brain">
            <Field label="Confidence" value={fmt(confidence)} />
            <Field label="Prediction" value={fmt(prediction)} />
            <Field
              label="Correct"
              value={correct == null ? '—' : String(correct)}
              color={correct == null ? T.text : /true|1|yes|correct/i.test(String(correct)) ? T.good : T.bad}
            />
          </Group>
        </div>
      </div>
    </div>
  )
}

function SectionTitle({ children }) {
  return (
    <div
      style={{
        fontSize: 10,
        textTransform: 'uppercase',
        letterSpacing: 0.8,
        color: T.muted,
        marginBottom: 8,
      }}
    >
      {children}
    </div>
  )
}

function Group({ title, children }) {
  return (
    <div
      style={{
        background: T.panel2,
        border: `1px solid ${T.border}`,
        borderRadius: 8,
        padding: 12,
      }}
    >
      <SectionTitle>{title}</SectionTitle>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>{children}</div>
    </div>
  )
}

function Field({ label, value, color }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, fontSize: 13 }}>
      <span style={{ color: T.muted }}>{label}</span>
      <span
        style={{
          color: color || T.text,
          fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
          textAlign: 'right',
          wordBreak: 'break-word',
        }}
      >
        {value}
      </span>
    </div>
  )
}

// Self-contained inline-SVG mini replay: price line entry→exit, entry marker
// (accent), exit marker (pnl-coloured), optional shaded MAE/MFE band.
function TradeReplay({ entryPrice, exitPrice, mae, mfe, netNum }) {
  const W = 640
  const H = 140
  const padX = 28
  const padY = 24

  if (entryPrice == null || exitPrice == null) {
    return (
      <div
        style={{
          height: H,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: T.muted,
          fontSize: 12,
          border: `1px dashed ${T.border}`,
          borderRadius: 8,
        }}
      >
        no price data for replay
      </div>
    )
  }

  // Build the value range from all known points so the band fits in view.
  const vals = [entryPrice, exitPrice]
  if (mae != null) vals.push(mae)
  if (mfe != null) vals.push(mfe)
  let lo = Math.min(...vals)
  let hi = Math.max(...vals)
  if (hi === lo) {
    hi = lo + 1
    lo = lo - 1
  }
  const span = hi - lo

  const yOf = (v) => padY + (H - 2 * padY) * (1 - (v - lo) / span)
  const xEntry = padX
  const xExit = W - padX

  const exitCol = pnlColor(netNum)
  const yEntry = yOf(entryPrice)
  const yExit = yOf(exitPrice)

  const hasBand = mae != null && mfe != null
  const yBandTop = hasBand ? yOf(Math.max(mae, mfe)) : 0
  const yBandBot = hasBand ? yOf(Math.min(mae, mfe)) : 0

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      style={{ width: '100%', height: H, display: 'block', background: T.bg, borderRadius: 8 }}
      preserveAspectRatio="none"
    >
      {/* MAE/MFE shaded band */}
      {hasBand && (
        <rect
          x={padX}
          y={yBandTop}
          width={xExit - xEntry}
          height={Math.max(1, yBandBot - yBandTop)}
          fill={T.accent}
          opacity={0.1}
        />
      )}
      {hasBand && (
        <>
          <line x1={padX} y1={yOf(mfe)} x2={xExit} y2={yOf(mfe)} stroke={T.good} strokeWidth={1} strokeDasharray="4 4" opacity={0.5} />
          <line x1={padX} y1={yOf(mae)} x2={xExit} y2={yOf(mae)} stroke={T.bad} strokeWidth={1} strokeDasharray="4 4" opacity={0.5} />
        </>
      )}

      {/* price line entry → exit */}
      <line x1={xEntry} y1={yEntry} x2={xExit} y2={yExit} stroke={exitCol} strokeWidth={2} />

      {/* entry marker */}
      <circle cx={xEntry} cy={yEntry} r={5} fill={T.accent} stroke={T.bg} strokeWidth={1.5} />
      <text x={xEntry} y={yEntry - 9} fill={T.accent} fontSize={10} textAnchor="start" fontFamily="monospace">
        in {entryPrice}
      </text>

      {/* exit marker */}
      <circle cx={xExit} cy={yExit} r={5} fill={exitCol} stroke={T.bg} strokeWidth={1.5} />
      <text x={xExit} y={yExit - 9} fill={exitCol} fontSize={10} textAnchor="end" fontFamily="monospace">
        out {exitPrice}
      </text>
    </svg>
  )
}
