# Mission restarts starve the measurement they serve
Every loop restart wipes the mirror's in-RAM history — OPE labeling, regime classification
and 4h ledger resolution all restart their warm-up clocks. Three mission restarts in one
morning kept OPE at 0 labeled / 1,146 skipped. Rule: batch code changes, reload ONCE, then
freeze restarts until the data thresholds hit. Uptime is a measurement input. SUPERSEDED same day: candles now persist across restarts (commit 8a1f424) — the freeze became unnecessary. The general form: persist any RAM state that measurements warm up from. SUPERSEDED same day: candles now persist across restarts (commit 8a1f424) — the freeze became unnecessary; the lesson generalizes to: persist any RAM state that measurements warm up from.
