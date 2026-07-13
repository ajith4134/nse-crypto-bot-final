// NeuronWebPanel.jsx — "🕸 Web of Neurons" (Brain Ultra Upgrade Pillar 1, R15/R16/R24)
// The ONE common language: every strategy / research doc / trade episode / news item /
// finding / lesson is a Neuron with a mandatory instruction-shaped `action` facet.
// Shows the real store (/api/brain/neurons), the live graph (/api/brain/neurons/graph)
// as a self-contained SVG force layout (no lib lifecycle risk at ≤300 nodes), the
// growth series (R28), and live search (/api/brain/neurons/search) that always shows
// the action facet — knowledge you can't act on is dead weight.
import { useEffect, useMemo, useRef, useState } from 'react'
import { T } from './theme.js'

async function getJSON(url) {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json()
}

const KIND_COLORS = {
  fact: '#4da3ff', concept: '#7ac7ff', instruction: '#ffd166', skill: '#f4a261',
  strategy: '#e76f51', finding: '#b388ff', invention: '#ff7ad9', episode: '#5dd39e',
  source: '#9aa7b8', news: '#c9d64f', 'book-chapter': '#d4a373', exam: '#ff6b6b',
  lesson: '#64dfdf',
}

function Chip({ label, value, color }) {
  return (
    <div style={{ border: `1px solid ${T.border}`, borderRadius: 8, padding: '4px 10px',
                  display: 'flex', gap: 6, alignItems: 'baseline' }}>
      <span style={{ fontSize: 15, fontWeight: 800, color: color || T.text }}>{value}</span>
      <span style={{ fontSize: 10, color: T.muted }}>{label}</span>
    </div>
  )
}

// Deterministic mini force-layout: seeded ring by kind, then a few relaxation passes.
function layout(nodes, edges, W, H) {
  const idx = new Map(nodes.map((n, i) => [n.id, i]))
  const pos = nodes.map((n, i) => {
    const a = (i / Math.max(1, nodes.length)) * Math.PI * 2
    const r = 0.28 + 0.16 * ((n.kind.charCodeAt(0) * 31 + i * 7) % 100) / 100
    return { x: W / 2 + Math.cos(a) * W * r, y: H / 2 + Math.sin(a) * H * r * 0.9 }
  })
  const links = edges.map((e) => [idx.get(e.src), idx.get(e.dst)])
    .filter(([a, b]) => a != null && b != null)
  for (let it = 0; it < 60; it++) {
    for (const [a, b] of links) {                       // springs pull linked nodes
      const dx = pos[b].x - pos[a].x, dy = pos[b].y - pos[a].y
      const d = Math.max(1, Math.hypot(dx, dy)), f = (d - 46) / d * 0.04
      pos[a].x += dx * f; pos[a].y += dy * f
      pos[b].x -= dx * f; pos[b].y -= dy * f
    }
    for (const p of pos) {                              // gravity to center + bounds
      p.x += (W / 2 - p.x) * 0.004; p.y += (H / 2 - p.y) * 0.004
      p.x = Math.min(W - 8, Math.max(8, p.x)); p.y = Math.min(H - 8, Math.max(8, p.y))
    }
  }
  return pos
}

