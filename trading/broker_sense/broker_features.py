"""trading/broker_sense/broker_features.py — USE the broker apps' OWN built-in pickers.

The owner's insight: Upstox and Binance already RUN heavy screeners on their servers (momentum
gainers 1m/3m/5m, trending, top gainers/losers, funding board, liquidation heatmap, OI analysis…).
Re-computing that ourselves wastes CPU. This module treats each built-in picker as a ready-made
CANDIDATE SOURCE — the brain reads the list the broker already ranked, and LEARNS which pickers
actually predict winners (stacking). Everything read-only; never places or previews-to-submit an
order (the order-preview reader reads the ticket's risk math, never clicks Buy/Sell).

Built on the existing stack: sessions.page (logged-in browser), interception (the app's own JSON
traffic), learning_columns (extra number discovery). Feature reads run in PARALLEL (owner: use the
32 GB / 12 cores) so every picker refreshes each bar instead of one-at-a-time.

  read_all_features(broker)  → {feature: [symbols…]}   (parallel, #1 + #2)
  fuse(broker, feature_map)  → [{symbol, score, bullish, bearish, features}]   (#3 stacking)
  new_entries(broker, feat)  → symbols that JUST entered the list   (momentum-ignition, extra)
  order_preview(broker, sym) → {margin, liq_price, impact…}   (broker's own risk math, extra)
  cross_broker_signals()     → correlated crypto/equity plays   (extra)
  watchlist_remember(...)    → persist picks to the REAL account watchlist   (extra, gated)
"""
from __future__ import annotations

import concurrent.futures
import os
import re
import time

from trading import state

_PERF_FILE = "broker_feature_perf.json"
_SNAP_FILE = "broker_feature_snapshots.json"     # last-seen list per feature (new-entry diff)
_REGIME_FILE = "broker_regime.json"              # last computed cross-broker regime (cheap cache)


def current_regime() -> str:
    """The market regime (risk_on / risk_off / neutral) the picker weights condition on. Cheap
    cached read — cross_broker_signals() refreshes it; defaults to 'neutral' before first compute."""
    try:
        return str(state.load_json(_REGIME_FILE, {}).get("regime") or "neutral")
    except Exception:
        return "neutral"

# Each built-in picker the apps expose. `kind`=movers|gainers|losers|trending|funding|liquidation|
# oi|news|scalper|options; `dir`=bullish/bearish/neutral prior; `route`=logged-in URL (learned
# routes in the App School override these). segment scopes crypto vs nse.
FEATURE_CATALOG: dict[str, list[dict]] = {
    "upstox": [
        {"name": "momentum_gainers_1m", "kind": "gainers", "dir": "bullish", "segment": "equity",
         "route": "https://pro.upstox.com/discover/momentum?tf=1m"},
        {"name": "momentum_gainers_3m", "kind": "gainers", "dir": "bullish", "segment": "equity",
         "route": "https://pro.upstox.com/discover/momentum?tf=3m"},
        {"name": "momentum_gainers_5m", "kind": "gainers", "dir": "bullish", "segment": "equity",
         "route": "https://pro.upstox.com/discover/momentum?tf=5m"},
        {"name": "top_gainers", "kind": "gainers", "dir": "bullish", "segment": "equity",
         "route": "https://pro.upstox.com/discover/top-gainers"},
        {"name": "top_losers", "kind": "losers", "dir": "bearish", "segment": "equity",
         "route": "https://pro.upstox.com/discover/top-losers"},
        {"name": "trending_stocks", "kind": "trending", "dir": "bullish", "segment": "equity",
         "route": "https://pro.upstox.com/discover/trending"},
        {"name": "trending_under_500", "kind": "trending", "dir": "bullish", "segment": "equity",
         "route": "https://pro.upstox.com/discover/trending?price=lt500"},
        {"name": "algovers", "kind": "movers", "dir": "neutral", "segment": "equity",
         "route": "https://pro.upstox.com/discover/algovers"},
        {"name": "scalper", "kind": "scalper", "dir": "neutral", "segment": "equity",
         "route": "https://pro.upstox.com/discover/scalper"},
        {"name": "chart360", "kind": "movers", "dir": "neutral", "segment": "equity",
         "route": "https://pro.upstox.com/discover/chart360"},
        {"name": "oi_analysis", "kind": "oi", "dir": "neutral", "segment": "futures",
         "route": "https://pro.upstox.com/discover/oi-analysis"},
        {"name": "news", "kind": "news", "dir": "neutral", "segment": "equity",
         "route": "https://pro.upstox.com/discover/news"},
    ],
    "binance": [
        {"name": "top_movers", "kind": "movers", "dir": "neutral", "segment": "spot",
         "route": "https://www.binance.com/en/markets/overview"},
        {"name": "top_gainers", "kind": "gainers", "dir": "bullish", "segment": "spot",
         "route": "https://www.binance.com/en/markets/spot_gainers"},
        {"name": "top_losers", "kind": "losers", "dir": "bearish", "segment": "spot",
         "route": "https://www.binance.com/en/markets/spot_losers"},
        {"name": "new_listings", "kind": "trending", "dir": "bullish", "segment": "spot",
         "route": "https://www.binance.com/en/markets/newListing"},
        {"name": "futures_gainers", "kind": "gainers", "dir": "bullish", "segment": "futures",
         "route": "https://www.binance.com/en/futures/markets"},
        {"name": "funding_board", "kind": "funding", "dir": "neutral", "segment": "futures",
         "route": "https://www.binance.com/en/futures/funding-fee-history"},
        {"name": "long_short_leaderboard", "kind": "long_short", "dir": "neutral",
         "segment": "futures", "route": "https://www.binance.com/en/futures/funding-rate"},
        {"name": "liquidation_heatmap", "kind": "liquidation", "dir": "neutral",
         "segment": "futures", "route": "https://www.binance.com/en/futures/markets"},
        {"name": "options_movers", "kind": "options", "dir": "neutral", "segment": "options",
         "route": "https://www.binance.com/en/eoptions"},
    ],
}

