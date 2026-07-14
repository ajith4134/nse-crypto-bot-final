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

// ── Animated, kind-clustered neuron web on a canvas (self-contained, no libs) ──────────
// Every visual maps to REAL data: node color = real kind, node size/glow = real degree,
// position = force sim clustered by kind (colors form readable regions, not one blob),
// and signal pulses travel along REAL edges (hubs — high real degree — fire more often).
// Nothing fabricated: no fake neurons, no demo activity — pulses ride the actual link graph.
const KIND_LIST = Object.keys(KIND_COLORS)
function _kindCenter(kind, W, H) {          // deterministic cluster anchor per kind (readable regions)
  const i = Math.max(0, KIND_LIST.indexOf(kind))
  const a = (i / KIND_LIST.length) * Math.PI * 2
  return { x: W / 2 + Math.cos(a) * W * 0.30, y: H / 2 + Math.sin(a) * H * 0.30 }
}

function GraphCanvas({ graph }) {
  const W = 640, H = 380
  const canvasRef = useRef(null)
  const [hover, setHover] = useState(null)
  const stateRef = useRef({ nodes: [], edges: [], pulses: [] })

  const prepared = useMemo(() => {
    const nodes = (graph?.nodes || []).slice(0, 240).map((n) => ({ ...n }))
    const keep = new Set(nodes.map((n) => n.id))
    const idx = new Map(nodes.map((n, i) => [n.id, i]))
    const edges = (graph?.edges || []).filter((e) => keep.has(e.src) && keep.has(e.dst))
      .slice(0, 800).map((e) => ({ a: idx.get(e.src), b: idx.get(e.dst) }))
    // seed positions near each node's kind cluster (so regions are readable from frame 1)
    nodes.forEach((n, i) => {
      const c = _kindCenter(n.kind || 'source', W, H)
      const j = (n.id.charCodeAt ? n.id.charCodeAt(0) : i) * 13 + i * 7
      n.x = c.x + Math.cos(j) * 40 + (j % 23) - 11
      n.y = c.y + Math.sin(j) * 40 + (j % 17) - 8
      n.vx = 0; n.vy = 0
      n.r = 2.5 + Math.min(7, (n.degree || 0) * 0.55)     // size = real degree
      n.phase = (j % 100) / 100 * Math.PI * 2             // per-node breathing offset
    })
    return { nodes, edges }
  }, [graph])

  useEffect(() => {
    stateRef.current = { ...prepared, pulses: [] }
    const cv = canvasRef.current
    if (!cv || !prepared.nodes.length) return
    const dpr = Math.min(2, window.devicePixelRatio || 1)
    cv.width = W * dpr; cv.height = H * dpr
    const ctx = cv.getContext('2d'); ctx.scale(dpr, dpr)
    let raf, t = 0, running = true
    const { nodes, edges } = stateRef.current

    const step = () => {
      if (!running) return
      t += 1
      // physics: spring links + kind-cluster gravity + mild mutual repulsion among hubs
      for (const e of edges) {
        const a = nodes[e.a], b = nodes[e.b]
        const dx = b.x - a.x, dy = b.y - a.y, d = Math.max(1, Math.hypot(dx, dy))
        const f = (d - 40) / d * 0.008
        a.vx += dx * f; a.vy += dy * f; b.vx -= dx * f; b.vy -= dy * f
      }
      for (const n of nodes) {
        const c = _kindCenter(n.kind || 'source', W, H)
        n.vx += (c.x - n.x) * 0.0016; n.vy += (c.y - n.y) * 0.0016   // toward its kind region
        n.vx *= 0.90; n.vy *= 0.90                                    // damping → gentle settle
        n.x += n.vx; n.y += n.vy
        n.x = Math.min(W - 6, Math.max(6, n.x)); n.y = Math.min(H - 6, Math.max(6, n.y))
      }
      // fire pulses along real edges from high-degree hubs (rate ∝ real degree)
      if (t % 3 === 0 && edges.length) {
        for (let k = 0; k < 3; k++) {
          const e = edges[(Math.floor(t * 7 + k * 131)) % edges.length]
          const deg = nodes[e.a].degree || 0
          if (deg + (nodes[e.b].degree || 0) > 1) stateRef.current.pulses.push({ e, p: 0 })
        }
      }
      stateRef.current.pulses = stateRef.current.pulses.filter((pl) => (pl.p += 0.05) < 1)

      // ── render ──
      ctx.clearRect(0, 0, W, H)
      ctx.fillStyle = '#0a0e15'; ctx.fillRect(0, 0, W, H)
      // edges (faint; brighter when either endpoint is a hub)
      for (const e of edges) {
        const a = nodes[e.a], b = nodes[e.b]
        const hub = Math.max(a.degree || 0, b.degree || 0)
        ctx.strokeStyle = `rgba(70,100,150,${0.06 + Math.min(0.22, hub * 0.02)})`
        ctx.lineWidth = 0.6
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke()
      }
      // travelling signal pulses (real links firing)
      for (const pl of stateRef.current.pulses) {
        const a = nodes[pl.e.a], b = nodes[pl.e.b]
        const x = a.x + (b.x - a.x) * pl.p, y = a.y + (b.y - a.y) * pl.p
        const col = KIND_COLORS[b.kind] || '#8fd6ff'
        ctx.beginPath(); ctx.arc(x, y, 1.8, 0, Math.PI * 2)
        ctx.fillStyle = col; ctx.globalAlpha = 1 - pl.p; ctx.fill(); ctx.globalAlpha = 1
      }
      // nodes: glow halo (breathing, scaled by degree) + core
      for (const n of nodes) {
        const col = KIND_COLORS[n.kind] || '#9aa7b8'
        const pulse = 0.5 + 0.5 * Math.sin(t * 0.05 + n.phase)
        const glow = n.r + 3 + (n.degree || 0) * 0.35 * pulse
        const g = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, glow)
        g.addColorStop(0, col + '88'); g.addColorStop(1, col + '00')
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(n.x, n.y, glow, 0, Math.PI * 2); ctx.fill()
        ctx.fillStyle = col; ctx.beginPath(); ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2); ctx.fill()
      }
      raf = requestAnimationFrame(step)
    }
    raf = requestAnimationFrame(step)
    return () => { running = false; cancelAnimationFrame(raf) }
  }, [prepared])

  const onMove = (ev) => {
    const cv = canvasRef.current; if (!cv) return
    const rect = cv.getBoundingClientRect()
    const mx = (ev.clientX - rect.left) / rect.width * W
    const my = (ev.clientY - rect.top) / rect.height * H
    let best = null, bd = 14 * 14
    for (const n of stateRef.current.nodes) {
      const d = (n.x - mx) ** 2 + (n.y - my) ** 2
      if (d < bd) { bd = d; best = n }
    }
    setHover(best ? { ...best, px: best.x / W, py: best.y / H } : null)
  }

  if (graph?.warming) return <div style={{ color: T.muted, fontSize: 12 }}>graph snapshot warming (serial background init) — appears shortly</div>
  if (!prepared.nodes.length) return <div style={{ color: T.muted, fontSize: 12 }}>web empty — run the backfill</div>
  return (
    <div style={{ position: 'relative' }}>
      <canvas ref={canvasRef} onMouseMove={onMove} onMouseLeave={() => setHover(null)}
              style={{ width: '100%', height: 'auto', aspectRatio: `${W} / ${H}`, display: 'block',
                       background: '#0a0e15', borderRadius: 8, border: `1px solid ${T.border}`,
                       cursor: 'crosshair' }} />
      {hover && (
        <div style={{ position: 'absolute', left: `${hover.px * 100}%`, top: `${hover.py * 100}%`,
                      transform: 'translate(-50%, -130%)', background: '#0e1420',
                      border: `1px solid ${T.border}`, borderRadius: 6, padding: '4px 8px',
                      fontSize: 11, color: T.text, pointerEvents: 'none', maxWidth: 280, zIndex: 5 }}>
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
          <GraphCanvas graph={graph} />
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
