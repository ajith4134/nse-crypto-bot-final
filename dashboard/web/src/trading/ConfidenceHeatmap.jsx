// ConfidenceHeatmap.jsx — Phase T6 (Dark Pro UI), blueprint §T6.10
// Brain Confidence Score heatmap. Presentational / props-only, inline-styled via
// ./theme.js, no styles.css dependency. Robust to empty/missing props.
import { T, scoreColor } from './theme.js'

function pct(v) {
  if (v == null || (typeof v === 'number' && !Number.isFinite(v))) return '—'
  const n = typeof v === 'number' ? v : Number(v)
  if (!Number.isFinite(n)) return '—'
  // Accept either 0..1 or 0..100 win_rate; confidence is always 0..1 here.
  return `${(n <= 1 ? n * 100 : n).toFixed(0)}%`
}

// Pick a readable text colour given the cell's confidence (dark on bright greens).
function textOn(conf) {
  const x = typeof conf === 'number' && Number.isFinite(conf) ? conf : 0
  return x >= 0.66 ? '#06140d' : T.text
}

function Cell({ s }) {
  const conf = s ? s.confidence : null
  const bg = scoreColor(conf)
  const fg = textOn(conf)
  const brier =
    s && s.brier != null && Number.isFinite(Number(s.brier))
      ? Number(s.brier).toFixed(3)
      : 'n/a'

  return (
    <div
      title={`${(s && s.symbol) || '—'} — brier: ${brier}`}
      style={{
        background: bg,
        border: `1px solid ${T.border}`,
        borderRadius: 6,
        padding: '10px 8px',
        minHeight: 64,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        color: fg,
        cursor: 'default',
      }}
    >
      <div
        style={{
          fontWeight: 700,
          fontSize: 12,
          letterSpacing: 0.3,
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
      >
        {(s && s.symbol) || '—'}
      </div>
      <div style={{ fontWeight: 700, fontSize: 20, lineHeight: 1 }}>
        {pct(conf)}
      </div>
      <div style={{ fontSize: 10, opacity: 0.85 }}>
        WR {pct(s && s.win_rate)} · n {(s && s.n != null) ? s.n : '—'}
      </div>
    </div>
  )
}

export default function ConfidenceHeatmap({ symbols }) {
  const data = Array.isArray(symbols) ? symbols.filter(Boolean) : []

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

  const header = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 10,
  }

  if (data.length === 0) {
    return (
      <div style={wrap}>
        <div style={header}>
          <span style={{ fontWeight: 600, letterSpacing: 0.4 }}>Brain Confidence</span>
        </div>
        <div
          style={{
            padding: '32px 16px',
            textAlign: 'center',
            color: T.muted,
            fontSize: 13,
          }}
        >
          <div style={{ fontSize: 26, marginBottom: 6, opacity: 0.5 }}>▦</div>
          no confidence data
        </div>
      </div>
    )
  }

  // Legend gradient built from scoreColor stops (low→high confidence).
  const stops = [0, 0.25, 0.5, 0.75, 1].map((s) => scoreColor(s))
  const legendGradient = `linear-gradient(90deg, ${stops.join(', ')})`

  return (
    <div style={wrap}>
      <div style={header}>
        <span style={{ fontWeight: 600, letterSpacing: 0.4 }}>Brain Confidence</span>
        <span style={{ fontSize: 12, color: T.muted }}>{data.length} symbols</span>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(96px, 1fr))',
          gap: 8,
        }}
      >
        {data.map((s, i) => (
          <Cell key={`${s && s.symbol}-${i}`} s={s} />
        ))}
      </div>

      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          marginTop: 12,
          fontSize: 10,
          color: T.muted,
        }}
      >
        <span>low</span>
        <div
          style={{
            flex: 1,
            height: 8,
            borderRadius: 4,
            background: legendGradient,
            border: `1px solid ${T.border}`,
          }}
        />
        <span>high</span>
      </div>
    </div>
  )
}
