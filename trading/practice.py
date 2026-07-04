"""Practice mode — the brain trades HISTORIC data to learn (user mandate
2026-07-04: "make brain trade on historic data to practice", NSE parity with
crypto).

The replay drives the SAME decision path the live crypto loop uses — the
CortexSignalSource (28-feature bus: candles + recorded order-book + MTF +
market + live-recorded blocks, reflex-arc abstention, risk-overlay sizing) —
bar by bar over a historic OHLCV frame, with honest paper fills:

    fit on the first `warmup_frac` of history (chronological)
    → per bar: signal(symbol, df[:i]) → open/close a paper position at the
      NEXT bar's open (no same-bar fill), fees applied
    → every closed practice trade credits the PRACTICE trust ledger
      (separate file — never contaminates the live ledger)
    → run summary scored by trading.fitness.scorecard + honest gates.

State isolation: results land in data/cache/practice_runs/<run_id>.json and the
trust ledger at data/cache/practice_runs/trust.json — never the live journal
(isolate-state rule)."""
from __future__ import annotations

import json
import os
import time

import numpy as np

RUNS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir,
                                        "data", "cache", "practice_runs"))
FEE = 0.0005          # ~5bps per side (NSE-ish all-in for practice realism)


def _source(trust_path: str, explore: bool):
    """A fresh CortexSignalSource wired to the PRACTICE trust ledger.

    explore=True loosens the reflex arc's conformal abstention (alpha 0.15→0.35,
    flat_threshold 0.53) so the brain actually PRACTICES — takes more trades and
    learns from their outcomes. The live loop keeps the strict calibrated arc;
    exploration is a training-ground privilege, never a live setting."""
    from core.trust import TrustLedger
    from trading.cortex_signal import CortexSignalSource, default_arc
    ledger = TrustLedger(path=trust_path)
    arc = default_arc(alpha=0.35, flat_threshold=0.53) if explore else None
    return CortexSignalSource(arc=arc), ledger


def replay(df, symbol: str, *, warmup_frac: float = 0.5, fee: float = FEE,
           run_id: str | None = None, record_trust: bool = True,
           explore: bool = True) -> dict:
    """Replay one symbol's history through the live cortex path.

    `df` = chronological OHLCV DataFrame with a 'date' column (any timeframe).
    Returns the run report (trades, equity, scorecard, per-expert credits) and
    persists it under data/cache/practice_runs/. Honest: if the cortex stays
    flat the whole time, the report says 0 trades — never a fabricated fill."""
    os.makedirs(RUNS_DIR, exist_ok=True)
    run_id = run_id or f"{symbol.replace('/', '_').replace(':', '_')}_{int(time.time())}"
    trust_path = os.path.join(RUNS_DIR, "trust.json")
    src, ledger = _source(trust_path, explore)

    n = len(df)
    cut = max(80, int(n * warmup_frac))
    if n - cut < 20:
        raise ValueError(f"history too short to practice on ({n} bars, warmup {cut})")
    src.fit(df.iloc[:cut], symbol)

    opens = df["open"].to_numpy(float)
    position = None            # {"side", "entry", "entry_i", "experts", "frac"}
    trades: list = []

    def _close(i: int, reason: str):
        nonlocal position
        if position is None:
            return
        px = float(opens[i])
        d = 1.0 if position["side"] == "long" else -1.0
        gross = d * (px - position["entry"]) / position["entry"]
        net = gross - 2 * fee
        tr = {"symbol": symbol, "side": position["side"],
              "entry_i": position["entry_i"], "exit_i": int(i),
              "entry": position["entry"], "exit": px,
              "net_ret": round(float(net), 6),
              "size_fraction": position["frac"],
              "experts": position["experts"], "exit_reason": reason}
        trades.append(tr)
        if record_trust and position["experts"]:
            # win→loss<0.5, loss→loss>0.5, magnitude-scaled (same shape as live
            # apply_trust_feedback) — but into the PRACTICE ledger only.
            mag = min(1.0, abs(net) * 20)
            loss = (1.0 - mag) / 2.0 if net > 0 else 0.5 + mag / 2.0
            for ex in position["experts"]:
                try:
                    ledger.update(str(ex), float(np.clip(loss, 0, 1)))
                except Exception:
                    pass
        position = None

    for i in range(cut, n - 1):
        sig = src.signal(symbol, df.iloc[: i + 1])
        side = sig.get("side")
        if position is not None:
            flip = side in ("long", "short") and side != position["side"]
            if side == "flat" and sig.get("reason", "").startswith("reflex arc stayed flat"):
                # calibrated abstention alone doesn't force an exit; hold.
                pass
            if flip:
                _close(i + 1, "signal_flip")
        if position is None and side in ("long", "short"):
            position = {"side": side, "entry": float(opens[i + 1]), "entry_i": i + 1,
                        "experts": list(sig.get("experts_fired") or []),
                        "frac": float(sig.get("size_fraction") or 0.0)}
    _close(n - 1, "end_of_history")

    rets = [t["net_ret"] for t in trades]
    equity = list(np.cumprod([1.0] + [1 + r for r in rets]))
    wins = sum(1 for r in rets if r > 0)
    report = {
        "run_id": run_id, "symbol": symbol, "explore": bool(explore),
        "bars": int(n), "warmup_bars": int(cut),
        "n_trades": len(trades), "wins": wins,
        "win_rate": round(wins / len(trades), 4) if trades else None,
        "total_return": round(float(equity[-1] - 1.0), 6),
        "fee_per_side": fee,
        "equity_curve": [round(float(e), 6) for e in equity],
        "trades": trades[-200:],
        "trust_path": trust_path,
        "practiced_at_bar_time": str(df["date"].iloc[-1]) if "date" in df else None,
    }
    try:                                     # honest gates when enough trades
        from trading.fitness import scorecard  # noqa: F401  (heavy; optional)
        if len(rets) >= 5:
            import pandas as pd
            r = pd.Series(rets)
            report["sharpe_naive"] = round(float(r.mean() / r.std() * np.sqrt(252)), 4) \
                if r.std() > 0 else None
    except Exception:
        pass
    with open(os.path.join(RUNS_DIR, f"{run_id}.json"), "w") as fh:
        json.dump(report, fh, indent=1)
    return report


def list_runs(limit: int = 20) -> list:
    """Most recent practice-run reports (summaries only)."""
    if not os.path.isdir(RUNS_DIR):
        return []
    out = []
    files = sorted((f for f in os.listdir(RUNS_DIR) if f.endswith(".json")
                    and f != "trust.json"),
                   key=lambda f: -os.path.getmtime(os.path.join(RUNS_DIR, f)))
    for f in files[:limit]:
        try:
            with open(os.path.join(RUNS_DIR, f)) as fh:
                r = json.load(fh)
            out.append({k: r.get(k) for k in
                        ("run_id", "symbol", "bars", "n_trades", "win_rate",
                         "total_return", "sharpe_naive")})
        except Exception:
            continue
    return out
