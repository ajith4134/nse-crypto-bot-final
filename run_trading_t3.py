"""run_trading_t3.py — Trading Phase T3 (Trade Execution Engine) offline demo + status.

Drives the network-INDEPENDENT execution engine end to end with a deterministic
synthetic price path (NO network, NO API keys, fully reproducible):

  1. Order lifecycle: register a PENDING order, fill it → entry.
  2. Open a LONG TradeManager (ExponentialTrailingStop + a two-rung R-multiple
     ProfitLadder: book 50% at +1R, 25% at +2R, trail the rest).
  3. Feed a deterministic up-then-pullback bar path through engine.on_bar(...) and
     print every partial-booking and the trailing-stop exit as they fire.
  4. Print the final honest engine.status() (orders/positions/breaker/kill-switch).
  5. Kill-switch demo: engine.panic() cancels all + flattens all (idempotent).
  6. Circuit-breaker demo: a tiny daily-loss limit trips on open P&L, auto-engaging
     the kill-switch (auto-flatten + halt new orders).

Everything here is pure CPU logic — the same engine drives paper sim, live NSE
(OpenAlgo) and crypto (ccxt) once market I/O callables are injected.

Usage:
    .venv/bin/python run_trading_t3.py
"""
from __future__ import annotations

import json
import sys

from trading.execution import (
    DailyCircuitBreaker,
    ExecutionEngine,
    ExponentialTrailingStop,
    Order,
    ProfitLadder,
    Rung,
    TradeManager,
    check_margin,
    nse_intraday_margin,
)


def _hdr(title: str) -> None:
    print(f"\n=== {title} ===")


def _demo_happy_path() -> ExecutionEngine:
    """Order fill → managed long → partial bookings → trailing-stop exit."""
    engine = ExecutionEngine(max_daily_loss=10_000.0)

    symbol, qty, entry, stop = "RELIANCE", 100.0, 100.0, 95.0  # R = 5.0

    _hdr("1. order lifecycle (register → fill)")
    order = engine.register_order(Order(
        id="O-1", symbol=symbol, exchange="NSE", side="BUY", quantity=qty))
    engine.on_fill(order.id, qty=qty, price=entry)
    print(f"  order {order.id}: status={order.status.value} "
          f"filled={order.filled_qty} avg={order.avg_price:.2f}")

    _hdr("2. honest margin estimate (NSE intraday, 5x)")
    bd = nse_intraday_margin(qty * entry)
    chk = check_margin(required=bd["total"], available=5_000.0, breakdown=bd)
    print(f"  notional={bd['notional']:.0f} required={chk.required:.0f} "
          f"available={chk.available:.0f} ok={chk.ok} (estimate, not broker SPAN)")

    _hdr("3. open managed LONG (exp-trail + 2-rung R ladder)")
    ladder = ProfitLadder(
        side="long", entry_price=entry, quantity=qty, initial_stop=stop,
        rungs=[
            Rung(target=1.0, fraction=0.50, as_r=True, label="+1R"),
            Rung(target=2.0, fraction=0.25, as_r=True, label="+2R"),
        ],
    )
    manager = TradeManager(
        symbol=symbol, side="long", quantity=qty, entry_price=entry,
        trailing=ExponentialTrailingStop("long", entry, base_frac=0.03,
                                         floor_frac=0.004, k=8.0),
        ladder=ladder, initial_stop=stop,
    )
    engine.open_trade(symbol, manager)
    print(f"  entry={entry} stop={stop} R={abs(entry - stop):.1f} "
          f"rungs: book 50% @ +1R(105), 25% @ +2R(110), trail rest")

    _hdr("4. feed deterministic bar path → bookings + exit")
    # close prices (price-only feed); rises through +1R and +2R, then pulls back.
    path = [101.0, 103.0, 106.0, 108.0, 110.5, 113.0, 112.0, 110.0]
    for px in path:
        res = engine.on_bar(symbol, high=px, low=px, close=px)
        line = f"  px={px:6.2f}  stop={res.get('stop'):.2f}"
        for ev in res.get("book_events", []):
            line += (f"\n      BOOK {ev['label']}: qty={ev['qty']:.0f} @ {ev['price']:.2f} "
                     f"remaining={ev['remaining_after']:.0f}")
        if res.get("exit"):
            line += (f"\n      EXIT ({res['exit_reason']}): qty={res['exit_qty']:.0f} "
                     f"@ {res['exit_price']:.2f}")
        print(line)

    _hdr("5. final engine.status() (real state only)")
    print(json.dumps(engine.status(), indent=2, default=str))
    return engine


def _demo_kill_switch() -> None:
    """Panic flatten on a fresh engine holding one open position."""
    _hdr("6. kill-switch demo (panic: cancel-all + flatten-all)")
    engine = ExecutionEngine(max_daily_loss=10_000.0)
    engine.register_order(Order(id="O-K", symbol="INFY", exchange="NSE",
                                side="BUY", quantity=50.0))
    engine.open_trade("INFY", TradeManager(
        symbol="INFY", side="long", quantity=50.0, entry_price=1500.0,
        trailing=ExponentialTrailingStop("long", 1500.0), initial_stop=1480.0))
    report = engine.panic(reason="manual demo")
    print(f"  engaged={engine.kill.engaged} cancelled={report['cancelled']} "
          f"flattened={report['flattened']} ok={report['ok']}")
    again = engine.panic(reason="mashing the button")
    print(f"  second engage idempotent: already_engaged={again.get('already_engaged')}")
    st = engine.status()
    print(f"  open_positions now={st['open_positions']} "
          f"kill_switch.engaged={st['kill_switch']['engaged']}")


def _demo_circuit_breaker() -> None:
    """Tiny daily-loss limit trips on open P&L → auto kill-switch."""
    _hdr("7. circuit-breaker trip demo (open-loss breaches daily limit)")
    # persist=False so the demo never writes/reads circuit_breaker.json state.
    breaker = DailyCircuitBreaker(max_daily_loss=200.0, persist=False)
    engine = ExecutionEngine(circuit_breaker=breaker)
    # Wide trailing stop so the adverse move registers as OPEN loss (no early exit).
    engine.open_trade("NIFTYBEES", TradeManager(
        symbol="NIFTYBEES", side="long", quantity=100.0, entry_price=100.0,
        trailing=ExponentialTrailingStop("long", 100.0, base_frac=0.5,
                                          floor_frac=0.49, k=0.0),
        initial_stop=95.0))
    print(f"  limit=-{breaker.max_daily_loss:.0f}  feeding an adverse bar (100 → 97)...")
    res = engine.on_bar("NIFTYBEES", high=97.0, low=97.0, close=97.0)  # open PnL ≈ -300
    cb = engine.status()["circuit_breaker"]
    print(f"  open_pnl={cb['open_pnl']:.0f} tripped={cb['tripped']} "
          f"reason={cb['trip_reason']!r}")
    print(f"  tripped_this_bar={res.get('circuit_breaker_tripped', False)} "
          f"kill_switch.engaged={engine.kill.engaged}")
    print(f"  new orders blocked: allow_new_order={breaker.allow_new_order()}")


def main() -> int:
    print("ML Network Brain — Trading T3 (Trade Execution Engine) offline demo")
    engine = _demo_happy_path()
    # Sanity: the happy-path trade fully booked/exited.
    assert engine.status()["open_positions"] == 0, "happy-path position should be flat"
    _demo_kill_switch()
    _demo_circuit_breaker()
    print("\n✅ T3 execution-engine demo complete (offline, deterministic).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