_ROW = re.compile(r"\b([A-Z][A-Z0-9]{1,14}(?:/USDT)?)\b[^\n%]{0,40}?([+-]?\d{1,3}(?:\.\d+)?)\s*%")


# Screener-like feature detection: a discovered app control is a usable PICKER when its label
# looks like a ranked list of symbols. Maps label keywords → (kind, direction prior).
_PICKER_KEYWORDS = {
    "bullish": ("gainer", "top gain", "advancer", "momentum", "breakout", "surge", "bullish",
                "trending", "new listing", "top gainers", "rocket"),
    "bearish": ("loser", "top los", "decliner", "bearish", "oversold", "laggard"),
    "neutral": ("mover", "most active", "unusual volume", "top volume", "turnover", "screener",
                "scanner", "scalper", "open interest", "funding rate", "funding board",
                "liquidation", "heatmap", "long short", "long/short", "chart360", "chart 360",
                "algover", "52 week", "circuit", "put call", "max pain", "delivery", "vwap",
                "option chain", "options movers", "sector", "watchlist", "discover", "oi analysis"),
}
# labels that contain a picker keyword but are NOT pickers (nav/marketing/price-laden noise)
_PICKER_JUNK = ("sign up", "sign in", "log in", "login", "register", "download", "deposit",
                "withdraw", "account", "setting", "open futures", "open account", "learn",
                "academy", "more download", "download options")
_PICKER_KIND = {"gainer": "gainers", "loser": "losers", "mover": "movers", "trending": "trending",
                "momentum": "gainers", "funding": "funding", "liquidation": "liquidation",
                "oi": "oi", "open interest": "oi", "long short": "long_short", "scalper": "scalper",
                "option": "options", "screener": "screener", "scanner": "screener",
                "volume": "movers", "active": "movers", "new listing": "trending"}


def _classify_label(label: str):
    """(is_picker, direction, kind) for a discovered app control label."""
    lo = " ".join((label or "").split()).lower()
    if not lo or len(lo) > 40:
        return False, None, None
    if any(j in lo for j in _PICKER_JUNK) or sum(c.isdigit() for c in lo) > 4:
        return False, None, None                 # nav/marketing/price-laden label, not a picker
    direction = None
    for d, kws in _PICKER_KEYWORDS.items():
        if any(k in lo for k in kws):
            direction = d
            break
    if direction is None:
        return False, None, None
    kind = "movers"
    for k, v in _PICKER_KIND.items():
        if k in lo:
            kind = v
            break
    return True, direction, kind