function GraphSVG({ graph }) {
  const W = 640, H = 360
  const nodes = (graph?.nodes || []).slice(0, 220)
  const keep = new Set(nodes.map((n) => n.id))
  const edges = (graph?.edges || []).filter((e) => keep.has(e.src) && keep.has(e.dst))
    .slice(0, 700)
  const [hover, setHover] = useState(null)
  const pos = useMemo(() => layout(nodes, edges, W, H), [graph])
  if (graph?.warming) return <div style={{ color: T.muted, fontSize: 12 }}>graph snapshot warming (serial background init) — appears shortly</div>
  if (!nodes.length) return <div style={{ color: T.muted, fontSize: 12 }}>web empty — run the backfill</div>
  const idx = new Map(nodes.map((n, i) => [n.id, i]))
  return (
    <div style={{ position: 'relative' }}>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 'auto',
           background: '#0b0f16', borderRadius: 8, border: `1px solid ${T.border}` }}>
        {edges.map((e, i) => {
          const a = pos[idx.get(e.src)], b = pos[idx.get(e.dst)]
          return <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                       stroke="#233046" strokeWidth={0.7} opacity={0.8} />
        })}
        {nodes.map((n, i) => (
          <circle key={n.id} cx={pos[i].x} cy={pos[i].y}
                  r={3 + Math.min(6, (n.degree || 0) * 0.6)}
                  fill={KIND_COLORS[n.kind] || T.muted} opacity={0.92}
                  onMouseEnter={() => setHover({ ...n, x: pos[i].x / W, y: pos[i].y / H })}
                  onMouseLeave={() => setHover(null)} style={{ cursor: 'pointer' }} />
        ))}
      </svg>
      {hover && (
        <div style={{ position: 'absolute', left: `${hover.x * 100}%`, top: `${hover.y * 100}%`,
                      transform: 'translate(-50%, -120%)', background: '#0e1420',
                      border: `1px solid ${T.border}`, borderRadius: 6, padding: '4px 8px',
                      fontSize: 11, color: T.text, pointerEvents: 'none', maxWidth: 260,
                      zIndex: 5 }}>
          <span style={{ color: KIND_COLORS[hover.kind] }}>{hover.kind}</span> · {hover.label}
          <span style={{ color: T.muted }}> · {hover.degree} links · conf {Number(hover.confidence).toFixed(2)}</span>
        </div>
      )}
    </div>
  )
}

function GrowthBars({ growth }) {
  const buckets = growth || []
  if (!buckets.length) return null
  const max = Math.max(1, ...buckets.map((b) => b.neurons + b.links))
  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 2, height: 46 }}>
      {buckets.map((b, i) => (
        <div key={i} title={`${new Date(b.t * 1000).toLocaleDateString()}: +${b.neurons} neurons, +${b.links} links`}
             style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', height: '100%' }}>
          <div style={{ height: `${(b.links / max) * 100}%`, background: '#233046' }} />
          <div style={{ height: `${(b.neurons / max) * 100}%`, background: T.accent, minHeight: b.neurons ? 2 : 0 }} />
        </div>
      ))}
    </div>
  )
}

