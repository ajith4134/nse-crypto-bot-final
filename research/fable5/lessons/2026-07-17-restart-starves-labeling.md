# Mission restarts starve the measurement they serve
Every loop restart wipes the mirror's in-RAM history — OPE labeling, regime classification
and 4h ledger resolution all restart their warm-up clocks. Three mission restarts in one
morning kept OPE at 0 labeled / 1,146 skipped. Rule: batch code changes, reload ONCE, then
freeze restarts until the data thresholds hit. Uptime is a measurement input.
