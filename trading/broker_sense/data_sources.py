"""trading/broker_sense/data_sources.py — per-broker PUBLIC-vs-ACCOUNT data-source switch.

Owner's idea: turn a broker's PUBLIC data OFF so the brain's MAIN source becomes the LOGGED-IN
ACCOUNT pages (opened after login), not free public screeners. This switch is the cross-process
truth both the dashboard (which flips it) and the funnel LOOP (which reads it each cycle) share,
via a small state file — same pattern as the funnel status file.

  public ON  (default): funnel uses the public lanes — TradingView public screener + the broker's
                        PUBLIC screener page (works with no login).
  public OFF:           funnel drops those public lanes for that broker and screens from the
                        LOGGED-IN ACCOUNT page instead (requires the connected account; the
                        interception layer then captures the account-gated data). Account-first.

No secrets here — just booleans. Execution is unaffected (APIs only, always)."""
from __future__ import annotations

from trading import state

_FILE = "broker_data_sources.json"
# brokers the switch applies to; others stay public-only screening
_TOGGLEABLE = ("binance", "angelone", "upstox", "groww")
# per-market PRIMARY account broker (owner's slice). Angel One's web login turned out to be
# server-blocked for automated browsers (research/angelone-login-blocked.md), so the NSE
# primary is switchable — Upstox's QR login connects with no typing at all.
_DEFAULT_PRIMARY = {"crypto": "binance", "nse": "angelone"}


def _load() -> dict:
    d = state.load_json(_FILE, {})
    return d if isinstance(d, dict) else {}


def public_enabled(broker: str) -> bool:
    """True (default) if the broker's PUBLIC data lanes are on. False → account-first."""
    return bool(_load().get(broker, {}).get("public", True))


def set_public(broker: str, on: bool) -> dict:
    """Flip a broker's public-data lanes on/off. Returns the new full status."""
    d = _load()
    d.setdefault(broker, {})["public"] = bool(on)
    state.save_json(_FILE, d)
    return status()


def account_first(broker: str) -> bool:
    """True when the brain should source this broker from the logged-in account page."""
    return not public_enabled(broker)


def primary_broker(market: str) -> str:
    """The market's PRIMARY account broker (state-backed, owner-switchable)."""
    p = _load().get("_primary", {})
    return str(p.get(market) or _DEFAULT_PRIMARY.get(market, ""))


def set_primary(market: str, broker: str) -> dict:
    """Switch a market's primary account broker (e.g. nse → upstox). Returns full status."""
    d = _load()
    d.setdefault("_primary", {})[market] = str(broker)
    state.save_json(_FILE, d)
    return status()


def status() -> dict:
    """Per-broker source state for the dashboard (honest: reflects the shared state file)."""
    d = _load()
    out = {b: {"public": bool(d.get(b, {}).get("public", True)),
               "mode": "public" if d.get(b, {}).get("public", True) else "account"}
           for b in _TOGGLEABLE}
    out["_primary"] = {m: primary_broker(m) for m in _DEFAULT_PRIMARY}
    return out
