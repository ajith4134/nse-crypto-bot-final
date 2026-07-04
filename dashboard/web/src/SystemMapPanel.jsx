import React, { useEffect, useMemo, useRef, useState } from 'react'

// SystemMapPanel — the WHOLE brain as a living wired map (user mandate
// 2026-07-04): every subsystem drawn PERMANENTLY like neurons in a brain —
// the working ones glow (awake/firing), the resting ones stay dim but remain
// visibly connected. Statuses come from /api/network/system, which proves each
// one from real evidence (file freshness, live probes, env flags) — the
// evidence string is shown on the node. Never decorative.

const POLL_MS = 20000
const STATUS = {
  working: { color: '#3ecf8e', label: 'working' },
  standby: { color: '#8b96b8', label: 'resting' },
  off: { color: '#ff6b6b', label: 'off' },
}
const LAYER_LABEL = {
  data: 'Data senses', features: 'Feature bus', neurons: 'Neurons (ML models)',
  routing: 'Routing & decision', execution: 'Execution', learning: 'Learning',
}

export default function SystemMapPanel() {
  const [map, setMap] = useState(null)
  const [sel, setSel] = useState(null)         // selected node id
  const wrapRef = useRef(null)
  const nodeRefs = useRef({})
  const [lines, setLines] = useState([])

  useEffect(() => {
    let on = true
    const load = () => fetch('/api/network/system').then((r) => r.json())
      .then((j) => { if (on) setMap(j) }).catch(() => {})
    load()
    const t = setInterval(load, POLL_MS)
    return () => { on = false; clearInterval(t) }
  }, [])

  const byLayer = useMemo(() => {
    const g = {}
    for (const n of map?.nodes || []) (g[n.layer] = g[n.layer] || []).push(n)
    return g
  }, [map])

  // measure node card positions → SVG edge endpoints (re-run on data + resize)
  useEffect(() => {
    const measure = () => {
      const wrap = wrapRef.current
      if (!wrap || !map?.edges) return
      const wb = wrap.getBoundingClientRect()
      const pos = {}
      for (const [id, el] of Object.entries(nodeRefs.current)) {
        if (!el) continue
        const b = el.getBoundingClientRect()
        pos[id] = { x1: b.left - wb.left, x2: b.right - wb.left, y: b.top - wb.top + b.height / 2 }
      }
      setLines(map.edges.filter((e) => pos[e.source] && pos[e.target]).map((e) => {
        const s = pos[e.source], t = pos[e.target]
        const leftToRight = s.x2 <= t.x1
        return { ...e, sx: leftToRight ? s.x2 : s.x1, sy: s.y, tx: leftToRight ? t.x1 : t.x2, ty: t.y }
      }))
    }
    measure()
    const ro = new ResizeObserver(measure)
    if (wrapRef.current) ro.observe(wrapRef.current)
    return () => ro.disconnect()
  }, [map, sel])

  if (!map) return <section className="card"><h2>Whole-Brain System Map</h2><div className="hint">loading…</div></section>
  if (map.note) return <section className="card"><h2>Whole-Brain System Map</h2><div className="hint">{map.note}</div></section>

  const selNode = (map.nodes || []).find((n) => n.id === sel)
  const touching = new Set(sel ? map.edges.filter((e) => e.source === sel || e.target === sel)
    .flatMap((e) => [e.source, e.target]) : [])

  return (
    <section className="card" style={{ marginBottom: 16 }}>
      <h2 style={{ display: 'flex', gap: 12, alignItems: 'baseline', flexWrap: 'wrap' }}>
        Whole-Brain System Map
        <span style={{ fontSize: 12, fontWeight: 400 }}>
          {Object.entries(map.counts).map(([k, v]) => (
            <span key={k} style={{ marginRight: 10, color: STATUS[k]?.color }}>
              ● {v} {STATUS[k]?.label || k}</span>
          ))}
        </span>
      </h2>
      <div className="hint">
        Like a brain: every neuron stays drawn and CONNECTED — glowing = awake/firing now,
        dim = resting until routed to. Statuses proven from real evidence (shown on each node).
        Click a node to highlight its wiring + inputs/outputs.
      </div>

      <div ref={wrapRef} style={{ position: 'relative' }}>
        <svg style={{ position: 'absolute', inset: 0, width: '100%', height: '100%',
          pointerEvents: 'none', zIndex: 0 }}>
          {lines.map((l, i) => {
            const active = sel && (l.source === sel || l.target === sel)
            const mx = (l.sx + l.tx) / 2
            return (
              <g key={i}>
                <path d={`M ${l.sx} ${l.sy} C ${mx} ${l.sy}, ${mx} ${l.ty}, ${l.tx} ${l.ty}`}
                  fill="none" stroke={active ? '#4da3ff' : '#26314a'}
                  strokeWidth={active ? 1.8 : 0.8} opacity={sel && !active ? 0.25 : 1} />
                {active && (
                  <text x={mx} y={(l.sy + l.ty) / 2 - 4} textAnchor="middle"
                    style={{ fill: '#4da3ff', fontSize: 10 }}>{l.stream}</text>
                )}
              </g>
            )
          })}
        </svg>

        <div style={{ display: 'grid', position: 'relative', zIndex: 1,
          gridTemplateColumns: `repeat(${(map.layers || []).length}, minmax(0,1fr))`, gap: 10 }}>
          {(map.layers || []).map((layer) => (
            <div key={layer}>
              <div style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: 0.8,
                color: '#8b96b8', marginBottom: 6 }}>{LAYER_LABEL[layer] || layer}</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {(byLayer[layer] || []).map((n) => {
                  const st = STATUS[n.status] || STATUS.standby
                  const dimmed = sel && n.id !== sel && !touching.has(n.id)
                  return (
                    <div key={n.id} ref={(el) => { nodeRefs.current[n.id] = el }}
                      onClick={() => setSel(sel === n.id ? null : n.id)}
                      title={n.evidence}
                      style={{ background: '#121a2b', border: `1px solid ${n.id === sel ? '#4da3ff' : '#1e2837'}`,
                        borderRadius: 8, padding: '6px 8px', cursor: 'pointer',
                        opacity: dimmed ? 0.35 : 1, transition: 'opacity .15s',
                        boxShadow: n.status === 'working' ? `0 0 10px ${st.color}33` : 'none' }}>
                      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                        <span style={{ width: 8, height: 8, borderRadius: 4, background: st.color,
                          flexShrink: 0,
                          animation: n.status === 'working' ? 'sysmap-pulse 2.2s infinite' : 'none' }} />
                        <span style={{ fontSize: 11.5, lineHeight: 1.25 }}>{n.label}</span>
                      </div>
                      <div style={{ fontSize: 9.5, color: '#8b96b8', marginTop: 2 }}>{n.evidence}</div>
                    </div>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      </div>

      {selNode && (
        <div style={{ marginTop: 10, border: '1px solid #1e2837', borderRadius: 8,
          padding: '8px 12px', fontSize: 12.5 }}>
          <b>{selNode.label}</b>
          <span style={{ marginLeft: 8, color: (STATUS[selNode.status] || {}).color }}>
            ● {(STATUS[selNode.status] || {}).label}</span>
          <span className="k" style={{ marginLeft: 8 }}>{selNode.evidence}</span>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginTop: 6 }}>
            <div>
              <div style={{ color: '#8b96b8', fontSize: 10, textTransform: 'uppercase' }}>inputs ⇢</div>
              {selNode.inputs.map((x, i) => <div key={i}>• {x}</div>)}
            </div>
            <div>
              <div style={{ color: '#8b96b8', fontSize: 10, textTransform: 'uppercase' }}>⇢ outputs</div>
              {selNode.outputs.map((x, i) => <div key={i}>• {x}</div>)}
            </div>
          </div>
        </div>
      )}
      <style>{`@keyframes sysmap-pulse { 0%,100% { box-shadow: 0 0 0 0 rgba(62,207,142,.5);} 50% { box-shadow: 0 0 0 5px rgba(62,207,142,0);} }`}</style>
    </section>
  )
}
