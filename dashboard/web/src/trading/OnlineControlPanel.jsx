// OnlineControlPanel.jsx — Phase O5 "Online Control" (Dark Pro UI)
// Primary live-trading control surface for the trading dashboard. Self-fetching
// (like BrainPanel): on mount it GETs /api/trading/online/status and polls ~4s,
// then renders a per-market control card (CRYPTO + NSE) with start/stop/pause/halt,
// a Paper/Real toggle (REAL → confirm() + confirm:true), an allow-live checkbox, an
// editable paper balance (set/top-up/reset), plus a global PANIC button. Every POST
// goes through control() with try/catch; buttons disable briefly while in flight.
// Inline-styled via ./theme.js, no styles.css dependency. Robust to partial data.
import { useEffect, useRef, useState } from 'react'
import { T } from './theme.js'

const STATUS_URL = '/api/trading/online/status'
const CONTROL_URL = '/api/trading/online/control'
const MARKETS = ['CRYPTO', 'NSE']

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

function money(v) {
  const n = num(v)
  if (n == null) return '—'
  return n.toLocaleString(undefined, { maximumFractionDigits: 2 })
}

// truthy/affirmative detection robust to bool/string/number
function truthy(v) {
  if (v === true) return true
  if (typeof v === 'number') return v !== 0
  if (typeof v === 'string') return /^(1|true|yes|on|enabled|active)$/i.test(v.trim())
  return false
}

// Colour a market's trading_state (ACTIVE/RUNNING green, PAUSED amber, others red).
function stateColor(s) {
  const t = String(s || '').toUpperCase()
  if (/(ACTIVE|RUNNING|LIVE|STARTED|TRADING|ON)/.test(t)) return T.good
  if (/(PAUSE|REDUCE)/.test(t)) return T.warn
  return T.bad
}

// Mode colour: REAL is dangerous (red), PAPER is safe (green).
function modeColor(m) {
  return String(m || '').toUpperCase() === 'REAL' ? T.bad : T.good
}

// Session mode colour: LIVE green, REPLAY amber.
function sessionColor(s) {
  return String(s || '').toUpperCase() === 'LIVE' ? T.good : T.warn
}

// Pull a per-market object out of the status payload, regardless of casing.
function marketStatus(status, market) {
  const markets = (status && status.markets) || {}
  return (
    markets[market] ||
    markets[market.toLowerCase()] ||
    markets[market.toUpperCase()] ||
    {}
  )
}

// Pull the wallet for a market. The backend returns wallets as a LIST of
// {market, portfolio_id, cash, equity, ...}; also tolerate a dict-keyed shape.
function marketWallet(status, market) {
  const wallets = (status && status.wallets) || []
  if (Array.isArray(wallets)) {
    const m = String(market).toUpperCase()
    return wallets.find((w) => String(w.market).toUpperCase() === m) || {}
  }
  return wallets[market] || wallets[String(market).toUpperCase()] || {}
}

// ---- presentational primitives ------------------------------------------------

