"""trading/brain/gui/perception.py — the SEE layer of the computer-use agent.

Reads a dashboard the way a human reads it, in layers that degrade honestly:

  1. API read  (stdlib urllib, works TODAY) — fetch the same JSON the panels/charts draw,
     so the agent "sees" prices, regimes, open trades, P&L, kill-switch state, etc. This is
     the most reliable signal and needs no new dependency.
  2. HTML read (stdlib html.parser, works TODAY) — parse the served page to enumerate the
     interactive elements a user could press (buttons, links, inputs) by visible label, so
     the agent knows what controls exist.
  3. DOM read  (Playwright, activate-on-install) — open the live page, get a structured DOM
     with on-screen text + clickable nodes + bounding boxes (adapted from vendor/browser_use_src).
  4. Pixel read (PaddleOCR / vendor/omniparser, activate-on-install, OmniParser=GPU upgrade) —
     OCR a screenshot to read chart numbers/labels rendered as pixels.

ChartReader turns OHLCV candles (already served at /api/trading/candles) into the same plain
reading a trader gets from a chart: last price, trend, range, momentum — no pixels needed.

Every reader exposes an honest `available` flag; nothing here raises on a missing dep or a
dashboard that is down. Secrets-free.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser

# ── optional upgrade deps (honest, CHEAP capability detection) ────────────────────────────
# Use importlib.util.find_spec so we DON'T pay the (heavy) import cost just to report a flag —
# importing paddleocr eagerly added ~50s to process startup. The actual libs are imported lazily
# only when a reader is invoked.
import importlib.util as _ilu


def _has(mod: str) -> bool:
    try:
        return _ilu.find_spec(mod) is not None
    except (ImportError, ValueError):
        return False


_HAS_PLAYWRIGHT = _has("playwright")
# PaddleOCR is only usable WITH its inference engine (paddlepaddle / `paddle`). Reporting the
# flag True without the engine would be dishonest (real OCR would crash), so require BOTH.
_HAS_PADDLEOCR = _has("paddleocr") and _has("paddle")


def capabilities() -> dict:
    """Honest map of which perception layers are live in THIS environment."""
    return {"api": True, "html": True, "dom_playwright": _HAS_PLAYWRIGHT,
            "ocr_paddle": _HAS_PADDLEOCR,
            "ocr_omniparser": False,            # GPU upgrade slot (vendor/omniparser)
            "note": ("api+html read works today (stdlib); install playwright for DOM clicking "
                     "and paddleocr for chart-pixel OCR — see vendor/ for the vendored source")}


# ============================================================================ #
#  Low-level HTTP (stdlib) — read JSON + HTML without any new dependency         #
# ============================================================================ #
def _get(url: str, timeout: float = 4.0) -> tuple[int, str]:
    """GET url → (status, body_text). Never raises; returns (0, "") on failure."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "brain-gui-agent"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError, ValueError):
        return 0, ""


def _get_json(url: str, timeout: float = 4.0) -> dict | None:
    status, body = _get(url, timeout)
    if status != 200 or not body:
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


# ============================================================================ #
#  HTML element reader (stdlib) — enumerate pressable controls by label         #
# ============================================================================ #
class _ButtonHarvester(HTMLParser):
    """Collect button/link/input controls + their visible text (what a user could press)."""

    PRESSABLE = {"button", "a", "input", "select"}

    def __init__(self):
        super().__init__()
        self.elements: list[dict] = []
        self._stack: list[dict] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.PRESSABLE:
            a = dict(attrs)
            el = {"tag": tag, "text": "",
                  "id": a.get("id", ""), "name": a.get("name", ""),
                  "type": a.get("type", ""), "value": a.get("value", ""),
                  "aria": a.get("aria-label", ""), "href": a.get("href", "")}
            self.elements.append(el)
            self._stack.append(el)

    def handle_endtag(self, tag):
        if tag in self.PRESSABLE and self._stack:
            self._stack.pop()

    def handle_data(self, data):
        if self._stack:
            txt = data.strip()
            if txt:
                self._stack[-1]["text"] = (self._stack[-1]["text"] + " " + txt).strip()


