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
import ClosedTradesTable from './ClosedTradesTable.jsx'
import PnlStrip from './PnlStrip.jsx'
import PracticePanel from './PracticePanel.jsx'
import TradeDrilldown from './TradeDrilldown.jsx'
import ConfidenceHeatmap from './ConfidenceHeatmap.jsx'
import ContextPanel from './ContextPanel.jsx'
import BrainPanel from './BrainPanel.jsx'
import BrainOutcomeNet from './BrainOutcomeNet.jsx'
import WorldModelPanel from './WorldModelPanel.jsx'
import PsychologyPanel from './PsychologyPanel.jsx'
import MetacognitionPanel from './MetacognitionPanel.jsx'
import DebatePanel from './DebatePanel.jsx'
import HypothesesPanel from './HypothesesPanel.jsx'
import EvolvePanel from './EvolvePanel.jsx'
import FreqtradeCryptoPanel from './FreqtradeCryptoPanel.jsx'
import CryptoMarketsPanel from './CryptoMarketsPanel.jsx'
import StrategyLibraryPanel from './StrategyLibraryPanel.jsx'
import FoundryPanel from './FoundryPanel.jsx'
import BrainLearningPanel from './BrainLearningPanel.jsx'
import BrainUltraPanel from './BrainUltraPanel.jsx'
import BrainOpsPanel from './BrainOpsPanel.jsx'
import GoalOpsPanel from './GoalOpsPanel.jsx'
import DecisionMemoryPanel from './DecisionMemoryPanel.jsx'
import ComputerUsePanel from './ComputerUsePanel.jsx'
import BrokerSensePanel from './BrokerSensePanel.jsx'
import OcularCortexPanel from './OcularCortexPanel.jsx'
import XRayPanel from './XRayPanel.jsx'
import LiveBrowserPanel from './LiveBrowserPanel.jsx'
import BrainMirrorPanel from './BrainMirrorPanel.jsx'
import AppSchoolPanel from './AppSchoolPanel.jsx'
import BrokerFeaturesPanel from './BrokerFeaturesPanel.jsx'
import SegmentFocusPanel from './SegmentFocusPanel.jsx'
import TradeColumnsPanel from './TradeColumnsPanel.jsx'
import ConnectivityPanel from './ConnectivityPanel.jsx'
import SandboxPanel from './SandboxPanel.jsx'
import StrategyGeneratorsPanel from './StrategyGeneratorsPanel.jsx'
import LLMProvidersPanel from './LLMProvidersPanel.jsx'
import ConceptSpacePanel from './ConceptSpacePanel.jsx'
import ExchangeVenuesPanel from './ExchangeVenuesPanel.jsx'

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

      <Card title="Brain Learning & Web — reads, browses, self-evaluates" hint="reads books/papers → KnowledgeBrain · read-only web screening + Google gap-browse · answer login requests · ephemeral activity">
        <BrainLearningPanel />
      </Card>

      <Card title="Brain Ultra — associative memory · micro-LLM · perception · continual" hint="HippoRAG+A-MEM recall · Claude-style file memory · cloned nanoGPT/llama2.c · Docling reads docs · Avalanche no-forgetting">
        <BrainUltraPanel />
      </Card>

      <Card title="Brain Ops — subsystems the audit found hidden (real boss/R&D/mind-bus + honest real/demo catalog)" hint="boss directives · R&D inventions · mind event bus (live) + memory/hybrid/librarian/autonomy/stream endpoints, honestly labelled real vs offline-demo">
        <BrainOpsPanel />
      </Card>

      <Card title="Goal & Rails — the owner's 2026-07-07 evidence spine" hint="goal scoreboard · watchdogs+autonomy gates · one-variable rails · smart-money consensus · track records · UI-only data coverage — live from /api/trading/{goal,evidence,surface,scouts,track_record,ui_data,briefing}">
        <GoalOpsPanel />
      </Card>

      <Card title="LLM Providers — cloud-LLM failover telemetry" hint="per-provider hit-rate · free calls used · failures/rate-limits · last latency · reload cooldown — real core.llm.chat call stats">
        <LLMProvidersPanel />
      </Card>

      <Card title="Exchange Data Venues — multi-venue ban-proofing" hint="per-venue calls · errors · request budget · ban cooldown across binance/bybit/okx/kucoin — real market-data pool telemetry">
        <ExchangeVenuesPanel />
      </Card>

      <Card title="Concept Discovery — idea-discovery mode (pure-self feature invention)" hint="self-supervised encoder invents features → sparse-autoencoder probe → LLM naming → concept manifold · experiment(ungated) + validated(gated) lanes">
        <ConceptSpacePanel />
      </Card>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
        <Card title="AI Brain (T8)" hint="evolution · self-eval · skills · end-to-end decision">
          <BrainPanel />
        </Card>
        <Card title="Brain Outcome Net" hint="trade rows → node network → win-prob / verdict">
          <BrainOutcomeNet data={data?.brainPredict} />
        </Card>
      </div>

      <Card title="Trader Psychology — order-book depth crowd signal" hint="OBI · OFI · Stoikov microprice · whale walls · fear (spread/λ/VPIN) — live entry signal + journal columns the brain learns from">
        <PsychologyPanel />
      </Card>

      <Card title="Metacognition — calibrated uncertainty & abstention (Pillar 17)" hint="crepes conformal p_up + coverage-guaranteed intervals · ACI-adapted · reliability diagram · first-class abstention log — sizing consumes calibration">
        <MetacognitionPanel />
      </Card>

      <Card title="Adversarial Debate + Verifier (Pillar 18)" hint="bull/bear/risk debate (society) + process-reward step verifier (PRM) over a candidate trade — verified reasoning, not just PnL; gate + size multiplier">
        <DebatePanel />
      </Card>

      <Card title="Decision Memory — episodes · attribution · reflections" hint="FinMem layered episodes (shallow/mid/deep) · SHAP 'which data drove it' · TradingAgents outcome-closure lessons recalled before new entries">
        <DecisionMemoryPanel />
      </Card>

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

      <Card title="Broker-Sense Funnel — trades through the broker web apps" hint="their screeners narrow the universe · candle screenshots → CNN direction · screen-mirror bid/ask (API fail-safe) · APIs execute only · paper-first">
        <BrokerSensePanel />
      </Card>

      <Card title="Ocular Cortex — the brain's eyes & visual memory" hint="FREE vision (no GPU/paid API) reads each broker screen · fuses pixels+DOM+OCR+the app's own JSON · learns golden paths (iconic→working→habit) · links the frame that drove each trade">
        <OcularCortexPanel />
      </Card>

      <Card title="Stock X-Ray — full per-stock picture on trade-open" hint="fused snapshot: OpenAlgo multi-TF candles+indicators, 20-level depth+imbalance, circuit bands, computed demand/supply zones + free-eyes Upstox visual · auto-captured when a trade opens · type a symbol to X-ray any stock">
        <XRayPanel />
      </Card>

      <Card title="Live browser — connect your broker account" hint="a real browser streamed here so YOU solve the login captcha/OTP that automation can't · your clicks+typing drive the page · Save session → the brain reads your account headless after">
        <LiveBrowserPanel broker="binance" />
      </Card>

      <Card title="Brain Screen Mirror — watch the brain operate the apps" hint="READ-ONLY live mirror of the browser the BRAIN drives after login · every page it opens, button it clicks (marker shown), text it reads · funnel screening + ⭐ watchlist hand + app-school · watching never steers the hand">
        <BrainMirrorPanel />
      </Card>

      <Card title="App Driving School — Binance (crypto)" hint="explores the logged-in BINANCE app read-only · clicks every feature · learns the golden route to each market-data kind (spot/futures/options/screeners) from the app's own traffic · no hardcoded pages">
        <AppSchoolPanel broker="binance" />
      </Card>

      <Card title="App Driving School — Upstox (NSE)" hint="a SEPARATE school for the logged-in UPSTOX app (kept distinct from Binance so the brain never confuses them) · learns NSE movers/watchlist/F&O/option-chain/depth routes from Upstox's own traffic · read-only">
        <AppSchoolPanel broker="upstox" />
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

      <Card title="Wiring watchdog — self-healing connectivity" hint="flags any module/endpoint that WAS wired coming unwired (a regression) so nothing silently disconnects · backlog baselined · heuristic early-warning">
        <ConnectivityPanel />
      </Card>

      <TradeDrilldown trade={drill} onClose={() => setDrill(null)} />
    </div>
  )
}