function SearchBox() {
  const [q, setQ] = useState('')
  const [hits, setHits] = useState(null)
  const timer = useRef(null)
  useEffect(() => {
    if (!q.trim()) { setHits(null); return }
    clearTimeout(timer.current)
    timer.current = setTimeout(async () => {
      try {
        const j = await getJSON(`/api/brain/neurons/search?q=${encodeURIComponent(q)}`)
        setHits(j.hits || [])
      } catch { setHits([]) }
    }, 350)
    return () => clearTimeout(timer.current)
  }, [q])
  return (
    <div>
      <input value={q} onChange={(e) => setQ(e.target.value)}
             placeholder="ask the web of neurons… (e.g. RSI oversold, Binance login)"
             style={{ width: '100%', boxSizing: 'border-box', background: '#0b0f16',
                      border: `1px solid ${T.border}`, borderRadius: 8, color: T.text,
                      padding: '7px 10px', fontSize: 12, outline: 'none' }} />
      {hits && (
        <div style={{ marginTop: 6, display: 'flex', flexDirection: 'column', gap: 6,
                      maxHeight: 240, overflowY: 'auto' }}>
          {hits.length === 0 && <div style={{ color: T.muted, fontSize: 11 }}>no neurons matched</div>}
          {hits.slice(0, 8).map((h) => (
            <div key={h.id} style={{ border: `1px solid ${T.border}`, borderRadius: 8, padding: 8 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: KIND_COLORS[h.kind] || T.text }}>
                {h.kind} · <span style={{ color: T.text }}>{h.title}</span>
                <span style={{ color: T.muted, fontWeight: 400 }}> · conf {Number(h.confidence).toFixed(2)} · used {h.stats?.times_used ?? 0}×</span>
              </div>
              <div style={{ fontSize: 11, color: T.muted, marginTop: 3 }}>{h.body}</div>
              <div style={{ fontSize: 11, color: '#ffd166', marginTop: 4 }}>⚡ {h.action}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function NeuronWebPanel({ intervalMs = 20000 }) {
  const [state, setState] = useState({ loading: true })
  const [graph, setGraph] = useState(null)
  useEffect(() => {
    let alive = true
    const tick = async () => {
      try {
        const [ov, g] = await Promise.all([
          getJSON('/api/brain/neurons'), getJSON('/api/brain/neurons/graph')])
        if (alive) { setState({ data: ov, stamp: new Date() }); setGraph(g) }
      } catch (e) { if (alive) setState({ error: String(e.message || e) }) }
    }
    tick()
    const t = setInterval(tick, intervalMs)
    return () => { alive = false; clearInterval(t) }
  }, [intervalMs])

  const wrap = { background: T.bg, border: `1px solid ${T.border}`, borderRadius: 12,
                 padding: 14, color: T.text, fontFamily: 'system-ui, sans-serif' }
  if (state.loading) return <div style={wrap}><div style={{ color: T.muted, fontSize: 13 }}>🕸 loading the web of neurons…</div></div>
  if (state.error || !state.data) return <div style={wrap}><div style={{ color: T.muted, fontSize: 12 }}>web unavailable: {state.error}</div></div>
  if (state.data.warming) {
    return <div style={wrap}><div style={{ color: T.muted, fontSize: 12 }}>
      🕸 Web of Neurons — snapshot warming (serial background init after restart); the store on disk is intact and appears here shortly.</div></div>
  }

  const s = state.data.store || {}
  const kinds = Object.entries(s.by_kind || {}).sort((a, b) => b[1] - a[1])
  return (
    <div style={wrap}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 10, flexWrap: 'wrap' }}>
        <span style={{ fontWeight: 700, fontSize: 16 }}>🕸 Web of Neurons</span>
        <span style={{ fontSize: 11, color: T.muted }}>one common language — every neuron carries a “how to use me” action facet (R24)</span>
        <div style={{ flex: 1 }} />
        {state.stamp && <span style={{ fontSize: 10, color: T.muted }}>updated {state.stamp.toLocaleTimeString()}</span>}
      </div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 10 }}>
        <Chip label="neurons" value={s.neurons ?? '—'} color={T.accent} />
        <Chip label="links" value={s.links ?? '—'} />
        <Chip label="action coverage" value={s.action_coverage != null ? `${(s.action_coverage * 100).toFixed(1)}%` : '—'}
              color={s.action_coverage >= 0.999 ? T.good : T.warn} />
        <Chip label="instructions" value={state.data.instructions?.instructions ?? 0} color="#ffd166" />
        <Chip label="evolved" value={state.data.instructions?.evolved ?? 0} color="#b388ff" />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 3fr) minmax(0, 2fr)', gap: 12 }}>
        <div>
          <GraphSVG graph={graph} />
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 6 }}>
            {kinds.map(([k, v]) => (
              <span key={k} style={{ fontSize: 10, color: T.muted }}>
                <span style={{ color: KIND_COLORS[k] || T.text }}>●</span> {k} {v}
              </span>
            ))}
          </div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, minWidth: 0 }}>
          <div>
            <div style={{ fontSize: 11, color: T.muted, marginBottom: 4 }}>
              accumulation — neurons (blue) + links (grey) per day, last 30d (R28)
            </div>
            <GrowthBars growth={state.data.growth} />
          </div>
          <SearchBox />
        </div>
      </div>
    </div>
  )
}
