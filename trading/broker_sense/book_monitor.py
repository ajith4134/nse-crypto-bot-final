"""trading/broker_sense/book_monitor.py — non-invasive screen-mirror order-book reader.

Owner's step 5: extract bid/ask WITHOUT touching the page's source — a "monitor mode".
Implementation: screenshot the RENDERED pixels of the app's book region and OCR them
(PaddleOCR via gui.perception.OcrReader). Because it reads pixels, not DOM, it works on
canvas order books that expose no HTML at all, and it can't perturb the page.

Savers G + rule 4:
  • TOP-OF-BOOK only, ON-CHANGE only — the region screenshot is hashed; unchanged pixels
    ⇒ the last read is returned with zero OCR work.
  • ACCURACY GATE — the OCR bid/ask must sit within 1% of the API reference quote; a
    misread digit is discarded and the API number is used instead (source honestly flips
    to "api:*"), so no trade is ever skipped OR taken on a bad read.
"""
from __future__ import annotations

import hashlib
import os
import re
import time

from trading import state
from trading.broker_sense import data_failsafe
from trading.broker_sense.brokers import REGISTRY

_NUM = re.compile(r"\d[\d,]*\.?\d+")
_SHOT = "book_shots"


def _shot_dir():
    d = state._path(_SHOT)
    d.mkdir(parents=True, exist_ok=True)
    return d


class BookMonitor:
    """Read best bid/ask off the screen for symbols we hold or are about to trade."""

    def __init__(self, sessions=None):
        self.sessions = sessions
        self._last: dict[str, dict] = {}        # symbol -> {hash, read, ts}
        self.stats = {"ocr_reads": 0, "unchanged_skips": 0, "api_fallbacks": 0,
                      "ocr_rejected": 0}

    # ── the screen-mirror read ──────────────────────────────────────────────────
    def _ocr_book(self, symbol: str, market: str, lane: str) -> dict | None:
        """Screenshot the book area of the app page → OCR → best bid/ask candidates."""
        if self.sessions is None:
            return None
        app = REGISTRY.get(lane) or REGISTRY.get("binance" if market == "crypto" else "groww")
        if app is None or not (app.book_url or app.chart_url):
            return None
        url = (app.book_url or app.chart_url).format(symbol=symbol.split("/")[0],
                                                     interval="5")
        path = None
        try:
            pg = self.sessions.page(app.name, url)
            if pg is None:
                return None
            pg.wait_for_timeout(2500)
            path = str(_shot_dir() / f"{symbol.split('/')[0]}_{int(time.time())}.png")
            # right third of the viewport — where trade apps draw the book ladder
            pg.screenshot(path=path, clip={"x": 1060, "y": 80, "width": 540, "height": 700})
            pg.close()
            sha = hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]
            prev = self._last.get(symbol)
            if prev and prev["hash"] == sha:                 # saver G: unchanged ⇒ no OCR
                self.stats["unchanged_skips"] += 1
                return {**prev["read"], "unchanged": True}
            from trading.brain.gui.perception import OcrReader
            res = OcrReader().read_image(path, max_items=80)
            items = res.get("items", res) if isinstance(res, dict) else res
            nums = []
            for it in items or []:
                txt = it.get("text") if isinstance(it, dict) else str(it)
                for m in _NUM.finditer(txt or ""):
                    try:
                        nums.append(float(m.group(0).replace(",", "")))
                    except ValueError:
                        pass
            self.stats["ocr_reads"] += 1
            if len(nums) < 2:
                return None
            # the book ladder straddles the spread: best ask = smallest number just above
            # mid, best bid = largest just below — approximate with the two middle values
            # of the price-like cluster around the API mid (validated by the gate anyway)
            ref = data_failsafe.quote(symbol, market) or {}
            mid = ref.get("last")
            if mid:
                near = sorted(n for n in nums if 0.9 * mid <= n <= 1.1 * mid)
                if len(near) >= 2:
                    bids = [n for n in near if n <= mid]
                    asks = [n for n in near if n >= mid]
                    if bids and asks:
                        read = {"bid": max(bids), "ask": min(asks), "source": f"screen:{app.name}"}
                        self._last[symbol] = {"hash": sha, "read": read, "ts": time.time()}
                        return read
            return None
        except Exception:
            return None
        finally:
            if path and os.path.exists(path):               # owner's step 7: delete
                try:
                    os.remove(path)
                except OSError:
                    pass

    # ── public: gated read with API fail-safe (rule 4) ─────────────────────────
    def top_of_book(self, symbol: str, market: str, lane: str = "") -> dict:
        """Best bid/ask, screen-first, API-verified, API-backed. ALWAYS returns numbers
        when the API is reachable — a missing/inconsistent screen read never blocks."""
        api = data_failsafe.top_of_book(symbol, market) or {}
        scr = self._ocr_book(symbol, market, lane)
        if scr and api.get("bid") and api.get("ask"):
            ok = (data_failsafe.consistent(scr["bid"], api["bid"]) and
                  data_failsafe.consistent(scr["ask"], api["ask"]))
            if ok:
                out = {**scr, "consistent": True}
            else:                                            # misread digit → API wins
                self.stats["ocr_rejected"] += 1
                out = {**api, "consistent": False, "screen_rejected": scr}
        elif scr:
            out = {**scr, "consistent": None}                # no API reference to check
        else:
            self.stats["api_fallbacks"] += 1
            out = {**api, "consistent": None} if api else {"bid": None, "ask": None,
                                                           "source": "unavailable"}
        b, a = out.get("bid"), out.get("ask")
        out["spread_pct"] = round((a - b) / ((a + b) / 2) * 100, 4) if a and b else None
        return out
