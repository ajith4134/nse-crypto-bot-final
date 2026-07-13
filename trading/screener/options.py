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

# Index underlyings always screened for options — with the exchange each one's
# SPOT quote and OPTION contracts live on. NSE indices → NSE_INDEX spot + NFO
# options; BSE indices (SENSEX/BANKEX) → BSE_INDEX spot + BFO options. Previously
# only INDEX_UNDERLYINGS[:2] (NIFTY, BANKNIFTY) were seeded and the rest relied on
# the IP-blocked nselib active_underlying feed → NIFTY-only options (2026-07-07 fix).
INDEX_EXCHANGES: dict[str, tuple[str, str]] = {
    "NIFTY": ("NSE_INDEX", "NFO"),
    "BANKNIFTY": ("NSE_INDEX", "NFO"),
    "FINNIFTY": ("NSE_INDEX", "NFO"),
    "MIDCPNIFTY": ("NSE_INDEX", "NFO"),
    "NIFTYNXT50": ("NSE_INDEX", "NFO"),
    "SENSEX": ("BSE_INDEX", "BFO"),
    "BANKEX": ("BSE_INDEX", "BFO"),
}
INDEX_UNDERLYINGS = list(INDEX_EXCHANGES.keys())
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


def _spot_exch(underlying: str) -> str:
    """Exchange for the underlying's SPOT quote (NSE_INDEX / BSE_INDEX / NSE)."""
    return INDEX_EXCHANGES.get(underlying.upper(), (None, None))[0] or "NSE"


def _opt_exch(underlying: str) -> str:
    """Exchange the underlying's OPTION contracts live on (NFO for NSE, BFO for BSE)."""
    return INDEX_EXCHANGES.get(underlying.upper(), (None, "NFO"))[1] or "NFO"


def _ui_ltp(underlying: str) -> float:
    """Underlying LTP from the Upstox UI feed ONLY (NSE_UI_ONLY). 0.0 → abstain."""
    try:
        from trading.broker_sense import ui_market
        t = ui_market.ticker(underlying) or {}
        return float(t.get("last") or t.get("ltp") or 0) or 0.0
    except Exception:
        return 0.0


def _ui_option_chain_fresh(underlying: str) -> bool:
    """True when the Upstox UI has a FRESH option-chain capture for `underlying` — the
    brain only screens options it is actually LOOKING at in the Upstox app (NSE_UI_ONLY)."""
    try:
        from trading.broker_sense import ui_market
        return ui_market.option_chain(underlying) is not None
    except Exception:
        return False


def _ltp(client: Any, underlying: str) -> float:
    # NSE_UI_ONLY (owner 2026-07-13): the underlying LTP comes from the Upstox UI feed only.
    from trading.broker_sense.ui_data import nse_ui_only
    if nse_ui_only():
        return _ui_ltp(underlying)
    # REST quotes(), NOT get_ltp(): the SDK's get_ltp is the websocket-stream helper and
    # returns {'ltp': {}} without a live subscription — which made every ATM strike
    # uncomputable and the options screener return [] forever.
    exch = _spot_exch(underlying)
    try:
        r = client.quotes(exchange=exch, symbol=underlying)
        d = r.get("data", r) if isinstance(r, dict) else {}
        return float(d.get("ltp") or d.get("last_price") or 0) if isinstance(d, dict) else 0.0
    except Exception:
        return 0.0


def _search_options(client: Any, underlying: str, exchange: str = "NFO") -> list[dict]:
    try:
        return _norm_rows(client.search(query=underlying, exchange=exchange))
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

    # Universe: ALL index underlyings (NSE + BSE) — always screened — plus top-liquid
    # F&O STOCK underlyings. nselib active_underlying is IP-blocked, so stock names come
    # from the reliable liquid F&O universe (trading/screener/universe.py). This is what
    # makes BankNifty/FinNifty/Sensex options open too, not just NIFTY (2026-07-07 fix).
    underlyings: list[str] = list(INDEX_UNDERLYINGS)          # every index, NSE + BSE
    try:
        au = source.active_underlying() or [] if source is not None else []
        au.sort(key=lambda r: float(r.get("optVolume") or r.get("totVolume") or 0), reverse=True)
        for r in au:
            u = str(r.get("symbol") or r.get("underlying") or "").upper()
            if u and u not in _INDEX_SET and u not in underlyings:
                underlyings.append(u)
    except Exception:
        pass
    try:                                                     # reliable stock F&O names
        from trading.screener.universe import NSE_FO_STOCKS
        for u in NSE_FO_STOCKS:
            if u not in underlyings:
                underlyings.append(u)
                if len(underlyings) >= max(len(INDEX_UNDERLYINGS) + 8, limit):
                    break
    except Exception:
        pass

    from trading.broker_sense.ui_data import nse_ui_only
    ui_only = nse_ui_only()
    out: list[dict] = []
    for u in underlyings:
        # NSE_UI_ONLY: only screen an underlying whose option chain the eyes are actually
        # watching in the Upstox app (fresh option_chain capture), else ABSTAIN it — no
        # blind API-driven option candidates.
        if ui_only and not _ui_option_chain_fresh(u):
            continue
        ltp = _ltp(client, u)
        if ui_only and ltp <= 0:
            continue                                         # no UI LTP → can't place ATM → skip
        opt_exch = _opt_exch(u)                              # NFO (NSE) or BFO (BSE)
        rows = _search_options(client, u, exchange=opt_exch)
        picks = pick_contracts(rows, ltp, mode)
        for i, p in enumerate(picks):
            score = round(0.9 - i * 0.05, 6)
            out.append(_cand(
                p["symbol"], "options", "NSE", max(score, 0.1),
                f"{opt_exch} options {mode}: {u} {p['opt_type']} {p['strike']:g} exp {p['expiry']}",
                # `oa_exchange` tells the loop which venue to quote/route on (BFO for
                # SENSEX/BANKEX, else NFO) — see live_loop._oa_exch_for_option.
                {"underlying": u, "strike": p["strike"], "opt_type": p["opt_type"],
                 "expiry": p["expiry"], "ltp": ltp, "mode": mode, "oa_exchange": opt_exch},
                "openalgo"))
    return out
