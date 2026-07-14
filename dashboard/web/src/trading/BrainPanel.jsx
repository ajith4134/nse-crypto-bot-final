// BrainPanel.jsx — Phase T8.9 (Dark Pro UI)
// Self-contained "🧬 AI Brain" panel surfacing the T8 backend endpoints in the
// trading dashboard. Unlike the T6 presentational components, this panel owns its
// own fetching: on mount it polls every /api/trading/*/status endpoint in parallel
// (per-endpoint try/catch so one 404/error never blanks the whole panel) every ~5s
// and cleans up on unmount. Inline-styled via ./theme.js, no styles.css dependency.
// No external chart libs — sparklines are hand-rolled inline SVG.
import { useEffect, useRef, useState } from 'react'
import { T, pnlColor, scoreColor } from './theme.js'

// The eight T8 status endpoints. Each returns JSON {...; demo:true; note}; some may
// 404 / error if the backend slice is not present yet — we degrade gracefully.
const ENDPOINTS = {
  strategy: '/api/trading/strategy/status',
  evolution: '/api/trading/evolution/status',
  experience: '/api/trading/experience/status',
  selfeval: '/api/trading/selfeval/status',
  patterns: '/api/trading/patterns/status',
  news: '/api/trading/news/status',
  skills: '/api/trading/skills/status',
  brain: '/api/trading/brain/status',
}

async function getJSON(url) {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json()
}

// ---- small helpers ------------------------------------------------------------

function num(v) {
  if (v == null) return null
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? n : null
}

function pct(v, digits = 0) {
  const n = num(v)
  if (n == null) return '—'
  return `${(n <= 1 && n >= -1 ? n * 100 : n).toFixed(digits)}%`
}

function fmt(v, digits = 2) {
  const n = num(v)
  if (n == null) return '—'
  return n.toFixed(digits)
}

// Colour an action verb (LONG/BUY green, SHORT/SELL red, FLAT/HOLD muted).
function actionColor(a) {
  const s = String(a || '').toUpperCase()
  if (/(LONG|BUY|UP|BULL)/.test(s)) return T.good
  if (/(SHORT|SELL|DOWN|BEAR)/.test(s)) return T.bad
  return T.muted
}

// Extract an array of numbers from a variety of possible shapes (array of numbers,
// array of objects with a numeric field, etc.).
function toSeries(arr, ...keys) {
  if (!Array.isArray(arr)) return []
  return arr
    .map((d) => {
      if (typeof d === 'number') return d
      if (d && typeof d === 'object') {
        for (const k of keys) {
          const n = num(d[k])
          if (n != null) return n
        }
      }
      return num(d)
    })
    .filter((n) => n != null)
}

// ---- inline SVG sparkline -----------------------------------------------------

function Sparkline({ values, color = T.accent, w = 160, h = 36 }) {
  const data = Array.isArray(values) ? values.filter((v) => v != null && Number.isFinite(v)) : []
  if (data.length < 2) {
    return (
      <div style={{ width: w, height: h, display: 'flex', alignItems: 'center', color: T.muted, fontSize: 10 }}>
        no series
      </div>
    )
  }
  const min = Math.min(...data)
  const max = Math.max(...data)
  const span = max - min || 1
  const pad = 2
  const stepX = (w - pad * 2) / (data.length - 1)
  const y = (v) => h - pad - ((v - min) / span) * (h - pad * 2)
  const pts = data.map((v, i) => `${(pad + i * stepX).toFixed(1)},${y(v).toFixed(1)}`)
  const last = data[data.length - 1]
  const lastX = pad + (data.length - 1) * stepX
  const area = `M ${pts[0]} L ${pts.join(' L ')} L ${lastX.toFixed(1)},${h - pad} L ${pad},${h - pad} Z`
  return (
    <svg width={w} height={h} style={{ display: 'block' }}>
      <path d={area} fill={color} opacity={0.12} />
      <polyline points={pts.join(' ')} fill="none" stroke={color} strokeWidth={1.5} strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={lastX} cy={y(last)} r={2.5} fill={color} />
    </svg>
  )
}

