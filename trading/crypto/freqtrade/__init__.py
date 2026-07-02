"""trading/crypto/freqtrade/ — managed Freqtrade config + launch helper (T-split B).

Freqtrade is the crypto execution engine. It runs as a SEPARATE self-hosted process; this
package only (a) generates a Freqtrade config.json from our central crypto_config / TRADING_MODE
so `dry_run` and the exchange always match the rest of the system, and (b) prints the exact
command to launch it. The project talks to the running bot via `CryptoEngineClient` (REST).
"""