def read_html_controls(url: str) -> list[dict]:
    """Parse a served page → list of pressable controls (label, id, type). Stdlib only."""
    status, body = _get(url)
    if status != 200 or not body:
        return []
    h = _ButtonHarvester()
    try:
        h.feed(body)
    except Exception:
        return []
    # keep only controls that have *some* identity (label/id/name/value)
    out = []
    for e in h.elements:
        label = e["text"] or e["aria"] or e["value"] or e["name"] or e["id"]
        if label:
            out.append({"label": label, **e})
    return out


# ============================================================================ #
#  ChartReader — read a candle chart the way a trader reads it (no pixels)       #
# ============================================================================ #
@dataclass
class ChartReading:
    symbol: str = ""
    market: str = ""
    timeframe: str = ""
    last: float = 0.0
    high: float = 0.0
    low: float = 0.0
    change_pct: float = 0.0          # close-to-close over the window
    trend: str = "flat"              # up | down | flat
    momentum: float = 0.0            # last close vs short SMA, normalized
    n: int = 0
    source: str = "api-candles"

    def to_dict(self) -> dict:
        return asdict(self)


class ChartReader:
    """Reads the chart from the data behind it (the candles the chart draws)."""

    def read_candles(self, candles: list[dict], symbol: str = "", market: str = "",
                     timeframe: str = "") -> ChartReading:
        closes = [float(c.get("close", 0.0)) for c in candles if c.get("close") is not None]
        highs = [float(c.get("high", 0.0)) for c in candles if c.get("high") is not None]
        lows = [float(c.get("low", 0.0)) for c in candles if c.get("low") is not None]
        if not closes:
            return ChartReading(symbol=symbol, market=market, timeframe=timeframe)
        last = closes[-1]
        first = closes[0]
        chg = ((last - first) / first * 100.0) if first else 0.0
        sma = sum(closes[-min(len(closes), 10):]) / min(len(closes), 10)
        mom = ((last - sma) / sma) if sma else 0.0
        trend = "up" if chg > 0.2 else "down" if chg < -0.2 else "flat"
        return ChartReading(symbol=symbol, market=market, timeframe=timeframe,
                            last=round(last, 6), high=round(max(highs or [last]), 6),
                            low=round(min(lows or [last]), 6), change_pct=round(chg, 4),
                            trend=trend, momentum=round(mom, 5), n=len(closes))


# ============================================================================ #
#  DomReader — Playwright: SEE the live (React-rendered) page like a human       #
# ============================================================================ #
class DomReader:
    """Opens the live page in headless chromium and reads the elements a USER actually sees —
    including React-rendered buttons a stdlib HTML parse can't (the SPA controls). Returns the
    visible interactive controls (+ a screenshot for the OCR layer). Adapted from the DOM
    approach in vendor/browser_use_src. Lazy + offline-safe: needs playwright (installed)."""

    def read(self, web_url: str, *, screenshot_path: str | None = None,
             timeout_ms: int = 15000) -> dict:
        if not _HAS_PLAYWRIGHT:
            return {"available": False, "reason": "playwright not installed", "controls": []}
        try:
            from playwright.sync_api import sync_playwright
            out = {"available": True, "controls": [], "title": "", "screenshot": None}
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width": 1600, "height": 1200})
                page.goto(web_url, timeout=timeout_ms, wait_until="networkidle")
                out["title"] = page.title()
                # every clickable/role-button/link/input the rendered app exposes
                handles = page.query_selector_all(
                    "button, a, [role=button], input, select, [onclick]")
                for h in handles[:200]:
                    try:
                        label = (h.inner_text() or h.get_attribute("aria-label")
                                 or h.get_attribute("value") or h.get_attribute("title") or "").strip()
                        if not label:
                            continue
                        box = h.bounding_box() or {}
                        out["controls"].append({
                            "label": label[:80], "tag": h.evaluate("e => e.tagName.toLowerCase()"),
                            "x": round(box.get("x", 0)), "y": round(box.get("y", 0)),
                            "visible": h.is_visible()})
                    except Exception:
                        continue
                if screenshot_path:
                    page.screenshot(path=screenshot_path, full_page=True)
                    out["screenshot"] = screenshot_path
                browser.close()
            return out
        except Exception as e:
            return {"available": False, "reason": f"{type(e).__name__}: {e}", "controls": []}


