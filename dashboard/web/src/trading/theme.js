// Dark-Pro trading palette (T6). Single source of truth for trading-UI colours so
// every component renders consistently without depending on the global styles.css.
export const T = {
  bg: '#0b0e14',
  panel: '#121722',
  panel2: '#0e131c',
  border: '#1f2733',
  text: '#c8d3e0',
  muted: '#7488a0',
  good: '#2ec27e',   // long / profit / up
  bad: '#ff5c6c',    // short / loss / down
  accent: '#4da3ff',
  warn: '#ffb454',
  gridline: '#1a212c',
}

// Colour for a signed value (green positive, red negative, muted zero).
export function pnlColor(v) {
  if (v == null || v === 0) return T.muted
  return v > 0 ? T.good : T.bad
}

// Heatmap colour from a 0..1 score (red→amber→green), for the confidence grid.
export function scoreColor(s) {
  if (s == null) return T.panel2
  const x = Math.max(0, Math.min(1, s))
  const hue = 120 * x            // 0 = red, 120 = green
  return `hsl(${hue}, 65%, ${28 + 14 * x}%)`
}
