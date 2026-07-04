// DebatePanel.jsx — "⚖️ Adversarial Debate + Verifier (Pillar 18)"
// Surfaces trading/brain/debate_gate.py: a bull/bear/risk debate (cognition.society) plus a
// process-reward step verifier (cognition.verifier) over a candidate trade. The user picks a
// symbol/direction (+ optional evidence), the brain deliberates via the real core.llm failover,
// and this shows the auditable decision_snapshot — role votes, arguments, per-step verifier
// scores, flip-rate, process reward, and the final gate (approve/block + size multiplier).
import { useState } from 'react'
import { T } from './theme.js'

async function getJSON(url) {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json()
}
const num = (v) => (v == null || !Number.isFinite(Number(v)) ? null : Number(v))
const pct = (v, d = 0) => { const n = num(v); return n == null ? '—' : `${(n * 100).toFixed(d)}%` }

function Vote({ role, v }) {
  const color = v > 0 ? T.good : v < 0 ? T.bad : T.muted
  const label = v > 0 ? 'YES' : v < 0 ? 'NO' : '—'
  return (
    <div style={{ minWidth: 66 }}>
      <div style={{ fontSize: 9, textTransform: 'uppercase', letterSpacing: 0.6, color: T.muted }}>{role}</div>
      <div style={{ fontSize: 14, fontWeight: 800, color }}>{label}</div>
    </div>
  )
}

export default function DebatePanel() {
  const [symbol, setSymbol] = useState('BTC/USDT')
  const [direction, setDirection] = useState('LONG')
  const [busy, setBusy] = useState(false)
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)

  const run = () => {
    setBusy(true); setErr(null)
    const q = new URLSearchParams({ symbol, direction }).toString()
    getJSON(`/api/trading/brain/debate?${q}`)
      .then(d => { setData(d); if (d && d.available === false) setErr(d.error || 'unavailable') })
      .catch(e => setErr(String(e)))
      .finally(() => setBusy(false))
  }

  const snap = data?.decision_snapshot || {}
  const steps = snap.verifier_steps || []
  const approved = data?.approved
  return (
    <div>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 10, flexWrap: 'wrap' }}>
        <input value={symbol} onChange={e => setSymbol(e.target.value)} placeholder="symbol"
               style={{ width: 110, background: T.panel2 || '#111', color: T.text,
                        border: `1px solid ${T.border}`, borderRadius: 6, padding: '4px 8px', fontSize: 12 }} />
        <select value={direction} onChange={e => setDirection(e.target.value)}
                style={{ background: T.panel2 || '#111', color: T.text, border: `1px solid ${T.border}`,
                         borderRadius: 6, padding: '4px 8px', fontSize: 12 }}>
          <option>LONG</option><option>SHORT</option>
        </select>
        <button onClick={run} disabled={busy}
                style={{ background: T.accent, color: '#000', border: 'none', borderRadius: 6,
                         padding: '5px 14px', fontSize: 12, fontWeight: 700, cursor: 'pointer', opacity: busy ? 0.6 : 1 }}>
          {busy ? 'deliberating…' : 'Run debate'}
        </button>
        {data && (
          <span style={{ fontSize: 11, marginLeft: 'auto' }}>
            gate <b style={{ color: approved ? T.good : T.bad }}>{approved ? 'APPROVE' : 'BLOCK'}</b>
            {' · '}size ×<b style={{ color: T.text }}>{num(data.size_mult) ?? '—'}</b>
          </span>
        )}
      </div>
      {err && <div style={{ color: T.bad, fontSize: 11, marginBottom: 8 }}>{err}</div>}
      {!data && !err && (
        <div style={{ fontSize: 11, color: T.muted }}>
          Pick a symbol/direction and run — bull/bear/risk debate the trade, then a step verifier checks the reasoning.
        </div>
      )}
      {data && (
        <>
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'flex-start', marginBottom: 8 }}>
            {Object.entries(snap.votes || {}).map(([r, v]) => <Vote key={r} role={r} v={v} />)}
            <div style={{ minWidth: 80 }}>
              <div style={{ fontSize: 9, textTransform: 'uppercase', letterSpacing: 0.6, color: T.muted }}>Verdict</div>
              <div style={{ fontSize: 14, fontWeight: 800,
                            color: snap.debate_verdict === 'yes' ? T.good : snap.debate_verdict === 'no' ? T.bad : T.muted }}>
                {(snap.debate_verdict || '—').toUpperCase()}
              </div>
            </div>
            <div style={{ minWidth: 80 }}>
              <div style={{ fontSize: 9, textTransform: 'uppercase', letterSpacing: 0.6, color: T.muted }}>Flip-rate</div>
              <div style={{ fontSize: 14, fontWeight: 800, color: T.text }}>{pct(snap.flip_rate)}</div>
            </div>
            <div style={{ minWidth: 90 }}>
              <div style={{ fontSize: 9, textTransform: 'uppercase', letterSpacing: 0.6, color: T.muted }}>Process reward</div>
              <div style={{ fontSize: 14, fontWeight: 800,
                            color: num(snap.process_reward) >= 0.5 ? T.good : T.warn }}>{pct(snap.process_reward)}</div>
            </div>
          </div>
          <div style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: 0.6, color: T.muted, margin: '8px 0 4px' }}>
            Verifier steps — each rationale step scored 0/1 (mode: {snap.mode?.verifier || '—'})
          </div>
          <div style={{ maxHeight: 150, overflowY: 'auto', marginBottom: 8 }}>
            {steps.map((s, i) => (
              <div key={i} style={{ display: 'flex', gap: 8, fontSize: 11, padding: '3px 2px',
                                    borderBottom: `1px solid ${T.gridline}`, alignItems: 'baseline' }}>
                <span style={{ color: s.score ? T.good : T.bad, fontWeight: 800, width: 16 }}>{s.score ? '✓' : '✗'}</span>
                <span style={{ flex: 1, color: T.text, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                      title={s.step}>{s.step}</span>
                <span style={{ color: T.muted, fontSize: 10, maxWidth: 180, overflow: 'hidden',
                               textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={s.critique}>{s.critique}</span>
              </div>
            ))}
          </div>
          <div style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: 0.6, color: T.muted, marginBottom: 4 }}>
            Role arguments
          </div>
          {Object.entries(snap.arguments || {}).map(([r, a]) => (
            <div key={r} style={{ fontSize: 11, marginBottom: 4 }}>
              <b style={{ color: T.accent }}>{r}:</b> <span style={{ color: T.muted }}>{a}</span>
            </div>
          ))}
        </>
      )}
    </div>
  )
}
