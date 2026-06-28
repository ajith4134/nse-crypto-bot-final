"""trading/crypto/paper_engine.py — crypto paper-fill simulator (T2 §3).

Simulates order fills against the REAL order book (fetched live via ccxt by the
session, or passed in directly for tests). Tracks positions with leverage and
margin mode, realised + unrealised PnL, and liquidation price. Pure Python and
deterministic — no network here, so it is fully unit-testable.

Order-book format (ccxt): {"bids": [[price, size], ...desc], "asks": [[price, size], ...asc]}.
A BUY market order consumes asks (ascending); a SELL consumes bids (descending).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from trading.crypto.config import DEFAULT_MMR
from trading.crypto.liquidation import liquidation_price


@dataclass(frozen=True)
class Fill:
    avg_price: float
    filled: float          # base quantity actually filled
    requested: float       # base quantity requested
    slippage: float        # fraction vs best price (0 = no slippage)
    levels: int            # order-book levels consumed

    @property
    def fully_filled(self) -> bool:
        return self.filled >= self.requested - 1e-12


def walk_order_book(side: str, amount: float, book: dict) -> Fill:
    """Walk the book to fill `amount` base units. Returns the realised fill."""
    if amount <= 0:
        raise ValueError("amount must be > 0")
    s = side.lower()
    if s in ("buy", "long", "b"):
        levels = book.get("asks") or []
    elif s in ("sell", "short", "s"):
        levels = book.get("bids") or []
    else:
        raise ValueError(f"unknown side: {side!r}")
    if not levels:
        return Fill(0.0, 0.0, amount, 0.0, 0)

    best = float(levels[0][0])
    remaining = amount
    cost = 0.0
    used = 0
    for price, size in levels:
        price, size = float(price), float(size)
        take = min(remaining, size)
        cost += take * price
        remaining -= take
        used += 1
        if remaining <= 1e-12:
            break
    filled = amount - remaining
    avg = cost / filled if filled > 0 else 0.0
    slippage = abs(avg - best) / best if best > 0 and filled > 0 else 0.0
    return Fill(avg, filled, amount, slippage, used)


@dataclass
class Position:
    symbol: str
    exchange: str
    size: float            # signed base qty: + long, - short
    entry_price: float
    leverage: float
    margin_mode: str = "isolated"
    mmr: float = DEFAULT_MMR

    @property
    def side(self) -> str:
        return "long" if self.size > 0 else "short"

    @property
    def notional(self) -> float:
        return abs(self.size) * self.entry_price

    @property
    def margin(self) -> float:
        return self.notional / self.leverage if self.leverage else self.notional

    def unrealized_pnl(self, mark_price: float) -> float:
        return self.size * (mark_price - self.entry_price)

    def liquidation_price(self) -> float:
        return liquidation_price(
            side=self.side, entry_price=self.entry_price, leverage=self.leverage,
            mmr=self.mmr, margin_mode=self.margin_mode,
        )


class PaperEngine:
    """In-memory paper broker. One per CryptoSession."""

    def __init__(self, starting_balance: float = 100_000.0, quote: str = "USDT"):
        self.starting_balance = starting_balance
        self.quote = quote
        self.balance = starting_balance      # free collateral
        self.used_margin = 0.0
        self.realized_pnl = 0.0
        self._positions: dict[str, Position] = {}
        self._fills: list[dict] = []         # audit trail

    @staticmethod
    def _key(exchange: str, symbol: str) -> str:
        return f"{exchange}:{symbol}"

    # ── order entry ───────────────────────────────────────────────────────────
    def market_order(self, *, symbol: str, exchange: str, side: str, amount: float,
                     order_book: dict, leverage: float = 1.0,
                     margin_mode: str = "isolated", mmr: float = DEFAULT_MMR) -> dict:
        """Fill a market order against `order_book` and update the position."""
        fill = walk_order_book(side, amount, order_book)
        if fill.filled <= 0:
            return {"status": "rejected", "reason": "empty/thin order book", "fill": fill.__dict__}

        signed = fill.filled if side.lower() in ("buy", "long", "b") else -fill.filled
        key = self._key(exchange, symbol)
        pos = self._positions.get(key)
        result = {"status": "filled", "symbol": symbol, "exchange": exchange,
                  "side": side.lower(), "avg_price": fill.avg_price, "filled": fill.filled,
                  "slippage": fill.slippage}

        if pos is None:
            # Open fresh position.
            self._positions[key] = Position(symbol, exchange, signed, fill.avg_price,
                                            leverage, margin_mode, mmr)
            self.used_margin += self._positions[key].margin
            self.balance -= self._positions[key].margin
        else:
            result.update(self._apply_to_existing(pos, key, signed, fill.avg_price,
                                                  leverage, margin_mode, mmr))

        p = self._positions.get(key)
        if p is not None:
            result["liquidation_price"] = p.liquidation_price()
            result["position_size"] = p.size
        self._fills.append(result)
        return result

    def _apply_to_existing(self, pos: Position, key: str, signed: float, price: float,
                           leverage: float, margin_mode: str, mmr: float) -> dict:
        same_dir = (pos.size > 0) == (signed > 0)
        info: dict = {}
        # Release old margin; recompute after.
        self.used_margin -= pos.margin
        self.balance += pos.margin

        if same_dir:
            # Increase: weighted-average entry.
            total = pos.size + signed
            pos.entry_price = (pos.entry_price * abs(pos.size) + price * abs(signed)) / abs(total)
            pos.size = total
            pos.leverage = leverage
            pos.margin_mode = margin_mode
        else:
            closing = min(abs(signed), abs(pos.size))
            # Realised PnL on the closed quantity (direction of the OLD position).
            direction = 1.0 if pos.size > 0 else -1.0
            realized = direction * closing * (price - pos.entry_price)
            self.realized_pnl += realized
            self.balance += realized
            info["realized_pnl"] = realized
            new_size = pos.size + signed
            if abs(new_size) <= 1e-12:
                del self._positions[key]      # flat
                return {**info, "closed": True}
            elif (new_size > 0) != (pos.size > 0):
                # Flipped: remainder opens opposite at fill price.
                pos.size = new_size
                pos.entry_price = price
                pos.leverage = leverage
                pos.margin_mode = margin_mode
                info["flipped"] = True
            else:
                pos.size = new_size           # partial reduce, entry unchanged

        # Re-reserve margin for the surviving position.
        if key in self._positions:
            self.used_margin += pos.margin
            self.balance -= pos.margin
        return info

    def close(self, symbol: str, exchange: str, order_book: dict) -> dict:
        """Market-close the whole position at the current book."""
        pos = self._positions.get(self._key(exchange, symbol))
        if pos is None:
            return {"status": "noop", "reason": "no position"}
        side = "sell" if pos.size > 0 else "buy"
        return self.market_order(symbol=symbol, exchange=exchange, side=side,
                                 amount=abs(pos.size), order_book=order_book,
                                 leverage=pos.leverage, margin_mode=pos.margin_mode,
                                 mmr=pos.mmr)

    # ── views ─────────────────────────────────────────────────────────────────
    def positions(self, mark_prices: dict | None = None) -> list[dict]:
        marks = mark_prices or {}
        out = []
        for key, p in self._positions.items():
            mark = marks.get(key, marks.get(p.symbol, p.entry_price))
            out.append({
                "symbol": p.symbol, "exchange": p.exchange, "side": p.side,
                "size": p.size, "entry_price": p.entry_price, "leverage": p.leverage,
                "margin_mode": p.margin_mode, "notional": p.notional, "margin": p.margin,
                "unrealized_pnl": p.unrealized_pnl(mark),
                "liquidation_price": p.liquidation_price(),
            })
        return out

    def equity(self, mark_prices: dict | None = None) -> float:
        unreal = sum(pp["unrealized_pnl"] for pp in self.positions(mark_prices))
        return self.balance + self.used_margin + unreal

    def summary(self, mark_prices: dict | None = None) -> dict:
        return {
            "quote": self.quote,
            "starting_balance": self.starting_balance,
            "free_balance": self.balance,
            "used_margin": self.used_margin,
            "realized_pnl": self.realized_pnl,
            "equity": self.equity(mark_prices),
            "open_positions": self.positions(mark_prices),
        }