// ---- presentational primitives ------------------------------------------------

function Card({ title, hint, children, span }) {
  return (
    <div
      style={{
        background: T.panel,
        border: `1px solid ${T.border}`,
        borderRadius: 10,
        padding: 12,
        gridColumn: span ? `span ${span}` : undefined,
        boxSizing: 'border-box',
        minWidth: 0,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 10 }}>
        <span style={{ fontWeight: 600, fontSize: 13, color: T.text, letterSpacing: 0.3 }}>{title}</span>
        {hint && <span style={{ color: T.muted, fontSize: 11 }}>{hint}</span>}
      </div>
      {children}
    </div>
  )
}

function Badge({ text, color }) {
  return (
    <span
      style={{
        fontSize: 10,
        fontWeight: 700,
        letterSpacing: 0.5,
        color,
        border: `1px solid ${color}`,
        borderRadius: 4,
        padding: '1px 6px',
        textTransform: 'uppercase',
        whiteSpace: 'nowrap',
      }}
    >
      {text}
    </span>
  )
}

function Stat({ label, value, color }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <span style={{ fontSize: 10, color: T.muted, textTransform: 'uppercase', letterSpacing: 0.4 }}>{label}</span>
      <span style={{ fontSize: 16, fontWeight: 700, color: color || T.text }}>{value}</span>
    </div>
  )
}

function Empty({ note }) {
  return <div style={{ color: T.muted, fontSize: 12, padding: '6px 0' }}>{note || 'no data'}</div>
}

// ---- per-card renderers -------------------------------------------------------

function DecisionRow({ label, d }) {
  if (!d || typeof d !== 'object') return null
  const action = d.action || d.signal || d.side || d.decision || '—'
  const conf = num(d.confidence ?? d.conf ?? d.score)
  const regime = d.regime || d.market_regime
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 0', borderTop: `1px solid ${T.gridline}` }}>
      <span style={{ width: 56, fontSize: 11, color: T.muted, textTransform: 'uppercase', letterSpacing: 0.4 }}>{label}</span>
      <span style={{ fontWeight: 700, fontSize: 14, color: actionColor(action), minWidth: 64 }}>
        {String(action).toUpperCase()}
      </span>
      <span style={{ fontSize: 12, color: scoreColor(conf), fontWeight: 600 }}>
        {conf != null ? `conf ${pct(conf)}` : ''}
      </span>
      {regime && <span style={{ fontSize: 11, color: T.muted }}>· {regime}</span>}
    </div>
  )
}

function DecisionCard({ brain }) {
  if (brain.error || !brain.data) return <Card title="🎯 End-to-End Decision"><Empty note={brain.error || 'no decision'} /></Card>
  const d = brain.data
  const safety = d.safety || {}
  // safety may be {clear:true} / {blocked:true,reason} / a string
  let blocked = false
  let reason = ''
  if (typeof safety === 'string') {
    blocked = /block|halt|reject|stop/i.test(safety)
    reason = safety
  } else {
    blocked = safety.blocked === true || safety.clear === false || safety.passed === false || !!safety.reason
    reason = safety.reason || safety.message || ''
  }
  const safetyColor = blocked ? T.bad : T.good
  const safetyText = blocked ? `BLOCKED${reason ? ': ' + reason : ''}` : 'clear'
  return (
    <Card title="🎯 End-to-End Decision" span={2}>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 4 }}>
        <Badge text={safetyText} color={safetyColor} />
      </div>
      <DecisionRow label="crypto" d={d.crypto} />
      <DecisionRow label="nse" d={d.nse} />
    </Card>
  )
}

