"""trading/strategy/library/catalog/ — the strategy definitions, one module per family group.

Executable-on-OHLCV families (real signal functions, real backtest):
  trend, mean_reversion, momentum, breakout, volatility, volume_flow, pattern, multi_indicator

Data-gated families (full spec + OSS source + data requirements; backtest lights up when the
feed carries the needed columns):
  statistical_arbitrage, market_making, high_frequency, order_flow, options,
  event_macro, machine_learning

The registry imports each module's `STRATEGIES` list.
"""
