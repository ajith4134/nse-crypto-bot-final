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

WEDGE detection (2026-07-17): pgrep alone cannot see the failure the owner actually hits — a
dashboard that is ALIVE but unresponsive (GIL/CPU starvation, see brain-audit + 524-wedge). It
stays in pgrep, so this keeper called it healthy and left it hanging until a manual reboot. So
processes in HEALTH also get an HTTP probe. Two things make the probe safe to act on:
  - ANY HTTP status counts as alive (the dashboard answers /api/health with 401 — a reply is a
    reply; we are testing whether the event loop still turns, not whether we are authorized).
  - A kill needs WEDGE_STRIKES consecutive failures (~15 min at the */5 cron). This box runs at
    load ~15 on 12 cores, so a single slow probe is normal and must NEVER cost a restart.
Only after that does it SIGKILL the wedged pid — start_all is pgrep-guarded, so a wedged process
must actually die before it can be replaced.

Kill-switch (owner): `touch ~/.loop_keeper_off` disables restarts (state still records).
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

HOME = os.path.expanduser("~")
START_ALL = os.path.join(HOME, "start_all.sh")
OFF_FLAG = os.path.join(HOME, ".loop_keeper_off")
HISTORY_CAP = 50

# name → local URL proving the process still SERVES, not merely exists. Loopback only: this asks
# "does the event loop still turn", so the public gateway/tunnel must not be in the path.
HEALTH = {
    "dashboard": "http://127.0.0.1:8000/api/health",
    "freqtrade": "http://127.0.0.1:8080/api/v1/ping",
}
PROBE_TIMEOUT = 25      # generous: a loaded box answers slowly, and slow is not wedged
WEDGE_STRIKES = 3       # consecutive failures (~15 min) before we kill. Never act on one spike.

# name → pgrep -f pattern. These are the processes whose silent death froze the brain.
REQUIRED = {
    "freqtrade": r"freqtrade trade",
    "funnel_crypto": r"broker_sense\.run_funnel_loop crypto",
    "funnel_nse": r"broker_sense\.run_funnel_loop nse",
    "live_loop": r"trading\.online\.run_live_loop",
    "micro_distill": r"freqtrade\.run_micro_distill",
    "candle_updater": r"freqtrade\.candle_updater",
    # Continuous strategy-research daemon (breeds strategies into the SkillLibrary). Was never
    # self-healed before 2026-07-13, so it died in the Jul-7 VM stop and left skill_library stale.
    "autoresearch": r"trading\.strategy\.run_autoresearch",
    # Per-coin best-strategy table producer (2026-07-13): feeds the Strategy column + the breadth
    # lane's tournament synergy. If it dies the column goes stale, so it self-heals like the rest.
    "strategy_table": r"trading\.crypto\.freqtrade\.run_strategy_table",
    "dashboard": r"dashboard/server\.py",
}


def _alive(pattern: str) -> bool:
    try:
        return subprocess.run(["pgrep", "-f", pattern],
                              capture_output=True, timeout=10).returncode == 0
    except Exception:
        return False           # pgrep itself failing → treat as dead, let start_all guard


def _responsive(url: str) -> bool:
    """True if the server produced ANY HTTP reply. An HTTPError (401/404/5xx) is still a reply —
    it proves the process is serving, which is the only thing this probe is asking. Only a
    timeout / refused connection / socket error means the event loop has stopped turning."""
    try:
        urllib.request.urlopen(url, timeout=PROBE_TIMEOUT).read(1)
        return True
    except urllib.error.HTTPError:
        return True
    except Exception:
        return False


def _kill_wedged(name: str, pattern: str) -> bool:
    """SIGKILL a wedged process so the pgrep-guarded start_all will replace it.

    SIGKILL, not SIGTERM: the process is wedged precisely because it is not processing anything,
    so a handler-based signal it can't run is unlikely to land. Nothing here holds unflushed
    state that a graceful stop would save — the ledger/journal are written by other processes.
    """
    try:
        out = subprocess.run(["pgrep", "-f", pattern], capture_output=True,
                             text=True, timeout=10)
        pids = [int(p) for p in out.stdout.split()]
    except Exception:
        return False
    killed = False
    for pid in pids:
        if pid == os.getpid():
            continue
        try:
            os.kill(pid, signal.SIGKILL)
            killed = True
            print(f"[loop-keeper] WEDGED {name} (pid {pid}) unresponsive "
                  f"{WEDGE_STRIKES}x → SIGKILL, start_all will replace it", flush=True)
        except Exception as e:
            print(f"[loop-keeper] kill {name} pid {pid} failed: {type(e).__name__}: {e}",
                  flush=True)
    return killed


