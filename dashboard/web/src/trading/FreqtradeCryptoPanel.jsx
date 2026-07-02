// FreqtradeCryptoPanel.jsx — crypto cockpit (Phase F+): full open/closed trade tables with all
// columns (capital placed, P&L in USDT, peak profit/loss = MFE/MAE, leverage) + adjustable
// controls (paper balance, max open trades, min capital/stake, leverage, spot/futures, paper/live).
// Self-fetches /api/trading/crypto/trades (~5s); controls POST /params + /mode (guarded restart).
import { useEffect, useRef, useState } from 'react'
import { T } from './theme.js'
import OrderFlowMap from './OrderFlowMap.jsx'
import OpenTradesPanel from './OpenTradesPanel.jsx'
import ClosedTradesTable from './ClosedTradesTable.jsx'

const TRADES_URL = '/api/trading/crypto/trades'
const MARKETS_URL = '/api/trading/crypto/markets'
const ORDERBOOK_URL = '/api/trading/orderbook'
// ccxt order book is spot; strip the futures ":USDT" settle suffix (BTC/USDT:USDT → BTC/USDT).
const spotSym = (s) => String(s || '').split(':')[0]

async function getJSON(u) { const r = await fetch(u); if (!r.ok) throw new Error('HTTP ' + r.status); return r.json() }
async function postJSON(u, b) {
  const r = await fetch(u, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) })
  return r.json()
}
const n2 = (v) => (v == null || isNaN(v) ? '—' : Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 }))
const pnlColor = (v) => (v > 0 ? T.good : v < 0 ? T.bad : T.muted)
// Fallback column list = first-seen union of row keys (only used if the backend doesn't
// supply the fixed schema). Prefer d.open_columns / d.closed_columns — those are FIXED
// (derived from the mappers/schema, not the data), so the column count stays stable as
// trades open/close, exactly like the dark dashboard.
function colsOf(rows) {
  const seen = []
  const set = new Set()
  for (const r of rows || []) for (const k of Object.keys(r || {})) if (!set.has(k)) { set.add(k); seen.push(k) }
  return seen
}

function TotalStat({ label, value, big }) {
  const v = Number(value) || 0
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 1, minWidth: 120 }}>
      <span style={{ fontSize: 9.5, color: T.muted, textTransform: 'uppercase', letterSpacing: 0.5 }}>{label}</span>
      <b style={{ fontSize: big ? 18 : 15, color: pnlColor(v) }}>
        {v >= 0 ? '+' : '−'}{Math.abs(v).toLocaleString(undefined, { maximumFractionDigits: 2 })}
      </b>
    </div>
  )
}

function NumCtl({ label, value, onApply, step = 1, suffix }) {
  const [v, setV] = useState('')
  useEffect(() => { setV(value ?? '') }, [value])
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <span style={{ fontSize: 10, color: T.muted, textTransform: 'uppercase', letterSpacing: 0.4 }}>{label}</span>
      <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
        <input type="number" step={step} value={v} onChange={(e) => setV(e.target.value)}
          style={{ width: 90, background: T.panel2, color: T.text, border: `1px solid ${T.border}`,
            borderRadius: 6, padding: '5px 7px', fontSize: 12 }} />
        {suffix && <span style={{ fontSize: 11, color: T.muted }}>{suffix}</span>}
        <button onClick={() => onApply(Number(v))} style={{ background: T.panel2, color: T.accent,
          border: `1px solid ${T.accent}`, borderRadius: 6, padding: '5px 9px', fontSize: 11, fontWeight: 700, cursor: 'pointer' }}>Set</button>
      </div>
    </div>
  )
}

