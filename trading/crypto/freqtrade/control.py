"""trading/crypto/freqtrade/control.py — guarded paper↔live & spot↔futures switch (Phase F).

FreqUI controls everything Freqtrade does natively (start/stop, force-enter/exit, balance,
positions, the ~250 liquid+volatile pairs). The ONE thing it can't do is flip `dry_run`
(paper↔live) or `trading_mode` (spot↔futures) — those are set at config time. This module does
that safely, server-side:

  • persists the choice to .env (CRYPTO_MODE / CRYPTO_TRADING_MODE) so it survives restarts and is
    INDEPENDENT of NSE's TRADING_MODE,
  • rewrites the Freqtrade config.json (dry_run / trading_mode / pairs / paper balance),
  • on a segment change, regenerates the library strategy files so can_short matches the segment,
  • restarts the bot.

Real-money guard: switching to LIVE requires confirm=True AND real exchange API keys present —
the same 2-step deliberate pattern as controls.set_mode(confirm=) / OpenAlgoClient._guard_live.
Secrets-safe: never prints the .env password; only the keys it changes.
"""
from __future__ import annotations

import dataclasses
import json
import os
import re
import socket
import subprocess
import time

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")


def _cfg():
    # Base config from .env. NOTE: the root `config.settings` reads os.environ and is cached
    # at process start — load_dotenv() will NOT re-read a changed .env in a long-lived process
    # (the dashboard server). So the operator-adjustable fields below would otherwise be STALE,
    # and set_params/switch would silently revert a previously-applied value to its startup
    # default. Overlay those fields from the LIVE config.json (the persisted truth on disk).
    from trading.crypto import config as _c
    import importlib
    importlib.reload(_c)
    cfg = _c._load()
    c = _config_json()
    if c:
        patch = {}
        if "dry_run_wallet" in c:
            patch["paper_balance"] = float(c["dry_run_wallet"])
        if "max_open_trades" in c:
            patch["max_open_trades"] = int(c["max_open_trades"])
        sa = c.get("stake_amount")
        if sa is not None:
            patch["stake_amount"] = 0.0 if sa == "unlimited" else float(sa)
        if "ml_leverage" in c:
            patch["leverage"] = float(c["ml_leverage"])
        if c.get("trading_mode"):
            patch["trading_mode"] = c["trading_mode"]
        if "dry_run" in c:
            patch["mode"] = "paper" if c.get("dry_run") else "live"
        if patch:
            cfg = dataclasses.replace(cfg, **patch)
    return cfg


def _config_json() -> dict:
    from trading.crypto.freqtrade.config_template import CONFIG_PATH
    try:
        with open(CONFIG_PATH) as fh:
            return json.load(fh)
    except Exception:
        return {}


def _bot_running() -> bool:
    try:
        r = subprocess.run(["pgrep", "-f", "bin/freqtrade trade"],
                           capture_output=True, text=True)
        return r.returncode == 0 and bool(r.stdout.strip())
    except Exception:
        return False


def status() -> dict:
    """Current crypto-engine mode (read from the live config.json + process state)."""
    c = _config_json()
    dry = c.get("dry_run", True)
    sa = c.get("stake_amount")
    return {
        "mode": "paper" if dry else "live",
        "dry_run": bool(dry),
        "segment": c.get("trading_mode", "spot"),
        "running": _bot_running(),
        "pairs_configured": len(c.get("exchange", {}).get("pair_whitelist", []) or []),
        "paper_balance": c.get("dry_run_wallet"),
        "max_open_trades": c.get("max_open_trades"),
        "stake_amount": (0.0 if sa == "unlimited" else sa),
        "leverage": c.get("ml_leverage", 1.0),
    }


def _set_env_keys(updates: dict) -> None:
    """Update/insert keys in .env (gitignored). Values are NOT printed. Creates .env if missing."""
    lines = []
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH) as fh:
            lines = fh.read().splitlines()
    have = set()
    out = []
    for ln in lines:
        m = re.match(r"^([A-Z0-9_]+)=", ln)
        if m and m.group(1) in updates:
            out.append(f"{m.group(1)}={updates[m.group(1)]}")
            have.add(m.group(1))
        else:
            out.append(ln)
    for k, v in updates.items():
        if k not in have:
            out.append(f"{k}={v}")
    with open(ENV_PATH, "w") as fh:
        fh.write("\n".join(out) + "\n")


def _wait_port_free(host: str, port: int, timeout: float = 20.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port)); s.close(); return True
        except OSError:
            s.close(); time.sleep(0.5)
    return False