def discovered_pickers(broker: str) -> list[dict]:
    """AUTO-DISCOVERED pickers (owner: "find ALL built-in features, not only the ones I named").
    Reads every control the App Driving School catalogued on the app + its learned page controls,
    keeps the screener-like ones, and turns each into a usable picker. Dynamic — grows as the crawl
    finds more of the app's features. The learned route to each (if known) is used at read time."""
    labels: set = set()
    try:
        from trading.broker_sense.app_explorer import get_catalog
        for lab in (get_catalog().data.get(broker, {}).get("features", {}) or {}):
            labels.add(lab)
    except Exception:
        pass
    try:                                     # also the App School's per-page control lists
        from trading.broker_sense.app_school import get_school
        for _url, pg in (get_school().map.pages.get(broker, {}) or {}).items():
            for c in (pg.get("controls") or []):
                labels.add(c)
    except Exception:
        pass
    seg_default = "futures" if broker == "binance" else "equity"
    out = []
    for lab in labels:
        ok, direction, kind = _classify_label(lab)
        if not ok:
            continue
        seg = ("options" if kind == "options" else
               "futures" if kind in ("funding", "liquidation", "long_short", "oi") else seg_default)
        out.append({"name": "disc_" + re.sub(r"[^a-z0-9]+", "_", lab.lower()).strip("_")[:28],
                    "kind": kind, "dir": direction, "segment": seg, "route": "", "label": lab,
                    "discovered": True})
    return out


def features_for(broker: str, segment: str | None = None) -> list[dict]:
    # seed (owner-named) pickers + AUTO-DISCOVERED ones (dedup by name) — ALL the app's features
    seed = FEATURE_CATALOG.get(broker, [])
    disc = discovered_pickers(broker)
    seen = {f["name"] for f in seed}
    feats = seed + [d for d in disc if d["name"] not in seen]
    if segment is not None:
        feats = [f for f in feats if f.get("segment") == segment]
    # GLOBAL segment focus: drop pickers whose segment the owner turned OFF (whole-brain gate).
    try:
        from trading.brain import boss
        market = "CRYPTO" if broker == "binance" else "NSE"
        active = set(boss.active_segments(market))
        # map picker segment → market segment vocabulary (equity is NSE's 'spot')
        alias = {"spot": {"spot", "equity"}, "equity": {"equity", "spot"},
                 "futures": {"futures"}, "options": {"options"}, "prediction": {"prediction"}}
        feats = [f for f in feats
                 if active & alias.get(f.get("segment", ""), {f.get("segment", "")})]
    except Exception:
        pass
    return feats


def _route(broker: str, feat: dict) -> str:
    """Prefer the App-School-LEARNED route to this feature's kind; else the seeded route."""
    try:
        from trading.broker_sense.app_school import get_school
        best = get_school().map.best(broker, feat["kind"])
        if best and best.get("url"):
            return best["url"]
    except Exception:
        pass
    return feat.get("route", "")


def read_feature(broker: str, feat: dict, sessions, *, limit: int = 25) -> list[dict]:
    """Read ONE built-in picker → [{symbol, change}]. PRIMARY path = the app's OWN market data
    the fast way (App School fast_movers / ccxt tickers) sliced per picker kind — real numbers,
    ~300ms, no page render. Falls back to parsing the rendered page when that yields nothing
    (e.g. NSE, which fast_movers doesn't cover). Read-only."""
    kind = feat.get("kind", "movers")
    # FAST reliable path: the whole universe the app itself uses, sliced by this picker's kind.
    try:
        from trading.broker_sense.app_school import get_school
        market = "crypto" if broker == "binance" else "nse"
        seg = feat.get("segment", "futures")
        universe = get_school().fast_movers(broker, market,
                                            segment=("futures" if seg in ("futures", "options",
                                                     "prediction") else "spot"), limit=300)
        if not universe and broker == "upstox":
            # NSE isn't covered by fast_movers (crypto-only) → use the same NSE universe the
            # funnel screens (TradingView-india pushdown), so Upstox pickers have real rows too.
            try:
                from trading.broker_sense.screeners import tv_screen
                universe = [{"symbol": r.get("symbol"), "change": r.get("change")}
                            for r in tv_screen("nse", "top_movers", limit=300)]
            except Exception:
                universe = []
        if universe:
            rows = _slice_by_kind(universe, kind, limit)
            if rows:
                return rows
    except Exception:
        pass
    url = _route(broker, feat)
    if not url:
        return []
    rows: list[dict] = []
    try:
        pg = sessions.page(broker, url, timeout_ms=15000)
        if pg is None:
            return []
        pg.wait_for_timeout(2200)
        body = pg.inner_text("body") or ""
        try:                                 # popup/ad aware (reuse the App School dismisser)
            from trading.broker_sense.app_school import get_school
            get_school()._dismiss_popups(pg)
            body = pg.inner_text("body") or body
        except Exception:
            pass
        pg.close()
    except Exception:
        return []
    from trading.broker_sense.screeners import _crypto_pair
    seen = set()
    for m in _ROW.finditer(body[:24000]):
        sym, chg = m.group(1), float(m.group(2))
        if sym in {"NSE", "BSE", "USDT", "INR", "USD", "TOP", "ALL", "USDC"} or sym in seen:
            continue
        if broker == "binance":
            sym = _crypto_pair(sym) or ""
            if not sym:
                continue
        seen.add(sym)
        rows.append({"symbol": sym, "change": chg})
        if len(rows) >= limit:
            break
    try:
        from trading.broker_sense.learning_columns import discover_from_text
        discover_from_text(broker, body)
    except Exception:
        pass
    return rows


