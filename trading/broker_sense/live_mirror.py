"""trading/broker_sense/live_mirror.py — M: LIVE video screen mirror (Pillar 27 batch).

The owner asked for the Brain Screen Mirror to be a real moving picture, not a
per-action snapshot. The brain's headed browsers all render into one Xvfb display
(sessions._ensure_display, default :99) — so a single ffmpeg x11grab of that display
IS a live video of everything the brain is doing, including between actions.

This module turns that into an MJPEG frame generator the dashboard streams as
multipart/x-mixed-replace (plain <img> tag — no player, no WebRTC infra, zero deps
beyond the ffmpeg already installed):

  frames(...)  → generator yielding JPEG bytes; SPAWNS ffmpeg on first pull and
                 KILLS it when the consumer stops (viewer-demand: no viewers → zero
                 capture cost). Frames are split on JPEG SOI/EOI markers.
  available()  → honest capability check (ffmpeg present + X socket up) for the
                 panel to decide LIVE vs the existing frame-poll fallback.

Guardrails: at most MIRROR_MAX_VIEWERS (default 2) concurrent streams; fps/size
bounded; ffmpeg runs at nice 10 so it never competes with trading loops.
Levers: LIVE_MIRROR=0 disables; BROKER_SENSE_DISPLAY (:99), LIVE_MIRROR_FPS (3),
LIVE_MIRROR_SIZE (1600x1000 — must match the Xvfb geometry).
"""
from __future__ import annotations

import os
import subprocess
import threading

_SOI = b"\xff\xd8"                     # JPEG start-of-image
_EOI = b"\xff\xd9"                     # JPEG end-of-image
_viewers = 0
_lock = threading.Lock()


def _env(name: str, default: str) -> str:
    return os.environ.get(name, "") or default


def enabled() -> bool:
    return os.environ.get("LIVE_MIRROR", "1") in ("1", "true", "TRUE", "yes", "on")


def display() -> str:
    return _env("BROKER_SENSE_DISPLAY", ":99")


def available() -> dict:
    """Honest capability report: can a live stream actually be produced right now?"""
    import shutil
    disp = display()
    sock = f"/tmp/.X11-unix/X{disp.lstrip(':')}"
    ffmpeg = bool(shutil.which("ffmpeg"))
    x_up = os.path.exists(sock)
    return {"enabled": enabled(), "ffmpeg": ffmpeg, "display": disp,
            "display_up": x_up, "viewers": _viewers,
            "available": enabled() and ffmpeg and x_up,
            "reason": None if (enabled() and ffmpeg and x_up) else
            ("disabled" if not enabled() else
             "ffmpeg missing" if not ffmpeg else
             f"no X server on {disp} (brain browsers not headed yet)")}


def frames(fps: int | None = None):
    """Yield JPEG frames grabbed live from the brain's Xvfb display. Raises
    RuntimeError with an honest reason when streaming can't start; always releases
    the viewer slot + ffmpeg on generator close."""
    global _viewers
    cap = available()
    if not cap["available"]:
        raise RuntimeError(cap["reason"] or "unavailable")
    max_v = int(float(_env("MIRROR_MAX_VIEWERS", "2")))
    with _lock:
        if _viewers >= max_v:
            raise RuntimeError(f"viewer limit ({max_v}) reached")
        _viewers += 1
    fps = int(fps or float(_env("LIVE_MIRROR_FPS", "3")))
    fps = max(1, min(8, fps))
    size = _env("LIVE_MIRROR_SIZE", "1600x1000")
    cmd = ["nice", "-n", "10", "ffmpeg", "-loglevel", "quiet",
           "-f", "x11grab", "-video_size", size, "-framerate", str(fps),
           "-i", display(), "-f", "mjpeg", "-q:v", "8", "-r", str(fps), "pipe:1"]
    proc = None
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, bufsize=0)
        buf = b""
        while True:
            chunk = proc.stdout.read(65536)
            if not chunk:
                rc = proc.poll()
                raise RuntimeError(f"ffmpeg ended (rc={rc})")
            buf += chunk
            while True:
                start = buf.find(_SOI)
                if start < 0:
                    buf = b""
                    break
                end = buf.find(_EOI, start + 2)
                if end < 0:
                    if start > 0:
                        buf = buf[start:]
                    break
                yield buf[start:end + 2]
                buf = buf[end + 2:]
            if len(buf) > 8 * 1024 * 1024:         # torn stream safety valve
                buf = b""
    finally:
        with _lock:
            _viewers = max(0, _viewers - 1)
        if proc is not None:
            try:
                proc.kill()
                proc.wait(timeout=3)
            except Exception:
                pass