def restart_bot() -> dict:
    """Stop any running Freqtrade trader and relaunch it detached via start.sh."""
    from trading.crypto.freqtrade.config_template import HERE
    start_sh = os.path.join(HERE, "start.sh")
    log = os.path.join(HERE, "user_data", "ft.log")
    subprocess.run(["pkill", "-9", "-f", "bin/freqtrade trade"], capture_output=True)
    _wait_port_free("127.0.0.1", 8080, timeout=20.0)
    with open(log, "a") as lf:
        subprocess.Popen(["bash", start_sh], cwd=PROJECT_ROOT, start_new_session=True,
                         stdout=lf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
    return {"restarted": True, "log": log}


def switch(*, mode: str | None = None, segment: str | None = None,
           paper_balance: float | None = None, confirm: bool = False) -> dict:
    """Switch crypto paper↔live and/or spot↔futures, then restart the bot.

    mode    ∈ {"paper","live"}  (live needs confirm=True AND real API keys — real money)
    segment ∈ {"spot","futures"} (futures enables shorting; regenerates strategy can_short)
    """
    cur = _cfg()
    new_mode = (mode or cur.mode).lower()
    new_seg = (segment or cur.trading_mode).lower()
    if new_mode not in ("paper", "live"):
        raise ValueError(f"mode must be paper|live, got {mode!r}")
    if new_seg not in ("spot", "futures"):
        raise ValueError(f"segment must be spot|futures, got {segment!r}")

    # ── real-money guard (2-step, deliberate) ──────────────────────────────────
    if new_mode == "live":
        if not confirm:
            raise PermissionError("LIVE crypto requires confirm=True (real money). Refusing.")
        if not cur.has_keys(cur.default_exchange):
            raise PermissionError(
                f"LIVE crypto refused: no API keys for {cur.default_exchange}. Set "
                f"{cur.default_exchange.upper()}_API_KEY/_API_SECRET in .env first.")

    # no-op guard: nothing actually changes → don't churn the bot with a needless restart
    if new_mode == cur.mode and new_seg == cur.trading_mode and paper_balance is None:
        return {"ok": True, "mode": new_mode, "segment": new_seg, "unchanged": True,
                "status": status()}

    # persist independent of NSE (CRYPTO_MODE, not TRADING_MODE)
    _set_env_keys({"CRYPTO_MODE": new_mode, "CRYPTO_TRADING_MODE": new_seg})

    # rewrite config.json for the new mode/segment (+ optional paper balance)
    from trading.crypto.freqtrade.config_template import write_config
    new_cfg = dataclasses.replace(cur, mode=new_mode, trading_mode=new_seg)
    write_config(cfg=new_cfg, dry_run_wallet=paper_balance)

    # regenerate library strategies so can_short matches the segment (spot=long-only)
    from trading.strategy.freqtrade_adapter import generate_strategy_files
    gen = generate_strategy_files(
        os.path.join(os.path.dirname(__file__), "user_data", "strategies"),
        spot_mode=(new_seg == "spot"))

    restart_bot()
    return {"ok": True, "mode": new_mode, "segment": new_seg,
            "strategies_regenerated": gen["n_written"], "requested_paper_balance": paper_balance}


def set_params(*, paper_balance: float | None = None, max_open_trades: int | None = None,
               stake_amount: float | None = None, leverage: float | None = None) -> dict:
    """Apply operator-adjustable Freqtrade params (persist to .env, rewrite config, restart bot)."""
    env, fields = {}, {}
    if paper_balance is not None:
        env["CRYPTO_PAPER_BALANCE"] = float(paper_balance); fields["paper_balance"] = float(paper_balance)
    if max_open_trades is not None:
        env["CRYPTO_MAX_OPEN_TRADES"] = int(max_open_trades); fields["max_open_trades"] = int(max_open_trades)
    if stake_amount is not None:
        env["CRYPTO_STAKE_AMOUNT"] = float(stake_amount); fields["stake_amount"] = float(stake_amount)
    if leverage is not None:
        env["CRYPTO_LEVERAGE"] = float(leverage); fields["leverage"] = float(leverage)
    if not env:
        return {"ok": True, "unchanged": True, "status": status()}
    _set_env_keys(env)
    cur = _cfg()
    from trading.crypto.freqtrade.config_template import write_config
    new_cfg = dataclasses.replace(cur, **fields)
    write_config(cfg=new_cfg)
    restart_bot()
    return {"ok": True, "applied": fields, "status": status()}


def set_segments_enabled(segments: list[str]) -> dict:
    """Enable exactly `segments` in the multi-segment engine (persist to .env CRYPTO_SEGMENTS,
    rewrite config.json's mlnb_segments block, restart the one engine process)."""
    valid = ("futures", "spot", "options", "prediction")
    segs = [s for s in (str(x).strip().lower() for x in segments) if s in valid]
    if not segs:
        raise ValueError(f"need at least one of {valid}, got {segments!r}")
    _set_env_keys({"CRYPTO_SEGMENTS": ",".join(segs)})
    os.environ["CRYPTO_SEGMENTS"] = ",".join(segs)   # config_template reads env at write time
    from trading.crypto.freqtrade.config_template import write_config
    write_config(cfg=_cfg())
    restart_bot()
    return {"ok": True, "segments": segs}


def main(argv: list[str]) -> int:
    import json as _json
    cmd = argv[1] if len(argv) > 1 else "status"
    if cmd == "status":
        print(_json.dumps(status(), indent=2)); return 0
    confirm = "--confirm" in argv
    try:
        if cmd in ("paper", "live"):
            res = switch(mode=cmd, confirm=confirm)
        elif cmd in ("spot", "futures"):
            res = switch(segment=cmd, confirm=confirm)
        else:
            print(f"usage: status | paper | live --confirm | spot | futures"); return 2
        print(_json.dumps(res, indent=2)); return 0
    except (PermissionError, ValueError) as e:
        print(f"refused: {e}"); return 1


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv))