def _slice_by_kind(universe: list, kind: str, limit: int) -> list:
    """Turn the full ranked universe into the specific picker's list (gainers = top +%, losers =
    top −%, movers = top |%|, funding/trending = by the broker's own order). Each 'picker' is just
    a different view of the same app data — exactly what the app's UI tabs do."""
    rows = [{"symbol": r.get("symbol"), "change": float(r.get("change") or r.get("percentage") or 0)}
            for r in universe if r.get("symbol")]
    if kind == "gainers":
        rows = [r for r in rows if r["change"] > 0]
        rows.sort(key=lambda r: -r["change"])
    elif kind == "losers":
        rows = [r for r in rows if r["change"] < 0]
        rows.sort(key=lambda r: r["change"])
    else:                                    # movers / trending / funding / liquidation / oi
        rows.sort(key=lambda r: -abs(r["change"]))
    return rows[:limit]


def _max_workers() -> int:
    # owner: use the 12 cores / 32 GB — but bound so we never storm a broker (ban-safe)
    return max(2, min(8, (os.cpu_count() or 4) - 2))


def read_all_features(broker: str, sessions=None, *, segment: str | None = None,
                      limit: int = 25, parallel: bool = True) -> dict:
    """Read EVERY built-in picker for `broker` (optionally one segment) → {feature: [rows]}.
    Parallel by default (#2): each picker gets its OWN browser context on its own thread so all
    of them refresh together. Records a snapshot per feature for new-entry detection (#extra)."""
    if sessions is None:
        from trading.broker_sense.sessions import get_sessions
        sessions = get_sessions()
    feats = features_for(broker, segment)
    out: dict[str, list] = {}

    def _one(feat):
        return feat["name"], read_feature(broker, feat, sessions, limit=limit)

    if parallel and len(feats) > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=_max_workers()) as pool:
            for name, rows in pool.map(_one, feats):
                out[name] = rows
    else:
        for feat in feats:
            n, rows = _one(feat)
            out[n] = rows
    _detect_ignitions(broker, out)               # BEFORE overwriting snapshots (#4)
    _record_snapshots(broker, out)
    return out


_IGNITE_FILE = "broker_feature_ignitions.json"


def _detect_ignitions(broker: str, feature_map: dict) -> list:
    """Momentum-ignition (owner's screenshot-diff idea): a symbol that JUST entered a picker list
    this read = a momentum onset. Emit a brain alert + stash igniters so fuse() boosts them. Must
    run BEFORE _record_snapshots overwrites the previous list."""
    igniters: dict = {}
    for name, rows in (feature_map or {}).items():
        syms = [r.get("symbol") for r in (rows or []) if r.get("symbol")]
        fresh = new_entries(broker, name, syms)
        for s in fresh:
            igniters.setdefault(s, []).append(name)
    if igniters:
        # persist for fuse() to read this cycle
        d = state.load_json(_IGNITE_FILE, {})
        d[broker] = {"igniters": igniters, "ts": time.time()}
        state.save_json(_IGNITE_FILE, d)
        try:                                     # tell the brain (Stream of Mind) about the onset
            from trading.brain import mind_events
            strong = [s for s, feats in igniters.items() if len(feats) >= 2]
            if strong:
                mind_events.emit("discovery",
                                 f"Momentum ignition on {broker}: {', '.join(strong[:5])} "
                                 f"just entered {max(len(f) for f in igniters.values())} picker(s)",
                                 salience=0.75, data={"broker": broker, "igniters": igniters})
        except Exception:
            pass
    return list(igniters)


