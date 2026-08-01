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
import ScorecardPanel from './ScorecardPanel.jsx'
import DirectionTruthPanel from './DirectionTruthPanel.jsx'
import PostmortemPanel from './PostmortemPanel.jsx'
import ClosedTradesTable from './ClosedTradesTable.jsx'
import PnlStrip from './PnlStrip.jsx'
import PracticePanel from './PracticePanel.jsx'
import PracticeNotebookPanel from './PracticeNotebookPanel.jsx'
import TradeDrilldown from './TradeDrilldown.jsx'
import ConfidenceHeatmap from './ConfidenceHeatmap.jsx'
import ContextPanel from './ContextPanel.jsx'
import PsychologyPanel from './PsychologyPanel.jsx'
import FreqtradeCryptoPanel from './FreqtradeCryptoPanel.jsx'
import CryptoMarketsPanel from './CryptoMarketsPanel.jsx'
import StrategyLibraryPanel from './StrategyLibraryPanel.jsx'
import FoundryPanel from './FoundryPanel.jsx'
import BrokerSensePanel from './BrokerSensePanel.jsx'
import XRayPanel from './XRayPanel.jsx'
import LiveBrowserPanel from './LiveBrowserPanel.jsx'
import HumanHandoffPanel from './HumanHandoffPanel.jsx'
import BinanceEdgePanel from './BinanceEdgePanel.jsx'
import BrokerFeaturesPanel from './BrokerFeaturesPanel.jsx'
import SegmentFocusPanel from './SegmentFocusPanel.jsx'
import TradeColumnsPanel from './TradeColumnsPanel.jsx'
import StrategyGeneratorsPanel from './StrategyGeneratorsPanel.jsx'
import ExchangeVenuesPanel from './ExchangeVenuesPanel.jsx'
// Brain panels (BrainPanel, WorldModel, Metacognition, Debate, Hypotheses, Evolve,
// BrainLearning/Ultra/Ops, GoalOps, DecisionMemory, ComputerUse, Ocular, BrainMirror,
// AppSchool, Connectivity, ConceptSpace, LLMProviders, BrainOutcomeNet) moved to the
// unified Brain page (src/BrainPage.jsx) — owner order 2026-07-12: ONE brain page.

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
      {/* Brain Sandbox retired from the UI 2026-07-06 — the owner graduated to Freqtrade
          (CRYPTO_ENGINE=freqtrade). SandboxPanel.jsx is kept in the tree and can be re-shown
          by restoring this Card + setting CRYPTO_ENGINE=sandbox. Crypto trading now runs on the
          Freqtrade engine; the Strategy Generators + Freqtrade panels below are the live view. */}

      <Card title="Strategy Generators — the brain's strategy creator" hint="DEAP genetic evolver + 6 SOTA generators (LLM-mutation · gplearn+PySR symbolic regression · pyribs quality-diversity · formulaic-alpha mining · Optuna · RD-Agent) → one overfit + family-wise gate → skill library → the brain trades the best survivor">
        <StrategyGeneratorsPanel />
      </Card>

      <Card title="Segment focus — one switch for the whole brain" hint="turn any crypto/NSE segment on or off · gates entries, screening, broker pickers, and strategy research everywhere the brain focuses">
        <SegmentFocusPanel />
      </Card>

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

      <Card title="Segment Scorecard — NSE · Crypto · Prediction" hint="per-segment score: total profit (closed) + current profit (open) — same sources as the tables below">
        <ScorecardPanel scorecard={data?.scorecard} />
      </Card>

      <Card title="🎯 Direction Truth — who is actually right about direction (Pillar 27)" hint="every directional decision (taken AND skipped) labeled with what price really did at 15m/1h/4h · Wilson CIs · worst sources are Mirror-Gate invert candidates">
        <DirectionTruthPanel />
      </Card>

      <Card title="🔬 Trade Post-Mortem & Excursion — why trades win vs lose + ideal entry" hint="subgroup discovery over every closed trade's entry context: the patterns winners share vs losers · plus MFE/MAE peak timing and how much better the entry could have been per symbol · feeds size + entry back into the funnel when FEEDBACK LIVE">
        <PostmortemPanel />
      </Card>

      <Card title="📓 Practice Notebook — the brain's rough / calculating paper" hint="every pick waits on the rough page until price double-confirms the predicted direction, THEN opens (answer sheet) · went-the-other-way picks go to the mistakes book with the diagnosed cause and the wrong lens loses trust · practises + grades on all ~500 symbols">
        <PracticeNotebookPanel />
      </Card>

      <Card title="Open Trades — unified (paper loop + Freqtrade + OpenAlgo)" hint={`${(openT.rows || []).length} live · ${(openT.columns || []).length} cols · Trade Type column shows the engine`}
        right={<button style={{ ...btn, color: '#ff6b6b', padding: '4px 10px', fontSize: 12 }}
          onClick={() => {
            if (!window.confirm('Close ALL open trades on every engine (paper loop + Freqtrade + OpenAlgo sandbox)?')) return
            postControl({ action: 'close_all' })
              .then((r) => alert(r?.detail || JSON.stringify(r)))
              .catch((e) => alert(`close_all failed: ${e}`))
          }}>✖ Close All</button>}>
        <OpenTradesPanel columns={openT.columns || []} rows={openT.rows || []} totals={openT.totals} />
      </Card>

      <Card title="Closed Trades — unified (journal + Freqtrade + OpenAlgo)" hint={`${(closedT.rows || []).length} trades · ${(closedT.columns || []).length}-col journal · click a row to drill down`}>
        <ClosedTradesTable columns={closedT.columns || []} rows={closedT.rows || []} totals={closedT.totals}
          onRowClick={(row) => setDrill(row)} />
      </Card>

      <Card title="Per-trade P&L (CANON-56)" hint="per-trade P&L strip + distribution histogram — real closed trades only">
        <PnlStrip trades={closedT.rows || []} />
      </Card>

      <Card title="NSE Practice — brain trades historic data" hint="same cortex as crypto, replayed on real 2017-2021 NSE 1m history · isolated practice ledger">
        <PracticePanel />
      </Card>

      <Card title="Strategy Library (institutional templates)" hint="239 named strategies · OOS leaderboard · evolution gated OFF">
        <StrategyLibraryPanel data={data?.strategyLibrary} />
      </Card>

      <Card title="Strategy Foundry — brain discovers & keeps the best" hint="institutional catalog per segment · unique id · online research · real-performance leaderboard · promote best">
        <FoundryPanel />
      </Card>

      <Card title="Exchange Data Venues — multi-venue ban-proofing" hint="per-venue calls · errors · request budget · ban cooldown across binance/bybit/okx/kucoin — real market-data pool telemetry">
        <ExchangeVenuesPanel />
      </Card>

      <Card title="Trader Psychology — order-book depth crowd signal" hint="OBI · OFI · Stoikov microprice · whale walls · fear (spread/λ/VPIN) — live entry signal + journal columns the brain learns from">
        <PsychologyPanel />
      </Card>

      <Card title="Broker-Sense Funnel — trades through the broker web apps" hint="their screeners narrow the universe · candle screenshots → CNN direction · screen-mirror bid/ask (API fail-safe) · APIs execute only · paper-first">
        <BrokerSensePanel />
      </Card>

      <Card title="Stock X-Ray — full per-stock picture on trade-open" hint="fused snapshot: OpenAlgo multi-TF candles+indicators, 20-level depth+imbalance, circuit bands, computed demand/supply zones + free-eyes Upstox visual · auto-captured when a trade opens · type a symbol to X-ray any stock">
        <XRayPanel />
      </Card>

      <Card title="Live browser — connect your broker account" hint="a real browser streamed here so YOU solve the login captcha/OTP that automation can't · your clicks+typing drive the page · Save session → the brain reads your account headless after">
        <LiveBrowserPanel broker="binance" />
      </Card>

      <Card title="Binance Edge — compute offloaded to Binance" hint="data the brain now READS from Binance instead of computing locally (frees CPU for ML) · all-market websocket mirror (funding/movers/liquidations pushed to RAM) · funding extremes · live listing catalysts · state-file-only route the funnel refreshes ~10s">
        <BinanceEdgePanel />
      </Card>

      <Card title="Human Handoff — solve the broker's CAPTCHA" hint="when a brain browser hits a human-only security check (Binance slide puzzle / image CAPTCHA) it PAUSES that browser and hands you interactive control · Take control → drag the slider yourself → automation auto-resumes the instant it clears · also pings Telegram">
        <HumanHandoffPanel />
      </Card>

      <Card title="Broker built-in pickers — Binance" hint="USE the app's OWN screeners (top movers/gainers/funding/liquidation) as ready-made candidate sources · read in parallel · brain learns which picker predicts winners (stacking) · read-only, no re-computing the universe">
        <BrokerFeaturesPanel broker="binance" />
      </Card>

      <Card title="Broker built-in pickers — Upstox" hint="Upstox's OWN pickers (momentum gainers 1m/3m/5m, trending, trending<500, top gainers/losers, Algovers, Chart360, Scalper, OI analysis, News) as candidate sources · brain learns each one's hit-rate · read-only">
        <BrokerFeaturesPanel broker="upstox" />
      </Card>

      <Card title="Self-growing trade columns — discovered on the apps" hint="new data fields the App Driving School found on the broker apps (noise-filtered, cross-checked vs the journal) · Accept → it joins the open/closed trade tables">
        <TradeColumnsPanel />
      </Card>

      <TradeDrilldown trade={drill} onClose={() => setDrill(null)} />
    </div>
  )
}
