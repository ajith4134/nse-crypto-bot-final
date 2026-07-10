"""tools/loop_keeper.py — RUNTIME self-heal for the trading stack (2026-07-10).

The 2026-07-10 audit found all three loop processes dead for 2+ hours with every brain
panel silently frozen: the stack has BOOT self-heal (systemd → start_all.sh) but nothing
watched it during the day. This keeper closes that gap.

Run from cron every 5 minutes (installed by `python tools/loop_keeper.py --install-cron`):
    */5 * * * * flock -n /tmp/loop_keeper.lock .venv/bin/python tools/loop_keeper.py

Behavior — deliberately boring:
  - pgrep each REQUIRED process; all alive → write state, exit 0 (no log noise).
  - anything dead → ONE `bash start_all.sh` run (the sanctioned boot path; every part of
    it is pgrep-guarded, so it only starts what is missing), then re-check and record.
  - state → trading/state/loop_keeper.json (read by connectivity_check / dashboard);
    actions append to logs/loop_keeper.log via cron's redirect.

Kill-switch (owner): `touch ~/.loop_keeper_off` disables restarts (state still records).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

HOME = os.path.expanduser("~")
START_ALL = os.path.join(HOME, "start_all.sh")
OFF_FLAG = os.path.join(HOME, ".loop_keeper_off")
HISTORY_CAP = 50

# name → pgrep -f pattern. These are the processes whose silent death froze the brain.
REQUIRED = {
    "freqtrade": r"freqtrade trade",
    "funnel_crypto": r"broker_sense\.run_funnel_loop crypto",
    "funnel_nse": r"broker_sense\.run_funnel_loop nse",
    "live_loop": r"trading\.online\.run_live_loop",
    "micro_distill": r"freqtrade\.run_micro_distill",
    "candle_updater": r"freqtrade\.candle_updater",
    "dashboard": r"dashboard/server\.py",
}


def _alive(pattern: str) -> bool:
    try:
        return subprocess.run(["pgrep", "-f", pattern],
                              capture_output=True, timeout=10).returncode == 0
    except Exception:
        return False           # pgrep itself failing → treat as dead, let start_all guard


def _check() -> dict:
    return {name: _alive(pat) for name, pat in REQUIRED.items()}


def _save_state(state: dict) -> None:
    """Atomic write via trading.state when importable, plain file otherwise (cron-safe)."""
    try:
        sys.path.insert(0, HOME)
        from trading import state as tstate
        prev = tstate.load_json("loop_keeper.json", {}) or {}
        hist = (prev.get("history") or [])[-HISTORY_CAP:]
        if state["missing"] or state["restarted"]:
            hist = hist[-(HISTORY_CAP - 1):] + [{"ts": state["ts"],
                                                 "missing": state["missing"],
                                                 "restarted": state["restarted"]}]
        state["history"] = hist
        tstate.save_json("loop_keeper.json", state)
    except Exception:
        try:
            path = os.path.join(HOME, "trading", "state", "loop_keeper.json")
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(state, f)
            os.replace(tmp, path)
        except Exception:
            pass


def run_once() -> int:
    now = time.time()
    alive = _check()
    missing = sorted(n for n, ok in alive.items() if not ok)
    disabled = os.path.exists(OFF_FLAG)
    state = {"ts": now, "alive": alive, "missing": missing,
             "restarted": False, "disabled": disabled}
    if missing and not disabled:
        print(f"[loop-keeper] {time.strftime('%F %T')} dead: {missing} → start_all.sh",
              flush=True)
        try:
            subprocess.run(["bash", START_ALL], cwd=HOME, timeout=300,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            state["restarted"] = True
        except Exception as e:
            print(f"[loop-keeper] start_all failed: {type(e).__name__}: {e}", flush=True)
        time.sleep(20)          # freqtrade takes >5s to fork its workers (false
                                # "still missing" at the 5s recheck, 2026-07-10)
        state["alive_after"] = _check()
        still = sorted(n for n, ok in state["alive_after"].items() if not ok)
        state["still_missing"] = still
        print(f"[loop-keeper] after restart still missing: {still or 'none'}", flush=True)
    elif missing:
        print(f"[loop-keeper] dead: {missing} but ~/.loop_keeper_off set — NOT restarting",
              flush=True)
    _save_state(state)
    return 1 if state.get("still_missing") else 0


def install_cron() -> None:
    """Idempotently add the */5 cron line (flock prevents overlapping runs)."""
    py = os.path.join(HOME, ".venv", "bin", "python")
    line = (f"*/5 * * * * /usr/bin/flock -n /tmp/loop_keeper.lock {py} "
            f"{os.path.join(HOME, 'tools', 'loop_keeper.py')} "
            f">> {os.path.join(HOME, 'logs', 'loop_keeper.log')} 2>&1")
    cur = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    existing = cur.stdout if cur.returncode == 0 else ""
    if "loop_keeper.py" in existing:
        print("[loop-keeper] cron line already installed")
        return
    new = existing.rstrip("\n") + ("\n" if existing.strip() else "") + line + "\n"
    subprocess.run(["crontab", "-"], input=new, text=True, check=True)
    print("[loop-keeper] cron installed: " + line)


if __name__ == "__main__":
    if "--install-cron" in sys.argv:
        install_cron()
    else:
        sys.exit(run_once())
