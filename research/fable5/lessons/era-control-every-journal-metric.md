# Era-control (and de-poison) every journal/ledger metric before quoting it

2026-07-16: the project's three headline numbers (40.3% realized, 36.5% exit, 55.2% 4h) were all
era artifacts — the system changed regime around 7/11 (crypto realized 0.361→0.523). Also found
456 poisoned journal rows (USDT|NSE|momentum, qty 66M, ~₹45M fake profit each, sum ₹3.86B) that
make any naive journal P&L readout garbage; they also fed ~400 fake labels into momentum|NSE exit
buckets. Rules: (1) always split metrics by era around known system changes; (2) filter/flag
absurd-magnitude rows before summing P&L; (3) the ledger's `taken|4h` aggregate mixes eras AND
label methods (feather 0.544 vs probe 0.328) — never quote it unqualified.
