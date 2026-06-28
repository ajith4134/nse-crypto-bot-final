"""trading/online/wallet.py — editable per-market paper-money wallet (O2).

A `PaperWallet` is virtual cash + positions + realised/unrealised PnL for ONE
market (NSE → ₹, CRYPTO → USDT), persisted in isolation from any real ledger so
paper play money can never be confused with a live account.

Design (research: online-editable-paper-money-engine.md):
  * Per-market wallet objects, editable balance API (Freqtrade dict-wallet +
    OpenAlgo SandboxFunds): set_starting_capital / top_up / reset.
  * Multiple named portfolios (Alpaca multi-account): keyed by portfolio_id.
  * Pluggable **reality models** (QuantConnect LEAN): SlippageModel / FeeModel /
    FillModel injected per wallet with sane per-market defaults.
  * Hard isolation + persistence: a dedicated state file per (market, portfolio)
    `paper_wallet_<market>_<portfolio_id>.json` via trading.state.

REUSE: for CRYPTO the wallet COMPOSES `crypto.paper_engine.PaperEngine` for all
order-book-walk fills, position/leverage/margin accounting, realised + unrealised
PnL and liquidation. The NSE side is a plain cash + position ledger (delivery,
1x, no order book) and reuses `journal.charges.nse_charges` for commission.

Deterministic, CPU-only, offline, no new deps.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from trading import state as _state
from trading.crypto.paper_engine import PaperEngine, Position, walk_order_book
from trading.journal import charges as _charges


def _is_buy(side: str) -> bool:
    return side.lower() in ("buy", "long", "b")


def _state_file(market: str, portfolio_id: str) -> str:
    safe = "".join(c if c.isalnum() else "_" for c in portfolio_id)
    return f"paper_wallet_{market.upper()}_{safe}.json"


# ── reality models (QuantConnect LEAN: pluggable per-security objects) ──────────
class SlippageModel:
    """Adverse price move applied to a marketable fill.

    Fixed basis-points (default 0) hard-capped at `cap_pct` (5%, Freqtrade rule):
    a BUY fills higher, a SELL lower. Subclass / inject for impact models.
    """

    def __init__(self, bps: float = 0.0, cap_pct: float = 0.05):
        self.bps = float(bps)
        self.cap_pct = float(cap_pct)

    def __call__(self, side: str, price: float, qty: float) -> float:
        frac = min(self.bps / 10_000.0, self.cap_pct)
        return price * (1 + frac) if _is_buy(side) else price * (1 - frac)


class FeeModel:
    """Base commission model. Returns the (>=0) cash fee for one fill leg."""

    def __call__(self, market: str, side: str, qty: float, price: float,
                 *, is_maker: bool = False) -> float:
        return 0.0


class CryptoFeeModel(FeeModel):
    """Crypto maker/taker bps on notional (default 5 bps taker / 2 bps maker)."""

    def __init__(self, taker_bps: float = 5.0, maker_bps: float = 2.0):
        self.taker_bps = float(taker_bps)
        self.maker_bps = float(maker_bps)

    def __call__(self, market, side, qty, price, *, is_maker=False) -> float:
        rate = (self.maker_bps if is_maker else self.taker_bps) / 10_000.0
        return abs(qty) * price * rate


class NseFeeModel(FeeModel):
    """NSE charges per leg via journal.charges.nse_charges (equity delivery)."""

    def __init__(self, segment: str = "eq_delivery", brokerage_per_order: float = 0.0):
        self.segment = segment
        self.brokerage_per_order = float(brokerage_per_order)

    def __call__(self, market, side, qty, price, *, is_maker=False) -> float:
        value = abs(qty) * price
        buy_value = value if _is_buy(side) else 0.0
        sell_value = 0.0 if _is_buy(side) else value
        c = _charges.nse_charges(self.segment, buy_value=buy_value, sell_value=sell_value,
                                 num_orders=1, brokerage_per_order=self.brokerage_per_order)
        return float(c["total_charges"])


class FillModel:
    """Decide (filled_qty, fill_price) for a marketable order.

    Default: market @ requested price (or order-book walk if a book is supplied),
    then slippage applied; always fully filled. Inject a subclass for partials.
    """

    def __call__(self, side: str, qty: float, price: float | None,
                 *, order_book: dict | None, slippage: SlippageModel) -> tuple[float, float]:
        if order_book:
            fill = walk_order_book(side, qty, order_book)
            return fill.filled, fill.avg_price  # book walk already reflects depth/slippage
        if price is None:
            raise ValueError("FillModel needs a price or an order_book")
        return qty, slippage(side, price, qty)


class ProbabilisticFillModel(FillModel):
    """Deterministic partial-fill model (Alpaca ~10%): fills `fill_ratio` of qty."""

    def __init__(self, fill_ratio: float = 0.9):
        self.fill_ratio = max(0.0, min(1.0, float(fill_ratio)))

    def __call__(self, side, qty, price, *, order_book, slippage):
        filled, px = super().__call__(side, qty, price, order_book=order_book, slippage=slippage)
        return filled * self.fill_ratio, px


# ── the wallet ─────────────────────────────────────────────────────────────────
class PaperWallet:
    """Editable virtual-money wallet for ONE market + named portfolio."""

    def __init__(self, market: str, currency: str, starting_capital: float, *,
                 portfolio_id: str = "default", persist: bool = True,
                 slippage_model: SlippageModel | None = None,
                 fee_model: FeeModel | None = None,
                 fill_model: FillModel | None = None,
                 exchange: str = "paper"):
        self.market = market.upper()
        self.currency = currency
        self.portfolio_id = portfolio_id
        self.persist = persist
        self.starting_capital = float(starting_capital)
        self._exchange = exchange
        self._is_crypto = self.market == "CRYPTO"

        self.slippage_model = slippage_model or SlippageModel()
        self.fee_model = fee_model or (CryptoFeeModel() if self._is_crypto else NseFeeModel())
        self.fill_model = fill_model or FillModel()

        self.total_fees = 0.0
        self._marks: dict = {}
        # CRYPTO: compose PaperEngine. NSE: plain cash/position ledger.
        self._engine = PaperEngine(self.starting_capital, currency) if self._is_crypto else None
        self._cash = self.starting_capital
        self._realized = 0.0
        self._ledger: dict[str, dict] = {}  # NSE: symbol -> {qty, entry_price}

        if self.persist and not self._load():
            self.save()

    # ── editable balance API ────────────────────────────────────────────────────
    def set_starting_capital(self, amount: float) -> "PaperWallet":
        """Clean reset to a NEW starting capital: clears positions, PnL, fees."""
        self.starting_capital = float(amount)
        return self.reset()

    def top_up(self, amount: float) -> "PaperWallet":
        """Add cash, keep positions and PnL (deposit)."""
        amount = float(amount)
        if self._is_crypto:
            self._engine.balance += amount
        else:
            self._cash += amount
        self.starting_capital += amount
        self.save()
        return self

    def reset(self) -> "PaperWallet":
        """Back to starting_capital, flat (no positions, zero PnL/fees)."""
        self.total_fees = 0.0
        self._marks = {}
        if self._is_crypto:
            self._engine = PaperEngine(self.starting_capital, self.currency)
        else:
            self._cash = self.starting_capital
            self._realized = 0.0
            self._ledger = {}
        self.save()
        return self

    # ── order entry ──────────────────────────────────────────────────────────────
    def order(self, symbol: str, side: str, qty: float, price: float | None = None, *,
              order_book: dict | None = None, is_maker: bool = False,
              leverage: float = 1.0) -> dict:
        """Run the reality models (fill → slippage → fee), then book the fill."""
        filled, fill_price = self.fill_model(side, qty, price, order_book=order_book,
                                             slippage=self.slippage_model)
        if filled <= 0:
            return {"status": "rejected", "reason": "no fill", "requested": qty}
        fee = self.fee_model(self.market, side, filled, fill_price, is_maker=is_maker)
        res = self.record_fill(symbol, side, filled, fill_price, fee=fee, leverage=leverage)
        res.update({"requested": qty, "fee": fee})
        return res

    def record_fill(self, symbol: str, side: str, qty: float, price: float,
                    fee: float = 0.0, *, leverage: float = 1.0) -> dict:
        """Low-level accounting: update cash / position / realised PnL by one fill.

        Crypto reuses PaperEngine (synthetic single-level book at `price`); NSE
        uses a delivery cash+position ledger. `fee` is a cash cost on top.
        """
        if qty <= 0:
            raise ValueError("qty must be > 0")
        fee = float(fee)
        self.total_fees += fee

        if self._is_crypto:
            book = ({"asks": [[price, qty]]} if _is_buy(side) else {"bids": [[price, qty]]})
            res = self._engine.market_order(symbol=symbol, exchange=self._exchange, side=side,
                                            amount=qty, order_book=book, leverage=leverage)
            # Fees are a cash cost not modelled by the engine: net them out.
            self._engine.balance -= fee
            self._engine.realized_pnl -= fee
        else:
            res = self._nse_fill(symbol, side, qty, price, fee)
        self.save()
        return res

    def _nse_fill(self, symbol: str, side: str, qty: float, price: float, fee: float) -> dict:
        pos = self._ledger.get(symbol, {"qty": 0.0, "entry_price": 0.0})
        signed = qty if _is_buy(side) else -qty
        out: dict = {"status": "filled", "symbol": symbol, "side": side.lower(),
                     "avg_price": price, "filled": qty}
        cur = pos["qty"]
        same_dir = (cur >= 0) == (signed >= 0) or cur == 0
        if same_dir:
            total = cur + signed
            if abs(total) > 1e-12:
                pos["entry_price"] = (pos["entry_price"] * abs(cur) + price * abs(signed)) / abs(total)
            pos["qty"] = total
        else:
            closing = min(abs(signed), abs(cur))
            direction = 1.0 if cur > 0 else -1.0
            realized = direction * closing * (price - pos["entry_price"])
            self._realized += realized
            out["realized_pnl"] = realized
            new = cur + signed
            if abs(new) <= 1e-12:
                pos = {"qty": 0.0, "entry_price": 0.0}
            elif (new > 0) != (cur > 0):
                pos = {"qty": new, "entry_price": price}  # flipped
                out["flipped"] = True
            else:
                pos["qty"] = new  # partial reduce, entry unchanged
        # Cash: pay for buys / receive for sells, fee always a cost.
        self._cash -= signed * price + fee
        self._realized -= fee
        if abs(pos["qty"]) <= 1e-12:
            self._ledger.pop(symbol, None)
            out["closed"] = True
        else:
            self._ledger[symbol] = pos
        out["position_size"] = pos["qty"]
        return out

    # ── valuation ─────────────────────────────────────────────────────────────────
    def mark(self, prices: dict) -> dict:
        """Update mark prices; return unrealised PnL + equity at those marks."""
        self._marks = dict(prices or {})
        self.save()
        return {"unrealized_pnl": self.unrealized_pnl(), "equity": self.equity()}

    def _nse_positions(self) -> list[dict]:
        out = []
        for sym, p in self._ledger.items():
            mark = self._marks.get(sym, p["entry_price"])
            out.append({"symbol": sym, "side": "long" if p["qty"] > 0 else "short",
                        "size": p["qty"], "entry_price": p["entry_price"],
                        "notional": abs(p["qty"]) * p["entry_price"], "margin": 0.0,
                        "unrealized_pnl": p["qty"] * (mark - p["entry_price"])})
        return out

    def positions(self) -> list[dict]:
        return self._engine.positions(self._marks) if self._is_crypto else self._nse_positions()

    def unrealized_pnl(self) -> float:
        return sum(p["unrealized_pnl"] for p in self.positions())

    def cash(self) -> float:
        return self._engine.balance if self._is_crypto else self._cash

    def used_margin(self) -> float:
        return self._engine.used_margin if self._is_crypto else 0.0

    def realized_pnl(self) -> float:
        return self._engine.realized_pnl if self._is_crypto else self._realized

    def equity(self) -> float:
        if self._is_crypto:
            return self._engine.equity(self._marks)
        return self._cash + sum(abs(p["size"]) * self._marks.get(p["symbol"], p["entry_price"])
                                * (1 if p["size"] > 0 else -1) for p in self._nse_positions())

    def summary(self) -> dict:
        return {
            "market": self.market, "currency": self.currency,
            "portfolio_id": self.portfolio_id,
            "starting_capital": self.starting_capital,
            "cash": self.cash(), "used_margin": self.used_margin(),
            "realized_pnl": self.realized_pnl(), "unrealized_pnl": self.unrealized_pnl(),
            "equity": self.equity(), "total_fees": self.total_fees,
            "positions": self.positions(),
        }

    # ── persistence (isolated paper state file) ────────────────────────────────────
    def _file(self) -> str:
        return _state_file(self.market, self.portfolio_id)

    def save(self) -> None:
        if not self.persist:
            return
        data = {
            "market": self.market, "currency": self.currency,
            "portfolio_id": self.portfolio_id,
            "starting_capital": self.starting_capital,
            "total_fees": self.total_fees, "marks": self._marks,
        }
        if self._is_crypto:
            data["cash"] = self._engine.balance
            data["used_margin"] = self._engine.used_margin
            data["realized_pnl"] = self._engine.realized_pnl
            data["positions"] = {k: vars(p) for k, p in self._engine._positions.items()}
        else:
            data["cash"] = self._cash
            data["realized_pnl"] = self._realized
            data["ledger"] = self._ledger
        _state.save_json(self._file(), data)

    def _load(self) -> bool:
        data = _state.load_json(self._file(), None)
        if not isinstance(data, dict):
            return False
        self.starting_capital = float(data.get("starting_capital", self.starting_capital))
        self.total_fees = float(data.get("total_fees", 0.0))
        self._marks = data.get("marks", {}) or {}
        if self._is_crypto:
            self._engine = PaperEngine(self.starting_capital, self.currency)
            self._engine.balance = float(data.get("cash", self.starting_capital))
            self._engine.used_margin = float(data.get("used_margin", 0.0))
            self._engine.realized_pnl = float(data.get("realized_pnl", 0.0))
            for k, pd in (data.get("positions") or {}).items():
                self._engine._positions[k] = Position(**pd)
        else:
            self._cash = float(data.get("cash", self.starting_capital))
            self._realized = float(data.get("realized_pnl", 0.0))
            self._ledger = data.get("ledger", {}) or {}
        return True


# ── book of wallets (multi-market, multi-portfolio) ─────────────────────────────
_DEFAULT_CURRENCY = {"NSE": "INR", "CRYPTO": "USDT"}
_DEFAULT_CAPITAL = {"NSE": 1_000_000.0, "CRYPTO": 100_000.0}


class PaperWalletBook:
    """Holds wallets per (market, portfolio_id). Supports multiple named portfolios."""

    def __init__(self, *, persist: bool = True):
        self.persist = persist
        self._wallets: dict[tuple[str, str], PaperWallet] = {}

    def wallet(self, market: str, portfolio_id: str = "default", *,
               currency: str | None = None, starting_capital: float | None = None,
               **kw) -> PaperWallet:
        market = market.upper()
        key = (market, portfolio_id)
        w = self._wallets.get(key)
        if w is None:
            w = PaperWallet(
                market,
                currency or _DEFAULT_CURRENCY.get(market, "USDT"),
                starting_capital if starting_capital is not None else _DEFAULT_CAPITAL.get(market, 100_000.0),
                portfolio_id=portfolio_id, persist=self.persist, **kw)
            self._wallets[key] = w
        return w

    def reset_all(self) -> None:
        for w in self._wallets.values():
            w.reset()

    def status(self) -> dict:
        return {"wallets": [w.summary() for w in self._wallets.values()]}
