// TickerTape.jsx — Phase T6 (Dark Pro UI)
// Horizontal scrolling ticker tape (top bar). Presentational / props-only,
// inline-styled via ./theme.js, no styles.css dependency. Robust to empty/missing
// props (renders a thin "no ticker data" bar, never crashes).
import { T, pnlColor } from './theme.js'

// Small per-market colour tag (NSE vs CRYPTO, fallback for anything else).
function marketTag(market) {
  const m = String(market || '').toUpperCase()
  if (m === 'NSE') return { label: 'NSE', color: T.accent }
  if (m === 'CRYPTO') return { label: 'CRYPTO', color: T.warn }
  return { label: m || '—', color: T.muted }
}

function fmtPrice(v) {
  if (v == null || v === '') return '—'
  if (typeof v === 'number') {
    return Number.isFinite(v)
      ? v.toLocaleString(undefined, { maximumFractionDigits: 2 })
      : '—'
  }
  return String(v)
}

function fmtPct(v) {
  if (v == null || v === '' || (typeof v === 'number' && !Number.isFinite(v))) return '—'
  const n = typeof v === 'number' ? v : Number(v)
  if (!Number.isFinite(n)) return String(v)
  const sign = n > 0 ? '+' : ''
  return `${sign}${n.toFixed(2)}%`
}

function TickerItem({ t }) {
  const tag = marketTag(t && t.market)
  const pct = t ? t.change_pct : null
  const num = typeof pct === 'number' ? pct : Number(pct)
  const up = Number.isFinite(num) ? num >= 0 : true
  const color = pnlColor(Number.isFinite(num) ? num : null)

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 8,
        padding: '0 18px',
        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
        fontSize: 13,
        whiteSpace: 'nowrap',
      }}
    >
      <span
        style={{
          fontSize: 9,
          fontWeight: 700,
          letterSpacing: 0.5,
          color: tag.color,
          border: `1px solid ${tag.color}`,
          borderRadius: 4,
          padding: '1px 4px',
          opacity: 0.85,
        }}
      >
        {tag.label}
      </span>
      <span style={{ fontWeight: 700, color: T.text }}>{(t && t.symbol) || '—'}</span>
      <span style={{ color: T.muted }}>{fmtPrice(t && t.last)}</span>
      <span style={{ color, fontWeight: 600 }}>
        {Number.isFinite(num) ? (up ? '▲' : '▼') : ''} {fmtPct(pct)}
      </span>
    </span>
  )
}

export default function TickerTape({ tickers }) {
  const data = Array.isArray(tickers) ? tickers.filter(Boolean) : []

  const bar = {
    background: T.panel2,
    borderBottom: `1px solid ${T.border}`,
    color: T.text,
    width: '100%',
    fontFamily: 'system-ui, sans-serif',
    overflow: 'hidden',
  }

  if (data.length === 0) {
    return (
      <div
        style={{
          ...bar,
          padding: '6px 12px',
          fontSize: 12,
          color: T.muted,
          textAlign: 'center',
          letterSpacing: 0.5,
        }}
      >
        no ticker data
      </div>
    )
  }

  // Duplicate the content once so the marquee can scroll seamlessly (-50%).
  const track = data.concat(data)

  return (
    <div style={bar} className="ticker-tape">
      <style>{`
        @keyframes ticker-scroll {
          0%   { transform: translateX(0); }
          100% { transform: translateX(-50%); }
        }
        .ticker-tape .ticker-track {
          display: inline-flex;
          align-items: center;
          padding: 7px 0;
          animation: ticker-scroll 40s linear infinite;
          will-change: transform;
        }
        .ticker-tape:hover .ticker-track {
          animation-play-state: paused;
        }
      `}</style>
      <div style={{ whiteSpace: 'nowrap' }}>
        <div className="ticker-track">
          {track.map((t, i) => (
            <TickerItem key={`${t && t.symbol}-${i}`} t={t} />
          ))}
        </div>
      </div>
    </div>
  )
}
