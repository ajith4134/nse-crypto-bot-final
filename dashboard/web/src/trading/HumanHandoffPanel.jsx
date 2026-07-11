// HumanHandoffPanel.jsx — "🧩 Human Handoff (solve the broker's CAPTCHA)"
// When a brain browser hits a human-only security challenge (Binance slide puzzle / image
// CAPTCHA), broker_sense/human_handoff.py pauses that browser and records it. This panel
// reads /api/trading/handoff (pure state-file), shows a red HUMAN-NEEDED banner, and a
// "Take control" button that brings up the interactive noVNC over the brain's shared Xvfb
// display so you drag the slider yourself — automation auto-resumes the instant it clears.
// Self-contained; polls ~3s; inline-styled via ./theme.js. Fully null-guarded so a bad
// payload degrades to an idle line and never unmounts the Trading view.
import { useEffect, useState, useCallback } from 'react'
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
function ago(ts) {
  const n = Number(ts)
  if (!Number.isFinite(n) || n <= 0) return '—'
  const s = Math.max(0, Math.floor(Date.now() / 1000 - n))
  if (s < 60) return `${s}s`
  if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60}s`
  return `${Math.floor(s / 3600)}h`
}

export default function HumanHandoffPanel() {
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)
  const [busy, setBusy] = useState(false)
  const [novnc, setNovnc] = useState(null)     // {broker, path, needs_install, no_display}

  const tick = useCallback(() => getJSON('/api/trading/handoff')
    .then((d) => { setData(d); setErr(null) })
    .catch((e) => setErr(String(e.message || e))), [])

  useEffect(() => {
    let alive = true
    const run = () => { if (alive) tick() }
    run()
    const id = setInterval(run, 3000)
    return () => { alive = false; clearInterval(id) }
  }, [tick])

  const activeBrokers = (data && Array.isArray(data.active_brokers)) ? data.active_brokers : []
  const anyActive = !!(data && data.any_active) && activeBrokers.length > 0
  const brokers = (data && data.brokers && typeof data.brokers === 'object') ? data.brokers : {}
  const primary = activeBrokers[0] || ''

  const takeControl = useCallback((broker) => {
    setBusy(true)
    postJSON('/api/trading/handoff', { op: 'take_control', broker })
      .then((r) => {
        setNovnc({ broker, path: r && r.novnc_path, needs_install: !!(r && r.needs_install),
          no_display: !!(r && r.no_display), detail: r && r.detail })
        tick()
      })
      .catch((e) => setErr(String(e.message || e)))
      .finally(() => setBusy(false))
  }, [tick])

  const resume = useCallback((broker) => {
    setBusy(true)
    postJSON('/api/trading/handoff', { op: 'resume', broker })
      .then(() => { setNovnc(null); tick() })
      .catch((e) => setErr(String(e.message || e)))
      .finally(() => setBusy(false))
  }, [tick])

  const btn = (bg) => ({ background: bg, color: '#fff', border: 'none', borderRadius: 6,
    padding: '7px 14px', fontSize: 12, fontWeight: 700, cursor: busy ? 'wait' : 'pointer',
    opacity: busy ? 0.6 : 1 })

  return (
    <div style={{ background: T.panel, border: `1px solid ${anyActive ? T.bad : T.gridline}`,
                  borderRadius: 8, padding: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: T.text }}>🧩 Human Handoff</span>
        <span style={{ fontSize: 10, color: T.muted }}>
          {data && data.enabled === false ? 'DISABLED (HUMAN_HANDOFF=0)' : 'auto-resumes when solved'}
        </span>
      </div>

      {err && <div style={{ color: T.bad, fontSize: 11 }}>error: {err}</div>}

      {!anyActive && (
        <div style={{ color: T.muted, fontSize: 12, padding: '4px 0' }}>
          No security challenge — brain browsers running. If a CAPTCHA appears, this turns red
          and you get a Take-control button (+ a Telegram ping).
        </div>
      )}

      {anyActive && activeBrokers.map((broker) => {
        const b = brokers[broker] || {}
        const showVnc = novnc && novnc.broker === broker && novnc.path && !novnc.needs_install && !novnc.no_display
        return (
          <div key={broker} style={{ border: `1px solid ${T.bad}`, borderRadius: 6, padding: 10,
                                     display: 'flex', flexDirection: 'column', gap: 8,
                                     background: 'rgba(255,60,60,0.06)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <span style={{ fontSize: 13, fontWeight: 800, color: T.bad, letterSpacing: 0.3 }}>
                HUMAN NEEDED — solve CAPTCHA
              </span>
              <span style={{ fontSize: 11, color: T.text, fontFamily: 'monospace',
                             border: `1px solid ${T.gridline}`, borderRadius: 4, padding: '1px 6px' }}>
                {broker}
              </span>
              <span style={{ fontSize: 10, color: T.muted }}>paused {ago(b.since)}</span>
            </div>
            {b.url && <div style={{ fontSize: 10, color: T.muted, fontFamily: 'monospace',
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={b.url}>
              {b.url}</div>}

            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button style={btn(T.bad)} disabled={busy} onClick={() => takeControl(broker)}>
                Take control ↦ drag the slider
              </button>
              {novnc && novnc.broker === broker && novnc.path && (
                <a href={novnc.path} target="_blank" rel="noreferrer"
                   style={{ ...btn(T.warn || '#c80'), textDecoration: 'none', display: 'inline-block' }}>
                  Open in new tab ↗
                </a>
              )}
              <button style={btn(T.good || '#2a2')} disabled={busy} onClick={() => resume(broker)}>
                I solved it — resume
              </button>
            </div>

            {b.needs_install && (
              <div style={{ fontSize: 11, color: T.warn }}>
                ⚠ x11vnc is not installed — interactive control needs it. Ask to run:
                <code style={{ marginLeft: 6 }}>sudo apt-get install -y x11vnc xauth</code>
              </div>
            )}
            {novnc && novnc.broker === broker && novnc.no_display && (
              <div style={{ fontSize: 11, color: T.warn }}>
                No X display {b.display || ':99'} — the brain's headed browser isn't up yet.
              </div>
            )}
            {novnc && novnc.broker === broker && novnc.needs_install && (
              <div style={{ fontSize: 11, color: T.warn }}>
                Can't start interactive control: x11vnc missing on the host.
              </div>
            )}

            {showVnc && (
              <iframe title={`novnc-${broker}`} src={novnc.path}
                      style={{ width: '100%', height: 520, border: `1px solid ${T.gridline}`,
                               borderRadius: 6, background: '#000' }} />
            )}
          </div>
        )
      })}
    </div>
  )
}
