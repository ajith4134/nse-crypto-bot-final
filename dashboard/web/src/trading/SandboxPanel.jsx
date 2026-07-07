// SandboxPanel.jsx — the brain's FAST paper-trading sandbox. A lightweight simulator (reuses the
// real PaperEngine for fills/leverage/liquidation) where the brain opens trades instantly to LEARN
// quickly — no Freqtrade friction. Signal source is switchable: BRAIN (the real per-coin backtest ×
// brain-weight + cortex engine the live loop uses) or MOMENTUM (fast fallback). Honest label:
// LEARNING ONLY, not live-accurate; Freqtrade stays the faithful bridge to real money.
import { useEffect, useRef, useState } from 'react'
import { T } from './theme.js'

const API = '/api/trading/sandbox'
async function getJSON() { const r = await fetch(API); if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() }
async function post(b) { const r = await fetch(API, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }); return r.json() }

function Btn({ children, onClick, color, busy }) {
  const c = color || T.accent || '#5b9dff'
  return <button onClick={onClick} disabled={busy} style={{ background: T.panel2 || '#1a1f2b', color: busy ? T.muted : c, border: `1px solid ${c}`, borderRadius: 8, padding: '6px 12px', cursor: busy ? 'wait' : 'pointer', fontSize: 12, fontWeight: 700 }}>{children}</button>
}

function NumInput({ label, value, min, step, onSave, busy }) {
  const [v, setV] = useState(String(value))
  useEffect(() => { setV(String(value)) }, [value])
  const inp = { background: T.panel2 || '#1a1f2b', color: T.text, border: `1px solid ${T.border}`, borderRadius: 6, padding: '3px 6px', fontSize: 12, width: 90, outline: 'none' }
  const save = () => { const n = parseFloat(v); if (!isNaN(n) && n >= (min || 0)) onSave(n) }
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
      <span style={{ fontSize: 11, color: T.muted }}>{label}</span>
      <input style={inp} type="number" min={min} step={step || 1} value={v}
        onChange={e => setV(e.target.value)}
        onKeyDown={e => e.key === 'Enter' && save()}
        onBlur={save} />
    </span>
  )
}

