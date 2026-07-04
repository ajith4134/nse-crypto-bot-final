import React, { useEffect, useMemo, useState } from 'react'
import SigmaNetwork from './SigmaNetwork.jsx'

// CORTEX B7 — the living cortex view (design §3, saved-plan Step 5).
// Self-fetches /api/network/state (network_state.json written by run_network.py in a
// SUBPROCESS — the dashboard never trains in-process) and renders the upgraded
// SigmaNetwork plus a right-hand summary column: top-10 trust bars, reflex-arc
// escalation stats, community count, and CANON-56 mini-charts IF the state carries a
// fitness scorecard — skipped honestly when absent (no fake data, ever).

const POLL_MS = 30000

function ageLabel(s) {
  if (s == null) return null
  if (s < 90) return `${Math.round(s)}s ago`
  if (s < 5400) return `${Math.round(s / 60)}m ago`
  return `${(s / 3600).toFixed(1)}h ago`
}

function Sparkline({ values, color = '#4da3ff', h = 34 }) {
  const pts = useMemo(() => {
    const v = (values || []).map(Number).filter((x) => Number.isFinite(x))
    if (v.length < 2) return null
    const min = Math.min(...v), max = Math.max(...v), span = (max - min) || 1
    return v.map((x, i) => `${(i / (v.length - 1)) * 100},${h - 3 - ((x - min) / span) * (h - 6)}`).join(' ')
  }, [values, h])
  if (!pts) return null
  return (
    <svg viewBox={`0 0 100 ${h}`} preserveAspectRatio="none" style={{ width: '100%', height: h }}>
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.6" vectorEffect="non-scaling-stroke" />
    </svg>
  )
}

const RISK_COLOR = { ok: '#3ecf8e', watch: '#ffb454', high: '#ff6b6b' }

