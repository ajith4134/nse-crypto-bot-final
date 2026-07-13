"""trading/brain/trade_learn.py — one market-scoped brain-learning hook per closed trade.

Both markets learn through here, kept STRICTLY SEPARATE: crypto and NSE are different
markets, so their recipes are different instruction neurons and their outcomes credit
different genius-use domains (trade:crypto vs trade:nse). A crypto recipe can never be
applied to an NSE decision and vice-versa (the market is part of the instruction identity;
see induction._key and apply.select). Called from freqtrade_ingest (crypto) and
journal.record (NSE) so every close, in either market, feeds the right side of the brain.

Fail-open: learning must never break trade recording.
"""
from __future__ import annotations


def learn_from_closed(*, market: str, strategy: str, regime: str, direction: str,
                      win: bool, net_pnl: float = 0.0, symbol: str = "",
                      consulted_ids=None) -> None:
    market = (market or "").strip().lower() or "crypto"
    try:
        from trading.brain import brain_os as _bos, induction as _ind
        if consulted_ids:                              # grade the neurons fuse() consulted
            _bos.grade(list(consulted_ids), win=bool(win), pnl=float(net_pnl or 0.0),
                       domain=f"trade:{market}")       # market-scoped domain = brain knows
        _ind.induce_from_trade(market=market, strategy=strategy, regime=regime,
                               direction=direction, win=bool(win),
                               net_pnl=float(net_pnl or 0.0), symbol=symbol)
    except Exception:
        pass                                           # fail-open
