"""trading/broker_sense/sessions.py — persistent logged-in broker browser sessions (saver H).

One Playwright browser per process; one CONTEXT per broker app whose cookies/localStorage are
persisted to trading/state/browser_sessions/<broker>.json (0600), so a login survives restarts
and the funnel never re-logs-in while a session is valid. Login flow (owner decision #3):

  first time  → vault ask IN DETAIL for user-id + password (each field explained) → saved
                encrypted FOREVER in the vault;
  afterwards  → the app usually restores from storage-state; when it does demand a fresh
                OTP, the chat ask is OTP-ONLY ("Angel One needs the 6-digit OTP it just sent
                you — I already have your saved client-ID/PIN") and the consumed OTP is
                cleared from the vault after use (one-time by construction).

The OTP wait POLLS the vault (the owner answers in Brain Chat → /api/trading/credentials →
vault.submit merge) with a hard timeout — a cycle is never wedged on a login. Read-only
guard: this layer only navigates/logs in; order placement lives in exec_adapter (APIs).
"""
from __future__ import annotations

import os
import re
import stat
import time

from trading import state
from trading.broker_sense.brokers import REGISTRY, BrokerApp

_SESS_DIR = "browser_sessions"
_OTP_WAIT_S = float(os.environ.get("BROKER_SENSE_OTP_WAIT", "180"))
_OTP_POLL_S = 3.0
# never type into / click anything that smells like an order control (same guard family as
# gui.web_screener._FORBIDDEN — login pages only)
_FORBIDDEN = re.compile(r"\b(buy|sell|order|place|trade|confirm|withdraw|transfer|deposit)\b", re.I)


def _sess_path(broker: str):
    d = state._path(_SESS_DIR)
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{broker}.json"


def has_session(broker: str) -> bool:
    """True if a saved (persisted) browser session exists for `broker` — QR logins produce
    one with no vault credentials at all, and it counts as connected."""
    try:
        return _sess_path(broker).exists()
    except Exception:
        return False


_USER_SEL = ("input[type=email], input[type=tel], input[name*=user i], input[name*=email i], "
             "input[name*=mobile i], input[name*=phone i], input[autocomplete=username], "
             "input[placeholder*=email i], input[placeholder*=phone i], "
             "input[placeholder*=mobile i]")
_SUBMIT_SEL = "button[type=submit], input[type=submit], button"


def _looks_like_login(pg) -> bool:
    """True if the page is a login form — including MULTI-STEP flows (e.g. Binance) whose first
    step shows ONLY an email/phone field + a 'Log in' button, with the password on step 2."""
    try:
        if pg.query_selector("input[type=password], input[autocomplete='one-time-code']"):
            return True
        if pg.query_selector(_USER_SEL):                 # step-1: email/phone field present…
            body = (pg.inner_text("body") or "")[:3000].lower()
            return any(k in body for k in ("log in", "login", "sign in", "log-in", "sign-in"))
    except Exception:
        pass
    return False


# captcha-SPECIFIC phrases only — NOT generic words like "slider"/"unusual activity" that appear
# on ordinary carousels/markets pages (those false-flagged a real login as failed).
_CHALLENGE_TXT = ("select all images", "select each image", "please select all", "captcha",
                  "slide to complete", "slide the puzzle", "verify you are human",
                  "i'm not a robot", "are you human", "complete the security check")


def is_human_challenge(pg) -> bool:
    """Public: True if `pg` shows a human-only security challenge (image CAPTCHA, slide
    puzzle, bot check). Thin, never-raising wrapper over the login detector so mid-session
    loops (via human_handoff.guard) reuse the exact same detection as the login flow."""
    try:
        return _challenge_present(pg)
    except Exception:
        return False


