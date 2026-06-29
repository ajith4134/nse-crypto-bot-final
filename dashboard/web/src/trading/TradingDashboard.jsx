// TradingDashboard — Dark-Pro trading view (T6). Composes the T6 components and
// feeds them from the single useTrading() hook (the only thing that touches the API).
// Honest wiring: every panel shows REAL endpoint data; demo endpoints are labelled.
import React, { useState } from 'react'
import { T } from './theme.js'
import { useTrading } from './useTrading.js'
import TickerTape from './TickerTape.jsx'
import PriceChart from './PriceChart.jsx'
import OrderFlowMap from './OrderFlowMap.jsx'
import OpenTradesPanel from './OpenTradesPanel.jsx'
import ClosedTradesTable from './ClosedTradesTable.jsx'
import TradeDrilldown from './TradeDrilldown.jsx'
import ConfidenceHeatmap from './ConfidenceHeatmap.jsx'
import ContextPanel from './ContextPanel.jsx'
import BrainPanel from './BrainPanel.jsx'
import OnlineControlPanel from './OnlineControlPanel.jsx'

function Card({ title, hint, children, right }) {
  return (
    <div style={{ background: T.panel, border: `1px solid ${T.border}`, borderRadius: 10, padding: 14 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
        <h2 style={{ margin: 0, fontSize: 15, color: T.text }}>{title}</h2>
        {hint && <span style={{ color: T.muted, fontSize: 12 }}>{hint}</span>}
        <div style={{ flex: 1 }} />
        {right}
      </div>
      <div style={{ marginTop: 10 }}>{children}</div>
    </div>
  )
}

function openMarketWindow(market) {
  const url = `${location.pathname}?win=${market}`
  window.open(url, `${market}-window`, 'width=1500,height=950,menubar=no,toolbar=no')
}

export default function TradingDashboard() {
  const { data, err } = useTrading(4000)
  const [drill, setDrill] = useState(null)

  const tickers = data.tickers?.tickers || []
  const openT = data.openTrades || {}
  const closedT = data.closedTrades || {}
  const confidence = data.confidence?.symbols || []
  const context = data.context || {}

  const btn = {
    background: T.panel2, color: T.accent, border: `1px solid ${T.border}`,
    borderRadius: 8, padding: '7px 12px', cursor: 'pointer', fontSize: 13,
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <TickerTape tickers={tickers} />

      {err && <div style={{ color: T.warn, fontSize: 12 }}>trading feed: {err}</div>}

      <div style={{ display: 'flex', gap: 10 }}>
        <button style={btn} onClick={() => openMarketWindow('nse')}>↗ Open NSE Window</button>
        <button style={btn} onClick={() => openMarketWindow('crypto')}>↗ Open Crypto Window</button>
      </div>

      <Card title="Online Control (Start/Stop · Paper/Real · Balance)" hint="Phase O5 — primary live-trading switchboard">
        <OnlineControlPanel />
      </Card>

      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 14 }}>
        <Card title="Price" hint="TradingView Lightweight Charts v5">
          <PriceChart symbol="BTC/USDT" candles={data?.candles?.candles} height={360} />
        </Card>
        <Card title="Order Flow" hint="depth + flow primitive">
          <OrderFlowMap symbol="BTC/USDT" bids={data?.orderbook?.bids} asks={data?.orderbook?.asks} height={360} />
        </Card>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
        <Card title="Brain Confidence" hint="per-symbol calibrated score">
          <ConfidenceHeatmap symbols={confidence} />
        </Card>
        <Card title="Market Context" hint="VIX · FII/DII · Fear & Greed">
          <ContextPanel context={context} />
        </Card>
      </div>

      <Card title="Open Trades" hint={`${(openT.rows || []).length} live · ${(openT.columns || []).length} cols`}>
        <OpenTradesPanel columns={openT.columns || []} rows={openT.rows || []} totals={openT.totals} />
      </Card>

      <Card title="Closed Trades" hint={`${(closedT.rows || []).length} trades · ${(closedT.columns || []).length}-col journal · click a row to drill down`}>
        <ClosedTradesTable columns={closedT.columns || []} rows={closedT.rows || []} totals={closedT.totals}
          onRowClick={(row) => setDrill(row)} />
      </Card>

      <Card title="AI Brain (T8)" hint="evolution · self-eval · skills · end-to-end decision">
        <BrainPanel />
      </Card>

      <TradeDrilldown trade={drill} onClose={() => setDrill(null)} />
    </div>
  )
}