export default function NetworkPanel() {
  const [state, setState] = useState(null)
  const [antiOverfit, setAntiOverfit] = useState(null)
  const [err, setErr] = useState(null)
  const [refreshing, setRefreshing] = useState(false)
  const [refreshNote, setRefreshNote] = useState(null)

  const load = async () => {
    try {
      const r = await fetch('/api/network/state')
      const j = await r.json()
      setState(j)
      setErr(null)
    } catch (e) {
      setErr(String(e))
    }
    try {
      const ra = await fetch('/api/network/antioverfit')
      setAntiOverfit(await ra.json())
    } catch { /* telemetry is best-effort */ }
  }
  useEffect(() => {
    load()
    const t = setInterval(load, POLL_MS)
    return () => clearInterval(t)
  }, [])

  const refresh = async () => {
    setRefreshing(true)
    setRefreshNote(null)
    try {
      const r = await fetch('/api/network/refresh', { method: 'POST' })
      const j = await r.json()
      setRefreshNote(j.started ? 'rebuilding in background (~1–3 min)…' : (j.note || 'not started'))
    } catch (e) {
      setRefreshNote(`refresh failed: ${e}`)
    } finally {
      setRefreshing(false)
    }
  }

  const nodes = state?.nodes || []
  const hasGraph = nodes.length > 0 && (state?.edges || []).length > 0
  // top-10 trust: prefer the ledger snapshot; fall back to per-node trust tags
  const trustRows = useMemo(() => {
    const t = state?.trust && Object.keys(state.trust).length
      ? Object.entries(state.trust)
      : nodes.filter((n) => n.trust != null).map((n) => [n.name, n.trust])
    return t.map(([k, v]) => [k, Number(v)]).filter(([, v]) => Number.isFinite(v))
      .sort((a, b) => b[1] - a[1]).slice(0, 10)
  }, [state, nodes])
  const trustMax = trustRows.length ? Math.max(...trustRows.map(([, v]) => v)) || 1 : 1
  const compute = state?.compute
  const nComms = state?.active_subnet?.n_communities
  // CANON-56: equity curve only when a REAL fitness scorecard rode along in the state
  const equity = state?.fitness?.equity_curve || state?.scorecard?.equity_curve || null

  return (
    <section className="card" style={{ marginBottom: 16 }}>
      <h2 style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        CORTEX Network
        <button onClick={refresh} disabled={refreshing}
          style={{ fontSize: 12, padding: '3px 12px', cursor: 'pointer', borderRadius: 8,
            background: '#1b2433', color: '#4cc2ff', border: '1px solid #1e2837' }}>
          {refreshing ? '…' : '⟳ Refresh'}
        </button>
        {state?.state_age_s != null && (
          <span style={{ fontSize: 12, fontWeight: 400,
            color: state.state_age_s > 3600 ? '#ffb454' : '#8b96b8' }}>
            built {ageLabel(state.state_age_s)}
          </span>
        )}
        {refreshNote && <span style={{ fontSize: 12, fontWeight: 400, color: '#8b96b8' }}>{refreshNote}</span>}
      </h2>
      <div className="hint">
        T4 hierarchical gate over Leiden communities · T3 reflex conditional compute ·
        trust-biased routing — real trained weights only (run_network.py).
      </div>

      {err && <div style={{ color: 'var(--bad,#ff6b6b)', fontSize: 13 }}>fetch error: {err}</div>}
      {!err && !state && <div className="hint">loading network state…</div>}
      {state && !hasGraph && (
        <div className="hint">{state.note || 'no network state yet — press Refresh to build it'}</div>
      )}

      {hasGraph && (
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) 280px', gap: 14 }}>
          <div className="graphwrap-card" style={{ padding: 0, minHeight: 480 }}>
            <SigmaNetwork state={state} />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, fontSize: 13 }}>
            <div>
              <div style={{ color: '#8b96b8', marginBottom: 4 }}>network</div>
              <div>{nodes.length} nodes · {(state.edges || []).length} edges
                {nComms != null && <> · <b>{nComms}</b> communities</>}</div>
              {state.headline_accuracy != null && (
                <div className="k">accuracy {Number(state.headline_accuracy).toFixed(3)}
                  {state.dataset?.naive_baseline != null && ` · baseline ${Number(state.dataset.naive_baseline).toFixed(3)}`}</div>
              )}
            </div>

            {compute && (
              <div>
                <div style={{ color: '#8b96b8', marginBottom: 4 }}>reflex arc (T3 compute)</div>
                <div>escalation rate <b>{(compute.escalation_rate * 100).toFixed(0)}%</b>
                  <span className="k"> of {compute.n_inputs} inputs</span></div>
                <div className="k">
                  {Object.entries(compute.tier_counts || {}).map(([t, c]) => `tier ${+t + 1}: ${c}`).join(' · ')}
                </div>
              </div>
            )}

            <div>
              <div style={{ color: '#8b96b8', marginBottom: 4 }}>top-10 node trust</div>
              {trustRows.length === 0 && (
                <div className="k">no trust ledger yet — trust accrues as the brain records node outcomes</div>
              )}
              {trustRows.map(([name, v]) => (
                <div key={name} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                  <div style={{ width: 110, overflow: 'hidden', textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap' }} title={name}>{name}</div>
                  <div style={{ flex: 1, height: 7, background: '#161d33', borderRadius: 4 }}>
                    <div style={{ width: `${Math.min(100, (v / trustMax) * 100)}%`, height: '100%',
                      background: '#4da3ff', borderRadius: 4 }} />
                  </div>
                  <div style={{ width: 44, textAlign: 'right' }} className="k">{v.toFixed(3)}</div>
                </div>
              ))}
            </div>

            {equity ? (
              <div>
                <div style={{ color: '#8b96b8', marginBottom: 4 }}>equity curve (fitness scorecard)</div>
                <Sparkline values={equity} />
              </div>
            ) : (
              <div className="k">no fitness scorecard in this state — equity mini-chart appears
                once a run_network build carries one (never fabricated).</div>
            )}

            {antiOverfit && !antiOverfit.note && (
              <div>
                <div style={{ color: '#8b96b8', marginBottom: 4 }}>
                  anti-overfit telemetry (CANON-43)
                  <span style={{ marginLeft: 8, padding: '1px 7px', borderRadius: 6, fontSize: 11,
                    color: '#0b0f18', background: RISK_COLOR[antiOverfit.overfit_risk] || '#8b96b8' }}>
                    {String(antiOverfit.overfit_risk || '?').toUpperCase()}
                  </span>
                </div>
                <div className="k">free params <b>{antiOverfit.free_params}</b>
                  {antiOverfit.n_observations ? <> / {antiOverfit.n_observations} obs
                    {antiOverfit.params_per_observation != null && ` = ${antiOverfit.params_per_observation}`}</> : null}</div>
                <div className="k">backtests run <b>{antiOverfit.backtests_run}</b>
                  {antiOverfit.research_time_days ? ` · research age ${antiOverfit.research_time_days}d` : null}</div>
                {(antiOverfit.flags || []).map((f, i) => (
                  <div key={i} style={{ fontSize: 11, color: '#ffb454' }}>⚠ {f}</div>
                ))}
                {(!antiOverfit.flags || antiOverfit.flags.length === 0) && (
                  <div className="k">no overfitting flags raised.</div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  )
}