def recent_igniters(broker: str, *, max_age_s: float = 400) -> dict:
    """Symbols that ignited onto picker lists recently → their feature list (for fuse boost)."""
    d = state.load_json(_IGNITE_FILE, {}).get(broker) or {}
    if not d or time.time() - d.get("ts", 0) > max_age_s:
        return {}
    return d.get("igniters", {})


# ── #3  Feature → signal fusion (stacking: learn each picker's real hit-rate) ───────────────
class FeaturePerf:
    """Per (broker, feature) outcome memory: how trades sourced from that picker actually did →
    a learned WEIGHT (win-rate × log(sample)). The fusion score weights pickers by this, so a
    picker that reliably precedes winners counts more than a noisy one (stacking / weak-labelers)."""

    def __init__(self):
        d = state.load_json(_PERF_FILE, {})
        self.perf: dict = d.get("perf", {})          # "broker|feature" -> {n, wins, pnl}

    def record(self, broker: str, feature: str, *, win: bool, pnl: float = 0.0,
               regime: str | None = None) -> None:
        k = f"{broker}|{feature}"
        p = self.perf.setdefault(k, {"n": 0, "wins": 0, "pnl": 0.0})
        p["n"] += 1
        p["wins"] += 1 if win else 0
        p["pnl"] += float(pnl)
        # REGIME-conditional bucket (#5): a picker that only works in risk-on shouldn't be trusted
        # in risk-off. Credit the regime this trade happened in.
        reg = (regime or current_regime())
        rb = p.setdefault("by_regime", {}).setdefault(reg, {"n": 0, "wins": 0})
        rb["n"] += 1
        rb["wins"] += 1 if win else 0
        state.save_json(_PERF_FILE, {"perf": self.perf})

    def record_counterfactual(self, broker: str, feature: str, *, would_win: bool) -> None:
        """OFF-POLICY credit (invent-beyond #6): the resolved shadow outcome of a candidate
        this picker surfaced but the funnel SKIPPED. A missed winner = the lane was right;
        an avoided loser = it was noise. Kept in its own bucket so on-policy evidence
        (real trades) and counterfactual evidence never mix silently."""
        k = f"{broker}|{feature}"
        p = self.perf.setdefault(k, {"n": 0, "wins": 0, "pnl": 0.0})
        cf = p.setdefault("cf", {"n": 0, "wins": 0})
        cf["n"] += 1
        cf["wins"] += 1 if would_win else 0
        state.save_json(_PERF_FILE, {"perf": self.perf})

    def weight(self, broker: str, feature: str, *, regime: str | None = None) -> float:
        import math
        p = self.perf.get(f"{broker}|{feature}")
        if not p or (p["n"] < 3 and (p.get("cf") or {}).get("n", 0) < 3):
            return 1.0                                # neutral prior until it has evidence
        wr = p["wins"] / max(1, p["n"]) if p["n"] else 0.5
        reg = regime or current_regime()
        rb = (p.get("by_regime") or {}).get(reg)
        if rb and rb["n"] >= 3:                        # blend toward THIS regime's hit-rate
            wr = 0.4 * wr + 0.6 * (rb["wins"] / max(1, rb["n"]))
        # DR-flavored blend (#6): counterfactual (skipped-candidate) evidence refines the
        # on-policy estimate at a lower coefficient — every logged decision teaches.
        cf = p.get("cf") or {}
        if cf.get("n", 0) >= 3:
            cf_wr = cf["wins"] / max(1, cf["n"])
            wr = (0.7 * wr + 0.3 * cf_wr) if p["n"] >= 3 else cf_wr
        n_eff = p["n"] + 0.5 * cf.get("n", 0)
        return round(max(0.1, wr * 2) * (1 + math.log10(max(1, n_eff))), 3)

    def table(self) -> list[dict]:
        out = []
        for k, p in self.perf.items():
            br, ft = k.split("|", 1)
            out.append({"broker": br, "feature": ft, "n": p["n"],
                        "win_rate": round(p["wins"] / max(1, p["n"]), 3),
                        "pnl": round(p["pnl"], 2), "weight": self.weight(br, ft)})
        return sorted(out, key=lambda r: -r["weight"])


