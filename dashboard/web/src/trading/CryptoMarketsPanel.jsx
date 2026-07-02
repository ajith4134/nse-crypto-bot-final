// CryptoMarketsPanel.jsx — Binance-style live crypto markets / screener (the brain's pick universe).
// Coin icon + symbol + segment tag + 24h volume · live last price · 24h% · volatility · funding,
// sortable (volume / movers / gainers / losers / volatility / funding / price) + segment + search.
// Self-fetches /api/trading/crypto/markets (~8s). This is the ranked universe the brain screens.
import { useEffect, useRef, useState } from 'react'
import { T } from './theme.js'
import CoinDetailPanel from './CoinDetailPanel.jsx'

const URL = '/api/trading/crypto/markets'
const SORTS = [
  ['volume', 'Volume'], ['movers', 'Movers'], ['gainers', 'Gainers'], ['losers', 'Losers'],
  ['volatility', 'Volatility'], ['funding', 'Funding'], ['price', 'Price'],
]
const fmtV = (v) => (v >= 1e9 ? (v / 1e9).toFixed(2) + 'B' : v >= 1e6 ? (v / 1e6).toFixed(2) + 'M' : v >= 1e3 ? (v / 1e3).toFixed(1) + 'K' : Math.round(v))
const fmtP = (v) => (v == null ? '—' : Number(v).toLocaleString(undefined, { maximumFractionDigits: v < 1 ? 6 : 2 }))

function Icon({ base }) {
  const [bad, setBad] = useState(false)
  const c = '#' + ((base || 'X').charCodeAt(0) * 53 % 0xffffff).toString(16).padStart(6, '0')
  if (bad || !base) {
    return <span style={{ width: 22, height: 22, borderRadius: '50%', background: c, color: '#fff',
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: 9, fontWeight: 800 }}>{(base || '?').slice(0, 3)}</span>
  }
  return <img src={`https://assets.coincap.io/assets/icons/${base.toLowerCase()}@2x.png`} alt={base}
    onError={() => setBad(true)} style={{ width: 22, height: 22, borderRadius: '50%' }} />
}

export default function CryptoMarketsPanel() {
  const [rows, setRows] = useState([])
  const [segment, setSegment] = useState('perp')
  const [sort, setSort] = useState('volume')
  const [q, setQ] = useState('')
  const [stamp, setStamp] = useState(null)
  const [sel, setSel] = useState(null)
  const alive = useRef(true)

  const load = async () => {
    try {
      const r = await fetch(`${URL}?segment=${segment}&sort=${sort}&limit=80&q=${encodeURIComponent(q)}`)
      const j = await r.json()
      if (alive.current) { setRows(j.rows || []); setStamp(new Date()) }
    } catch { /* keep last */ }
  }
  useEffect(() => { alive.current = true; load(); const t = setInterval(load, 8000); return () => { alive.current = false; clearInterval(t) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [segment, sort, q])

  const tab = (active) => ({ padding: '4px 12px', borderRadius: 8, fontSize: 12, fontWeight: 700, cursor: 'pointer',
    border: `1px solid ${active ? T.accent : T.border}`, color: active ? (T.bg || '#0a0e14') : T.muted,
    background: active ? T.accent : 'transparent' })
  const wrap = { background: T.bg, border: `1px solid ${T.border}`, borderRadius: 12, padding: 14, color: T.text, fontFamily: 'system-ui, sans-serif', width: '100%', boxSizing: 'border-box' }
  const Th = ({ children, right }) => <th style={{ textAlign: right ? 'right' : 'left', padding: '6px 8px', fontSize: 10, color: T.muted, textTransform: 'uppercase', letterSpacing: 0.4, borderBottom: `1px solid ${T.border}` }}>{children}</th>

  return (
    <div style={wrap}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 10 }}>
        <span style={{ fontWeight: 700, fontSize: 16 }}>📈 Crypto Markets</span>
        <span onClick={() => setSegment('perp')} style={tab(segment === 'perp')}>USDⓈ-M Perp</span>
        <span onClick={() => setSegment('spot')} style={tab(segment === 'spot')}>Spot</span>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search coin"
          style={{ background: T.panel2, color: T.text, border: `1px solid ${T.border}`, borderRadius: 8, padding: '5px 10px', fontSize: 12, width: 130 }} />
        <div style={{ flex: 1 }} />
        {stamp && <span style={{ fontSize: 10, color: T.muted }}>{rows.length} · {stamp.toLocaleTimeString()}</span>}
      </div>
      {/* sort / filter chips */}
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
        {SORTS.map(([k, label]) => (
          <span key={k} onClick={() => setSort(k)} style={{ ...tab(sort === k), padding: '3px 10px', fontSize: 11 }}>{label}</span>
        ))}
      </div>
      <div style={{ overflowX: 'auto', maxHeight: 520, overflowY: 'auto' }}>
        <table style={{ borderCollapse: 'collapse', width: '100%' }}>
          <thead style={{ position: 'sticky', top: 0, background: T.bg }}><tr>
            <Th>Name / Vol</Th><Th right>Last</Th><Th right>24h %</Th><Th right>Volatility</Th>
            {segment === 'perp' && <Th right>Funding</Th>}
          </tr></thead>
          <tbody>
            {rows.map((r) => {
              const up = r.pct_24h >= 0
              return (
                <tr key={r.symbol} onClick={() => setSel(r.symbol)} className="mkt-row"
                  style={{ borderBottom: `1px solid ${T.gridline}`, cursor: 'pointer' }}>
                  <td style={{ padding: '6px 8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <Icon base={r.base} />
                      <div style={{ display: 'flex', flexDirection: 'column' }}>
                        <span style={{ fontSize: 13, fontWeight: 700 }}>
                          {r.display} <span style={{ fontSize: 9, color: T.muted, border: `1px solid ${T.border}`, borderRadius: 3, padding: '0 4px', marginLeft: 2 }}>{r.segment}</span>
                        </span>
                        <span style={{ fontSize: 10, color: T.muted }}>{r.base} · {fmtV(r.quote_volume)}</span>
                      </div>
                    </div>
                  </td>
                  <td style={{ textAlign: 'right', padding: '6px 8px', fontSize: 13, fontWeight: 600 }}>{fmtP(r.last)}</td>
                  <td style={{ textAlign: 'right', padding: '6px 8px' }}>
                    <span style={{ fontSize: 12, fontWeight: 700, color: '#fff', background: up ? T.good : T.bad, borderRadius: 5, padding: '2px 8px', display: 'inline-block', minWidth: 64, textAlign: 'center' }}>
                      {up ? '+' : ''}{Number(r.pct_24h).toFixed(2)}%</span>
                  </td>
                  <td style={{ textAlign: 'right', padding: '6px 8px', fontSize: 12, color: r.volatility > 20 ? T.warn : T.muted }}>{r.volatility}%</td>
                  {segment === 'perp' && <td style={{ textAlign: 'right', padding: '6px 8px', fontSize: 12, color: r.funding >= 0 ? T.good : T.bad }}>{r.funding}%</td>}
                </tr>
              )
            })}
            {rows.length === 0 && <tr><td colSpan={5} style={{ padding: 16, textAlign: 'center', color: T.muted }}>loading live markets…</td></tr>}
          </tbody>
        </table>
      </div>
      <div style={{ fontSize: 11, color: T.muted, marginTop: 8 }}>
        ℹ Click any row for the multi-timeframe chart + order book. The brain screens its picks from this ranked universe.
      </div>
      {sel && <CoinDetailPanel symbol={sel} onClose={() => setSel(null)} />}
    </div>
  )
}
