"""trading/brain/boss.py — the BOSS COMMAND ENGINE: talk to the brain like a boss.

The dashboard's Brain Chat routes every operator message through here first. If the message
is a COMMAND ("open at least 50 trades in crypto futures", "turn off spot", "focus options",
"collect more data", "be more profitable", "pause NSE"), it EXECUTES IMMEDIATELY against the
real control surfaces (operator decision 2026-07-04: no confirmation step — paper trading is
the safety net) and replies like an employee reporting back. Questions fall through to the
normal RAG chat (core/chat_brain.py).

Three stitched donors (research/boss-command-brain-stitch-map.md):
  • tool registry — adapted from vendor/browser_use_src/browser_use/tools/registry/service.py
    (decorator → registered action with a param spec), pydantic-free and synchronous here.
  • NL routing — core.llm.chat prompted-JSON tool calls (our LLM layer has no native
    function-calling), with a DETERMINISTIC regex command parser first so the boss works
    even with no LLM key configured.
  • persistence — trading/state atomic JSON (boss_directives.json): directives survive
    restarts and BOTH loops (crypto + NSE) obey them every cycle.

Directive semantics the loops honor (see run_brain_loop.py / brain_executor.py):
  segments   — per-market on/off overrides (crypto also reconfigures the Freqtrade engine)
  targets    — target OPEN trade count per segment ("at least N open") → entry pressure
  focus      — one segment gets every cycle; the others run every 3rd cycle
  mode       — profit (tighter gates) | data_collect (gates advisory: trade to learn) | balanced
  intensity  — 0.25..4.0 multiplier on loop cadence
  paused     — hard stop for a market's entries (exits still manage themselves)
"""
from __future__ import annotations

import json
import re
import threading
import time

from trading.brain import mind_events

_FILE = "boss_directives.json"
_lock = threading.Lock()

CRYPTO_SEGMENTS = ("futures", "spot", "options", "prediction")
NSE_SEGMENTS = ("equity", "futures", "options", "commodities")
MODES = ("balanced", "profit", "data_collect")

_DEFAULT = {
    "version": 1, "updated": 0.0,
    "mode": "balanced", "intensity": 1.0,
    "focus": {"CRYPTO": None, "NSE": None},
    "markets": {
        "CRYPTO": {"segments": {}, "targets": {}},   # empty = don't override existing config
        "NSE": {"segments": {}, "targets": {}},
    },
    "paused": {"CRYPTO": False, "NSE": False},
    "standing_goals": [],
    "history": [],
}


def directives() -> dict:
    from trading import state
    d = state.load_json(_FILE, None)
    if not isinstance(d, dict):
        return json.loads(json.dumps(_DEFAULT))
    out = json.loads(json.dumps(_DEFAULT))
    for k in out:
        if k in d:
            out[k] = d[k]
    return out


def _save(d: dict) -> None:
    from trading import state
    d["updated"] = time.time()
    d["history"] = (d.get("history") or [])[-100:]
    state.save_json(_FILE, d)


# ── loop-facing helpers (the obedience API) ──────────────────────────────────

def segment_enabled(market: str, segment: str) -> bool | None:
    """Boss override for a segment: True/False, or None = boss has no opinion."""
    seg = (directives()["markets"].get(market.upper()) or {}).get("segments") or {}
    v = seg.get(segment.lower())
    return None if v is None else bool(v)


def all_segments(market: str) -> tuple:
    """The full segment set for a market (crypto vs NSE)."""
    return CRYPTO_SEGMENTS if _norm_market(market) == "CRYPTO" else NSE_SEGMENTS


def active_segments(market: str) -> list:
    """THE single source of truth for "which segments the brain should focus on right now" —
    read by EVERY brain feature (news, strategy research, feature-discovery, learning, the funnel)
    so the owner's dashboard segment toggles gate the WHOLE brain, not just execution. A segment
    is active unless the boss explicitly turned it OFF (segment_enabled == False). If the owner
    turned a market fully off (all segments False) the list is empty and the brain skips it."""
    mk = _norm_market(market)
    out = []
    for s in all_segments(mk):
        v = segment_enabled(mk, s)
        if v is None or v:                    # None = no opinion (default ON); True = ON
            out.append(s)
    return out


