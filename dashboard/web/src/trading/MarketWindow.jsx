// MarketWindow — the NSE / Crypto pop-out window content (T6 §3, §4). Opened via
// window.open(`?win=nse|crypto`); App.jsx renders this full-screen when ?win is set.
// A focused market workspace: chart + order flow + (NSE) options chain + trades,
// fed by the same useTrading() hook. Honest: shows real endpoint data, demo-labelled.
import React, { useState } from 'react'
import { T, pnlColor } from './theme.js'
import { useTrading } from './useTrading.js'
import PriceChart from './PriceChart.jsx'
import OrderFlowMap from './OrderFlowMap.jsx'
import OpenTradesPanel from './OpenTradesPanel.jsx'
import ClosedTradesTable from './ClosedTradesTable.jsx'
import TradeDrilldown from './TradeDrilldown.jsx'
import OnlineControlPanel from './OnlineControlPanel.jsx'

function Card({ title, hint, children }) {
  return (
    <div style={{ background: T.panel, border: `1px solid ${T.border}`, borderRadius: 10, padding: 12 }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'baseline' }}>
        <h2 style={{ margin: 0, fontSize: 14, color: T.text }}>{title}</h2>
        {hint && <span style={{ color: T.muted, fontSize: 11 }}>{hint}</span>}
      </div>
      <div style={{ marginTop: 8 }}>{children}</div>
    </div>
  )
}

function OptionsChainMini({ options }) {
  const s = options || {}
  if (s.error) return <div style={{ color: T.muted, fontSize: 12 }}>options feed unavailable</div>
  const rows = [
    ['ATM strike', s.atm_strike], ['ATM IV', s.atm_iv], ['Max Pain', s.max_pain],
    ['PCR (OI)', s.pcr_oi], ['GEX regime', s.gex?.regime], ['Zero-gamma', s.gex?.zero_gamma],
  ]
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, color: T.text }}>
      <tbody>
        {rows.map(([k, v]) => (
          <tr key={k} style={{ borderBottom: `1px solid ${T.gridline}` }}>
            <td style={{ padding: '5px 6px', color: T.muted }}>{k}</td>
            <td style={{ padding: '5px 6px', textAlign: 'right' }}>
              {v == null ? '—' : (typeof v === 'number' ? v.toFixed(2) : String(v))}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export default function MarketWindow({ market = 'crypto' }) {
  const { data } = useTrading(4000)
  const [drill, setDrill] = useState(null)
  const isNSE = market === 'nse'
  const symbol = isNSE ? 'NIFTY' : 'BTCUSDT'
  const closedT = data.closedTrades || {}
  const openT = data.openTrades || {}

  return (
    <div style={{ background: T.bg, minHeight: '100vh', padding: 16, color: T.text,
      fontFamily: 'system-ui, sans-serif' }}>
      <h1 style={{ fontSize: 18, margin: '0 0 12px' }}>
        {isNSE ? 'NSE' : 'Crypto'} Window · {symbol}
        <span style={{ color: T.muted, fontSize: 12, marginLeft: 8 }}>live workspace</span>
      </h1>

      <Card title="Online Control (Start/Stop · Paper/Real · Balance)">
        <OnlineControlPanel marketList={[isNSE ? 'NSE' : 'CRYPTO']} />
      </Card>
      <div style={{ height: 12 }} />

      <div style={{ display: 'grid', gridTemplateColumns: isNSE ? '2fr 1fr 1fr' : '2fr 1fr',
        gap: 12, marginBottom: 12 }}>
        <Card title="Chart"><PriceChart symbol={symbol} height={340} /></Card>
        <Card title="Order Flow"><OrderFlowMap symbol={symbol} height={340} /></Card>
        {isNSE && <Card title="Options Chain" hint="T4 analytics">
          <OptionsChainMini options={data.options} />
        </Card>}
      </div>

      <div style={{ marginBottom: 12 }}>
        <Card title="Open Trades" hint={`${(openT.rows || []).length} live`}>
          <OpenTradesPanel columns={openT.columns || []} rows={openT.rows || []} />
        </Card>
      </div>

      <Card title="Closed Trades" hint="click a row to drill down">
        <ClosedTradesTable columns={closedT.columns || []} rows={closedT.rows || []}
          onRowClick={(row) => setDrill(row)} />
      </Card>

      <TradeDrilldown trade={drill} onClose={() => setDrill(null)} />
    </div>
  )
}
