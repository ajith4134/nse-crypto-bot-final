"""trading/screener/options.py — single-leg NSE option (CE/PE) candidate generation.

Sources contracts from OpenAlgo/Zerodha (the broker we already route NSE orders
through) because nselib's live option-chain endpoint is IP-blocked from the server
(`nse_live_option_chain` → KeyError 'records'). Per underlying the flow is:

    broker LTP  →  ATM strike (nearest listed)  →  nearest expiry  →
    pick ATM/OTM CE&PE per `option_mode`  →  emit the broker's EXACT tradable symbol

Symbols are taken verbatim from the broker `search` rows (no fragile format
guessing). `option_mode`: 'atm' (ATM CE+PE), 'ladder' (ATM + N OTM each side),
'chain' (whole nearest-expiry chain, capped — let the brain×backtest scorer pick).

The pure helpers (atm_strike / nearest_expiry / pick_contracts) are unit-tested with
mocked rows; the live wiring is best-effort and returns [] (never raises) when the
broker session/data is unavailable, so the loop degrades gracefully.
"""
from __future__ import annotations

from typing import Any, Callable, Iterable, Optional

# Index underlyings always screened for options; stock underlyings are added from
# the live most-active F&O list (ranked by option volume).
INDEX_UNDERLYINGS = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]
_INDEX_SET = {u.upper() for u in INDEX_UNDERLYINGS}
_MODES = ("atm", "ladder", "chain")


# ── pure helpers (unit-tested, no I/O) ───────────────────────────────────────
def atm_strike(ltp: float, strikes: Iterable[float]) -> Optional[float]:
    """Nearest LISTED strike to the underlying LTP (robust to per-underlying steps)."""
    ss = sorted({float(s) for s in strikes if s})
    if not ss or not ltp:
        return None
    return min(ss, key=lambda s: abs(s - float(ltp)))


def _strike_step(strikes: list[float]) -> float:
    """Infer the strike step from the smallest gap between consecutive listed strikes."""
    ss = sorted({float(s) for s in strikes if s})
    gaps = [b - a for a, b in zip(ss, ss[1:]) if b > a]
    return min(gaps) if gaps else 0.0


