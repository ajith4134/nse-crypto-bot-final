// SchoolPanel.jsx — "🎓 The School + Self-Evaluation" (Brain Ultra Upgrade Pillars 3+5,
// R2/R21/R27 + R3/R22/R23/R28). Dual-track curriculum L0→L6 (Track A: intelligence
// itself — recall/connect/APPLY; Track B: the domain), real exams graded held-out via
// POST /api/brain/school/exam, and the standing self-evaluation report
// (/api/brain/selfeval): genius-use on ALL the things, LLM-parity, accumulation,
// agentic time horizon, independent-learning runs. All numbers come from disk truth.
import { useEffect, useState } from 'react'
import { T } from './theme.js'

async function getJSON(url) {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json()
}
async function postJSON(url, body) {
  const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' },
                               body: JSON.stringify(body || {}) })
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json()
}

function scoreCol(v) {
  if (v == null) return T.muted
  return v >= 0.7 ? T.good : v >= 0.4 ? T.warn : T.bad
}
function pct(v, d = 0) { return v == null ? '—' : `${(v * 100).toFixed(d)}%` }

function Tile({ label, value, sub, color }) {
  return (
    <div style={{ border: `1px solid ${T.border}`, borderRadius: 8, padding: '8px 10px', minWidth: 0 }}>
      <div style={{ fontSize: 10, color: T.muted }}>{label}</div>
      <div style={{ fontSize: 16, fontWeight: 800, color: color || T.text }}>{value}</div>
      {sub && <div style={{ fontSize: 10, color: T.muted, marginTop: 2 }}>{sub}</div>}
    </div>
  )
}

function Curriculum({ school, onExam, busy, lastExam }) {
  const levels = Object.entries(school?.curriculum || {})
  const current = school?.level || 'L0'
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
      {levels.map(([lvl, c]) => {
        const reached = lvl.localeCompare(current) <= 0
        const isCurrent = lvl === current
        const r = lastExam && lastExam.level === lvl ? lastExam : null
        return (
          <div key={lvl} style={{ display: 'flex', alignItems: 'center', gap: 8,
                border: `1px solid ${isCurrent ? T.accent : T.border}`, borderRadius: 8,
                padding: '6px 9px', opacity: reached || isCurrent ? 1 : 0.55 }}>
            <span style={{ fontSize: 12, fontWeight: 800, width: 26,
                           color: isCurrent ? T.accent : reached ? T.good : T.muted }}>{lvl}</span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 12, fontWeight: 600 }}>{c.name}</div>
              <div style={{ fontSize: 10, color: T.muted }}>{c.goal}</div>
              {r && (
                <div style={{ fontSize: 10, marginTop: 2 }}>
                  <span style={{ color: scoreCol(r.track_a?.score) }}>A(intelligence) {pct(r.track_a?.score)}</span>
                  {' · '}
                  <span style={{ color: scoreCol(r.track_b?.score) }}>B(domain) {pct(r.track_b?.score)}</span>
                  {' · '}
                  <span style={{ color: r.passed ? T.good : T.bad, fontWeight: 700 }}>
                    {r.passed ? 'PASSED → promoted' : r.track_a?.note || 'not passed'}</span>
                </div>
              )}
            </div>
            <button disabled={busy} onClick={() => onExam(lvl)}
              style={{ fontSize: 11, padding: '3px 10px', cursor: busy ? 'wait' : 'pointer',
                       background: '#1b2433', color: '#4cc2ff',
                       border: `1px solid ${T.border}`, borderRadius: 6 }}>
              {busy === lvl ? 'examining…' : 'exam'}
            </button>
          </div>
        )
      })}
    </div>
  )
}

function Spark({ vals, w = 84, h = 18, color = '#4cc2ff' }) {
  const nums = vals.filter((v) => v != null)
  if (nums.length < 2) return <span style={{ color: T.muted, fontSize: 10 }}>—</span>
  const min = Math.min(...nums), max = Math.max(...nums), span = max - min || 1
  const pts = nums.map((v, i) =>
    `${(i / (nums.length - 1)) * w},${h - ((v - min) / span) * (h - 2) - 1}`).join(' ')
  return (
    <svg width={w} height={h} style={{ verticalAlign: 'middle' }}>
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" />
    </svg>
  )
}

function TrendRow({ history }) {
  const first = history[0], last = history[history.length - 1]
  const dUse = (last.knowledge_use_rate ?? 0) - (first.knowledge_use_rate ?? 0)
  const dNeur = (last.neurons ?? 0) - (first.neurons ?? 0)
  return (
    <div style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap', fontSize: 10,
                  color: T.muted, border: `1px solid ${T.border}`, borderRadius: 8, padding: 8 }}>
      <span style={{ fontWeight: 700, color: T.text }}>trend · {history.length} pts (R23/R28)</span>
      <span>genius-use <Spark vals={history.map((h) => h.knowledge_use_rate)}
            color={dUse >= 0 ? T.good : T.warn} /> {dUse >= 0 ? '▲' : '▼'}{pct(Math.abs(dUse), 2)}</span>
      <span>neurons <Spark vals={history.map((h) => h.neurons)} color={T.accent} /> {dNeur >= 0 ? '+' : ''}{dNeur}</span>
      {last.parity_brain != null &&
        <span>parity <Spark vals={history.map((h) => h.parity_brain)} color={T.good} /> {last.parity_brain}v{last.parity_llm ?? '—'}</span>}
    </div>
  )
}

