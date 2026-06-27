import React, { useMemo, useRef, useState } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { OrbitControls, Html, Line, Stars } from '@react-three/drei'
import * as THREE from 'three'
import { kindColor } from './useState.js'

// Layered radial layout: each node-family `kind` gets its own vertical layer;
// nodes in a layer are spread around a circle. Edges (upstream -> node) are
// drawn as glowing lines. The whole graph slowly auto-rotates and each node
// pulses with an emissive intensity proportional to its test accuracy.

const LAYER_ORDER = ['base', 'chaos', 'regime', 'symbolic', 'router', 'ensemble', 'automl', 'brain']

function layout(nodes) {
  const byKind = {}
  nodes.forEach((n) => { (byKind[n.kind] = byKind[n.kind] || []).push(n) })
  const kinds = Object.keys(byKind).sort(
    (a, b) => (LAYER_ORDER.indexOf(a) + 1 || 99) - (LAYER_ORDER.indexOf(b) + 1 || 99))
  const pos = {}
  const layers = kinds.length
  kinds.forEach((k, li) => {
    const group = byKind[k]
    const y = (li - (layers - 1) / 2) * 3.4
    const radius = 4.2 + group.length * 0.18
    group.forEach((n, i) => {
      const ang = (i / group.length) * Math.PI * 2 + li * 0.6
      pos[n.name] = [Math.cos(ang) * radius, y, Math.sin(ang) * radius]
    })
  })
  return pos
}

function Node({ node, position, onHover }) {
  const ref = useRef()
  const acc = node.metrics?.test_accuracy ?? 0.5
  const color = kindColor(node.kind)
  const size = 0.28 + Math.max(0, acc - 0.5) * 1.4
  useFrame((st) => {
    if (!ref.current) return
    const t = st.clock.elapsedTime
    ref.current.material.emissiveIntensity = 0.55 + 0.45 * Math.sin(t * 2 + position[0])
  })
  return (
    <group position={position}>
      <mesh
        ref={ref}
        onPointerOver={(e) => { e.stopPropagation(); onHover(node) }}
        onPointerOut={() => onHover(null)}
      >
        <sphereGeometry args={[size, 24, 24]} />
        <meshStandardMaterial
          color={color} emissive={color} emissiveIntensity={0.7}
          metalness={0.3} roughness={0.35} />
      </mesh>
      <Html distanceFactor={14} center style={{ pointerEvents: 'none' }}>
        <div style={{
          color: '#cfe0ff', fontSize: 10, whiteSpace: 'nowrap', opacity: 0.85,
          textShadow: '0 0 6px #000', transform: 'translateY(-18px)',
        }}>{node.name}</div>
      </Html>
    </group>
  )
}

function Edges({ edges, pos }) {
  return edges.map((e, i) => {
    const a = pos[e.source], b = pos[e.target]
    if (!a || !b) return null
    return (
      <Line key={i} points={[a, b]} color={'#4a6cff'} lineWidth={1}
        transparent opacity={0.28} />
    )
  })
}

function Scene({ nodes, edges, onHover }) {
  const grp = useRef()
  const pos = useMemo(() => layout(nodes), [nodes])
  useFrame((_, dt) => { if (grp.current) grp.current.rotation.y += dt * 0.12 })
  return (
    <>
      <ambientLight intensity={0.45} />
      <pointLight position={[10, 12, 8]} intensity={1.1} color="#9ec8ff" />
      <pointLight position={[-10, -8, -6]} intensity={0.6} color="#b98cff" />
      <Stars radius={60} depth={40} count={1800} factor={3} fade speed={1} />
      <group ref={grp}>
        <Edges edges={edges} pos={pos} />
        {nodes.map((n) => (
          <Node key={n.name} node={n} position={pos[n.name] || [0, 0, 0]} onHover={onHover} />
        ))}
      </group>
    </>
  )
}

export default function Graph3D({ nodes, edges }) {
  const [hover, setHover] = useState(null)
  return (
    <div className="graphwrap">
      <Canvas camera={{ position: [0, 2, 18], fov: 55 }} dpr={[1, 2]}>
        <color attach="background" args={['#05070f']} />
        <fog attach="fog" args={['#05070f', 18, 46]} />
        <Scene nodes={nodes} edges={edges} onHover={setHover} />
        <OrbitControls enablePan={false} minDistance={8} maxDistance={34}
          autoRotate={false} />
      </Canvas>
      {hover && (
        <div className="detail">
          <div><b>{hover.name}</b></div>
          <div className="k">{hover.kind} node</div>
          <div style={{ margin: '6px 0' }}>{hover.summary}</div>
          <div><span className="k">test acc:</span> {(hover.metrics?.test_accuracy ?? '—')}</div>
          <div><span className="k">input dim:</span> {hover.input_dim}</div>
          {hover.upstream?.length > 0 &&
            <div><span className="k">upstream:</span> {hover.upstream.length} nodes</div>}
        </div>
      )}
    </div>
  )
}
