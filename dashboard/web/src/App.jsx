import React from 'react'
import Graph3D from './Graph3D.jsx'
import { AccuracyBars, NoiseSweep } from './Charts.jsx'
import { useNetworkState, KIND_COLOR } from './useState.js'

function Kpi({ label, value, sub, pct }) {
  return (
    <div className="kpi">
      <div className="label">{label}</div>
      <div className="val">{value}</div>
      {sub && <div className="sub">{sub}</div>}
      {pct != null && <div className="bar" style={{ width: `${Math.min(100, pct)}%` }} />}
    </div>
  )
}

export default function App() {
  const { state, err } = useNetworkState(4000)

  if (!state) {
    return <div className="loading">{err ? `connection error: ${err}` : 'connecting to ML Network Brain…'}</div>
  }

  const nodes = state.nodes || []
  const edges = state.edges || []
  const baseline = state.dataset?.naive_baseline
  const headline = state.headline_accuracy
  const best = nodes.reduce((b, n) => {
    const a = n.metrics?.test_accuracy ?? 0
    return a > (b.acc ?? 0) ? { name: n.name, acc: a } : b
  }, {})
  const stackChips = (state.stack || '').split('·').map((s) => s.trim()).filter(Boolean)

  return (
    <div className="app">
      <header className="top">
        <div className="brand">
          <span className="dot" />
          <div>
            <h1>{state.project || 'ML Network Brain'}</h1>
            <small>{state.dataset?.name}</small>
          </div>
        </div>
        <div className="chips">
          {stackChips.map((c) => <span className="chip" key={c}>{c}</span>)}
        </div>
        <div className="spacer" />
        <div className="gen">
          updated<br />{state.generated_at || '—'}
        </div>
      </header>

      <section className="kpis">
        <Kpi label="Headline accuracy" value={headline != null ? headline.toFixed(3) : '—'}
          sub={`vs baseline ${baseline?.toFixed?.(3) ?? '—'}`}
          pct={headline ? headline * 100 : 0} />
        <Kpi label="Nodes" value={nodes.length} sub={`${edges.length} wired edges`} />
        <Kpi label="Best node" value={best.name || '—'} sub={best.acc ? best.acc.toFixed(3) : ''} />
        <Kpi label="Stacking (sklearn)" value={state.stacking_accuracy?.toFixed?.(3) ?? '—'}
          sub="cross-validated meta-learner" />
        {state.autogluon_accuracy != null &&
          <Kpi label="AutoGluon" value={state.autogluon_accuracy.toFixed(3)} sub="multi-layer ensemble" />}
        {state.router_accuracy != null &&
          <Kpi label="Learned router" value={state.router_accuracy.toFixed(3)} sub="dynamic per-input routing" />}
      </section>

      <section className="grid">
        <div className="card graphwrap-card" style={{ padding: 0 }}>
          <Graph3D nodes={nodes} edges={edges} />
          <div className="legend">
            {Object.entries(KIND_COLOR).filter(([k]) => nodes.some((n) => n.kind === k)).map(([k, c]) => (
              <span key={k}><i style={{ background: c }} />{k}</span>
            ))}
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="card">
            <h2>Node accuracy ranking</h2>
            <div className="hint">Per-node test accuracy (walk-forward). Bar colour = node family.</div>
            <AccuracyBars nodes={nodes} baseline={baseline} />
          </div>
          {state.noise_sweep?.length > 0 && (
            <div className="card">
              <h2>Reservoir accuracy vs injected noise</h2>
              <div className="hint">How a reservoir node degrades as chaos-noise rises.</div>
              <NoiseSweep sweep={state.noise_sweep} />
            </div>
          )}
        </div>
      </section>

      <div className="footer">
        ML Network Brain · live registry-driven dashboard · React + Three.js + D3 ·
        {' '}{nodes.length} nodes auto-synced from <code>/api/state</code>
      </div>
    </div>
  )
}