_PERF: FeaturePerf | None = None


def get_perf() -> FeaturePerf:
    global _PERF
    if _PERF is None:
        _PERF = FeaturePerf()
    return _PERF


def fuse(broker: str, feature_map: dict) -> list[dict]:
    """Combine all pickers into ONE ranked candidate list. Each symbol scores by the WEIGHTED
    count of bullish pickers minus bearish pickers it appears in (weights = learned hit-rate).
    'In 3+ strong bullish pickers' floats to the top — the owner's fusion idea, calibrated."""
    perf = get_perf()
    feats_by_name = {f["name"]: f for f in FEATURE_CATALOG.get(broker, [])}
    igniters = recent_igniters(broker)           # #4: symbols that JUST ignited get a score boost
    agg: dict[str, dict] = {}
    for name, rows in (feature_map or {}).items():
        feat = feats_by_name.get(name, {})
        direction = feat.get("dir", "neutral")
        w = perf.weight(broker, name)
        for r in rows or []:
            sym = r.get("symbol")
            if not sym:
                continue
            a = agg.setdefault(sym, {"symbol": sym, "score": 0.0, "bullish": 0, "bearish": 0,
                                     "features": [], "chg": r.get("change")})
            a["features"].append(name)
            if direction == "bullish":
                a["score"] += w
                a["bullish"] += 1
            elif direction == "bearish":
                a["score"] -= w
                a["bearish"] += 1
            else:                                     # neutral picker: use the row's own sign
                s = 1 if (r.get("change") or 0) >= 0 else -1
                a["score"] += 0.5 * w * s
                a["bullish" if s > 0 else "bearish"] += 1
    for sym, feats in igniters.items():          # #4: fresh igniters get a momentum-onset boost
        if sym in agg:
            agg[sym]["score"] *= 1.25
            agg[sym]["ignited"] = feats
    ranked = sorted(agg.values(), key=lambda a: -abs(a["score"]))
    for a in ranked:
        a["side"] = "long" if a["score"] > 0 else ("short" if a["score"] < 0 else "flat")
        a["score"] = round(a["score"], 3)
    return ranked


# ── new-entry detection (momentum ignition): a symbol that JUST entered a picker list ───────
def _record_snapshots(broker: str, feature_map: dict) -> None:
    snaps = state.load_json(_SNAP_FILE, {})
    b = snaps.setdefault(broker, {})
    for name, rows in (feature_map or {}).items():
        b[name] = {"syms": [r.get("symbol") for r in (rows or []) if r.get("symbol")],
                   "ts": time.time()}
    state.save_json(_SNAP_FILE, snaps)


def credit_symbol(broker: str, symbol: str, *, win: bool, pnl: float = 0.0) -> list:
    """Stacking feedback: at trade close, credit EVERY built-in picker whose latest snapshot
    listed `symbol` (i.e. the pickers that flagged this trade) with the win/loss — so each
    picker's learned weight reflects how its picks actually performed. Returns credited features."""
    snaps = state.load_json(_SNAP_FILE, {}).get(broker, {})
    perf = get_perf()
    credited = []
    for feature, snap in snaps.items():
        if symbol in (snap.get("syms") or []):
            perf.record(broker, feature, win=win, pnl=pnl)
            credited.append(feature)
    return credited


def new_entries(broker: str, feature: str, current_syms: list) -> list:
    """Symbols in `current_syms` that were NOT in the previous read of this feature — the moment a
    name IGNITES onto a top-mover list (a momentum-onset signal the broker computed for free)."""
    snaps = state.load_json(_SNAP_FILE, {})
    prev = set((snaps.get(broker, {}).get(feature, {}) or {}).get("syms", []))
    return [s for s in (current_syms or []) if s not in prev]


