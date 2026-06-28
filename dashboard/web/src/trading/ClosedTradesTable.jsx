// ClosedTradesTable.jsx — Phase T6 (Dark Pro UI)
// The full 85+/110-column closed-trades journal. Presentational / props-driven,
// inline-styled via ./theme.js, dependency-free (no table libs). Features:
//   - sortable columns (click header toggles asc → desc → unsorted)
//   - free-text filter across all cells
//   - column chooser (toggle individual columns; defaults to a ~15-col subset,
//     with a "show all" switch since there can be 110 columns)
//   - CSV export built from the CURRENT (visible) columns + filtered rows
//   - row click → onRowClick(row)
// Renders fine with empty/missing props (tasteful empty state, never crashes).
import { useMemo, useState } from 'react'
import { T, pnlColor } from './theme.js'

// Default ~15-column subset to show first (matched case-insensitively, in order).
// Anything else stays hidden until the user opts in via the column chooser.
const DEFAULT_VISIBLE = [
  'id', 'trade_id', 'symbol', 'instrument', 'direction', 'side',
  'entry_time', 'exit_time', 'entry_price', 'exit_price', 'qty', 'quantity',
  'net_pnl', 'pnl', 'net_pnl_pct', 'r_multiple', 'strategy',
]

function isPnlLike(name) {
  if (!name) return false
  const n = String(name).toLowerCase()
  return n.includes('pnl') || n.includes('p&l') || n.includes('r_multiple') || n === 'r' || n.includes('rmultiple')
}

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

// Mixed numeric/string compare so sorting "just works" on a journal of both.
function compare(a, b) {
  const na = toNumber(a)
  const nb = toNumber(b)
  if (na != null && nb != null) return na - nb
  const sa = a == null ? '' : String(a)
  const sb = b == null ? '' : String(b)
  return sa.localeCompare(sb, undefined, { numeric: true })
}

