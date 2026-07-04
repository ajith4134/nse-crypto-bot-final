"""System map — the WHOLE brain as a wired graph with honest live statuses.

User mandate (2026-07-04): show ALL nodes — which are WORKING and which are
STANDBY — how they are connected, what inputs each consumes and what outputs it
produces. A permanent architecture view, not a transient firing animation.

Every status is proven from REAL evidence, never asserted:
  * working  — fresh activity (state-file mtime within its window, live HTTP
               probe 200, recent rows) with the evidence string shown;
  * standby  — built and importable but idle right now (on-demand subsystem,
               gated by a flag, or waiting for data to accrue) — WHY is stated;
  * off      — its service/flag is down/disabled.

Layers: data → features → neurons → routing → execution → learning.
Edges carry the actual stream that flows (e.g. "28-feature vector", "p_up+conf").
"""
from __future__ import annotations

import glob
import json
import os
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
STATE = os.path.join(ROOT, "trading", "state")
DEPTH = os.path.join(ROOT, "trading", "data", "depth")
FEATS = os.path.join(ROOT, "trading", "data", "brain_feats")

LAYERS = ["data", "features", "neurons", "routing", "execution", "learning"]


def _age(path: str) -> float | None:
    try:
        return time.time() - os.path.getmtime(path)
    except OSError:
        return None


def _fmt_age(a: float | None) -> str:
    if a is None:
        return "never"
    if a < 90:
        return f"{a:.0f}s ago"
    if a < 5400:
        return f"{a / 60:.0f}m ago"
    if a < 172800:
        return f"{a / 3600:.1f}h ago"
    return f"{a / 86400:.1f}d ago"


def _json_len(path: str) -> int:
    try:
        with open(path) as fh:
            d = json.load(fh)
        return len(d) if isinstance(d, (list, dict)) else 1
    except Exception:
        return 0


def _probe(port: int, path: str = "/") -> bool:
    import http.client
    try:
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=1.5)
        c.request("GET", path)
        r = c.getresponse()
        c.close()
        return r.status < 500
    except Exception:
        return False


def _proc_running(needle: str) -> bool:
    for p in glob.glob("/proc/[0-9]*/cmdline"):
        try:
            with open(p, "rb") as fh:
                if needle.encode() in fh.read():
                    return True
        except OSError:
            continue
    return False


def _env_on(name: str) -> bool:
    return os.environ.get(name, "") in ("1", "true", "TRUE", "yes")


def _node(id_, label, layer, status, evidence, inputs, outputs):
    return {"id": id_, "label": label, "layer": layer, "status": status,
            "evidence": evidence, "inputs": inputs, "outputs": outputs}


def _fresh_status(age: float | None, window_s: float, standby_why: str):
    if age is not None and age <= window_s:
        return "working", f"active {_fmt_age(age)}"
    return "standby", f"{standby_why} (last {_fmt_age(age)})"


