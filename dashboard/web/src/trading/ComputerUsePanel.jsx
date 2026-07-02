// ComputerUsePanel.jsx — the brain's COMPUTER-USE / GUI agent (Dark Pro UI).
// Honest view of the agent that SEES dashboards (own + Freqtrade/FreqUI), presses their
// buttons, experiments, reflects (Reflexion) and grows a Voyager-style skill library.
// Self-fetching like OnlineControlPanel: GETs /api/trading/gui/status?observe=1 every ~5s,
// and POSTs /api/trading/gui/action for {observe, step, practice, experiment}. PAPER-FIRST:
// step/practice run dry_run by default (the agent plans + learns without firing real actions).
import { useEffect, useRef, useState } from 'react'
import { T } from './theme.js'

const STATUS_URL = '/api/trading/gui/status?observe=1'
const ACTION_URL = '/api/trading/gui/action'

async function getJSON(url) {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json()
}

function pct(v) {
  const n = Number(v)
  return Number.isFinite(n) ? `${(n * 100).toFixed(0)}%` : '—'
}

function Cap({ on, label }) {
  return (
    <span style={{ fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 4,
      color: on ? T.good : T.muted, border: `1px solid ${on ? T.good : T.border}`,
      textTransform: 'uppercase', letterSpacing: 0.3, whiteSpace: 'nowrap' }}>
      {on ? '✓' : '○'} {label}
    </span>
  )
}

function Stat({ label, value, color }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <span style={{ fontSize: 10, color: T.muted, textTransform: 'uppercase', letterSpacing: 0.4 }}>{label}</span>
      <span style={{ fontSize: 15, fontWeight: 700, color: color || T.text }}>{value}</span>
    </div>
  )
}

function Btn({ children, onClick, color, disabled }) {
  const c = color || T.accent
  return (
    <button onClick={onClick} disabled={disabled} style={{
      background: T.panel2, color: disabled ? T.muted : c,
      border: `1px solid ${disabled ? T.border : c}`, borderRadius: 8, padding: '7px 12px',
      cursor: disabled ? 'not-allowed' : 'pointer', fontSize: 13, fontWeight: 600,
      opacity: disabled ? 0.6 : 1, whiteSpace: 'nowrap' }}>
      {children}
    </button>
  )
}