function Badge({ text, color }) {
  return (
    <span
      style={{
        fontSize: 11,
        fontWeight: 700,
        letterSpacing: 0.5,
        color,
        border: `1px solid ${color}`,
        borderRadius: 4,
        padding: '2px 8px',
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
      <span style={{ fontSize: 15, fontWeight: 700, color: color || T.text }}>{value}</span>
    </div>
  )
}

// Small inline spinner (Dark-Pro). Reuses one @keyframes definition by name.
function Spinner({ color, size = 11 }) {
  return (
    <>
      <style>{'@keyframes ocp-spin{to{transform:rotate(360deg)}}'}</style>
      <span
        aria-hidden="true"
        style={{
          display: 'inline-block',
          width: size,
          height: size,
          border: `2px solid ${color || T.accent}`,
          borderTopColor: 'transparent',
          borderRadius: '50%',
          animation: 'ocp-spin 0.6s linear infinite',
          verticalAlign: 'middle',
        }}
      />
    </>
  )
}

// `loading` shows a spinner on *this* button and disables it (per-action feedback);
// `title` adds a native tooltip (used for the "arm allow live first" hint).
function ActionButton({ children, onClick, disabled, color, loading, title }) {
  const c = color || T.accent
  const off = disabled || loading
  return (
    <button
      onClick={onClick}
      disabled={off}
      title={title}
      style={{
        background: T.panel2,
        color: off ? T.muted : c,
        border: `1px solid ${off ? T.border : c}`,
        borderRadius: 8,
        padding: '7px 12px',
        cursor: off ? 'not-allowed' : 'pointer',
        fontSize: 13,
        fontWeight: 600,
        opacity: off ? 0.6 : 1,
        whiteSpace: 'nowrap',
        display: 'inline-flex',
        alignItems: 'center',
        gap: 7,
      }}
    >
      {loading && <Spinner color={c} />}
      {children}
    </button>
  )
}

// ---- per-market card ----------------------------------------------------------

function MarketCard({ market, status, busy, onAction, pending }) {
  const ms = marketStatus(status, market)
  const wallet = marketWallet(status, market)
  const [balanceInput, setBalanceInput] = useState('')

  const mode = ms.mode || (truthy(ms.real) ? 'REAL' : 'PAPER')
  const tradingState = ms.trading_state || ms.state || (truthy(ms.enabled) ? 'ACTIVE' : 'HALTED')
  const enabled = truthy(ms.enabled)
  const allowLive = truthy(ms.allow_live)
  const session = ms.session_mode || ms.session || ms.mode_session || '—'
  const isReal = String(mode).toUpperCase() === 'REAL'

  const equity = ms.equity ?? wallet.equity ?? wallet.paper_equity
  const cash = ms.cash ?? wallet.cash ?? wallet.balance ?? wallet.paper_cash

  const inFlight = !!busy
  // is a given action the one currently in flight for THIS card? (per-action spinner)
  const loadingFor = (a) => inFlight && pending === a
  // arming gate: PAPER→REAL is only allowed once "allow live" is armed.
  const armGated = !isReal && !allowLive

  // Banner text e.g. "CRYPTO: PAPER ● ACTIVE ● LIVE-session"
  const banner = (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        flexWrap: 'wrap',
        background: T.panel2,
        border: `1px solid ${T.border}`,
        borderRadius: 8,
        padding: '8px 10px',
        fontWeight: 700,
        fontSize: 13,
      }}
    >
      <span style={{ color: market === 'CRYPTO' ? T.warn : T.accent }}>{market}:</span>
      <span style={{ color: modeColor(mode) }}>{String(mode).toUpperCase()}</span>
      <span style={{ color: T.muted }}>●</span>
      <span style={{ color: stateColor(tradingState) }}>{String(tradingState).toUpperCase()}</span>
      <span style={{ color: T.muted }}>●</span>
      <span style={{ color: sessionColor(session) }}>{String(session).toUpperCase()}-session</span>
    </div>
  )

  const send = (extra) => onAction({ market, ...extra })

  const toggleMode = () => {
    if (isReal) {
      // turning REAL -> PAPER (safe, no confirm)
      send({ action: 'mode', value: 'PAPER' })
    } else {
      // turning PAPER -> REAL (dangerous, confirm + confirm:true)
      if (window.confirm(
        `Switch ${market} to REAL money mode?\n\nThis enables live order placement. Are you sure?`
      )) {
        send({ action: 'mode', value: 'REAL', confirm: true })
      }
    }
  }

  const setBalance = () => {
    const amt = num(balanceInput)
    if (amt == null) return
    send({ action: 'set_balance', amount: amt })
  }
  const topUp = () => {
    const amt = num(balanceInput)
    send({ action: 'top_up', amount: amt != null ? amt : undefined })
  }
  const resetWallet = () => {
    if (window.confirm(`Reset ${market} paper wallet to default balance?`)) {
      send({ action: 'reset_wallet' })
    }
  }

  return (
    <div
      style={{
        background: T.panel,
        border: `1px solid ${isReal ? T.bad : T.border}`,
        borderRadius: 10,
        padding: 12,
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
        boxSizing: 'border-box',
        minWidth: 0,
      }}
    >
      {banner}

      {/* trade-type SEGMENT selector — only selected segments are traded */}
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center', marginTop: 8 }}>
        <span style={{ fontSize: 10, color: T.muted, textTransform: 'uppercase', letterSpacing: 0.5, marginRight: 2 }}>Trade types:</span>
        {(ms.available_segments || []).map((seg) => {
          const on = (ms.segments || []).includes(seg)
          return (
            <span key={seg} onClick={() => !inFlight && send({ action: 'toggle_segment', value: seg })}
              title={on ? 'click to disable' : 'click to enable'}
              style={{ cursor: inFlight ? 'not-allowed' : 'pointer', fontSize: 11, fontWeight: 600,
                padding: '3px 9px', borderRadius: 12, textTransform: 'uppercase', letterSpacing: 0.3,
                color: on ? T.bg || '#0a0e14' : T.muted,
                background: on ? (market === 'CRYPTO' ? T.warn : T.accent) : 'transparent',
                border: `1px solid ${on ? (market === 'CRYPTO' ? T.warn : T.accent) : T.border}` }}>
              {on ? '✓ ' : ''}{seg}
            </span>
          )
        })}
      </div>

      {/* prominent REAL-money warning (the red border alone is easy to miss) */}
      {isReal && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            background: 'rgba(255,92,108,0.12)',
            border: `1px solid ${T.bad}`,
            borderRadius: 8,
            padding: '8px 10px',
            color: T.bad,
            fontWeight: 800,
            fontSize: 13,
            letterSpacing: 0.3,
          }}
        >
          ⚠ REAL MONEY — live orders can be placed
        </div>
      )}

      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        <Stat label="enabled" value={enabled ? 'yes' : 'no'} color={enabled ? T.good : T.muted} />
        <Stat label="mode" value={String(mode).toUpperCase()} color={modeColor(mode)} />
        <Stat label="allow live" value={allowLive ? 'yes' : 'no'} color={allowLive ? T.warn : T.muted} />
        <Stat label="session" value={String(session).toUpperCase()} color={sessionColor(session)} />
      </div>

      {/* lifecycle controls */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <ActionButton onClick={() => send({ action: 'start' })} disabled={inFlight} loading={loadingFor('start')} color={T.good}>▶ Start</ActionButton>
        <ActionButton onClick={() => send({ action: 'stop' })} disabled={inFlight} loading={loadingFor('stop')} color={T.accent}>⏹ Stop</ActionButton>
        <ActionButton onClick={() => send({ action: 'pause' })} disabled={inFlight} loading={loadingFor('pause')} color={T.warn}>⏸ Pause (reduce-only)</ActionButton>
        <ActionButton onClick={() => send({ action: 'halt' })} disabled={inFlight} loading={loadingFor('halt')} color={T.bad}>🛑 Halt</ActionButton>
      </div>

      {/* mode + allow-live */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
        <ActionButton
          onClick={toggleMode}
          disabled={inFlight || armGated}
          loading={loadingFor('mode')}
          color={isReal ? T.good : T.bad}
          title={armGated ? "arm ‘allow live’ first" : undefined}
        >
          {isReal ? 'Switch to PAPER' : 'Switch to REAL'}
        </ActionButton>
        {/* arming pill: makes the allow_live state unmistakable */}
        <Badge
          text={allowLive ? '🔓 LIVE ARMED' : '🔒 live disarmed'}
          color={allowLive ? T.bad : T.muted}
        />
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: T.text, cursor: inFlight ? 'not-allowed' : 'pointer' }}>
          <input
            type="checkbox"
            checked={allowLive}
            disabled={inFlight}
            onChange={(e) => send({ action: 'allow_live', value: e.target.checked })}
          />
          allow live
          {loadingFor('allow_live') && <Spinner color={T.warn} size={9} />}
        </label>
      </div>

      {/* paper balance */}
      <div style={{ borderTop: `1px solid ${T.gridline}`, paddingTop: 10, display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          <Stat label="paper equity" value={money(equity)} color={T.text} />
          <Stat label="paper cash" value={money(cash)} color={T.muted} />
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <input
            type="number"
            value={balanceInput}
            onChange={(e) => setBalanceInput(e.target.value)}
            placeholder="amount"
            disabled={inFlight}
            style={{
              background: T.panel2,
              color: T.text,
              border: `1px solid ${T.border}`,
              borderRadius: 8,
              padding: '7px 10px',
              fontSize: 13,
              width: 120,
            }}
          />
          <ActionButton onClick={setBalance} disabled={inFlight} loading={loadingFor('set_balance')} color={T.accent}>Set</ActionButton>
          <ActionButton onClick={topUp} disabled={inFlight} loading={loadingFor('top_up')} color={T.good}>Top-up</ActionButton>
          <ActionButton onClick={resetWallet} disabled={inFlight} loading={loadingFor('reset_wallet')} color={T.warn}>Reset</ActionButton>
        </div>
      </div>
    </div>
  )
}

