"""trading/broker_sense/feed_selfheal.py — detect + diagnose web-feed SCHEMA DRIFT (adopt item 2).

The Upstox web app streams market data as protobuf WS frames (`upstox_feed`) and Binance as JSON
WS frames (`binance_stream`). When the broker changes its wire format, decoding SILENTLY yields
empty records — under NSE_UI_ONLY that means the eyes stop feeding and the brain hard-abstains
(no NSE trades) with no obvious cause. This watcher makes drift LOUD and self-diagnosing:

  * per broker, track the rolling fraction of frames that decoded to at least one record;
  * when frames keep ARRIVING but the decode rate COLLAPSES, it's schema drift (not a quiet
    market) → run mildsunrise's **protobuf-inspector** over a captured raw frame to print the
    live field-number/wire-type structure (so the new schema can be re-mapped fast), and emit a
    high-salience mind-event alert. Crypto (JSON) gets the key-shape equivalent.

Never raises into the WS/interception hot path (all best-effort). Cooldown-guarded so a genuine
outage alerts once, not every frame. Kill-switch: FEED_SELFHEAL=0.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
import time
from typing import Any

_WINDOW = 40                      # frames per evaluation window
_MIN_RATE = 0.05                  # decode-success rate below this (with frames flowing) = drift
_ALERT_COOLDOWN_S = 900.0         # one alert per broker per 15 min
_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_LOCK = threading.Lock()
_STATE: dict[str, dict] = {}      # broker -> counters


def _enabled() -> bool:
    return os.environ.get("FEED_SELFHEAL", "1") not in ("0", "false", "FALSE", "no", "off")


def _st(broker: str) -> dict:
    return _STATE.setdefault((broker or "web").lower(), {
        "seen": 0, "ok": 0, "win_seen": 0, "win_ok": 0, "sample": None,
        "kind": None, "last_alert": 0.0, "drift_events": 0, "last_structure": None})


def inspect_protobuf(raw: bytes, *, timeout: float = 5.0) -> str:
    """Field-number/wire-type structure of an unknown protobuf blob via protobuf-inspector
    (no .proto needed). Best-effort; '' on failure. ANSI colour stripped for clean logs."""
    try:
        p = subprocess.run([sys.executable, "-m", "protobuf_inspector"],
                           input=raw, capture_output=True, timeout=timeout,
                           env={**os.environ, "NO_COLOR": "1"})
        return _ANSI.sub("", p.stdout.decode("utf-8", "replace")).strip()[:4000]
    except Exception:
        return ""


def _alert(broker: str, st: dict, detail: str) -> None:
    now = time.time()
    if now - st["last_alert"] < _ALERT_COOLDOWN_S:
        return
    st["last_alert"] = now
    st["drift_events"] += 1
    try:
        from trading.brain import mind_events
        mind_events.emit(
            "feed-selfheal",
            f"{broker} web-feed DECODE COLLAPSED ({st['win_ok']}/{st['win_seen']} frames "
            f"decoded) — likely SCHEMA DRIFT. The eyes are receiving frames but can't read "
            f"them, so market data is starving (UI-only ⇒ abstain). {detail}",
            salience=0.92)
    except Exception:
        pass


def note(broker: str, *, stored: int, raw: bytes | None = None) -> None:
    """Record one PROTOBUF frame outcome (upstox_feed). `stored`>0 ⇒ decoded ok. On a
    drift window it inspects a captured raw frame and alerts. Never raises."""
    if not _enabled():
        return
    try:
        with _LOCK:
            st = _st(broker)
            st["kind"] = "protobuf"
            st["seen"] += 1
            st["win_seen"] += 1
            if stored > 0:
                st["ok"] += 1
                st["win_ok"] += 1
            elif raw:
                st["sample"] = bytes(raw[:2048])          # keep a fresh undecoded sample
            if st["win_seen"] >= _WINDOW:
                rate = st["win_ok"] / max(1, st["win_seen"])
                if rate < _MIN_RATE and st["sample"]:
                    structure = inspect_protobuf(st["sample"])
                    st["last_structure"] = structure or None
                    _alert(broker, st,
                           "Live protobuf structure follows in the log — re-map the fields."
                           if structure else "protobuf-inspector could not parse it either.")
                    if structure:
                        print(f"[feed-selfheal] {broker} protobuf drift — live structure:\n"
                              f"{structure}", flush=True)
                st["win_seen"] = st["win_ok"] = 0
    except Exception:
        pass


def note_json(broker: str, msg: Any, *, ok: bool) -> None:
    """Record one JSON frame outcome (binance_stream). `ok` ⇒ the expected keys were present
    and applied. On drift it reports the OBSERVED top-level keys so the new shape is visible."""
    if not _enabled():
        return
    try:
        with _LOCK:
            st = _st(broker)
            st["kind"] = "json"
            st["seen"] += 1
            st["win_seen"] += 1
            if ok:
                st["ok"] += 1
                st["win_ok"] += 1
            elif isinstance(msg, dict):
                st["sample"] = sorted(list(msg.keys()))[:24]
            if st["win_seen"] >= _WINDOW:
                rate = st["win_ok"] / max(1, st["win_seen"])
                if rate < _MIN_RATE and st["sample"]:
                    st["last_structure"] = f"observed keys: {st['sample']}"
                    _alert(broker, st, f"Observed JSON top-level keys: {st['sample']}.")
                st["win_seen"] = st["win_ok"] = 0
    except Exception:
        pass


def status() -> dict:
    """Honest per-broker feed-decode health for the dashboard."""
    out = {}
    with _LOCK:
        for b, st in _STATE.items():
            seen = st["seen"] or 1
            out[b] = {"kind": st["kind"], "frames": st["seen"],
                      "decode_rate": round(st["ok"] / seen, 4),
                      "drift_events": st["drift_events"],
                      "last_structure": st["last_structure"]}
    return {"enabled": _enabled(), "brokers": out}
