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
  const heads = state.heads && state.heads.length ? state.heads : null
  const baseline = state.dataset?.naive_baseline
  const headline = state.headline_accuracy
  const getAcc = (n) => n.metrics?.value ?? n.metrics?.test_accuracy ?? 0
  const best = nodes.filter((n) => !['output', 'input'].includes(n.kind)).reduce((b, n) => {
    const a = getAcc(n); return a > (b.acc ?? -1) ? { name: n.name, acc: a } : b
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
        {heads ? (
          <>
            {heads.map((h) => (
              <Kpi key={h.name} label={`${h.name} · ${h.task}`}
                value={Number(h.value).toFixed(3)}
                sub={`${h.metric} · base ${Number(h.baseline).toFixed(2)} · ${h.beats_baseline ? 'beats ✓' : 'below'}`}
                pct={(h.task === 'regression' ? Math.max(0, h.value) : h.value) * 100} />
            ))}
            <Kpi label="Output heads" value={heads.length}
              sub={`${nodes.length} nodes · ${edges.length} real edges`} />
          </>
        ) : (
          <>
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
          </>
        )}
      </section>

      <section className="grid">
        <div className="card graphwrap-card" style={{ padding: 0 }}>
          <Graph3D nodes={nodes} edges={edges} dataset={state.dataset} heads={heads} />
          <div className="legend">
            {Object.entries(KIND_COLOR).filter(([k]) => nodes.some((n) => n.kind === k)).map(([k, c]) => (
              <span key={k}><i style={{ background: c }} />{k}</span>
            ))}
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {heads ? (
            <div className="card">
              <h2>Output heads (multi-output layer)</h2>
              <div className="hint">Each head is a real sub-network on the same inputs · walk-forward · vs its task baseline.</div>
              <div className="bars">
                {heads.map((h) => {
                  const v = h.task === 'regression' ? Math.max(0, h.value) : h.value
                  const b = h.task === 'regression' ? Math.max(0, h.baseline) : h.baseline
                  return (
                    <div className="row" key={h.name}>
                      <div className="nm" title={`${h.name} (${h.task})`}>{h.name}</div>
                      <div className="track">
                        <div className="fill" style={{ width: `${Math.min(100, v * 100)}%` }} />
                      </div>
                      <div className="pc">{Number(h.value).toFixed(3)}</div>
                      <div className="pc" style={{ color: h.beats_baseline ? 'var(--good)' : 'var(--bad)' }}>
                        {h.beats_baseline ? '✓' : '✗'}{Number(b).toFixed(2)}
                      </div>
                    </div>
                  )
                })}
              </div>
              <div className="baseline-note">✓ = beats the task baseline (majority for classification, mean-predictor for regression).</div>
            </div>
          ) : (
            <div className="card">
              <h2>Node accuracy ranking</h2>
              <div className="hint">Per-node test accuracy (walk-forward). Bar colour = node family.</div>
              <AccuracyBars nodes={nodes} baseline={baseline} />
            </div>
          )}
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