# ============================================================================ #
#  OcrReader — PaddleOCR: read chart pixels (numbers/labels) as text            #
# ============================================================================ #
class OcrReader:
    """Reads text/numbers rendered as PIXELS (chart axis labels, prices on a canvas the DOM
    can't expose) via PaddleOCR. Lazy: the (heavy) engine is built once on first use and only
    if both paddleocr + its paddle engine are installed. Honest off-flag otherwise."""

    _engine = None

    def _get_engine(self):
        if OcrReader._engine is None:
            # paddleocr 3.7 + paddlepaddle 3.3 crash in the oneDNN/PIR text-rec backend
            # (NotImplementedError ConvertPirAttribute2RuntimeAttribute). Disabling oneDNN is the
            # known root-cause fix; set the flag before the engine builds its predictor.
            import os
            os.environ.setdefault("FLAGS_use_mkldnn", "0")
            from paddleocr import PaddleOCR
            try:                                  # PaddleOCR 3.x signature (oneDNN off)
                OcrReader._engine = PaddleOCR(lang="en", use_textline_orientation=False,
                                              use_doc_orientation_classify=False,
                                              use_doc_unwarping=False, enable_mkldnn=False)
            except TypeError:
                try:                              # 3.x without the enable_mkldnn kw
                    OcrReader._engine = PaddleOCR(lang="en", use_textline_orientation=False,
                                                  use_doc_orientation_classify=False,
                                                  use_doc_unwarping=False)
                except TypeError:                 # PaddleOCR 2.x fallback
                    OcrReader._engine = PaddleOCR(lang="en", use_angle_cls=False)
        return OcrReader._engine

    @staticmethod
    def _extract_texts(res) -> list[str]:
        """Pull text strings out of either the 3.x (dict with rec_texts) or 2.x (nested list)
        PaddleOCR result shape."""
        texts: list[str] = []
        for item in (res or []):
            # 3.x: OCRResult behaves like a dict with 'rec_texts'
            rec = None
            if isinstance(item, dict):
                rec = item.get("rec_texts")
            elif hasattr(item, "get"):
                try:
                    rec = item.get("rec_texts")
                except Exception:
                    rec = None
            if rec:
                texts.extend(str(t) for t in rec)
                continue
            # 2.x: item is a list of [box, (text, score)]
            try:
                for line in item:
                    texts.append(str(line[1][0]))
            except (TypeError, IndexError):
                continue
        return texts

    def read_image(self, image_path: str, *, max_items: int = 80) -> dict:
        if not _HAS_PADDLEOCR:
            return {"available": False, "reason": "paddleocr+paddle engine not installed",
                    "texts": [], "numbers": []}
        try:
            engine = self._get_engine()
            res = engine.predict(image_path) if hasattr(engine, "predict") else engine.ocr(image_path)
            texts = self._extract_texts(res)
            numbers = []
            for txt in texts:
                cleaned = txt.replace(",", "").replace("$", "").replace("%", "").replace("₹", "").strip()
                try:
                    numbers.append(float(cleaned))
                except ValueError:
                    pass
            return {"available": True, "texts": texts[:max_items],
                    "numbers": numbers[:max_items], "n": len(texts)}
        except Exception as e:
            return {"available": False, "reason": f"{type(e).__name__}: {e}",
                    "texts": [], "numbers": []}


