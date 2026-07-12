"""trading/broker_sense/tab_pool.py — parked streaming tabs: the app IS the feed.

THE MOTTO (owner-approved 2026-07-12): all market data comes from NAVIGATING the account
web apps. ui_crawl visits pages serially (4/cycle, ~10s each) — good for the long tail,
but the funnel's SHORTLIST needs *continuous* freshness (the governor flips UI-only mode
only at ≥80% fresh coverage, and that must then STAY true). The trick this module adds:

  a Binance/Upstox chart page left OPEN keeps its own WebSocket pushing live klines,
  depth, mark-price and ticker for that symbol — zero re-navigation, zero polling, zero
  API calls by us. So we PARK one tab per top-shortlist symbol and let the app stream.

  ensure(symbols)  — reconcile the pool with the current shortlist: close tabs whose
                     symbol dropped out, open tabs for new entrants (bounded per call),
                     rotate ONE tab's chart timeframe per call (multi-TF coverage: the
                     rotation always returns to the funnel's primary 5m), and snapshot
                     each tab's REAL chart pixels for the vision lane + screen mirror.
  charts(symbol)   — fresh app-chart screenshots {tf: path} for the vision worker /
                     ocular (the owner's "multi-timeframe candle chart screenshots").
  status()         — honest pool state for the dashboard (tab_pool.json).

Interception does the capturing (sessions.page attaches the recorder before nav);
ui_data.feed_ws_kline keeps the parked symbols' candles continuously fresh. Playwright
sync API is thread-bound: ensure() must run on the browser-owner thread (the funnel
loop) — sessions' own-thread guard degrades safely otherwise. Operator logins win: when
the login lock is up, the pool drops its pages immediately (one Chromium per profile).
Levers: UI_TAB_POOL=0 kill, UI_TAB_POOL_N (6), UI_TAB_OPEN_PER_CALL (2),
UI_TAB_SNAP_S (20), UI_TAB_TFS ("5m,15m,1h,4h").
"""
from __future__ import annotations

import os
import re
import time

from trading import state

_STATUS_FILE = "tab_pool.json"
_SHOT_DIRNAME = "app_charts"
_TF_LABELS = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
              "1h": "1h", "4h": "4h", "1d": "1D"}


def enabled() -> bool:
    return os.environ.get("UI_TAB_POOL", "1") in ("1", "true", "TRUE", "yes")


def _pool_n() -> int:
    try:
        return max(1, int(os.environ.get("UI_TAB_POOL_N", "6")))
    except ValueError:
        return 6


def _rotation_tfs() -> list[str]:
    raw = os.environ.get("UI_TAB_TFS", "5m,15m,1h,4h")
    tfs = [t.strip() for t in raw.split(",") if t.strip() in _TF_LABELS]
    return tfs or ["5m", "15m", "1h", "4h"]


def _rotation_seq() -> list[str]:
    """15m/1h/4h visits interleaved with returns to 5m — the funnel's primary TF must
    dominate wall-clock so its kline stream (and 900s freshness window) never lapses."""
    tfs = _rotation_tfs()
    primary = tfs[0]
    seq: list[str] = []
    for tf in tfs[1:]:
        seq += [primary, tf]
    return seq or [primary]


def _flat(symbol: str) -> str:
    s = re.sub(r"[/:]", "", (symbol or "").upper())
    return s[:-4] if s.endswith("USDTUSDT") else s


def _shot_dir():
    d = state._path(_SHOT_DIRNAME)
    d.mkdir(parents=True, exist_ok=True)
    return d


