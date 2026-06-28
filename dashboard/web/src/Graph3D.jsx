import React, { useMemo, useRef, useState } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { OrbitControls, Html, Text, Stars } from '@react-three/drei'
import * as THREE from 'three'
import { kindColor } from './useState.js'

// ---------------------------------------------------------------------------
//  HONEST view of the ACTUAL network — single- OR multi-output. Everything is
//  real, derived only from /api/state; nothing is fabricated (rule "honest
//  wiring"). Multi-output: one horizontal BAND per output head — shared input
//  features -> that head's model nodes -> its meta -> its ŷ output. A node
//  connects only to the head it truly predicts; particles flow in the real
//  data-flow direction.
// ---------------------------------------------------------------------------

const FEATURE_CONSUMERS = ['base', 'chaos', 'regime', 'symbolic', 'regressor']
const X_GAP = 4.6
const Y_GAP = 1.45

function chunk(arr, n) {
  const out = Array.from({ length: n }, () => [])
  arr.forEach((v, i) => out[i % n].push(v))
  return out
}

// ---- multi-output layout (bands per head) ---------------------------------
function buildMultiHead(nodes, edges, dataset, heads) {
  const byName = Object.fromEntries(nodes.map((n) => [n.name, n]))
  const upstreamMap = {}
  edges.forEach((e) => { (upstreamMap[e.target] = upstreamMap[e.target] || []).push(e.source) })

  const features = (dataset?.feature_names || []).slice(0, 14)
  const xInput = -2 * X_GAP, xMeta = 1 * X_GAP, xOutput = 2 * X_GAP
  const bandGap = 6.2
  const H = heads.length
  const pos = {}
  const renderNodes = []
  const headLabels = []

  // shared input features, centred across the whole figure
  features.forEach((f, i) => {
    const y = ((features.length - 1) / 2 - i) * Y_GAP
    pos[f] = [xInput, y, 0]
    renderNodes.push({ name: f, kind: 'input', _feature: true, _pos: pos[f] })
  })

  heads.forEach((h, hi) => {
    const bandY = ((H - 1) / 2 - hi) * bandGap
    const models = nodes.filter((n) => n.head === h.name && !['meta', 'output', 'input'].includes(n.kind))
    const cols = chunk(models, 2)                      // two compact sub-columns
    cols.forEach((col, ci) => {
      const x = (-1 + ci) * X_GAP                      // model sub-columns at x=-GAP, 0
      col.forEach((n, i) => {
        const y = bandY + ((col.length - 1) / 2 - i) * Y_GAP
        pos[n.name] = [x, y, 0]
        renderNodes.push({ ...n, _pos: pos[n.name] })
      })
    })
    const meta = nodes.find((n) => n.head === h.name && n.kind === 'meta')
    if (meta) { pos[meta.name] = [xMeta, bandY, 0]; renderNodes.push({ ...meta, _pos: pos[meta.name] }) }
    const out = nodes.find((n) => n.head === h.name && n.kind === 'output')
    if (out) { pos[out.name] = [xOutput, bandY, 0]; renderNodes.push({ ...out, _pos: pos[out.name] }) }
    headLabels.push({
      x: xOutput, y: bandY + 1.1,
      text: `${h.name} · ${h.metric} ${Number(h.value).toFixed(3)}${h.baseline != null ? ` (base ${Number(h.baseline).toFixed(2)})` : ''}`,
      color: kindColor(h.task === 'regression' ? 'regressor' : (h.task === 'multiclass' ? 'regime' : 'base')),
    })
  })

  // REAL edges only
  const realEdges = []
  // input feature -> each model node that consumes raw features (upstream empty)
  heads.forEach((h) => {
    nodes.filter((n) => n.head === h.name && (upstreamMap[n.name] || []).length === 0 && pos[n.name])
      .forEach((n) => features.forEach((f) => realEdges.push({ a: pos[f], b: pos[n.name], kind: 'data' })))
  })
  // real upstream edges (base->meta, meta->output) straight from state.edges
  edges.forEach((e) => {
    if (pos[e.source] && pos[e.target]) {
      const k = byName[e.target]?.kind === 'output' ? 'pred' : 'stack'
      realEdges.push({ a: pos[e.source], b: pos[e.target], kind: k })
    }
  })

  const colLabels = [
    { x: xInput, label: 'input · features' }, { x: -X_GAP / 2, label: 'model nodes' },
    { x: xMeta, label: 'meta' }, { x: xOutput, label: 'outputs ŷ' },
  ]
  const topY = (Math.max(features.length, H * 3) / 2 + 1) * Y_GAP
  return { realEdges, renderNodes, headLabels, colLabels, topY, upstreamMap, multi: true }
}

