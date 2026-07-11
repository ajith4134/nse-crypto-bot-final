"""trading/broker_sense/human_handoff.py — mid-session human-CAPTCHA handoff.

When the brain's headed browsers hit a human-only security challenge (Binance's
"Slide to complete the puzzle" slider, an image CAPTCHA, "verify you are human", ...),
the brain must NOT try to defeat it — those puzzles are deliberately bot-hard. Instead
it PAUSES that browser and hands the operator interactive control so THEY drag the
slider arrow, then resumes automatically the instant the challenge clears.

Wiring (no loop code changes): ``screen_mirror.record()`` — the shared per-action
chokepoint every driving loop (funnels / app-school / watchlist / human_ui) funnels
through — calls ``guard(broker, page)`` on every action. guard():

  1. detects the challenge via ``sessions.is_human_challenge(page)`` (throttled so the
     Playwright body read doesn't tax every action);
  2. on first detection marks state ACTIVE (atomic state file), brings up an interactive
     noVNC over the brain's SHARED Xvfb display (``tools/handoff_vnc.sh`` attaches
     x11vnc+websockify to the EXISTING :99 — never a second Xvfb), and pushes ONE
     Telegram alert; the red dashboard banner reads the same state file;
  3. BLOCKS that browser (the loop is parked here, so it issues no further actions) while
     periodically refreshing the mirror frame, until the challenge clears or
     ``HANDOFF_MAX_WAIT`` seconds elapse;
  4. on clear marks RESOLVED and tears the VNC down when no other browser still needs it.

Trading is API-only, so parking a perception browser never blocks order execution.
The dashboard side reads ``status()`` (pure state-file read — safe in a request thread).
Secrets-safe: the Telegram alert runs dry-run when no creds are set. Kill switch:
``HUMAN_HANDOFF=0`` (detection+pause off); ``HUMAN_HANDOFF_VNC=0`` (skip the VNC bring-up,
e.g. in tests/headless CI).
"""
from __future__ import annotations

import json
import os
import subprocess
import time

from trading import state

_HOME = "/home/karan18190164"
_VNC_SCRIPT = os.path.join(_HOME, "tools", "handoff_vnc.sh")
_WEB_PORT = int(os.getenv("HANDOFF_VNC_WEBPORT", "6090") or "6090")
# noVNC URL the "Take control" button opens — fronted by the gateway (see gateway/Caddyfile
# handle_path /handoff-vnc/*). resize=scale fits the 1600x1000 Xvfb into the panel.
NOVNC_PATH = "/handoff-vnc/vnc.html?path=websockify&autoconnect=1&resize=scale"

# a sleeper indirection so tests can run guard() without real wall-clock waits
_sleep = time.sleep


# ── config / levers ───────────────────────────────────────────────────────────
def enabled() -> bool:
    return os.getenv("HUMAN_HANDOFF", "1").strip().lower() not in ("0", "false", "off")


def _vnc_enabled() -> bool:
    return os.getenv("HUMAN_HANDOFF_VNC", "1").strip().lower() not in ("0", "false", "off")


def _display() -> str:
    d = os.getenv("BROKER_SENSE_DISPLAY", ":99") or ":99"
    return d if d.startswith(":") else f":{d}"


def _max_wait() -> float:
    try:
        return float(os.getenv("HANDOFF_MAX_WAIT", "900"))   # cap a parked loop at 15 min
    except ValueError:
        return 900.0


def _poll_interval() -> float:
    try:
        return max(0.5, float(os.getenv("HANDOFF_POLL_S", "3")))
    except ValueError:
        return 3.0


def _check_interval() -> float:
    """Min seconds between challenge checks per broker on the hot path (per action)."""
    try:
        return max(0.0, float(os.getenv("HANDOFF_CHECK_S", "4")))
    except ValueError:
        return 4.0


# ── state file (atomic; the dashboard reads this, never our live objects) ──────
def _state_path():
    return state._path("human_handoff") / "state.json"


def _read() -> dict:
    try:
        p = _state_path()
        if p.exists():
            return json.loads(p.read_text() or "{}")
    except Exception:
        pass
    return {"brokers": {}}


