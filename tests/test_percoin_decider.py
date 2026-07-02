"""tests/test_percoin_decider.py — brain picks the best strategy PER COIN (offline, no network).

Isolates state: a fake OHLCV feed + fake strategies, so no ccxt call, no Freqtrade, no journal
mutation. Verifies the per-coin backtest×brain blend, the stay-flat threshold, and that the chosen
strategy is carried as `tag` for enter_tag attribution.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from trading.crypto.freqtrade.percoin_decider import PerCoinBrainDecider


class _Strat:
    """Minimal stand-in for a LibraryStrategy with a deterministic signal."""
    def __init__(self, name, sig_fn):
        self.name = name
        self.segments = ("crypto_futures",)
        self.signal = sig_fn
        self._fn = sig_fn

    def make_signal(self, feats):
        return self._fn(feats)


def _trend_df(n=240, up=True):
    # a clean trend so a trend-following strategy is profitable and a contrarian one is not
    drift = 0.002 if up else -0.002
    close = 100 * np.cumprod(1 + drift + 0.0001 * np.sin(np.arange(n)))
    return pd.DataFrame({"open": close, "high": close * 1.001, "low": close * 0.999,
                         "close": close, "volume": np.full(n, 1000.0)})


def _make_decider(df, strategies):
    d = PerCoinBrainDecider(strategies=strategies, use_brain=False)  # isolate: no journal/brain
    d._ohlcv = lambda symbol: df                                     # isolate: no ccxt
    # bypass the heavy feature build — feed OHLCV straight through (fake strats ignore it). Patch the
    # SOURCE module so the `from ... import` inside decide() picks up the stub.
    import trading.strategy.library.features_ext as fx
    fx.compute_features_ext = lambda x: x
    return d


def test_picks_the_profitable_strategy_on_an_uptrend():
    df = _trend_df(up=True)
    # trend strat: always long (+1); contrarian: always short (-1)
    strats = [_Strat("TrendFollow", lambda f: pd.Series(np.ones(len(f)))),
              _Strat("Contrarian", lambda f: pd.Series(-np.ones(len(f))))]
    d = _make_decider(df, strats)
    out = d.decide("CRYPTO", "BTC/USDT:USDT", None, in_position=False)
    assert out["action"] == "LONG", out
    assert out["tag"] == "TrendFollow", out                          # chose the winner, per coin
    assert out["_brain"]["chosen_strategy"] == "TrendFollow"
    assert out["_brain"]["sharpe"] > 0


def test_stays_flat_when_no_strategy_clears_threshold():
    df = _trend_df(up=True)
    # a strategy that almost never holds a position → fails the activity guard → no candidate
    strats = [_Strat("Idle", lambda f: pd.Series(np.zeros(len(f))))]
    d = _make_decider(df, strats)
    out = d.decide("CRYPTO", "ETH/USDT:USDT", None, in_position=False)
    assert out["action"] == "FLAT", out


def test_high_threshold_forces_flat_even_with_a_winner():
    df = _trend_df(up=True)
    strats = [_Strat("TrendFollow", lambda f: pd.Series(np.ones(len(f))))]
    d = _make_decider(df, strats)
    d._min_final = 1e12                                              # nothing can clear this
    out = d.decide("CRYPTO", "SOL/USDT:USDT", None, in_position=False)
    assert out["action"] == "FLAT"
    assert out["_brain"]["reason"] == "below threshold"


def test_exit_when_best_strategy_turns_negative_while_in_position():
    df = _trend_df(up=False)                                         # downtrend
    # long-only strat is now losing → in a position the decider should EXIT
    strats = [_Strat("TrendFollow", lambda f: pd.Series(np.ones(len(f))))]
    d = _make_decider(df, strats)
    out = d.decide("CRYPTO", "BTC/USDT:USDT", None, in_position=True)
    assert out["action"] == "EXIT", out


def test_backtest_is_causal_no_lookahead():
    # constant price → zero returns → no scorable strategy (sd==0 guard)
    df = pd.DataFrame({"open": np.full(100, 50.0), "high": np.full(100, 50.0),
                       "low": np.full(100, 50.0), "close": np.full(100, 50.0),
                       "volume": np.full(100, 1.0)})
    strats = [_Strat("Always", lambda f: pd.Series(np.ones(len(f))))]
    d = _make_decider(df, strats)
    out = d.decide("CRYPTO", "BTC/USDT:USDT", None, in_position=False)
    assert out["action"] == "FLAT"
