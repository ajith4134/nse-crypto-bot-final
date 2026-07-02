"""trading/screener/commodities.py — MCX commodity FUTURES candidate generation.

MCX commodities trade as DATED FUTURES contracts (e.g. ``GOLD05AUG26FUT``,
``CRUDEOIL20JUL26FUT``), never as bare base symbols. Quoting/ordering a bare
``GOLD`` on MCX returns HTTP 400 "Symbol 'GOLD' not found" — which is exactly why
the commodities segment opened no trades.

This resolves each liquid commodity base name to the broker's EXACT near-month
tradable FUT symbol via the OpenAlgo ``search`` endpoint — the SAME mechanism the
options screener (trading/screener/options.py) uses for CE/PE, so there is no
fragile symbol-format guessing. Best-effort: returns [] if the broker is
unavailable / not logged in (caller falls back to the deterministic stub).

    contract flow:  search(base, exchange="MCX")  →  keep exact-base FUT rows  →
                    pick nearest expiry (near-month)  →  emit the broker's symbol
"""
from __future__ import annotations

from typing import Any, Optional

# Reuse the options screener's broker handle + expiry parser (no duplication).
from trading.screener.options import _broker, nearest_expiry

# Liquid MCX commodity underlyings (research: nse-commodities-mcx). Resolved to the
# near-month FUT contract at screen time. Ordered by typical liquidity/ATR appeal.
MCX_UNDERLYINGS = [
    "CRUDEOIL", "NATURALGAS", "GOLD", "SILVER", "COPPER", "ZINC",
    "CRUDEOILM", "GOLDM", "SILVERM", "ALUMINIUM", "LEAD", "NICKEL",
]


def _fut_rows(raw: Any) -> list[dict]:
    """Normalize OpenAlgo MCX search output → [{symbol, expiry}] for FUT rows only."""
    if isinstance(raw, dict):
        raw = raw.get("data", raw)
    if isinstance(raw, dict):
        raw = raw.get("data", [])
    rows: list[dict] = []
    for r in raw or []:
        if not isinstance(r, dict):
            continue
        itype = str(r.get("instrumenttype") or r.get("instrument_type") or "").upper()
        sym = str(r.get("symbol") or r.get("tradingsymbol") or "")
        if itype == "FUT" and sym:
            rows.append({"symbol": sym, "expiry": r.get("expiry")})
    return rows


def resolve_near_month_fut(client: Any, base: str, *, exchange: str = "MCX") -> Optional[dict]:
    """Base commodity (e.g. 'GOLD') → its near-month FUT row {symbol, expiry}, or None.

    Exact-base match: the char right after the base must be the expiry-day DIGIT, so a
    search for 'GOLD' never bleeds into GOLDM / GOLDPETAL / GOLDGUINEA contracts.
    """
    try:
        raw = client.search(query=base, exchange=exchange)
    except Exception:
        return None
    b = base.upper()
    rows = [
        r for r in _fut_rows(raw)
        if r["symbol"].upper().startswith(b)
        and len(r["symbol"]) > len(b)
        and r["symbol"][len(b)].isdigit()
    ]
    if not rows:
        return None
    exp = nearest_expiry([r.get("expiry") for r in rows])
    if exp is not None:
        for r in rows:
            if str(r.get("expiry")) == str(exp):
                return r
    return rows[0]


def screen_mcx_commodities(source: Any = None, *, limit: int = 5,
                           filters: dict | None = None) -> list[dict]:
    """Ranked near-month MCX commodity FUTURES candidates. Best-effort; [] on no broker."""
    from trading.screener.screener import _cand  # lazy: avoid import cycle

    client = _broker()
    if client is None:
        return []
    out: list[dict] = []
    for i, base in enumerate(MCX_UNDERLYINGS):
        if len(out) >= limit:
            break
        pick = resolve_near_month_fut(client, base)
        if not pick:
            continue
        score = round(0.9 - i * 0.03, 6)
        out.append(_cand(
            pick["symbol"], "commodities", "NSE", max(score, 0.1),
            f"MCX near-month FUT: {base} exp {pick.get('expiry')}",
            {"underlying": base, "expiry": pick.get("expiry")},
            "openalgo"))
    return out[:limit]