export default function ComputerUsePanel({ intervalMs = 5000 }) {
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)
  const [busy, setBusy] = useState(null)
  const [result, setResult] = useState(null)
  const alive = useRef(true)

  const refresh = async () => {
    try {
      const d = await getJSON(STATUS_URL)
      if (alive.current) { setData(d); setErr(null) }
    } catch (e) { if (alive.current) setErr(String(e.message || e)) }
  }

  useEffect(() => {
    alive.current = true; refresh()
    const t = setInterval(refresh, intervalMs)
    return () => { alive.current = false; clearInterval(t) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intervalMs])

  const act = async (body, key) => {
    setBusy(key)
    try {
      const r = await fetch(ACTION_URL, { method: 'POST',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      const d = await r.json()
      setResult({ ok: d.ok !== false, text: `${body.op} ${d.ok !== false ? '✓' : '✗ ' + (d.reason || d.error || '')}`, ts: new Date() })
    } catch (e) {
      setResult({ ok: false, text: `${body.op} failed: ${String(e.message || e)}`, ts: new Date() })
    } finally { setBusy(null); refresh() }
  }

  const wrap = { background: T.bg, border: `1px solid ${T.border}`, borderRadius: 12,
    padding: 14, color: T.text, fontFamily: 'system-ui, sans-serif', boxSizing: 'border-box', width: '100%' }

  if (!data) {
    return (<div style={wrap}><div style={{ color: T.muted, fontSize: 13, padding: '24px 0', textAlign: 'center' }}>
      <span style={{ fontSize: 22, opacity: 0.6 }}>🖥️</span>
      <div style={{ marginTop: 8 }}>{err ? `computer-use feed: ${err}` : 'loading computer-use agent…'}</div>
    </div></div>)
  }

  const pc = data.perception_capabilities || {}
  const ac = data.action_capabilities || {}
  const last = data.last_perception || {}
  const charts = (last.charts || [])
  const chart = charts[0] || null
  const skills = (data.skills && data.skills.skills) || []
  const refl = (data.reflections && data.reflections.recent) || []
  const targets = (data.targets && data.targets.targets) || []

  return (
    <div style={wrap}>
      {/* header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12, flexWrap: 'wrap' }}>
        <span style={{ fontWeight: 700, fontSize: 16 }}>🖥️ Computer-Use Agent</span>
        <span style={{ fontSize: 11, color: T.muted }}>sees · presses buttons · experiments · learns</span>
        <div style={{ flex: 1 }} />
        {result && <span style={{ fontSize: 11, fontWeight: 700, color: result.ok ? T.good : T.bad,
          border: `1px solid ${result.ok ? T.good : T.bad}`, borderRadius: 4, padding: '2px 8px' }}>{result.text}</span>}
        <span style={{ fontSize: 11, fontWeight: 700, color: ac.armed_for_live ? T.bad : T.muted,
          border: `1px solid ${ac.armed_for_live ? T.bad : T.border}`, borderRadius: 4, padding: '2px 8px' }}>
          {ac.armed_for_live ? '🔓 LIVE ARMED' : '🔒 paper-first'}
        </span>
      </div>

      {/* capabilities — honest what-it-can-do flags */}
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
        <Cap on={pc.api} label="see: api" />
        <Cap on={pc.html} label="see: controls" />
        <Cap on={pc.dom_playwright} label="dom click" />
        <Cap on={pc.ocr_paddle} label="chart ocr" />
        <Cap on={ac.in_process} label="act: in-process" />
        <Cap on={ac.http} label="act: http" />
      </div>

      {/* what the agent sees right now */}
      <div style={{ background: T.panel, border: `1px solid ${T.border}`, borderRadius: 10, padding: 12, marginBottom: 12 }}>
        <div style={{ fontSize: 10, color: T.muted, textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 8 }}>what it sees · own_dashboard</div>
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          <Stat label="reachable" value={last.reachable ? 'yes' : 'no'} color={last.reachable ? T.good : T.bad} />
          <Stat label="controls found" value={last.n_controls ?? '—'} color={T.text} />
          {chart && <Stat label={`${chart.symbol} ${chart.timeframe}`} value={chart.last} color={T.accent} />}
          {chart && <Stat label="trend" value={String(chart.trend).toUpperCase()}
            color={chart.trend === 'up' ? T.good : chart.trend === 'down' ? T.bad : T.muted} />}
          {chart && <Stat label="Δ%" value={chart.change_pct} color={chart.change_pct >= 0 ? T.good : T.bad} />}
          {last.deep && <Stat label="ocr items" value={(last.ocr && last.ocr.n) ?? 0} color={T.accent} />}
        </div>
        {last.deep && last.ocr && last.ocr.numbers && last.ocr.numbers.length > 0 && (
          <div style={{ marginTop: 8, fontSize: 11, color: T.muted }}>
            chart-pixel OCR read: {last.ocr.numbers.slice(0, 12).join(' · ')}
          </div>
        )}
      </div>

      {/* drive the agent (paper/dry by default) */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
        <Btn onClick={() => act({ op: 'observe', target: 'own_dashboard' }, 'observe')} disabled={!!busy} color={T.accent}>👁 Observe</Btn>
        <Btn onClick={() => act({ op: 'observe', target: 'own_dashboard', deep: true }, 'deep')} disabled={!!busy || !pc.dom_playwright} color={T.accent}>🔬 Deep See (DOM+OCR)</Btn>
        <Btn onClick={() => act({ op: 'step', goal: 'pause crypto', dry_run: true }, 'step')} disabled={!!busy} color={T.warn}>▷ Step (dry)</Btn>
        <Btn onClick={() => act({ op: 'practice', rounds: 2 }, 'practice')} disabled={!!busy} color={T.good}>🏋 Practice ×2</Btn>
        <Btn onClick={() => act({ op: 'experiment' }, 'experiment')} disabled={!!busy} color={T.accent}>🔬 Experiment</Btn>
      </div>

      {/* skill library — Voyager-pattern, with empirical success */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 12 }}>
        <div style={{ background: T.panel, border: `1px solid ${T.border}`, borderRadius: 10, padding: 12 }}>
          <div style={{ fontSize: 10, color: T.muted, textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 8 }}>
            skill library · {data.skills?.n_practiced ?? 0}/{data.skills?.n_skills ?? 0} practiced
          </div>
          {skills.slice(0, 8).map((s) => (
            <div key={s.name} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0', borderBottom: `1px solid ${T.gridline}` }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: T.text, flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={s.description}>{s.name}</span>
              <span style={{ fontSize: 11, color: T.muted }}>×{s.n_used}</span>
              <span style={{ fontSize: 11, fontWeight: 700, color: s.n_used ? (s.success_rate >= 0.5 ? T.good : T.bad) : T.muted }}>{s.n_used ? pct(s.success_rate) : '—'}</span>
            </div>
          ))}
        </div>

        {/* reflections — Reflexion lessons */}
        <div style={{ background: T.panel, border: `1px solid ${T.border}`, borderRadius: 10, padding: 12 }}>
          <div style={{ fontSize: 10, color: T.muted, textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 8 }}>
            reflections · {data.reflections?.n_failures ?? 0} failures / {data.reflections?.n_lessons ?? 0} lessons
          </div>
          {refl.length === 0 && <span style={{ fontSize: 12, color: T.muted }}>no lessons yet — run a step</span>}
          {refl.slice().reverse().slice(0, 6).map((l, i) => (
            <div key={i} style={{ padding: '4px 0', borderBottom: `1px solid ${T.gridline}` }}>
              <span style={{ fontSize: 11, fontWeight: 700, color: l.outcome === 'success' ? T.good : T.bad }}>{l.outcome === 'success' ? '✓' : '✗'} </span>
              <span style={{ fontSize: 11, color: T.text }}>{l.lesson}</span>
            </div>
          ))}
        </div>
      </div>

      {/* operable targets */}
      <div style={{ marginTop: 12, display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        <span style={{ fontSize: 10, color: T.muted, textTransform: 'uppercase', letterSpacing: 0.5 }}>operates:</span>
        {targets.map((t) => (
          <a key={t.name} href={t.web_url} target="_blank" rel="noopener noreferrer"
            style={{ fontSize: 11, fontWeight: 600, color: T.accent, textDecoration: 'none',
              border: `1px solid ${T.border}`, borderRadius: 12, padding: '3px 10px' }} title={t.note}>
            ⤴ {t.name}
          </a>
        ))}
      </div>

      <div style={{ fontSize: 11, color: T.muted, borderTop: `1px solid ${T.gridline}`, marginTop: 12, paddingTop: 8 }}>
        ℹ {data.note}
      </div>
    </div>
  )
}
