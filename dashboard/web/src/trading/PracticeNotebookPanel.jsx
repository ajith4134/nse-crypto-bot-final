// PracticeNotebookPanel.jsx — "📓 Practice Notebook" (the brain's rough / calculating paper)
// After the brain picks entry-time + direction, the pick waits on the ROUGH PAGE until realised
// price double-confirms the direction; confirmed → ANSWER SHEET (a real paper trade opens);
// went-the-other-way → MISTAKES BOOK with the diagnosed cause + the lens loses trust. Reads
// /api/trading/practice_notebook (state-file-only). Every number is a real graded outcome.
import { useEffect, useState } from 'react'
import { T } from './theme.js'

async function getJSON(url) {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json()
}
function num(v) { const n = v == null ? null : Number(v); return Number.isFinite(n) ? n : null }
function pct(v, d = 1) { const n = num(v); return n == null ? '—' : `${(n * 100).toFixed(d)}%` }
function rateColor(rate, n) {
  if (rate == null || !n) return T.muted
  if (rate >= 0.55) return T.good
  if (rate >= 0.5) return T.warn
  return T.bad
}

function Stat({ label, value, sub, color }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 92 }}>
      <span style={{ fontSize: 10, color: T.muted, textTransform: 'uppercase', letterSpacing: 0.4 }}>{label}</span>
      <span style={{ fontSize: 16, fontWeight: 700, color: color || T.text }}>{value}</span>
      {sub ? <span style={{ fontSize: 9, color: T.muted }}>{sub}</span> : null}
    </div>
  )
}