export default function FreqtradeCryptoPanel() {
  const [d, setD] = useState(null)
  const [msg, setMsg] = useState(null)
  const [syms, setSyms] = useState(['BTC/USDT'])   // top-20 symbols for the depth selector
  const [obSym, setObSym] = useState('BTC/USDT')   // selected order-book symbol
  const [ob, setOb] = useState(null)               // live order book {bids, asks, ...}
  const [showReset, setShowReset] = useState(false)  // type-to-confirm closed-trade wipe
  const [resetText, setResetText] = useState('')
  const [resetting, setResetting] = useState(false)
  const alive = useRef(true)
  // Params the operator just Set, "pinned" briefly so an in-flight /trades poll (which may have
  // STARTED before the change persisted) can't resolve later and clobber the new value back to old.
  const pinned = useRef({})        // { field: value }
  const pinnedUntil = useRef(0)
  const load = async () => {
    try {
      const j = await getJSON(TRADES_URL)
      if (!alive.current) return
      // Keep just-Set params authoritative until the pin window expires.
      if (j && j.params && Date.now() < pinnedUntil.current) j.params = { ...j.params, ...pinned.current }
      else if (Date.now() >= pinnedUntil.current) pinned.current = {}
      setD(j)
    } catch (e) { if (alive.current) setD({ error: String(e.message || e) }) }
  }
  useEffect(() => { alive.current = true; load(); const t = setInterval(load, 5000); return () => { alive.current = false; clearInterval(t) } }, [])

  // Top-20 symbols by volume → the depth-ladder selector (refresh every 30s).
  useEffect(() => {
    let on = true
    const loadSyms = async () => {
      try {
        const j = await getJSON(`${MARKETS_URL}?sort=volume&limit=20`)
        const list = (j.rows || []).map((r) => spotSym(r.symbol)).filter(Boolean)
        if (on && list.length) { setSyms([...new Set(list)]); if (!list.includes(spotSym(obSym))) setObSym(list[0]) }
      } catch { /* keep BTC/USDT default */ }
    }
    loadSyms(); const t = setInterval(loadSyms, 30000)
    return () => { on = false; clearInterval(t) }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Live order book for the selected symbol (refresh every 3s; backend caches 2.5s).
  useEffect(() => {
    let on = true
    setOb(null)
    const loadOb = async () => {
      try {
        const j = await getJSON(`${ORDERBOOK_URL}?symbol=${encodeURIComponent(spotSym(obSym))}&market=CRYPTO`)
        if (on) setOb(j)
      } catch { if (on) setOb(null) }
    }
    loadOb(); const t = setInterval(loadOb, 3000)
    return () => { on = false; clearInterval(t) }
  }, [obSym])

  const p = (d && d.params) || {}
  const openR = (d && d.open) || []
  const closedR = (d && d.closed) || []
  const isFut = p.segment === 'futures'
  const isLive = p.dry_run === false

  const applyParam = async (body, label) => {
    setMsg({ ok: true, text: `${label} → applying (bot restart)…` })
    // Pin + optimistically show the new value so neither a slow restart NOR an in-flight /trades
    // poll (started before the change persisted) can snap the input back to the old value.
    pinned.current = { ...pinned.current, ...body }
    pinnedUntil.current = Date.now() + 20000
    setD((prev) => (prev ? { ...prev, params: { ...prev.params, ...body } } : prev))
    const r = await postJSON('/api/trading/crypto/params', body)
    // Reconcile with the server's persisted status (authoritative); keep it pinned a bit longer.
    if (r && r.status) {
      pinned.current = { ...pinned.current, ...r.status }
      pinnedUntil.current = Date.now() + 8000
      setD((prev) => (prev ? { ...prev, params: { ...prev.params, ...r.status } } : prev))
    }
    setMsg({ ok: r.ok !== false, text: r.ok !== false ? `${label} ✓` : `${label}: ${r.reason || 'failed'}` })
    setTimeout(load, 6000)
  }
  // Permanently wipe ALL closed-trade data (brain journal + Freqtrade closed paper trades) so the
  // brain stops learning on contaminated history. Type-to-confirm (must type RESET). Backs up first.
  const doReset = async () => {
    if (resetText.trim().toUpperCase() !== 'RESET') return
    setResetting(true)
    setMsg({ ok: true, text: 'Resetting closed trades…' })
    try {
      const r = await postJSON('/api/trading/closedtrades/reset', { confirm: resetText })
      if (r.ok) {
        setMsg({ ok: true, text: `Closed trades wiped ✓ journal ${r.journal_cleared ?? 0} · freqtrade ${r.freqtrade_deleted ?? 0} (backed up)` })
        setShowReset(false); setResetText('')
        setTimeout(load, 1500)
      } else {
        setMsg({ ok: false, text: `Reset failed: ${r.reason || 'error'}` })
      }
    } catch (e) {
      setMsg({ ok: false, text: `Reset failed: ${e.message || e}` })
    }
    setResetting(false)
  }
  const switchMode = async (body, label, confirm) => {
    if (confirm && !window.confirm(confirm)) return
    setMsg({ ok: true, text: `${label} → restarting…` })
    const r = await postJSON('/api/trading/crypto/mode', body)
    setMsg({ ok: r.ok !== false, text: r.ok !== false ? `${label} ✓` : `${label}: ${r.reason || 'refused'}` })
    setTimeout(load, 6000)
  }

  const wrap = { background: T.bg, border: `1px solid ${T.border}`, borderRadius: 12, padding: 14, color: T.text, fontFamily: 'system-ui, sans-serif', width: '100%', boxSizing: 'border-box' }
  const sumOpenPnl = openR.reduce((a, r) => a + (Number(r.unrealized_pnl_usdt) || 0), 0)
  const sumCapital = openR.reduce((a, r) => a + (Number(r.capital_usdt) || 0), 0)
  const sumClosedPnl = closedR.reduce((a, r) => a + (Number(r.net_pnl_crypto ?? r.net_pnl) || 0), 0)

  return (
    <div style={wrap}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 10 }}>
        <span style={{ fontWeight: 700, fontSize: 16 }}>⛓ Freqtrade Crypto</span>
        <span style={{ fontSize: 11, color: isLive ? T.bad : T.good, fontWeight: 700 }}>{isLive ? 'LIVE 💵' : 'PAPER'}</span>
        <span style={{ fontSize: 11, color: T.accent, fontWeight: 700 }}>{(p.segment || 'spot').toUpperCase()}</span>
        <div style={{ flex: 1 }} />
        {msg && <span style={{ fontSize: 11, color: msg.ok ? T.good : T.bad, border: `1px solid ${msg.ok ? T.good : T.bad}`, borderRadius: 4, padding: '2px 8px' }}>{msg.text}</span>}
      </div>

      {/* adjustable controls */}
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'flex-end', background: T.panel, border: `1px solid ${T.border}`, borderRadius: 10, padding: 12, marginBottom: 12 }}>
        <NumCtl label="Paper balance" value={p.paper_balance} step={1000} suffix="USDT" onApply={(v) => applyParam({ paper_balance: v }, 'Paper balance')} />
        <NumCtl label="Max open trades" value={p.max_open_trades} step={1} onApply={(v) => applyParam({ max_open_trades: v }, 'Max open')} />
        <NumCtl label="Min capital / trade" value={p.stake_amount} step={50} suffix="USDT" onApply={(v) => applyParam({ stake_amount: v }, 'Stake')} />
        <NumCtl label="Leverage" value={p.leverage} step={1} suffix="x" onApply={(v) => applyParam({ leverage: v }, 'Leverage')} />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          <span style={{ fontSize: 10, color: T.muted, textTransform: 'uppercase', letterSpacing: 0.4 }}>segment</span>
          <button onClick={() => switchMode({ segment: isFut ? 'spot' : 'futures' }, isFut ? '→ Spot' : '→ Futures', isFut ? null : 'Switch CRYPTO to FUTURES (perp, shorting)? Bot restarts.')}
            style={{ background: T.panel2, color: T.warn, border: `1px solid ${T.warn}`, borderRadius: 6, padding: '6px 10px', fontSize: 12, fontWeight: 700, cursor: 'pointer' }}>
            {isFut ? '→ Spot' : '→ Futures'}</button>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          <span style={{ fontSize: 10, color: T.muted, textTransform: 'uppercase', letterSpacing: 0.4 }}>mode</span>
          <button onClick={() => isLive ? switchMode({ mode: 'paper' }, '→ Paper') : switchMode({ mode: 'live', confirm: true }, '→ LIVE', 'Switch CRYPTO to LIVE (REAL MONEY)? Bot restarts and trades real funds.')}
            style={{ background: T.panel2, color: isLive ? T.good : T.bad, border: `1px solid ${isLive ? T.good : T.bad}`, borderRadius: 6, padding: '6px 10px', fontSize: 12, fontWeight: 700, cursor: 'pointer' }}>
            {isLive ? '→ Paper' : '→ LIVE 💵'}</button>
        </div>
      </div>

      {/* ORDER BOOK DEPTH — top-20 symbols, live L2 (red asks / green bids + buy/sell ratio) */}
      <div style={{ fontSize: 12, fontWeight: 700, color: T.muted, margin: '4px 0' }}>ORDER BOOK DEPTH</div>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
        {syms.map((s) => {
          const active = spotSym(s) === spotSym(obSym)
          return (
            <button key={s} onClick={() => setObSym(s)}
              style={{ background: active ? T.panel2 : 'transparent', color: active ? T.accent : T.muted,
                border: `1px solid ${active ? T.accent : T.border}`, borderRadius: 6, padding: '3px 8px',
                fontSize: 11, fontWeight: active ? 700 : 500, cursor: 'pointer' }}>{spotSym(s)}</button>
          )
        })}
      </div>
      <div style={{ marginBottom: 14 }}>
        <OrderFlowMap symbol={spotSym(obSym)} bids={ob?.bids} asks={ob?.asks} height={340} />
      </div>

      {/* TOTAL P&L (USDT) — open = unrealized, closed = realized net, plus combined */}
      <div style={{ display: 'flex', gap: 18, flexWrap: 'wrap', alignItems: 'center', background: T.panel2,
        border: `1px solid ${T.border}`, borderRadius: 10, padding: '8px 14px', marginBottom: 12,
        fontFamily: 'ui-monospace, Menlo, monospace' }}>
        <TotalStat label="Open uP&L (USDT)" value={sumOpenPnl} />
        <TotalStat label="Closed net P&L (USDT)" value={sumClosedPnl} />
        <TotalStat label="Total P&L (USDT)" value={sumOpenPnl + sumClosedPnl} big />
        <span style={{ fontSize: 11, color: T.muted }}>capital open {n2(sumCapital)} USDT · {openR.length} open · {closedR.length} closed</span>
      </div>

      {/* OPEN trades — full many-column journal (reuses the dark dashboard's OpenTradesPanel) */}
      <div style={{ fontSize: 12, fontWeight: 700, color: T.muted, margin: '4px 0' }}>
        OPEN ({openR.length}) · capital {n2(sumCapital)} USDT · uP&L <span style={{ color: pnlColor(sumOpenPnl) }}>{n2(sumOpenPnl)} USDT</span>
      </div>
      <div style={{ marginBottom: 14 }}>
        <OpenTradesPanel columns={(d && d.open_columns) || colsOf(openR)} rows={openR} />
      </div>

      {/* CLOSED trades — full journal (reuses the dark dashboard's ClosedTradesTable: sortable,
          column chooser + "show all", CSV export, P&L/side coloring). Uses the FIXED schema and
          the SAME default ~15-col subset as the dark dashboard (toggle "show all" for every
          column) — so the column count matches the dark dashboard and stays stable. */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', margin: '4px 0' }}>
        <span style={{ fontSize: 12, fontWeight: 700, color: T.muted }}>
          CLOSED ({closedR.length}) · net P&L <span style={{ color: pnlColor(sumClosedPnl) }}>{n2(sumClosedPnl)} USDT</span>
        </span>
        <div style={{ flex: 1 }} />
        {!showReset ? (
          <button onClick={() => setShowReset(true)} title="Permanently delete ALL closed trades (journal + Freqtrade) so the brain doesn't learn on contaminated data. Backs up first."
            style={{ background: 'transparent', color: T.bad, border: `1px solid ${T.bad}`, borderRadius: 6, padding: '4px 10px', fontSize: 11, fontWeight: 700, cursor: 'pointer' }}>
            ⟲ Reset closed trades
          </button>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: T.panel2, border: `1px solid ${T.bad}`, borderRadius: 8, padding: '5px 8px' }}>
            <span style={{ fontSize: 11, color: T.bad, fontWeight: 700 }}>Type RESET to wipe ALL closed trades (permanent, backed up):</span>
            <input autoFocus value={resetText} onChange={(e) => setResetText(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') doReset() }} placeholder="RESET"
              style={{ width: 90, background: T.panel, color: T.text, border: `1px solid ${T.border}`, borderRadius: 6, padding: '4px 7px', fontSize: 12 }} />
            <button onClick={doReset} disabled={resetting || resetText.trim().toUpperCase() !== 'RESET'}
              style={{ background: resetText.trim().toUpperCase() === 'RESET' ? T.bad : T.panel, color: resetText.trim().toUpperCase() === 'RESET' ? '#fff' : T.muted, border: `1px solid ${T.bad}`, borderRadius: 6, padding: '4px 10px', fontSize: 11, fontWeight: 700, cursor: resetting ? 'wait' : 'pointer' }}>
              {resetting ? 'Wiping…' : 'Confirm wipe'}
            </button>
            <button onClick={() => { setShowReset(false); setResetText('') }}
              style={{ background: 'transparent', color: T.muted, border: `1px solid ${T.border}`, borderRadius: 6, padding: '4px 10px', fontSize: 11, cursor: 'pointer' }}>Cancel</button>
          </div>
        )}
      </div>
      <ClosedTradesTable columns={(d && d.closed_columns) || colsOf(closedR)} rows={closedR} />
      {d && d.error && <div style={{ color: T.warn, fontSize: 12, marginTop: 8 }}>crypto trades: {d.error}</div>}
    </div>
  )
}
