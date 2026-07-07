#!/usr/bin/env bash
# tools/remote_login.sh — bring up (or tear down) a remote-view browser so the operator can
# complete a broker login (image CAPTCHA + OTP) that automated login can't pass. Stack:
#   Xvfb :N  →  headful chromium (broker profile)  →  x11vnc on :N  →  websockify+noVNC (web)
# The operator opens the printed noVNC URL, solves the login; `stop` saves the session and
# tears everything down. No secrets handled here.
#
# Usage: tools/remote_login.sh start <broker> [url]   |   tools/remote_login.sh stop <broker>
#        tools/remote_login.sh status <broker>
set -u
HOME_DIR="/home/karan18190164"
VENV="$HOME_DIR/.venv/bin/python"
NOVNC="$HOME_DIR/vendor/noVNC"
RUN="$HOME_DIR/trading/state/remote_login"
mkdir -p "$RUN"

broker="${2:-binance}"
# stable per-broker ports (binance=99/5900/6080; add more here as needed)
case "$broker" in
  binance)  DISP=99; VNCP=5900; WEBP=6080 ;;
  angelone) DISP=98; VNCP=5901; WEBP=6081 ;;
  *)        DISP=97; VNCP=5902; WEBP=6082 ;;
esac
PIDF="$RUN/$broker"

start() {
  command -v x11vnc >/dev/null || { echo "MISSING x11vnc — run: sudo apt-get install -y x11vnc xauth"; exit 3; }
  command -v Xvfb   >/dev/null || { echo "MISSING Xvfb — run: sudo apt-get install -y xvfb"; exit 3; }
  stop >/dev/null 2>&1
  # 1) virtual display
  Xvfb ":$DISP" -screen 0 1360x900x24 >"$RUN/$broker.xvfb.log" 2>&1 &
  echo $! > "$PIDF.xvfb"; sleep 2
  # 2) headful chromium in the broker profile (saves session on SIGTERM)
  DISPLAY=":$DISP" "$VENV" "$HOME_DIR/tools/remote_login_browser.py" "$broker" "${3:-}" \
    >"$RUN/$broker.chromium.log" 2>&1 &
  echo $! > "$PIDF.chromium"; sleep 3
  # 3) VNC server on the display (localhost only; noVNC fronts it)
  x11vnc -display ":$DISP" -rfbport "$VNCP" -localhost -forever -shared -nopw -quiet \
    >"$RUN/$broker.x11vnc.log" 2>&1 &
  echo $! > "$PIDF.x11vnc"; sleep 1
  # 4) noVNC over websockify (serves the web client + proxies the websocket to VNC)
  "$VENV" -m websockify --web "$NOVNC" "$WEBP" "localhost:$VNCP" \
    >"$RUN/$broker.novnc.log" 2>&1 &
  echo $! > "$PIDF.novnc"; sleep 1
  echo "STARTED $broker  → open:  /novnc/vnc.html?path=novnc/&autoconnect=1&resize=scale"
  echo "  (local web port $WEBP; exposed via the gateway at /novnc/)"
}

stop() {
  # SIGTERM the chromium FIRST so it exports the authenticated session before dying
  [ -f "$PIDF.chromium" ] && kill -TERM "$(cat "$PIDF.chromium")" 2>/dev/null && sleep 3
  for part in novnc x11vnc chromium xvfb; do
    [ -f "$PIDF.$part" ] && kill "$(cat "$PIDF.$part")" 2>/dev/null; rm -f "$PIDF.$part"
  done
  echo "STOPPED $broker (session saved if login was completed)"
}

status() {
  up=0
  for part in xvfb chromium x11vnc novnc; do
    if [ -f "$PIDF.$part" ] && kill -0 "$(cat "$PIDF.$part")" 2>/dev/null; then
      echo "  $part: UP ($(cat "$PIDF.$part"))"; up=$((up+1))
    else echo "  $part: down"; fi
  done
  sess="$HOME_DIR/trading/state/browser_sessions/$broker.json"
  echo "  session_file: $([ -f "$sess" ] && echo present || echo none)"
  echo "  web_port: $WEBP  running_parts: $up/4"
}

case "${1:-}" in
  start)  start "$@" ;;
  stop)   stop ;;
  status) status ;;
  *) echo "usage: $0 start|stop|status <broker> [url]"; exit 1 ;;
esac