function SelfEval({ ev, onRun, running }) {
  const [topic, setTopic] = useState('')
  const gu = ev?.genius_use
  const th = ev?.time_horizon
  const lp = ev?.llm_parity
  const il = ev?.independent_learning
  const acc = ev?.accumulation
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0,1fr))', gap: 8 }}>
        <Tile label="genius-use (all the things, R22)" value={pct(gu?.knowledge_use_rate, 2)}
              sub={`${gu?.neurons_ever_used ?? 0}/${gu?.neurons_total ?? 0} neurons ever used · domains: ${Object.keys(gu?.by_domain || {}).join(', ') || 'none yet'}`}
              color={scoreCol(gu?.knowledge_use_rate)} />
        <Tile label="agentic time horizon" value={th?.ok ? `${Math.round((th.current_run_secs || 0) / 60)}m` : '—'}
              sub={th?.ok ? `longest run ${Math.round(th.longest_run_secs / 60)}m · last event ${th.last_event_age_secs}s ago` : th?.note}
              color={th?.current_run_secs > 0 ? T.good : T.warn} />
        <Tile label="LLM parity (R23)" value={lp?.ok ? `${lp.brain_score} vs ${lp.llm_score ?? '—'}` : 'not run'}
              sub={lp?.ok ? (lp.parity === true ? 'brain ≥ raw LLM on home domain' : lp.parity === false ? 'raw LLM ahead — keep studying' : lp.note) : 'run it →'}
              color={lp?.parity === true ? T.good : lp?.parity === false ? T.warn : T.muted} />
        <Tile label="accumulation (R28)" value={acc ? `${acc.neurons_last7d} new/7d` : '—'}
              sub={acc ? `${acc.growing ? 'growing' : 'STALLED'} · decayed levels: ${Object.entries(acc.exam_trends || {}).filter(([, t]) => t.decayed).map(([l]) => l).join(', ') || 'none'}` : ''}
              color={acc?.growing ? T.good : T.warn} />
      </div>
      {ev?.apply_lift && (() => {
        const al = ev.apply_lift
        const lift = al.lift
        return (
          <div style={{ display: 'flex', gap: 14, alignItems: 'center', flexWrap: 'wrap', fontSize: 10,
                        color: T.muted, border: `1px solid ${T.border}`, borderRadius: 8, padding: 8 }}>
            <span style={{ fontWeight: 700, color: T.text }}>
              applied-instruction lift {al.tilt_enabled ? '(tilt ON)' : '(attribution only)'}
            </span>
            <span>baseline {pct(al.baseline_win_rate)}</span>
            <span>applied {al.applied?.n
              ? <><b style={{ color: T.text }}>{pct(al.applied.win_rate)}</b> (n={al.applied.n})</>
              : <span style={{ color: T.muted }}>no applied trades yet</span>}</span>
            {lift != null && <span style={{ color: lift >= 0 ? T.good : T.warn, fontWeight: 800 }}>
              {lift >= 0 ? '▲' : '▼'}{pct(Math.abs(lift))} lift</span>}
            {al.applied_high_conf?.n > 0 &&
              <span>hi-conf {pct(al.applied_high_conf.win_rate)} (n={al.applied_high_conf.n})</span>}
          </div>
        )
      })()}
      {ev?.history?.length > 1 && <TrendRow history={ev.history} />}
      {il && (
        <div style={{ fontSize: 11, border: `1px solid ${T.border}`, borderRadius: 8, padding: 8 }}>
          <span style={{ fontWeight: 700 }}>last independent-learning test (R3): </span>
          {il.ok
            ? <span>topic “{il.topic}” → {il.neurons_created} neurons + 1 instruction, quiz {pct(il.quiz_score)} in {il.secs}s</span>
            : <span style={{ color: T.warn }}>{il.topic}: {il.note}</span>}
        </div>
      )}
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
        <input value={topic} onChange={(e) => setTopic(e.target.value)}
               placeholder="unknown topic for independent-learning test…"
               style={{ flex: 1, minWidth: 180, background: '#0b0f16', color: T.text,
                        border: `1px solid ${T.border}`, borderRadius: 6,
                        padding: '5px 8px', fontSize: 11 }} />
        <button disabled={running || !topic.trim()}
                onClick={() => onRun('independent_learning', topic.trim())}
                style={{ fontSize: 11, padding: '4px 10px', cursor: 'pointer',
                         background: '#1b2433', color: '#4cc2ff',
                         border: `1px solid ${T.border}`, borderRadius: 6 }}>
          learn unaided (R3)
        </button>
        <button disabled={running} onClick={() => onRun('llm_parity')}
                style={{ fontSize: 11, padding: '4px 10px', cursor: 'pointer',
                         background: '#1b2433', color: '#ffd166',
                         border: `1px solid ${T.border}`, borderRadius: 6 }}>
          run LLM-parity (R23)
        </button>
        {running && <span style={{ fontSize: 10, color: T.muted }}>started — lands here when done</span>}
      </div>
    </div>
  )
}

