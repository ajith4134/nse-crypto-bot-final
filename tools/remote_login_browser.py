#!/usr/bin/env python
"""tools/remote_login_browser.py — a HEADFUL chromium the operator drives over VNC to complete
a broker login (solve the image CAPTCHA + OTP that automated login can't pass), after which the
authenticated session is saved so the brain reads the account HEADLESS forever after.

Runs inside an Xvfb display (started by tools/remote_login.sh); x11vnc + noVNC expose that
display to the operator's browser. The browser lives in the broker's PERSISTENT profile, and we
also export Playwright storage_state to the SAME file the funnel's SessionManager loads
(trading/state/browser_sessions/<broker>.json) — periodically and on SIGTERM — so a completed
login flows straight into the funnel with no re-login.

Usage: DISPLAY=:99 python tools/remote_login_browser.py <broker> <url>
Stop:  send SIGTERM (tools/remote_login.sh stop) → it exports the session and exits cleanly.
Read-only: this only logs in; the brain never places orders in the app (APIs execute)."""
from __future__ import annotations

import os
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trading import state                      # noqa: E402
from trading.broker_sense.brokers import REGISTRY  # noqa: E402

_STOP = False


def _on_term(_sig, _frame):
    global _STOP
    _STOP = True


def main() -> int:
    broker = sys.argv[1] if len(sys.argv) > 1 else "binance"
    app = REGISTRY.get(broker)
    url = sys.argv[2] if len(sys.argv) > 2 else (
        "https://accounts.binance.com/en/login" if broker == "binance"
        else (app.home_url if app else ""))
    prof_dir = state._path("browser_profiles") / broker
    prof_dir.mkdir(parents=True, exist_ok=True)
    sess_file = state._path("browser_sessions") / f"{broker}.json"
    sess_file.parent.mkdir(parents=True, exist_ok=True)

    signal.signal(signal.SIGTERM, _on_term)
    signal.signal(signal.SIGINT, _on_term)

    from playwright.sync_api import sync_playwright
    p = sync_playwright().start()
    ctx = p.chromium.launch_persistent_context(
        str(prof_dir), headless=False, viewport={"width": 1280, "height": 860},
        args=["--no-sandbox", "--disable-dev-shm-usage", "--start-maximized"])
    pg = ctx.pages[0] if ctx.pages else ctx.new_page()
    try:
        pg.goto(url, wait_until="domcontentloaded", timeout=45000)
    except Exception:
        pass

    def _save():
        try:
            ctx.storage_state(path=str(sess_file))
            try:
                import stat
                os.chmod(sess_file, stat.S_IRUSR | stat.S_IWUSR)   # 0600 — cookies are secrets
            except OSError:
                pass
        except Exception:
            pass

    (state._path("browser_profiles") / broker / ".ready").write_text(str(time.time()))
    last = 0.0
    while not _STOP:                            # keep the browser alive for the operator to drive
        time.sleep(1.0)
        if time.time() - last > 8:             # periodic save so a hard kill still keeps cookies
            _save()
            last = time.time()
    _save()                                    # final save on SIGTERM (login just completed)
    try:
        ctx.close()
    except Exception:
        pass
    p.stop()
    print(f"[remote-login] {broker}: session saved to {sess_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
