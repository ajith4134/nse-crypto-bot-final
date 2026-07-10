"""trading/broker_sense/live_browser.py — an interactive HEADLESS browser streamed to the
dashboard, so the operator can complete a broker login that automation can't (Binance's image
CAPTCHA + OTP) WITHOUT any system installs (no X, no VNC, no root).

How it realizes "remote-view login": a headless chromium page runs in the broker's persistent
profile; the dashboard shows its screenshot (JPEG frames) and forwards the operator's clicks +
typing to the real page (page.mouse / page.keyboard). When login succeeds, the authenticated
storage_state is saved to the SAME file the funnel's SessionManager loads, so the brain then
reads the account HEADLESS forever after.

Thread-safety: Playwright's sync API is bound to one thread, but the dashboard serves requests
on many. So each broker session owns a DEDICATED worker thread that holds the page; public
methods enqueue a command and wait for its result. Read-only: only logs in; APIs execute."""
from __future__ import annotations

import queue
import threading
import time

from trading import state

_VIEW_W, _VIEW_H = 1280, 800


class _Session:
    """One broker's live browser, driven entirely on its own worker thread."""

    # Speed (2026-07-10): the worker serializes EVERYTHING, so frame polls used to queue
    # ahead of the operator's clicks/typing and each poll cost a fresh screenshot — login
    # felt seconds-laggy. Now (a) frames are cached ~0.4s and served without touching the
    # worker when fresh, (b) input commands jump the queue ahead of frame requests, and
    # (c) input ops invalidate the cache so the very next poll shows their effect.
    _FRAME_CACHE_S = 0.4

    def __init__(self, broker: str, url: str):
        self.broker = broker
        self.url = url
        self.q: queue.PriorityQueue = queue.PriorityQueue()
        self._seq = 0
        self._seq_lock = threading.Lock()
        self.last_jpeg: bytes | None = None
        self.last_jpeg_ts: float = 0.0
        self.ready = threading.Event()
        self.err: str | None = None
        self.thread = threading.Thread(target=self._run, name=f"live-browser-{broker}",
                                       daemon=True)
        self.thread.start()

    def request(self, name: str, kw: dict | None = None, timeout: float = 20.0) -> dict:
        if not self.thread.is_alive():
            return {"error": "session not running"}
        ev = threading.Event()
        box: dict = {}
        prio = 1 if name == "frame" else 0     # operator input beats frame polls
        with self._seq_lock:
            self._seq += 1
            seq = self._seq
        self.q.put((prio, seq, (name, kw or {}, ev, box)))
        if not ev.wait(timeout):
            return {"error": "timeout"}
        return box.get("result", {"error": "no result"})

    def _run(self) -> None:
        try:
            from playwright.sync_api import sync_playwright
            p = sync_playwright().start()
            prof = state._path("browser_profiles") / self.broker
            prof.mkdir(parents=True, exist_ok=True)
            ctx = p.chromium.launch_persistent_context(
                str(prof), headless=True, viewport={"width": _VIEW_W, "height": _VIEW_H},
                args=["--no-sandbox", "--disable-dev-shm-usage"])
            pg = ctx.pages[0] if ctx.pages else ctx.new_page()
            try:
                from trading.broker_sense.interception import get_recorder
                get_recorder().attach(pg, self.broker)
            except Exception:
                pass
            try:
                pg.goto(self.url, timeout=45000, wait_until="domcontentloaded")
            except Exception:
                pass
        except Exception as e:
            self.err = f"{type(e).__name__}: {str(e)[:160]}"
            self.ready.set()
            return
        self.ready.set()
        stop = False
        while not stop:
            try:
                _, _, (name, kw, ev, box) = self.q.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                box["result"] = self._exec(pg, ctx, name, kw)
            except Exception as e:
                box["result"] = {"error": f"{type(e).__name__}: {str(e)[:140]}"}
            finally:
                ev.set()
            if name == "stop":
                stop = True
        try:
            ctx.close()
        except Exception:
            pass
        try:
            p.stop()
        except Exception:
            pass

    def _exec(self, pg, ctx, name: str, kw: dict) -> dict:
        if name == "frame":
            jpeg = pg.screenshot(type="jpeg", quality=45)
            self.last_jpeg, self.last_jpeg_ts = jpeg, time.monotonic()
            return {"jpeg": jpeg}
        if name == "click":
            pg.mouse.click(float(kw.get("x", 0)), float(kw.get("y", 0)))
            pg.wait_for_timeout(120)
            self.last_jpeg_ts = 0.0            # screen changed — next poll refetches
            return {"ok": True}
        if name == "type":
            pg.keyboard.type(str(kw.get("text", "")), delay=12)
            self.last_jpeg_ts = 0.0
            return {"ok": True}
        if name == "key":
            pg.keyboard.press(str(kw.get("key", "Enter")))
            pg.wait_for_timeout(120)
            self.last_jpeg_ts = 0.0
            return {"ok": True}
        if name == "scroll":
            pg.mouse.wheel(0, int(kw.get("dy", 400)))
            self.last_jpeg_ts = 0.0
            return {"ok": True}
        if name == "nav":
            pg.goto(str(kw.get("url") or self.url), timeout=30000, wait_until="domcontentloaded")
            self.last_jpeg_ts = 0.0
            return {"ok": True}
        if name == "save":
            sf = state._path("browser_sessions") / f"{self.broker}.json"
            sf.parent.mkdir(parents=True, exist_ok=True)
            ctx.storage_state(path=str(sf))
            try:
                import os
                import stat
                os.chmod(sf, stat.S_IRUSR | stat.S_IWUSR)     # 0600 — cookies are secrets
            except OSError:
                pass
            # heuristic: logged in if the login form / captcha is gone
            body = ""
            try:
                body = (pg.inner_text("body") or "")[:2000].lower()
            except Exception:
                pass
            has_pw = False
            try:
                has_pw = pg.query_selector("input[type=password]") is not None
            except Exception:
                pass
            logged_in = (not has_pw and "log in" not in body[:200]
                         and not any(k in body for k in ("select all images", "captcha")))
            return {"ok": True, "saved": str(sf), "looks_logged_in": logged_in, "url": pg.url}
        if name == "status":
            return {"ok": True, "url": pg.url, "title": (pg.title() or "")[:80],
                    "view": {"w": _VIEW_W, "h": _VIEW_H}}
        if name == "stop":
            return {"ok": True}
        return {"error": f"unknown command {name}"}


