# Check a source's LONG-rate before trusting its ledger accuracy

Five of the fourteen truth-ledger direction sources were (near-)constant emitters on 2026-07-16:
hypothesis 100% LONG (recording bug — hint-relative support written as absolute direction,
brain_sources.py:236), live_loop 100% LONG (executed long-only NSE trades, not a lens),
river_online 96.7% LONG and symbol_move_net 99.3% SHORT (degenerate model outputs),
strategy_library 100% SHORT (constant table this window).

A constant emitter's "accuracy" is just the era's up/down base rate — it says nothing about
skill, and learned_direction "earns" fusion weight from these fake track records. Rule: any
source whose vote distribution is >85% one side is a constant, and its accuracy row must not
be cited as lens quality. Confirmed by independent re-derivation (fresh-context verifier).