class TabPool:
    def __init__(self, sessions, broker: str = "binance"):
        self.sessions = sessions
        self.broker = broker
        self._tabs: dict[str, dict] = {}   # SYM -> {page, tf, rot_i, opened_ts, last_snap}
        self._rot_cursor = 0               # which tab rotates its TF this call (staggered)

    # ── reconcile with the shortlist ─────────────────────────────────────────
    def ensure(self, symbols: list[str], *, deadline: float | None = None) -> dict:
        rep = {"broker": self.broker, "parked": [], "opened": [], "closed": [],
               "rotated": None, "snaps": 0, "errors": []}
        if not enabled():
            rep["errors"].append("disabled (UI_TAB_POOL=0)")
            return rep
        try:
            from trading.broker_sense.sessions import login_in_progress
            if login_in_progress(self.broker):
                self.drop_all("operator login")
                rep["errors"].append("yielded to operator login")
                return rep
        except Exception:
            pass

        def _over() -> bool:
            return deadline is not None and time.monotonic() > deadline

        targets = [s for s in symbols if s][: _pool_n()]
        want = {_flat(s): s for s in targets}

        # 1) prune: dead pages + symbols that left the shortlist
        for sym in list(self._tabs):
            t = self._tabs[sym]
            pg = t.get("page")
            dead = pg is None
            try:
                dead = dead or pg.is_closed()
            except Exception:
                dead = True
            if dead:
                self._tabs.pop(sym, None)
                continue
            if sym not in want:
                try:
                    pg.close()
                except Exception:
                    pass
                self._tabs.pop(sym, None)
                rep["closed"].append(sym)

        # 2) open missing tabs (bounded per call so ensure() fits the budget tail)
        try:
            per_call = max(1, int(os.environ.get("UI_TAB_OPEN_PER_CALL", "2")))
        except ValueError:
            per_call = 2
        opened = 0
        for sym, orig in want.items():
            if sym in self._tabs or opened >= per_call or _over():
                continue
            try:
                from trading.broker_sense import ui_crawl
                url = ui_crawl._page_url(self.broker, orig)
                pg = self.sessions.page(self.broker, url, timeout_ms=15000)
                if pg is None:
                    rep["errors"].append(f"{sym}: no page/session")
                    continue
                # the app REMEMBERS the last interval per profile (live-probe: a fresh
                # tab opened on 15m) — click the primary explicitly; a failed click
                # marks the tab stray so the self-heal pass keeps retrying.
                primary_tf = _rotation_tfs()[0]
                landed = self._click_tf(pg, primary_tf)
                self._tabs[sym] = {"page": pg,
                                   "tf": primary_tf if landed else "?",
                                   "rot_i": 0, "opened_ts": time.time(),
                                   "last_snap": 0.0}
                rep["opened"].append(sym)
                opened += 1
            except Exception as e:
                rep["errors"].append(f"{sym}: {type(e).__name__}: {str(e)[:60]}")

        # 3) rotate ONE tab through a higher TF and BACK to the primary in the SAME
        # call. Leaving a tab parked on 15m until its next rotation turn (~pool_size
        # cycles ≈ 30min) would lapse its 5m kline stream past ui_data's 900s window
        # and flip the governor OFF — the visit only needs a few seconds for the app
        # to fire that TF's kline fetch (captured) and a chart snapshot.
        tfs = _rotation_tfs()
        primary, extras = tfs[0], tfs[1:]
        # never click a tab the operator is solving a challenge on
        live = sorted(s for s in self._tabs if not self._tabs[s].get("challenged"))
        # SELF-HEAL first (live-probe 2026-07-12): a failed rotate-back strands a tab on
        # a higher TF — its 5m kline stream stops and the symbol's primary freshness
        # decays. Recover stranded tabs before spending this call's rotation slot.
        strays = [s for s in live if self._tabs[s]["tf"] != primary]
        for sym in strays:
            if _over():
                break
            if self._click_tf(self._tabs[sym]["page"], primary):
                self._tabs[sym]["tf"] = primary
                rep["rotated"] = f"{sym}→{primary} (recovered)"
        if strays:
            live = []                              # recovery used this call's slot
        if live and extras and not _over():
            sym = live[self._rot_cursor % len(live)]
            self._rot_cursor += 1
            t = self._tabs[sym]
            nxt = extras[t["rot_i"] % len(extras)]
            t["rot_i"] += 1
            if self._click_tf(t["page"], nxt):
                t["tf"] = nxt
                if self._snap(sym, t):                # the higher-TF app-chart pixels
                    t["last_snap"] = time.time()
                    rep["snaps"] += 1
                if self._click_tf(t["page"], primary):
                    t["tf"] = primary
                rep["rotated"] = f"{sym}→{nxt}→{t['tf']}"

        # 4) snapshot each parked tab's REAL chart pixels (throttled per tab)
        try:
            snap_s = float(os.environ.get("UI_TAB_SNAP_S", "20"))
        except ValueError:
            snap_s = 20.0
        now = time.time()
        for sym, t in self._tabs.items():
            if _over():
                break
            if now - t["last_snap"] < snap_s:
                continue
            if self._snap(sym, t):
                t["last_snap"] = now
                rep["snaps"] += 1
        rep["parked"] = [{"symbol": s, "tf": t["tf"],
                          "age_s": round(time.time() - t["opened_ts"], 1)}
                         for s, t in sorted(self._tabs.items())]
        self._persist(rep)
        return rep

    def _click_tf(self, pg, tf: str) -> bool:
        """Flip the chart's interval tab like a human — read-only navigation (the only
        click). Binance's TF tabs carry stable element ids (id="5m"/"15m"/"1h"…,
        live-DOM verified 2026-07-12) but a DESELECTED tf drops out of the quick row
        into the expand dropdown (svg.interval-expand-btn) — open it when the id isn't
        visible. [id=…] not #…: css #5m is invalid for digit-leading ids."""
        tf_id = tf.lower()

        def _try_direct() -> bool:
            for el in pg.locator(f'[id="{tf_id}"]').all()[:3]:
                try:
                    if el.is_visible(timeout=600):
                        el.click(timeout=1500)
                        pg.wait_for_timeout(900)   # let the app fire the TF's kline fetch
                        return True
                except Exception:
                    continue
            return False

        try:
            if _try_direct():
                return True
            btn = pg.locator("svg.interval-expand-btn").first
            if btn.is_visible(timeout=600):
                btn.click(timeout=1500)
                pg.wait_for_timeout(800)
                if _try_direct():
                    return True
                label = _TF_LABELS.get(tf, tf)      # popup may label, not id
                for el in pg.locator(f"text=/^{label}$/i").all()[:5]:
                    try:
                        if el.is_visible(timeout=500):
                            el.click(timeout=1500)
                            pg.wait_for_timeout(900)
                            return True
                    except Exception:
                        continue
        except Exception:
            pass
        return False

    def _snap(self, sym: str, t: dict) -> bool:
        """JPEG of the tab (~50-150ms) → app_charts/<SYM>__<tf>.jpg (atomic tmp+rename)
        + a screen-mirror frame so the owner can WATCH the parked eyes."""
        pg = t.get("page")
        try:
            if pg is None or pg.is_closed():
                return False
            # HUMAN-CAPTCHA HANDOFF (owner 2026-07-12): parked tabs mirror via
            # record_bytes, which never runs the challenge guard — a CAPTCHA on a
            # parked tab was invisible. Non-blocking guard: on a challenge it raises
            # the alert + VNC and we leave the tab UNTOUCHED (no snap/click fights
            # the operator's drag) until the guard reports clear.
            try:
                from trading.broker_sense import human_handoff
                if human_handoff.guard(self.broker, pg, block=False):
                    t["challenged"] = True
                    return False
                if t.pop("challenged", None):
                    pass                        # cleared — resume normal snaps
            except Exception:
                pass
            raw = pg.screenshot(type="jpeg", quality=45, timeout=4000)
        except Exception:
            return False
        try:
            path = _shot_dir() / f"{sym}__{t['tf']}.jpg"
            tmp = path.with_suffix(".jpg.tmp")
            tmp.write_bytes(raw)
            os.replace(tmp, path)
        except Exception:
            return False
        try:
            from trading.broker_sense import screen_mirror
            screen_mirror.record_bytes(self.broker, raw, title=f"park {sym} {t['tf']}")
        except Exception:
            pass
        return True

    def pump(self, *, budget_s: float = 1.5) -> int:
        """CHEAP owner-thread tick: process each parked tab's QUEUED WebSocket frames so
        the app's live klines/depth land in interception → ui_data continuously — even
        while the funnel's main thread is busy with CPU brain-work (the root cause of
        lapsed coverage + frozen mirror, 2026-07-12: Playwright sync only pumps a page's
        WS 'framereceived' events when we touch that page, so idle CPU stretches starved
        the streams). A tiny wait_for_timeout per tab pumps its event loop. Returns the
        number of tabs pumped. No snapshots, no clicks — call it OFTEN and near-free."""
        if not enabled() or not self._tabs:
            return 0
        try:
            from trading.broker_sense.sessions import login_in_progress
            if login_in_progress(self.broker):
                return 0
        except Exception:
            pass
        pumped = 0
        t0 = time.monotonic()
        for sym in list(self._tabs):
            if time.monotonic() - t0 > budget_s:
                break
            t = self._tabs[sym]
            pg = t.get("page")
            try:
                if pg is None or pg.is_closed() or t.get("challenged"):
                    continue
                pg.wait_for_timeout(60)          # pump this page's event loop (WS frames)
                pumped += 1
            except Exception:
                # dead page — let refresh()/ensure() reap it; don't churn here
                continue
        return pumped

    def refresh(self, *, deadline: float | None = None) -> dict:
        """Snapshot + keep the ALREADY-parked tabs warm, WITHOUT opening/closing any.
        Called from the funnel's inter-cycle sleep loop (owner thread) so the parked
        tabs stream continuously and the mirror keeps MOVING between cycles — the
        per-cycle ensure() runs at the end of the budget and had no time left to snap
        (observed 2026-07-12: parked tabs, snaps=0, tf='?', frozen mirror). Cheap: one
        snapshot per due tab, plus a stray-TF self-heal. Never opens a page."""
        rep = {"broker": self.broker, "snapped": [], "healed": [], "dead": []}
        if not enabled() or not self._tabs:
            return rep
        try:
            from trading.broker_sense.sessions import login_in_progress
            if login_in_progress(self.broker):
                return rep                            # operator has the browser — don't touch
        except Exception:
            pass
        primary = _rotation_tfs()[0]
        try:
            snap_s = float(os.environ.get("UI_TAB_SNAP_S", "20"))
        except ValueError:
            snap_s = 20.0
        now = time.time()
        for sym in sorted(self._tabs):
            if deadline is not None and time.monotonic() > deadline:
                break
            t = self._tabs[sym]
            pg = t.get("page")
            try:
                if pg is None or pg.is_closed():
                    self._tabs.pop(sym, None)
                    rep["dead"].append(sym)
                    continue
            except Exception:
                self._tabs.pop(sym, None)
                rep["dead"].append(sym)
                continue
            if t.get("challenged"):                   # operator solving a CAPTCHA here
                continue
            if t.get("tf") in ("?", None) and self._click_tf(pg, primary):
                t["tf"] = primary                     # heal the TF the starved open() couldn't set
                rep["healed"].append(sym)
            if now - t.get("last_snap", 0.0) >= snap_s and self._snap(sym, t):
                t["last_snap"] = now
                rep["snapped"].append(sym)
        if rep["snapped"] or rep["healed"] or rep["dead"]:
            self._persist({"parked": [{"symbol": s, "tf": self._tabs[s]["tf"],
                                       "age_s": round(now - self._tabs[s]["opened_ts"], 1)}
                                      for s in self._tabs],
                           "opened": [], "closed": rep["dead"], "rotated": None,
                           "snaps": len(rep["snapped"]), "errors": []})
        return rep

    def drop_all(self, reason: str = "") -> None:
        """Close every pooled page (operator login / shutdown). Context stays alive.
        The reason lands in tab_pool.json — the diagnostic for a coverage collapse."""
        n = len(self._tabs)
        for sym in list(self._tabs):
            try:
                pg = self._tabs[sym].get("page")
                if pg is not None:
                    pg.close()
            except Exception:
                pass
            self._tabs.pop(sym, None)
        if n:
            try:
                state.update_json(_STATUS_FILE, {self.broker: {
                    "ts": time.time(), "parked": [], "dropped": n,
                    "drop_reason": reason or "unspecified"}})
            except Exception:
                pass

    def _persist(self, rep: dict) -> None:
        try:
            state.update_json(_STATUS_FILE, {self.broker: {
                "ts": time.time(), "parked": rep["parked"],
                "opened": rep["opened"], "closed": rep["closed"],
                "rotated": rep["rotated"], "snaps": rep["snaps"],
                "errors": rep["errors"][-5:]}})
        except Exception:
            pass


# ── cross-process read paths (vision worker / ocular / dashboard) ────────────
def charts(symbol: str, *, max_age_s: float = 600.0) -> dict[str, str]:
    """Fresh app-chart screenshots {tf: absolute_path} for `symbol` — the REAL pixels
    the owner asked the vision model to read. Empty dict when none are fresh."""
    out: dict[str, str] = {}
    flat = _flat(symbol)
    try:
        d = _shot_dir()
        now = time.time()
        for p in d.glob(f"{flat}__*.jpg"):
            tf = p.stem.split("__", 1)[1] if "__" in p.stem else None
            if tf and now - p.stat().st_mtime <= max_age_s:
                out[tf] = str(p)
    except Exception:
        pass
    return out


def latest_shot(symbol: str, tf: str, *, max_age_s: float = 600.0) -> str | None:
    return charts(symbol, max_age_s=max_age_s).get(tf)


def status() -> dict:
    return state.load_json(_STATUS_FILE, {})


_POOLS: dict[tuple[int, str], TabPool] = {}


def get_pool(sessions, broker: str = "binance") -> TabPool:
    key = (id(sessions), broker)
    if key not in _POOLS:
        _POOLS[key] = TabPool(sessions, broker)
    return _POOLS[key]