def _write(data: dict) -> None:
    try:
        p = _state_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, default=str))
        tmp.replace(p)                                       # atomic: readers never see a torn file
    except Exception:
        pass


def _now() -> float:
    return time.time()


# ── VNC lifecycle (reuses tools/handoff_vnc.sh; honest when x11vnc absent) ─────
def _vnc(op: str) -> str:
    """Run the handoff VNC helper (up|down|status) against the shared display. Returns its
    combined output; never raises. 'up'/'down' are no-ops when HUMAN_HANDOFF_VNC=0."""
    if op in ("up", "down") and not _vnc_enabled():
        return f"skipped ({op}): HUMAN_HANDOFF_VNC=0"
    try:
        r = subprocess.run(["bash", _VNC_SCRIPT, op, _display(), str(_WEB_PORT)],
                           capture_output=True, text=True, timeout=30)
        return ((r.stdout or "") + (r.stderr or "")).strip()
    except Exception as e:
        return f"error: {type(e).__name__}: {e}"


def _vnc_up() -> tuple[bool, str]:
    out = _vnc("up")
    ok = ("UP" in out) or ("skipped" in out)
    return ok, out


# ── Telegram alert (T7; dry-run without creds) ────────────────────────────────
def _alert(broker: str, url: str, *, resolved: bool = False) -> None:
    try:
        from trading.alerts import AlertEvent, TelegramChannel
        ep = _read().get("brokers", {}).get(broker, {}).get("since", "")
        if resolved:
            ev = AlertEvent(kind="challenge", severity="info", symbol=broker,
                            title=f"✅ CAPTCHA solved — {broker} resumed",
                            body=f"Automation resumed on {broker}.",
                            dedup_key=f"challenge_done:{broker}:{ep}")
        else:
            ev = AlertEvent(
                kind="challenge", severity="critical", symbol=broker,
                title=f"🧩 HUMAN NEEDED — solve CAPTCHA ({broker})",
                body=(f"The {broker} browser hit a security check and is paused. Open the "
                      f"dashboard → Human Handoff → Take control, drag the slider, and it "
                      f"resumes automatically.\nPage: {url}"),
                fields={"broker": broker, "page": url[:120]},
                dedup_key=f"challenge:{broker}:{ep}")     # one alert per challenge episode
        TelegramChannel().send(ev)
    except Exception:
        pass


# ── activate / deactivate ─────────────────────────────────────────────────────
def _any_other_active(brokers: dict, exclude: str) -> bool:
    return any(b != exclude and v.get("active") for b, v in brokers.items())


def _activate(broker: str, url: str) -> None:
    """First detection of a challenge on `broker`: record it, bring up VNC, alert once."""
    data = _read()
    brokers = data.setdefault("brokers", {})
    cur = brokers.get(broker) or {}
    if cur.get("active"):
        return                                               # already handling this episode
    clear_resume(broker)                                     # a fresh episode ignores any stale override
    ok, out = _vnc_up()
    brokers[broker] = {
        "active": True, "url": url, "since": _now(), "resolved_ts": None,
        "vnc_ok": ok, "vnc_detail": out[:300], "novnc_path": NOVNC_PATH,
        "display": _display(), "web_port": _WEB_PORT,
        "needs_install": "MISSING x11vnc" in out,
    }
    _write(data)
    _alert(broker, url)


def _deactivate(broker: str, *, resolved: bool = True) -> None:
    data = _read()
    brokers = data.setdefault("brokers", {})
    cur = brokers.get(broker)
    if not cur or not cur.get("active"):
        return
    cur["active"] = False
    cur["resolved_ts"] = _now()
    cur["resolved"] = resolved
    if not _any_other_active(brokers, broker):               # last one out tears the VNC down
        _vnc("down")
    _write(data)
    clear_resume(broker)                                     # episode over — drop any override flag
    if resolved:
        _alert(broker, cur.get("url", ""), resolved=True)


# ── the hot-path hook (called from screen_mirror.record) ──────────────────────
_last_check: dict[str, float] = {}
_parking: set[str] = set()               # brokers whose park loop is on the stack (re-entrancy)


