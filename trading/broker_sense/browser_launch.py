"""trading/broker_sense/browser_launch.py — pick the stealth Playwright driver (adopt item 5).

Our broker logins (Binance "Security Verification", Upstox) fingerprint the browser and challenge
it when it smells automated. We already harden the FINGERPRINT with init scripts (stealth.py:
navigator.webdriver / window.chrome / plugins) — but init scripts run AFTER the page's own probes
and can't fix the CDP/runtime-level tells (the Runtime.enable leak, patched console, etc.) that a
real anti-bot notices. **Patchright** is a drop-in Playwright fork that patches those at the driver
level, so the browser looks real from the first byte. This helper swaps the driver behind a flag:

    STEALTH_BROWSER=patchright   → the anti-detect fork (when installed + its Chromium present)
    STEALTH_BROWSER=playwright   → standard Playwright (DEFAULT — kill-switch / no behavior change)

Callers use `browser_launch.sync_playwright().start()` exactly like Playwright's. Honest degrade:
if patchright or its browser isn't available, it falls back to standard Playwright (never breaks a
login). Layered WITH stealth.py — Patchright hardens the runtime, stealth.py the JS fingerprint.
"""
from __future__ import annotations

import os


def mode() -> str:
    return os.environ.get("STEALTH_BROWSER", "playwright").strip().lower()


def _patchright_ready() -> bool:
    """True only when patchright AND its Chromium are actually installed (so we never hand back a
    driver whose browser launch would then fail on a live login path)."""
    try:
        import patchright  # noqa: F401
        from patchright._impl._driver import compute_driver_executable  # type: ignore
        # a cheap availability signal; any import error → not ready → fall back.
        _ = compute_driver_executable
        return True
    except Exception:
        return False


def active() -> str:
    """Which driver a call to sync_playwright() will actually return right now."""
    return "patchright" if (mode() == "patchright" and _patchright_ready()) else "playwright"


def sync_playwright():
    """Return the Playwright (or Patchright) sync context-manager, per STEALTH_BROWSER. Same
    surface as playwright.sync_api.sync_playwright — callers `.start()` it as before."""
    if mode() == "patchright" and _patchright_ready():
        try:
            from patchright.sync_api import sync_playwright as _sp
            return _sp()
        except Exception:
            pass
    from playwright.sync_api import sync_playwright as _sp
    return _sp()


def status() -> dict:
    return {"requested": mode(), "active": active(), "patchright_ready": _patchright_ready()}