def nearest_expiry(expiries: Iterable[str]) -> Optional[str]:
    """Earliest expiry by lexical date parse; falls back to first if unparseable."""
    exps = [e for e in {str(x) for x in expiries if x}]
    if not exps:
        return None
    from datetime import datetime

    def _key(e: str):
        for fmt in ("%d-%b-%Y", "%d%b%Y", "%d-%b-%y", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                return datetime.strptime(e, fmt)
            except ValueError:
                continue
        return datetime.max  # unparseable → sort last

    return sorted(exps, key=_key)[0]


def pick_contracts(rows: list[dict], ltp: float, mode: str = "atm",
                   otm_depth: int = 2, chain_cap: int = 12) -> list[dict]:
    """From normalized option rows [{symbol,strike,expiry,opt_type}], pick contracts
    at the NEAREST expiry per `mode`. Returns the chosen rows (subset of input)."""
    mode = (mode or "atm").lower()
    if mode not in _MODES:
        mode = "atm"
    rows = [r for r in rows if r.get("symbol") and r.get("opt_type") in ("CE", "PE") and r.get("strike")]
    if not rows:
        return []
    exp = nearest_expiry([r.get("expiry") for r in rows])
    near = [r for r in rows if str(r.get("expiry")) == str(exp)] if exp else rows
    strikes = [float(r["strike"]) for r in near]
    atm = atm_strike(ltp, strikes)
    if atm is None:
        return []
    if mode == "chain":
        # whole nearest-expiry chain, capped around ATM (closest strikes first)
        near.sort(key=lambda r: abs(float(r["strike"]) - atm))
        return near[:chain_cap]
    step = _strike_step(strikes) or 1.0
    if mode == "atm":
        wanted = {atm}
    else:  # ladder: ATM + N OTM each side (CE above, PE below handled by opt_type)
        wanted = {atm + i * step for i in range(otm_depth + 1)}
        wanted |= {atm - i * step for i in range(otm_depth + 1)}
    out = [r for r in near if float(r["strike"]) in wanted]
    # keep both CE and PE, closest strikes first
    out.sort(key=lambda r: (abs(float(r["strike"]) - atm), r["opt_type"]))
    return out


# ── broker adapters (best-effort, isolated for mocking) ──────────────────────
def _norm_rows(raw: Any) -> list[dict]:
    """Normalize OpenAlgo search output → [{symbol,strike,expiry,opt_type}]."""
    if raw is None:
        return []
    data = raw.get("data", raw) if isinstance(raw, dict) else raw
    rows = []
    for r in (data or []):
        if not isinstance(r, dict):
            continue
        itype = str(r.get("instrumenttype") or r.get("instrument_type") or "").upper()
        sym = str(r.get("symbol") or r.get("tradingsymbol") or "")
        if itype not in ("CE", "PE"):
            # derive from symbol suffix ONLY when preceded by a digit (the strike),
            # so equity names like "RELIANCE" (ends 'CE') are never misclassified.
            if len(sym) > 2 and sym[-2:] in ("CE", "PE") and sym[-3].isdigit():
                itype = sym[-2:]
            else:
                continue
        try:
            strike = float(r.get("strike") or r.get("strike_price") or 0)
        except (TypeError, ValueError):
            strike = 0.0
        rows.append({"symbol": sym, "strike": strike,
                     "expiry": r.get("expiry") or r.get("expiry_date") or "",
                     "opt_type": itype})
    return rows


def _broker():
    """Lazy OpenAlgo client (raw SDK) — None if unavailable."""
    try:
        from trading.openalgo_client import OpenAlgoClient
        return OpenAlgoClient()._client()
    except Exception:
        return None


def _ltp(client: Any, underlying: str) -> float:
    exch = "NSE_INDEX" if underlying.upper() in _INDEX_SET else "NSE"
    try:
        r = client.get_ltp(exchange=exch, symbol=underlying)
        d = r.get("data", r) if isinstance(r, dict) else {}
        return float(d.get("ltp") or d.get("last_price") or 0) if isinstance(d, dict) else 0.0
    except Exception:
        return 0.0


def _search_options(client: Any, underlying: str) -> list[dict]:
    try:
        return _norm_rows(client.search(query=underlying, exchange="NFO"))
    except Exception:
        return []


# ── entry point (wired into screener._live for NSE 'options') ────────────────
def screen_nse_options(source: Any, *, limit: int = 5, filters: dict | None = None) -> list[dict]:
    """Generate single-leg NSE option (CE/PE) candidates. Best-effort; [] on no data."""
    from trading.screener.screener import _cand  # lazy: avoid import cycle

    mode = str((filters or {}).get("option_mode", "atm")).lower()
    client = _broker()
    if client is None:
        return []

    # Universe: index underlyings + top-liquid F&O stock underlyings (by option volume).
    underlyings: list[str] = list(INDEX_UNDERLYINGS[:2])  # NIFTY, BANKNIFTY
    try:
        au = source.active_underlying() or [] if source is not None else []
        au.sort(key=lambda r: float(r.get("optVolume") or r.get("totVolume") or 0), reverse=True)
        for r in au:
            u = str(r.get("symbol") or r.get("underlying") or "").upper()
            if u and u not in _INDEX_SET and u not in underlyings:
                underlyings.append(u)
            if len(underlyings) >= max(4, limit):
                break
    except Exception:
        pass

    out: list[dict] = []
    for u in underlyings:
        ltp = _ltp(client, u)
        rows = _search_options(client, u)
        picks = pick_contracts(rows, ltp, mode)
        for i, p in enumerate(picks):
            score = round(0.9 - i * 0.05, 6)
            out.append(_cand(
                p["symbol"], "options", "NSE", max(score, 0.1),
                f"NSE options {mode}: {u} {p['opt_type']} {p['strike']:g} exp {p['expiry']}",
                {"underlying": u, "strike": p["strike"], "opt_type": p["opt_type"],
                 "expiry": p["expiry"], "ltp": ltp, "mode": mode},
                "openalgo"))
    return out
