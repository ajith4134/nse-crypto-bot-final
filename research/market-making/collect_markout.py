#!/usr/bin/env python3
"""Fill-toxicity (markout) collector for the market-making feasibility test.

The question: if we posted passive quotes, would our fills be systematically followed
by adverse price moves? (i.e. does adverse selection eat the spread we capture?)

We do NOT need to quote to answer this. Every Binance trade carries `m` = "was the
BUYER the maker". That identifies, for every single trade, which side was PASSIVE --
i.e. a real resting maker order that just got filled, at a known price and time.
That is the exact population our quotes would live in.

NOTE on stream choice: on the FUTURES host (fstream) `@aggTrade` yields nothing from
this VM -- measured 0 messages in 12s on BTCUSDT while REST reported ~770 trades/min.
`@trade` works and is strictly better here: per-trade rather than aggregated, same `m`
flag. (Spot's `stream.binance.com` serves @aggTrade fine; the futures host does not.)

  m == True  -> the resting order was a BID  -> maker is now LONG  at price p
  m == False -> the resting order was an ASK -> maker is now SHORT at price p

Markout at horizon h = the maker's mark-to-market PnL h seconds after the fill,
signed by the maker's side, in basis points. This is the industry-standard measure
of adverse selection. Negative markout = toxic flow = we get picked off.

Writes newline-delimited JSON so the analysis can be re-run without re-collecting.
"""
import asyncio
import json
import os
import sys
import time

import websockets

WS = "wss://fstream.binance.com/stream?streams="
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# Candidates chosen by the spread-vs-flow scan: wide spread AND real flow.
# Majors included as controls -- their spread is BELOW the maker fee, so they should
# look unambiguously unprofitable and act as a sanity check on the measurement.
SYMBOLS = ["HOMEUSDT", "SYNUSDT", "GWEIUSDT", "BULLAUSDT", "FWDIUSDT", "SOLUSDT", "BTCUSDT"]


async def collect(symbols, seconds, out_path):
    streams = "/".join(
        f"{s.lower()}@{kind}" for s in symbols for kind in ("trade", "bookTicker")
    )
    url = WS + streams
    deadline = time.time() + seconds
    n_trade = n_book = 0

    with open(out_path, "w") as fh:
        async with websockets.connect(url, ping_interval=20, max_queue=None) as ws:
            print(f"connected: {len(symbols)} symbols, {seconds}s", flush=True)
            while time.time() < deadline:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=30)
                except asyncio.TimeoutError:
                    print("recv timeout", file=sys.stderr, flush=True)
                    break
                msg = json.loads(raw)
                d = msg.get("data", {})
                ev = d.get("e")
                # local receipt time matters: it is what WE could have acted on
                now_ms = time.time() * 1000.0
                if ev == "trade":
                    rec = {
                        "t": "T", "s": d["s"], "ts": d["T"], "rx": now_ms,
                        "p": d["p"], "q": d["q"], "m": d["m"],
                    }
                    n_trade += 1
                elif d.get("u") is not None and d.get("b") is not None:
                    # bookTicker (no "e" field on futures bookTicker payloads)
                    rec = {
                        "t": "B", "s": d["s"], "ts": d.get("T") or d.get("E"), "rx": now_ms,
                        "b": d["b"], "B": d["B"], "a": d["a"], "A": d["A"],
                    }
                    n_book += 1
                else:
                    continue
                fh.write(json.dumps(rec) + "\n")
                if (n_trade + n_book) % 20000 == 0:
                    left = int(deadline - time.time())
                    print(f"  {n_trade:,} trades / {n_book:,} book  ({left}s left)", flush=True)

    print(f"done: {n_trade:,} trades, {n_book:,} book updates -> {out_path}", flush=True)


if __name__ == "__main__":
    secs = int(sys.argv[1]) if len(sys.argv) > 1 else 600
    out = os.path.join(OUT_DIR, f"markout-raw-{int(time.time())}.jsonl")
    asyncio.run(collect(SYMBOLS, secs, out))
    print(out)
