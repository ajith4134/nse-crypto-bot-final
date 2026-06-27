import React, { useMemo, useRef, useState } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { OrbitControls, Html, Text, Stars } from '@react-three/drei'
import * as THREE from 'three'
import { kindColor } from './useState.js'

// ---------------------------------------------------------------------------
//  HONEST layered view of the ACTUAL network. Every node, edge and flow shown
//  here is REAL — derived only from /api/state (the live node registry); nothing
//  is fabricated to look pretty (project rule: "honest wiring").
//
//  Real architecture it renders:
//   * INPUT layer  = the dataset's real feature channels (dataset.feature_names).
//   * MODEL layer  = each predictor node; it REALLY consumes the whole feature
//                    vector (node.input_dim features, upstream=[]), so every
//                    feature -> model edge is a true data dependency.
//   * META layer   = nodes with a real upstream list (e.g. sk_stacking stacks the
//                    base nodes) — edges come straight from state.edges.
//   * OUTPUT       = p(class=1): terminal predictors (no downstream) emit the
//                    final prediction, so terminal -> output is their real output.
//  Particles flow along these real edges in the real direction of data flow.
// ---------------------------------------------------------------------------

const FEATURE_CONSUMERS = ['base', 'chaos', 'regime', 'symbolic']  // read raw features
const X_GAP = 4.6
const Y_GAP = 1.5
const OUTPUT = '＝ p(class=1)'

function chunk(arr, n) {
  const out = Array.from({ length: n }, () => [])
  arr.forEach((v, i) => out[i % n].push(v))
  return out
}
function colY(count) {
  const h = (count - 1) / 2
  return (i) => (h - i) * Y_GAP
}

// Build the layered model strictly from real nodes + real edges.
function buildModel(nodes, edges, dataset) {
  const upstreamMap = {}                       // target -> [sources] (REAL)
  const hasDownstream = new Set()              // any node that feeds another
  edges.forEach((e) => {
    (upstreamMap[e.target] = upstreamMap[e.target] || []).push(e.source)
    hasDownstream.add(e.source)
  })

  const featureNames = (dataset?.feature_names || []).slice(0, 14)
  const models = nodes.filter((n) => FEATURE_CONSUMERS.includes(n.kind))
  const metas = nodes.filter((n) => ['ensemble', 'router', 'meta'].includes(n.kind))
  const automl = nodes.filter((n) => n.kind === 'automl')

  // ---- columns (x positions), left -> right = direction of data flow ----
  const cols = []
  cols.push({ label: 'input · features', kind: 'input',
    items: featureNames.map((f) => ({ name: f, kind: 'input', _feature: true })) })
  const hiddenCols = chunk(models, Math.min(3, Math.max(1, Math.ceil(models.length / 7))))
  hiddenCols.forEach((c, i) => cols.push({ label: `model nodes ${hiddenCols.length > 1 ? i + 1 : ''}`.trim(), kind: 'model', items: c }))
  const midItems = [...metas, ...automl]
  if (midItems.length) cols.push({ label: 'meta / automl', kind: 'meta', items: midItems })
  cols.push({ label: 'output', kind: 'output', items: [{ name: OUTPUT, kind: 'output', _output: true }] })

  // ---- assign positions ----
  const pos = {}
  const L = cols.length
  const x0 = -((L - 1) * X_GAP) / 2
  cols.forEach((col, ci) => {
    col.x = x0 + ci * X_GAP
    const y = colY(col.items.length)
    col.items.forEach((it, i) => { it._pos = [col.x, y(i), 0]; pos[it.name] = it._pos })
  })

  // ---- REAL edges only ----
  const realEdges = []
  // (1) input feature -> every node that consumes raw features (upstream empty)
  const featureItems = cols[0].items
  ;[...models, ...automl].forEach((n) => {
    if ((upstreamMap[n.name] || []).length === 0) {
      featureItems.forEach((f) => realEdges.push({ a: f._pos, b: pos[n.name], kind: 'data' }))
    }
  })
  // (2) real upstream edges straight from state.edges (e.g. base -> sk_stacking)
  edges.forEach((e) => {
    if (pos[e.source] && pos[e.target]) realEdges.push({ a: pos[e.source], b: pos[e.target], kind: 'stack' })
  })
  // (3) terminal predictors (no downstream) -> output prediction
  const outPos = cols[cols.length - 1].items[0]._pos
  ;[...metas, ...automl, ...models].forEach((n) => {
    if (!hasDownstream.has(n.name)) realEdges.push({ a: pos[n.name], b: outPos, kind: 'pred' })
  })

  // node objects for rendering (real nodes + the input/output channels)
  const renderNodes = cols.flatMap((c) => c.items.map((it) => {
    const real = nodes.find((n) => n.name === it.name)
    return real ? { ...real, _pos: it._pos } : it
  }))
  const topY = (Math.max(...cols.map((c) => c.items.length)) / 2 + 0.8) * Y_GAP
  return { cols, realEdges, renderNodes, topY, upstreamMap }
}

