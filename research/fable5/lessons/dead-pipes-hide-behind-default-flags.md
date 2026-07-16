# Check the default value of every flag guarding a write path — dead pipes hide there

2026-07-16 (Input Hunt): `orderflow_store.snapshot()` was "wired" into indicator_fusion behind
`if not _cheap`, where `_cheap = CRYPTO_UNLIMITED_OPENS != off` and the DEFAULT is on — so the
per-bar order-flow store had never written a single row, while the code read as shipped. Same
shape as the exit-label wedge (writer with no production caller) and the direction_model f_*/m_*
dead pipe. Detection rule: for any accumulating store, don't audit the code — check the OUTPUT
exists on disk and its mtime moves (`ls -la` beats reading the wiring). When wiring a write behind
a condition, test the condition's DEFAULT path actually reaches it.