def segment_focus_active(market: str, segment: str) -> bool:
    """Convenience for feature code: is THIS segment currently in focus? (respects the toggles)."""
    return segment.lower() in active_segments(market)


def target_for(market: str, segment: str) -> int:
    t = (directives()["markets"].get(market.upper()) or {}).get("targets") or {}
    try:
        return int(t.get(segment.lower()) or 0)
    except Exception:
        return 0


def is_paused(market: str) -> bool:
    return bool(directives()["paused"].get(market.upper()))


def focus_of(market: str) -> str | None:
    return directives()["focus"].get(market.upper())


def mode() -> str:
    m = directives().get("mode", "balanced")
    return m if m in MODES else "balanced"


def intensity() -> float:
    try:
        return max(0.25, min(4.0, float(directives().get("intensity", 1.0))))
    except Exception:
        return 1.0


def entry_policy(market: str, segment: str, *, open_now: int | None = None) -> dict:
    """What the executor should do with its safety gates THIS cycle, per the boss.

    profit        → gates at full strength (UQ blocks, psych veto tight 0.5).
    balanced      → default behavior (UQ blocks, psych veto 0.6).
    data_collect  → gates become ADVISORY (logged, not blocking): the boss asked for
                    volume/experience over per-trade edge.
    Below-target pressure (open < target) relaxes gates one notch regardless of mode —
    that is exactly what "open at least N trades" means.
    """
    m = mode()
    tgt = target_for(market, segment)
    pressure = bool(tgt and open_now is not None and open_now < tgt)
    relax = (m == "data_collect") or pressure
    return {
        "mode": m, "target": tgt, "pressure": pressure,
        "uq_advisory": relax and m != "profit",
        "psych_veto": 0.5 if m == "profit" else (0.85 if relax else 0.6),
        "reason": ("below boss target" if pressure else m),
    }


_last_progress: dict = {}


def report_progress(market: str, segment: str, open_now: int) -> None:
    """Emit a throttled directive-progress mind event ('target 50 → 23 open')."""
    tgt = target_for(market, segment)
    if not tgt:
        return
    key = f"{market}:{segment}"
    now = time.time()
    last = _last_progress.get(key, (0, -1))
    if now - last[0] < 300 and last[1] == open_now:
        return
    _last_progress[key] = (now, open_now)
    done = open_now >= tgt
    mind_events.emit(
        "directive",
        f"Boss target {market.lower()} {segment}: {open_now}/{tgt} open trades"
        + (" — target reached ✓" if done else " — pushing for more entries"),
        salience=0.8 if done else 0.6,
        data={"market": market, "segment": segment, "open": open_now, "target": tgt})


# ── tool registry (adapted from browser-use Registry: decorator → registered action) ──

class BossRegistry:
    def __init__(self):
        self.tools: dict = {}

    def tool(self, description: str, params: dict):
        """params: {name: (type_name, description, required)}"""
        def deco(fn):
            self.tools[fn.__name__] = {"fn": fn, "description": description, "params": params}
            return fn
        return deco

    def schema_text(self) -> str:
        lines = []
        for name, t in self.tools.items():
            ps = ", ".join(f"{k}:{v[0]}{'' if v[2] else '?'}" for k, v in t["params"].items())
            lines.append(f"- {name}({ps}) — {t['description']}")
        return "\n".join(lines)

    def execute(self, name: str, args: dict) -> dict:
        t = self.tools.get(name)
        if t is None:
            return {"ok": False, "error": f"unknown tool {name!r}"}
        kwargs = {}
        for k, (typ, _desc, required) in t["params"].items():
            if k in (args or {}):
                v = args[k]
                try:
                    if typ == "int":
                        v = int(float(v))
                    elif typ == "float":
                        v = float(v)
                    elif typ == "list":
                        v = list(v) if isinstance(v, (list, tuple)) else [
                            s.strip() for s in str(v).split(",") if s.strip()]
                    elif typ == "bool":
                        v = str(v).lower() in ("1", "true", "yes", "on")
                    else:
                        v = str(v)
                except Exception:
                    return {"ok": False, "error": f"bad value for {k}: {args[k]!r}"}
                kwargs[k] = v
            elif required:
                return {"ok": False, "error": f"missing required arg {k!r} for {name}"}
        try:
            out = t["fn"](**kwargs)
            return out if isinstance(out, dict) else {"ok": True, "result": out}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"[:200]}