function Node({ node, onHover }) {
  const ref = useRef()
  const acc = node.metrics?.test_accuracy
  const color = kindColor(node.kind)
  const channel = node._feature || node._output
  const size = channel ? 0.18 : 0.26 + Math.max(0, (acc ?? 0.5) - 0.5) * 0.9
  useFrame((st) => {
    if (ref.current) ref.current.material.emissiveIntensity =
      0.5 + 0.4 * Math.sin(st.clock.elapsedTime * 2 + node._pos[1])
  })
  return (
    <group position={node._pos}>
      <mesh ref={ref}
        onPointerOver={(e) => { e.stopPropagation(); onHover(node) }}
        onPointerOut={() => onHover(null)}>
        {channel
          ? <boxGeometry args={[0.34, 0.34, 0.34]} />
          : <sphereGeometry args={[size, 22, 22]} />}
        <meshStandardMaterial color={color} emissive={color}
          emissiveIntensity={0.7} metalness={0.25} roughness={0.4} />
      </mesh>
      <Html distanceFactor={15} center style={{ pointerEvents: 'none' }}>
        <div style={{
          color: channel ? '#9fb4e6' : '#dbe6ff', fontSize: channel ? 8 : 9,
          whiteSpace: 'nowrap', opacity: 0.9, textShadow: '0 0 6px #000',
          transform: 'translateY(-15px)',
        }}>{node.name}</div>
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
  return (
    <lineSegments geometry={geom}>
      <lineBasicMaterial color={color} transparent opacity={opacity} />
    </lineSegments>
  )
}

// glowing data packets travelling along the REAL edges, in the real flow direction
function FlowParticles({ edges, color, speed = 0.32, size = 0.06 }) {
  const ref = useRef()
  const dummy = useMemo(() => new THREE.Object3D(), [])
  const phases = useMemo(() => edges.map((_, i) => (i * 0.173) % 1), [edges])
  useFrame((st) => {
    if (!ref.current || !edges.length) return
    const t = st.clock.elapsedTime
    edges.forEach((e, i) => {
      const f = (t * speed + phases[i]) % 1
      dummy.position.set(
        e.a[0] + (e.b[0] - e.a[0]) * f,
        e.a[1] + (e.b[1] - e.a[1]) * f,
        e.a[2] + (e.b[2] - e.a[2]) * f)
      dummy.updateMatrix()
      ref.current.setMatrixAt(i, dummy.matrix)
    })
    ref.current.instanceMatrix.needsUpdate = true
  })
  if (!edges.length) return null
  return (
    <instancedMesh ref={ref} args={[undefined, undefined, edges.length]}>
      <sphereGeometry args={[size, 8, 8]} />
      <meshBasicMaterial color={color} toneMapped={false}
        transparent opacity={0.95} blending={THREE.AdditiveBlending} />
    </instancedMesh>
  )
}

function LayerLabel({ x, y, text }) {
  return (
    <Text position={[x, y, 0]} fontSize={0.4} color="#7f93bd"
      anchorX="center" anchorY="middle" outlineWidth={0.01} outlineColor="#05070f">
      {text.toUpperCase()}
    </Text>
  )
}

function Scene({ model, onHover }) {
  const grp = useRef()
  const dataEdges = useMemo(() => model.realEdges.filter((e) => e.kind === 'data'), [model])
  const stackEdges = useMemo(() => model.realEdges.filter((e) => e.kind === 'stack'), [model])
  const predEdges = useMemo(() => model.realEdges.filter((e) => e.kind === 'pred'), [model])
  useFrame((st) => {
    if (grp.current) grp.current.rotation.y = Math.sin(st.clock.elapsedTime * 0.1) * 0.3
  })
  return (
    <>
      <ambientLight intensity={0.5} />
      <pointLight position={[0, 10, 14]} intensity={1.2} color="#bcd4ff" />
      <pointLight position={[-12, -6, -8]} intensity={0.5} color="#b98cff" />
      <Stars radius={70} depth={40} count={1400} factor={3} fade speed={1} />
      <group ref={grp}>
        <EdgeLines edges={dataEdges} color="#2f5bd0" opacity={0.13} />
        <EdgeLines edges={stackEdges} color="#7a52d8" opacity={0.3} />
        <EdgeLines edges={predEdges} color="#2fd0a8" opacity={0.5} />
        <FlowParticles edges={dataEdges} color="#5cd0ff" speed={0.3} />
        <FlowParticles edges={stackEdges} color="#b98cff" speed={0.42} size={0.07} />
        <FlowParticles edges={predEdges} color="#4ade80" speed={0.5} size={0.09} />
        {model.cols.map((c) => <LayerLabel key={c.label} x={c.x} y={model.topY} text={c.label} />)}
        {model.renderNodes.map((n) => <Node key={n.name} node={n} onHover={onHover} />)}
      </group>
    </>
  )
}

export default function Graph3D({ nodes, edges, dataset }) {
  const [hover, setHover] = useState(null)
  const model = useMemo(() => buildModel(nodes, edges, dataset), [nodes, edges, dataset])
  const up = hover && model.upstreamMap[hover.name]
  return (
    <div className="graphwrap">
      <Canvas camera={{ position: [0, 1, 22], fov: 50 }} dpr={[1, 2]}>
        <color attach="background" args={['#05070f']} />
        <fog attach="fog" args={['#05070f', 28, 64]} />
        <Scene model={model} onHover={setHover} />
        <OrbitControls enablePan minDistance={8} maxDistance={46} />
      </Canvas>
      {hover && (
        <div className="detail">
          <div><b>{hover.name}</b></div>
          <div className="k">{hover._feature ? 'input feature channel'
            : hover._output ? 'network output'
            : `${hover.kind} node`}</div>
          {hover.summary && <div style={{ margin: '6px 0' }}>{hover.summary}</div>}
          {hover.input_desc && <div><span className="k">consumes:</span> {up && up.length ? `${up.length} upstream nodes` : hover.input_desc}</div>}
          {hover.metrics?.test_accuracy != null &&
            <div><span className="k">test acc:</span> {hover.metrics.test_accuracy}</div>}
        </div>
      )}
      <div className="legend" style={{ left: 14, bottom: 38 }}>
        <span><i style={{ background: '#5cd0ff' }} />features → models (raw data)</span>
        <span><i style={{ background: '#b98cff' }} />models → stacking (predictions)</span>
        <span><i style={{ background: '#4ade80' }} />→ output p(class=1)</span>
      </div>
    </div>
  )
}
