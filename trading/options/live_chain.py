"""trading/options/live_chain.py — REAL NFO/BFO option chain → T4 analytics (2026-07-10).

Replaces the last demo tile: builds the same `OptionsChain` object the T4 analytics run
on (Greeks/IV solved from LTP, max pain, PCR, GEX, OI walls) from the BROKER'S live
chain via OpenAlgo `optionchain` (zero-cost — our own OpenAlgo server; nselib's public
chain endpoint is IP-blocked from this VM, see trading/screener/options.py).

Flow per underlying:
    search NFO/BFO → nearest expiry (DD-MMM-YY → compact DDMMMYY the API requires) →
    optionchain(underlying, exchange, expiry) → OptionQuote rows (iv=None → solved
    from ltp) → OptionsChain(forward from ATM put-call parity, else spot·e^{rT})

Every successful fetch is cached to trading/state/options_chain_live.json so the tile
keeps serving the last REAL chain (honest `as_of` timestamp) when the broker session is
down or the market is closed; the synthetic demo remains only for a never-fetched box.
"""
from __future__ import annotations

import datetime as _dt
import math
import time

from trading.options.chain import OptionQuote, OptionsChain

_STATE_FILE = "options_chain_live.json"
_RATE = 0.065                      # same default short rate as the rest of T4
# spot-quote exchange + option exchange per index underlying (mirrors screener/options.py)
_EXCHANGES = {
    "NIFTY": ("NSE_INDEX", "NFO"), "BANKNIFTY": ("NSE_INDEX", "NFO"),
    "FINNIFTY": ("NSE_INDEX", "NFO"), "MIDCPNIFTY": ("NSE_INDEX", "NFO"),
    "SENSEX": ("BSE_INDEX", "BFO"), "BANKEX": ("BSE_INDEX", "BFO"),
}


def _nearest_expiry(cli, underlying: str, opt_exchange: str) -> tuple[str, _dt.date] | None:
    """Nearest option expiry from broker search rows: ('14JUL26', date(2026,7,14))."""
    s = cli._client().search(query=underlying, exchange=opt_exchange)
    rows = [r for r in (s.get("data") or [])
            if r.get("instrumenttype") in ("CE", "PE") and r.get("name") == underlying]
    dates = []
    for r in rows:
        try:
            dates.append(_dt.datetime.strptime(str(r.get("expiry")), "%d-%b-%y").date())
        except ValueError:
            continue
    today = _dt.date.today()
    future = sorted(d for d in set(dates) if d >= today)
    if not future:
        return None
    d = future[0]
    return d.strftime("%d%b%y").upper(), d


def fetch_raw_chain(underlying: str = "NIFTY", strike_count: int = 15) -> dict | None:
    """One real broker chain fetch → plain dict (persisted); None when unavailable."""
    from trading import state
    from trading.openalgo_client import OpenAlgoClient
    try:
        spot_ex, opt_ex = _EXCHANGES.get(underlying.upper(), ("NSE", "NFO"))
        cli = OpenAlgoClient()
        exp = _nearest_expiry(cli, underlying.upper(), opt_ex)
        if not exp:
            return None
        expiry_compact, expiry_date = exp
        r = cli._client().optionchain(underlying=underlying.upper(), exchange=spot_ex,
                                      expiry_date=expiry_compact,
                                      strike_count=strike_count)
        if r.get("status") != "success" or not r.get("chain"):
            return None
        raw = {"ts": time.time(), "underlying": underlying.upper(),
               "expiry": expiry_compact, "expiry_iso": expiry_date.isoformat(),
               "spot": r.get("underlying_ltp"), "atm_strike": r.get("atm_strike"),
               "chain": r["chain"]}
        cache = state.load_json(_STATE_FILE, {}) or {}
        cache[underlying.upper()] = raw
        state.save_json(_STATE_FILE, cache)
        return raw
    except Exception:
        return None


def cached_raw_chain(underlying: str = "NIFTY") -> dict | None:
    from trading import state
    return (state.load_json(_STATE_FILE, {}) or {}).get(underlying.upper())


def to_chain(raw: dict) -> OptionsChain:
    """Real broker rows → the T4 OptionsChain (IVs solved from LTP downstream)."""
    spot = float(raw.get("spot") or 0.0)
    expiry_date = _dt.date.fromisoformat(raw["expiry_iso"])
    # time to expiry in years; expiry day itself still gets half a trading day
    t = max((expiry_date - _dt.date.today()).days, 0.5) / 365.0
    quotes: list[OptionQuote] = []
    lot = 1
    for row in raw.get("chain") or []:
        strike = float(row.get("strike") or 0.0)
        if strike <= 0:
            continue
        for side in ("ce", "pe"):
            q = row.get(side) or {}
            if not q:
                continue
            lot = int(q.get("lotsize") or lot)
            quotes.append(OptionQuote(strike=strike, opt_type=side.upper(),
                                      expiry=raw.get("expiry", ""),
                                      oi=float(q.get("oi") or 0.0),
                                      volume=float(q.get("volume") or 0.0),
                                      ltp=float(q.get("ltp") or 0.0)))
    if not quotes or spot <= 0:
        raise ValueError(f"chain for {raw.get('underlying')} has no usable quotes/spot")
    # forward: ATM put-call parity F = K + (C−P)·e^{rT} when both legs traded, else carry
    forward = spot * math.exp(_RATE * t)
    atm = raw.get("atm_strike")
    if atm:
        row = next((x for x in raw["chain"] if float(x.get("strike") or 0) == float(atm)), None)
        if row:
            c_ltp = float((row.get("ce") or {}).get("ltp") or 0.0)
            p_ltp = float((row.get("pe") or {}).get("ltp") or 0.0)
            if c_ltp > 0 and p_ltp > 0:
                forward = float(atm) + (c_ltp - p_ltp) * math.exp(_RATE * t)
    return OptionsChain(quotes, forward=forward, t=t, r=_RATE, spot=spot, lot_size=lot)


def live_status(underlying: str = "NIFTY", max_age_sec: float = 300.0) -> dict | None:
    """T4 status() off the REAL chain — fetches when stale, else serves the cached real
    chain with an honest as_of. None only when no real chain has EVER been fetched."""
    raw = cached_raw_chain(underlying)
    if raw is None or (time.time() - float(raw.get("ts") or 0)) > max_age_sec:
        raw = fetch_raw_chain(underlying) or raw
    if raw is None:
        return None
    try:
        snap = to_chain(raw).status()
    except (ValueError, KeyError) as e:
        return {"available": False, "underlying": raw.get("underlying"),
                "error": f"{type(e).__name__}: {e}"}
    snap.update({"demo": False, "live": True, "underlying": raw.get("underlying"),
                 "expiry": raw.get("expiry"), "as_of": raw.get("ts"),
                 "as_of_age_sec": round(time.time() - float(raw.get("ts") or 0), 1),
                 "note": "REAL broker option chain via OpenAlgo optionchain "
                         "(IV/Greeks solved from live premiums)"})
    return snap
