import React, { useRef, useState } from 'react'
import Graph3D from './Graph3D.jsx'
import SigmaNetwork from './SigmaNetwork.jsx'
import NetworkPanel from './NetworkPanel.jsx'
import { AccuracyBars, NoiseSweep } from './Charts.jsx'
import ChatPanel from './ChatPanel.jsx'
import StreamOfMind from './StreamOfMind.jsx'
import { useBrainThoughts } from './useBrainThoughts.js'
import { useNetworkState, KIND_COLOR } from './useState.js'
import TradingDashboard from './trading/TradingDashboard.jsx'
import MarketWindow from './trading/MarketWindow.jsx'

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
  // Pop-out market window: render only that workspace, no brain chrome.
  // NSE control now lives INSIDE OpenAlgo (/paper) — send any ?win=nse there so no
  // NSE control panel renders outside OpenAlgo. Crypto stays its own independent window.
  const winParam = new URLSearchParams(window.location.search).get('win')
  if (winParam === 'nse') {
    window.location.replace('/auto-trading')
    return null
  }
  if (winParam === 'crypto') {
    return <MarketWindow market="crypto" />
  }

  const [view, setView] = useState('brain')   // 'brain' | 'trading'
  const { state, err } = useNetworkState(4000)
  const [thoughts, setThoughts] = useState([])
  const thoughtSeq = useRef(0)
  const onThought = (text) => {
    if (!text) return
    const id = `${Date.now()}-${thoughtSeq.current++}`
    setThoughts((t) => [{ id, text, ts: Date.now() }, ...t].slice(0, 40))
  }
  // P4.6: stream the brain's REAL think-cycle thoughts into the panel via the AG-UI protocol.
  const think = useBrainThoughts(onThought)

  // in-app React views (Brain/Trading) + links to the other local-hosted dashboards.
  // Each external page opens in a NEW TAB; the Hub aggregates every brain (P4.1–P4.6) and
  // trading (T1–T8) live panel, so "the rest of the dashboard" is one click away here.
  const NAV_LINKS = [
    { href: '/hub', label: '🗂 Hub' },
    { href: '/architecture', label: '🏗 Architecture' },
    { href: '/knowledge', label: '🕸 Knowledge' },
  ]
  const TabBar = () => (
    <div className="chips" style={{ gap: 8, flexWrap: 'wrap' }}>
      <span className={`chip${view === 'brain' ? ' active' : ''}`}
        style={{ cursor: 'pointer', borderColor: view === 'brain' ? '#4da3ff' : undefined }}
        onClick={() => setView('brain')}>🧠 Brain</span>
      <span className={`chip${view === 'trading' ? ' active' : ''}`}
        style={{ cursor: 'pointer', borderColor: view === 'trading' ? '#4da3ff' : undefined }}
        onClick={() => setView('trading')}>📈 Trading</span>
      <span style={{ width: 1, alignSelf: 'stretch', background: '#1e2837', margin: '0 2px' }} />
      {NAV_LINKS.map((l) => (
        <a className="chip" key={l.href} href={l.href} target="_blank" rel="noopener"
          style={{ cursor: 'pointer', textDecoration: 'none' }}>{l.label}</a>
      ))}
    </div>
  )

  if (view === 'trading') {
    return (
      <div className="app">
        <header className="top">
          <div className="brand">
            <span className="dot" />
            <div><h1>Trading · Dark Pro</h1><small>NSE + Crypto · T1–T6</small></div>
          </div>
          <TabBar />
          <div className="spacer" />
        </header>
        <div style={{ padding: '0 16px 24px' }}>
          <TradingDashboard />
        </div>
      </div>
    )
  }

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
        <TabBar />
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
            {state.gate_accuracy != null &&
              <Kpi label="Diff. gate (P3.5)" value={state.gate_accuracy.toFixed(3)} sub="backprop over frozen experts" />}
            {state.cascade_accuracy != null &&
              <Kpi label="Deep cascade (P3.6)" value={state.cascade_accuracy.toFixed(3)} sub={`grown depth ${state.cascade_depth ?? '—'} · skip-connected`} />}
            {state.bus_accuracy != null &&
              <Kpi label="Dynamic I/O bus (P3.7)" value={state.bus_accuracy.toFixed(3)} sub="heterogeneous-width sources" />}
            {state.active_subnet != null &&
              <Kpi label="Active subnetwork (P3.8)" value={`top-${state.active_subnet.top_k}/${state.active_subnet.n_experts}`}
                sub={`per-input · ${state.active_subnet.n_communities} communities · ${state.active_subnet.mean_active} avg active`} />}
          </>
        )}
      </section>

      <NetworkPanel />

      <section className="grid">
        <div className="card graphwrap-card" style={{ padding: 0 }}>
          {state.firing?.length ? (
            <SigmaNetwork state={state} />
          ) : (
            <>
              <Graph3D nodes={nodes} edges={edges} dataset={state.dataset} heads={heads} />
              <div className="legend">
                {Object.entries(KIND_COLOR).filter(([k]) => nodes.some((n) => n.kind === k)).map(([k, c]) => (
                  <span key={k}><i style={{ background: c }} />{k}</span>
                ))}
              </div>
            </>
          )}
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
          <div className="card mind-card">
            <h2>Stream of Mind
              <button className="think-btn" onClick={() => think('How does the brain decide when to ask for help?')}
                style={{ marginLeft: 10, fontSize: 12, padding: '2px 10px', cursor: 'pointer',
                  background: '#1b2433', color: '#4cc2ff', border: '1px solid #1e2837', borderRadius: 8 }}>
                ⚡ Think
              </button>
            </h2>
            <div className="hint">The brain's live state of mind (AG-UI stream) — thoughts fire, glow, then fade; salient ones consolidate to memory.</div>
            <StreamOfMind thoughts={thoughts} />
          </div>
          <div className="card chat-card">
            <h2>Brain Chat</h2>
            <div className="hint">Chat with the brain about the network, nodes and results.</div>
            <ChatPanel onThought={onThought} />
          </div>
        </div>
      </section>

      <div className="footer">
        ML Network Brain · live registry-driven dashboard · React + Three.js + D3 ·
        {' '}{nodes.length} nodes auto-synced from <code>/api/state</code>
      </div>
    </div>
  )
}
