// BrainMirrorPanel.jsx — the Brain Screen Mirror: a READ-ONLY live view of the browsers the
// BRAIN itself drives (crypto/NSE funnels, the ⭐-watchlist hand, app-school). Shows the page
// the brain is on right now, a marker where it last clicked, and a live feed of its actions
// (open / click / type / read / order-guard blocks). Watching never steers the hand — the
// interactive login browser is the separate LiveBrowserPanel above.
import { useCallback, useEffect, useRef, useState } from 'react'
import { T } from './theme.js'

const API = '/api/trading/mirror'

const ACT_ICON = { open: '🌐', click: '🖱️', type: '⌨️', press: '⏎', read: '👁️', perceive: '👁️' }

// M fix (2026-07-11): Chromium does NOT render multipart/x-mixed-replace <img>
// streams delivered over HTTP/2 — and every public tunnel (cloudflare/ngrok) speaks
// h2 to the browser, so the naive <img src=stream> stayed naturalWidth=0 forever.
// fetch() streaming works fine over h2: parse the MJPEG bytes ourselves (JPEG
// SOI ff d8 → EOI ff d9) and paint each frame via a blob URL.
function indexOfSeq(buf, a, b, from) {
  for (let i = from || 0; i < buf.length - 1; i++) {
    if (buf[i] === a && buf[i + 1] === b) return i
  }
  return -1
}

function LiveStreamView({ onFail }) {
  const ref = useRef(null)
  useEffect(() => {
    const ctrl = new AbortController()
    let dead = false
    let lastUrl = null
    ;(async () => {
      try {
        const res = await fetch(`/api/trading/mirror/stream?t=${Date.now()}`, { signal: ctrl.signal })
        if (!res.ok || !res.body) {
          let msg = `live stream unavailable (HTTP ${res.status})`
          try { msg = (await res.json()).error || msg } catch { /* non-JSON body */ }
          if (!dead) onFail(msg)
          return
        }
        const reader = res.body.getReader()
        let buf = new Uint8Array(0)
        while (!dead) {
          const { done, value } = await reader.read()
          if (done) break
          const nb = new Uint8Array(buf.length + value.length)
          nb.set(buf); nb.set(value, buf.length); buf = nb
          let start = indexOfSeq(buf, 0xff, 0xd8)
          let end = start >= 0 ? indexOfSeq(buf, 0xff, 0xd9, start + 2) : -1
          let painted = -1
          while (start >= 0 && end >= 0) {          // paint the newest complete frame
            painted = end
            const jpg = buf.slice(start, end + 2)
            if (ref.current) {
              const u = URL.createObjectURL(new Blob([jpg], { type: 'image/jpeg' }))
              ref.current.src = u
              if (lastUrl) URL.revokeObjectURL(lastUrl)
              lastUrl = u
            }
            start = indexOfSeq(buf, 0xff, 0xd8, end + 2)
            end = start >= 0 ? indexOfSeq(buf, 0xff, 0xd9, start + 2) : -1
          }
          if (painted >= 0) buf = buf.slice(painted + 2)
          if (buf.length > 8_000_000) buf = new Uint8Array(0)   // runaway guard
        }
        if (!dead) onFail('live stream ended — brain display went away (falls back to frames)')
      } catch {
        if (!dead) onFail('live stream unavailable — no headed display up (falls back to frames)')
      }
    })()
    return () => { dead = true; ctrl.abort(); if (lastUrl) URL.revokeObjectURL(lastUrl) }
  }, [onFail])
  return (
    <img ref={ref} alt="live brain display"
      style={{ width: '100%', minHeight: 200, border: '1px solid #ff5b5b', borderRadius: 8, display: 'block' }} />
  )
}

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
  // stable callback: an inline lambda would re-mount LiveStreamView (and reconnect
  // the stream) on every 2.5s poll re-render
  const onLiveFail = useCallback((msg) => { setLiveErr(msg); setLive(false) }, [])
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
          {/* group tabs by market (CRYPTO first, then NSE) so the two markets read as separate
              feeds, and show each broker's live/stale/login state — a stale Upstox reads as
              "needs re-login", never "missing" (2026-07-13 isolation pass). */}
          {[...brokers].sort((a, c) => {
            const ma = (st.brokers[a]?.market || 'CRYPTO'), mc = (st.brokers[c]?.market || 'CRYPTO')
            return ma === mc ? a.localeCompare(c) : (ma === 'CRYPTO' ? -1 : 1)
          }).map((b) => {
            const bm = st.brokers[b] || {}
            const mkt = bm.market || 'CRYPTO'
            const dot = bm.login_in_progress ? '🔑' : (bm.live ? '●' : '○')
            const mktColor = mkt === 'CRYPTO' ? '#f0b90b' : '#5b9dff'   // binance-gold vs nse-blue
            return (
              <button key={b} onClick={() => setBroker(b)} title={`${mkt} · ${bm.login_in_progress ? 'operator logging in' : bm.live ? 'live' : `stale${bm.age_s != null ? ` ${bm.age_s}s` : ''}`}`} style={{
                background: T.panel2 || '#1a1f2b', color: b === broker ? (T.accent || '#5b9dff') : T.muted,
                border: `1px solid ${b === broker ? (T.accent || '#5b9dff') : T.border}`, borderRadius: 8,
                padding: '5px 10px', cursor: 'pointer', fontSize: 12, fontWeight: 700 }}>
                {dot} {b}
                <span style={{ marginLeft: 5, fontSize: 9, fontWeight: 800, color: mktColor,
                  border: `1px solid ${mktColor}`, borderRadius: 4, padding: '0 3px' }}>{mkt}</span>
              </button>
            )
          })}
        </div>
      </div>
      <div style={{ fontSize: 11, color: T.muted, marginBottom: 8 }}>
        Read-only mirror of the browser the brain operates (funnel screening, ⭐ watchlist hand, app-school).
        {meta && meta.url ? <> Current page: <b style={{ color: T.text }}>{(meta.title || meta.url).slice(0, 90)}</b> · frame {age}</> : ' Waiting for the brain to touch a page…'}
      </div>
      {liveStream ? (
        // M (2026-07-11): REAL live video — one MJPEG stream of the brain's whole Xvfb
        // display (every browser it drives), capture running only while this is open.
        // Parsed client-side (LiveStreamView) because h2 tunnels break native MJPEG <img>.
        <div style={{ position: 'relative' }}>
          <LiveStreamView onFail={onLiveFail} />
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
