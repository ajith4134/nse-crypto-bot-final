"""run_online.py — Trading Phase ONLINE (O1–O5) OFFLINE demo.

Drives the always-on trading bot end to end, fully OFFLINE and deterministic (NO network,
NO API keys, NO broker, NO live exchange). Everything the live deployment does is exercised
through INJECTED stubs so the same code paths run here that run in production:

  * O1 session — per-market LIVE↔REPLAY mode (crypto 24/7 LIVE, NSE replays its OHLCV cache
    off-hours).
  * O1 state  — per-market enable/mode/allow_live + ACTIVE/REDUCING/HALTED trading-state gate.
  * O2 wallet — editable per-market PAPER money (set balance / top-up / reset).
  * O4 supervisor — one step() loop: acquire price → decide → gate → route fill.
  * O5 controls — the SHARED, persisted control surface the dashboard + Telegram both use:
    Start/Stop/Pause/Halt, paper↔real switch (guarded), editable money, panic().

Walkthrough: START crypto + NSE (paper) → run a few off-hours steps (NSE replay, crypto
live) → edit paper balance → show status → STOP → a paper→real switch (blocked without
allow_live, then allowed+confirmed but no live adapter wired) → panic()/halt.

`build_demo_online()` returns a JSON-able status snapshot for the dashboard (cached).

Usage:
    .venv/bin/python run_online.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime

import numpy as np
import pandas as pd

from trading.online import controls
from trading.online.session import IST
from trading.online.supervisor import OnlineSupervisor


def _hdr(title: str) -> None:
    print(f"\n=== {title} ===")


# ── injected, deterministic stub I/O (no network) ─────────────────────────────────────
class _StubCryptoPrice:
    """A deterministic crypto live-price source (callable(symbol) -> {last})."""

    def __init__(self, start: float = 60000.0):
        self.t = 0
        self.start = start

    def __call__(self, symbol: str) -> dict:
        self.t += 1
        # gentle deterministic drift so the demo isn't static
        return {"last": self.start * (1.0 + 0.001 * self.t)}


def _seeded_nse_ohlcv(seed: int = 0, n: int = 60) -> pd.DataFrame:
    """A deterministic NSE OHLCV cache for off-hours REPLAY (rising drift)."""
    rng = np.random.default_rng(seed)
    drift = np.linspace(0.0, 0.10, n) + rng.normal(0, 0.003, n)
    close = 2800.0 * np.exp(drift)
    high = close * (1.0 + np.abs(rng.normal(0, 0.002, n)))
    low = close * (1.0 - np.abs(rng.normal(0, 0.002, n)))
    open_ = np.concatenate([[close[0]], close[:-1]])
    vol = 10_000.0 + rng.normal(0, 200, n)
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close,
                         "volume": np.abs(vol)})


def _decide_fn(market: str, symbol: str, window_or_price) -> dict:
    """A simple deterministic decision: go LONG on an up-bar, else FLAT (offline demo)."""
    if isinstance(window_or_price, pd.DataFrame) and len(window_or_price) >= 2:
        up = window_or_price["close"].iloc[-1] > window_or_price["close"].iloc[-2]
        return {"action": "LONG", "size": 1.0} if up else {"action": "FLAT"}
    return {"action": "LONG", "size": 0.01}     # crypto: small fixed clip


# Off-hours NSE timestamp (Sunday) so the session resolves to REPLAY deterministically.
_OFF_HOURS = datetime(2026, 6, 28, 3, 0, tzinfo=IST)   # Sunday 03:00 IST → NSE closed


def build_supervisor() -> OnlineSupervisor:
    """An OnlineSupervisor wired to the SHARED persisted controls registry + wallet book.

    The supervisor reuses controls.registry()/book() so a Start from controls (or the
    dashboard / Telegram) is the same state the supervisor steps over — one source of truth.
    """
    return OnlineSupervisor(
        registry=controls.registry(),
        wallets=controls.book(),
        crypto_price_source=_StubCryptoPrice(),
        nse_ohlcv={"RELIANCE": _seeded_nse_ohlcv()},
        decide_fn=_decide_fn,
    )


_CACHE: dict | None = None


def build_demo_online() -> dict:
    """JSON-able ONLINE snapshot for the dashboard (cached, deterministic, offline)."""
    global _CACHE
    if _CACHE is None:
        # Run the demo against in-memory (non-persisting) singletons so the dashboard
        # snapshot is reproducible and never writes machine-local paper state on import.
        controls.reset_singletons(persist=False)
        controls.start("CRYPTO")
        controls.start("NSE")
        sup = build_supervisor()
        sup.run(steps=3, when=_OFF_HOURS)
        controls.set_balance("NSE", 500_000.0)
        controls.top_up("CRYPTO", 25_000.0)
        snap = controls.status()
        snap["heartbeats"] = sup.heartbeats
        _CACHE = json.loads(json.dumps(snap, default=str))   # ensure JSON-able
    return _CACHE


def main() -> int:
    print("ML Network Brain — Trading ONLINE (O1–O5 always-on bot) offline demo")

    # Fresh, non-persisting singletons so the demo is deterministic + leaves no disk state.
    controls.reset_singletons(persist=False)

    _hdr("1. START crypto + NSE (paper) via the shared control surface")
    print("  start CRYPTO →", controls.start("CRYPTO"))
    print("  start NSE    →", controls.start("NSE"))

    sup = build_supervisor()
    _hdr("2. run 3 supervised steps OFF-HOURS (NSE→REPLAY, crypto→LIVE)")
    for entry in sup.run(steps=3, when=_OFF_HOURS):
        for r in entry["results"]:
            if "skipped" in r:
                print(f"  hb{entry['heartbeat']} {r['market']:<7} skipped: {r['skipped']}")
            else:
                routed = r.get("routed")
                tag = (routed.get("mode") if isinstance(routed, dict) else None) or "—"
                print(f"  hb{entry['heartbeat']} {r['market']:<7} mode={r['mode']:<6} "
                      f"price={r['price']:<12} action={r['action']:<5} "
                      f"gate_ok={r['gate']['ok']} routed={tag}")

    _hdr("3. edit paper money (set NSE balance, top-up crypto)")
    nse_w = controls.set_balance("NSE", 500_000.0)
    cry_w = controls.top_up("CRYPTO", 25_000.0)
    print(f"  NSE wallet  → cash={nse_w['cash']:.2f} {nse_w['currency']} "
          f"equity={nse_w['equity']:.2f}")
    print(f"  CRYPTO wallet → cash={cry_w['cash']:.2f} {cry_w['currency']} "
          f"equity={cry_w['equity']:.2f}")

    _hdr("4. status snapshot (shared registry + walletbook)")
    print(json.dumps(controls.status(), indent=2, default=str)[:900] + "  ...")

    _hdr("5. STOP NSE (no new activity)")
    print("  stop NSE →", controls.stop("NSE"))

    _hdr("6. paper→real switch attempt (guarded 2-step)")
    blocked = controls.set_mode("CRYPTO", "REAL")
    print(f"  REAL without allow_live → ok={blocked['ok']}  reason={blocked.get('reason')!r}")
    controls.set_allow_live("CRYPTO", True)
    no_confirm = controls.set_mode("CRYPTO", "REAL")
    print(f"  REAL armed but no confirm → ok={no_confirm['ok']}  "
          f"reason={no_confirm.get('reason')!r}")
    confirmed = controls.set_mode("CRYPTO", "REAL", confirm=True)
    print(f"  REAL armed + confirmed → ok={confirmed['ok']}  mode={confirmed.get('mode')}")
    # A REAL order now has no live adapter wired → routed honestly reports that.
    real_step = sup.step(symbols={"CRYPTO": "BTCUSDT"}, when=_OFF_HOURS)
    routed = real_step["results"][0].get("routed")
    print(f"  REAL step routed → {routed}  (no live adapter wired — honest, no network)")

    _hdr("7. Telegram command surface (same controls, offline-safe)")
    for cmd, args in (("/online_status", ""), ("/balance", "NSE 750000"),
                      ("/start_nse", "")):
        print(f"  > {cmd} {args}".rstrip())
        for line in controls.handle_command(cmd, args).splitlines():
            print(f"      | {line}")

    _hdr("8. PANIC — halt ALL markets (the big red button)")
    controls.panic("run_online demo panic")
    for m, d in controls.status()["markets"].items():
        print(f"  {m:<7} trading_state={d['trading_state']}")

    _hdr("9. dashboard snapshot (build_demo_online — JSON-able, cached)")
    print(json.dumps(build_demo_online(), indent=2, default=str)[:700] + "  ...")

    print("\n✅ ONLINE (O1–O5) always-on bot demo complete (offline, deterministic, "
          "no network).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