# ── cross-broker feature arbitrage (extra): correlated crypto/equity context ────────────────
def cross_broker_signals() -> dict:
    """Cross-check Binance's crypto risk-state (funding board) against Upstox's NSE breadth
    (top gainers/OI) — a market-wide risk-on/off read neither app gives alone. Read-only; empty
    until both accounts are connected."""
    out = {"binance_funding_extreme": [], "nse_breadth": None, "regime": "unknown"}
    try:
        from trading.broker_sense.sessions import get_sessions
        s = get_sessions()
        bfund = read_feature("binance", {"name": "funding_board", "kind": "funding",
                             "route": FEATURE_CATALOG["binance"][5]["route"]}, s, limit=30)
        out["binance_funding_extreme"] = [r["symbol"] for r in bfund
                                          if abs(r.get("change") or 0) > 0.05][:10]
        up = read_feature("upstox", FEATURE_CATALOG["upstox"][3], s, limit=30)  # top_gainers
        adv = sum(1 for r in up if (r.get("change") or 0) > 0)
        out["nse_breadth"] = round(adv / max(1, len(up)), 2) if up else None
        if out["nse_breadth"] is not None:
            out["regime"] = ("risk_on" if out["nse_breadth"] > 0.6 else
                             "risk_off" if out["nse_breadth"] < 0.4 else "neutral")
        state.save_json(_REGIME_FILE, {"regime": out["regime"], "ts": time.time()})  # #5 cache
    except Exception as e:
        out["error"] = str(e)[:120]
    return out


# ── order-preview scraping (extra): the app's OWN risk math, READ never SUBMIT ──────────────
_PREVIEW_FORBIDDEN = re.compile(r"\b(buy|sell|place|submit|confirm|swipe)\b", re.I)


def order_preview(broker: str, symbol: str, sessions=None) -> dict:
    """Open the app's order ticket for `symbol` and READ the broker's own pre-trade risk numbers
    (required margin, liquidation price, price impact, brokerage) WITHOUT ever submitting — we
    read the preview text only; the submit control is never clicked (double-guarded)."""
    if sessions is None:
        from trading.broker_sense.sessions import get_sessions
        sessions = get_sessions()
    from trading.broker_sense.brokers import REGISTRY
    app = REGISTRY.get(broker)
    if app is None:
        return {}
    url = (app.chart_url or app.home_url).format(symbol=symbol.split("/")[0], interval="5") \
        if "{symbol}" in (app.chart_url or "") else app.home_url
    out: dict = {"symbol": symbol, "broker": broker}
    try:
        pg = sessions.page(broker, url, timeout_ms=15000)
        if pg is None:
            return out
        pg.wait_for_timeout(2000)
        body = (pg.inner_text("body") or "")[:12000]
        pg.close()
    except Exception:
        return out
    for key, pat in (("required_margin", r"(?:required\s*margin|margin\s*required)[^\d]{0,20}([\d,]+\.?\d*)"),
                     ("liquidation_price", r"(?:liq(?:uidation)?\.?\s*price)[^\d]{0,20}([\d,]+\.?\d*)"),
                     ("price_impact", r"(?:price\s*impact|impact)[^\d]{0,20}([\d.]+)\s*%"),
                     ("brokerage", r"(?:brokerage|fees?|charges)[^\d]{0,20}([\d,]+\.?\d*)")):
        m = re.search(pat, body, re.I)
        if m:
            try:
                out[key] = float(m.group(1).replace(",", ""))
            except ValueError:
                pass
    return out


# ── watchlist as memory (extra, gated): persist picks in the REAL account watchlist ─────────
def watchlist_remember(broker: str, symbols: list, sessions=None) -> dict:
    """Add the brain's current picks to the broker account's OWN watchlist so they persist in the
    app the owner actually looks at. GATED behind BROKER_WATCHLIST_WRITE=1 (a write to the app,
    though never an order). Read-only by default — returns what it WOULD add."""
    picks = [s for s in (symbols or []) if s][:20]
    if os.environ.get("BROKER_WATCHLIST_WRITE") not in ("1", "true", "TRUE", "yes"):
        return {"broker": broker, "would_add": picks, "wrote": False,
                "note": "gated — set BROKER_WATCHLIST_WRITE=1 to write to the real account watchlist"}
    # write path: click the app's "add to watchlist" affordance per symbol (never an order button)
    wrote = []
    try:
        if sessions is None:
            from trading.broker_sense.sessions import get_sessions
            sessions = get_sessions()
        from trading.broker_sense.brokers import REGISTRY
        from trading.brain.vision.computer_use import _control_forbidden
        app = REGISTRY.get(broker)
        pg = sessions.page(broker, app.home_url, timeout_ms=15000) if app else None
        if pg is not None:
            for sym in picks:
                try:
                    btn = pg.query_selector(f"[aria-label*='add {sym}' i], [title*='watchlist' i]")
                    if btn and not _control_forbidden(btn.inner_text() or "watchlist"):
                        btn.click(timeout=1500)
                        wrote.append(sym)
                except Exception:
                    continue
            pg.close()
    except Exception:
        pass
    return {"broker": broker, "added": wrote, "wrote": bool(wrote)}


