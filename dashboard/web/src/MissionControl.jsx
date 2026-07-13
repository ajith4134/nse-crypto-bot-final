// MissionControl.jsx — "🎯 Mission Control" (proposal D): one dense command surface over the
// REAL endpoints. Grafana/OpenBB-style KPI strip + the most decision-critical panels in one
// screen: direction accuracy (X-Ray + model AUC), per-market scorecards, brain health, live
// trade status. Every tile is honest — real data or an explicit loading/empty state.
import { useEffect, useState } from 'react'
import { T } from './trading/theme.js'
import DirectionXrayPanel from './trading/DirectionXrayPanel.jsx'

async function getJSON(url) {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json()
}
function usePoll(url, ms = 12000) {
  const [d, setD] = useState({ loading: true })
  useEffect(() => {
    let on = true
    const tick = () => getJSON(url).then((j) => on && setD({ data: j })).catch((e) => on && setD({ error: String(e.message || e) }))
    tick(); const t = setInterval(tick, ms)
    return () => { on = false; clearInterval(t) }
  }, [url, ms])
  return d
}
const pct = (v, dp = 0) => (v == null ? '—' : `${(v * 100).toFixed(dp)}%`)

function Stat({ label, value, sub, tone = 'muted' }) {
  const col = { good: T.good, warn: T.warn, bad: T.bad, accent: T.accent, muted: T.text }[tone] || T.text
  return (
    <div style={{ flex: '1 1 150px', minWidth: 150, background: T.panel, border: `1px solid ${T.border}`,
                  borderRadius: 10, padding: '10px 12px' }}>
      <div style={{ fontSize: 10, color: T.muted, textTransform: 'uppercase', letterSpacing: 0.4 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 800, color: col, lineHeight: 1.15, marginTop: 2 }}>{value}</div>
      {sub && <div style={{ fontSize: 10, color: T.muted, marginTop: 2 }}>{sub}</div>}
    </div>
  )
}
function Card({ title, hint, children }) {
  return (
    <div style={{ background: T.bg, border: `1px solid ${T.border}`, borderRadius: 12, padding: 14 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
        <span style={{ fontWeight: 700, fontSize: 15, color: T.text }}>{title}</span>
        {hint && <span style={{ fontSize: 10, color: T.muted }}>{hint}</span>}
      </div>
      {children}
    </div>
  )
}

export default function MissionControl() {
  const dir = usePoll('/api/trading/direction/xray').data || {}
  const se = usePoll('/api/brain/selfeval').data || {}
  const neu = usePoll('/api/brain/neurons', 20000).data || {}
  const evo = usePoll('/api/brain/evolution', 20000).data || {}
  const flow = usePoll('/api/trading/brain/flow', 15000).data || {}

  const ds = dir.summary || {}
  const model = dir.model || {}
  const ms = se.market_scorecard || {}
  const gu = se.genius_use || {}
  const store = neu.store || {}
  const healthy = (flow.stages || []).filter((s) => s.ok).length
  const totalStages = (flow.stages || []).length

  return (
    <div style={{ padding: '0 4px 24px', display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* KPI STRIP — the whole system at a glance */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <Stat label="Direction model AUC" value={model.trained ? (model.holdout_auc ?? '—') : 'untrained'}
              sub={model.trained ? `${model.engine} · n${model.n} · >0.5 = edge` : 'needs resolved data'}
              tone={model.holdout_auc > 0.55 ? 'good' : model.holdout_auc > 0.52 ? 'warn' : 'bad'} />
        <Stat label="Direction coverage" value={ds.with_driver_rate == null ? '—' : pct(ds.with_driver_rate)}
              sub={`${ds.decisions ?? 0} decisions · abstain ${ds.abstain_rate == null ? '—' : pct(ds.abstain_rate)}`}
              tone={(ds.with_driver_rate ?? 0) > 0.7 ? 'good' : 'warn'} />
        <Stat label="Crypto win-rate" value={pct(ms.crypto?.win_rate, 1)}
              sub={`${ms.crypto?.trades ?? 0} trades · pnl ${ms.crypto?.net_pnl ?? '—'}`}
              tone={(ms.crypto?.win_rate ?? 0) >= 0.5 ? 'good' : 'warn'} />
        <Stat label="NSE win-rate" value={pct(ms.nse?.win_rate, 1)}
              sub={`${ms.nse?.trades ?? 0} trades`} tone={(ms.nse?.win_rate ?? 0) >= 0.5 ? 'good' : 'warn'} />
        <Stat label="Neuron web" value={(store.neurons ?? 0).toLocaleString()}
              sub={`${store.links ?? 0} links · genius-use ${pct(gu.actionable_use_rate, 1)}`} tone="accent" />
        <Stat label="Evolution" value={evo.proven_lineages ?? 0}
              sub={`proven child>parent · ${evo.live_instructions ?? 0} instr`} tone="accent" />
        <Stat label="Cognitive loop" value={totalStages ? `${healthy}/${totalStages}` : '—'}
              sub="stages carrying live data" tone={healthy === totalStages && totalStages ? 'good' : 'warn'} />
      </div>

      {/* Direction — the owner's #1: front and centre */}
      <Card title="🧭 Direction — what data decides each trade"
            hint="the model + every source, weighted by measured edge">
        <DirectionXrayPanel />
      </Card>

      {/* Two-up: markets + brain health */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 14 }}>
        <Card title="📊 Per-market scorecard" hint="crypto ≠ NSE, kept separate">
          {['crypto', 'nse'].map((m) => {
            const s = ms[m] || {}
            return (
              <div key={m} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0',
                                    borderBottom: `1px solid ${T.border}`, fontSize: 13 }}>
                <b style={{ color: m === 'crypto' ? '#f0b90b' : '#4cc2ff' }}>{m.toUpperCase()}</b>
                <span>{s.trades ? <>win <b style={{ color: (s.win_rate ?? 0) >= 0.5 ? T.good : T.warn }}>{pct(s.win_rate, 1)}</b> · {s.trades} trades · {s.instruction_uses ?? 0} instr-uses</> : <span style={{ color: T.muted }}>no trades</span>}</span>
              </div>
            )
          })}
          {se.apply_lift && <div style={{ fontSize: 11, color: T.muted, marginTop: 8 }}>
            applied-instruction lift: baseline {pct(se.apply_lift.baseline_win_rate, 1)} · applied {se.apply_lift.applied?.n ? pct(se.apply_lift.applied.win_rate, 1) : '—'} {se.apply_lift.tilt_enabled ? '(tilt ON)' : '(attribution)'}</div>}
        </Card>

        <Card title="🧠 Brain health" hint="live subsystems">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
            <Row k="Neuron web" v={`${(store.neurons ?? 0).toLocaleString()} neurons · ${pct(store.action_coverage, 0)} action-coverage`} ok={store.action_coverage >= 0.99} />
            <Row k="Genius-use (actionable)" v={pct(gu.actionable_use_rate, 1)} ok={(gu.actionable_use_rate ?? 0) > 0.05} />
            <Row k="LLM parity (R23)" v={se.llm_parity?.ok ? `${se.llm_parity.brain_score} vs ${se.llm_parity.llm_score ?? '—'}` : 'not run'} ok={se.llm_parity?.parity === true} />
            <Row k="Cognitive loop" v={totalStages ? `${healthy}/${totalStages} stages flowing` : 'warming'} ok={healthy === totalStages && !!totalStages} />
            <Row k="Instruction evolution" v={`${evo.proven_lineages ?? 0} proven · ${evo.live_instructions ?? 0} live`} ok={(evo.live_instructions ?? 0) > 0} />
          </div>
        </Card>
      </div>
    </div>
  )
}

function Row({ k, v, ok }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, padding: '3px 0', borderBottom: `1px solid ${T.border}` }}>
      <span style={{ color: T.muted }}>{k}</span>
      <span style={{ color: ok ? T.good : T.warn, fontWeight: 600, textAlign: 'right' }}>{v}</span>
    </div>
  )
}