def _challenge_present(pg) -> bool:
    """True if the page shows a human-only challenge (image CAPTCHA, puzzle, bot check). Kept
    specific: a page with a promo carousel or the word 'verification' is NOT a challenge."""
    try:
        body = (pg.inner_text("body") or "")[:4000].lower()
        if any(k in body for k in _CHALLENGE_TXT):
            return True
        # only a VISIBLE captcha widget counts — the invisible reCAPTCHA v3 badge that sits on
        # many login pages (e.g. Angel One) needs no human step and must not abort the login
        for el in pg.query_selector_all(
                "iframe[src*=captcha i], [class*=captcha i], [id*=captcha i], "
                "[class*=geetest i], [class*=recaptcha i], [class*=hcaptcha i]"):
            cls = (el.get_attribute("class") or "")
            if "grecaptcha-badge" in cls:
                continue
            box = el.bounding_box()
            if el.is_visible() and box and box["width"] > 60 and box["height"] > 60:
                return True
        return False
    except Exception:
        return False


# NOT the real submit: SSO providers + cookie-consent buttons whose text also contains
# "sign in"/"continue" — clicking these derails a multi-step login.
_NOT_SUBMIT = ("google", "apple", "telegram", "passkey", "qr", "facebook", "wallet",
               "cookie", "accept", "continue with", "sign in with", "sign up", "register",
               "create account")


_IDENTITY_HINTS = re.compile(r"mobile|phone|user|email|client|login\s*id", re.I)


def _otp_attrs_are_code_box(attrs: dict) -> bool:
    """True if an input's attributes describe a one-time-code box rather than the login's
    identity field (mobile/email/client-id), which can share inputmode=numeric. Pure predicate
    so the false-'OTP sent' regression stays unit-testable without a browser."""
    if "one-time-code" in (attrs.get("autocomplete") or ""):
        return True
    ident = " ".join(str(attrs.get(k) or "") for k in
                     ("placeholder", "aria-label", "name", "id"))
    if _IDENTITY_HINTS.search(ident):
        return False
    if re.search(r"otp|code|token", ident, re.I):
        return True
    # a bare numeric box only counts when it is SHORT (OTP boxes cap at 4-8 chars);
    # unlabeled full-width numeric fields are identity inputs, not code boxes
    try:
        return 1 <= int(attrs.get("maxlength") or 0) <= 8
    except (TypeError, ValueError):
        return False


def _otp_input(el) -> bool:
    attrs = {k: el.get_attribute(k) for k in
             ("autocomplete", "placeholder", "aria-label", "name", "id", "maxlength")}
    return _otp_attrs_are_code_box(attrs)


def _click_login(pg):
    """Click the PRIMARY login/next submit button — never an SSO/consent button or an order
    control. Exact 'log in'/'sign in'/'next' beats a generic 'continue'."""
    try:
        cands = []
        for b in pg.query_selector_all(_SUBMIT_SEL):
            t = " ".join((b.inner_text() or "").split()).lower()
            if not t or _FORBIDDEN.search(t) or any(n in t for n in _NOT_SUBMIT):
                continue
            if t in ("log in", "login", "sign in", "next", "submit", "continue", "confirm",
                     "proceed"):                              # "proceed" = Angel One's step-1 submit
                cands.append((0, b))                          # exact primary submit → best
            elif any(k in t for k in ("log in", "login", "sign in", "next", "submit", "proceed")):
                cands.append((1, b))
        for _rank, b in sorted(cands, key=lambda x: x[0]):
            b.click()
            return True
    except Exception:
        pass
    return False