registry = BossRegistry()


def _norm_market(market: str) -> str:
    m = str(market or "CRYPTO").upper()
    return "NSE" if m in ("NSE", "INDIA", "STOCK", "STOCKS", "OPENALGO") else "CRYPTO"


def _bg(fn, *a, **kw) -> None:
    threading.Thread(target=lambda: fn(*a, **kw), daemon=True).start()


@registry.tool("Turn trading segments on/off for a market (crypto: futures/spot/options/"
               "prediction; NSE: equity/futures/options/commodities). Applies to the engine "
               "immediately.",
               {"market": ("str", "CRYPTO or NSE", True),
                "enable": ("list", "segments to turn ON", False),
                "disable": ("list", "segments to turn OFF", False)})
def set_segments(market: str, enable: list | None = None, disable: list | None = None) -> dict:
    market = _norm_market(market)
    valid = CRYPTO_SEGMENTS if market == "CRYPTO" else NSE_SEGMENTS
    enable = [s.lower() for s in (enable or []) if s.lower() in valid]
    disable = [s.lower() for s in (disable or []) if s.lower() in valid]
    if not enable and not disable:
        return {"ok": False, "error": f"no valid segments given (valid: {valid})"}
    with _lock:
        d = directives()
        segs = d["markets"].setdefault(market, {}).setdefault("segments", {})
        for s in enable:
            segs[s] = True
        for s in disable:
            segs[s] = False
        _save(d)
    # push to the real engines (slow: crypto restarts the bot) in the background
    if market == "CRYPTO":
        on = [s for s in CRYPTO_SEGMENTS if (directives()["markets"]["CRYPTO"]["segments"]
                                             .get(s, s in _engine_segments()))]
        if on:
            def _apply():
                try:
                    from trading.crypto.freqtrade import control
                    control.set_segments_enabled(on)
                    mind_events.emit("boss", f"Crypto engine reconfigured: segments={on}",
                                     salience=0.7)
                except Exception as e:
                    mind_events.emit("problem", f"Segment apply failed on crypto engine: {e}",
                                     salience=0.7)
            _bg(_apply)
    else:
        try:
            from trading.online import controls
            cur = set((((controls.status().get("markets") or {}).get("NSE") or {})
                       .get("segments")) or [])
            cur |= set(enable)
            cur -= set(disable)
            controls.set_segments("NSE", sorted(cur))
        except Exception as e:
            return {"ok": True, "directive": True,
                    "note": f"directive saved; NSE controls sync failed: {e}"[:160]}
    return {"ok": True, "market": market, "enabled": enable, "disabled": disable}


def _engine_segments() -> list:
    try:
        from trading.crypto.freqtrade.config_template import enabled_segments
        return list(enabled_segments())
    except Exception:
        return list(CRYPTO_SEGMENTS)


@registry.tool("Set a TARGET number of open trades for a segment ('open at least N'). The "
               "loop pushes entries until the target is met and reports progress.",
               {"market": ("str", "CRYPTO or NSE", True),
                "segment": ("str", "segment name", True),
                "target": ("int", "desired open-trade count", True)})
