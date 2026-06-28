"""trading/online/session.py — market calendar + LIVE↔REPLAY mode (O1).

The "spine" of going online (research: online-nse-offhours-paper-trading). For each
market it answers: is the market open right now, and therefore should the bot run in
LIVE mode (trade live ticks) or REPLAY mode (off-hours simulation against the tick cache)?

Reuse-first: NSE/BSE hours + holidays come from **pandas_market_calendars** (MIC `XNSE`),
which bakes the calendar in (no network). Crypto is 24/7 → always LIVE. Time is injected
(IST-aware `now`) so it is fully deterministic in tests.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

try:
    import pandas_market_calendars as mcal
    _HAVE_MCAL = True
except Exception:  # pragma: no cover
    _HAVE_MCAL = False

IST = timezone(timedelta(hours=5, minutes=30))
_CRYPTO = {"CRYPTO", "BINANCE", "BYBIT"}


class MarketSession:
    """Session/calendar awareness per market → LIVE vs REPLAY mode."""

    def __init__(self, market: str = "NSE", *, calendar: str = "XNSE"):
        self.market = market.upper()
        self.is_crypto = self.market in _CRYPTO
        self._cal = None
        if not self.is_crypto and _HAVE_MCAL:
            try:
                self._cal = mcal.get_calendar(calendar)
            except Exception:
                self._cal = None

    @staticmethod
    def now_ist() -> datetime:
        return datetime.now(IST)

    def is_open(self, when: datetime | None = None) -> bool:
        """Is the market open at `when` (IST-aware; defaults to now)?"""
        if self.is_crypto:
            return True                                  # 24/7
        when = when or self.now_ist()
        if when.tzinfo is None:
            when = when.replace(tzinfo=IST)
        if self._cal is None:                            # no calendar → fall back to clock
            return self._clock_open(when)
        day = when.astimezone(IST).date()
        try:
            sched = self._cal.schedule(start_date=day, end_date=day)
            if sched.empty:                              # weekend / holiday
                return False
            ts = pd.Timestamp(when.astimezone(timezone.utc))
            return bool(self._cal.open_at_time(sched, ts))
        except Exception:
            return self._clock_open(when)

    @staticmethod
    def _clock_open(when: datetime) -> bool:
        """Fallback: NSE 09:15–15:30 IST, Mon–Fri (ignores holidays)."""
        t = when.astimezone(IST)
        if t.weekday() >= 5:
            return False
        mins = t.hour * 60 + t.minute
        return 9 * 60 + 15 <= mins <= 15 * 60 + 30

    def mode(self, when: datetime | None = None) -> str:
        """'LIVE' when the market is open, else 'REPLAY' (NSE off-hours)."""
        return "LIVE" if self.is_open(when) else "REPLAY"

    def next_session_bounds(self, when: datetime | None = None) -> dict:
        """Next (open, close) for NSE; None for crypto (always open)."""
        if self.is_crypto or self._cal is None:
            return {"market": self.market, "always_open": self.is_crypto}
        when = when or self.now_ist()
        try:
            sched = self._cal.schedule(
                start_date=when.astimezone(IST).date(),
                end_date=(when.astimezone(IST) + timedelta(days=7)).date())
            if sched.empty:
                return {"market": self.market, "next_open": None, "next_close": None}
            return {"market": self.market,
                    "next_open": str(sched.iloc[0]["market_open"]),
                    "next_close": str(sched.iloc[0]["market_close"])}
        except Exception:
            return {"market": self.market, "next_open": None, "next_close": None}

    def status(self, when: datetime | None = None) -> dict:
        return {"market": self.market, "is_crypto": self.is_crypto,
                "is_open": self.is_open(when), "mode": self.mode(when),
                "calendar": "XNSE" if self._cal is not None else
                ("24/7" if self.is_crypto else "clock-fallback")}