function StreamCard({ brain, skills }) {
  // Prefer brain.stream_of_mind, fall back to skills.stream_of_mind.
  let steps = []
  if (brain.data && Array.isArray(brain.data.stream_of_mind)) steps = brain.data.stream_of_mind
  else if (skills.data && Array.isArray(skills.data.stream_of_mind)) steps = skills.data.stream_of_mind
  const items = steps.slice().reverse() // newest first
  return (
    <Card title="🧠 Stream of Mind" hint={`${steps.length} steps`} span={2}>
      {items.length === 0 ? (
        <Empty note="no reasoning trace" />
      ) : (
        <div
          style={{
            maxHeight: 180,
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
            gap: 4,
            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
            fontSize: 11,
          }}
        >
          {items.map((s, i) => {
            const text = typeof s === 'string' ? s : (s.text || s.thought || s.message || JSON.stringify(s))
            return (
              <div key={i} style={{ color: i === 0 ? T.text : T.muted, lineHeight: 1.4 }}>
                <span style={{ color: T.accent }}>›</span> {text}
              </div>
            )
          })}
        </div>
      )}
    </Card>
  )
}

function EvolutionCard({ evolution }) {
  if (evolution.error || !evolution.data) return <Card title="🧬 Evolution"><Empty note={evolution.error || 'no data'} /></Card>
  const d = evolution.data
  const series = toSeries(d.history, 'best', 'best_score', 'fitness', 'score', 'fitness_score')
  return (
    <Card title="🧬 Evolution" hint="generation best score">
      <Sparkline values={series} color={T.good} w={180} h={40} />
      <div style={{ display: 'flex', gap: 16, marginTop: 10 }}>
        <Stat label="pareto" value={d.pareto_size != null ? d.pareto_size : '—'} />
        <Stat label="promoted" value={d.n_promoted != null ? d.n_promoted : '—'} color={T.accent} />
        <Stat label="best" value={fmt(d.best?.fitness_score ?? d.best?.score ?? d.best, 3)} color={T.good} />
      </div>
    </Card>
  )
}

function AutoQuizCard({ selfeval }) {
  if (selfeval.error || !selfeval.data) return <Card title="📈 Auto-Quiz"><Empty note={selfeval.error || 'no data'} /></Card>
  const d = selfeval.data
  const q = d.autoquiz || {}
  const curve = toSeries(q.curve, 'accuracy', 'acc', 'value')
  const rising = q.rising === true
  return (
    <Card title="📈 Auto-Quiz" hint="self-evaluation accuracy">
      <Sparkline values={curve} color={rising ? T.good : T.warn} w={180} h={40} />
      <div style={{ display: 'flex', gap: 16, marginTop: 10, flexWrap: 'wrap' }}>
        <Stat label="final acc" value={pct(q.final_accuracy)} color={scoreColor(num(q.final_accuracy))} />
        <Stat label="slope" value={fmt(q.slope, 3)} color={pnlColor(num(q.slope))} />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <span style={{ fontSize: 10, color: T.muted, textTransform: 'uppercase', letterSpacing: 0.4 }}>rising</span>
          <Badge text={rising ? '✓ yes' : '✗ no'} color={rising ? T.good : T.bad} />
        </div>
        <Stat label="drift evts" value={Array.isArray(d.drift_events) ? d.drift_events.length : (d.drift_events ?? '—')} color={T.warn} />
        <Stat label="few-shot gain" value={fmt(d.meta?.few_shot_gain, 3)} color={pnlColor(num(d.meta?.few_shot_gain))} />
      </div>
    </Card>
  )
}

function ExperienceCard({ experience }) {
  if (experience.error || !experience.data) return <Card title="🗂 Experience"><Empty note={experience.error || 'no data'} /></Card>
  const e = experience.data.experience || {}
  const recall = experience.data.sample_recall || {}
  return (
    <Card title="🗂 Experience" hint="replay memory">
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        <Stat label="cases" value={e.n_cases != null ? e.n_cases : '—'} color={T.accent} />
        <Stat label="recall bias" value={fmt(recall.bias, 3)} color={pnlColor(num(recall.bias))} />
        <Stat label="exp. win rate" value={pct(recall.expected_win_rate)} color={scoreColor(num(recall.expected_win_rate))} />
      </div>
    </Card>
  )
}