def set_target_open_trades(market: str, segment: str, target: int) -> dict:
    market = _norm_market(market)
    segment = str(segment).lower()
    target = max(0, int(target))
    with _lock:
        d = directives()
        d["markets"].setdefault(market, {}).setdefault("targets", {})[segment] = target
        _save(d)
    note = ""
    if market == "CRYPTO" and target > 0:
        # the Freqtrade cap must allow the target; raise max_open_trades if needed (restarts bot)
        def _raise_cap():
            try:
                from trading.crypto.freqtrade import control
                cur = control.status().get("max_open_trades")
                if cur is not None and int(cur) < target:
                    control.set_params(max_open_trades=target)
                    mind_events.emit("boss",
                                     f"Raised crypto max_open_trades {cur}→{target} for the "
                                     f"boss target", salience=0.7)
            except Exception as e:
                mind_events.emit("problem", f"Could not raise max_open_trades: {e}", salience=0.6)
        _bg(_raise_cap)
        note = "raising engine max_open_trades in background if below target"
    elif market == "NSE" and target > 0:
        try:
            from trading.online.live_loop import get_loop
            get_loop().set_config(min_open_by_segment={segment: target})
        except Exception as e:
            note = f"directive saved; NSE loop sync failed: {e}"[:160]
    return {"ok": True, "market": market, "segment": segment, "target": target, "note": note}


@registry.tool("Focus on ONE segment of a market (it runs every cycle; others every 3rd "
               "cycle). segment='none' clears the focus.",
               {"market": ("str", "CRYPTO or NSE", True),
                "segment": ("str", "segment to focus, or 'none'", True)})
def focus_segment(market: str, segment: str) -> dict:
    market = _norm_market(market)
    seg = str(segment).lower()
    with _lock:
        d = directives()
        d["focus"][market] = None if seg in ("none", "clear", "off", "") else seg
        _save(d)
    return {"ok": True, "market": market, "focus": d["focus"][market]}


@registry.tool("Set the brain's operating mode: 'profit' (maximize profitability, gates at "
               "full strength), 'data_collect' (do more trades to gather learning data; "
               "safety gates become advisory), or 'balanced'.",
               {"mode": ("str", "profit | data_collect | balanced", True)})
def set_mode(mode: str) -> dict:
    m = str(mode).lower().replace("-", "_").replace(" ", "_")
    alias = {"profitable": "profit", "profits": "profit", "profit_max": "profit",
             "data": "data_collect", "collect": "data_collect", "learn": "data_collect",
             "normal": "balanced", "default": "balanced"}
    m = alias.get(m, m)
    if m not in MODES:
        return {"ok": False, "error": f"mode must be one of {MODES}"}
    with _lock:
        d = directives()
        d["mode"] = m
        _save(d)
    return {"ok": True, "mode": m}


@registry.tool("Increase/decrease trading intensity — a 0.25..4.0 multiplier on loop cadence "
               "(2.0 = cycle twice as often).",
               {"level": ("float", "intensity multiplier", True)})
def set_intensity(level: float) -> dict:
    lv = max(0.25, min(4.0, float(level)))
    with _lock:
        d = directives()
        d["intensity"] = lv
        _save(d)
    return {"ok": True, "intensity": lv}


@registry.tool("Pause NEW entries for a market (exits still manage themselves).",
               {"market": ("str", "CRYPTO or NSE", True)})
def pause_trading(market: str) -> dict:
    return _set_paused(_norm_market(market), True)


@registry.tool("Resume entries for a paused market.",
               {"market": ("str", "CRYPTO or NSE", True)})
def resume_trading(market: str) -> dict:
    return _set_paused(_norm_market(market), False)


def _set_paused(market: str, val: bool) -> dict:
    with _lock:
        d = directives()
        d["paused"][market] = val
        _save(d)
    if market == "NSE":                # NSE loop obeys the shared online controls registry
        try:
            from trading.online import controls
            (controls.pause if val else controls.start)("NSE")
        except Exception:
            pass
    return {"ok": True, "market": market, "paused": val}


@registry.tool("Ask the brain to research a topic online right now (ddgs + LLM synthesis, "
               "deep-research when configured); findings land in the mind stream + memory.",
               {"topic": ("str", "what to research", True)})
