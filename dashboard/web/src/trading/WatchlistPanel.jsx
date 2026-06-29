// WatchlistPanel.jsx — Watchlist / Screener (Dark Pro UI)
// Presentational / props-only (like OpenTradesPanel): renders the active watchlist
// symbols the loop is trading plus the screened "candidates" sub-list, grouped by
// segment with a small segment chip. Inline-styled via ./theme.js, robust to missing
// props (optional chaining everywhere; tasteful "screener warming up" empty state).
import { T } from './theme.js'

const MARKETS = ['NSE', 'CRYPTO']

// Best-effort numeric parse (handles numbers, "1,234.5", "₹50", null).
function num(v) {
  if (v == null) return null
  if (typeof v === 'number') return Number.isFinite(v) ? v : null
  const cleaned = String(v).replace(/[^0-9.+-]/g, '')
  if (cleaned === '' || cleaned === '-' || cleaned === '+' || cleaned === '.') return null
  const n = Number(cleaned)
  return Number.isFinite(n) ? n : null
}

function price(v) {
  const n = num(v)
  if (n == null) return '—'
  return n.toLocaleString(undefined, { maximumFractionDigits: 4 })
}

// Stable small palette per segment so chips read consistently across renders.
function segColor(seg) {
  const s = String(seg || '').toUpperCase()
  if (/EQ|EQUITY|CASH|SPOT/.test(s)) return T.accent
  if (/FUT|FUTURE/.test(s)) return T.warn
  if (/OPT|OPTION|CE|PE/.test(s)) return T.good
  if (/PERP|SWAP|MARGIN/.test(s)) return T.bad
  return T.muted
}

function SegChip({ seg }) {
  const c = segColor(seg)
  return (
    <span
      style={{
        fontSize: 9.5,
        fontWeight: 700,
        letterSpacing: 0.4,
        color: c,
        border: `1px solid ${c}`,
        borderRadius: 10,
        padding: '1px 7px',
        textTransform: 'uppercase',
        whiteSpace: 'nowrap',
      }}
    >
      {String(seg || '—')}
    </span>
  )
}

// Group a flat list of {segment,...} rows into { segment: [rows] } in stable order.
function groupBySegment(list) {
  const out = {}
  for (const row of Array.isArray(list) ? list : []) {
    const seg = (row && row.segment) || '—'
    if (!out[seg]) out[seg] = []
    out[seg].push(row)
  }
  return out
}

// One market column: active watchlist on top, screened candidates below.
function MarketColumn({ market, watchlist, candidates }) {
  const wl = Array.isArray(watchlist) ? watchlist : []
  const cand = (Array.isArray(candidates) ? candidates : [])
    .slice()
    .sort((a, b) => (num(b?.score) ?? -Infinity) - (num(a?.score) ?? -Infinity))

  const wlGroups = groupBySegment(wl)
  const accent = market === 'CRYPTO' ? T.warn : T.accent

  const sub = {
    fontSize: 10,
    color: T.muted,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    margin: '0 0 6px',
  }

  return (
    <div
      style={{
        background: T.panel,
        border: `1px solid ${T.border}`,
        borderRadius: 10,
        padding: 12,
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        boxSizing: 'border-box',
        minWidth: 0,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontWeight: 700, fontSize: 14, color: accent }}>{market}</span>
        <span style={{ fontSize: 11, color: T.muted }}>{wl.length} trading · {cand.length} screened</span>
      </div>

      {/* active watchlist (what the loop is trading), grouped by segment */}
      <div>
        <p style={sub}>Trading now</p>
        {wl.length === 0 ? (
          <div style={{ fontSize: 12, color: T.muted, padding: '8px 0' }}>screener warming up…</div>
        ) : (
          Object.keys(wlGroups).map((seg) => (
            <div key={seg} style={{ marginBottom: 8 }}>
              <SegChip seg={seg} />
              <div style={{ marginTop: 5, display: 'flex', flexDirection: 'column', gap: 3 }}>
                {wlGroups[seg].map((r, i) => (
                  <div
                    key={`${r?.symbol || i}`}
                    style={{
                      display: 'flex',
                      alignItems: 'baseline',
                      gap: 8,
                      fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
                      fontSize: 12.5,
                      padding: '3px 8px',
                      background: i % 2 ? T.panel2 : 'transparent',
                      borderRadius: 6,
                    }}
                  >
                    <span style={{ fontWeight: 600, color: T.text }}>{r?.symbol || '—'}</span>
                    <span style={{ flex: 1 }} />
                    <span style={{ color: T.muted }}>{price(r?.last)}</span>
                  </div>
                ))}
              </div>
            </div>
          ))
        )}
      </div>

      {/* screened candidates (top by score) */}
      <div style={{ borderTop: `1px solid ${T.gridline}`, paddingTop: 10 }}>
        <p style={sub}>Candidates · top by score</p>
        {cand.length === 0 ? (
          <div style={{ fontSize: 12, color: T.muted, padding: '8px 0' }}>screener warming up…</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {cand.map((c, i) => {
              const score = num(c?.score)
              return (
                <div
                  key={`${c?.symbol || i}`}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    padding: '5px 8px',
                    background: i % 2 ? T.panel2 : 'transparent',
                    borderRadius: 6,
                    minWidth: 0,
                  }}
                  title={c?.reason || undefined}
                >
                  <span
                    style={{
                      fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
                      fontSize: 12.5,
                      fontWeight: 600,
                      color: T.text,
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {c?.symbol || '—'}
                  </span>
                  <SegChip seg={c?.segment} />
                  <span
                    style={{
                      flex: 1,
                      fontSize: 11,
                      color: T.muted,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                      minWidth: 0,
                    }}
                  >
                    {c?.reason || ''}
                  </span>
                  {score != null && (
                    <span
                      style={{
                        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
                        fontSize: 12,
                        fontWeight: 700,
                        color: accent,
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {score.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                    </span>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

export default function WatchlistPanel({ watchlist, candidates }) {
  const wl = watchlist || {}
  const cand = candidates || {}

  return (
    <div style={{ color: T.text, fontFamily: 'system-ui, sans-serif', width: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10, flexWrap: 'wrap' }}>
        <span style={{ fontWeight: 700, fontSize: 15, color: T.text }}>Watchlist / Screener</span>
        <span style={{ fontSize: 11, color: T.muted }}>symbols traded + screened candidates</span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 12 }}>
        {MARKETS.map((m) => (
          <MarketColumn
            key={m}
            market={m}
            watchlist={wl[m] || wl[m.toLowerCase()]}
            candidates={cand[m] || cand[m.toLowerCase()]}
          />
        ))}
      </div>
    </div>
  )
}
