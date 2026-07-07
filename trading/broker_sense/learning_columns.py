"""trading/broker_sense/learning_columns.py — discovered app data → DYNAMIC learning columns.

Owner decision #6: "if the brain finds additional new data from the web trading apps, add
them as learning column data". Broker apps show labelled numbers our schema never planned
for (Delivery %, OI change, analyst rating, funding rate, long/short ratio, technical-gauge
score…). This registry:

  1. DISCOVERS them — `discover_from_text` mines any page text / OCR dump for
     "<label> <number>" pairs and registers each new label as a column (per source app);
  2. SNAPSHOTS them — `snapshot(symbol)` returns the latest values, which the funnel puts
     into decision_snapshot["app_signals"] at entry time (entry_meta), so freqtrade_ingest
     merges them into the ClosedTrade → journal → TradeOutcomeNet learning, with NO schema
     migration (decision_snapshot is already a JSON column);
  3. reports honestly — the dashboard shows exactly which columns exist, where each was
     discovered, and how often it's been seen.
"""
from __future__ import annotations

import re
import time

from trading import state

_FILE = "broker_sense_columns.json"
# "<Label words> 12,345.67 %" — labels 3..28 chars, value with optional %, ×, Cr, K/M/B suffix
_PAIR = re.compile(r"([A-Za-z][A-Za-z /%&\-]{2,28}?)\s*[:\-]?\s*"
                   r"(-?\d[\d,]*\.?\d*)\s*(%|x|Cr|L|K|M|B)?(?=\s|$)", re.M)
_STOP = {"open", "high", "low", "close", "price", "qty", "quantity", "total", "change",
         "volume"}                       # already first-class columns — not "new" discoveries
_MAX_COLS = 400


def _norm(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", label.strip().lower()).strip("_")[:40]


class ColumnRegistry:
    """Persistent registry of discovered columns + latest per-symbol values."""

    def __init__(self):
        d = state.load_json(_FILE, {})
        self.columns: dict = d.get("columns", {})     # name -> {source, first_seen, n_seen, label}
        self.values: dict = d.get("values", {})       # symbol -> {name: value}

    def _save(self) -> None:
        state.save_json(_FILE, {"columns": self.columns, "values": self.values})

    def register(self, name: str, *, source: str, label: str) -> bool:
        """Register a discovered column; True when it's NEW (first time any app showed it)."""
        new = name not in self.columns
        if new and len(self.columns) >= _MAX_COLS:
            return False
        c = self.columns.setdefault(name, {"source": source, "label": label,
                                           "first_seen": time.time(), "n_seen": 0})
        c["n_seen"] += 1
        return new

    def observe(self, symbol: str, name: str, value: float) -> None:
        self.values.setdefault(symbol, {})[name] = value
        self.values[symbol]["_ts"] = time.time()

    def snapshot(self, symbol: str) -> dict:
        """Latest discovered values for `symbol` → decision_snapshot['app_signals']."""
        return dict(self.values.get(symbol) or {})

    def status(self) -> dict:
        top = sorted(self.columns.items(), key=lambda kv: -kv[1]["n_seen"])[:40]
        return {"n_columns": len(self.columns),
                "n_symbols_tracked": len(self.values),
                "columns": [{"name": n, **c} for n, c in top]}


_REG: ColumnRegistry | None = None


def get_registry() -> ColumnRegistry:
    global _REG
    if _REG is None:
        _REG = ColumnRegistry()
    return _REG


def discover_from_text(source: str, text: str, *, symbol: str | None = None,
                       max_pairs: int = 60) -> list[str]:
    """Mine page/OCR text for labelled numbers; register each as a column and (when a
    symbol is in scope) record its value. Returns the NEWLY discovered column names."""
    reg = get_registry()
    fresh: list[str] = []
    for m in _PAIR.finditer(text or ""):
        label, raw, unit = m.group(1).strip(), m.group(2), m.group(3) or ""
        name = _norm(label)
        if not name or name in _STOP or name.isdigit() or len(name) < 3:
            continue
        try:
            val = float(raw.replace(",", ""))
        except ValueError:
            continue
        if reg.register(name + (f"_{unit.lower()}" if unit in ("%", "x") else ""),
                        source=source, label=label):
            fresh.append(name)
        if symbol is not None:
            reg.observe(symbol, name + (f"_{unit.lower()}" if unit in ("%", "x") else ""), val)
        if len(fresh) >= max_pairs:
            break
    if fresh:
        reg._save()
        try:
            from trading.brain import mind_events
            mind_events.emit("discovery",
                             f"Found {len(fresh)} NEW data column(s) on {source}: "
                             f"{', '.join(fresh[:5])} — added to my learning columns",
                             salience=0.7, data={"source": source, "columns": fresh[:20]})
        except Exception:
            pass
    else:
        reg._save()
    return fresh
