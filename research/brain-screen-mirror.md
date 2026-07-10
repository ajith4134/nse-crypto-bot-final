# Brain Screen Mirror — approach research (2026-07-09)

Goal: live view in the dashboard of the brain's OWN working browsers (Binance/Upstox funnels,
watchlist hand, app-school) with real-time action annotations (opens/clicks/reads + markers).
Read-only observability; the login panel (live_browser.py) stays the interactive one.

| Candidate | Where | Key features | Fit | Verdict |
|---|---|---|---|---|
| In-repo `trading/broker_sense/live_browser.py` pattern (JPEG frame polling) | this repo | proven: headless page → JPEG frames → dashboard `<img>` polling; no X/VNC/root; thread-safe worker | Perfect; already the UX the owner knows | **WINNER — reuse pattern** |
| CDP `Page.startScreencast` | Chromium devtools | push frames over CDP | needs a ws bridge per funnel process + dashboard ws fan-in; Playwright sync API owns the CDP session — risky to share | rejected (weight) |
| x11vnc + noVNC embed on the Xvfb display | OSS (x11vnc, noVNC) | true full-desktop mirror incl. all tabs | system installs (root), always-on encoder cost, mirrors the whole display not per-broker; interactive (not read-only) by default | rejected (heavy + not read-only) |
| websockify/mjpeg-streamer | OSS | generic mjpeg | still needs an in-process capturer anyway | rejected (adds nothing) |

Key architectural difference vs the login panel: the browsers to mirror live in OTHER
processes (crypto funnel, NSE funnel, live_loop watchlist writer). So capture happens
IN-PROCESS at the shared chokepoints — `trading/brain/vision/human_ui.py` (every eyes-read /
hand-click, with coordinates for markers) and `trading/broker_sense/sessions.py` (every page
open/navigation) — writing throttled JPEG frames + an action log to `trading/state/
screen_mirror/<broker>/` (atomic tmp+rename). The dashboard serves the files read-only and the
panel polls, same UX as the login stream. Honest LIVE/STALE from frame age; zero effect on
trading cycles beyond a budgeted ~100ms throttled screenshot.