class SessionManager:
    """Owns the browser + one persistent context per broker. Lazy: Playwright starts on
    first page request; everything degrades honestly when it's unavailable."""

    def __init__(self, *, headless: bool | None = None):
        # HEADED-under-Xvfb (2026-07-07): SPAs with headless-detection (Upstox Pro hangs on
        # "Loading" forever in a headless browser but renders normally headed) need a REAL
        # browser on a virtual display. BROKER_SENSE_HEADED=1 flips this whole manager to a
        # headed context and auto-starts Xvfb when there's no DISPLAY. Default stays headless
        # (Binance etc. render fine + it's lighter). See memory human-ui-headed-xvfb.
        if headless is None:
            headless = os.environ.get("BROKER_SENSE_HEADED", "") not in ("1", "true", "TRUE", "yes", "on")
        self.headless = headless
        self._pw = None
        self._browser = None
        self._xvfb = None                          # Popen handle for an auto-started Xvfb
        self._contexts: dict[str, object] = {}
        self.events: list[dict] = []               # honest session log for the dashboard

    # ── virtual display (headed rendering without a physical screen) ──────────────
    def _ensure_display(self) -> None:
        """When running headed with no DISPLAY, start an Xvfb virtual screen so the real
        (non-headless) browser can render. No-op if headless, DISPLAY already set, or Xvfb
        missing (the browser then fails honestly rather than silently rendering nothing)."""
        if self.headless or os.environ.get("DISPLAY") or self._xvfb is not None:
            return
        import shutil
        if not shutil.which("Xvfb"):
            self._log("no_xvfb", "-", "Xvfb not installed — headed render needs it (apt install xvfb)")
            return
        import subprocess
        disp = os.environ.get("BROKER_SENSE_DISPLAY", ":99")
        try:
            self._xvfb = subprocess.Popen(
                ["Xvfb", disp, "-screen", "0", "1600x1000x24", "-nolisten", "tcp"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1.5)                        # let the X server come up before Chromium
            os.environ["DISPLAY"] = disp
            self._log("xvfb_started", "-", f"virtual display {disp} up for headed rendering")
        except Exception as e:
            self._log("xvfb_fail", "-", f"Xvfb start failed: {str(e)[:80]}")

    # stealth args: a headed profile that doesn't advertise automation renders like a human's
    _CHROMIUM_ARGS = ["--no-sandbox", "--disable-dev-shm-usage",
                      "--disable-blink-features=AutomationControlled",
                      # Kill the native prompts/banners the brain otherwise wastes a vision
                      # glance() on (2026-07-11 slow-nav): the Binance "Show notifications"
                      # permission bubble and the "Restore pages? Chromium didn't shut down
                      # correctly" crash-restore banner. Auto-deny every permission prompt so
                      # no site can pop one over the page and stall navigation.
                      "--disable-notifications",
                      "--deny-permission-prompts",
                      "--hide-crash-restore-bubble"]

    # ── plumbing ────────────────────────────────────────────────────────────────
    def _log(self, kind: str, broker: str, msg: str) -> None:
        self.events.append({"ts": time.time(), "kind": kind, "broker": broker, "msg": msg})
        self.events = self.events[-100:]
        try:
            from trading.brain import activity_feed as feed
            feed.emit(kind, msg, site=broker)
        except Exception:
            pass

    def _ensure_browser(self):
        if self._browser is not None:
            return self._browser
        self._ensure_display()
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=self.headless, args=self._CHROMIUM_ARGS)
        return self._browser

    def context(self, broker: str):
        """Context for `broker`. Prefers the PERSISTENT PROFILE created by the live-browser
        login (browser_profiles/<broker>) because device-bound logins (e.g. Binance) survive
        ONLY in the original profile — an exported storage_state loaded into a fresh context
        gets bounced back to login. Falls back to storage_state / a plain context otherwise."""
        if broker in self._contexts:
            return self._contexts[broker]
        prof = state._path("browser_profiles") / broker
        if prof.exists() and any(prof.iterdir()):
            try:                                  # the profile can only be opened by ONE process;
                from playwright.sync_api import sync_playwright  # if another holds it, chromium's
                self._ensure_display()            # headed needs a screen (auto-Xvfb)
                if self._pw is None:              # SingletonLock makes this throw — degrade to a
                    self._pw = sync_playwright().start()         # storage_state context instead of
                ctx = self._pw.chromium.launch_persistent_context(   # crashing the whole cycle
                    str(prof), headless=self.headless, viewport={"width": 1600, "height": 1000},
                    args=self._CHROMIUM_ARGS)
                self._contexts[broker] = ctx
                return ctx
            except Exception:
                self._log("profile_busy", broker,
                          f"{broker} profile is in use by another process — using saved cookies")
        b = self._ensure_browser()
        sp = _sess_path(broker)
        kw = {"viewport": {"width": 1600, "height": 1000}}
        if sp.exists():
            kw["storage_state"] = str(sp)
        ctx = b.new_context(**kw)
        self._contexts[broker] = ctx
        return ctx

    def save_state(self, broker: str) -> None:
        ctx = self._contexts.get(broker)
        if ctx is None:
            return
        sp = _sess_path(broker)
        ctx.storage_state(path=str(sp))
        try:
            os.chmod(sp, stat.S_IRUSR | stat.S_IWUSR)       # 0600 — session cookies are secrets
        except OSError:
            pass

    def close(self) -> None:
        for name in list(self._contexts):
            try:
                self.save_state(name)
                self._contexts.pop(name).close()
            except Exception:
                pass
        for obj in (self._browser, self._pw):
            try:
                if obj is not None:
                    obj.close() if obj is self._browser else obj.stop()
            except Exception:
                pass
        self._browser = self._pw = None

    # ── the login flow ──────────────────────────────────────────────────────────
    def page(self, broker: str, url: str | None = None, *, timeout_ms: int = 30000):
        """Open `url` (default: app home) in the broker's persistent context, logging in if
        the app asks. Returns a live Page, or None with the reason logged (never raises on
        a login wall — the funnel continues with public/API paths)."""
        app = REGISTRY[broker]
        ctx = self.context(broker)
        pg = ctx.new_page()
        try:                                  # capture the app's own internal JSON traffic —
            from trading.broker_sense.interception import get_recorder  # attach BEFORE nav so
            get_recorder().attach(pg, broker)  # the first data calls are recorded (read-only)
        except Exception:
            pass
        try:
            pg.goto(url or app.home_url, timeout=timeout_ms, wait_until="domcontentloaded")
        except Exception:                    # slow page past deadline → give what rendered
            pass
        pg.wait_for_timeout(2000)
        if _looks_like_login(pg):
            if not self._login(pg, app):
                pg.close()
                return None
            self.save_state(broker)
        try:                                   # owner's screen mirror: every page the brain
            from trading.broker_sense import screen_mirror
            screen_mirror.log_action(broker, pg, "open", url or app.home_url)
        except Exception:
            pass
        return pg

    def ensure_login_requested(self, broker: str) -> bool:
        """Proactively raise a Brain-Chat ask to connect `broker` when we have NO saved login yet
        — so the operator can hand over credentials up front, instead of only when the brain
        happens to hit a login wall (broker screener pages are public, so that wall rarely
        fires). Idempotent: skips if already connected. True if an ask was (re)raised."""
        from trading.brain.credentials import get_vault
        app = REGISTRY.get(broker)
        if app is None or not app.login_fields:
            return False
        creds = get_vault().get(app.site) or {}
        if creds.get("username") and creds.get("password"):
            return False                                  # already connected
        self._ask(app, ["username", "password"],
                  "log into your account and read ALL its data — screeners, order book, "
                  "positions, balance (READ-ONLY; the brain never places orders in the app)")
        self._log("login_needed", app.name,
                  f"Asked you in Brain Chat to connect {app.name} (one-time save)")
        return True

    def _ask(self, app: BrokerApp, fields: list[str], why: str) -> None:
        """Raise a DETAILED Brain-Chat credential request (owner decision #3)."""
        from trading.brain.credentials import get_vault
        expl = {k: v for k, v in app.login_fields}
        lines = [f"  • {f} — {expl.get(f, f)}" for f in fields]
        note = (f"🔐 I'm logging into {app.name} ({app.site}) to {why}. Please reply in this "
                f"chat with:\n" + "\n".join(lines) +
                ("\n(I'll save these encrypted so next time I only ever ask for the OTP.)"
                 if "password" in fields else
                 "\n(Your saved login details are already on file — I only need this OTP.)"))
        get_vault().request_login(app.site, fields, note)

    def _wait_otp(self, site: str) -> str | None:
        """Poll the vault until the owner submits an `otp` field in chat (bounded)."""
        from trading.brain.credentials import get_vault
        v = get_vault()
        deadline = time.time() + _OTP_WAIT_S
        while time.time() < deadline:
            creds = v.get(site) or {}
            if creds.get("otp"):
                return str(creds["otp"])
            time.sleep(_OTP_POLL_S)
        return None

    def _login(self, pg, app: BrokerApp) -> bool:
        """Vault-backed login: saved user/pass typed in; OTP asked (detailed) via chat and
        consumed one-time. True on success."""
        from trading.brain.credentials import get_vault
        v = get_vault()
        creds = v.get(app.site) or {}
        user, pw = creds.get("username"), creds.get("password")
        if not (user and pw):
            self._ask(app, ["username", "password"], "read its screener + charts (read-only)")
            self._log("login_needed", app.name,
                      f"Asked you in Brain Chat for {app.name} login details (one-time save)")
            return False
        u = pg.query_selector(_USER_SEL) or pg.query_selector("input[type=text]")
        if u:
            u.fill(str(user))
        p = pg.query_selector("input[type=password]")
        if p is None:                            # MULTI-STEP (Binance): submit email → step 2
            if not _click_login(pg) and u:
                u.press("Enter")
            pg.wait_for_timeout(4000)
            p = pg.query_selector("input[type=password]")
        if p:
            p.fill(str(pw))
            btn = pg.query_selector("button[type=submit], input[type=submit]")
            if btn and not _FORBIDDEN.search(btn.inner_text() or ""):
                btn.click()
            elif not _click_login(pg):
                p.press("Enter")
        pg.wait_for_timeout(3500)
        # OTP step? — must be a REAL code box, not the step-1 identity field: on Angel One the
        # mobile-number input is ALSO inputmode=numeric, so a rejected step 1 ("unable to
        # authenticate this device") used to false-flag as "OTP sent" with no SMS ever sent
        otp_box = None
        for el in pg.query_selector_all("input[autocomplete='one-time-code'], input[name*=otp i], "
                                        "input[id*=otp i], input[inputmode=numeric]"):
            if _otp_input(el):
                otp_box = el
                break
        if otp_box:
            self._ask(app, ["otp"], "finish the login it just challenged with an OTP")
            self._log("otp_needed", app.name,
                      f"{app.name} sent you an OTP — asked for it in Brain Chat "
                      f"(saved login already typed in)")
            otp = self._wait_otp(app.site)
            if not otp:
                return False
            otp_box.fill(otp)
            btn = pg.query_selector("button[type=submit], input[type=submit]")
            if btn and not _FORBIDDEN.search(btn.inner_text() or ""):
                btn.click()
            else:
                otp_box.press("Enter")
            pg.wait_for_timeout(3500)
            v.clear_field(app.site, "otp")           # one-time by construction
            # OTP-then-PIN flows (Angel One): the password/MPIN screen comes AFTER the OTP —
            # fill it now if it appeared (the pre-OTP password branch never saw it)
            p2 = pg.query_selector("input[type=password]")
            if p2 and pw:
                p2.fill(str(pw))
                btn2 = pg.query_selector("button[type=submit], input[type=submit]")
                if btn2 and not _FORBIDDEN.search(btn2.inner_text() or ""):
                    btn2.click()
                elif not _click_login(pg):
                    p2.press("Enter")
                pg.wait_for_timeout(3500)
        # HUMAN-CHALLENGE detection (Binance shows an image CAPTCHA after the email step): the
        # absence of a password field does NOT mean success — a captcha/verification page also
        # has none. Report honestly so we never claim a login that didn't happen.
        if _challenge_present(pg):
            self._log("login_challenge", app.name,
                      f"{app.name} requires a human step (image CAPTCHA / verification) that "
                      f"automated login can't pass — needs a one-time human login (see report)")
            return False
        ok = (pg.query_selector("input[type=password]") is None
              and not _looks_like_login(pg))       # not still parked on a login form
        self._log("login_ok" if ok else "login_failed", app.name,
                  f"{app.name} login {'succeeded — session saved' if ok else 'did not complete'}")
        return ok

    # ── honest status (dashboard) ───────────────────────────────────────────────
    def status(self) -> dict:
        from trading.brain.credentials import get_vault
        vs = get_vault().status()
        saved = {s["site"]: s["fields"] for s in vs["stored_sites"]}
        return {
            "sessions_on_disk": sorted(p.stem for p in state._path(_SESS_DIR).glob("*.json"))
            if state._path(_SESS_DIR).exists() else [],
            "open_contexts": sorted(self._contexts),
            "credentials_saved": {a.name: sorted(k for k in saved.get(a.site, []) if k != "otp")
                                  for a in REGISTRY.values() if a.site in saved},
            "pending_asks": vs["pending_requests"],
            "recent_events": self.events[-12:],
        }


_MGR: SessionManager | None = None


def get_sessions() -> SessionManager:
    global _MGR
    if _MGR is None:
        _MGR = SessionManager()
    return _MGR
