"""trading/alerts/events.py — the AlertEvent model + builders (T7).

One normalized event type flows through the whole alert pipeline (dedup → format →
channels). Builders construct the common trading events with a stable `dedup_key` so
the deduplicator can suppress repeats. Pure data, no I/O; timestamps are passed in
(epoch seconds) to keep everything deterministic and testable.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

SEVERITIES = ("info", "warn", "critical")


@dataclass
class AlertEvent:
    kind: str                       # fill | daily_pnl | signal | circuit_breaker | kill | error
    title: str
    body: str = ""
    severity: str = "info"
    symbol: str = ""
    fields: dict = field(default_factory=dict)   # label -> value (shown in the message)
    dedup_key: str = ""             # stable identity for dedup; auto-derived if blank
    ts: float = 0.0                 # epoch seconds (caller supplies; 0 = unset)

    def __post_init__(self) -> None:
        if self.severity not in SEVERITIES:
            self.severity = "info"
        if not self.dedup_key:
            self.dedup_key = self._auto_key()

    def _auto_key(self) -> str:
        # Stable across identical events; excludes free-form body so near-dupes collapse.
        basis = f"{self.kind}|{self.symbol}|{self.title}|" + \
            "|".join(f"{k}={v}" for k, v in sorted(self.fields.items()))
        return f"{self.kind}:" + hashlib.sha1(basis.encode()).hexdigest()[:16]

    def as_dict(self) -> dict:
        return {
            "kind": self.kind, "title": self.title, "body": self.body,
            "severity": self.severity, "symbol": self.symbol, "fields": self.fields,
            "dedup_key": self.dedup_key, "ts": self.ts,
        }


# ── builders ────────────────────────────────────────────────────────────────────
def fill_event(*, symbol: str, side: str, qty: float, price: float, order_id: str = "",
               exchange: str = "", ts: float = 0.0) -> AlertEvent:
    side = side.upper()
    return AlertEvent(
        kind="fill", severity="info", symbol=symbol,
        title=f"FILL {side} {qty} {symbol} @ {price}",
        fields={"side": side, "qty": qty, "price": price, "exchange": exchange,
                "order_id": order_id},
        dedup_key=f"fill:{order_id or symbol}:{side}:{qty}:{price}", ts=ts,
    )


def daily_pnl_event(*, net_pnl: float, trades: int, win_rate: float | None = None,
                    day: str = "", ts: float = 0.0) -> AlertEvent:
    sev = "info" if net_pnl >= 0 else "warn"
    return AlertEvent(
        kind="daily_pnl", severity=sev,
        title=f"Daily P&L {day}: {net_pnl:+.2f}",
        fields={"net_pnl": round(net_pnl, 2), "trades": trades,
                "win_rate": None if win_rate is None else round(win_rate, 1)},
        dedup_key=f"daily_pnl:{day}", ts=ts,
    )


def signal_event(*, symbol: str, signal: str, confidence: float | None = None,
                 source: str = "", ts: float = 0.0) -> AlertEvent:
    return AlertEvent(
        kind="signal", severity="info", symbol=symbol,
        title=f"SIGNAL {signal.upper()} {symbol}",
        fields={"signal": signal.upper(),
                "confidence": None if confidence is None else round(confidence, 3),
                "source": source},
        dedup_key=f"signal:{symbol}:{signal.upper()}:{source}", ts=ts,
    )


def circuit_breaker_event(*, reason: str, ts: float = 0.0) -> AlertEvent:
    return AlertEvent(
        kind="circuit_breaker", severity="critical",
        title="⚠ CIRCUIT BREAKER TRIPPED", body=reason,
        fields={"reason": reason}, dedup_key="circuit_breaker", ts=ts,
    )


def kill_event(*, reason: str, report: dict | None = None, ts: float = 0.0) -> AlertEvent:
    rep = report or {}
    return AlertEvent(
        kind="kill", severity="critical",
        title="🛑 KILL SWITCH ENGAGED", body=reason,
        fields={"reason": reason, "cancelled": rep.get("cancelled"),
                "flattened": rep.get("flattened"), "ok": rep.get("ok")},
        dedup_key=f"kill:{reason}", ts=ts,
    )
