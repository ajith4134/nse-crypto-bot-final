"""catalog/high_frequency.py — HFT / market-microstructure family (data-gated).

Speed- and microstructure-driven edges that need L2/L3 order book + tick feeds and low-latency
execution (Jump/HRT/Tower/Quadeye/Graviton territory). All DATA_GATED with OSS/model sources;
they plug into an L2 + tick feed and an hftbacktest-style latency-aware simulator.
"""
from __future__ import annotations

from trading.strategy.library.base import DataReq, LibraryStrategy

_CRY = ("crypto_futures", "crypto_spot")
_NSE = ("nse_futures", "nse_options")
_L2 = (DataReq.ORDERBOOK_L2,)
_L2T = (DataReq.ORDERBOOK_L2, DataReq.TICKS)


def _g(name, family, logic, segments, data_req, oss, notes=""):
    return LibraryStrategy(name=name, category="high_frequency", family=family, logic=logic,
                           segments=segments, timeframe="µs–seconds", data_req=tuple(data_req),
                           signal=None, oss_source=oss, notes=notes)


STRATEGIES = [
    _g("hft_latency_arbitrage", "latency_arb",
       "Exploit stale quotes between venues/feeds faster than they update.",
       _CRY + _NSE, _L2T, "hello2all/gamma-ray; ayan-goel/crypto_bot"),
    _g("hft_order_book_imbalance", "ob_imbalance",
       "Predict next-tick direction from bid/ask size imbalance at top levels.",
       _CRY + _NSE, _L2, "nkaz001/hftbacktest; zozoheir/hftpy"),
    _g("hft_queue_position_arb", "queue_arb",
       "Value resting queue priority; trade around expected queue advancement.",
       _CRY + _NSE, _L2, "queue-position arbitrage (Jump/HRT/Tower)"),
    _g("hft_queue_position_prediction", "queue_prediction",
       "Predict fill / queue-jump / execution likelihood for resting orders.",
       _CRY, _L2T, "queue-position prediction"),
    _g("hft_microprice_prediction", "microprice_pred",
       "Predict short-horizon mid move from the imbalance-weighted microprice.",
       _CRY + _NSE, _L2, "Stoikov microprice prediction"),
    _g("hft_order_book_alpha", "ob_alpha",
       "Composite OB-alpha: imbalance + queue + microprice deviation + cumulative delta.",
       _CRY, _L2T, "nkaz001/hftbacktest; zozoheir/hftpy"),
    _g("hft_quote_stuffing_detection", "quote_stuffing",
       "Detect quote-stuffing bursts and fade the induced micro-dislocation.",
       _CRY + _NSE, _L2T, "quote-stuffing detection"),
    _g("hft_tick_scalping", "tick_scalp",
       "Scalp 1-tick edges off microstructure signals with tight risk.",
       _CRY + _NSE, _L2T, "tick scalping"),
    _g("hft_order_anticipation", "order_anticipation",
       "Anticipate large institutional orders from footprint and front-run the impact.",
       _CRY + _NSE, _L2T, "order-anticipation"),
    _g("hft_deeplob", "neural_microstructure",
       "DeepLOB: CNN/LSTM over the limit-order-book to predict next-move direction.",
       _CRY + _NSE, _L2, "DeepLOB (Zhang et al.)", notes="neural microstructure model"),
    _g("hft_deep_ofi", "neural_microstructure",
       "Deep Order-Flow-Imbalance model for short-horizon price prediction.",
       _CRY + _NSE, _L2T, "Deep Order Flow Imbalance"),
]


# ── Wave 3: order-book imbalance + microprice get REAL flow/MM-proxy backtests. True L2-latency
# HFT (queue/latency/quote-stuffing/tick-scalp) + DeepLOB stay gated for the forward L2/tick
# collector (free historical depth is limited; DeepLOB is GPU-heavy).
from trading.strategy.library.catalog import _impl_orderflow as _hfb  # noqa: E402
_HF_BT = {"hft_order_book_imbalance": _hfb.bt_order_book_imbalance,
          "hft_microprice_prediction": _hfb.bt_microprice}
for _s in STRATEGIES:
    if _s.name in _HF_BT and any('crypto' in seg for seg in _s.segments):
        _s.backtest = _HF_BT[_s.name]
        _s.notes = (_s.notes + " · REAL: flow/microprice proxy (L2 grows forward)").strip(" ·")
