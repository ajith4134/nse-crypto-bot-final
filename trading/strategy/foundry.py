"""trading/strategy/foundry.py — the brain's STRATEGY FOUNDRY.

The brain doesn't just pick from a fixed library — it DISCOVERS, CREATES, TRACKS and
KEEPS-THE-BEST ultra-advanced institutional strategies per segment (operator directive
2026-07-02). Three parts:

  1. SEED CATALOG — the institutional playbook (NSE futures/options + crypto futures):
     Index-basket arb, StatArb pairs, calendar-spread arb, correlation-breakdown, HMM
     regime-switching; gamma-scalping, dispersion, vol-surface arb, dealer-GEX, vanna-charm,
     vol-risk-premium; funding-rate arb, cross-exchange arb, Avellaneda-Stoikov MM. Each is a
     FoundrySpec with a STABLE UNIQUE ID, segment, data need, reference OSS repo, and honest
     status (executable-on-feed vs data-gated → wire real data, never stub: no-data-gating-skip).

  2. ONLINE RESEARCH — `research_segment()` uses AutonomousResearcher (ddgs/Google + the
     core.llm failover) to search for MORE ultra-advanced ideas per segment, dedupes by id,
     and adds them as candidate specs the brain can later synthesise into executable signals.

  3. PERFORMANCE LEDGER — trading/state/strategy_foundry.json tracks every strategy id's
     backtest + live metrics over time; `leaderboard()` ranks by risk-adjusted score and
     `promote()` keeps the best per segment. This is the "give each idea a unique id, track
     performance, save the best" loop.

Reuse-first: specs reference real OSS (repos below); executable signals plug into the existing
library backtest. Persistence via trading.state (STATE_DIR-isolatable in tests).
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field, asdict

FOUNDRY_FILE = "strategy_foundry.json"


def strategy_id(segment: str, name: str) -> str:
    """Stable unique id for a strategy: FND-<seg>-<8hex over segment+name>."""
    h = hashlib.sha1(f"{segment}::{name}".lower().encode()).hexdigest()[:8]
    seg = {"nse_futures": "NF", "nse_options": "NO", "crypto_futures": "CF",
           "crypto_spot": "CS", "crypto_options": "CO", "nse_cash": "NC",
           "nse_intraday": "NI", "mcx_commodities": "MX"}.get(segment, "XX")
    return f"FND-{seg}-{h}"


@dataclass
class FoundrySpec:
    """One discovered/curated strategy idea with a stable unique id + provenance."""
    name: str
    segment: str
    family: str                         # arb | stat_arb | volatility | market_making | regime | flow
    idea: str                           # one-line description of the edge
    data_req: tuple = ()                # what real data it needs (honest; never stubbed)
    reference: str = ""                 # OSS repo / paper it reuses
    status: str = "idea"                # idea | data_gated | executable | promoted | retired
    source: str = "seed"                # seed | research (online-discovered)
    sid: str = ""                       # unique id (filled in __post_init__)

    def __post_init__(self):
        if not self.sid:
            self.sid = strategy_id(self.segment, self.name)

    def to_dict(self) -> dict:
        return asdict(self)


# ── The institutional seed catalog (Levels 1–11, all segments) ───────────────────
# Compact rows: (name, segment, family, idea, data_req, reference). The operator's
# examples are a subset — this is the full institutional universe (build-from-oss, real repos).
_CATALOG = [
    # ===== CRYPTO SPOT =====
    ("EMA/SMA Crossover Trend", "crypto_spot", "trend", "Classic MA-cross trend entries/exits.",
     ("OHLCV",), "github.com/freqtrade/freqtrade-strategies"),
    ("Supertrend Trend Following", "crypto_spot", "trend", "ATR Supertrend flip signals.",
     ("OHLCV",), "github.com/freqtrade/freqtrade"),
    ("RSI/Bollinger Mean Reversion", "crypto_spot", "mean_reversion", "Fade RSI/BB extremes.",
     ("OHLCV",), "github.com/freqtrade/freqtrade-strategies"),
    ("NostalgiaForInfinity Multi-TF", "crypto_spot", "trend", "Multi-timeframe momentum + volume filters + dynamic exits.",
     ("OHLCV", "MULTI_TF"), "github.com/iterativv/NostalgiaForInfinity"),
    ("FreqAI LSTM Alpha", "crypto_spot", "ml", "LSTM/AI-ensemble price prediction with dynamic weighting.",
     ("OHLCV",), "github.com/Netanelshoshan/freqAI-LSTM"),
    ("Grid Trading", "crypto_spot", "market_making", "Layered buy/sell grid around price (range harvest).",
     ("OHLCV",), "github.com/51bitquant/binance_grid_trader"),
    ("DCA Accumulation", "crypto_spot", "trend", "Dollar-cost-average accumulation with dip-buy triggers.",
     ("OHLCV",), "github.com/chrisleekr/binance-trading-bot"),
    ("Triangular Arbitrage", "crypto_spot", "arb", "USDT→BTC→ETH→USDT cycle mispricing.",
     ("multi_pair_quotes",), "github.com/hummingbot/hummingbot"),
    ("Cross-Exchange Spot Arb", "crypto_spot", "arb", "Buy cheaper venue / sell richer (Binance↔Bybit↔Coinbase).",
     ("multi_exchange_quotes",), "github.com/hummingbot/hummingbot"),
    ("DEX-CEX Arbitrage", "crypto_spot", "arb", "Uniswap/Hyperliquid vs Binance price gap.",
     ("dex_quotes", "cex_quotes"), "github.com/hummingbot/hummingbot"),
    # ===== CRYPTO FUTURES =====
    ("Funding Rate Arbitrage", "crypto_futures", "arb", "Long spot / short perp to collect rich funding.",
     ("spot_quote", "perp_funding"), "github.com/aoki-h-jp/funding-rate-arbitrage"),
    ("Basis Arbitrage", "crypto_futures", "arb", "Trade perp/quarterly premium vs spot fair value.",
     ("spot_quote", "futures_quote"), "github.com/dennislwy/binance-spot-futures-arbitrage-spread-monitor"),
    ("Cross Exchange Futures Arb", "crypto_futures", "arb", "Perp price dislocation across venues.",
     ("multi_exchange_quotes",), "github.com/hummingbot/hummingbot"),
    ("Avellaneda-Stoikov Market Making", "crypto_futures", "market_making",
     "Optimal MM: reservation price, dynamic spread, inventory skew, risk aversion.",
     ("l2_orderbook", "trades"), "github.com/nkaz001/hftbacktest"),
    ("Order-Book Imbalance Alpha", "crypto_futures", "order_flow",
     "Bid/ask + queue imbalance, cumulative delta, microprice deviation.",
     ("l2_orderbook", "trades"), "github.com/nkaz001/hftbacktest"),
    ("Microprice Prediction", "crypto_futures", "order_flow", "Short-horizon move from L2 sizes + trade flow.",
     ("l2_orderbook",), "github.com/zozoheir/hftpy"),
    ("Queue Position Model", "crypto_futures", "market_making", "Fill/queue-jump/cancel probability modelling.",
     ("l2_orderbook",), "github.com/nkaz001/hftbacktest"),
    ("Latency Arbitrage", "crypto_futures", "hft", "Exploit faster information/quote updates.",
     ("l2_orderbook", "multi_exchange_quotes"), "github.com/hello2all/gamma-ray"),
    ("Liquidation/Sweep Detection", "crypto_futures", "order_flow", "Detect stop-hunts / forced liquidations / sweeps.",
     ("l2_orderbook", "liquidations"), "coinalyze/coinglass-style"),
    # ===== CRYPTO OPTIONS =====
    ("Crypto Vol Arbitrage (IV-RV)", "crypto_options", "volatility", "Trade implied vs forecast realized vol.",
     ("option_chain", "greeks"), "github.com/leanderdulac/crypto_vol_arb"),
    ("Crypto Vol Surface Arb", "crypto_options", "volatility", "Skew/smile/surface anomaly on Deribit.",
     ("option_chain", "iv_surface"), "github.com/alexanderkudryashov3/Crypto-Options"),
    ("Crypto Gamma Scalping", "crypto_options", "volatility", "Long gamma, delta-hedge on BTC/ETH options.",
     ("option_chain", "greeks", "perp_quote"), "github.com/u3ffrzi/options-market-maker-algorithm"),
    ("Crypto Options Market Making", "crypto_options", "market_making", "Quote options two-sided w/ vega/greeks risk control.",
     ("option_chain", "greeks"), "github.com/u3ffrzi/options-market-maker-algorithm"),
    # ===== NSE CASH =====
    ("Breakout/Consolidation Screener", "nse_cash", "breakout", "Breakouts, consolidation, volume-expansion scans.",
     ("OHLCV",), "github.com/pkjmesra/PKScreener"),
    ("Relative Strength Momentum", "nse_cash", "momentum", "Cross-sectional relative-strength leaders.",
     ("OHLCV", "universe"), "github.com/je-suis-tm/quant-trading"),
    ("Relative Volume Shock", "nse_cash", "momentum", "Current volume / expected volume-profile spike.",
     ("OHLCV",), "PKScreener"),
    ("Sector Rotation", "nse_cash", "momentum", "Rotate into leading sectors (bank→NIFTY lead).",
     ("OHLCV", "sector_map"), "machine-learning-for-trading"),
    ("News/Sentiment Alpha", "nse_cash", "alt_data", "News + sentiment technical overlay.",
     ("news", "OHLCV"), "github.com/KalyanM45/MarketInsight"),
    # ===== NSE INTRADAY =====
    ("Opening Range Breakout", "nse_intraday", "breakout", "ORB + gap-breakout + momentum ignition.",
     ("OHLCV", "MULTI_TF"), "github.com/je-suis-tm/quant-trading"),
    ("VWAP Reversion/Alpha", "nse_intraday", "mean_reversion", "VWAP deviation/reversion + institutional footprint.",
     ("OHLCV", "vwap"), "OpenAlgo templates"),
    ("Opening Auction Imbalance", "nse_intraday", "order_flow", "Pre-open auction imbalance + order concentration.",
     ("preopen_auction",), "institutional positioning"),
    ("Option-Chain OI/PCR", "nse_intraday", "flow", "OI build-up + PCR + S/R from the chain.",
     ("option_chain", "open_interest"), "github.com/VarunS2002/Python-NSE-Option-Chain-Analyzer"),
    ("Leader-Laggard Pairs", "nse_intraday", "stat_arb", "Trade laggard when leader (BankNifty) moves first.",
     ("pair_ohlcv",), "je-suis-tm/quant-trading"),
    # ===== NSE FUTURES =====
    ("StatArb Pairs Trading", "nse_futures", "stat_arb", "Cointegrated pairs (HDFC↔ICICI, RELIANCE↔ONGC); trade spread.",
     ("pair_ohlcv",), "github.com/sap215/StatArbPairsTrading"),
    ("Calendar Spread Arbitrage", "nse_futures", "arb", "Long near / short far on carry & roll-yield distortion.",
     ("multi_expiry_futures",), "term-structure roll desks"),
    ("Index Basket Arbitrage", "nse_futures", "arb", "Buy NIFTY basket, short future when premium excessive.",
     ("basket_quotes", "futures_quote"), "index-arb / ETF MM"),
    ("Futures Basis Trading", "nse_futures", "arb", "Spot vs future fair-value deviation + carry.",
     ("spot_quote", "futures_quote"), "basis desks"),
    ("Correlation Breakdown", "nse_futures", "stat_arb", "Trade convergence when BankNifty↔Nifty corr collapses.",
     ("pair_ohlcv",), "relative-value funds"),
    ("HMM Regime Switching", "nse_futures", "regime", "HMM / Markov-switching-GARCH regimes: trend/chop/panic/revert.",
     ("OHLCV",), "github.com/hmmlearn/hmmlearn"),
    # ===== NSE OPTIONS =====
    ("Option Selling (Strangle/Condor)", "nse_options", "volatility", "Short strangles/iron-condors on Nifty/BankNifty/FinNifty.",
     ("option_chain", "greeks"), "github.com/buzzsubash/algo_trading_strategies_india"),
    ("Automated Nifty Options Intraday", "nse_options", "flow", "Automated intraday option entries/exits.",
     ("option_chain",), "github.com/srikar-kodakandla/fully-automated-nifty-options-trading"),
    ("Multi-Leg Payoff Builder", "nse_options", "volatility", "Butterflies/condors/credit-spreads w/ greeks payoff.",
     ("option_chain", "greeks"), "github.com/mirajgodha/options"),
    ("Gamma Scalping", "nse_options", "volatility", "Long ATM straddle, delta-neutral via futures; RV>IV.",
     ("option_chain", "greeks", "futures_quote"), "github.com/alpacahq/gamma-scalping"),
    ("Dynamic Delta Hedging", "nse_options", "volatility", "Continuously delta-hedge an options book.",
     ("option_chain", "greeks"), "vol desks"),
    ("Volatility Surface Arbitrage", "nse_options", "volatility", "Skew/smile/term-structure mispricing.",
     ("option_chain", "iv_surface"), "github.com/mirajgodha/options"),
    ("Volatility Risk Premium", "nse_options", "volatility", "Sell overpriced IV, hedge delta; harvest IV>RV.",
     ("option_chain", "greeks", "iv_rank"), "VRP harvesting"),
    ("Dispersion Trading", "nse_options", "volatility", "Long index vol, short constituent stock vol.",
     ("index_option_chain", "stock_option_chains"), "github.com/billydavila/Dispersion-Trading-Strategy"),
    ("Dealer Gamma Exposure (GEX)", "nse_options", "flow", "Dealer gamma positioning, squeeze prob, pinning.",
     ("option_chain", "open_interest", "greeks"), "GEX / SpotGamma-style"),
    ("Dealer Vanna Flow", "nse_options", "flow", "Delta changes from IV moves around expiry/macro.",
     ("option_chain", "greeks"), "dealer-flow desks"),
    ("Dealer Charm Flow", "nse_options", "flow", "Delta decay from time passing near expiry.",
     ("option_chain", "greeks"), "dealer-flow desks"),
    # ===== MCX COMMODITIES =====
    ("Turtle / Donchian Breakout", "mcx_commodities", "trend", "Donchian-channel managed-futures breakout.",
     ("OHLCV",), "je-suis-tm/quant-trading"),
    ("Calendar Spread (Crude/NatGas)", "mcx_commodities", "arb", "Near/far month spread on carry + curve.",
     ("multi_expiry_futures",), "commodity roll desks"),
    ("Crack/Spark/Crush Spread", "mcx_commodities", "arb", "Crude↔products / gas↔power / soy complex spreads.",
     ("multi_asset_quotes",), "commodity spread desks"),
    ("Gold-Silver Ratio Trading", "mcx_commodities", "stat_arb", "Mean-revert the gold/silver ratio.",
     ("pair_ohlcv",), "ratio-trading desks"),
    ("Storage/Convenience-Yield Arb", "mcx_commodities", "arb", "Inventory/carry vs futures-curve arbitrage.",
     ("futures_curve", "inventory"), "commodity desks"),
    # ===== CROSS-SEGMENT ML / RL / META =====
    ("Gradient-Boost Alpha (XGB/LGBM)", "crypto_futures", "ml", "GBM direction/vol/probability alpha.",
     ("OHLCV",), "github.com/stefan-jansen/machine-learning-for-trading"),
    ("Transformer Forecaster (PatchTST/TFT)", "crypto_futures", "ml", "Multi-horizon multi-asset forecasting.",
     ("OHLCV",), "github.com/thuml/Time-Series-Library"),
    ("FinRL Exit/Sizing Policy", "crypto_futures", "rl", "PPO/SAC RL policy for exit + position sizing.",
     ("OHLCV", "features"), "github.com/AI4Finance-Foundation/FinRL"),
    ("Multi-Agent RL Desk", "crypto_futures", "rl", "Alpha/exec/risk/MM/regime/router agents (EarnHFT-style).",
     ("OHLCV", "l2_orderbook"), "arxiv.org/abs/2309.12891"),
    ("Meta Regime Strategy Allocator", "crypto_futures", "meta", "Regime-detect → allocate capital across strategy families (Thompson/bandits).",
     ("OHLCV",), "meta multi-strategy"),
]


def _seed_specs() -> list[FoundrySpec]:
    return [FoundrySpec(name=n, segment=seg, family=fam, idea=idea,
                        data_req=dr, reference=ref) for (n, seg, fam, idea, dr, ref) in _CATALOG]


class StrategyFoundry:
    """Discover → create → track → keep-the-best, per segment, with unique ids."""

    def __init__(self, *, persist: bool = True):
        self.persist = persist
        self._researcher = None
        self.specs: dict[str, FoundrySpec] = {}
        for sp in _seed_specs():
            self.specs[sp.sid] = sp
        self._ledger = self._load_ledger()      # sid -> {metrics history, best}

    # ── persistence ──────────────────────────────────────────────────────────────
    def _load_ledger(self) -> dict:
        if not self.persist:
            return {}
        try:
            from trading import state
            blob = state.load_json(FOUNDRY_FILE, {})
            # restore research-discovered specs so ids/history survive restarts
            for d in blob.get("specs", []):
                sp = FoundrySpec(**{k: (tuple(v) if k == "data_req" else v)
                                    for k, v in d.items() if k in FoundrySpec.__dataclass_fields__})
                self.specs.setdefault(sp.sid, sp)
            return blob.get("ledger", {})
        except Exception:
            return {}

    def _save(self) -> None:
        if not self.persist:
            return
        try:
            from trading import state
            state.save_json(FOUNDRY_FILE, {
                "updated_at": time.time(),
                "specs": [sp.to_dict() for sp in self.specs.values()],
                "ledger": self._ledger,
            })
        except Exception:
            pass

    # ── online research: discover MORE ideas per segment ──────────────────────────
    def researcher(self):
        if self._researcher is None:
            from trading.brain.researcher import AutonomousResearcher
            self._researcher = AutonomousResearcher()
        return self._researcher

    def research_segment(self, segment: str) -> list[FoundrySpec]:
        """Search online (ddgs/Google + LLM) for more ultra-advanced strategies in `segment`;
        register any NEW ones as candidate specs (status=idea, source=research). Returns the
        new specs. Best-effort/offline-safe."""
        q = (f"ultra advanced institutional {segment.replace('_', ' ')} trading strategies "
             "quant hedge fund github")
        new: list[FoundrySpec] = []
        try:
            res = self.researcher().research(q)
            for src in (res.get("sources") or [])[:8]:
                title = (src.get("title") or "").strip()
                if len(title) < 6:
                    continue
                sp = FoundrySpec(name=title[:80], segment=segment, family="research",
                                 idea=title, reference=src.get("href", ""), source="research")
                if sp.sid not in self.specs:
                    self.specs[sp.sid] = sp
                    new.append(sp)
        except Exception:
            pass
        if new:
            self._save()
        return new

    # ── performance tracking + keep-the-best ──────────────────────────────────────
    @staticmethod
    def _score(m: dict) -> float:
        """Risk-adjusted rank score from a metrics dict (Sharpe-led, penalise drawdown)."""
        sharpe = float(m.get("sharpe", 0.0) or 0.0)
        winr = float(m.get("win_rate", 0.0) or 0.0)
        dd = abs(float(m.get("max_drawdown", 0.0) or 0.0))
        trades = float(m.get("trades", 0) or 0)
        return round(sharpe * 1.0 + winr * 0.5 - dd * 0.5 + min(trades, 50) * 0.002, 4)

    def record(self, sid: str, metrics: dict, *, live: bool = False) -> None:
        """Record a backtest/live metrics snapshot for a strategy id, update its best score."""
        e = self._ledger.setdefault(sid, {"history": [], "best_score": None, "live_pnl": 0.0})
        snap = {"t": time.time(), "live": live, "score": self._score(metrics), **metrics}
        e["history"] = (e.get("history", []) + [snap])[-40:]     # keep last 40 snapshots
        if live:
            e["live_pnl"] = float(metrics.get("net_pnl", e.get("live_pnl", 0.0)) or 0.0)
        if e["best_score"] is None or snap["score"] > e["best_score"]:
            e["best_score"] = snap["score"]
        sp = self.specs.get(sid)
        if sp and sp.status in ("idea", "data_gated", "executable") and snap["score"] > 0:
            sp.status = "executable"
        self._save()

    def leaderboard(self, segment: str | None = None, k: int = 20) -> list[dict]:
        """Best strategies by recorded score (optionally one segment)."""
        rows = []
        for sid, sp in self.specs.items():
            if segment and sp.segment != segment:
                continue
            e = self._ledger.get(sid, {})
            rows.append({"sid": sid, "name": sp.name, "segment": sp.segment,
                         "family": sp.family, "status": sp.status, "source": sp.source,
                         "best_score": e.get("best_score"), "live_pnl": e.get("live_pnl", 0.0),
                         "n_snapshots": len(e.get("history", [])), "reference": sp.reference})
        rows.sort(key=lambda r: (r["best_score"] is not None, r["best_score"] or -1e9,
                                 r["live_pnl"]), reverse=True)
        return rows[:k]

    def promote(self, segment: str | None = None, keep: int = 5) -> list[str]:
        """Mark the top-`keep` scored strategies per segment as 'promoted'; demote the rest
        that were previously promoted. Returns promoted ids."""
        segs = [segment] if segment else sorted({sp.segment for sp in self.specs.values()})
        promoted: list[str] = []
        for seg in segs:
            ranked = [r for r in self.leaderboard(seg, k=999) if r["best_score"] is not None]
            top = {r["sid"] for r in ranked[:keep]}
            for sid in top:
                self.specs[sid].status = "promoted"
                promoted.append(sid)
            for r in ranked[keep:]:
                if self.specs[r["sid"]].status == "promoted":
                    self.specs[r["sid"]].status = "executable"
        self._save()
        return promoted

    def to_json(self) -> dict:
        by_seg: dict = {}
        for sp in self.specs.values():
            by_seg.setdefault(sp.segment, {"total": 0, "seed": 0, "research": 0, "promoted": 0})
            by_seg[sp.segment]["total"] += 1
            by_seg[sp.segment]["seed" if sp.source == "seed" else "research"] += 1
            if sp.status == "promoted":
                by_seg[sp.segment]["promoted"] += 1
        return {"n_specs": len(self.specs), "by_segment": by_seg,
                "leaderboard": self.leaderboard(k=25)}
