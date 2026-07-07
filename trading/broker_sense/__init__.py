"""trading/broker_sense — the Broker-Sense Funnel (owner-approved 2026-07-05).

The brain drives broker WEB APPS with its own browser + vision: the brokers' built-in
screeners narrow the whole universe for free (their servers do the compute), candle-chart
SCREENSHOTS are read by a CNN for direction, the order book is read off the rendered pixels
(non-invasive screen-mirror + OCR), and every extra datum an app shows becomes a dynamic
learning column. APIs are used ONLY for execution (paper: Zerodha-sandbox/Binance-dry;
real: hard-gated OFF until the owner's explicit go). Full design:
research/broker-sense-design.md. Replaces the wedged run_brain_loop universe scan.
"""
