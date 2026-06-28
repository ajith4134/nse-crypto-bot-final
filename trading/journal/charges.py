"""trading/journal/charges.py — Indian + crypto transaction-cost math (T5 §5 P&L).

Turns a round-trip trade's gross P&L into NET P&L after every statutory + broker
charge. Indian charges follow the post-Oct-2024 SEBI/exchange schedule for NSE; they
change often, so all rates live in tunable dataclasses (`IndianChargeRates`) and the
output is honestly labelled an ESTIMATE — the broker contract note is authoritative.

Charge structure (NSE):
  • STT/CTT   : security/commodity transaction tax — side-specific (see rates).
  • Exch txn  : exchange transaction charge — % of turnover, BOTH sides.
  • SEBI      : ₹10 per crore = 0.0001% of turnover, both sides.
  • Stamp duty: BUY side only.
  • Brokerage : flat per order (discount-broker model), tunable.
  • GST       : 18% on (brokerage + exchange txn + SEBI).

Crypto: maker/taker fee as a % of notional per side, plus perp funding P&L (passed
in, signed: negative = paid). Pure functions, deterministic, no I/O.
"""
from __future__ import annotations

from dataclasses import dataclass

GST_RATE = 0.18


@dataclass(frozen=True)
class SegmentRates:
    stt_buy: float = 0.0          # fraction of buy turnover
    stt_sell: float = 0.0         # fraction of sell turnover
    exch_txn: float = 0.0         # fraction of turnover, both sides
    sebi: float = 0.000001        # 0.0001% = ₹10/crore
    stamp_buy: float = 0.0        # fraction of buy turnover


@dataclass(frozen=True)
class IndianChargeRates:
    """Default NSE rates (~FY2024-25). Tune per broker/segment as needed."""
    eq_intraday: SegmentRates = SegmentRates(
        stt_sell=0.00025, exch_txn=0.0000297, sebi=0.000001, stamp_buy=0.00003)
    eq_delivery: SegmentRates = SegmentRates(
        stt_buy=0.001, stt_sell=0.001, exch_txn=0.0000297, sebi=0.000001, stamp_buy=0.00015)
    fut: SegmentRates = SegmentRates(
        stt_sell=0.0002, exch_txn=0.0000173, sebi=0.000001, stamp_buy=0.00002)
    opt: SegmentRates = SegmentRates(          # all on PREMIUM turnover
        stt_sell=0.001, exch_txn=0.0003503, sebi=0.000001, stamp_buy=0.00003)

    def for_segment(self, segment: str) -> SegmentRates:
        key = segment.lower()
        table = {"eq_intraday": self.eq_intraday, "eq_delivery": self.eq_delivery,
                 "fut": self.fut, "opt": self.opt,
                 # friendly aliases
                 "mis": self.eq_intraday, "cnc": self.eq_delivery,
                 "futures": self.fut, "options": self.opt, "ce": self.opt, "pe": self.opt}
        if key not in table:
            raise ValueError(f"unknown segment {segment!r}; use eq_intraday/eq_delivery/fut/opt")
        return table[key]


DEFAULT_RATES = IndianChargeRates()


def nse_charges(segment: str, *, buy_value: float, sell_value: float,
                num_orders: int = 2, brokerage_per_order: float = 20.0,
                rates: IndianChargeRates | None = None) -> dict:
    """Estimate all NSE charges for a round trip (one buy leg + one sell leg).

    For options/futures pass PREMIUM/contract turnover as buy_value/sell_value.
    Brokerage default is the ₹20/order discount model; pass 0.0 for free delivery.
    """
    if buy_value < 0 or sell_value < 0:
        raise ValueError("turnover values must be >= 0")
    r = (rates or DEFAULT_RATES).for_segment(segment)
    turnover = buy_value + sell_value

    stt = r.stt_buy * buy_value + r.stt_sell * sell_value
    exchange_txn = r.exch_txn * turnover
    sebi = r.sebi * turnover
    stamp_duty = r.stamp_buy * buy_value
    brokerage = brokerage_per_order * max(0, num_orders)
    gst = GST_RATE * (brokerage + exchange_txn + sebi)

    total = stt + exchange_txn + sebi + stamp_duty + brokerage + gst
    return {
        "stt": round(stt, 4), "exchange_txn_charges": round(exchange_txn, 4),
        "sebi_charges": round(sebi, 4), "stamp_duty": round(stamp_duty, 4),
        "brokerage": round(brokerage, 4), "gst": round(gst, 4),
        "total_charges": round(total, 4), "estimate": True,
    }


def crypto_charges(*, entry_notional: float, exit_notional: float,
                   funding_pnl: float = 0.0, taker_rate: float = 0.0005,
                   maker_rate: float = 0.0002, entry_is_maker: bool = False,
                   exit_is_maker: bool = False) -> dict:
    """Estimate crypto fees (per-side maker/taker) + fold in perp funding P&L.

    funding_pnl is signed (negative = funding paid). Fee is always a cost (>= 0).
    """
    if entry_notional < 0 or exit_notional < 0:
        raise ValueError("notionals must be >= 0")
    entry_fee = entry_notional * (maker_rate if entry_is_maker else taker_rate)
    exit_fee = exit_notional * (maker_rate if exit_is_maker else taker_rate)
    fee = entry_fee + exit_fee
    return {
        "maker_taker_fee": round(fee, 8),
        "funding_pnl": round(funding_pnl, 8),
        # total cost reduces P&L: fees are a cost, funding is signed.
        "total_charges": round(fee - funding_pnl, 8),
        "estimate": True,
    }


def net_pnl(gross_pnl: float, total_charges: float) -> float:
    """Net P&L = gross − total charges."""
    return gross_pnl - total_charges
