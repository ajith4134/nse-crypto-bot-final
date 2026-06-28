"""trading/execution/bracket.py — bracket + cover order builders (T3 §9).

NSE intraday risk-bracketed orders:

  • Bracket Order (BO): entry + a profit-target leg + a stop-loss leg. Booking the
    target or hitting the stop auto-cancels the sibling (OCO).
  • Cover Order (CO): entry + a compulsory stop-loss leg (no target).

OpenAlgo's REST API places plain legs (it does not expose a native BO/CO product for
every broker), so we BUILD the leg specifications here as plain dicts that map onto
`OpenAlgoClient.place_order(...)`, and compute the target/stop prices from points.
The engine/session dispatches them (target as LIMIT, stop as SL-M). Pure builders +
validation — no network, fully unit-testable.
"""
from __future__ import annotations


def _exit_action(entry_action: str) -> str:
    a = entry_action.upper()
    if a == "BUY":
        return "SELL"
    if a == "SELL":
        return "BUY"
    raise ValueError(f"entry action must be BUY/SELL, got {entry_action!r}")


def _target_stop_prices(entry_action: str, entry_price: float,
                        target_points: float, stop_points: float) -> tuple[float, float]:
    if entry_price <= 0:
        raise ValueError("entry_price must be > 0")
    if target_points <= 0 or stop_points <= 0:
        raise ValueError("target_points and stop_points must be > 0")
    if entry_action.upper() == "BUY":           # long
        return entry_price + target_points, entry_price - stop_points
    return entry_price - target_points, entry_price + stop_points   # short


def bracket_order(*, symbol: str, action: str, quantity: int, entry_price: float,
                  target_points: float, stop_points: float, exchange: str = "NSE",
                  product: str = "MIS", entry_type: str = "LIMIT") -> dict:
    """Build a 3-leg bracket order spec (entry + target + stop-loss, OCO)."""
    if quantity <= 0:
        raise ValueError("quantity must be > 0")
    target_price, stop_price = _target_stop_prices(action, entry_price, target_points, stop_points)
    exit_action = _exit_action(action)
    rr = round(target_points / stop_points, 4)
    entry_leg = {
        "leg": "entry", "symbol": symbol, "exchange": exchange.upper(),
        "action": action.upper(), "quantity": quantity, "product": product.upper(),
        "price_type": entry_type.upper(),
        "price": entry_price if entry_type.upper() == "LIMIT" else 0.0,
    }
    target_leg = {
        "leg": "target", "symbol": symbol, "exchange": exchange.upper(),
        "action": exit_action, "quantity": quantity, "product": product.upper(),
        "price_type": "LIMIT", "price": round(target_price, 2),
    }
    stop_leg = {
        "leg": "stoploss", "symbol": symbol, "exchange": exchange.upper(),
        "action": exit_action, "quantity": quantity, "product": product.upper(),
        "price_type": "SL-M", "trigger_price": round(stop_price, 2),
    }
    return {
        "kind": "bracket", "symbol": symbol, "exchange": exchange.upper(),
        "direction": "LONG" if action.upper() == "BUY" else "SHORT",
        "entry_price": entry_price, "target_price": round(target_price, 2),
        "stop_price": round(stop_price, 2), "risk_reward": rr, "oco": True,
        "legs": [entry_leg, target_leg, stop_leg],
    }


def cover_order(*, symbol: str, action: str, quantity: int, entry_price: float,
                stop_points: float, exchange: str = "NSE", product: str = "MIS",
                entry_type: str = "MARKET") -> dict:
    """Build a 2-leg cover order spec (entry + compulsory stop-loss)."""
    if quantity <= 0:
        raise ValueError("quantity must be > 0")
    _, stop_price = _target_stop_prices(action, entry_price, target_points=stop_points,
                                        stop_points=stop_points)
    exit_action = _exit_action(action)
    entry_leg = {
        "leg": "entry", "symbol": symbol, "exchange": exchange.upper(),
        "action": action.upper(), "quantity": quantity, "product": product.upper(),
        "price_type": entry_type.upper(),
        "price": entry_price if entry_type.upper() == "LIMIT" else 0.0,
    }
    stop_leg = {
        "leg": "stoploss", "symbol": symbol, "exchange": exchange.upper(),
        "action": exit_action, "quantity": quantity, "product": product.upper(),
        "price_type": "SL-M", "trigger_price": round(stop_price, 2),
    }
    return {
        "kind": "cover", "symbol": symbol, "exchange": exchange.upper(),
        "direction": "LONG" if action.upper() == "BUY" else "SHORT",
        "entry_price": entry_price, "stop_price": round(stop_price, 2),
        "legs": [entry_leg, stop_leg],
    }
