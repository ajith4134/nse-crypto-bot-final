// LiveBrowserPanel.jsx — an interactive HEADLESS browser streamed into the dashboard so YOU can
// complete a broker login (Binance's image CAPTCHA + OTP) that automation can't. Your clicks and
// typing are forwarded to the real page; "Save session" persists the login so the brain reads
// your account headless afterward. No installs, works over the public link.
import { useEffect, useRef, useState } from 'react'
import { T } from './theme.js'

const API = '/api/trading/live_browser'

async function post(body) {
  const r = await fetch(API, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  return r.json()
}

function Btn({ children, onClick, color, disabled }) {
  const c = color || T.accent || '#5b9dff'
  return (
    <button onClick={onClick} disabled={disabled} style={{
      background: T.panel2 || '#1a1f2b', color: disabled ? T.muted : c, border: `1px solid ${disabled ? T.border : c}`,
      borderRadius: 8, padding: '6px 11px', cursor: disabled ? 'not-allowed' : 'pointer', fontSize: 12, fontWeight: 700,
      opacity: disabled ? 0.6 : 1, whiteSpace: 'nowrap' }}>{children}</button>
  )
}

const BROKERS = ['binance', 'upstox', 'groww', 'angelone']   // accounts the funnel reads (crypto + NSE); upstox = instant QR login

export default function LiveBrowserPanel({ broker: initialBroker = 'binance' }) {
  const [broker, setBroker] = useState(initialBroker)
  const [running, setRunning] = useState(false)
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState(null)
  const [typed, setTyped] = useState('')
  const [savedMsg, setSavedMsg] = useState('')
  const [view] = useState({ w: 1280, h: 800 })
  const imgRef = useRef(null)
  const alive = useRef(true)

  useEffect(() => {
    // CHAINED streaming (2026-07-10 speed fix): request the next frame only after the
    // previous one finished loading — a fixed interval piled up requests on slow links
    // and made every click feel seconds-laggy. This self-paces to the connection:
    // fast link ≈ 3-4 fps, slow link degrades gracefully instead of jamming the queue.
    alive.current = true
    let timer
    const img = imgRef.current
    const next = (delay) => { if (alive.current) timer = setTimeout(load, delay) }
    const load = () => {
      if (!alive.current) return
      if (!running || !imgRef.current) return next(400)
      imgRef.current.onload = () => next(220)
      imgRef.current.onerror = () => next(1200)   // 204/blip — retry gently
      imgRef.current.src = `${API}/frame?broker=${broker}&t=${Date.now()}`
    }
    load()
    return () => {
      alive.current = false
      clearTimeout(timer)
      if (img) { img.onload = null; img.onerror = null }
    }
  }, [running, broker])

  const start = async () => { setBusy(true); const r = await post({ op: 'start', broker }); if (alive.current) { setRunning(!!r.ok); setStatus(r); setBusy(false) } }
  const stop = async () => { setBusy(true); await post({ op: 'stop', broker }); if (alive.current) { setRunning(false); setBusy(false) } }
  const save = async () => {
    // ONE-CLICK HANDOFF (2026-07-11): "Save session" used to only persist cookies and leave the
    // panel open — the operator then had to ALSO click Close for the brain to reclaim the browser
    // profile, so it looked like nothing happened ("button not working"). Now a successful save
    // when logged-in immediately closes the login browser too, which releases the shared Chromium
    // profile so the funnel reads the account headless. One click does the whole handoff.
    setBusy(true); setSavedMsg('⏳ Saving your session…')
    const r = await post({ op: 'save', broker })
    if (!alive.current) return
    if (r && r.looks_logged_in) {
      setSavedMsg('✅ Logged in — handing over to the brain…')
      await post({ op: 'stop', broker })                 // release the profile → funnel reclaims it
      if (alive.current) {
        setRunning(false)
        setSavedMsg(`✅ Done! ${broker} session saved — the brain is now reading your account headless. You can close this panel.`)
      }
    } else {
      setSavedMsg('⚠️ Saved, but you are not fully logged in yet — finish the login/verification steps above, then click Save session again.')
    }
    if (alive.current) setBusy(false)
  }

  const onImgClick = async (e) => {
    if (!running || !imgRef.current) return
    const rect = imgRef.current.getBoundingClientRect()
    const x = Math.round((e.clientX - rect.left) / rect.width * view.w)
    const y = Math.round((e.clientY - rect.top) / rect.height * view.h)
    await post({ op: 'click', broker, x, y })
  }
  const sendText = async () => { if (typed) { await post({ op: 'type', broker, text: typed }); setTyped('') } }
  const key = async (k) => post({ op: 'key', broker, key: k })

  const card = { background: T.panel, border: `1px solid ${T.border}`, borderRadius: 12, padding: 14 }

  return (
    <div style={card}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <div style={{ fontSize: 14, fontWeight: 800, color: T.text }}>🖥️ Live browser — connect {broker} (solve captcha / scan QR here)</div>
        <div style={{ display: 'flex', gap: 8 }}>
          {!running && BROKERS.map((b) => (
            <Btn key={b} onClick={() => setBroker(b)} color={b === broker ? undefined : T.muted}>
              {b === broker ? `● ${b}` : b}
            </Btn>
          ))}
          {!running ? <Btn onClick={start} disabled={busy}>Open {broker} login</Btn>
            : <>
              <Btn onClick={save} disabled={busy} color={T.good || '#3ecf8e'}>Save session</Btn>
              <Btn onClick={stop} disabled={busy} color={T.bad || '#ff6b6b'}>Close</Btn>
            </>}
        </div>
      </div>
      <div style={{ fontSize: 11, color: T.muted, marginBottom: 8 }}>
        Click directly on the page below (the captcha tiles, buttons). Type your email/OTP in the box, press Send. When you&apos;re logged in, click <b>Save session</b>.
      </div>
      {running ? (
        <div>
          <img ref={imgRef} onClick={onImgClick} alt="live browser"
            style={{ width: '100%', border: `1px solid ${T.border}`, borderRadius: 8, cursor: 'crosshair', display: 'block' }} />
          <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <input value={typed} onChange={(e) => setTyped(e.target.value)} placeholder="type here (email / OTP), then Send"
              onKeyDown={(e) => { if (e.key === 'Enter') sendText() }}
              style={{ flex: 1, minWidth: 200, background: T.panel2 || '#1a1f2b', color: T.text, border: `1px solid ${T.border}`, borderRadius: 8, padding: '7px 10px', fontSize: 13 }} />
            <Btn onClick={sendText}>Send text</Btn>
            <Btn onClick={() => key('Enter')}>Enter</Btn>
            <Btn onClick={() => key('Backspace')}>⌫</Btn>
          </div>
          {savedMsg && (() => {
            const ok = savedMsg.startsWith('✅'); const wait = savedMsg.startsWith('⏳')
            const c = ok ? (T.good || '#3ecf8e') : wait ? (T.muted || '#8b93a7') : (T.warn || '#e6b800')
            return (
              <div style={{ marginTop: 10, padding: '10px 12px', fontSize: 13, fontWeight: 700,
                color: c, background: `${c}1a`, border: `1px solid ${c}`, borderRadius: 8 }}>
                {savedMsg}
              </div>
            )
          })()}
        </div>
      ) : (
        <div style={{ color: T.muted, fontSize: 12, padding: '10px 0' }}>
          Click &quot;Open {broker} login&quot; to launch the browser here. {status && status.error ? `(${status.error})` : ''}
        </div>
      )}
    </div>
  )
}
