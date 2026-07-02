// OpenTradesPanel.jsx — Phase T6 (Dark Pro UI)
// Live "Open Trades" table (blueprint §4, ~22 columns). Presentational / props-only,
// inline-styled via ./theme.js, no styles.css dependency. Renders fine with empty
// or missing props (shows a tasteful "no open positions" empty state, never crashes).
import { T, pnlColor } from './theme.js'

// A column carries P&L semantics if its name mentions P&L / PnL (case-insensitive).
function isPnlColumn(name) {
  if (!name) return false
  const n = String(name).toLowerCase().replace(/[\s_-]/g, '')
  return n.includes('p&l') || n.includes('pnl')
}

// Best-effort numeric parse for colouring (handles "1,234.5", "-12%", "₹50").
function toNumber(v) {
  if (v == null) return null
  if (typeof v === 'number') return Number.isFinite(v) ? v : null
  const cleaned = String(v).replace(/[^0-9.+-]/g, '')
  if (cleaned === '' || cleaned === '-' || cleaned === '+' || cleaned === '.') return null
  const n = Number(cleaned)
  return Number.isFinite(n) ? n : null
}

function fmtCell(v) {
  if (v == null || v === '') return '—'
  return String(v)
}

// Summary bar: NSE (₹) + Binance ($) kept SEPARATE (different currencies, never blindly added),
// plus a grand total converted to ₹ via the live USD→INR rate. Reused by open + closed tables.
export function TotalsBar({ totals, label = 'Unrealized' }) {
  if (!totals) return null
  const pnl = (v, sym) => {
    const n = Number(v) || 0
    return <b style={{ color: n > 0 ? T.good : n < 0 ? T.bad : T.muted }}>{n >= 0 ? '+' : '−'}{sym}{Math.abs(n).toLocaleString(undefined, { maximumFractionDigits: 2 })}</b>
  }
  const cell = { display: 'flex', flexDirection: 'column', gap: 1, minWidth: 90 }
  const lab = { fontSize: 9.5, color: T.muted, textTransform: 'uppercase', letterSpacing: 0.5 }
  return (
    <div style={{ display: 'flex', gap: 18, alignItems: 'center', flexWrap: 'wrap',
      padding: '8px 12px', background: T.panel2, borderBottom: `1px solid ${T.border}`,
      fontFamily: 'ui-monospace, Menlo, monospace', fontSize: 14 }}>
      <div style={cell}><span style={lab}>NSE {label} (₹)</span>{pnl(totals.nse_pnl, '₹')}</div>
      <div style={cell}><span style={lab}>Binance {label} ($)</span>{pnl(totals.binance_pnl, '$')}</div>
      <div style={cell}>
        <span style={lab}>Total ≈ ₹ (converted)</span>
        <span style={{ fontSize: 16 }}>{pnl(totals.total_inr, '₹')}</span>
      </div>
      {totals.usdinr != null && <div style={cell}><span style={lab}>USD→INR</span><b style={{ color: T.muted }}>{Number(totals.usdinr).toFixed(2)}</b></div>}
    </div>
  )
}

export default function OpenTradesPanel({ columns, rows, totals }) {
  const cols = Array.isArray(columns) ? columns : []
  const data = Array.isArray(rows) ? rows : []

  const wrap = {
    background: T.panel,
    border: `1px solid ${T.border}`,
    borderRadius: 8,
    overflow: 'hidden',
    color: T.text,
    width: '100%',
    fontFamily: 'system-ui, sans-serif',
  }

  const header = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '8px 12px',
    borderBottom: `1px solid ${T.border}`,
  }

  const empty = {
    padding: '36px 16px',
    textAlign: 'center',
    color: T.muted,
    fontSize: 13,
  }

  // Empty state — either no columns to render or no rows of data.
  if (cols.length === 0 || data.length === 0) {
    return (
      <div style={wrap}>
        <div style={header}>
          <span style={{ fontWeight: 600, letterSpacing: 0.4 }}>Open Trades</span>
          <span style={{ fontSize: 12, color: T.muted }}>{data.length} open</span>
        </div>
        <div style={empty}>
          <div style={{ fontSize: 28, marginBottom: 6, opacity: 0.5 }}>○</div>
          no open positions
        </div>
      </div>
    )
  }

  const thStyle = {
    position: 'sticky',
    top: 0,
    zIndex: 2,
    background: T.panel2,
    color: T.muted,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
    fontSize: 10,
    fontWeight: 600,
    textAlign: 'left',
    padding: '7px 10px',
    borderBottom: `1px solid ${T.border}`,
    whiteSpace: 'nowrap',
  }

  return (
    <div style={wrap}>
      <div style={header}>
        <span style={{ fontWeight: 600, letterSpacing: 0.4 }}>Open Trades</span>
        <span style={{ fontSize: 12, color: T.good }}>{data.length} open</span>
      </div>
      <TotalsBar totals={totals} label="Unrealized" />

      <div style={{ overflowX: 'auto', maxHeight: 420, overflowY: 'auto' }}>
        <table
          style={{
            borderCollapse: 'collapse',
            width: '100%',
            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
            fontSize: 12,
          }}
        >
          <thead>
            <tr>
              {cols.map((c) => (
                <th key={c} style={thStyle}>
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row, ri) => (
              <tr
                key={ri}
                style={{
                  background: ri % 2 ? T.panel : T.panel2,
                  borderBottom: `1px solid ${T.gridline}`,
                }}
              >
                {cols.map((c) => {
                  const raw = row ? row[c] : undefined
                  let color = T.text
                  let weight = 400

                  const cl = String(c || '').toLowerCase()
                  if (isPnlColumn(c)) {
                    color = pnlColor(toNumber(raw))
                    weight = 600
                  } else if (/direction|side/i.test(c)) {
                    const v = String(raw || '').toUpperCase()
                    if (v.includes('LONG') || v === 'BUY') color = T.good
                    else if (v.includes('SHORT') || v === 'SELL') color = T.bad
                    weight = 600
                  } else if (!cl.includes('time') && (cl.includes('peak_profit') || cl === 'mfe')) {
                    color = T.good; weight = 600   // peak profit / MFE magnitude → green
                  } else if (!cl.includes('time') && (cl.includes('peak_loss') || cl === 'mae')) {
                    color = T.bad; weight = 600    // peak loss / MAE magnitude → red
                  }

                  return (
                    <td
                      key={c}
                      style={{
                        padding: '6px 10px',
                        whiteSpace: 'nowrap',
                        color,
                        fontWeight: weight,
                      }}
                    >
                      {fmtCell(raw)}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