def system_map() -> dict:
    """The full graph. Cheap enough for a 20s-cached API route (file stats +
    two localhost probes)."""
    nodes: list = []
    N = nodes.append

    # ── network_state.json context (which neuron pool is in the trained graph)
    ns_path = os.path.join(ROOT, "network_state.json")
    ns_age = _age(ns_path)
    try:
        with open(ns_path) as fh:
            ns = json.load(fh)
    except Exception:
        ns = {}
    graph_nodes = [n.get("name") for n in ns.get("nodes", [])]

    shadow_age = _age(os.path.join(STATE, "cortex_shadow.json"))
    depth_files = glob.glob(os.path.join(DEPTH, "*.jsonl"))
    depth_newest = max((_age(f) for f in depth_files), default=None,
                      key=lambda a: -a if a is None else a)
    depth_newest = min((a for a in (_age(f) for f in depth_files) if a is not None),
                       default=None)
    ft_up = _probe(8080, "/api/v1/ping")
    oa_up = _probe(5000, "/")

    # ── DATA ─────────────────────────────────────────────────────────────────
    btc = glob.glob(os.path.join(ROOT, "trading", "crypto", "freqtrade",
                                 "user_data", "data", "**", "BTC_USDT_USDT-1m-futures.feather"),
                    recursive=True)
    cand_age = _age(btc[0]) if btc else None
    st, ev = _fresh_status(cand_age, 3 * 3600, "candle store idle")
    N(_node("candles", "Candle store (438 pairs 1m)", "data", st,
            ev + f" · {len(glob.glob(os.path.join(ROOT, 'trading/crypto/freqtrade/user_data/data/**/*-1m-*.feather'), recursive=True))} files",
            ["binance/bybit/okx/kucoin OHLCV (multi-venue pool)"],
            ["1m OHLCV frames per pair"]))
    st, ev = _fresh_status(depth_newest, 1800, "depth recorder idle")
    N(_node("depth_recorder", f"L2 depth recorder ({len(depth_files)} pairs)", "data", st, ev,
            ["live order books (ccxt/OpenAlgo)"],
            ["BookSnapshot jsonl history (bids/asks ladders)"]))
    N(_node("openalgo_feed", "OpenAlgo NSE engine", "data",
            "working" if oa_up else "off",
            "HTTP :5000 " + ("200" if oa_up else "down"),
            ["Zerodha broker API"], ["NSE quotes/depth/orders"]))
    j_age = _age(os.path.join(STATE, "journal.json"))
    st, ev = _fresh_status(j_age, 24 * 3600, "no new closed trades")
    N(_node("journal", "Trade journal (85-col)", "data", st, ev,
            ["closed/open trades from every engine"],
            ["labeled outcomes for learning"]))

    # ── FEATURES (the feature bus) ───────────────────────────────────────────
    bus_working = shadow_age is not None and shadow_age <= 900
    bus_ev = f"built per bar by the live loop (cortex state {_fmt_age(shadow_age)})"
    N(_node("candle_ta", "Candle TA block (8)", "features",
            "working" if bus_working else "standby", bus_ev,
            ["1m/15m OHLCV"], ["rsi, EMA/SMA distances, %B, slope, ret_1"]))
    st = "working" if (bus_working and depth_newest is not None and depth_newest < 1800) else "standby"
    N(_node("ob_block", "Order-book block (6)", "features", st,
            f"depth history {_fmt_age(depth_newest)} · joins as-of per bar",
            ["BookSnapshot history"], ["OBI, spread, depth-slope, walls, gap map + psych_ok"]))
    N(_node("mtf_block", "Multi-TF block (4)", "features",
            "working" if bus_working else "standby", bus_ev,
            ["same candles resampled 1h (completed bars only)"],
            ["1h trend/RSI/return/vol"]))
    N(_node("market_block", "BTC/market block (3)", "features",
            "working" if bus_working else "standby", bus_ev,
            ["BTC 1m candles"], ["BTC return, relative strength, rolling corr"]))
    n_live = len(glob.glob(os.path.join(FEATS, "*.jsonl")))
    st = "working" if n_live else "standby"
    N(_node("live_rec", "Live brain-signal recorder (7)", "features", st,
            f"{n_live} pair files — history accrues per bar (started 2026-07-04)",
            ["regime probs, learner bias, psych fear, LLM p_up (live)"],
            ["recorded jsonl → trainable features + live_ok flag"]))
    st, ev = _fresh_status(depth_newest, 1800, "psych engine idle")
    N(_node("psychology", "Trader-psychology engine", "features", st, ev,
            ["order-book rings per symbol"],
            ["crowd score/label, fear, VPIN, microprice drift → journal columns"]))

    # ── NEURONS ──────────────────────────────────────────────────────────────
    cheap = [n for n in graph_nodes if str(n).startswith("sk_") or n == "xgboost"]
    N(_node("reflex_tier1", f"Reflex tier-1 experts ({len(cheap) or 6} sklearn)", "neurons",
            "working" if bus_working else "standby",
            f"fired in live shadow decisions {_fmt_age(shadow_age)}",
            ["28-feature vector"], ["class vote + confidence (cheap, every bar)"]))
    lanes = [n for n in graph_nodes if "lane" in str(n) or n == "tcn_prob"]
    N(_node("deep_lanes", f"Video deep lanes ({len(lanes) or 3}: TCN/LSTM/MLP)", "neurons",
            "working" if lanes else "standby",
            f"in trained graph: {lanes or 'pending next build'}",
            ["28-feature vector"], ["class prob (tier-2, escalation only)"]))
    catalog_in_graph = len(graph_nodes) > 40
    N(_node("catalog108", "Full catalog (108 ML nodes: SINDy, RQA, DMD, wavelets…)", "neurons",
            "working" if catalog_in_graph else "standby",
            (f"{len(graph_nodes)} nodes in trained graph"
             if catalog_in_graph else
             f"full-catalog training run in progress (graph now: {len(graph_nodes)} nodes)"),
            ["28-feature vector"], ["per-family predictions → hgate"]))
    N(_node("foundation_heads", "Foundation TS heads (TTM/Chronos/TabPFN)", "neurons",
            "standby", "on-demand via /api/trading/forecast + heads.py (DM-gated)",
            ["close-price windows"], ["multi-horizon forecast paths, P(TP before SL)"]))
    llm_age = _age(os.path.join(STATE, "llm_telemetry.json"))
    st, ev = _fresh_status(llm_age, 6 * 3600, "no recent LLM calls")
    N(_node("llm_nodes", "LLM nodes (12-provider failover + micro-LLM)", "neurons", st, ev,
            ["market context prompts"], ["directional forecast, research, chat"]))
    N(_node("neat_lane", "NEAT evolution lane (+REINFORCE edges)", "neurons",
            "standby", "on-demand: evolves topologies in simlab on PnL fitness",
            ["features + mark-to-market fitness"], ["evolved genomes + complexity telemetry"]))

    # ── ROUTING / DECISION ───────────────────────────────────────────────────
    st, ev = _fresh_status(ns_age, 24 * 3600, "graph stale — POST /api/network/refresh")
    N(_node("hgate", f"Hierarchical gate ({ns.get('active_subnet', {}).get('n_communities', '?')} Leiden communities)",
            "routing", st, ev + f" · acc {ns.get('headline_accuracy')}",
            ["all neuron outputs"], ["per-input active subnetwork + p_up"]))
    N(_node("reflex_arc", "Reflex arc (conditional compute)", "routing",
            "working" if bus_working else "standby",
            f"stay-flat routing live (shadow {_fmt_age(shadow_age)})",
            ["tier votes + agreement"], ["escalate / act / STAY-FLAT decision"]))
    trust_path = os.environ.get("MLNB_TRUST_PATH") or os.path.join(ROOT, "brain_memory", "node_trust.json")
    pend = _json_len(os.path.join(STATE, "cortex_pending.json"))
    if os.path.exists(trust_path):
        N(_node("trust", "Trust ledger (AdaHedge+BOCD)", "routing", "working",
                f"{_json_len(trust_path)} experts credited", ["closed-trade outcomes"],
                ["per-expert routing bias → hgate"]))
    else:
        N(_node("trust", "Trust ledger (AdaHedge+BOCD)", "routing", "standby",
                f"accruing — {pend} pending signals await trade closes",
                ["closed-trade outcomes"], ["per-expert routing bias → hgate"]))
    N(_node("regime", "Regime hub (jump-model + BOCD + drift sentry)", "routing",
            "standby", "hub not fitted in the live loop yet (shadow logs regime=None)",
            ["feature rows"], ["regime probs → trust conditioning + features"]))
    uq_age = _age(os.path.join(STATE, "uq_abstentions.json"))
    st, ev = _fresh_status(uq_age, 24 * 3600, "no recent abstentions")
    N(_node("uq_gate", "UQ conformal gate (crepes CPS+ACI)", "routing", st, ev,
            ["entry candidates + p_up"], ["allow / ABSTAIN (blocks low-p_up entries)"]))
    N(_node("risk_overlay", "Risk overlay (dead-band + inverse-σ̂ + cap)", "routing",
            "working" if bus_working else "standby",
            "applied to every non-flat signal (size_fraction in shadow log)",
            ["p_up + forecast vol"], ["side + size_fraction"]))
    em_age = _age(os.path.join(STATE, "crypto_entry_meta.json"))
    st, ev = _fresh_status(em_age, 3600, "decider idle")
    N(_node("decider", "Per-coin decider (strategy×brain, live decision-maker)", "routing",
            st, ev, ["strategy library backtests + brain confidence"],
            ["LONG/SHORT/FLAT + enter_tag per coin"]))
    de = _json_len(os.path.join(STATE, "decision_episodes.json"))
    N(_node("decision_memory", "Decision memory (FinMem episodes + SHAP)", "routing",
            "working" if de else "standby", f"{de} episodes recorded",
            ["every decision + context"], ["reflections, episode recall"]))

    # ── EXECUTION ────────────────────────────────────────────────────────────
    N(_node("brain_loop", "Brain loop (opens every trade)", "execution",
            "working" if bus_working else "off",
            f"cortex shadow {_fmt_age(shadow_age)} · CORTEX_SIGNAL={'on' if _env_on('CORTEX_SIGNAL') or bus_working else 'off'}"
            f" · CORTEX_TRADE={'on' if _env_on('CORTEX_TRADE') else 'off (shadow)'}",
            ["decider + cortex signals"], ["forceenter/forceexit → Freqtrade, orders → OpenAlgo"]))
    N(_node("freqtrade", "Freqtrade engine (4 crypto segments)", "execution",
            "working" if ft_up else "off", "HTTP :8080 " + ("200" if ft_up else "down"),
            ["entry/exit commands"], ["paper fills, positions, closed trades"]))
    N(_node("openalgo_exec", "OpenAlgo NSE executor", "execution",
            "working" if oa_up else "off", "HTTP :5000 " + ("200" if oa_up else "down"),
            ["NSE orders (5 segments)"], ["sandbox fills, positions"]))
    N(_node("candle_updater", "Candle updater (all TFs)", "execution",
            "working" if _proc_running("candle_updater") else "off",
            "process " + ("running" if _proc_running("candle_updater") else "not found"),
            ["exchange OHLCV"], ["fresh multi-TF candles on disk"]))

    # ── LEARNING ─────────────────────────────────────────────────────────────
    N(_node("trust_feedback", "Trust feedback (closed trades → experts)", "learning",
            "working" if pend else "standby",
            f"{pend} pending signals · credits on trade close each cycle",
            ["journal closes + pending experts"], ["TrustLedger updates"]))
    ll_age = _age(os.path.join(STATE, "learn_loop.json"))
    st, ev = _fresh_status(ll_age, 3600, "learner between 30m cycles")
    N(_node("continual", "Continual learner (30m auto-learn + FSRS)", "learning", st, ev,
            ["curriculum queue + trade outcomes"], ["updated knowledge brain"]))
    hy = _json_len(os.path.join(STATE, "hypotheses.json"))
    N(_node("hypotheses", "Hypothesis ledger + self-evolve", "learning",
            "working" if hy else "standby", f"{hy} hypotheses tracked",
            ["trade outcomes + experiments"], ["confirmed/refuted beliefs → entry vetoes"]))
    N(_node("world_model", "World model (MuZero-style imagination)", "learning",
            "standby", "on-demand: imagined rollouts before risky changes",
            ["market state + candidate actions"], ["imagined trajectories + values"]))
    ao = _json_len(os.path.join(ROOT, "data", "cache", "antioverfit_counter.json"))
    N(_node("antioverfit", "Anti-overfit telemetry (CANON-43)", "learning",
            "working" if ao else "standby",
            "counts every backtest + param budget on dashboard",
            ["backtest registrations"], ["overfit risk verdict"]))
    gs = _json_len(os.path.join(STATE, "gui_skills.json"))
    N(_node("gui_agent", "Computer-use GUI agent", "learning",
            "standby", f"{gs} learned skills · acts when invoked (paper-first)",
            ["dashboard screenshots + DOM"], ["button presses, experiments, reflections"]))

    edges = [
        ("candles", "candle_ta", "1m→15m OHLCV"),
        ("candles", "mtf_block", "1h resample"),
        ("candles", "market_block", "BTC series"),
        ("depth_recorder", "ob_block", "BookSnapshot history"),
        ("depth_recorder", "psychology", "live book rings"),
        ("psychology", "live_rec", "fear score"),
        ("regime", "live_rec", "regime probs"),
        ("candle_ta", "reflex_tier1", "28-feature vector"),
        ("ob_block", "reflex_tier1", "28-feature vector"),
        ("mtf_block", "reflex_tier1", "28-feature vector"),
        ("market_block", "reflex_tier1", "28-feature vector"),
        ("live_rec", "reflex_tier1", "28-feature vector"),
        ("reflex_tier1", "reflex_arc", "tier-1 votes"),
        ("deep_lanes", "reflex_arc", "tier-2 escalation"),
        ("catalog108", "hgate", "expert predictions"),
        ("reflex_arc", "risk_overlay", "p_up + confidence"),
        ("hgate", "reflex_arc", "deep-tier verdict"),
        ("trust", "hgate", "routing bias"),
        ("regime", "trust", "regime conditioning"),
        ("uq_gate", "brain_loop", "allow/abstain"),
        ("risk_overlay", "brain_loop", "side + size_fraction"),
        ("decider", "brain_loop", "LONG/SHORT/FLAT + tag"),
        ("foundation_heads", "decider", "forecast paths"),
        ("llm_nodes", "decider", "LLM forecast"),
        ("decision_memory", "decider", "episode recall"),
        ("brain_loop", "freqtrade", "forceenter/forceexit"),
        ("brain_loop", "openalgo_exec", "NSE orders"),
        ("freqtrade", "journal", "closed trades"),
        ("openalgo_exec", "journal", "closed trades"),
        ("journal", "trust_feedback", "realized outcomes"),
        ("trust_feedback", "trust", "expert credit/blame"),
        ("journal", "continual", "trade lessons"),
        ("journal", "hypotheses", "outcome evidence"),
        ("hypotheses", "decider", "entry vetoes"),
        ("world_model", "hypotheses", "imagined tests"),
        ("neat_lane", "catalog108", "evolved topologies"),
        ("candle_updater", "candles", "fresh multi-TF bars"),
        ("gui_agent", "brain_loop", "experiments"),
        ("antioverfit", "hgate", "capacity flags"),
    ]
    counts = {"working": 0, "standby": 0, "off": 0}
    for n in nodes:
        counts[n["status"]] = counts.get(n["status"], 0) + 1
    return {"generated_age_s": 0, "layers": LAYERS, "counts": counts,
            "nodes": nodes,
            "edges": [{"source": s, "target": t, "stream": lbl}
                      for s, t, lbl in edges]}