class LiveBrowser:
    """Manages one interactive browser session per broker."""

    def __init__(self):
        self._sessions: dict[str, _Session] = {}
        self._lock = threading.Lock()

    def start(self, broker: str, url: str) -> dict:
        with self._lock:
            s = self._sessions.get(broker)
            if s is None or not s.thread.is_alive():
                s = _Session(broker, url)
                self._sessions[broker] = s
        s.ready.wait(timeout=50)
        if s.err:
            return {"ok": False, "error": s.err}
        return {"ok": True, "broker": broker, "view": {"w": _VIEW_W, "h": _VIEW_H}}

    def frame(self, broker: str):
        s = self._sessions.get(broker)
        if s is None:
            return None
        # fresh-enough cache → serve instantly without occupying the worker thread
        if s.last_jpeg is not None and (time.monotonic() - s.last_jpeg_ts) < s._FRAME_CACHE_S:
            return s.last_jpeg
        r = s.request("frame", timeout=15)
        return r.get("jpeg")

    def action(self, broker: str, name: str, **kw) -> dict:
        s = self._sessions.get(broker)
        if s is None:
            return {"error": "not started"}
        return s.request(name, kw)

    def stop(self, broker: str) -> dict:
        with self._lock:
            s = self._sessions.pop(broker, None)
        if s is None:
            return {"ok": True, "note": "was not running"}
        return s.request("stop", timeout=10)

    def status(self, broker: str) -> dict:
        s = self._sessions.get(broker)
        if s is None or not s.thread.is_alive():
            return {"running": False, "broker": broker, "view": {"w": _VIEW_W, "h": _VIEW_H}}
        st = s.request("status", timeout=8)
        st["running"] = True
        return st


_LB: LiveBrowser | None = None


def get_live_browser() -> LiveBrowser:
    global _LB
    if _LB is None:
        _LB = LiveBrowser()
    return _LB
