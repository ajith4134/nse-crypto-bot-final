"""trading/broker_sense/ocular_perception.py — the funnel's NEW eyes (Phase-2 deep read).

Ties the Ocular Cortex + network interception + free vision into the Broker-Sense funnel's
per-symbol VERIFY stage, so every candidate the brain considers is perceived the way a
professional trader reads a symbol page: the app's OWN order book / funding / OI / candles
(captured for free via interception) + a free-VLM reading of the actual chart pixels +
consolidated layout memory — all fused into one frame, every number turned into a learning
column, and the frame linked to the decision so the outcome can be traced back to what was
seen.

Read-only: it observes and reads; it never places an order (execution stays in exec_adapter).
Budget-safe: a per-cycle vision quota bounds the free-VLM reads; everything degrades honestly
when a session/page/vision provider is unavailable."""
from __future__ import annotations

import os
import time

from trading.broker_sense.learning_columns import discover_from_text, get_registry


def _vision_quota() -> int:
    try:
        return int(os.environ.get("OCULAR_VISION_QUOTA", "6"))
    except ValueError:
        return 6


def _flag(name: str, default: str = "1") -> bool:
    return os.environ.get(name, default) not in ("0", "false", "False", "")


class OcularPerception:
    """Per-candidate fused perception feeding the funnel. One instance per funnel."""

    def __init__(self, *, cortex=None, market: str = ""):
        self.market = market
        if cortex is None:
            from trading.brain.vision.ocular_cortex import get_cortex
            cortex = get_cortex()
        self.cortex = cortex
        self._frames: dict[str, object] = {}          # symbol -> last PerceptualFrame (this cycle)
        # PER-5m-BAR VISION MEMO (2026-07-12): cortex.perceive (browser vision) is the funnel
        # VERIFY hog measured live at ~0.85s/candidate. The frame is bar-stable, but reset_cycle
        # cleared _frames EVERY cycle → the same symbol was re-perceived on each of the 3-4 cycles
        # per bar. This bar-scoped cache reuses a symbol's frame across cycles within its bar so
        # perceive runs once/bar — while enrich() still mines its learning columns every call
        # (side effects preserved). OCULAR_MEMO=0 disables.
        self._bar_frames: dict = {}                   # (symbol, bar_epoch) -> PerceptualFrame
        self._vision_used = 0
        self.stats = {"perceived": 0, "vision_reads": 0, "novel": 0, "columns_from_book": 0}

    def reset_cycle(self) -> None:
        self._vision_used = 0
        self._frames.clear()                          # this-cycle frames only; bar cache persists

    def _bar_frame(self, symbol: str):
        """Return this symbol's frame if it was perceived earlier in the CURRENT bar, else None.
        OCULAR_MEMO=0 disables; OCULAR_MEMO_BAR_S sets the bar seconds (default 300 = 5m)."""
        if os.environ.get("OCULAR_MEMO", "1") not in ("1", "true", "TRUE", "yes", "on"):
            return None
        try:
            bar = int(os.environ.get("OCULAR_MEMO_BAR_S", "300"))
        except Exception:
            bar = 300
        return self._bar_frames.get((symbol, int(time.time() // max(1, bar))))

    def _store_bar_frame(self, symbol: str, frame) -> None:
        if os.environ.get("OCULAR_MEMO", "1") not in ("1", "true", "TRUE", "yes", "on"):
            return
        try:
            bar = int(os.environ.get("OCULAR_MEMO_BAR_S", "300"))
        except Exception:
            bar = 300
        epoch = int(time.time() // max(1, bar))
        # drop stale-bar entries so the cache can't grow unbounded across bars
        if len(self._bar_frames) > 4000:
            self._bar_frames = {k: v for k, v in self._bar_frames.items() if k[1] == epoch}
        self._bar_frames[(symbol, epoch)] = frame

    # ── the app-chart vision sink (fed by ChartVision before it deletes a screenshot) ──
    def on_app_shot(self, symbol: str, tf: str, png_bytes: bytes) -> None:
        """ChartVision hands us the real app chart pixels for the primary timeframe (bounded
        by the per-cycle vision quota). We build a frame and get a FREE VLM reading of it."""
        if not _flag("OCULAR_VISION") or self._vision_used >= _vision_quota():
            return
        broker = self._broker_for(symbol)
        frame = self.cortex.perceive(broker, "symbol", screenshot=png_bytes,
                                     url=f"chart:{symbol}:{tf}")
        self._frames[symbol] = frame
        read = self.cortex.describe(
            frame,
            prompt=(f"You are a professional trader's eyes on the {symbol} {tf} chart. "
                    f"Read the price action, trend, key support/resistance, any visible "
                    f"indicators (RSI/MACD/MA/volume), and the order book if shown. State the "
                    f"likely direction (long/short/neutral) and a sensible entry, stop and "
                    f"target if a setup exists. Be concise and factual with numbers."),
            total_timeout=25.0)
        if read:
            self._vision_used += 1
            self.stats["vision_reads"] += 1
            discover_from_text(f"vision:{broker}", read, symbol=symbol)   # numbers → columns

    def _broker_for(self, symbol: str) -> str:
        # crypto app data is richest on binance; nse on angelone (owner's first slice)
        return "binance" if self.market == "crypto" else "angelone"

    # ── per-candidate enrichment (called in the funnel VERIFY loop) ──────────────
    def enrich(self, symbol: str, *, lane: str = "", chart: dict | None = None,
               book: dict | None = None, deadline: float | None = None) -> dict:
        """Fuse the app's captured data (order book / funding / OI / candles via interception)
        with the chart vote + book into ONE frame; mine every number into learning columns;
        remember the layout; return the enriched signal for decision_snapshot['app_signals']."""
        if deadline is not None and time.monotonic() > deadline:
            return {}
        broker = lane if lane and lane != "tradingview" else self._broker_for(symbol)
        api_ref = {}
        if book:
            for k in ("bid", "ask", "spread_pct"):
                if isinstance(book.get(k), (int, float)):
                    api_ref[k] = book[k]
        # reuse the vision frame from on_app_shot if we already saw this symbol this cycle
        frame = self._frames.get(symbol)
        if frame is None:
            frame = self._bar_frame(symbol)            # reuse a frame perceived earlier THIS bar
            if frame is None:
                frame = self.cortex.perceive(broker, "symbol", api_ref=api_ref,
                                             url=f"symbol:{symbol}")
                self._store_bar_frame(symbol, frame)
            self._frames[symbol] = frame
        verdict = self.cortex.last_verdict()
        if verdict.get("novel"):
            self.stats["novel"] += 1
        self.stats["perceived"] += 1
        # every number the app already computed (funding, OI, long/short, ticker fields…)
        # becomes a learning column for this symbol. JSON quotes/colons defeat the label-number
        # regex, so flatten scalar fields to plain "label value" text first (nested price
        # ladders like the order book are summarized separately, not exploded into columns).
        if frame.network:
            try:
                text = _flatten_numbers(frame.network)
                before = len(get_registry().columns)
                discover_from_text(f"network:{broker}", text, symbol=symbol)
                self.stats["columns_from_book"] += max(0, len(get_registry().columns) - before)
            except Exception:
                pass
        return {
            "broker": broker,
            "frame_id": frame.frame_id,
            "modalities": frame.modalities(),
            "network_kinds": sorted(frame.network),
            "novelty": verdict.get("consolidation", ""),
            "vision_read": (frame.vision_read or "")[:600],
            "order_book": _summarize_book(frame.network.get("orderbook")),
            "fused_values": frame.data_values(),
        }

    # ── visual-outcome linkage (called after a trade is entered) ─────────────────
    def link_entry(self, symbol: str, market: str, ts: float | None = None) -> str:
        """Link the frame that drove this entry to a decision key, so reflection can re-see it.
        Tolerant of symbol-format drift (the executor may report 'BTC/USDT:USDT' for a futures
        fill while the frame was keyed 'BTC/USDT')."""
        frame = self._frames.get(symbol) or self._frame_for_base(symbol)
        if frame is None:
            return ""
        key = f"{market}:{symbol}:{int(ts or time.time())}"
        try:
            return self.cortex.link_to_decision(frame, key)
        except Exception:
            return ""

    def _frame_for_base(self, symbol: str):
        """Match a stored frame by base symbol, ignoring a settlement suffix (':USDT') or the
        quote (so 'BTC/USDT:USDT' or 'BTC' finds the frame stored under 'BTC/USDT')."""
        base = symbol.split(":")[0]
        if base in self._frames:
            return self._frames[base]
        root = base.split("/")[0].upper()
        for k, fr in self._frames.items():
            if k.split(":")[0].split("/")[0].upper() == root:
                return fr
        return None

    def status(self) -> dict:
        return {"stats": dict(self.stats), "vision_used": self._vision_used,
                "cortex": self.cortex.status()}


def _flatten_numbers(obj, prefix: str = "", *, out=None, depth: int = 0, cap: int = 80) -> str:
    """Walk a captured JSON body and emit 'label value' lines for scalar numbers (skipping the
    long price ladders, which are summarized elsewhere), so the learning-column miner can read
    them. Returns newline-joined text."""
    if out is None:
        out = []
    if len(out) >= cap or depth > 4:
        return "\n".join(out)
    if isinstance(obj, dict):
        for k, v in obj.items():
            if len(out) >= cap:               # enforce the budget mid-loop, not just on entry
                break
            label = f"{prefix}{k}" if not prefix else f"{prefix}_{k}"
            if isinstance(v, bool):
                continue
            if isinstance(v, (int, float)):
                out.append(f"{label} {v}")
            elif isinstance(v, (dict,)):
                _flatten_numbers(v, label, out=out, depth=depth + 1, cap=cap)
            elif isinstance(v, list) and v and isinstance(v[0], dict):
                _flatten_numbers(v[0], label, out=out, depth=depth + 1, cap=cap)
            # bare price ladders (list of lists) are skipped — see _summarize_book
    return "\n".join(out)


def _summarize_book(ob) -> dict:
    """Compact top-of-book + imbalance from a captured order-book JSON (bids/asks ladders)."""
    if not isinstance(ob, dict):
        return {}
    bids, asks = ob.get("bids") or ob.get("b"), ob.get("asks") or ob.get("a")
    if not bids and not asks:                # no ladder present → honestly empty
        return {}
    try:
        bid = float(bids[0][0]) if bids else None
        ask = float(asks[0][0]) if asks else None
        bvol = sum(float(x[1]) for x in (bids or [])[:20])
        avol = sum(float(x[1]) for x in (asks or [])[:20])
        imb = (bvol - avol) / (bvol + avol) if (bvol + avol) else None
        return {"bid": bid, "ask": ask, "depth_bid": round(bvol, 4), "depth_ask": round(avol, 4),
                "imbalance": round(imb, 4) if imb is not None else None}
    except Exception:
        return {}