# ── #4  Live movers stream: read the app's OWN realtime feed via interception (no polling) ──
def live_movers(broker: str, sessions=None, *, dwell_s: float = 6.0) -> list[dict]:
    """Open the movers page and let the interception recorder capture the app's realtime
    movers/ticker traffic for `dwell_s`, then return what it saw — the broker pushes the ranking
    to us (websocket/XHR), so we react without re-scanning. Falls back to a parsed read on miss."""
    if sessions is None:
        from trading.broker_sense.sessions import get_sessions
        sessions = get_sessions()
    feats = features_for(broker)
    movers_feat = next((f for f in feats if f["kind"] in ("movers", "gainers")), feats[0] if feats else None)
    if not movers_feat:
        return []
    try:
        pg = sessions.page(broker, _route(broker, movers_feat), timeout_ms=15000)
        if pg is None:
            return []
        pg.wait_for_timeout(int(dwell_s * 1000))     # dwell so the realtime stream is captured
        from trading.broker_sense.interception import get_recorder
        rec = get_recorder()
        rows = []
        for kind in ("movers", "ticker"):
            latest = rec.latest(broker, kind, max_age_s=dwell_s + 4)
            if latest:
                rows.append({"kind": kind, "captured": True})
        body = pg.inner_text("body") or ""
        pg.close()
    except Exception:
        return []
    parsed = read_feature.__wrapped__ if hasattr(read_feature, "__wrapped__") else None  # noqa
    return rows or [{"symbol": m.group(1)} for m in list(_ROW.finditer(body[:12000]))[:20]]


# ── #6  Self-inventing screener presets (Voyager-style skill growth) ────────────────────────
_INVENTED_FILE = "broker_invented_presets.json"
_PRESET_DIMS = {
    "chg": [(">", 2.0), (">", 5.0), ("<", -2.0), ("<", -5.0)],
    "rvol": [(">", 1.5), (">", 3.0)],
    "rsi": [("<", 30), (">", 70)],
}


def invent_preset(broker: str, cycle: int = 0) -> dict:
    """Compose a NEW screener filter combo (like a curious human trying the app's filter UI) and
    remember it so the good ones are kept. Deterministic per cycle (no RNG — reproducible), so
    successive cycles walk the combo space. The funnel/backtest scores it; winners persist."""
    d = state.load_json(_INVENTED_FILE, {})
    invented = d.setdefault(broker, {})
    dims = list(_PRESET_DIMS)
    # pick a 2-dim combo indexed by cycle → deterministic sweep of the space
    i = cycle % len(dims)
    j = (cycle // len(dims)) % len(dims)
    da, db = dims[i], dims[(i + 1 + j) % len(dims)]
    oa = _PRESET_DIMS[da][cycle % len(_PRESET_DIMS[da])]
    ob = _PRESET_DIMS[db][(cycle // 2) % len(_PRESET_DIMS[db])]
    name = f"inv_{da}{oa[0]}{oa[1]}_{db}{ob[0]}{ob[1]}".replace(".", "p")
    spec = {"name": name, "filters": [[da, oa[0], oa[1]], [db, ob[0], ob[1]]],
            "n": invented.get(name, {}).get("n", 0) + 1, "kept": True}
    invented[name] = {k: spec[k] for k in ("filters", "n", "kept")}
    state.save_json(_INVENTED_FILE, d)
    return spec


def invented_presets(broker: str) -> dict:
    return state.load_json(_INVENTED_FILE, {}).get(broker, {})


def status() -> dict:
    """Dashboard snapshot: catalog size per broker + the learned per-feature weights (honest)."""
    return {"catalog": {b: [f["name"] for f in feats] for b, feats in FEATURE_CATALOG.items()},
            "perf": get_perf().table(),
            "invented": {b: list(invented_presets(b)) for b in FEATURE_CATALOG}}
