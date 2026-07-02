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
import BrainOutcomeNet from './BrainOutcomeNet.jsx'
import WorldModelPanel from './WorldModelPanel.jsx'
import HypothesesPanel from './HypothesesPanel.jsx'
import EvolvePanel from './EvolvePanel.jsx'
import FreqtradeCryptoPanel from './FreqtradeCryptoPanel.jsx'
import CryptoMarketsPanel from './CryptoMarketsPanel.jsx'
import StrategyLibraryPanel from './StrategyLibraryPanel.jsx'
import FoundryPanel from './FoundryPanel.jsx'
import BrainLearningPanel from './BrainLearningPanel.jsx'
import ComputerUsePanel from './ComputerUsePanel.jsx'

function Card({ title, hint, children, right }) {
  return (
    <div data-card style={{ background: T.panel, border: `1px solid ${T.border}`, borderRadius: 10, padding: 14 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
        <h2 style={{ margin: 0, fontSize: 15, color: T.text, fontWeight: 700, letterSpacing: 0.2 }}>{title}</h2>
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

  // Shared POST helper for the online-control endpoint (same surface OnlineControlPanel
  // uses internally). StrategyControls posts {action:'set_strategy', ...} through this.
  const postControl = (body) =>
    fetch('/api/trading/online/control', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }).then((r) => r.json())

  const btn = {
    background: T.panel2, color: T.accent, border: `1px solid ${T.border}`,
    borderRadius: 8, padding: '7px 12px', cursor: 'pointer', fontSize: 13,
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <TickerTape tickers={tickers} />

      {err && <div style={{ color: T.warn, fontSize: 12 }}>trading feed: {err}</div>}

      <div style={{ display: 'flex', gap: 10 }}>
        {/* NSE controls live INSIDE OpenAlgo now (/paper). This entry opens that page
            rather than the old in-dash NSE control window. Crypto is independent and
            unchanged — its own workspace below. */}
        <button style={btn} onClick={() => window.open('/auto-trading', 'nse-openalgo')}>🧪 NSE Auto Trading (OpenAlgo)</button>
        <button style={btn} onClick={() => openMarketWindow('crypto')}>↗ Open Crypto Window</button>
      </div>

      {/* Online Control panel removed — NSE paper start/stop/segments/wallet now live
          in OpenAlgo (/paper page); crypto controls live in the Freqtrade panel below.
          This kills the duplicated start/stop clusters the operator flagged. */}
      <Card title="Crypto Markets — live screener (brain pick universe)" hint="Binance-style: icon · segment · live price · 24h% · volatility · funding — sort by volume / movers / volatility / funding">
        <CryptoMarketsPanel />
      </Card>

      <Card title="Freqtrade Crypto — trades + controls" hint="open/closed (capital · P&L USDT · peak MFE/MAE · leverage) + paper balance / max trades / stake / leverage / spot↔futures">
        <FreqtradeCryptoPanel />
      </Card>

      {/* Watchlist/Screener + Strategy & Sizing cards removed — duplicated controls now
          live in OpenAlgo's /paper page (NSE) and the Freqtrade panel (crypto); the
          crypto screener remains as the Crypto Markets panel above. */}

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

      <Card title="Open Trades — unified (paper loop + Freqtrade + OpenAlgo)" hint={`${(openT.rows || []).length} live · ${(openT.columns || []).length} cols · Trade Type column shows the engine`}>
        <OpenTradesPanel columns={openT.columns || []} rows={openT.rows || []} totals={openT.totals} />
      </Card>

      <Card title="Closed Trades — unified (journal + Freqtrade + OpenAlgo)" hint={`${(closedT.rows || []).length} trades · ${(closedT.columns || []).length}-col journal · click a row to drill down`}>
        <ClosedTradesTable columns={closedT.columns || []} rows={closedT.rows || []} totals={closedT.totals}
          onRowClick={(row) => setDrill(row)} />
      </Card>

      <Card title="Strategy Library (institutional templates)" hint="239 named strategies · OOS leaderboard · evolution gated OFF">
        <StrategyLibraryPanel data={data?.strategyLibrary} />
      </Card>

      <Card title="Strategy Foundry — brain discovers & keeps the best" hint="institutional catalog per segment · unique id · online research · real-performance leaderboard · promote best">
        <FoundryPanel />
      </Card>

      <Card title="Brain Learning & Web — reads, browses, self-evaluates" hint="reads books/papers → KnowledgeBrain · read-only web screening + Google gap-browse · answer login requests · ephemeral activity">
        <BrainLearningPanel />
      </Card>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
        <Card title="AI Brain (T8)" hint="evolution · self-eval · skills · end-to-end decision">
          <BrainPanel />
        </Card>
        <Card title="Brain Outcome Net" hint="trade rows → node network → win-prob / verdict">
          <BrainOutcomeNet data={data?.brainPredict} />
        </Card>
      </div>

      <Card title="Imagination — World-Model + MuZero planning" hint="learned market dynamics · MCTS plans entry/direction/stop/trailing in imagined R">
        <WorldModelPanel />
      </Card>

      <Card title="Hypothesis Ledger — AI-Scientist research loop" hint="propose → experiment on the journal → Bayesian credence → confirm/refute">
        <HypothesesPanel />
      </Card>

      <Card title="Self-Evolving Loop — lifelong strategy evolution" hint="evolve → admit guardrail-passed winners into the growing skill library (gated OFF · library-first)">
        <EvolvePanel />
      </Card>

      <Card title="Computer-Use Agent — sees & operates the dashboards" hint="reads panels/charts/buttons (own + Freqtrade/FreqUI), presses them paper-first, experiments, reflects (Reflexion) & grows a skill library (Voyager)">
        <ComputerUsePanel />
      </Card>

      <TradeDrilldown trade={drill} onClose={() => setDrill(null)} />
    </div>
  )
}
