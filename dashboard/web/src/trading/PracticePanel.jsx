// PracticePanel.jsx — brain practice mode on HISTORIC NSE data (user mandate
// 2026-07-04): the SAME cortex path as live crypto, replayed bar-by-bar over
// real 2017-2021 NSE 1-minute history (vendored dump) or Zerodha history when
// logged in. Real runs only — results come from trading/practice.py reports.
import { useEffect, useState } from 'react'
import { T } from './theme.js'

const fmtPct = (v) => (v == null ? '—' : `${(v * 100).toFixed(1)}%`)

export default function PracticePanel() {
  const [data, setData] = useState(null)
  const [sym, setSym] = useState('RELIANCE')
  const [bars, setBars] = useState(1200)
  const [msg, setMsg] = useState(null)

  const load = () => fetch('/api/trading/practice').then((r) => r.json())
    .then(setData).catch(() => {})
  useEffect(() => { load(); const t = setInterval(load, 15000); return () => clearInterval(t) }, [])

  const start = async () => {
    setMsg('starting…')
    try {
      const r = await fetch('/api/trading/practice/start', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol: sym, interval: '15m', bars, explore: true }),
      })
      const j = await r.json()
      setMsg(j.note || (j.started ? 'started' : 'not started'))
      load()
    } catch (e) { setMsg(`failed: ${e}`) }
  }

  const runs = data?.runs || []
  const symbols = data?.nse_symbols || []
  const cell = { padding: '3px 8px', fontSize: 11.5, borderBottom: `1px solid ${T.border}` }
  return (
    <div style={{ background: T.panel, border: `1px solid ${T.border}`, borderRadius: 8,
      padding: '10px 12px', color: T.text, fontFamily: 'system-ui, sans-serif' }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <b>NSE Practice (historic replay)</b>
        <select value={sym} onChange={(e) => setSym(e.target.value)}
          style={{ background: T.panel2, color: T.text, border: `1px solid ${T.border}`,
            borderRadius: 6, padding: '3px 6px', fontSize: 12 }}>
          {(symbols.length ? symbols : ['RELIANCE']).map((s) => <option key={s}>{s}</option>)}
        </select>
        <input type="number" value={bars} min={300} max={5000}
          onChange={(e) => setBars(+e.target.value)}
          style={{ width: 74, background: T.panel2, color: T.text,
            border: `1px solid ${T.border}`, borderRadius: 6, padding: '3px 6px', fontSize: 12 }} />
        <button onClick={start} disabled={data?.running}
          style={{ background: T.accent, color: '#0b0f18', border: 'none', borderRadius: 6,
            padding: '4px 12px', fontWeight: 700, cursor: 'pointer', fontSize: 12 }}>
          {data?.running ? 'running…' : '▶ Practice'}
        </button>
        {msg && <span style={{ fontSize: 11, color: T.muted }}>{msg}</span>}
      </div>
      <div style={{ fontSize: 10.5, color: T.muted, margin: '4px 0 8px' }}>
        Same cortex as live crypto (28-feature bus, reflex, risk sizing) on real 15m history
        (2017-2021 dump · {symbols.length} symbols · Zerodha-fresh after login). Explore mode:
        looser abstention so the brain takes trades and LEARNS (practice trust ledger, isolated).
      </div>
      {runs.length === 0
        ? <div style={{ fontSize: 12, color: T.muted }}>no practice runs yet — press ▶ Practice.</div>
        : (
          <table style={{ borderCollapse: 'collapse', width: '100%' }}>
            <thead><tr>
              {['run', 'symbol', 'trades', 'win rate', 'total return', 'sharpe'].map((h) => (
                <th key={h} style={{ ...cell, color: T.muted, textAlign: 'left',
                  textTransform: 'uppercase', fontSize: 9.5 }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.run_id}>
                  <td style={cell}>{r.run_id.split('_').slice(-1)[0]}</td>
                  <td style={cell}>{r.symbol}</td>
                  <td style={cell}>{r.n_trades}</td>
                  <td style={cell}>{fmtPct(r.win_rate)}</td>
                  <td style={{ ...cell, color: (r.total_return ?? 0) >= 0 ? T.good : T.bad }}>
                    {fmtPct(r.total_return)}</td>
                  <td style={cell}>{r.sharpe_naive ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
    </div>
  )
}
