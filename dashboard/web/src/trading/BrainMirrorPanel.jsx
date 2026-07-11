// BrainMirrorPanel.jsx — the Brain Screen Mirror: a READ-ONLY live view of the browsers the
// BRAIN itself drives (crypto/NSE funnels, the ⭐-watchlist hand, app-school). Shows the page
// the brain is on right now, a marker where it last clicked, and a live feed of its actions
// (open / click / type / read / order-guard blocks). Watching never steers the hand — the
// interactive login browser is the separate LiveBrowserPanel above.
import { useEffect, useRef, useState } from 'react'
import { T } from './theme.js'

const API = '/api/trading/mirror'

const ACT_ICON = { open: '🌐', click: '🖱️', type: '⌨️', press: '⏎', read: '👁️', perceive: '👁️' }

function Badge({ live }) {
  const c = live ? (T.good || '#3ecf8e') : (T.muted || '#8a93a6')
  return (
    <span style={{ fontSize: 10, fontWeight: 800, color: c, border: `1px solid ${c}`,
      borderRadius: 999, padding: '2px 8px', letterSpacing: 0.5 }}>
      {live ? '● LIVE' : '○ IDLE'}
    </span>
  )
}

export default function BrainMirrorPanel() {
  const [st, setSt] = useState(null)          // /api/trading/mirror payload
  const [broker, setBroker] = useState('')    // '' until brokers known
  const [frameTs, setFrameTs] = useState(0)   // cache-buster, bumped only on fresh frames
  const [liveStream, setLive] = useState(false) // M: MJPEG live video vs frame polling
  const [liveErr, setLiveErr] = useState(null)
  const imgRef = useRef(null)
  const alive = useRef(true)

  useEffect(() => {
    // Per-effect liveness + fetch timeout (2026-07-10 fix): a hung request used to
    // freeze the panel on the PREVIOUS broker's frame + action feed after switching
    // (upstox tab kept showing binance). Payloads are tagged with the broker they were
    // fetched for, so stale data can never render under the wrong tab.
    let live = true
    alive.current = true
    setFrameTs(0)
    const tick = async () => {
      const ctl = new AbortController()
      const kill = setTimeout(() => ctl.abort(), 6000)
      try {
        const q = broker ? `?broker=${broker}&limit=40` : ''
        const r = await fetch(`${API}${q}`, { signal: ctl.signal })
        const j = await r.json()
        if (!live) return
        setSt({ ...j, _for: broker })
        const names = Object.keys(j.brokers || {})
        if (!broker && names.length) {
          // default to the busiest LIVE mirror, else the first one
          const liveB = names.find((n) => j.brokers[n].live)
          setBroker(liveB || names[0])
        }
        const meta = j.brokers && j.brokers[broker]
        if (meta && meta.ts) setFrameTs(meta.ts)   // new frame → new <img> URL
      } catch { /* offline blip or timeout — next tick retries */ }
      finally { clearTimeout(kill) }
    }
    tick()
    const t = setInterval(tick, 2500)
    return () => { live = false; alive.current = false; clearInterval(t) }
  }, [broker])

  const brokers = st ? Object.keys(st.brokers || {}) : []
  const meta = (st && st.brokers && st.brokers[broker]) || null
  // only show an action feed fetched FOR the selected broker (never a stale tab's)
  const actions = (st && st._for === broker && st.actions) || []
  const la = meta && meta.last_action
  const vp = (meta && meta.viewport) || {}

  // click marker: last action coordinates mapped onto the rendered image size
  const marker = la && la.xy && vp.w && vp.h && imgRef.current
    ? {
        left: `${(la.xy[0] / vp.w) * 100}%`,
        top: `${(la.xy[1] / vp.h) * 100}%`,
      }
    : null

  const card = { background: T.panel, border: `1px solid ${T.border}`, borderRadius: 12, padding: 14 }
  const age = meta && meta.age_s != null ? (meta.age_s < 90 ? `${Math.round(meta.age_s)}s ago` : `${Math.round(meta.age_s / 60)}m ago`) : '—'

  return (
    <div style={card}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6, gap: 8, flexWrap: 'wrap' }}>
        <div style={{ fontSize: 14, fontWeight: 800, color: T.text }}>
          🪞 Brain Screen Mirror — watch the brain work {meta ? <Badge live={!!meta.live} /> : null}
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <button onClick={() => setLive(!liveStream)} title={liveErr || 'real MJPEG video of the brain display (ffmpeg x11grab)'} style={{
            background: T.panel2 || '#1a1f2b', color: liveStream ? '#ff5b5b' : T.muted,
            border: `1px solid ${liveStream ? '#ff5b5b' : T.border}`, borderRadius: 8,
            padding: '5px 10px', cursor: 'pointer', fontSize: 12, fontWeight: 800 }}>
            {liveStream ? '⏺ LIVE VIDEO' : '▶ LIVE VIDEO'}
          </button>
          {brokers.map((b) => (
            <button key={b} onClick={() => setBroker(b)} style={{
              background: T.panel2 || '#1a1f2b', color: b === broker ? (T.accent || '#5b9dff') : T.muted,
              border: `1px solid ${b === broker ? (T.accent || '#5b9dff') : T.border}`, borderRadius: 8,
              padding: '5px 10px', cursor: 'pointer', fontSize: 12, fontWeight: 700 }}>
              {b === broker ? `● ${b}` : b}
            </button>
          ))}
        </div>
      </div>
      <div style={{ fontSize: 11, color: T.muted, marginBottom: 8 }}>
        Read-only mirror of the browser the brain operates (funnel screening, ⭐ watchlist hand, app-school).
        {meta && meta.url ? <> Current page: <b style={{ color: T.text }}>{(meta.title || meta.url).slice(0, 90)}</b> · frame {age}</> : ' Waiting for the brain to touch a page…'}
      </div>
      {liveStream ? (
        // M (2026-07-11): REAL live video — one MJPEG stream of the brain's whole Xvfb
        // display (every browser it drives), capture running only while this is open.
        <div style={{ position: 'relative' }}>
          <img alt="live brain display" src={`/api/trading/mirror/stream?t=${Date.now()}`}
            onError={() => { setLiveErr('live stream unavailable — no headed display up (falls back to frames)'); setLive(false) }}
            style={{ width: '100%', border: '1px solid #ff5b5b', borderRadius: 8, display: 'block' }} />
          <div style={{ position: 'absolute', top: 8, right: 8, fontSize: 10, fontWeight: 800,
            color: '#ff5b5b', background: 'rgba(0,0,0,0.55)', borderRadius: 6, padding: '3px 8px' }}>⏺ LIVE</div>
        </div>
      ) : meta && meta.ts ? (
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <div style={{ flex: '2 1 480px', position: 'relative', minWidth: 320 }}>
            <img ref={imgRef} key={broker} alt={`brain browser ${broker}`}
              src={`${API}/frame?broker=${broker}&t=${frameTs}`}
              style={{ width: '100%', border: `1px solid ${T.border}`, borderRadius: 8, display: 'block',
                filter: meta.live ? 'none' : 'grayscale(60%) brightness(0.8)' }} />
            {marker && (
              <div style={{ position: 'absolute', ...marker, transform: 'translate(-50%, -50%)',
                width: 26, height: 26, borderRadius: '50%', pointerEvents: 'none',
                border: `2px solid ${T.warn || '#e6b800'}`,
                boxShadow: `0 0 10px ${T.warn || '#e6b800'}` }} />
            )}
            {!meta.live && (
              <div style={{ position: 'absolute', top: 8, right: 8, fontSize: 10, fontWeight: 800,
                color: T.muted, background: 'rgba(0,0,0,0.55)', borderRadius: 6, padding: '3px 8px' }}>
                last frame {age} — brain idle or browser closed
              </div>
            )}
          </div>
          <div style={{ flex: '1 1 240px', minWidth: 220, maxHeight: 430, overflowY: 'auto' }}>
            <div style={{ fontSize: 11, fontWeight: 800, color: T.muted, marginBottom: 6, letterSpacing: 0.5 }}>ACTION FEED</div>
            {actions.length === 0 && <div style={{ fontSize: 12, color: T.muted }}>No recorded actions yet.</div>}
            {[...actions].reverse().map((a, i) => (
              <div key={i} style={{ fontSize: 11.5, color: T.text, padding: '5px 6px', borderBottom: `1px solid ${T.border}`,
                opacity: a.blocked ? 0.9 : 1 }}>
                <span style={{ marginRight: 5 }}>{ACT_ICON[a.act] || '·'}</span>
                <b>{a.act}</b>
                {a.blocked ? <span style={{ color: T.bad || '#ff6b6b', fontWeight: 700 }}> BLOCKED ({a.blocked})</span> : null}
                {a.ok === false ? <span style={{ color: T.warn || '#e6b800' }}> ✗</span> : null}
                <span style={{ color: T.muted }}> {(a.detail || a.target || '').slice(0, 80)}</span>
                <div style={{ color: T.muted, fontSize: 10 }}>
                  {a.ts ? new Date(a.ts * 1000).toLocaleTimeString() : ''}{a.xy ? ` · @${a.xy[0]},${a.xy[1]}` : ''}{a.frame === false ? ' · no frame' : ''}
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div style={{ color: T.muted, fontSize: 12, padding: '10px 0' }}>
          {st && st.enabled === false
            ? 'Screen mirror is disabled (SCREEN_MIRROR=0).'
            : 'No frames yet — the mirror records automatically the moment the brain opens a broker page (funnel cycle, watchlist sync, app-school).'}
        </div>
      )}
    </div>
  )
}
