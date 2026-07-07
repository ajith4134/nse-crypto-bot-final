"""trading/screener/universe.py — the LIQUID, tradeable NSE equity universe.

Root-cause (2026-07-07): the intraday screener fed off nselib's movers feed
(`most_active_equities` / `top_gainers_or_losers`), which is IP-blocked from the
VM and, when it does answer, surfaces illiquid micro-caps (ZSARACOM ₹12,404,
KAUSHALYA, TARC…). Those are not the "500+ liquid stocks" the owner wants to
trade intraday, and the brain rightly abstains on them (calibrated p_up ≈ 0.24).

Fix: rank a REAL, liquid universe — the NSE F&O stock list (the ~190 most liquid
single-stock names, all with tight spreads + no circuit surprises) — by LIVE
momentum read from OpenAlgo quotes (reliable, already used for execution). This
is the correct intraday universe: every name is deeply liquid and F&O-eligible.

Offline-safe: the constant list needs no network; ranking degrades to the raw
list order when OpenAlgo is unreachable.
"""
from __future__ import annotations

from typing import Any

# NSE F&O single-stock underlyings (SEBI F&O list) — the liquid, intraday-tradeable
# equity universe. Curated from the exchange's derivatives-eligible securities; these
# are the deepest-liquidity NSE cash names (large + liquid mid caps). Indices are
# handled by the options screener, so they are intentionally NOT here.
NSE_FO_STOCKS: tuple[str, ...] = (
    "AARTIIND", "ABB", "ABBOTINDIA", "ABCAPITAL", "ABFRL", "ACC", "ADANIENT",
    "ADANIPORTS", "ALKEM", "AMBUJACEM", "ANGELONE", "APLAPOLLO", "APOLLOHOSP",
    "APOLLOTYRE", "ASHOKLEY", "ASIANPAINT", "ASTRAL", "ATUL", "AUBANK", "AUROPHARMA",
    "AXISBANK", "BAJAJ-AUTO", "BAJAJFINSV", "BAJFINANCE", "BALKRISIND", "BANDHANBNK",
    "BANKBARODA", "BANKINDIA", "BATAINDIA", "BEL", "BERGEPAINT", "BHARATFORG",
    "BHARTIARTL", "BHEL", "BIOCON", "BOSCHLTD", "BPCL", "BRITANNIA", "BSOFT",
    "CANBK", "CANFINHOME", "CGPOWER", "CHAMBLFERT", "CHOLAFIN", "CIPLA", "COALINDIA",
    "COFORGE", "COLPAL", "CONCOR", "COROMANDEL", "CROMPTON", "CUB", "CUMMINSIND",
    "DABUR", "DALBHARAT", "DEEPAKNTR", "DELHIVERY", "DIVISLAB", "DIXON", "DLF",
    "DMART", "DRREDDY", "EICHERMOT", "ESCORTS", "EXIDEIND", "FEDERALBNK", "GAIL",
    "GLENMARK", "GMRAIRPORT", "GNFC", "GODREJCP", "GODREJPROP", "GRANULES",
    "GRASIM", "GUJGASLTD", "HAL", "HAVELLS", "HCLTECH", "HDFCAMC", "HDFCBANK",
    "HDFCLIFE", "HEROMOTOCO", "HINDALCO", "HINDCOPPER", "HINDPETRO", "HINDUNILVR",
    "ICICIBANK", "ICICIGI", "ICICIPRULI", "IDEA", "IDFCFIRSTB", "IEX", "IGL",
    "INDHOTEL", "INDIAMART", "INDIGO", "INDUSINDBK", "INDUSTOWER", "INFY", "IOC",
    "IPCALAB", "IRCTC", "IRFC", "ITC", "JINDALSTEL", "JIOFIN", "JKCEMENT",
    "JSWENERGY", "JSWSTEEL", "JUBLFOOD", "KOTAKBANK", "LALPATHLAB", "LAURUSLABS",
    "LICHOUSING", "LICI", "LT", "LTF", "LTIM", "LUPIN", "M&M", "M&MFIN", "MANAPPURAM",
    "MARICO", "MARUTI", "MAXHEALTH", "MCX", "METROPOLIS", "MFSL", "MGL", "MOTHERSON",
    "MPHASIS", "MRF", "MUTHOOTFIN", "NATIONALUM", "NAUKRI", "NAVINFLUOR", "NESTLEIND",
    "NHPC", "NMDC", "NTPC", "NYKAA", "OBEROIRLTY", "OFSS", "ONGC", "PAGEIND",
    "PAYTM", "PEL", "PERSISTENT", "PETRONET", "PFC", "PIDILITIND", "PIIND", "PNB",
    "POLYCAB", "POONAWALLA", "POWERGRID", "PRESTIGE", "PVRINOX", "RAMCOCEM", "RBLBANK",
    "RECLTD", "RELIANCE", "SAIL", "SBICARD", "SBILIFE", "SBIN", "SHREECEM",
    "SHRIRAMFIN", "SIEMENS", "SONACOMS", "SRF", "SUNPHARMA", "SUNTV", "SYNGENE",
    "TATACHEM", "TATACOMM", "TATACONSUM", "TATAMOTORS", "TATAPOWER", "TATASTEEL",
    "TCS", "TECHM", "TIINDIA", "TITAN", "TORNTPHARM", "TORNTPOWER", "TRENT", "TVSMOTOR",
    "UBL", "ULTRACEMCO", "UNIONBANK", "UNITDSPR", "UPL", "VBL", "VEDL", "VOLTAS",
    "WIPRO", "ZOMATO", "ZYDUSLIFE",
)

_FO_SET = frozenset(NSE_FO_STOCKS)


def is_liquid(symbol: str) -> bool:
    """True if `symbol` is in the liquid NSE F&O equity universe."""
    return str(symbol or "").upper() in _FO_SET


def liquid_movers(oa_quote: Any, *, limit: int = 60,
                  universe: tuple[str, ...] = NSE_FO_STOCKS) -> list[dict]:
    """Rank the liquid universe by LIVE intraday momentum via `oa_quote(sym, "NSE")`.

    `oa_quote` is a callable returning OpenAlgo's quote dict for (symbol, exchange).
    Returns [{symbol, ltp, pct_change, volume, tags}] sorted by |pct_change| desc.
    Names that fail to quote are skipped. Degrades to the raw list on total failure.
    """
    out: list[dict] = []
    for sym in universe:
        try:
            q = oa_quote(sym, "NSE")
        except Exception:
            q = None
        d = (q.get("data", q) if isinstance(q, dict) else {}) or {}
        try:
            ltp = float(d.get("ltp") or d.get("last_price") or 0) or 0.0
            prev = float(d.get("prev_close") or 0) or 0.0
            vol = float(d.get("volume") or 0) or 0.0
        except (TypeError, ValueError):
            continue
        if ltp <= 0:
            continue
        pct = ((ltp - prev) / prev * 100.0) if prev > 0 else 0.0
        out.append({"symbol": sym, "ltp": ltp, "pct_change": round(pct, 3),
                    "volume": vol, "tags": ["liquid"]})
    if not out:  # OpenAlgo unreachable → keep the universe (raw order) so we never
        return [{"symbol": s, "pct_change": 0.0, "tags": ["liquid"]}   # go empty.
                for s in universe[:limit]]
    out.sort(key=lambda r: abs(r["pct_change"]), reverse=True)
    return out[:limit]