def research_online(topic: str) -> dict:
    topic = str(topic).strip()
    if not topic:
        return {"ok": False, "error": "empty topic"}

    def _run():
        mind_events.emit("research", f"Boss asked me to research: {topic}", salience=0.7)
        try:
            from trading.brain.researcher import AutonomousResearcher
            r = AutonomousResearcher().research(topic)
            if r.get("available"):
                mind_events.emit(
                    "research", f"Research done: {topic} — {r['n_sources']} sources",
                    detail=(r.get("summary") or "")[:800], salience=0.8,
                    data={"llm_used": r.get("llm_used")})
                try:
                    from memory.brain import get_brain
                    get_brain().ingest_text(f"boss-research: {topic}", r.get("summary") or "")
                except Exception:
                    pass
            else:
                mind_events.emit("problem", f"Research found no sources for: {topic}",
                                 salience=0.5)
        except Exception as e:
            mind_events.emit("problem", f"Research failed: {topic} — {e}", salience=0.6)
    _bg(_run)
    return {"ok": True, "started": True, "topic": topic,
            "note": "researching in background — watch the mind stream"}


@registry.tool("Add a standing goal the brain keeps pursuing across cycles (shown in status; "
               "the R&D drive draws invention topics from these).",
               {"text": ("str", "the goal", True)})
def add_goal(text: str) -> dict:
    text = str(text).strip()
    if not text:
        return {"ok": False, "error": "empty goal"}
    with _lock:
        d = directives()
        gid = 1 + max([g.get("id", 0) for g in d["standing_goals"]] or [0])
        d["standing_goals"] = (d["standing_goals"] + [
            {"id": gid, "text": text, "ts": time.time(), "active": True}])[-20:]
        _save(d)
    mind_events.emit("boss", f"New standing goal #{gid}: {text}", salience=0.7)
    return {"ok": True, "id": gid, "goal": text}


@registry.tool("Report current status: directives in force, open trades per segment, "
               "learning stats.", {})
def get_status() -> dict:
    d = directives()
    out = {"ok": True, "mode": d["mode"], "intensity": d["intensity"], "focus": d["focus"],
           "paused": d["paused"], "markets": d["markets"],
           "standing_goals": [g for g in d["standing_goals"] if g.get("active")]}
    try:
        from trading.crypto.engine_client import CryptoEngineClient
        cli = CryptoEngineClient()
        opens = {}
        for seg in _engine_segments():
            try:
                c = cli._client(seg).count() or {}
                opens[seg] = {"open": c.get("current"), "max": c.get("max")}
            except Exception:
                pass
        out["crypto_open"] = opens
    except Exception:
        pass
    try:
        from trading.brain.hypothesis import HypothesisLedger
        out["hypotheses"] = HypothesisLedger(persist=True).counts()
    except Exception:
        pass
    return out


# ── natural-language command parsing ─────────────────────────────────────────

_SEG_WORDS = "|".join(sorted(set(CRYPTO_SEGMENTS + NSE_SEGMENTS)))
_CMD_HINTS = re.compile(
    r"\b(open|close|turn|enable|disable|switch|focus|increase|decrease|more|less|pause|stop|"
    r"resume|start|collect|target|at\s*least|trades?|profitable|profit|intensity|research|"
    r"goal|mode|segment)\b", re.I)


def _looks_like_command(msg: str) -> bool:
    return bool(_CMD_HINTS.search(msg or ""))


def _market_in(msg: str) -> str:
    return "NSE" if re.search(r"\b(nse|india|equity|stock|commodit|mcx|nifty)\b", msg, re.I) \
        else "CRYPTO"


