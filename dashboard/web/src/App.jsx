import React, { useEffect, useRef, useState } from 'react'
import NetworkPanel from './NetworkPanel.jsx'
import ChatPanel from './ChatPanel.jsx'
import StreamOfMind from './StreamOfMind.jsx'
import { useBrainThoughts } from './useBrainThoughts.js'
import TradingDashboard from './trading/TradingDashboard.jsx'
import MarketWindow from './trading/MarketWindow.jsx'

// The brain page is the LIVING CORTEX view: real trained routing graph from
// /api/network/state (run_network.py on real market candles) — the old
// synthetic multi-output demo (run_active.py / mackey_glass) was removed
// 2026-07-04 on the honest-wiring rule: truth, real data, no demos.

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
  // CORTEX header state: real network_state.json (real candles, real weights).
  const [net, setNet] = useState(null)
  useEffect(() => {
    let on = true
    const load = () => fetch('/api/network/state').then((r) => r.json())
      .then((j) => { if (on) setNet(j) }).catch(() => {})
    load()
    const t = setInterval(load, 30000)
    return () => { on = false; clearInterval(t) }
  }, [])
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

  // Real CORTEX summary for the header + KPI strip (network_state.json only).
  const nodes = net?.nodes || []
  const edges = net?.edges || []
  const dsName = net?.dataset?.name
  const isReal = net?.dataset?.real !== false && !!dsName
  const headline = net?.headline_accuracy
  const baseline = net?.dataset?.naive_baseline
  const compute = net?.compute
  const stackChips = (net?.stack || '').split('·').map((s) => s.trim()).filter(Boolean)

  return (
    <div className="app">
      <header className="top">
        <div className="brand">
          <span className="dot" />
          <div>
            <h1>{net?.project || 'ML Network Brain — CORTEX'}</h1>
            <small>{dsName ? `${dsName}${isReal ? '' : ' ⚠ non-real state — press Refresh'}`
              : 'live market cortex · real data only'}</small>
          </div>
        </div>
        <div className="chips">
          {stackChips.map((c) => <span className="chip" key={c}>{c}</span>)}
        </div>
        <TabBar />
        <div className="spacer" />
        <div className="gen">
          built<br />{net?.generated_at || '—'}
        </div>
      </header>

      {nodes.length > 0 && (
        <section className="kpis">
          <Kpi label="Holdout accuracy" value={headline != null ? Number(headline).toFixed(3) : '—'}
            sub={`vs naive baseline ${baseline?.toFixed?.(3) ?? '—'} · chronological split`}
            pct={headline ? headline * 100 : 0} />
          <Kpi label="Network" value={nodes.length} sub={`${edges.length} real trained edges`} />
          {net?.active_subnet && (
            <Kpi label="Active subnetwork"
              value={`top-${net.active_subnet.top_k}/${net.active_subnet.n_experts}`}
              sub={`${net.active_subnet.n_communities} Leiden communities · ${net.active_subnet.mean_active} avg active`} />
          )}
          {compute && (
            <Kpi label="Reflex compute" value={`${Math.round((compute.escalation_rate || 0) * 100)}%`}
              sub={`escalation over ${compute.n_inputs} inputs · stay-flat is a routing outcome`} />
          )}
        </section>
      )}

      <NetworkPanel />

      <section className="grid">
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
      </section>

      <div className="footer">
        ML Network Brain · living CORTEX dashboard · real trained state only ·
        {' '}{nodes.length} nodes auto-synced from <code>/api/network/state</code>
      </div>
    </div>
  )
}
