# Video B — "FOURIER" (@rational_edge) — why DFT cycle-hunting on price is a trap

Uploaded 2026-07-17 (Instagram reel, 25s, no speech — music + animated panels). Keyframes in `frames/`.

## The video's argument, panel by panel

- x(t) = Σ_k A_k cos(2πf_k t + φ_k) — "every chart is a sum of circles" (8 spinning epicycle vectors redraw the price).
- Takes **a pure random walk — zero cycles by construction** — and shows 8 DFT harmonics fit it beautifully ("8 cycles explain 85% of it").
- **Power spectrum "screams" a 512-day cycle carrying 39% of the power.**
- Why: **the DFT assumes your series repeats forever.** Wrapping the series creates a **68-point CLIFF at the seam** (last bar → first bar). "The cycle you found is the cliff between your last bar and your first."
- **Kill the cliff (remove the seam) → 57% of the 'cycle' vanishes** (k=3 harmonic: −91%).
- Spectra: price ~ k^-1.92 (≈1/f², the random-walk signature), **returns ~ k^+0.11 (flat = white noise, no cycles)**.
- Forecast test: fit first half with 8 harmonics → **in-sample R² = 1.000**, out-of-sample **RMSE 24.2 vs 8.5 for 'tomorrow = today' → 2.84× WORSE than naive**.
- **98.7% of random walks report a 'multi-year cycle'** under this procedure.

## Fact-check (2026-07-17)

- Random walk power spectrum ∝ 1/f² (spectral index 2): CONFIRMED (standard result; integrated white noise). The video's measured k^-1.92 matches.
- DFT periodic-extension + endpoint mismatch → spectral leakage → spurious low-frequency peak: CONFIRMED (textbook; windowing/detrending exists precisely for this).
- Returns of a random walk are white → flat spectrum: CONFIRMED (k^0.11 ≈ flat).
- Optimal forecast of a random walk IS "tomorrow = today" (martingale) — any in-sample-perfect harmonic fit must extrapolate worse: CONFIRMED by theory.
- Related classical result: Slutsky–Yule effect (filtering noise manufactures cycles). The specific numbers (512-day, 39%, 98.7%) are the author's simulation but are qualitatively right.

## Lessons binding on OUR code

1. **Never run cycle/period detection (FFT, periodogram, autocorr peaks) on PRICE levels** — only on returns/stationary transforms, detrended + windowed, with a null test against simulated random walks.
2. **In-sample R² means nothing**; every direction/cycle claim must beat the **naive martingale baseline** out-of-sample. This is the same discipline as our "baseline to beat = 29.2% win / −0.213%" and the anti-inverter rule (unproven = ABSTAIN).
3. Any strategy-foundry-generated or researched strategy citing "dominant cycle" (Ehlers-style, MESA, Hilbert) must pass the random-walk null before its enter_tag can trade.
4. Selection effect: 98.7% of pure-noise series "have" a multi-year cycle → seeing a cycle is NOT evidence. Matches CONVENTIONS §16 (direction must be earned).

## Verdict

Not a trade-opening idea — a **guardrail**: adds a falsification gate we should apply to every periodicity-flavored feature/strategy in the repo.