def is_challenge(page) -> bool:
    try:
        from trading.broker_sense import sessions
        return sessions.is_human_challenge(page)
    except Exception:
        return False


def guard(broker: str, page, *, block: bool = True) -> bool:
    """Per-action hook: detect a human challenge on `page` and, if present, PARK the loop
    here (giving the operator interactive control) until it clears. Returns True if it
    detected/handled a challenge, False on the normal (no-challenge) fast path.

    Cheap by default: the Playwright body read is throttled to once per HANDOFF_CHECK_S per
    broker, so the overwhelming majority of calls return in microseconds."""
    if not enabled() or page is None:
        return False
    broker = (broker or "web").lower()
    if broker in _parking:                                    # a nested mirror refresh — never re-park
        return True
    now = time.monotonic()
    active = bool(_read().get("brokers", {}).get(broker, {}).get("active"))
    if not active and now - _last_check.get(broker, 0.0) < _check_interval():
        return False                                          # throttled fast path
    _last_check[broker] = now
    if not is_challenge(page):
        if active:                                            # cleared out-of-band (e.g. operator resumed)
            _deactivate(broker)
        return False

    # challenge present → hand off
    try:
        url = page.url
    except Exception:
        url = ""
    _activate(broker, url)
    if not block:
        return True
    # PARK: the loop is stuck here (issues no further actions) until it clears or times out.
    _parking.add(broker)
    try:
        t0 = time.monotonic()
        while is_challenge(page):
            if time.monotonic() - t0 > _max_wait():
                break                                         # safety cap — never wedge forever
            if _resume_requested(broker):                     # operator forced resume from the panel
                break
            try:                                              # keep the mirror live so you see your drag
                from trading.broker_sense import screen_mirror
                screen_mirror.record(broker, page, force=True)
            except Exception:
                pass
            _sleep(_poll_interval())
    finally:
        _parking.discard(broker)
    _deactivate(broker)
    return True


# ── operator controls (dashboard POST) ────────────────────────────────────────
def _resume_flag_path(broker: str):
    return state._path("human_handoff") / f"resume_{(broker or 'web').lower()}.flag"


def _resume_requested(broker: str) -> bool:
    try:
        return _resume_flag_path(broker).exists()
    except Exception:
        return False


def request_resume(broker: str) -> dict:
    """Operator override: force-resume `broker` even if the challenge check still trips
    (e.g. a residual widget). guard()'s park loop notices the flag and exits."""
    broker = (broker or "web").lower()
    try:
        p = _resume_flag_path(broker)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(str(_now()))
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    return {"ok": True, "broker": broker, "resume_requested": True}


def clear_resume(broker: str) -> None:
    try:
        _resume_flag_path(broker).unlink()
    except Exception:
        pass


def take_control(broker: str = "") -> dict:
    """Dashboard 'Take control' button: ensure the interactive VNC is up on the shared
    display and return the noVNC URL to open. Idempotent."""
    ok, out = _vnc_up()
    return {"ok": ok, "novnc_path": NOVNC_PATH, "web_port": _WEB_PORT,
            "display": _display(), "detail": out[:400],
            "needs_install": "MISSING x11vnc" in out,
            "no_display": "NO_DISPLAY" in out}


def stop_control() -> dict:
    return {"ok": True, "detail": _vnc("down")[:200]}


# ── dashboard read side (pure; safe in a request thread) ──────────────────────
def status() -> dict:
    """Current handoff state for the dashboard: which brokers are actively challenged,
    since when, VNC health, and the noVNC path. Pure state-file read — no browser calls."""
    data = _read()
    brokers = data.get("brokers", {})
    active = {b: v for b, v in brokers.items() if v.get("active")}
    return {
        "enabled": enabled(),
        "any_active": bool(active),
        "active_brokers": sorted(active.keys()),
        "brokers": brokers,
        "novnc_path": NOVNC_PATH,
        "web_port": _WEB_PORT,
        "display": _display(),
        "ts": _now(),
    }
