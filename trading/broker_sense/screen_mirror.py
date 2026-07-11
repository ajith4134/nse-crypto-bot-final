"""trading/broker_sense/screen_mirror.py — live screen-mirror of the brain's OWN browsers.

The owner asked (2026-07-09) to SEE the brain operate the trading apps after login — the
pages it opens, the buttons it clicks, what it reads — like screen-mirroring the browser
the brain works in. The login stream (live_browser.py) shows a browser the OWNER drives;
this module mirrors the browsers the BRAIN drives (crypto/NSE funnels, the watchlist hand,
app-school), read-only: watching never steers the hand.

Cross-process by design: the working browsers live inside the funnel/loop processes, the
dashboard in another. Capture therefore happens IN-PROCESS at the two chokepoints every
brain browser action already flows through —

  • trading/brain/vision/human_ui.py   → every eyes-read / hand-click (with coordinates,
                                          so the dashboard can draw the click marker)
  • trading/broker_sense/sessions.py   → every page open / navigation

— and lands here as throttled JPEG frames + an action log under
``trading/state/screen_mirror/<broker>/`` (atomic tmp+rename writes). The dashboard serves
the files as-is (`/api/trading/mirror`); LIVE vs STALE is derived honestly from frame age.

Budget: one viewport JPEG (quality ~45) per action, idle refreshes throttled to
``SCREEN_MIRROR_MIN_S`` (default 2s), screenshot timeout 4s — never meaningful next to a
funnel cycle, and never raises into a trading loop. Kill-switch: SCREEN_MIRROR=0.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any

from trading import state

_MAX_ACTIONS = 300          # per broker, newest kept
_FRAME_NAME = "frame.jpg"
_META_NAME = "meta.json"
_ACTIONS_NAME = "actions.jsonl"
_LAST_TS: dict[str, float] = {}          # per-process throttle (broker → monotonic ts)


def enabled() -> bool:
    return os.environ.get("SCREEN_MIRROR", "1") in ("1", "true", "TRUE", "yes", "on")


def _dir(broker: str):
    d = state._path("screen_mirror") / (broker or "web").lower()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _min_interval() -> float:
    try:
        return float(os.environ.get("SCREEN_MIRROR_MIN_S", "2") or 2)
    except ValueError:
        return 2.0


def record(broker: str, page, *, action: dict | None = None, force: bool = False) -> bool:
    """Capture one frame of `page` (+ optional action) into the broker's mirror store.

    `force`/`action` bypasses the idle throttle (an action IS the thing worth showing);
    plain refreshes are rate-limited to one per SCREEN_MIRROR_MIN_S. Never raises —
    a mirror failure must never cost a trading cycle. Returns True when a frame landed.
    """
    if not enabled() or page is None:
        return False
    broker = (broker or "web").lower()
    # Human-CAPTCHA handoff: the shared per-action chokepoint every driving loop funnels
    # through, so one hook covers them all. If a security challenge is on the page this PARKS
    # the loop (hands the operator interactive control) until it clears; otherwise it returns
    # instantly (throttled check). force=False refreshes inside the park loop must not recurse.
    if force:
        try:
            from trading.broker_sense import human_handoff
            human_handoff.guard(broker, page)
        except Exception:
            pass
    now = time.monotonic()
    if not force and now - _LAST_TS.get(broker, 0.0) < _min_interval():
        # throttled: skip the frame but keep the feed truthful (reads fire often)
        if action:
            _append_action(broker, {**action, "ts": time.time(), "frame": False})
        return False
    try:
        jpeg = page.screenshot(type="jpeg", quality=45, timeout=4000)
        url = page.url
        title = page.title() if not page.is_closed() else ""
        vp = page.viewport_size or {}
    except Exception:
        # page gone mid-shot: still log the action so the feed stays truthful
        if action:
            _append_action(broker, {**action, "ts": time.time(), "frame": False})
        return False
    _LAST_TS[broker] = now
    d = _dir(broker)
    try:
        tmp = d / (_FRAME_NAME + ".tmp")
        tmp.write_bytes(jpeg)
        tmp.replace(d / _FRAME_NAME)                     # atomic: readers never see a torn jpg
        meta = {"ts": time.time(), "url": url, "title": (title or "")[:160],
                "viewport": {"w": vp.get("width"), "h": vp.get("height")},
                "pid": os.getpid()}
        if action:
            meta["last_action"] = action
        mtmp = d / (_META_NAME + ".tmp")
        mtmp.write_text(json.dumps(meta, default=str))
        mtmp.replace(d / _META_NAME)
    except Exception:
        return False
    if action:
        _append_action(broker, {**action, "ts": time.time(), "url": url, "frame": True})
    return True


def record_bytes(broker: str, jpeg: bytes, *, url: str = "", title: str = "",
                 viewport: dict | None = None) -> bool:
    """Land an ALREADY-CAPTURED screenshot as the broker's mirror frame (throttled).

    The eyes take screenshots constantly (free-eyes glances, locate/read shots) right
    before long LLM waits — reusing those bytes keeps the mirror seconds-fresh while
    the brain thinks, at ZERO extra browser work (2026-07-10 speed fix). PNG bytes are
    served as-is (browsers sniff content; the endpoint's content-type mismatch is
    harmless). Never raises."""
    if not enabled() or not jpeg:
        return False
    broker = (broker or "web").lower()
    now = time.monotonic()
    if now - _LAST_TS.get(broker, 0.0) < _min_interval():
        return False
    _LAST_TS[broker] = now
    d = _dir(broker)
    try:
        tmp = d / (_FRAME_NAME + ".tmp")
        tmp.write_bytes(jpeg)
        tmp.replace(d / _FRAME_NAME)
        meta = {"ts": time.time(), "url": url, "title": (title or "")[:160],
                "viewport": viewport or {}, "pid": os.getpid()}
        # keep the last action visible across passive refreshes
        try:
            old = json.loads((d / _META_NAME).read_text())
            if old.get("last_action"):
                meta["last_action"] = old["last_action"]
        except Exception:
            pass
        mtmp = d / (_META_NAME + ".tmp")
        mtmp.write_text(json.dumps(meta, default=str))
        mtmp.replace(d / _META_NAME)
        return True
    except Exception:
        return False


def log_action(broker: str, page, act: str, detail: str = "", *,
               xy: tuple[int, int] | list | None = None, ok: bool | None = None,
               extra: dict | None = None, force: bool = True) -> None:
    """One brain action (open/click/type/read/…) → action feed + a fresh annotated frame.

    force=True (default) captures a frame immediately — right for actions that CHANGE the
    screen (click/type/open). Pass force=False for high-frequency read-only acts so the
    feed stays complete while frames stay throttled."""
    action: dict[str, Any] = {"act": act, "detail": (detail or "")[:160]}
    if xy is not None:
        action["xy"] = [int(xy[0]), int(xy[1])]
    if ok is not None:
        action["ok"] = bool(ok)
    if extra:
        action.update({k: v for k, v in extra.items() if k not in action})
    record(broker, page, action=action, force=force)


def _append_action(broker: str, row: dict) -> None:
    try:
        f = _dir(broker) / _ACTIONS_NAME
        lines = []
        if f.exists():
            lines = f.read_text().splitlines()[-(_MAX_ACTIONS - 1):]
        lines.append(json.dumps(row, default=str))
        tmp = f.with_suffix(".jsonl.tmp")
        tmp.write_text("\n".join(lines) + "\n")
        tmp.replace(f)
    except Exception:
        pass


# ── dashboard read side ───────────────────────────────────────────────────────
def frame(broker: str) -> bytes | None:
    """Latest JPEG frame for `broker`, or None when the mirror has never captured."""
    try:
        f = _dir(broker) / _FRAME_NAME
        return f.read_bytes() if f.exists() else None
    except Exception:
        return None


def actions(broker: str, limit: int = 60) -> list[dict]:
    """Newest-last action rows for `broker` (bounded read; malformed lines skipped)."""
    try:
        f = _dir(broker) / _ACTIONS_NAME
        if not f.exists():
            return []
        out = []
        for ln in f.read_text().splitlines()[-max(1, int(limit)):]:
            try:
                out.append(json.loads(ln))
            except Exception:
                continue
        return out
    except Exception:
        return []


def status(*, stale_after_s: float = 30.0) -> dict:
    """Honest per-broker mirror state: frame age, LIVE/STALE, current page, last action."""
    root = state._path("screen_mirror")
    out: dict[str, dict] = {}
    try:
        brokers = [p.name for p in root.iterdir() if p.is_dir()] if root.exists() else []
    except Exception:
        brokers = []
    now = time.time()
    for b in sorted(brokers):
        meta: dict = {}
        try:
            mf = root / b / _META_NAME
            if mf.exists():
                meta = json.loads(mf.read_text())
        except Exception:
            meta = {}
        ts = float(meta.get("ts") or 0.0)
        age = round(now - ts, 1) if ts else None
        out[b] = {"ts": ts or None, "age_s": age,
                  "live": bool(ts) and (now - ts) <= stale_after_s,
                  "url": meta.get("url"), "title": meta.get("title"),
                  "viewport": meta.get("viewport"),
                  "last_action": meta.get("last_action"),
                  "n_actions": len(actions(b, limit=_MAX_ACTIONS))}
    return {"enabled": enabled(), "brokers": out}
