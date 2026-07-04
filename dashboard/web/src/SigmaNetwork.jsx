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
// CORTEX B7: gate-ish kinds (network hubs, not routable experts)
const GATE_KINDS = new Set(['gate', 'hgate', 'community_gate', 'column', 'column_network'])
const TIER_COLORS = ['#7cff6b', '#ffd23f', '#ff8c42', '#ff5d8f']  // tier 1..4
const ZOOM_OUT_RATIO = 1.9   // camera ratio above which community super-nodes take over

export default function SigmaNetwork({ state }) {
  const containerRef = useRef(null)
  const rendererRef = useRef(null)
  const glowRef = useRef(new Map())    // node name -> eased glow intensity 0..1 (+ _t timestamp)
  const targetRef = useRef(new Set())  // names currently firing (glow eases toward these)
  const idxRef = useRef(0)
  const [hovered, setHovered] = useState(null)
  const [playing, setPlaying] = useState(true)
  const [curr, setCurr] = useState(0)
  // CORTEX B7: colour overlay (community default) — read inside reducers via ref
  const [overlay, setOverlay] = useState('community')
  const overlayRef = useRef('community')
  overlayRef.current = overlay

  const firing = state.firing || []
  // firing indices reference EXPERT nodes only (base kind), in state order — the
  // filter keeps legacy states (gate last) and B7 states (community gates + hgate
  // appended after the experts) index-compatible.
  const expertNames = useMemo(
    () => state.nodes.filter((n) => !GATE_KINDS.has(n.kind)).map((n) => n.name), [state.nodes])
  const centerName = useMemo(() => {
    const g = state.nodes.find((n) => n.kind === 'gate' || n.kind === 'hgate')
    return g ? g.name : 'gated_moe'
  }, [state.nodes])
  // colour lookups from the state's honest layouts (present only in B7 states)
  const columnColor = useMemo(() => Object.fromEntries(
    (Array.isArray(state.columns) ? state.columns : []).map((c) => [c.key, c.color])), [state.columns])
  const segmentColor = useMemo(() => Object.fromEntries(
    (state.segments || []).map((s) => [s.key, s.color])), [state.segments])
  const hasColumns = Object.keys(columnColor).length > 0 && state.nodes.some((n) => n.column)
  const hasSegments = Object.keys(segmentColor).length > 0 && state.nodes.some((n) => n.segment)
  const hasTiers = state.nodes.some((n) => n.tier != null)

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

    // CORTEX B7 layout: community-CLUSTERED. Each Leiden community gets an angular
    // sector on the main ring (the SAME communities the router uses — honest layout);
    // members sit on a small circle around their community centre; the centre node
    // (hgate / gated_moe) stays at the origin. Nodes WITHOUT a community fall back to
    // the legacy radial ring; PRUNED candidates keep the dim outer backdrop.
    const isHub = (n) => n.kind === 'gate' || n.kind === 'hgate'
    const isCommGate = (n) => n.kind === 'community_gate'
    const kept = nodes.filter((n) => !isHub(n) && !isCommGate(n) && n.kept !== false)
      .sort((a, b) => (a.community - b.community) || a.name.localeCompare(b.name))
    const pruned = nodes.filter((n) => !isHub(n) && !isCommGate(n) && n.kept === false)
    const keptOrder = Object.fromEntries(kept.map((n, i) => [n.name, i]))
    const prunedOrder = Object.fromEntries(pruned.map((n, i) => [n.name, i]))
    const KN = kept.length || 1, PN = pruned.length || 1
    // per-community cluster centres (angular sector per community)
    const commIds = [...new Set(kept.filter((n) => n.community >= 0).map((n) => n.community))].sort((a, b) => a - b)
    const commCenter = {}, commMembers = {}, commAgg = {}
    commIds.forEach((c, ci) => {
      const ang = (2 * Math.PI * ci) / (commIds.length || 1)
      commCenter[c] = [Math.cos(ang) * R, Math.sin(ang) * R]
      commMembers[c] = kept.filter((n) => n.community === c)
      commAgg[c] = commMembers[c].reduce((s, n) => s + (n.usage ?? 0.5), 0)
    })
    const clustered = commIds.length > 1   // 0/1 community → legacy radial is clearer

    nodes.forEach((n) => {
      const isGate = isHub(n)
      const isCG = isCommGate(n)
      const isPruned = !isGate && !isCG && n.kept === false
      let x = 0, y = 0, size, color
      if (isGate) { size = 9; color = '#aebbe6' }            // smaller, soft (not blinding white)
      else if (isCG) {                                       // community gate = cluster centre
        const c = n.community
        const [cx, cy] = commCenter[c] || [0, 0]
        x = cx; y = cy
        size = 6 + Math.min(8, (commAgg[c] || 1) * 2)
        color = PALETTE[(c >= 0 ? c : 0) % PALETTE.length]
      } else if (isPruned) {                                 // dim catalog backdrop (rejected nodes)
        const ang = (2 * Math.PI * (prunedOrder[n.name] ?? 0)) / PN
        x = Math.cos(ang) * R * 2.3; y = Math.sin(ang) * R * 2.3
        size = 3.5; color = '#39435e'
      } else if (clustered && n.community >= 0 && commCenter[n.community]) {
        // clustered member: small circle around its community centre
        const mem = commMembers[n.community]
        const mi = mem.findIndex((m) => m.name === n.name)
        const [cx, cy] = commCenter[n.community]
        const r = Math.min(R * 0.45, 1.6 + mem.length * 0.45)
        const ang = (2 * Math.PI * Math.max(0, mi)) / (mem.length || 1)
        x = cx + Math.cos(ang) * r; y = cy + Math.sin(ang) * r
        size = 7 + ((n.usage - umin) / ((umax - umin) || 1)) * 11
        color = PALETTE[(n.community >= 0 ? n.community : 0) % PALETTE.length]
      } else {                                               // fallback: legacy radial ring
        const ang = (2 * Math.PI * (keptOrder[n.name] ?? 0)) / KN
        x = Math.cos(ang) * R; y = Math.sin(ang) * R
        size = 7 + ((n.usage - umin) / ((umax - umin) || 1)) * 11
        color = PALETTE[(n.community >= 0 ? n.community : 0) % PALETTE.length]
      }
      graph.addNode(n.name, { label: isPruned ? '' : n.name, size, color, isGate, kept: !isPruned,
        x, y, community: n.community, usage: n.usage, mw: n.mean_weight,
        // B7 enrichments (undefined on legacy states — reducers/hover skip them)
        isCommGate: isCG, aggSize: isCG ? (6 + Math.min(14, (commAgg[n.community] || 1) * 3)) : 0,
        column: n.column, segment: n.segment, stage: n.stage, tier: n.tier, trust: n.trust })
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

    const hasCommGates = nodes.some((n) => n.kind === 'community_gate')
    renderer.setSetting('nodeReducer', (node, data) => {       // ALL nodes stay visible; firing ones glow
      const g = glowRef.current.get(node) || 0, t = glowRef.current._t || 0, res = { ...data }
      const pulse = 1 + 0.18 * g * Math.sin(t * 5 + (data.x || 0))
      res.size = data.size * (1 + 0.5 * g) * pulse           // base size always rendered; grow when firing
      res.zIndex = g > 0.25 ? 2 : 0
      // B7 colour overlay: recolour by column / segment / tier from the state layouts
      const mode = overlayRef.current
      if (!data.isGate && data.kept) {
        if (mode === 'column' && data.column) res.color = columnColor[data.column] || '#6b7280'
        else if (mode === 'segment' && data.segment) res.color = segmentColor[data.segment] || '#6b7280'
        else if (mode === 'tier' && data.tier != null) res.color = TIER_COLORS[(data.tier - 1 + 4) % 4]
      }
      // B7 semantic zoom: zoomed far out → community SUPER-nodes (aggregate size)
      // replace their members; only when real community gates exist (honest clusters).
      if (hasCommGates) {
        const ratio = renderer.getCamera().ratio
        if (ratio > ZOOM_OUT_RATIO) {
          if (data.isCommGate) { res.size = data.aggSize; res.forceLabel = true }
          else if (!data.isGate && data.kept) res.hidden = true
        }
      }
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
    set.add(centerName)
    // B7: light the community path (hgate → community gates the router picked)
    for (const c of f.community_path || []) set.add(`community_${c}`)
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
        {(hasColumns || hasSegments || hasTiers) && (
          <div style={{ display: 'flex', gap: 4, marginTop: 7, flexWrap: 'wrap' }}>
            {['community', hasColumns && 'column', hasSegments && 'segment', hasTiers && 'tier']
              .filter(Boolean).map((m) => (
                <button key={m} onClick={() => setOverlay(m)}
                  style={{ cursor: 'pointer', fontSize: 11, padding: '2px 8px', borderRadius: 6,
                    background: overlay === m ? '#243158' : '#161d33',
                    color: overlay === m ? '#8fb8ff' : '#8b96b8',
                    border: `1px solid ${overlay === m ? '#3d549c' : '#242e4d'}` }}>
                  {m}
                </button>
              ))}
          </div>
        )}
      </div>

      {hovered && (
        <div className="detail" style={{ right: 14, top: 12 }}>
          <div><b>{hovered.id}</b></div>
          <div className="k">{hovered.isGate ? 'differentiable gate' : `expert · community ${hovered.community}`}</div>
          {!hovered.isGate && <>
            <div><span className="k">fire rate:</span> {(hovered.usage * 100).toFixed(0)}%</div>
            <div><span className="k">mean gate wt:</span> {Number(hovered.mw).toFixed(3)}</div>
          </>}
          {hovered.trust != null &&
            <div><span className="k">trust:</span> {Number(hovered.trust).toFixed(4)}</div>}
          {hovered.column &&
            <div><span className="k">column:</span> {hovered.column}</div>}
          {hovered.segment &&
            <div><span className="k">segment:</span> {hovered.segment}{hovered.stage ? ` · ${hovered.stage}` : ''}</div>}
          {hovered.tier != null &&
            <div><span className="k">reflex tier:</span> {hovered.tier}</div>}
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