export default function SandboxPanel({ intervalMs = 6000 }) {
  const [d, setD] = useState(null)
  const [err, setErr] = useState(null)
  const [busy, setBusy] = useState(false)
  const alive = useRef(true)

  const refresh = async () => { try { const x = await getJSON(); if (alive.current) { setD(x); setErr(null) } } catch (e) { if (alive.current) setErr(String(e.message || e)) } }
  useEffect(() => { alive.current = true; refresh(); const t = setInterval(refresh, intervalMs); return () => { alive.current = false; clearInterval(t) } }, [intervalMs])

  const act = async (op) => { setBusy(true); try { await post({ op }) } finally { if (alive.current) setBusy(false); refresh() } }
  const setMode = async (m) => { setBusy(true); try { await post({ op: 'set_mode', mode: m }) } finally { if (alive.current) setBusy(false); refresh() } }
  const setParam = async (key, val) => {
    setBusy(true)
    try { await post({ op: 'set_params', [key]: val }) } finally { if (alive.current) setBusy(false); refresh() }
  }

  const card = { background: T.panel, border: `1px solid ${T.border}`, borderRadius: 12, padding: 14 }
  if (err) return <div style={{ ...card, color: T.bad || '#ff6b6b' }}>Sandbox: {err}</div>
  if (!d) return <div style={{ ...card, color: T.muted }}>Loading sandbox…</div>

  const on = d.enabled
  const mode = d.signal_mode || 'brain'
  // P&L = equity (free + locked margin + unrealized) minus what we started with.
  // Using just `balance` would show -used_margin as a fake "loss" — it's margin reservation, not a loss.
  const equity = d.equity != null ? d.equity : (d.balance || 0) + (d.used_margin || 0)
  const pnl = equity - (d.starting_balance || 0)
  const open = d.open || []
  const dot = on ? (T.good || '#3ecf8e') : (T.muted || '#7a8699')
  const maxOpen = d.max_open === 'unlimited' ? 0 : (d.max_open || 0)

  return (
    <div style={card}>
      {/* header row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
        <div style={{ fontSize: 14, fontWeight: 800, color: T.text }}><span style={{ color: dot }}>●</span> Brain sandbox — fast paper learning</div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {/* signal source toggle — BRAIN (real engine) vs MOMENTUM (fast fallback) */}
          <div style={{ display: 'inline-flex', border: `1px solid ${T.border}`, borderRadius: 8, overflow: 'hidden' }}>
            {['brain', 'momentum'].map(m => (
              <button key={m} onClick={() => !busy && mode !== m && setMode(m)} disabled={busy}
                style={{ background: mode === m ? (T.accent || '#5b9dff') : (T.panel2 || '#1a1f2b'),
                  color: mode === m ? '#0b0e14' : T.muted, border: 'none', padding: '5px 10px',
                  cursor: busy ? 'wait' : 'pointer', fontSize: 11, fontWeight: 700, textTransform: 'capitalize' }}>{m}</button>
            ))}
          </div>
          {on ? <Btn onClick={() => act('disable')} busy={busy} color={T.bad || '#ff6b6b'}>Stop</Btn>
              : <Btn onClick={() => act('enable')} busy={busy} color={T.good || '#3ecf8e'}>Start trading</Btn>}
          <Btn onClick={() => act('reset')} busy={busy} color={T.muted}>Reset</Btn>
        </div>
      </div>
      {/* signal source line — which engine is picking coins + the last tick's honest note */}
      <div style={{ fontSize: 11, marginBottom: 4 }}>
        <span style={{ color: T.muted }}>Signal: </span>
        <b style={{ color: mode === 'brain' ? (T.accent || '#5b9dff') : (T.warn || '#e6b800') }}>
          {mode === 'brain' ? 'BRAIN — per-coin backtest × brain-weight + cortex' : 'MOMENTUM — top movers (fast fallback)'}</b>
        {d.brain_note ? <span style={{ color: T.muted }}> · {d.brain_note}</span> : null}
      </div>
      <div style={{ fontSize: 11, color: T.warn || '#e6b800', marginBottom: 10 }}>⚠️ {d.note}</div>

      {/* KPI row */}
      <div style={{ display: 'flex', gap: 18, marginBottom: 6, flexWrap: 'wrap', alignItems: 'baseline' }}>
        <div><span style={{ fontSize: 20, fontWeight: 800, color: (pnl >= 0 ? (T.good || '#3ecf8e') : (T.bad || '#ff6b6b')) }}>{pnl >= 0 ? '+' : ''}{pnl.toFixed(0)}</span> <span style={{ fontSize: 11, color: T.muted }}>USDT total P&L</span></div>
        <div><span style={{ fontSize: 16, fontWeight: 800, color: T.text }}>{d.open_trades}</span> <span style={{ fontSize: 11, color: T.muted }}>open ({d.max_open})</span></div>
        <div><span style={{ fontSize: 16, fontWeight: 800, color: T.text }}>{d.closed_count}</span> <span style={{ fontSize: 11, color: T.muted }}>closed · win {Math.round((d.win_rate || 0) * 100)}%</span></div>
        <div style={{ fontSize: 11, color: T.muted }}>cycles {d.cycles} · lev {d.leverage}×</div>
      </div>

      {/* wallet breakdown — every USDT explained */}
      <div style={{ fontSize: 11, color: T.muted, marginBottom: 10, display: 'flex', gap: 14, flexWrap: 'wrap' }}>
        <span>wallet <b style={{ color: T.text }}>{equity.toFixed(0)}</b> USDT</span>
        <span style={{ color: T.border }}>|</span>
        <span title="not in any trade">free <b style={{ color: T.text }}>{(d.balance || 0).toFixed(0)}</b></span>
        <span style={{ color: T.border }}>|</span>
        <span title="margin reserved for open positions — NOT a loss">locked in {d.open_trades} trades <b style={{ color: T.text }}>{(d.used_margin || 0).toFixed(0)}</b></span>
        <span style={{ color: T.border }}>|</span>
        <span>unrealized <b style={{ color: (d.unrealized_pnl || 0) >= 0 ? (T.good || '#3ecf8e') : (T.bad || '#ff6b6b') }}>{(d.unrealized_pnl || 0) >= 0 ? '+' : ''}{(d.unrealized_pnl || 0).toFixed(0)}</b></span>
        <span style={{ color: T.border }}>|</span>
        <span>realized <b style={{ color: (d.realized_pnl || 0) >= 0 ? (T.good || '#3ecf8e') : (T.bad || '#ff6b6b') }}>{(d.realized_pnl || 0) >= 0 ? '+' : ''}{(d.realized_pnl || 0).toFixed(0)}</b></span>
      </div>

      {/* editable params row */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 10, flexWrap: 'wrap', alignItems: 'center', padding: '8px 10px', background: T.panel2 || '#1a1f2b', borderRadius: 8, border: `1px solid ${T.border}` }}>
        <span style={{ fontSize: 11, fontWeight: 700, color: T.muted }}>Settings</span>
        <NumInput label="Wallet USDT" value={d.starting_balance || 100000} min={1000} step={1000}
          onSave={v => setParam('starting_balance', v)} busy={busy} />
        <NumInput label="Stake/trade USDT" value={d.stake || 200} min={10} step={10}
          onSave={v => setParam('stake', v)} busy={busy} />
        <NumInput label="Leverage ×" value={d.leverage || 5} min={1} step={1}
          onSave={v => setParam('leverage', v)} busy={busy} />
        <span style={{ fontSize: 10, color: T.muted }}>Enter or blur to apply · trades are unlimited</span>
      </div>

      <div style={{ fontSize: 12, fontWeight: 700, color: T.text, marginBottom: 4 }}>Open positions <span style={{ fontWeight: 400, color: T.muted, fontSize: 10 }}>· 🔒 lock only arms once peak ≥ 0.5% · negative trades exit via the −8% stop, not the tailgate</span></div>
      {open.length === 0
        ? <div style={{ fontSize: 12, color: T.muted }}>{on
            ? (mode === 'brain' ? 'The brain is scoring coins (per-coin backtest) — trades open when a strategy clears the gate…' : 'Opening momentum trades on the next tick…')
            : `Press "Start trading" — the ${mode} engine opens trades fast.`}</div>
        : (
          <div style={{ maxHeight: 220, overflowY: 'auto' }}>
            {open.slice(0, 25).map((t, i) => (
              <div key={i} style={{ borderTop: `1px solid ${T.border}`, padding: '4px 0', display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 12 }}>
                <span style={{ color: T.text }}>{t.symbol} <span style={{ color: t.side === 'long' ? (T.good || '#3ecf8e') : (T.bad || '#ff6b6b') }}>{t.side}</span>
                  {/* provenance: brain's chosen strategy (tag) + confidence — momentum shows the tag "momentum" */}
                  {t.tag ? <span style={{ color: T.muted, fontSize: 10 }}> · {t.tag}{t.conf != null ? ` (${Math.round(t.conf * 100)}%)` : ''}</span> : null}</span>
                <span style={{ color: (t.pnl_pct >= 0 ? (T.good || '#3ecf8e') : (T.bad || '#ff6b6b')) }}>{t.pnl_pct >= 0 ? '+' : ''}{t.pnl_pct}%
                  <span style={{ color: T.muted }}> · {t.tailgate_armed
                    ? <span style={{ color: t.exit_by === 'tailgate-pending' ? (T.warn || '#e6b800') : T.muted }}>🔒{t.tailgate_locked_pct}%{t.exit_by === 'tailgate-pending' ? ' ⏳exit next tick' : ''}</span>
                    : <span title="peak profit hasn't reached 0.5% — tailgate not armed; exits via −8% stop">🔓 not armed</span>
                  } · peak {t.peak_pct}%</span></span>
              </div>
            ))}
          </div>
        )}
    </div>
  )
}