def parse_deterministic(msg: str) -> list[dict]:
    """Regex layer: canonical boss phrasings → tool calls. Works with zero LLM keys."""
    m = msg.strip()
    market = _market_in(m)
    calls: list[dict] = []

    # "open (at least) 50 (open) trades in crypto futures" / "50 open trades futures"
    r = re.search(r"(?:open|do|make|keep|maintain|target)\D{0,20}?(\d{1,4})\s*(?:open\s*)?"
                  r"(?:trades?|positions?)(?:.{0,30}?\b(" + _SEG_WORDS + r")\b)?", m, re.I)
    if not r:
        r = re.search(r"\bat\s*least\s*(\d{1,4})\b(?:.{0,40}?\b(" + _SEG_WORDS + r")\b)?", m, re.I)
    if r:
        seg = (r.group(2) or ("futures" if market == "CRYPTO" else "equity")).lower()
        calls.append({"tool": "set_target_open_trades",
                      "args": {"market": market, "segment": seg, "target": int(r.group(1))}})

    # "turn on/off X", "enable/disable X", "switch off X"
    for r in re.finditer(r"\b(turn\s*on|enable|switch\s*on|activate)\b.{0,25}?\b("
                         + _SEG_WORDS + r")\b", m, re.I):
        calls.append({"tool": "set_segments",
                      "args": {"market": market, "enable": [r.group(2).lower()]}})
    for r in re.finditer(r"\b(turn\s*off|disable|switch\s*off|deactivate|stop)\b.{0,25}?\b("
                         + _SEG_WORDS + r")\b", m, re.I):
        calls.append({"tool": "set_segments",
                      "args": {"market": market, "disable": [r.group(2).lower()]}})

    # "focus (more) on options"
    r = re.search(r"\bfocus\b.{0,25}?\b(" + _SEG_WORDS + r"|none)\b", m, re.I)
    if r:
        calls.append({"tool": "focus_segment",
                      "args": {"market": market, "segment": r.group(1).lower()}})

    # modes
    if re.search(r"\b(more\s+profit|profitab|maximi[sz]e\s+profit)", m, re.I):
        calls.append({"tool": "set_mode", "args": {"mode": "profit"}})
    if re.search(r"\b(collect|gather|more)\s+(more\s+)?data\b|\bdata\s+collect", m, re.I) or \
            re.search(r"\bmore\s+trades?\s+to\s+learn\b", m, re.I):
        calls.append({"tool": "set_mode", "args": {"mode": "data_collect"}})
    if re.search(r"\b(balanced|normal)\s+mode\b|\bmode\s+(to\s+)?(balanced|normal)\b", m, re.I):
        calls.append({"tool": "set_mode", "args": {"mode": "balanced"}})

    # intensity
    if re.search(r"\b(trade|trading)\s+(more|harder|faster)\b|\bincrease\s+trading\b", m, re.I):
        calls.append({"tool": "set_intensity", "args": {"level": 2.0}})
    if re.search(r"\b(trade|trading)\s+less\b|\b(decrease|reduce|slow)\s+(down\s+)?trading\b",
                 m, re.I):
        calls.append({"tool": "set_intensity", "args": {"level": 0.5}})

    # pause / resume
    if re.search(r"\b(pause|halt|hold)\b.{0,20}\b(trading|entries|everything)?", m, re.I) and \
            not re.search(r"\bresume|unpause\b", m, re.I) and "pause" in m.lower():
        calls.append({"tool": "pause_trading", "args": {"market": market}})
    if re.search(r"\b(resume|unpause|continue)\b.{0,15}\btrading\b", m, re.I):
        calls.append({"tool": "resume_trading", "args": {"market": market}})

    # research / goals / status
    r = re.search(r"\bresearch\b\s+(.{4,120})", m, re.I)
    if r and not calls:
        calls.append({"tool": "research_online", "args": {"topic": r.group(1).strip(" .?!")}})
    r = re.search(r"\b(?:goal|objective)\s*[:\-]\s*(.{4,160})", m, re.I)
    if r:
        calls.append({"tool": "add_goal", "args": {"text": r.group(1).strip()}})
    if re.search(r"\b(status|report|how.{0,20}(going|doing))\b", m, re.I) and not calls:
        calls.append({"tool": "get_status", "args": {}})

    # dedup identical calls
    seen, out = set(), []
    for c in calls:
        k = json.dumps(c, sort_keys=True)
        if k not in seen:
            seen.add(k)
            out.append(c)
    return out