function PatternsCard({ patterns }) {
  if (patterns.error || !patterns.data) return <Card title="🔍 Regime & Patterns"><Empty note={patterns.error || 'no data'} /></Card>
  const d = patterns.data
  // regime may arrive as a string or an object ({current,label,regime,state,...}); never
  // stringify a raw object (that produced "[object Object]") — pick the first label-ish field.
  const _rg = d.regime
  const regime = (_rg && typeof _rg === 'object')
    ? (_rg.current || _rg.label || _rg.regime || _rg.state || '—')
    : (_rg || '—')
  const picking = d.picking || {}
  const top = Array.isArray(picking.top) ? picking.top : []
  return (
    <Card title="🔍 Regime & Patterns" hint="asset picking">
      <div style={{ display: 'flex', gap: 16, marginBottom: 8, flexWrap: 'wrap' }}>
        <Stat label="regime" value={String(regime)} color={T.accent} />
        <Stat label="factor src" value={picking.factor_source || '—'} />
      </div>
      {top.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {top.map((p, i) => {
            const sym = typeof p === 'string' ? p : (p.symbol || p.name || p.ticker || JSON.stringify(p))
            return <Badge key={i} text={sym} color={T.warn} />
          })}
        </div>
      )}
    </Card>
  )
}

function NewsCard({ news }) {
  if (news.error || !news.data) return <Card title="📰 News Sentiment"><Empty note={news.error || 'no data'} /></Card>
  const d = news.data
  const research = d.research || {}
  const symbols = Object.keys(research)
  return (
    <Card title="📰 News Sentiment" hint={d.scorer_backend ? `backend: ${d.scorer_backend}` : undefined}>
      {symbols.length === 0 ? (
        <Empty note="no research" />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {symbols.map((sym) => {
            const r = research[sym] || {}
            const s = num(r.avg_sentiment ?? r.sentiment ?? r.score ?? r)
            return (
              <div key={sym} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ fontWeight: 700, fontSize: 12, color: T.text, minWidth: 72 }}>{sym}</span>
                <span style={{ fontSize: 13, fontWeight: 600, color: pnlColor(s) }}>
                  {s != null ? (s > 0 ? '▲ ' : s < 0 ? '▼ ' : '') + fmt(s, 3) : '—'}
                </span>
              </div>
            )
          })}
        </div>
      )}
    </Card>
  )
}

function SkillsCard({ skills }) {
  if (skills.error || !skills.data) return <Card title="🛠 Skill Library"><Empty note={skills.error || 'no data'} /></Card>
  const d = skills.data
  const lib = d.skills || {}
  const top = Array.isArray(lib.top) ? lib.top : []
  const si = d.self_improve || {}
  const dspy = d.dspy || {}
  const dspyOn = dspy === true || dspy.enabled === true || dspy.status === 'on' || dspy.active === true
  return (
    <Card title="🛠 Skill Library" hint="self-improvement" span={2}>
      <div style={{ display: 'flex', gap: 16, marginBottom: 10, flexWrap: 'wrap', alignItems: 'flex-start' }}>
        <Stat label="skills" value={lib.n_skills != null ? lib.n_skills : '—'} color={T.accent} />
        <Stat
          label="self-improve"
          value={`${fmt(si.start ?? si.start_score, 3)} → ${fmt(si.best ?? si.best_score, 3)}`}
          color={T.good}
        />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <span style={{ fontSize: 10, color: T.muted, textTransform: 'uppercase', letterSpacing: 0.4 }}>dspy</span>
          <Badge text={dspyOn ? 'on' : 'off'} color={dspyOn ? T.good : T.muted} />
        </div>
      </div>
      {top.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {top.map((s, i) => {
            const name = typeof s === 'string' ? s : (s.name || s.skill || `skill ${i}`)
            const metric = typeof s === 'object' ? num(s.metric ?? s.score ?? s.value) : null
            return (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
                <span style={{ color: T.accent }}>•</span>
                <span style={{ color: T.text, flex: 1 }}>{name}</span>
                {metric != null && <span style={{ color: scoreColor(metric), fontWeight: 600 }}>{fmt(metric, 3)}</span>}
              </div>
            )
          })}
        </div>
      )}
    </Card>
  )
}

