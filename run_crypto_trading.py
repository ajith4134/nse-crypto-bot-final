"""run_crypto_trading.py — Trading Phase T2 (Crypto) smoke test + status.

Verifies the Crypto Foundation against LIVE public ccxt data (no API keys needed):
  1. Config + exchange reachability (honest probe).
  2. Market search + live ticker.
  3. Master toggle ON → feed starts; watchlist add streams prices.
  4. Funding-rate monitor across exchanges.
  5. Paper order: simulate a fill against the REAL order book; show position +
     liquidation price; then close and show realised PnL.
  6. Master toggle OFF → feed stops (zero-activity contract).

Usage:
    .venv/bin/python run_crypto_trading.py
    .venv/bin/python run_crypto_trading.py --exchange okx --symbol ETH/USDT
    .venv/bin/python run_crypto_trading.py --leverage 10 --amount 0.01
"""
from __future__ import annotations

import argparse
import json
import sys
import time

from trading.crypto.config import crypto_config
from trading.crypto.session import CryptoSession


def _hdr(t: str) -> None:
    print(f"\n=== {t} ===")


def main() -> int:
    ap = argparse.ArgumentParser(description="Trading T2 (Crypto) smoke test")
    ap.add_argument("--exchange", default=None, help="ccxt exchange id (default from .env)")
    ap.add_argument("--symbol", default=None, help="default BTC/<quote>")
    ap.add_argument("--market-type", default="swap", help="spot|swap|future|option")
    ap.add_argument("--amount", type=float, default=0.001, help="base qty for paper order")
    ap.add_argument("--leverage", type=float, default=5.0)
    ap.add_argument("--margin-mode", default="isolated")
    ap.add_argument("--status", action="store_true", help="status only, no paper order")
    args = ap.parse_args()

    _hdr("T2 config")
    print(json.dumps(crypto_config.as_status(), indent=2))

    session = CryptoSession(market_type=args.market_type)
    exchange = (args.exchange or crypto_config.default_exchange).lower()
    symbol = args.symbol or f"BTC/{crypto_config.quote}"

    _hdr(f"reachability: {exchange}")
    r = session.client(exchange).reachable()
    print(f"reachable={r.ok}  {r.detail}")
    if not r.ok:
        print(f"\n⚠️  {exchange} public API not reachable from this host. Try another "
              f"exchange via --exchange (e.g. okx, kraken, kucoin) or set CRYPTO_EXCHANGES in .env.")
        return 3

    _hdr(f"market search + ticker: {symbol}")
    try:
        hits = session.client(exchange).search_markets(symbol.split("/")[0])
        for m in hits[:5]:
            print(f"  {m['symbol']:20s} type={m['type']} active={m['active']}")
        tk = session.client(exchange).ticker(symbol)
        print(f"  {symbol} last={tk.get('last')}  bid={tk.get('bid')} ask={tk.get('ask')}")
    except Exception as exc:
        print(f"  error: {exc}")

    _hdr("master toggle ON → feed start")
    session.toggle.turn_on()
    session.watchlist.add(symbol, exchange, args.market_type)
    print(f"toggle on={session.toggle.is_on}  feed running={session.feed.is_running}")
    time.sleep(3.0)
    tick = session.cache.get(symbol, exchange)
    print(f"latest tick: {tick.ltp if tick else 'none yet'}")

    if args.market_type == "swap":
        _hdr(f"funding rates: {symbol}")
        rates = session.funding.scan(symbol)
        for f in rates:
            print(f"  {f.exchange:8s} rate={f.rate_pct:.4f}%  annualized≈{f.annualized_pct:.1f}%")
        spread = session.funding.best_spread(rates)
        if spread:
            print(f"  spread={spread['spread_pct']:.4f}%  "
                  f"(long {spread['long_funding_exchange']} / short {spread['short_funding_exchange']})")

    if not args.status:
        _hdr(f"paper order: BUY {args.amount} {symbol} {args.leverage}x {args.margin_mode}")
        res = session.paper_order(symbol=symbol, side="buy", amount=args.amount,
                                  exchange=exchange, leverage=args.leverage,
                                  margin_mode=args.margin_mode)
        print(f"  fill: avg={res.get('avg_price')} slippage={res.get('slippage'):.5f} "
              f"liq={res.get('liquidation_price')}")
        marks = session._mark_prices()
        for p in session.paper.positions(marks):
            print(f"  position: {p['side']} {p['size']} @ {p['entry_price']} "
                  f"uPnL={p['unrealized_pnl']:.2f} liq={p['liquidation_price']:.2f}")
        close = session.paper_close(symbol, exchange)
        print(f"  close: realized_pnl={close.get('realized_pnl', 0.0):.4f}")
        print(f"  equity: {session.paper.equity():.2f} {crypto_config.quote}")

    _hdr("master toggle OFF → feed stop")
    session.toggle.turn_off()
    print(f"toggle on={session.toggle.is_on}  feed running={session.feed.is_running}")
    session.shutdown()
    print("\n✅ T2 smoke test complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
