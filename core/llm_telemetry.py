"""Per-provider cloud-LLM telemetry (real call stats for the dashboard).

`core.llm.chat()` records every provider attempt here — success/failure, latency, and
rate-limit/quota "cooldowns". Persisted to a JSON file under trading/state so the
dashboard process (separate from the brain-loop process that makes the calls) can read
live stats. Honest wiring: every number shown on the panel comes from a real API attempt.

Fields per provider: calls, hits, failures, rate_limited, last_latency_ms, last_error,
last_ts, reload_at (epoch when a cooled-down provider may be retried).
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time

_LOCK = threading.Lock()

try:
    from trading.state import STATE_DIR as _SD
    _PATH = os.path.join(str(_SD), "llm_telemetry.json")
except Exception:
    _PATH = os.path.join(os.path.expanduser("~"), ".mlnb_llm_telemetry.json")

# how long a rate-limited / quota-exhausted provider is considered "cooling"
COOLDOWN_SEC = 60.0
_RATE_HINTS = ("rate limit", "ratelimit", "429", "quota", "resource exhausted",
               "too many requests", "overloaded", "capacity")
# persistent misconfigurations (retired model id, dead key, empty balance) — cooling for
# 60s is pointless, these fail identically for hours/days; retry hourly instead.
# (2026-07-10 audit: cerebras' retired llama-3.3-70b burned 3.8k NotFoundError calls.)
PERM_COOLDOWN_SEC = 3600.0
_PERM_HINTS = ("does not exist", "notfound", "model_not_found", "insufficient balance",
               "invalid api key", "incorrect api key", "authentication", "unauthorized",
               "no access", "decommissioned", "deprecated")


def _blank() -> dict:
    return {"calls": 0, "hits": 0, "failures": 0, "rate_limited": 0,
            "last_latency_ms": None, "last_error": None, "last_ts": None, "reload_at": None}


def _load() -> dict:
    try:
        with open(_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(d: dict) -> None:
    try:
        os.makedirs(os.path.dirname(_PATH), exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(_PATH), suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(d, f)
        os.replace(tmp, _PATH)                      # atomic
    except Exception:
        pass


def _is_rate_limit(err: str) -> bool:
    e = (err or "").lower()
    return any(h in e for h in _RATE_HINTS)


def _is_permanent(err: str) -> bool:
    e = (err or "").lower()
    return any(h in e for h in _PERM_HINTS)


# `cooling()` is consulted on EVERY chat() attempt across processes, so the state file is
# re-read at most every _COOL_REFRESH seconds per process (it's a small JSON, atomic-written).
_COOL_REFRESH = 3.0
_cool_cache: tuple[float, dict] = (0.0, {})


def cooling(provider: str) -> bool:
    """True while `provider` is inside a recorded cooldown window (rate-limit ≈60s,
    permanent misconfig ≈1h). Cross-process via the shared telemetry file."""
    global _cool_cache
    try:
        now = time.time()
        ts, d = _cool_cache
        if now - ts > _COOL_REFRESH:
            d = _load()
            _cool_cache = (now, d)
        reload_at = (d.get(provider) or {}).get("reload_at")
        return bool(reload_at) and float(reload_at) > now
    except Exception:
        return False


def record(provider: str, ok: bool, latency_ms: float | None = None,
           error: str | None = None) -> None:
    """Record one provider attempt. Never raises (telemetry must not break calls)."""
    try:
        now = time.time()
        with _LOCK:
            d = _load()
            p = d.get(provider) or _blank()
            p["calls"] += 1
            p["last_ts"] = now
            if latency_ms is not None:
                p["last_latency_ms"] = round(float(latency_ms), 1)
            if ok:
                p["hits"] += 1
                p["last_error"] = None
                p["reload_at"] = None               # a success clears any cooldown
            else:
                p["failures"] += 1
                p["last_error"] = (error or "error")[:160]
                if _is_rate_limit(error):
                    p["rate_limited"] += 1
                    p["reload_at"] = now + COOLDOWN_SEC
                elif _is_permanent(error):
                    p["reload_at"] = now + PERM_COOLDOWN_SEC
            d[provider] = p
            _save(d)
    except Exception:
        pass


def snapshot(order: list[str] | None = None) -> dict:
    """Live per-provider view for the dashboard. `order` = configured failover order so
    the panel can show providers in priority order (and which have never been called)."""
    now = time.time()
    d = _load()
    keys = list(order) if order else []
    for k in d:
        if k not in keys:
            keys.append(k)
    rows = []
    tot_calls = tot_hits = 0
    for name in keys:
        p = d.get(name) or _blank()
        calls, hits = int(p["calls"]), int(p["hits"])
        tot_calls += calls; tot_hits += hits
        reload_at = p.get("reload_at")
        reload_in = max(0.0, reload_at - now) if reload_at else 0.0
        if reload_in > 0:
            status = "cooling"
        elif calls == 0:
            status = "idle"
        elif hits == 0:
            status = "failing"
        else:
            status = "active"
        rows.append({
            "provider": name,
            "calls": calls,
            "hits": hits,
            "failures": int(p["failures"]),
            "rate_limited": int(p["rate_limited"]),
            "hit_rate": round(hits / calls, 3) if calls else None,
            "last_latency_ms": p.get("last_latency_ms"),
            "last_error": p.get("last_error"),
            "reload_in_sec": round(reload_in, 1),
            "status": status,
        })
    return {"providers": rows,
            "totals": {"calls": tot_calls, "hits": tot_hits,
                       "hit_rate": round(tot_hits / tot_calls, 3) if tot_calls else None},
            "cooldown_sec": COOLDOWN_SEC, "ts": now}


def reset() -> None:
    with _LOCK:
        _save({})