// ---- single-output layout (legacy state.json) -----------------------------
function buildSingleHead(nodes, edges, dataset) {
  const upstreamMap = {}, hasDownstream = new Set()
  edges.forEach((e) => { (upstreamMap[e.target] = upstreamMap[e.target] || []).push(e.source); hasDownstream.add(e.source) })
  const features = (dataset?.feature_names || []).slice(0, 14)
  const models = nodes.filter((n) => ['base', 'chaos', 'regime', 'symbolic', 'regressor'].includes(n.kind))
  const metas = nodes.filter((n) => ['ensemble', 'router', 'meta', 'gate', 'cascade', 'bus'].includes(n.kind))
  const automl = nodes.filter((n) => n.kind === 'automl')
  const cols = []
  cols.push({ label: 'input · features', items: features.map((f) => ({ name: f, kind: 'input', _feature: true })) })
  chunk(models, Math.min(3, Math.max(1, Math.ceil(models.length / 7)))).forEach((c, i) =>
    cols.push({ label: `model nodes ${i + 1}`.trim(), items: c }))
  const mid = [...metas, ...automl]
  if (mid.length) cols.push({ label: 'meta / automl', items: mid })
  cols.push({ label: 'output', items: [{ name: '＝ p(class=1)', kind: 'output', _output: true }] })
  const pos = {}, L = cols.length, x0 = -((L - 1) * X_GAP) / 2
  cols.forEach((col, ci) => {
    col.x = x0 + ci * X_GAP
    const h = (col.items.length - 1) / 2
    col.items.forEach((it, i) => { it._pos = [col.x, (h - i) * Y_GAP, 0]; pos[it.name] = it._pos })
  })
  const realEdges = []
  const featItems = cols[0].items
  ;[...models, ...automl].forEach((n) => { if ((upstreamMap[n.name] || []).length === 0) featItems.forEach((f) => realEdges.push({ a: f._pos, b: pos[n.name], kind: 'data' })) })
  edges.forEach((e) => { if (pos[e.source] && pos[e.target]) realEdges.push({ a: pos[e.source], b: pos[e.target], kind: 'stack' }) })
  const outPos = cols[cols.length - 1].items[0]._pos
  ;[...metas, ...automl, ...models].forEach((n) => { if (!hasDownstream.has(n.name)) realEdges.push({ a: pos[n.name], b: outPos, kind: 'pred' }) })
  const renderNodes = cols.flatMap((c) => c.items.map((it) => { const real = nodes.find((n) => n.name === it.name); return real ? { ...real, _pos: it._pos } : it }))
  const topY = (Math.max(...cols.map((c) => c.items.length)) / 2 + 0.8) * Y_GAP
  return { realEdges, renderNodes, headLabels: [], colLabels: cols.map((c) => ({ x: c.x, label: c.label })), topY, upstreamMap, multi: false }
}

function Node({ node, onHover }) {
  const ref = useRef()
  const acc = node.metrics?.value ?? node.metrics?.test_accuracy
  const channel = node._feature || node._output || node.kind === 'output'
  const color = node.kind === 'output' ? '#4ade80' : kindColor(node.kind)
  const size = channel ? 0.2 : 0.24 + Math.max(0, (acc ?? 0.5) - 0.5) * 0.8
  useFrame((st) => { if (ref.current) ref.current.material.emissiveIntensity = 0.5 + 0.4 * Math.sin(st.clock.elapsedTime * 2 + node._pos[1]) })
  return (
    <group position={node._pos}>
      <mesh ref={ref} onPointerOver={(e) => { e.stopPropagation(); onHover(node) }} onPointerOut={() => onHover(null)}>
        {channel ? <boxGeometry args={[0.32, 0.32, 0.32]} /> : <sphereGeometry args={[size, 20, 20]} />}
        <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.7} metalness={0.25} roughness={0.4} />
      </mesh>
      <Html distanceFactor={15} center style={{ pointerEvents: 'none' }}>
        <div style={{ color: channel ? '#a8bbe6' : '#dbe6ff', fontSize: channel ? 8 : 9, whiteSpace: 'nowrap', opacity: 0.9, textShadow: '0 0 6px #000', transform: 'translateY(-14px)' }}>{node.name}</div>
      </Html>
    </group>
  )
}

function EdgeLines({ edges, color, opacity }) {
  const geom = useMemo(() => {
    const g = new THREE.BufferGeometry()
    const arr = new Float32Array(edges.length * 6)
    edges.forEach((e, i) => arr.set([...e.a, ...e.b], i * 6))
    g.setAttribute('position', new THREE.BufferAttribute(arr, 3))
    return g
  }, [edges])
  if (!edges.length) return null
  return <lineSegments geometry={geom}><lineBasicMaterial color={color} transparent opacity={opacity} /></lineSegments>
}