# ============================================================================ #
#  Perception — one structured "what I see right now" snapshot of a dashboard    #
# ============================================================================ #
@dataclass
class Perception:
    """Structured reading of a dashboard at one instant."""
    target: str
    reachable: bool = False
    panels: dict = field(default_factory=dict)        # endpoint key -> JSON the panel shows
    controls: list = field(default_factory=list)      # pressable elements (label,id,type)
    charts: list = field(default_factory=list)        # ChartReading dicts
    ocr: dict = field(default_factory=dict)           # pixel-OCR read (deep observe only)
    deep: bool = False                                # was a Playwright/OCR pass run?
    capabilities: dict = field(default_factory=dict)
    note: str = ""

    def to_dict(self) -> dict:
        return {"target": self.target, "reachable": self.reachable,
                "panels": self.panels, "n_controls": len(self.controls),
                "controls": self.controls[:40], "charts": self.charts,
                "ocr": self.ocr, "deep": self.deep,
                "capabilities": self.capabilities, "note": self.note}


class DashboardPerception:
    """The SEE layer: build a Perception of a DashboardTarget from all available readers."""

    # the panels worth reading on our OWN dashboard (subset of the live endpoints)
    OWN_PANELS = {
        "online": "/api/trading/online/status",
        "brain": "/api/trading/brain/status",
        "tickers": "/api/trading/tickers",
        "open_trades": "/api/trading/opentrades",
        "watchlist": "/api/trading/watchlist",
        "hypotheses": "/api/brain/hypotheses",
    }
    # Freqtrade/FreqUI honest read endpoints (api_server v1)
    FREQ_PANELS = {
        "ping": "/ping",
        "status": "/status",
        "profit": "/profit",
        "balance": "/balance",
    }

    def __init__(self):
        self.chart_reader = ChartReader()
        self.dom_reader = DomReader()
        self.ocr_reader = OcrReader()

    def see(self, target, *, read_charts: bool = True, deep: bool = False) -> Perception:
        """Read every available layer of `target` into one Perception. Never raises.

        deep=False (default, cheap) → API + stdlib HTML read, safe for a 5s status poll.
        deep=True  (Playwright + OCR) → also open the LIVE rendered page to see React-rendered
        controls and OCR the chart pixels. Slower (launches chromium); use on explicit observe.
        """
        caps = capabilities()
        p = Perception(target=target.name, capabilities=caps, deep=deep)
        panel_map = self.OWN_PANELS if target.kind == "own" else (
            self.FREQ_PANELS if target.kind == "freqtrade" else {})
        reachable = False
        for key, sub in panel_map.items():
            j = _get_json(f"{target.api_base}{sub}")
            if j is not None:
                reachable = True
                p.panels[key] = j
        p.reachable = reachable
        # enumerate pressable controls from the served page (stdlib HTML parse)
        if target.can_dom:
            p.controls = read_html_controls(target.web_url)
        # read the chart the way a trader does (own dashboard candles endpoint)
        if read_charts and target.kind == "own":
            cj = _get_json(f"{target.api_base}/api/trading/candles"
                           "?symbol=BTC/USDT&market=CRYPTO&tf=5m")
            if cj and cj.get("candles"):
                r = self.chart_reader.read_candles(cj["candles"], cj.get("symbol", "BTC/USDT"),
                                                   cj.get("market", "CRYPTO"), cj.get("tf", "5m"))
                p.charts.append(r.to_dict())
        # DEEP pass: open the live rendered page (Playwright) → real controls + screenshot, then
        # OCR the screenshot (PaddleOCR) → chart-pixel numbers. Only when asked + deps present.
        if deep and target.can_dom and caps["dom_playwright"]:
            import os
            import tempfile
            shot = os.path.join(tempfile.gettempdir(), f"gui_{target.name}.png")
            dom = self.dom_reader.read(target.web_url, screenshot_path=shot)
            if dom.get("available") and dom.get("controls"):
                p.controls = dom["controls"]              # real rendered controls (incl. React)
            if dom.get("screenshot") and caps["ocr_paddle"]:
                p.ocr = self.ocr_reader.read_image(dom["screenshot"])
        p.note = ("read via api+html (stdlib)%s. reachable=%s." % (
            " + deep DOM/OCR" if (deep and caps["dom_playwright"]) else "", reachable))
        return p