function csvEscape(v) {
  const s = v == null ? '' : String(v)
  if (/[",\n]/.test(s)) return '"' + s.replace(/"/g, '""') + '"'
  return s
}

export default function ClosedTradesTable({ columns, rows, onRowClick }) {
  const allCols = Array.isArray(columns) ? columns : []
  const data = Array.isArray(rows) ? rows : []

  const [filter, setFilter] = useState('')
  const [sort, setSort] = useState({ col: null, dir: 1 }) // dir: 1 asc, -1 desc, 0 none
  const [showAll, setShowAll] = useState(false)
  const [chooserOpen, setChooserOpen] = useState(false)
  // Explicit per-column visibility overrides; undefined → fall back to default rule.
  const [overrides, setOverrides] = useState({})

  // Is a column visible right now? showAll forces everything; otherwise use the
  // explicit override, else the DEFAULT_VISIBLE membership rule.
  const isVisible = (c) => {
    if (showAll) return true
    if (c in overrides) return overrides[c]
    return DEFAULT_VISIBLE.includes(String(c).toLowerCase())
  }

  const visibleCols = useMemo(
    () => allCols.filter(isVisible),
    [allCols, overrides, showAll],
  )

  // Filter across ALL cells of a row (not just visible ones), case-insensitive.
  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase()
    if (!q) return data
    return data.filter((row) =>
      allCols.some((c) => {
        const v = row ? row[c] : undefined
        return v != null && String(v).toLowerCase().includes(q)
      }),
    )
  }, [data, allCols, filter])

  const sorted = useMemo(() => {
    if (!sort.col || sort.dir === 0) return filtered
    const arr = filtered.slice()
    arr.sort((ra, rb) => sort.dir * compare(ra ? ra[sort.col] : undefined, rb ? rb[sort.col] : undefined))
    return arr
  }, [filtered, sort])

  const toggleSort = (c) => {
    setSort((s) => {
      if (s.col !== c) return { col: c, dir: 1 }
      if (s.dir === 1) return { col: c, dir: -1 }
      return { col: null, dir: 0 } // third click clears the sort
    })
  }

  const toggleCol = (c) => {
    setOverrides((o) => ({ ...o, [c]: !isVisible(c) }))
  }

  // CSV export from the CURRENT visible columns + filtered/sorted rows.
  const exportCsv = () => {
    const cols = visibleCols
    const lines = [cols.map(csvEscape).join(',')]
    for (const row of sorted) {
      lines.push(cols.map((c) => csvEscape(row ? row[c] : '')).join(','))
    }
    const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `closed_trades_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}.csv`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const wrap = {
    background: T.panel,
    border: `1px solid ${T.border}`,
    borderRadius: 8,
    overflow: 'hidden',
    color: T.text,
    width: '100%',
    fontFamily: 'system-ui, sans-serif',
    position: 'relative',
  }

  const btn = {
    background: T.panel2,
    color: T.text,
    border: `1px solid ${T.border}`,
    borderRadius: 6,
    padding: '5px 10px',
    fontSize: 12,
    cursor: 'pointer',
  }

  // Header / toolbar (always rendered, even when empty).
  const toolbar = (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '8px 12px',
        borderBottom: `1px solid ${T.border}`,
        flexWrap: 'wrap',
      }}
    >
      <span style={{ fontWeight: 600, letterSpacing: 0.4, marginRight: 'auto' }}>
        Closed Trades{' '}
        <span style={{ color: T.muted, fontWeight: 400, fontSize: 12 }}>
          ({sorted.length}/{data.length} · {visibleCols.length}/{allCols.length} cols)
        </span>
      </span>

      <input
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        placeholder="filter all cells…"
        style={{
          background: T.bg,
          color: T.text,
          border: `1px solid ${T.border}`,
          borderRadius: 6,
          padding: '5px 9px',
          fontSize: 12,
          width: 180,
          outline: 'none',
        }}
      />

      <label style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 12, color: T.muted, cursor: 'pointer' }}>
        <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} />
        show all
      </label>

      <button style={btn} onClick={() => setChooserOpen((v) => !v)}>
        Columns ▾
      </button>
      <button style={{ ...btn, color: T.accent, borderColor: T.accent }} onClick={exportCsv}>
        Export CSV
      </button>
    </div>
  )

  // Column chooser dropdown (toggle individual columns on/off).
  const chooser = chooserOpen && (
    <div
      style={{
        position: 'absolute',
        right: 12,
        top: 46,
        zIndex: 10,
        background: T.panel2,
        border: `1px solid ${T.border}`,
        borderRadius: 8,
        padding: 8,
        maxHeight: 320,
        overflowY: 'auto',
        width: 240,
        boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
      }}
    >
      <div style={{ fontSize: 11, color: T.muted, padding: '2px 4px 6px', textTransform: 'uppercase', letterSpacing: 0.6 }}>
        toggle columns
      </div>
      {allCols.map((c) => (
        <label
          key={c}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            fontSize: 12,
            padding: '3px 4px',
            color: T.text,
            cursor: showAll ? 'not-allowed' : 'pointer',
            opacity: showAll ? 0.5 : 1,
          }}
        >
          <input
            type="checkbox"
            disabled={showAll}
            checked={isVisible(c)}
            onChange={() => toggleCol(c)}
          />
          {c}
        </label>
      ))}
    </div>
  )

  if (allCols.length === 0 || data.length === 0) {
    return (
      <div style={wrap}>
        {toolbar}
        {chooser}
        <div style={{ padding: '36px 16px', textAlign: 'center', color: T.muted, fontSize: 13 }}>
          <div style={{ fontSize: 28, marginBottom: 6, opacity: 0.5 }}>▤</div>
          no closed trades
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
    cursor: 'pointer',
    userSelect: 'none',
  }

  const arrow = (c) => {
    if (sort.col !== c || sort.dir === 0) return ''
    return sort.dir === 1 ? ' ▲' : ' ▼'
  }

  return (
    <div style={wrap}>
      {toolbar}
      {chooser}
      <div style={{ overflowX: 'auto', maxHeight: 480, overflowY: 'auto' }}>
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
              {visibleCols.map((c) => (
                <th key={c} style={thStyle} onClick={() => toggleSort(c)} title={`Sort by ${c}`}>
                  {c}
                  {arrow(c)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((row, ri) => (
              <tr
                key={ri}
                onClick={() => onRowClick && onRowClick(row)}
                style={{
                  background: ri % 2 ? T.panel : T.panel2,
                  borderBottom: `1px solid ${T.gridline}`,
                  cursor: onRowClick ? 'pointer' : 'default',
                }}
              >
                {visibleCols.map((c) => {
                  const raw = row ? row[c] : undefined
                  const pnl = isPnlLike(c)
                  return (
                    <td
                      key={c}
                      style={{
                        padding: '6px 10px',
                        whiteSpace: 'nowrap',
                        color: pnl ? pnlColor(toNumber(raw)) : T.text,
                        fontWeight: pnl ? 600 : 400,
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