// ---- main panel ---------------------------------------------------------------

export default function OnlineControlPanel({ intervalMs = 4000, marketList = MARKETS }) {
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)
  const [busy, setBusy] = useState(null) // market name in flight, or 'panic', or null
  const [pendingAction, setPendingAction] = useState(null) // action string of the in-flight click
  const [lastResult, setLastResult] = useState(null)
  const [stamp, setStamp] = useState(null)
  const aliveRef = useRef(true)

  const refresh = async () => {
    try {
      const data = await getJSON(STATUS_URL)
      if (!aliveRef.current) return
      setStatus(data)
      setErr(null)
      setStamp(new Date())
    } catch (e) {
      if (!aliveRef.current) return
      setErr(String(e.message || e))
    } finally {
      if (aliveRef.current) setLoading(false)
    }
  }

  useEffect(() => {
    aliveRef.current = true
    refresh()
    const timer = setInterval(refresh, intervalMs)
    return () => {
      aliveRef.current = false
      clearInterval(timer)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intervalMs])

  // POST a control action, then refresh. busyKey marks which control is in flight.
  const control = async (body, busyKey) => {
    setBusy(busyKey)
    setPendingAction(body.action) // remember which button to spin
    try {
      const r = await fetch(CONTROL_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      const data = await r.json()
      if (!aliveRef.current) return
      // GET /status is flat {markets,...}; POST /control returns {ok, action, status:{markets,...}}
      const newStatus = data && data.status && data.status.markets ? data.status
        : (data && data.markets ? data : null)
      if (newStatus) setStatus(newStatus) // reflect the new state immediately (no 4s wait)
      // honest toast: a rejected switch (e.g. REAL without allow_live+confirm) returns ok:false
      const ok = data && data.ok !== false
      const label = `${body.action}${body.market ? ' · ' + body.market : ''}`
      setLastResult({ ok, ts: new Date(),
        text: ok ? `${label} ✓` : `${label} rejected: ${data.reason || 'not allowed'}` })
      setErr(null)
    } catch (e) {
      if (!aliveRef.current) return
      setLastResult({ ok: false, text: `${body.action} failed: ${String(e.message || e)}`, ts: new Date() })
    } finally {
      if (aliveRef.current) {
        setBusy(null)
        setPendingAction(null)
        refresh()
      }
    }
  }

  const onMarketAction = (body) => control(body, body.market)

  const panic = () => {
    if (window.confirm('PANIC — halt ALL markets immediately?\n\nThis stops every market and goes flat/reduce-only. Continue?')) {
      control({ action: 'panic' }, 'panic')
    }
  }

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
          <span style={{ fontSize: 22, opacity: 0.6 }}>🎛</span>
          <div style={{ marginTop: 8 }}>loading online control…</div>
        </div>
      </div>
    )
  }

  return (
    <div style={wrap}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12, flexWrap: 'wrap' }}>
        <span style={{ fontWeight: 700, fontSize: 16, color: T.text }}>🎛 Online Control</span>
        <span style={{ fontSize: 11, color: T.muted }}>Phase O5 · live trading switchboard</span>
        <div style={{ flex: 1 }} />
        {lastResult && (
          <Badge
            text={lastResult.text}
            color={lastResult.ok ? T.good : T.bad}
          />
        )}
        {stamp && <span style={{ fontSize: 10, color: T.muted }}>updated {stamp.toLocaleTimeString()}</span>}
        <button
          onClick={panic}
          disabled={busy === 'panic'}
          style={{
            background: busy === 'panic' ? T.panel2 : T.bad,
            color: busy === 'panic' ? T.muted : '#0b0e14',
            border: `1px solid ${T.bad}`,
            borderRadius: 8,
            padding: '8px 16px',
            cursor: busy === 'panic' ? 'not-allowed' : 'pointer',
            fontSize: 13,
            fontWeight: 800,
            letterSpacing: 0.5,
            opacity: busy === 'panic' ? 0.6 : 1,
            display: 'inline-flex',
            alignItems: 'center',
            gap: 7,
          }}
        >
          {busy === 'panic' && <Spinner color={T.muted} />}
          🛑 PANIC (halt all)
        </button>
      </div>

      {err && (
        <div style={{ color: T.warn, fontSize: 12, marginBottom: 10 }}>
          online-control feed: {err}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: `repeat(${marketList.length > 1 ? 2 : 1}, minmax(0, 1fr))`, gap: 12 }}>
        {marketList.map((m) => (
          <MarketCard
            key={m}
            market={m}
            status={status}
            busy={busy === m}
            pending={busy === m ? pendingAction : null}
            onAction={onMarketAction}
          />
        ))}
      </div>
    </div>
  )
}