function FlowParticles({ edges, color, speed = 0.32, size = 0.06 }) {
  const ref = useRef()
  const dummy = useMemo(() => new THREE.Object3D(), [])
  const phases = useMemo(() => edges.map((_, i) => (i * 0.173) % 1), [edges])
  useFrame((st) => {
    if (!ref.current || !edges.length) return
    const t = st.clock.elapsedTime
    edges.forEach((e, i) => {
      const f = (t * speed + phases[i]) % 1
      dummy.position.set(e.a[0] + (e.b[0] - e.a[0]) * f, e.a[1] + (e.b[1] - e.a[1]) * f, e.a[2] + (e.b[2] - e.a[2]) * f)
      dummy.updateMatrix(); ref.current.setMatrixAt(i, dummy.matrix)
    })
    ref.current.instanceMatrix.needsUpdate = true
  })
  if (!edges.length) return null
  return (
    <instancedMesh ref={ref} args={[undefined, undefined, edges.length]}>
      <sphereGeometry args={[size, 8, 8]} />
      <meshBasicMaterial color={color} toneMapped={false} transparent opacity={0.95} blending={THREE.AdditiveBlending} />
    </instancedMesh>
  )
}

function Scene({ model, onHover }) {
  const grp = useRef()
  const data = useMemo(() => model.realEdges.filter((e) => e.kind === 'data'), [model])
  const stack = useMemo(() => model.realEdges.filter((e) => e.kind === 'stack'), [model])
  const pred = useMemo(() => model.realEdges.filter((e) => e.kind === 'pred'), [model])
  useFrame((st) => { if (grp.current) grp.current.rotation.y = Math.sin(st.clock.elapsedTime * 0.1) * 0.28 })
  return (
    <>
      <ambientLight intensity={0.5} />
      <pointLight position={[0, 10, 14]} intensity={1.2} color="#bcd4ff" />
      <pointLight position={[-12, -6, -8]} intensity={0.5} color="#b98cff" />
      <Stars radius={70} depth={40} count={1300} factor={3} fade speed={1} />
      <group ref={grp}>
        <EdgeLines edges={data} color="#2f5bd0" opacity={0.12} />
        <EdgeLines edges={stack} color="#7a52d8" opacity={0.3} />
        <EdgeLines edges={pred} color="#2fd0a8" opacity={0.55} />
        <FlowParticles edges={data} color="#5cd0ff" speed={0.3} />
        <FlowParticles edges={stack} color="#b98cff" speed={0.42} size={0.07} />
        <FlowParticles edges={pred} color="#4ade80" speed={0.5} size={0.09} />
        {model.colLabels.map((c) => (
          <Text key={c.label} position={[c.x, model.topY, 0]} fontSize={0.4} color="#7f93bd" anchorX="center" anchorY="middle" outlineWidth={0.01} outlineColor="#05070f">{c.label.toUpperCase()}</Text>
        ))}
        {model.headLabels.map((h, i) => (
          <Text key={i} position={[h.x, h.y, 0]} fontSize={0.34} color={h.color} anchorX="center" anchorY="middle" outlineWidth={0.012} outlineColor="#05070f">{h.text}</Text>
        ))}
        {model.renderNodes.map((n) => <Node key={n.name} node={n} onHover={onHover} />)}
      </group>
    </>
  )
}

export default function Graph3D({ nodes, edges, dataset, heads }) {
  const [hover, setHover] = useState(null)
  const model = useMemo(
    () => (heads && heads.length ? buildMultiHead(nodes, edges, dataset, heads) : buildSingleHead(nodes, edges, dataset)),
    [nodes, edges, dataset, heads])
  const up = hover && model.upstreamMap[hover.name]
  return (
    <div className="graphwrap">
      <Canvas camera={{ position: [0, 0, 26], fov: 52 }} dpr={[1, 2]}>
        <color attach="background" args={['#05070f']} />
        <fog attach="fog" args={['#05070f', 30, 70]} />
        <Scene model={model} onHover={setHover} />
        <OrbitControls enablePan minDistance={9} maxDistance={52} />
      </Canvas>
      {hover && (
        <div className="detail">
          <div><b>{hover.name}</b></div>
          <div className="k">{hover._feature ? 'input feature' : hover.kind === 'output' ? 'network output' : `${hover.kind} node`}{hover.head && hover.head !== 'y' ? ` · head: ${hover.head}` : ''}</div>
          {hover.summary && <div style={{ margin: '6px 0' }}>{hover.summary}</div>}
          {hover.task && hover.task !== 'binary' && <div><span className="k">task:</span> {hover.task}</div>}
          {up && up.length > 0 && <div><span className="k">consumes:</span> {up.length} upstream nodes</div>}
          {(hover.metrics?.value ?? hover.metrics?.test_accuracy) != null &&
            <div><span className="k">{hover.metrics?.metric || 'acc'}:</span> {hover.metrics?.value ?? hover.metrics?.test_accuracy}</div>}
        </div>
      )}
      <div className="legend" style={{ left: 14, bottom: 38 }}>
        <span><i style={{ background: '#5cd0ff' }} />features → models</span>
        <span><i style={{ background: '#b98cff' }} />models → meta</span>
        <span><i style={{ background: '#4ade80' }} />meta → ŷ output</span>
      </div>
    </div>
  )
}