function StrategyCard({ strategy }) {
  if (strategy.error || !strategy.data) return <Card title="⚙️ Strategy Population"><Empty note={strategy.error || 'no data'} /></Card>
  const d = strategy.data
  const pop = Array.isArray(d.population) ? d.population : []
  const passed = d.guardrail_passed === true
  const pbo = num(d.guardrails?.pbo)
  const best = pop.reduce((m, p) => Math.max(m, num(p.fitness_score) ?? -Infinity), -Infinity)
  return (
    <Card title="⚙️ Strategy Population" hint={`${pop.length} candidates`}>
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'flex-start' }}>
        <Stat label="best fitness" value={Number.isFinite(best) ? best.toFixed(3) : '—'} color={T.good} />
        <Stat label="pbo" value={pbo != null ? fmt(pbo, 3) : '—'} color={pbo != null ? scoreColor(1 - pbo) : T.text} />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <span style={{ fontSize: 10, color: T.muted, textTransform: 'uppercase', letterSpacing: 0.4 }}>guardrail</span>
          <Badge text={passed ? 'passed' : 'failed'} color={passed ? T.good : T.bad} />
        </div>
      </div>
    </Card>
  )
}

// ---- main panel ---------------------------------------------------------------

export default function BrainPanel({ intervalMs = 5000 }) {
  // Each key holds {data} on success or {error} on failure — never blanks siblings.
  const [state, setState] = useState({})
  const [loading, setLoading] = useState(true)
  const [stamp, setStamp] = useState(null)

  useEffect(() => {
    let alive = true
    const tick = async () => {
      const entries = await Promise.all(
        Object.entries(ENDPOINTS).map(async ([k, url]) => {
          try {
            return [k, { data: await getJSON(url) }]
          } catch (e) {
            return [k, { error: String(e.message || e) }]
          }
        })
      )
      if (!alive) return
      setState(Object.fromEntries(entries))
      setLoading(false)
      setStamp(new Date())
    }
    tick()
    const timer = setInterval(tick, intervalMs)
    return () => {
      alive = false
      clearInterval(timer)
    }
  }, [intervalMs])

  const g = (k) => state[k] || {}

  const wrap = {
    background: T.bg,
    border: `1px solid ${T.border}`,
    borderRadius: 12,
    padding: 14,
    color: T.text,
    fontFamily: 'system-ui, sans-serif',
    boxSizing: 'border-box',
    width: '100%',
  }

  if (loading) {
    return (
      <div style={wrap}>
        <div style={{ color: T.muted, fontSize: 13, padding: '24px 0', textAlign: 'center' }}>
          <span style={{ fontSize: 22, opacity: 0.6 }}>🧬</span>
          <div style={{ marginTop: 8 }}>loading AI Brain…</div>
        </div>
      </div>
    )
  }

  const errCount = Object.values(state).filter((v) => v && v.error).length
  const liveCount = Object.keys(ENDPOINTS).length - errCount

  return (
    <div style={wrap}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 12 }}>
        <span style={{ fontWeight: 700, fontSize: 16, color: T.text }}>🧬 AI Brain</span>
        <span style={{ fontSize: 11, color: T.muted }}>Phase T8 · {liveCount}/{Object.keys(ENDPOINTS).length} feeds live</span>
        <div style={{ flex: 1 }} />
        {stamp && <span style={{ fontSize: 10, color: T.muted }}>updated {stamp.toLocaleTimeString()}</span>}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 12 }}>
        <DecisionCard brain={g('brain')} />
        <StreamCard brain={g('brain')} skills={g('skills')} />
        <EvolutionCard evolution={g('evolution')} />
        <AutoQuizCard selfeval={g('selfeval')} />
        <ExperienceCard experience={g('experience')} />
        <PatternsCard patterns={g('patterns')} />
        <NewsCard news={g('news')} />
        <StrategyCard strategy={g('strategy')} />
        <SkillsCard skills={g('skills')} />
      </div>
    </div>
  )
}
