#!/usr/bin/env bash
# tools/handoff_vnc.sh — attach an INTERACTIVE VNC to the brain's EXISTING shared Xvfb
# display so the operator can solve a mid-session security challenge (Binance slide
# puzzle / image CAPTCHA) with their own mouse, then let automation auto-resume.
#
# Unlike tools/remote_login.sh this does NOT spawn Xvfb or a browser — the brain's headed
# browsers already render on the shared display (sessions._ensure_display, default :99).
# We only bring up x11vnc on that display + websockify/noVNC to serve it over the web,
# fronted by the gateway at /handoff-vnc/ (see gateway/Caddyfile). No secrets handled here.
#
# Usage: tools/handoff_vnc.sh up|down|status [:display] [webport]
set -u
HOME_DIR="/home/karan18190164"
VENV="$HOME_DIR/.venv/bin/python"
NOVNC="$HOME_DIR/vendor/noVNC"
RUN="$HOME_DIR/trading/state/handoff_vnc"; mkdir -p "$RUN"

DISP="${2:-:99}"; DISP="${DISP#:}"                 # accept ":99" or "99"
VNCP="${HANDOFF_VNC_PORT:-5910}"
WEBP="${3:-6090}"

up() {
  command -v x11vnc >/dev/null 2>&1 || { echo "MISSING x11vnc — run: sudo apt-get install -y x11vnc xauth"; exit 3; }
  DISPLAY=":$DISP" xdpyinfo >/dev/null 2>&1 || { echo "NO_DISPLAY :$DISP (brain browsers not headed yet)"; exit 4; }
  down >/dev/null 2>&1
  # VNC server on the SHARED display (localhost only; noVNC fronts it, gateway exposes it)
  x11vnc -display ":$DISP" -rfbport "$VNCP" -localhost -forever -shared -nopw -quiet \
    >"$RUN/x11vnc.log" 2>&1 &
  echo $! > "$RUN/x11vnc.pid"; sleep 1
  # noVNC web client + websocket proxy to the VNC server
  "$VENV" -m websockify --web "$NOVNC" "$WEBP" "localhost:$VNCP" \
    >"$RUN/novnc.log" 2>&1 &
  echo $! > "$RUN/novnc.pid"; sleep 1
  echo "UP display=:$DISP web=$WEBP  → /handoff-vnc/vnc.html?path=websockify&autoconnect=1&resize=scale"
}

down() {
  for p in novnc x11vnc; do
    [ -f "$RUN/$p.pid" ] && kill "$(cat "$RUN/$p.pid")" 2>/dev/null; rm -f "$RUN/$p.pid"
  done
  echo "DOWN"
}

status() {
  up=0
  for p in x11vnc novnc; do
    if [ -f "$RUN/$p.pid" ] && kill -0 "$(cat "$RUN/$p.pid")" 2>/dev/null; then
      echo "  $p: UP ($(cat "$RUN/$p.pid"))"; up=$((up+1))
    else echo "  $p: down"; fi
  done
  echo "  web_port: $WEBP  display: :$DISP  running_parts: $up/2"
}

case "${1:-}" in
  up)     up ;;
  down)   down ;;
  status) status ;;
  *) echo "usage: $0 up|down|status [:display] [webport]"; exit 1 ;;
esac
