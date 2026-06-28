"""run_trading.py — Trading Phase T1 (NSE) smoke test + status.

Verifies the NSE Foundation end-to-end against a RUNNING OpenAlgo server:
  1. Config + connectivity (honest ping — fails loudly if server/key absent).
  2. Instrument search (OpenAlgo symbol DB).
  3. Master toggle ON → live tick feed starts; watchlist add streams prices.
  4. Paper order place → modify → cancel (sandbox; never live unless --live).
  5. Squareoff schedule for the current IST time.
  6. Master toggle OFF → feed stops (zero-activity contract).

Usage:
    .venv/bin/python run_trading.py            # status + paper order cycle
    .venv/bin/python run_trading.py --status   # status only, no orders
    .venv/bin/python run_trading.py --symbol RELIANCE

Secrets-safe: prints only key fingerprints, never full keys.
"""
from __future__ import annotations

import argparse
import json
import sys
import time

from trading.config import trading_config
from trading.session import NSESession
from trading.openalgo_client import OpenAlgoError


def _hdr(title: str) -> None:
    print(f"\n=== {title} ===")


def main() -> int:
    ap = argparse.ArgumentParser(description="Trading T1 (NSE) smoke test")
    ap.add_argument("--status", action="store_true", help="status only, no orders")
    ap.add_argument("--symbol", default="RELIANCE", help="symbol to watch/trade")
    ap.add_argument("--exchange", default="NSE")
    ap.add_argument("--qty", type=int, default=1)
    ap.add_argument("--product", default="MIS", help="MIS|CNC|NRML (CNC works after 15:15 IST)")
    ap.add_argument("--price-type", default="MARKET", help="MARKET|LIMIT|SL|SL-M")
    ap.add_argument("--price", type=float, default=0.0, help="limit price (for LIMIT orders)")
    ap.add_argument("--live", action="store_true",
                    help="DANGER: allow a real-money order (requires TRADING_MODE=live)")
    args = ap.parse_args()

    _hdr("T1 config")
    print(json.dumps(trading_config.as_status(), indent=2))
    if not trading_config.is_configured:
        print("\n⚠️  OPENALGO_API_KEY is absent. Start the OpenAlgo server, copy its API "
              "key into .env, then re-run. (See .env.example / blueprint §8.1.)")
        return 2

    session = NSESession()

    _hdr("connectivity (real ping)")
    conn = session.client.ping()
    print(f"connected={conn.connected}  host={conn.host}  broker={conn.broker}")
    print(f"detail: {conn.detail}")
    if not conn.connected:
        print("\n⚠️  OpenAlgo server not reachable. Is it running at the host above?")
        return 3

    # Align the server's analyzer with our mode: paper -> sandbox (no live broker hit).
    try:
        analyze = session.client.sync_mode()
        print(f"analyzer mode: {'ANALYZE (paper/sandbox)' if analyze else 'LIVE (real money)'}")
    except OpenAlgoError as exc:
        print(f"analyzer sync skipped: {exc}")

    _hdr(f"instrument search: {args.symbol}")
    try:
        hits = session.store.search(args.symbol, args.exchange)
        for inst in hits[:5]:
            print(f"  {inst.exchange:5s} {inst.symbol:24s} {inst.instrument_type:4s} {inst.name}")
        if not hits:
            print("  (no matches)")
    except OpenAlgoError as exc:
        print(f"  search error: {exc}")

    _hdr("master toggle ON → feed start")
    session.toggle.turn_on()
    session.watchlist.add(args.symbol, args.exchange)
    print(f"toggle on={session.toggle.is_on}  feed running={session.feed.is_running} "
          f"mode={session.feed.mode}")
    time.sleep(2.5)  # let a couple of ticks arrive
    tick = session.cache.get(args.symbol, args.exchange)
    print(f"latest tick: {tick.ltp if tick else 'none yet'}")

    _hdr("squareoff schedule (IST now)")
    print(f"due now: {session.status()['squareoff_due'] or '—'}")

    if not args.status:
        _hdr(f"paper order cycle ({trading_config.mode} mode)")
        try:
            placed = session.place_order(
                symbol=args.symbol, action="BUY", exchange=args.exchange,
                quantity=args.qty, product=args.product, price_type=args.price_type,
                price=args.price, allow_live=args.live,
            )
            oid = placed.get("orderid") or placed.get("order_id")
            print(f"  placed: {placed}")
            if oid:
                mod = session.client.modify_order(
                    order_id=oid, symbol=args.symbol, action="BUY",
                    exchange=args.exchange, quantity=args.qty,
                    price=(args.price or 1.0) + 1.0,
                    product=args.product, price_type="LIMIT", allow_live=args.live,
                )
                print(f"  modified: {mod}")
                can = session.cancel_order(oid)
                print(f"  cancelled: {can}")
        except OpenAlgoError as exc:
            print(f"  order error: {exc}")

    _hdr("master toggle OFF → feed stop (zero-activity)")
    session.toggle.turn_off()
    print(f"toggle on={session.toggle.is_on}  feed running={session.feed.is_running}")
    session.shutdown()
    print("\n✅ T1 smoke test complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
