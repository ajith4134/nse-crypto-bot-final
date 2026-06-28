import React, { useEffect, useMemo, useRef, useState } from 'react'
import Graph from 'graphology'
import Sigma from 'sigma'

// P3.8 — the ACTIVE-SUBNETWORK view. Adapted from the official sigma.js v3 storybook
// (use-reducers / events stories) per the reuse-first rule. Renders the learned model-
// network and ANIMATES the real per-input firing path: on each sample only the top-k
// experts that actually fired light up — the dynamic active subnetwork, not a static
// prune. Everything is real, read from /api/state (honest wiring).
//
// Layout: a stable, deterministic RADIAL layout (gate at centre, experts on a ring
// sorted by co-activation community). We deliberately avoid a force layout here: the
// topology is a star (every expert → the gate), which a force layout collapses into a
// jittery hairball that re-converges on every poll. Radial is stable and legible.

const PALETTE = ['#5cc8ff', '#ff8c42', '#7cff6b', '#c98bff', '#ffd23f', '#ff5d8f',
  '#36e0c8', '#ffa94d', '#9bffb0', '#ff5cf0']
const R = 10

export default function SigmaNetwork({ state }) {
  const containerRef = useRef(null)
  const rendererRef = useRef(null)
  const glowRef = useRef(new Map())    // node name -> eased glow intensity 0..1 (+ _t timestamp)
  const targetRef = useRef(new Set())  // names currently firing (glow eases toward these)
  const idxRef = useRef(0)
  const [hovered, setHovered] = useState(null)
  const [playing, setPlaying] = useState(true)
  const [curr, setCurr] = useState(0)

  const firing = state.firing || []
  const expertNames = useMemo(
    () => state.nodes.filter((n) => n.kind !== 'gate').map((n) => n.name), [state.nodes])

  // The /api/state poll hands us NEW array objects every 4s. Keep the latest data in a
  // ref and rebuild the graph ONLY when the network's content actually changes (netSig),
  // so a poll with identical data does NOT relayout — that was the glitch.
  const dataRef = useRef({})
  dataRef.current = { nodes: state.nodes, edges: state.edges, firing, expertNames }
  const netSig = useMemo(
    () => state.nodes.map((n) => `${n.name}:${n.community}`).join('|') + '#'
      + state.edges.map((e) => `${e.source}>${e.target}:${e.weight}`).join('|'),
    [state.nodes, state.edges])

  // ── build the graph + renderer ONCE per distinct network ──
  useEffect(() => {
    if (!containerRef.current) return
    const { nodes, edges } = dataRef.current
    const graph = new Graph()
    const usages = nodes.map((n) => n.usage ?? 0.5)
    const umin = Math.min(...usages), umax = Math.max(...usages)

    // Radial layout: gate centred; KEPT experts (the learned active subnetwork) on an inner
    // ring sorted by community; PRUNED candidates as a dim backdrop on an outer ring.
    const kept = nodes.filter((n) => n.kind !== 'gate' && n.kept !== false)
      .sort((a, b) => (a.community - b.community) || a.name.localeCompare(b.name))
    const pruned = nodes.filter((n) => n.kind !== 'gate' && n.kept === false)
    const keptOrder = Object.fromEntries(kept.map((n, i) => [n.name, i]))
    const prunedOrder = Object.fromEntries(pruned.map((n, i) => [n.name, i]))
    const KN = kept.length || 1, PN = pruned.length || 1

    nodes.forEach((n) => {
      const isGate = n.kind === 'gate'
      const isPruned = !isGate && n.kept === false
      let x = 0, y = 0, size, color
      if (isGate) { size = 9; color = '#aebbe6' }            // smaller, soft (not blinding white)
      else if (isPruned) {                                  // dim catalog backdrop (rejected nodes)
        const ang = (2 * Math.PI * (prunedOrder[n.name] ?? 0)) / PN
        x = Math.cos(ang) * R * 2.3; y = Math.sin(ang) * R * 2.3
        size = 3.5; color = '#39435e'
      } else {                                              // kept = active subnetwork
        const ang = (2 * Math.PI * (keptOrder[n.name] ?? 0)) / KN
        x = Math.cos(ang) * R; y = Math.sin(ang) * R
        size = 7 + ((n.usage - umin) / ((umax - umin) || 1)) * 11
        color = PALETTE[(n.community >= 0 ? n.community : 0) % PALETTE.length]
      }
      graph.addNode(n.name, { label: isPruned ? '' : n.name, size, color, isGate, kept: !isPruned,
        x, y, community: n.community, usage: n.usage, mw: n.mean_weight })
    })
    edges.forEach((e) => {
      if (graph.hasNode(e.source) && graph.hasNode(e.target))
        graph.addEdge(e.source, e.target, { size: 1 + (e.weight || 0) * 7,
          color: `rgba(150,160,210,${0.12 + 0.7 * (e.weight || 0)})`, weight: e.weight })
    })

    const renderer = new Sigma(graph, containerRef.current, {
      defaultEdgeType: 'line', labelColor: { color: '#cdd9ff' }, labelSize: 11,
      labelRenderedSizeThreshold: 1, labelDensity: 1, zIndex: true,
    })
    rendererRef.current = { renderer, graph }

    renderer.setSetting('nodeReducer', (node, data) => {       // ALL nodes stay visible; firing ones glow
      const g = glowRef.current.get(node) || 0, t = glowRef.current._t || 0, res = { ...data }
      const pulse = 1 + 0.18 * g * Math.sin(t * 5 + (data.x || 0))
      res.size = data.size * (1 + 0.5 * g) * pulse           // base size always rendered; grow when firing
      res.zIndex = g > 0.25 ? 2 : 0
      // forceLabel (NOT highlighted) — sigma's highlight draws a white disc that hides the
      // node name; forceLabel keeps the label readable beside the node.
      if (g > 0.3 || data.isGate) res.forceLabel = true
      return res
    })
    renderer.setSetting('edgeReducer', (edge, data) => {       // glowing firing-path edges
      const [s] = graph.extremities(edge), g = glowRef.current.get(s) || 0, res = { ...data }
      if (g > 0.03) {
        res.color = `rgba(255,93,143,${(0.22 + 0.7 * g).toFixed(3)})`
        res.size = (data.size || 1) * (1 + 1.3 * g); res.zIndex = 2
      } else { res.color = 'rgba(90,100,130,0.05)' }
      return res
    })
    renderer.on('enterNode', ({ node }) => setHovered({ id: node, ...graph.getNodeAttributes(node) }))
    renderer.on('leaveNode', () => setHovered(null))
    return () => { renderer.kill(); rendererRef.current = null }
  }, [netSig])

  // ── animate the per-input firing path (reads from the ref, never rebuilds) ──
  const applyFrame = (i) => {
    const { firing, expertNames } = dataRef.current
    if (!firing.length) return
    const n = firing.length
    const f = firing[((i % n) + n) % n]
    const set = new Set((f.active || []).map((k) => expertNames[k]).filter(Boolean))
    set.add('gated_moe')
    targetRef.current = set
    setCurr(((i % n) + n) % n)
  }
  // smooth 60fps loop: ease each node's glow toward its firing target, pulse, advance samples
  useEffect(() => {
    applyFrame(idxRef.current)
    let raf, last = performance.now(), since = 0
    const SAMPLE_MS = 1300
    const loop = (now) => {
      const dt = Math.min(0.05, (now - last) / 1000); last = now; since += dt * 1000
      if (playing && since > SAMPLE_MS) { since = 0; idxRef.current += 1; applyFrame(idxRef.current) }
      const g = glowRef.current, tgt = targetRef.current
      for (const nd of dataRef.current.nodes) {
        const cur = g.get(nd.name) || 0
        const want = tgt.has(nd.name) ? 1 : 0
        g.set(nd.name, cur + (want - cur) * Math.min(1, dt * 5))   // exponential ease
      }
      g._t = now / 1000
      const r = rendererRef.current
      if (r) r.renderer.refresh({ skipIndexation: true })
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
  }, [playing, netSig])

  const sample = firing[curr] || {}
  const a = state.active_subnet || {}

  return (
    <div className="graphwrap" style={{ position: 'relative' }}>
      <div ref={containerRef} style={{ width: '100%', height: '100%', minHeight: 460 }} />

      <div className="detail" style={{ left: 14, top: 12, right: 'auto', maxWidth: 260 }}>
        <div><b>per-input active subnetwork</b></div>
        {state.n_candidates != null &&
          <div className="k">learned <b>{a.n_experts}</b> active of <b>{state.n_candidates}</b> catalog nodes · dim ring = pruned</div>}
        <div className="k">top-{a.top_k} fire per input · {a.n_communities} communities</div>
        <div style={{ margin: '6px 0' }}>
          input <b>#{sample.i ?? '—'}</b> · {(sample.active || []).length} firing ·{' '}
          <span style={{ color: sample.correct ? 'var(--good,#4ade80)' : 'var(--bad,#ff6b6b)' }}>
            {sample.correct ? '✓ correct' : '✗ wrong'}
          </span>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <button onClick={() => setPlaying((p) => !p)}
            style={{ cursor: 'pointer', background: '#1b2440', color: '#dbe6ff',
              border: '1px solid #2c3a63', borderRadius: 6, padding: '3px 9px' }}>
            {playing ? '⏸ pause' : '▶ play'}
          </button>
          <input type="range" min={0} max={Math.max(0, firing.length - 1)} value={curr}
            onChange={(e) => { idxRef.current = +e.target.value; setPlaying(false); applyFrame(+e.target.value) }}
            style={{ flex: 1 }} />
        </div>
      </div>

      {hovered && (
        <div className="detail" style={{ right: 14, top: 12 }}>
          <div><b>{hovered.id}</b></div>
          <div className="k">{hovered.isGate ? 'differentiable gate' : `expert · community ${hovered.community}`}</div>
          {!hovered.isGate && <>
            <div><span className="k">fire rate:</span> {(hovered.usage * 100).toFixed(0)}%</div>
            <div><span className="k">mean gate wt:</span> {Number(hovered.mw).toFixed(3)}</div>
          </>}
        </div>
      )}

      <div className="legend" style={{ left: 14, bottom: 12 }}>
        <span><i style={{ background: '#ff5d8f' }} />firing path (live)</span>
        <span><i style={{ background: '#ffffff' }} />gate</span>
        <span>node size = fire rate · colour = community</span>
      </div>
    </div>
  )
}
