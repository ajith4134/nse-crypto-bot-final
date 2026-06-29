// OrderFlowMap.jsx — Phase T6 (Dark Pro UI)
// Custom order-book depth + flow visualization (the blueprint's "OrderFlowMap
// primitive"). Pure divs/SVG, no external chart lib. Themed via ./theme.js.
// Presentational / props-driven. Renders fine with NO props (deterministic demo book).
import { T } from './theme.js'

// --- DEMO DATA (deterministic) -------------------------------------------------
// Generated only when no bids/asks supplied so the build/preview always shows
// something. Clearly marked as demo in the UI.
function demoBook(mid = 30000, levels = 12) {
  let seed = 9001
  const rnd = () => {
    seed |= 0
    seed = (seed + 0x6d2b79f5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
  const tick = 5
  const bids = []
  const asks = []
  for (let i = 0; i < levels; i++) {
    const bp = mid - tick * (i + 1)
    const ap = mid + tick * (i + 1)
    // sizes taper out away from mid, with deterministic jitter.
    const taper = 1 - i / (levels + 4)
    bids.push([round2(bp), round2((0.5 + rnd() * 6) * taper)])
    asks.push([round2(ap), round2((0.5 + rnd() * 6) * taper)])
  }
  return { bids, asks } // bids descending, asks ascending
}

function round2(v) {
  return Math.round(v * 100) / 100
}

function fmtPrice(p) {
  return p.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function fmtSize(s) {
  return s.toLocaleString(undefined, { minimumFractionDigits: 3, maximumFractionDigits: 3 })
}

function withAlpha(hex, a) {
  const h = hex.replace('#', '')
  const r = parseInt(h.substring(0, 2), 16)
  const g = parseInt(h.substring(2, 4), 16)
  const b = parseInt(h.substring(4, 6), 16)
  return `rgba(${r}, ${g}, ${b}, ${a})`
}

export default function OrderFlowMap({ bids, asks, height = 320, symbol = 'BTCUSDT' }) {
  const isDemo = !bids || !asks
  let bk = isDemo ? demoBook() : { bids, asks }

  const LEVELS = 20      // full L2 depth (matches the /api/trading/orderbook ladder)
  const topBids = (bk.bids || []).slice(0, LEVELS)
  const topAsks = (bk.asks || []).slice(0, LEVELS)

  const bestBid = topBids.length ? topBids[0][0] : 0
  const bestAsk = topAsks.length ? topAsks[0][0] : 0
  const mid = bestBid && bestAsk ? (bestBid + bestAsk) / 2 : bestBid || bestAsk
  const spread = bestBid && bestAsk ? bestAsk - bestBid : 0
  const spreadPct = mid ? (spread / mid) * 100 : 0

  // Bar widths are proportional to the largest single level size on either side.
  const maxSize = Math.max(
    1e-9,
    ...topBids.map((l) => l[1]),
    ...topAsks.map((l) => l[1]),
  )

  // Cumulative depth for the shaded background (totals per side).
  const cumBids = []
  let runB = 0
  for (const l of topBids) {
    runB += l[1]
    cumBids.push(runB)
  }
  const cumAsks = []
  let runA = 0
  for (const l of topAsks) {
    runA += l[1]
    cumAsks.push(runA)
  }
  const maxCum = Math.max(1e-9, runB, runA)

  const rowH = Math.max(14, Math.floor((height - 70) / LEVELS))

  const wrap = {
    background: T.panel,
    border: `1px solid ${T.border}`,
    borderRadius: 8,
    overflow: 'hidden',
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
    color: T.text,
    width: '100%',
  }

  return (
    <div style={wrap}>
      {/* Header: symbol, mid, spread, demo badge */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 12px',
          borderBottom: `1px solid ${T.border}`,
          fontFamily: 'system-ui, sans-serif',
        }}
      >
        <span style={{ fontWeight: 600, letterSpacing: 0.4 }}>{symbol} · Order Flow</span>
        <span style={{ display: 'flex', gap: 12, alignItems: 'center', fontSize: 12 }}>
          <span style={{ color: T.muted }}>
            mid <span style={{ color: T.text }}>{fmtPrice(mid)}</span>
          </span>
          <span style={{ color: T.muted }}>
            spread{' '}
            <span style={{ color: T.accent }}>
              {fmtPrice(spread)} ({spreadPct.toFixed(3)}%)
            </span>
          </span>
          {isDemo && (
            <span
              style={{
                fontSize: 10,
                color: T.warn,
                border: `1px solid ${T.warn}`,
                borderRadius: 4,
                padding: '1px 6px',
                textTransform: 'uppercase',
                letterSpacing: 0.6,
              }}
            >
              demo data
            </span>
          )}
        </span>
      </div>

      {/* Two-column depth ladder: bids (left, green) | asks (right, red) */}
      <div style={{ display: 'flex' }}>
        {/* BIDS */}
        <div style={{ flex: 1, borderRight: `1px solid ${T.border}` }}>
          <ColumnHeader left="size" right="bid" />
          {topBids.map((lvl, i) => (
            <DepthRow
              key={`b${i}`}
              price={lvl[0]}
              size={lvl[1]}
              maxSize={maxSize}
              cum={cumBids[i]}
              maxCum={maxCum}
              side="bid"
              rowH={rowH}
            />
          ))}
        </div>
        {/* ASKS */}
        <div style={{ flex: 1 }}>
          <ColumnHeader left="ask" right="size" />
          {topAsks.map((lvl, i) => (
            <DepthRow
              key={`a${i}`}
              price={lvl[0]}
              size={lvl[1]}
              maxSize={maxSize}
              cum={cumAsks[i]}
              maxCum={maxCum}
              side="ask"
              rowH={rowH}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

function ColumnHeader({ left, right }) {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        padding: '4px 10px',
        fontSize: 10,
        textTransform: 'uppercase',
        letterSpacing: 0.8,
        color: T.muted,
        borderBottom: `1px solid ${T.gridline}`,
      }}
    >
      <span>{left}</span>
      <span>{right}</span>
    </div>
  )
}

function DepthRow({ price, size, maxSize, cum, maxCum, side, rowH }) {
  const isBid = side === 'bid'
  const color = isBid ? T.good : T.bad
  const sizePct = Math.max(2, (size / maxSize) * 100)
  const cumPct = Math.max(0, (cum / maxCum) * 100)

  // Cumulative shading fills the row background; the per-level bar sits on top.
  // Bids grow from the right edge (toward the spread), asks from the left edge.
  const cumBg = {
    position: 'absolute',
    top: 0,
    bottom: 0,
    [isBid ? 'right' : 'left']: 0,
    width: `${cumPct}%`,
    background: withAlpha(color, 0.1),
  }
  const sizeBar = {
    position: 'absolute',
    top: 0,
    bottom: 0,
    [isBid ? 'right' : 'left']: 0,
    width: `${sizePct}%`,
    background: withAlpha(color, 0.28),
  }

  // Bids: price on the right (next to spread), size on the left. Asks mirror it.
  const sizeLabel = (
    <span style={{ color: T.muted, zIndex: 1 }}>{fmtSize(size)}</span>
  )
  const priceLabel = (
    <span style={{ color, fontWeight: 600, zIndex: 1 }}>{fmtPrice(price)}</span>
  )

  return (
    <div
      style={{
        position: 'relative',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        height: rowH,
        padding: '0 10px',
        fontSize: 12,
        borderBottom: `1px solid ${T.gridline}`,
      }}
    >
      <div style={cumBg} />
      <div style={sizeBar} />
      {isBid ? (
        <>
          {sizeLabel}
          {priceLabel}
        </>
      ) : (
        <>
          {priceLabel}
          {sizeLabel}
        </>
      )}
    </div>
  )
}