_ROUTER_SYS = (
    "You are the command router of an autonomous trading brain. The OPERATOR (the boss) sends "
    "a message. Decide if it is a COMMAND to change trading behavior or a question. Available "
    "tools:\n{tools}\n\nRespond with ONLY a JSON object: "
    '{{"is_command": true|false, "commands": [{{"tool": "...", "args": {{...}}}}]}}. '
    "Markets are CRYPTO (segments futures/spot/options/prediction) and NSE (segments "
    "equity/futures/options/commodities). Default market is CRYPTO unless the boss says "
    "NSE/India/stocks. If it is a pure question, is_command=false with empty commands.")


def parse_llm(msg: str) -> list[dict] | None:
    """LLM router for phrasings the regex layer misses. None = LLM unavailable/unsure."""
    try:
        from core import llm
        if not llm.active_model():
            return None
        raw = llm.chat([
            {"role": "system", "content": _ROUTER_SYS.format(tools=registry.schema_text())},
            {"role": "user", "content": msg}], max_tokens=400, temperature=0.0)
        j = re.search(r"\{.*\}", raw, re.S)
        if not j:
            return None
        data = json.loads(j.group(0))
        if not data.get("is_command"):
            return []
        cmds = [c for c in (data.get("commands") or [])
                if isinstance(c, dict) and c.get("tool") in registry.tools]
        return cmds
    except Exception:
        return None


# ── the boss entry point ─────────────────────────────────────────────────────

def handle(message: str, history: list | None = None) -> dict | None:
    """Route an operator chat message. Returns {reply, actions, thoughts} when it was a
    command (already EXECUTED), or None → caller falls through to the normal RAG chat."""
    msg = (message or "").strip()
    if not msg or not _looks_like_command(msg):
        return None
    calls = parse_deterministic(msg)
    if not calls:
        llm_calls = parse_llm(msg)
        if not llm_calls:          # None (no LLM) or [] (LLM says: not a command)
            return None
        calls = llm_calls

    mind_events.emit("boss", f"Boss command: {msg[:180]}", salience=0.9)
    actions, thoughts = [], [f"boss command received: {msg[:60]}"]
    for c in calls:
        res = registry.execute(c["tool"], c.get("args") or {})
        actions.append({"tool": c["tool"], "args": c.get("args") or {}, "result": res})
        ok = res.get("ok")
        thoughts.append(f"{'✓' if ok else '✗'} {c['tool']}({c.get('args')})")
        mind_events.emit("boss" if ok else "problem",
                         f"{'Executed' if ok else 'FAILED'}: {c['tool']} "
                         f"{json.dumps(c.get('args') or {})[:120]}",
                         detail=json.dumps(res, default=str)[:600],
                         salience=0.8 if ok else 0.7)
    with _lock:
        d = directives()
        d["history"].append({"ts": time.time(), "command": msg[:300],
                             "actions": [{"tool": a["tool"], "ok": a["result"].get("ok")}
                                         for a in actions]})
        _save(d)

    ok_n = sum(1 for a in actions if a["result"].get("ok"))
    lines = [f"Yes boss — executed {ok_n}/{len(actions)} command(s) immediately:"]
    for a in actions:
        r = a["result"]
        if r.get("ok"):
            extra = r.get("note") or ""
            args = {k: v for k, v in a["args"].items()}
            lines.append(f"  ✓ {a['tool']} {json.dumps(args)}" + (f" — {extra}" if extra else ""))
            if a["tool"] == "get_status":
                lines.append("    " + json.dumps(
                    {k: r[k] for k in ("mode", "intensity", "focus", "paused", "crypto_open",
                                       "hypotheses") if k in r}, default=str)[:700])
        else:
            lines.append(f"  ✗ {a['tool']} — {r.get('error')}")
    lines.append("The loops obey these directives from their very next cycle; progress "
                 "streams into my mind feed.")
    return {"reply": "\n".join(lines), "actions": actions, "thoughts": thoughts,
            "sources": [], "error": None}
