"""trading/brain/gui/actions.py — the ACT layer of the computer-use agent.

Three ways to press a button, weakest-coupling last, all guarded:

  1. in-process control (the reliable path, NO new dep) — call trading.online.controls /
     live_loop directly. This is the same code the dashboard POST handler runs, so the agent's
     action lands on the SAME persisted truth Telegram + the UI share.
  2. http button-press (stdlib urllib) — POST to the dashboard's own control endpoint exactly
     like the browser does ({action, market, ...}). This is "press the button as a user", and
     it also works against a remote/tunnelled dashboard.
  3. dom click (Playwright, activate-on-install) — find a control by visible label and click
     the pixels (adapted from vendor/browser_use_src). Pixel-true, for surfaces with no API.

SAFETY (secrets-safe + paper-first): every mutating action is gated. `dry_run=True` is the
default — the agent plans the action and returns what it WOULD do without firing. Real money
is doubly gated: a REAL-mode switch still requires the controls layer's own allow_live + confirm
2-step, and the executor refuses live-affecting actions unless constructed with allow_live=True.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field

try:
    import playwright  # noqa: F401
    _HAS_PLAYWRIGHT = True
except Exception:
    _HAS_PLAYWRIGHT = False

# actions that can affect live trading — never fired unless the executor is armed
_LIVE_AFFECTING = {"mode", "allow_live"}
# the control-surface verbs we understand (mirror dashboard POST /api/trading/online/control)
_CONTROL_ACTIONS = {"start", "stop", "pause", "halt", "panic", "mode", "allow_live",
                    "segments", "toggle_segment", "set_balance", "top_up", "reset_wallet",
                    "set_strategy", "close_all"}


@dataclass
class ActionResult:
    """Honest outcome of one attempted action."""
    action: str
    target: str = ""
    method: str = ""                  # "in_process" | "http" | "dom" | "planned"
    ok: bool = False
    dry_run: bool = True
    detail: dict = field(default_factory=dict)
    reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class ActionExecutor:
    """Presses buttons / drives controls on a dashboard, three ways, all guarded."""

    def __init__(self, *, allow_live: bool = False, default_dry_run: bool = True):
        # allow_live arms the executor to even ATTEMPT live-affecting actions; the controls
        # layer still enforces its own allow_live+confirm 2-step on top of this.
        self.allow_live = bool(allow_live)
        self.default_dry_run = bool(default_dry_run)

    # ---- guard ------------------------------------------------------------
    def _guard(self, action: str, dry_run: bool) -> str | None:
        if action in _LIVE_AFFECTING and not self.allow_live and not dry_run:
            return (f"action {action!r} can affect live trading; executor not armed "
                    f"(construct ActionExecutor(allow_live=True) AND pass dry_run=False)")
        return None

    # ---- 1. in-process control (reliable, no dep) -------------------------
    def control(self, action: str, market: str = "CRYPTO", *, dry_run: bool | None = None,
                **kw) -> ActionResult:
        """Drive trading.online.controls / live_loop in-process — the same path the dashboard
        POST handler runs. Returns what it did (or would do, when dry_run)."""
        dry = self.default_dry_run if dry_run is None else bool(dry_run)
        action = str(action).lower()
        res = ActionResult(action=action, target=market, method="in_process", dry_run=dry)
        if action not in _CONTROL_ACTIONS:
            res.reason = f"unknown control action {action!r}"
            return res
        blocked = self._guard(action, dry)
        if blocked:
            res.reason = blocked
            return res
        if dry:
            res.ok = True
            res.method = "planned"
            res.detail = {"would_call": f"controls.{action}", "market": market, "kw": kw}
            res.reason = "dry_run — not fired"
            return res
        try:
            from trading.online import controls
            if action == "start":
                # CRYPTO start/stop also drives the Freqtrade bot, mirroring the server handler
                if str(market).upper() == "CRYPTO":
                    self._freq_bot("start")
                res.detail = controls.start(market)
            elif action == "stop":
                if str(market).upper() == "CRYPTO":
                    self._freq_bot("stop")
                res.detail = controls.stop(market)
            elif action == "pause":
                res.detail = controls.pause(market)
            elif action == "halt":
                res.detail = controls.halt(market)
            elif action == "panic":
                res.detail = controls.panic()
            elif action == "mode":
                res.detail = controls.set_mode(market, str(kw.get("mode", "PAPER")).upper(),
                                               confirm=bool(kw.get("confirm", False)))
            elif action == "allow_live":
                res.detail = controls.set_allow_live(market, bool(kw.get("allow", False)))
            elif action == "segments":
                res.detail = controls.set_segments(market, kw.get("segments") or [])
            elif action == "toggle_segment":
                res.detail = controls.toggle_segment(market, kw.get("segment", ""))
            elif action == "set_balance":
                res.detail = controls.set_balance(market, float(kw.get("amount", 0.0)),
                                                  kw.get("portfolio_id", "default"))
            elif action == "top_up":
                res.detail = controls.top_up(market, float(kw.get("amount", 0.0)),
                                             kw.get("portfolio_id", "default"))
            elif action == "reset_wallet":
                res.detail = controls.reset_wallet(market, kw.get("portfolio_id", "default"))
            elif action == "set_strategy":
                from trading.online.live_loop import get_loop
                res.detail = {"config": get_loop().set_config(**{k: v for k, v in kw.items()
                                                                 if v is not None})}
            elif action == "close_all":
                from trading.online.live_loop import get_loop
                res.detail = {"result": get_loop().close_all()}
            res.ok = True
        except (PermissionError, ValueError) as e:        # refused by the safety guard
            res.reason = str(e)
        except Exception as e:
            res.reason = f"{type(e).__name__}: {e}"
        return res

    @staticmethod
    def _freq_bot(verb: str) -> None:
        """Best-effort start/stop of the Freqtrade bot (FreqUI's native action)."""
        try:
            from trading.crypto.engine_client import CryptoEngineClient
            getattr(CryptoEngineClient(), verb)()
        except Exception:
            pass

    # ---- 2. http button-press (press it like a user) ----------------------
    def http_control(self, target, action: str, market: str = "CRYPTO", *,
                     dry_run: bool | None = None, **body) -> ActionResult:
        """POST the dashboard's own control endpoint exactly like the browser. Works against a
        remote/tunnelled dashboard too. `target` is a DashboardTarget (own dashboard)."""
        dry = self.default_dry_run if dry_run is None else bool(dry_run)
        action = str(action).lower()
        res = ActionResult(action=action, target=getattr(target, "name", str(target)),
                           method="http", dry_run=dry)
        blocked = self._guard(action, dry)
        if blocked:
            res.reason = blocked
            return res
        url = f"{target.api_base}/api/trading/online/control"
        payload = {"action": action, "market": market, **body}
        if dry:
            res.ok = True
            res.method = "planned"
            res.detail = {"would_post": url, "payload": payload}
            res.reason = "dry_run — not fired"
            return res
        try:
            data = json.dumps(payload).encode()
            req = urllib.request.Request(url, data=data, method="POST",
                                         headers={"Content-Type": "application/json",
                                                  "User-Agent": "brain-gui-agent"})
            with urllib.request.urlopen(req, timeout=6.0) as r:
                res.detail = json.loads(r.read().decode("utf-8", "replace") or "{}")
            res.ok = bool(res.detail.get("ok", True))
            if not res.ok:
                res.reason = str(res.detail.get("reason") or res.detail.get("error") or "refused")
        except (urllib.error.URLError, OSError, ValueError) as e:
            res.reason = f"{type(e).__name__}: {e}"
        return res

    # ---- 3. dom click (pixel-true, Playwright upgrade) --------------------
    def dom_click(self, target, label: str, *, dry_run: bool | None = None) -> ActionResult:
        """Find a control by visible label and click it with Playwright. Needs the upgrade dep;
        until installed, returns an honest 'needs playwright' planned result."""
        dry = self.default_dry_run if dry_run is None else bool(dry_run)
        res = ActionResult(action=f"click:{label}", target=getattr(target, "name", str(target)),
                           method="dom", dry_run=dry)
        if not _HAS_PLAYWRIGHT:
            res.method = "planned"
            res.reason = ("playwright not installed — DOM clicking is the activate-on-install "
                          "upgrade layer (pip install playwright && playwright install chromium). "
                          "vendored source: vendor/browser_use_src")
            return res
        if dry:
            res.ok = True
            res.method = "planned"
            res.detail = {"would_click": label, "url": target.web_url}
            res.reason = "dry_run — not fired"
            return res
        try:                                              # pragma: no cover (needs browser)
            from playwright.sync_api import sync_playwright
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(target.web_url, timeout=15000)
                page.get_by_text(label, exact=False).first.click(timeout=5000)
                res.detail = {"clicked": label, "title": page.title()}
                browser.close()
            res.ok = True
        except Exception as e:                            # pragma: no cover
            res.reason = f"{type(e).__name__}: {e}"
        return res

    def capabilities(self) -> dict:
        return {"in_process": True, "http": True, "dom_playwright": _HAS_PLAYWRIGHT,
                "armed_for_live": self.allow_live, "default_dry_run": self.default_dry_run}