def _env_flag(name: str, default: str = "0") -> str:
    """Read a flag from the process env, falling back to ~/.env. loop_keeper MUST agree with
    start_all's own start/skip decisions (start_all reads .env too) — otherwise it declares a
    deliberately-disabled process 'missing' and re-runs start_all forever chasing a ghost."""
    if name in os.environ:
        return os.environ[name].strip()
    try:
        with open(os.path.join(HOME, ".env")) as f:
            for line in f:
                s = line.strip()
                if s.startswith(name + "="):
                    return s.split("=", 1)[1].strip()
    except Exception:
        pass
    return default


def _check() -> dict:
    required = dict(REQUIRED)
    # Respect the SAME intentional-off switches start_all honors — never chase a process the
    # boot script deliberately won't start (that was the pre-2026-07-13 candle_updater bug: it
    # is disabled by default, yet loop_keeper re-ran start_all every 5 min forever for it).
    if _env_flag("NSE_FUNNEL_OFF", "0") == "1":
        required.pop("funnel_nse", None)               # owner kill-switch — intentionally stopped
    if _env_flag("CANDLE_UPDATER", "0") != "1":        # disabled 2026-07-12 (API-load removal)
        required.pop("candle_updater", None)
    if _env_flag("AUTORESEARCH", "1") == "0":          # owner kill-switch for the research daemon
        required.pop("autoresearch", None)
    if _env_flag("STRATEGY_TABLE", "1") == "0":        # owner kill-switch for the strategy-table producer
        required.pop("strategy_table", None)
    return {name: _alive(pat) for name, pat in required.items()}


def _load_state() -> dict:
    """Previous run's state. Strikes MUST persist across cron runs — each run is a fresh process,
    so an in-memory counter would reset every 5 min and never reach WEDGE_STRIKES.

    Mirrors _save_state's resolution order (trading.state first, raw path only as the cron-safe
    fallback). Reading the raw path directly would ignore a monkeypatched STATE_DIR and let a
    test read the LIVE keeper state — the exact cross-contamination CONVENTIONS forbids.
    """
    try:
        sys.path.insert(0, HOME)
        from trading import state as tstate
        return tstate.load_json("loop_keeper.json", {}) or {}
    except Exception:
        pass
    try:
        with open(os.path.join(HOME, "trading", "state", "loop_keeper.json"),
                  encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _save_state(state: dict) -> None:
    """Atomic write via trading.state when importable, plain file otherwise (cron-safe)."""
    try:
        sys.path.insert(0, HOME)
        from trading import state as tstate
        prev = tstate.load_json("loop_keeper.json", {}) or {}
        hist = (prev.get("history") or [])[-HISTORY_CAP:]
        if state["missing"] or state["restarted"] or state.get("wedged"):
            hist = hist[-(HISTORY_CAP - 1):] + [{"ts": state["ts"],
                                                 "missing": state["missing"],
                                                 "wedged": state.get("wedged") or [],
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

    # --- WEDGE pass: only for processes pgrep says are alive. A dead one is already in `missing`
    # and start_all will handle it; probing it would just log a redundant failure.
    strikes = dict((_load_state().get("strikes") or {}))
    health = {}
    for name, url in HEALTH.items():
        if name not in alive or not alive[name]:
            strikes.pop(name, None)          # dead, not wedged — let the normal path restart it
            continue
        ok = _responsive(url)
        health[name] = ok
        strikes[name] = 0 if ok else strikes.get(name, 0) + 1
        if not ok:
            print(f"[loop-keeper] {time.strftime('%F %T')} {name} alive but UNRESPONSIVE "
                  f"({strikes[name]}/{WEDGE_STRIKES})", flush=True)

    wedged = sorted(n for n, s in strikes.items() if s >= WEDGE_STRIKES)
    state = {"ts": now, "alive": alive, "missing": missing, "health": health,
             "strikes": strikes, "wedged": wedged,
             "restarted": False, "disabled": disabled}
    if wedged and not disabled:
        for name in wedged:
            if _kill_wedged(name, REQUIRED[name]):
                strikes[name] = 0            # killed → next run re-probes the fresh process
                if name not in missing:
                    missing.append(name)     # now genuinely gone → start_all replaces it below
        missing.sort()
        state["missing"] = missing
    elif wedged:
        print(f"[loop-keeper] wedged: {wedged} but ~/.loop_keeper_off set — NOT restarting",
              flush=True)

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