export default function PracticeNotebookPanel() {
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    let alive = true
    const load = () => getJSON('/api/trading/practice_notebook')
      .then(d => { if (alive) { setData(d); setErr(null) } })
      .catch(e => { if (alive) setErr(String(e)) })
    load()
    const t = setInterval(load, 15000)
    return () => { alive = false; clearInterval(t) }
  }, [])

  if (err) return <div style={{ color: T.bad, fontSize: 12 }}>practice notebook: {err}</div>
  if (!data) return <div style={{ color: T.muted, fontSize: 12 }}>loading practice notebook…</div>
  if (data.note) return <div style={{ color: T.bad, fontSize: 12 }}>{data.note}</div>

  const rep = data.report || {}
  const rough = data.rough || []
  const answers = data.answer_sheet || []
  const mistakes = data.mistakes || []
  const need = data.confirmations_required || 2

  return (
    <div>
      <div style={{ display: 'flex', gap: 18, flexWrap: 'wrap', marginBottom: 8 }}>
        <Stat label="practice acc" value={pct(rep.practice_direction_hit_rate)}
              color={rateColor(rep.practice_direction_hit_rate, rep.practice_n)}
              sub={rep.practice_n ? `n=${rep.practice_n} · ${rep.universe || '—'} symbols` : 'grading…'} />
        <Stat label="confirm rate" value={pct(rep.confirm_rate)}
              color={rateColor(rep.confirm_rate, (rep.opened || 0) + (rep.rejected || 0))}
              sub={`${rep.opened || 0} opened · ${rep.rejected || 0} rejected`} />
        <Stat label="watching now" value={num(rep.confirmed_live) != null ? `${rough.length}` : `${rough.length}`}
              color={T.text} sub={`need ${need} confirms`} />
        <Stat label="abstained" value={num(rep.abstained) ?? 0} color={T.muted} sub="skipped (unsure)" />
        <Stat label={data.long_only ? 'LONG-only' : 'both sides'} value={data.enabled ? 'ON' : 'OFF'}
              color={data.enabled ? T.good : T.bad} sub={`abstain < ${data.abstain_below}`} />
      </div>

      {/* ROUGH PAGE — live pending attempts */}
      <div style={{ fontSize: 10, color: T.muted, margin: '8px 0 2px' }}>📝 ROUGH PAGE — picks waiting for the market to confirm the direction</div>
      {rough.length === 0 && <div style={{ fontSize: 11, color: T.muted, padding: '3px 0' }}>nothing on the rough page right now</div>}
      {rough.slice(0, 12).map((a, i) => (
        <div key={`r${i}`} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0', borderTop: `1px solid ${T.gridline}` }}>
          <span style={{ width: 150, fontSize: 11, fontFamily: 'monospace', color: T.text, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.symbol}</span>
          <span style={{ width: 44, fontSize: 10, fontWeight: 700, color: a.side === 'long' ? T.good : T.bad }}>{String(a.side || '').toUpperCase()}</span>
          <span style={{ width: 54, fontSize: 10, color: T.muted }}>{a.regime || '—'}</span>
          <div style={{ flex: 1, display: 'flex', gap: 3 }} title={`${a.confirms || 0}/${need} confirmations`}>
            {Array.from({ length: need }).map((_, k) => (
              <div key={k} style={{ height: 6, flex: 1, borderRadius: 3, background: (a.confirms || 0) > k ? T.good : T.panel2 }} />
            ))}
          </div>
          <span style={{ width: 48, fontSize: 10, color: T.muted, textAlign: 'right' }}>{Math.round(a.age_s || 0)}s</span>
        </div>
      ))}

      {/* ANSWER SHEET — confirmed → opened */}
      <div style={{ fontSize: 10, color: T.muted, margin: '10px 0 2px' }}>✅ ANSWER SHEET — confirmed the predicted way, then opened</div>
      {answers.length === 0 && <div style={{ fontSize: 11, color: T.muted, padding: '3px 0' }}>no confirmed entries yet</div>}
      {answers.slice(0, 10).map((a, i) => (
        <div key={`a${i}`} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '3px 0', borderTop: `1px solid ${T.gridline}` }}>
          <span style={{ width: 150, fontSize: 11, fontFamily: 'monospace', color: T.text, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.symbol}</span>
          <span style={{ width: 44, fontSize: 10, fontWeight: 700, color: a.side === 'long' ? T.good : T.bad }}>{String(a.side || '').toUpperCase()}</span>
          <span style={{ width: 60, fontSize: 10, color: T.muted }}>{a.regime || '—'}</span>
          <span style={{ flex: 1, fontSize: 10, color: T.muted }}>confirmed in {num(a.latency_s) != null ? `${a.latency_s}s` : '—'}</span>
          <span style={{ width: 60, fontSize: 10, color: T.text, textAlign: 'right' }}>p↑ {pct(a.p_up, 0)}</span>
        </div>
      ))}

      {/* MISTAKES BOOK — rejected + diagnosed */}
      <div style={{ fontSize: 10, color: T.muted, margin: '10px 0 2px' }}>❌ MISTAKES BOOK — went the other way → why + what lost trust</div>
      {Object.keys(rep.reject_causes || {}).length > 0 && (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 4 }}>
          {Object.entries(rep.reject_causes).sort((a, b) => b[1] - a[1]).slice(0, 6).map(([k, v]) => (
            <span key={k} style={{ fontSize: 9, color: T.bad, border: `1px solid ${T.bad}`, borderRadius: 4, padding: '1px 5px' }}>{k}: {v}</span>
          ))}
        </div>
      )}
      {mistakes.length === 0 && <div style={{ fontSize: 11, color: T.muted, padding: '3px 0' }}>no mistakes recorded yet</div>}
      {mistakes.slice(0, 10).map((m, i) => (
        <div key={`m${i}`} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '3px 0', borderTop: `1px solid ${T.gridline}` }}>
          <span style={{ width: 150, fontSize: 11, fontFamily: 'monospace', color: T.text, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{m.symbol}</span>
          <span style={{ width: 44, fontSize: 10, fontWeight: 700, color: m.side === 'long' ? T.good : T.bad }}>{String(m.side || '').toUpperCase()}</span>
          <span style={{ width: 64, fontSize: 10, color: T.bad, textAlign: 'right' }}>{num(m.move_pct) != null ? `${m.move_pct}%` : '—'}</span>
          <span style={{ flex: 1, fontSize: 10, color: T.muted, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                title={JSON.stringify(m.reason || {})}>{(m.reason && m.reason.headline) || 'unexplained'}</span>
        </div>
      ))}

      <div style={{ fontSize: 9, color: T.muted, marginTop: 8 }}>
        Practises (predicts + grades, opens nothing) on the whole universe; only picks that double-confirm the direction reach the answer sheet. Per-regime practice accuracy: {Object.entries(rep.per_regime || {}).map(([k, v]) => `${k} ${pct(v, 0)}`).join(' · ') || '—'}
      </div>
    </div>
  )
}
