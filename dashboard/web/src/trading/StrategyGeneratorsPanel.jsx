// StrategyGeneratorsPanel.jsx — "🧬 Strategy Generators (the creator portfolio)"
// Surfaces trading/strategy/generators: the DEAP evolver + 6 SOTA generators (LLM-mutation,
// gplearn+PySR symbolic regression, pyribs quality-diversity, formulaic-alpha mining, Optuna,
// RD-Agent). Every generator's candidates pass through ONE CPCV+Deflated-Sharpe+PBO + family-wise
// gate → the shared SkillLibrary → the brain pipeline. HONEST: `by_generator` is the live library
// grouped by which generator actually bred each admitted strategy — no demo numbers.
// Self-contained polling of /api/trading/generators (~8s), inline-styled via ./theme.js.
import { useEffect, useState } from 'react'
import { T } from './theme.js'

async function getJSON(url) {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json()
}
function fmt(v, d = 3) {
  const n = v == null ? null : Number(v)
  return n == null || !Number.isFinite(n) ? '—' : n.toFixed(d)
}

// friendly label per generator source id
const GEN_LABEL = {
  deap_nsga2: 'DEAP NSGA-II (genetic)',
  llm_mutation: 'LLM mutation (FunSearch)',
  symbolic_gplearn: 'Symbolic · gplearn',
  symbolic_pysr: 'Symbolic · PySR',
  quality_diversity: 'Quality-Diversity (pyribs)',
  alpha_mining: 'Formulaic-alpha mining',
  optuna_tune: 'Optuna tuner',
  rd_agent: 'RD-Agent(Q) researcher',
  self_evolve: 'Self-evolve (DEAP)',
}

function Card({ title, hint, children }) {
  return (
    <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 12,
      padding: 14, marginBottom: 12 }}>
      <div style={{ fontSize: 14, fontWeight: 800, color: T.text }}>{title}</div>
      {hint && <div style={{ fontSize: 11, color: T.muted, marginTop: 3, marginBottom: 8 }}>{hint}</div>}
      {children}
    </div>
  )
}

function Chip({ label, on }) {
  return (
    <span style={{ display: 'inline-block', padding: '3px 9px', margin: '3px 4px 0 0',
      borderRadius: 999, fontSize: 11, fontWeight: 700,
      background: on ? 'rgba(34,197,94,0.14)' : 'rgba(148,163,184,0.12)',
      color: on ? T.good : T.muted, border: `1px solid ${on ? T.good : T.border}` }}>
      {label}
    </span>
  )
}

export default function StrategyGeneratorsPanel({ intervalMs = 8000 }) {
  const [d, setD] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    let alive = true
    const tick = () => getJSON('/api/trading/generators')
      .then(j => { if (alive) { setD(j); setErr(null) } })
      .catch(e => { if (alive) setErr(String(e)) })
    tick()
    const id = setInterval(tick, intervalMs)
    return () => { alive = false; clearInterval(id) }
  }, [intervalMs])

  if (err && !d) return <div style={{ color: T.bad, fontSize: 12 }}>Generators: {err}</div>
  if (!d) return <div style={{ color: T.muted, fontSize: 12 }}>Loading strategy generators…</div>
  if (d.available === false) return <div style={{ color: T.bad, fontSize: 12 }}>Generators: {d.error}</div>

  const gens = d.generators || []
  const byGen = d.by_generator || {}
  const lib = d.library || {}
  const enabled = !!d.enabled

  return (
    <div>
      <Card title="🧬 Strategy Generators — the creator portfolio"
        hint="DEAP + 6 SOTA generators → ONE CPCV+Deflated-Sharpe+PBO + family-wise gate → skill library → brain">
        <div style={{ marginBottom: 8 }}>
          <span style={{ fontSize: 12, color: enabled ? T.good : T.warn, fontWeight: 800 }}>
            {enabled ? '● evolution ARMED (paper)' : '○ evolution gated OFF'}
          </span>
          <span style={{ fontSize: 12, color: T.muted, marginLeft: 10 }}>
            {d.n_generators} generators · {lib.n_skills ?? 0} strategies in library
          </span>
        </div>
        <div>{gens.map(g => <Chip key={g} label={GEN_LABEL[g] || g} on />)}</div>
      </Card>

      <Card title="Bred strategies by generator"
        hint="the live skill library grouped by which generator actually produced each admitted strategy (real, not a demo)">
        {Object.keys(byGen).length === 0
          ? <div style={{ fontSize: 12, color: T.muted }}>
              No strategies admitted yet — generators run each brain-learning cycle (~15 min) and a
              candidate is only admitted once it clears the overfit + family-wise gate on real data.
            </div>
          : <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ color: T.muted, textAlign: 'left' }}>
                  <th style={{ padding: '4px 6px' }}>Generator</th>
                  <th style={{ padding: '4px 6px' }}>Admitted</th>
                  <th style={{ padding: '4px 6px' }}>Best DSR</th>
                  <th style={{ padding: '4px 6px' }}>Markets</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(byGen).sort((a, b) => b[1].count - a[1].count).map(([src, g]) => (
                  <tr key={src} style={{ borderTop: `1px solid ${T.border}` }}>
                    <td style={{ padding: '4px 6px', color: T.text, fontWeight: 700 }}>{GEN_LABEL[src] || src}</td>
                    <td style={{ padding: '4px 6px', color: T.text }}>{g.count}</td>
                    <td style={{ padding: '4px 6px', color: T.good }}>{fmt(g.best_metric)}</td>
                    <td style={{ padding: '4px 6px', color: T.muted }}>
                      {Object.entries(g.markets || {}).map(([m, n]) => `${m}:${n}`).join(' · ')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>}
      </Card>

      <Card title="Best strategy now trading, per market"
        hint="the top library survivor the brain pipeline has wired in for live decisions (via evolved_link)">
        <div style={{ fontSize: 12, color: T.text }}>
          {Object.entries(d.best_by_market || {}).map(([m, id]) => (
            <div key={m} style={{ padding: '2px 0' }}>
              <span style={{ color: T.muted }}>{m}: </span>
              <span style={{ fontWeight: 700 }}>{id || '— none yet'}</span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}
