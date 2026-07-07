"""trading/broker_sense/trade_columns.py — turn the App Driving School's discovered app labels
into GENUINE trade-table column proposals.

The raw discovery (learning_columns.discover_from_text) captures every "<label> <number>" on a
page, so it is full of noise (ticker names, regions, months, marketing copy). This module distils
that into REAL, trade-relevant data fields the broker apps expose that the trade journal does NOT
already store — so the owner sees only honest, additive column candidates for the open/closed
trades tables. No scraping here; it reads the persisted discovery + the live journal schema."""
from __future__ import annotations

import re

from trading import state

# canonical trade-data concepts the broker apps surface → (clean column, meaning, applies-to).
# label-regex matches the discovered app label (case-insensitive). Only these are ever proposed,
# so marketing/ticker noise can never become a column.
_CONCEPTS = [
    (r"\bmark\s*price\b", "mark_price", "Perp mark price (funding/liquidation ref)", "crypto"),
    (r"\bindex\s*price\b", "index_price", "Spot index price behind the perp", "crypto"),
    (r"\bbasis\b", "basis", "Futures−spot basis (contango/backwardation)", "crypto"),
    (r"funding\s*interval|fundinginterval", "funding_interval_hours", "Hours between funding payments", "crypto"),
    (r"next\s*funding|funding\s*countdown", "next_funding_time", "Time to next funding", "crypto"),
    (r"open\s*interest\s*value|oi\s*value|oi\s*\(usd", "open_interest_value_usd", "OI in USD (not just contracts)", "both"),
    (r"top\s*trader.*ratio|toplongshort", "top_trader_long_short_ratio", "Top-trader long/short ratio", "crypto"),
    (r"taker\s*(buy|sell)|taker\s*ratio", "taker_buy_sell_ratio", "Aggressor buy vs sell volume", "crypto"),
    (r"estimated\s*leverage|elr\b", "estimated_leverage_ratio", "Market-wide estimated leverage", "crypto"),
    (r"insurance\s*fund", "insurance_fund", "Exchange insurance-fund size", "crypto"),
    (r"\b24h?\s*turnover|turnover\b", "turnover_24h", "24h traded value", "both"),
    (r"\b24h?\s*high|day\s*high|\bhigh\b", "high_24h", "24h / day high", "both"),
    (r"\b24h?\s*low|day\s*low|\blow\b", "low_24h", "24h / day low", "both"),
    (r"52\s*w(eek)?\s*high", "week52_high", "52-week high", "nse"),
    (r"52\s*w(eek)?\s*low", "week52_low", "52-week low", "nse"),
    (r"\bvwap\b", "vwap", "Volume-weighted average price", "both"),
    (r"deliver(y|able)\s*(%|per|qty)|delivery", "delivery_pct", "Delivery % (real buying vs intraday)", "nse"),
    (r"circuit|upper\s*limit|lower\s*limit|price\s*band", "circuit_limits", "Upper/lower circuit band", "nse"),
    (r"\bpcr\b|put\s*call\s*ratio", "put_call_ratio", "Put/call ratio (options sentiment)", "nse"),
    (r"max\s*pain", "max_pain", "Option max-pain strike", "nse"),
    (r"oi\s*build\s*up|buildup|long\s*build|short\s*build", "oi_buildup", "Long/short buildup classification", "both"),
    (r"total\s*buy\s*q|total\s*sell\s*q|buy\s*qty|sell\s*qty", "total_buy_sell_qty", "Total pending buy vs sell qty", "nse"),
    (r"bid\s*ask\s*spread|spread\b", "quoted_spread", "Live quoted bid/ask spread", "both"),
    (r"implied\s*vol|\biv\b", "iv_live", "Live implied volatility", "nse"),
]


def _norm(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (label or "").strip().lower()).strip("_")


def journal_fields() -> set:
    """Fields a trade already stores — so we never re-propose something already tracked."""
    try:
        d = state.load_json("journal.json", [])
        rows = d if isinstance(d, list) else (d.get("trades") or d.get("rows") or [])
        have = set()
        for r in rows[-50:]:
            if isinstance(r, dict):
                have |= {k.lower() for k in r}
        return have
    except Exception:
        return set()


def discovered_labels() -> list:
    """Every label the App Driving School captured across the broker apps (may be noisy)."""
    try:
        cols = state.load_json("broker_sense_columns.json", {}).get("columns", {})
        return [(c.get("label") or k, c.get("source", "")) for k, c in cols.items()]
    except Exception:
        return []


def propose() -> dict:
    """Distil discovered app labels → genuine NEW trade-table columns (cross-checked vs journal).
    Returns {proposals:[{column, meaning, applies_to, seen_as, sources}], covered:[...]}."""
    have = journal_fields()
    labels = discovered_labels()
    hits: dict = {}
    for concept_re, col, meaning, applies in _CONCEPTS:
        rx = re.compile(concept_re, re.I)
        seen = sorted({lab for lab, _src in labels if rx.search(lab or "")})
        if not seen:
            continue
        srcs = sorted({src for lab, src in labels if rx.search(lab or "") and src})
        already = col in have or f"{col}_entry" in have or _norm(col) in have
        hits[col] = {"column": col, "meaning": meaning, "applies_to": applies,
                     "seen_as": seen[:4], "sources": srcs, "already_tracked": already}
    proposals = [h for h in hits.values() if not h["already_tracked"]]
    covered = [h["column"] for h in hits.values() if h["already_tracked"]]
    return {"proposals": sorted(proposals, key=lambda h: h["column"]),
            "already_tracked": sorted(covered),
            "n_labels_scanned": len(labels)}


_ACCEPTED_FILE = "trade_columns_accepted.json"


def accepted() -> list:
    """Columns the owner has ACCEPTED into the trade tables (persisted)."""
    return state.load_json(_ACCEPTED_FILE, {}).get("columns", [])


def accept(column: str) -> dict:
    """Accept a proposed column → it joins the accepted set (surfaced in the trades tables as an
    extra dynamic column). Idempotent. Real fields already in the journal schema are populated at
    ingest; accepted-but-not-schema columns show from the discovered per-symbol values."""
    d = state.load_json(_ACCEPTED_FILE, {})
    cols = d.setdefault("columns", [])
    col = column.strip().lower().replace(" ", "_")
    if col and col not in cols:
        cols.append(col)
        state.save_json(_ACCEPTED_FILE, d)
    return {"accepted": cols}


def reject(column: str) -> dict:
    d = state.load_json(_ACCEPTED_FILE, {})
    cols = [c for c in d.get("columns", []) if c != column.strip().lower().replace(" ", "_")]
    d["columns"] = cols
    state.save_json(_ACCEPTED_FILE, d)
    return {"accepted": cols}


if __name__ == "__main__":
    import json
    print(json.dumps(propose(), indent=2, default=str))