export default function SchoolPanel({ intervalMs = 20000 }) {
  const [state, setState] = useState({ loading: true })
  const [busy, setBusy] = useState(null)
  const [running, setRunning] = useState(false)
  const [lastExam, setLastExam] = useState(null)

  const refresh = async () => {
    const [ov, ev] = await Promise.all([
      getJSON('/api/brain/neurons'), getJSON('/api/brain/selfeval')])
    setState({ school: ov.school, pareto: ov.pareto, instructions: ov.instructions,
               selfeval: ev, stamp: new Date() })
  }
  useEffect(() => {
    let alive = true
    const tick = () => refresh().catch((e) => alive && setState({ error: String(e.message || e) }))
    tick()
    const t = setInterval(tick, intervalMs)
    return () => { alive = false; clearInterval(t) }
  }, [intervalMs])

  const onExam = async (level) => {
    setBusy(level)
    try { setLastExam(await postJSON('/api/brain/school/exam', { level })); await refresh() }
    catch (e) { setLastExam({ level, error: String(e) }) }
    finally { setBusy(null) }
  }
  const onRun = async (test, topic) => {
    setRunning(true)
    try { await postJSON('/api/brain/selfeval/run', { test, topic }) }
    finally { setTimeout(() => { setRunning(false); refresh().catch(() => {}) }, 25000) }
  }

  const wrap = { background: T.bg, border: `1px solid ${T.border}`, borderRadius: 12,
                 padding: 14, color: T.text, fontFamily: 'system-ui, sans-serif' }
  if (state.loading) return <div style={wrap}><div style={{ color: T.muted, fontSize: 13 }}>🎓 loading the school…</div></div>
  if (state.error) return <div style={wrap}><div style={{ color: T.muted, fontSize: 12 }}>school unavailable: {state.error}</div></div>
  if (!state.school) {
    return <div style={wrap}><div style={{ color: T.muted, fontSize: 12 }}>
      🎓 The School — snapshot warming (serial background init after restart); exam history is on disk and appears here shortly.</div></div>
  }

  const school = state.school || {}
  return (
    <div style={wrap}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 10, flexWrap: 'wrap' }}>
        <span style={{ fontWeight: 700, fontSize: 16 }}>🎓 The School</span>
        <span style={{ fontSize: 12, fontWeight: 800, color: T.accent }}>
          level {school.level} · {school.level_name}</span>
        <span style={{ fontSize: 10, color: T.muted }}>
          dual track: A = intelligence itself (R21) · B = the domain · pass ≥ {pct(school.pass_score)} both · {school.exams_taken ?? 0} exams taken</span>
        <div style={{ flex: 1 }} />
        {state.stamp && <span style={{ fontSize: 10, color: T.muted }}>updated {state.stamp.toLocaleTimeString()}</span>}
      </div>
      {lastExam && (lastExam.error || lastExam.ok === false) && (
        <div style={{ fontSize: 11, color: T.warn, border: `1px solid ${T.warn}`,
                      borderRadius: 6, padding: '4px 8px', marginBottom: 8 }}>
          exam failed: {lastExam.error || 'see server log'}
        </div>
      )}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)', gap: 12 }}>
        <Curriculum school={school} onExam={onExam} busy={busy} lastExam={lastExam} />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, minWidth: 0 }}>
          <SelfEval ev={state.selfeval} onRun={onRun} running={running} />
          <div>
            <div style={{ fontSize: 11, color: T.muted, marginBottom: 4 }}>
              instruction Pareto archive (diverse working variants, R26) · {state.instructions?.retired ?? 0} retired
            </div>
            {(state.pareto || []).slice(0, 6).map((p) => (
              <div key={p.id} style={{ display: 'flex', gap: 8, fontSize: 11, padding: '3px 0',
                                       borderBottom: `1px solid ${T.gridline || '#141b28'}` }}>
                <span style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis',
                               whiteSpace: 'nowrap' }}>{p.title}</span>
                <span style={{ color: T.muted }}>v{p.version}</span>
                <span style={{ color: scoreCol(p.confidence) }}>conf {Number(p.confidence).toFixed(2)}</span>
                <span style={{ color: T.muted }}>{p.wins}W/{p.losses}L</span>
              </div>
            ))}
            {!(state.pareto || []).length && (
              <div style={{ fontSize: 11, color: T.muted }}>no instructions evolved yet — they appear as the brain follows/grades/mutates them</div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
