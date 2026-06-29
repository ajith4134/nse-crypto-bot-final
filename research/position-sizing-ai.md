# Position Sizing for Trades — Capital Allocation Layer (NSE + Crypto)

> Ranked, cited OSS research for a real **position-sizing layer** that decides
> *how much capital to deploy per trade* from `{capital, entry, stop/ATR,
> win-rate/edge, volatility}`, for **long and short**, **paper** trades on
> NSE (OpenAlgo) + crypto (ccxt). CPU-only, pip-first.
>
> **Date:** 2026-06-29 · **Scope:** classical sizing, AI/ML/RL sizing, risk
> overlays, and how to build on our existing `riskfolio` wiring in
> `trading/advintel/portfolio_risk.py`.

---

## 0. TL;DR — recommended stack

| Layer | Pick | Why |
|---|---|---|
| **Classical default sizing** | **`keeks`** (per-trade bet sizing) + **our own ATR/vol-target formula** (numpy) + **`riskfolio-lib`** (already wired, for Kelly/HRP/CVaR at portfolio level) | `keeks` gives drop-in `KellyCriterion`, `FractionalKelly`, `DrawdownAdjustedKelly`, `OptimalF`, `FixedFraction`, `CPPI` classes (MIT, fresh Oct-2025). ATR risk-per-trade is a 3-line numpy formula. Riskfolio already provides Kelly/HRP/CVaR for cross-asset weights. |
| **AI/ML sizing feature** | **`mlfinpy`** `bet_sizing` (meta-labeling → bet size, the López de Prado AFML Ch. 10 algorithms; open MIT fork of the now-gated `mlfinlab`) | Turns an ML model's *probability of a winning trade* into a calibrated bet size (`bet_size_probability`, `bet_size_dynamic`, averaging of concurrent bets). This is the cleanest "AI feature" that bolts onto our existing edge signal. |
| **RL sizing (later/optional)** | **`FinRL`** (continuous-action PPO/SAC where the action *is* the position fraction) | Heaviest option; only if we want the size learned end-to-end. CPU-trainable but slow. Treat as a Phase-T8+ experiment, not the default. |
| **Risk overlays** | `riskfolio` CVaR/max-DD + our own `portfolio_heat()` + correlation matrix (numpy/pandas) across NSE+crypto | Already half-built in `portfolio_risk.py`. |

**One-line architecture:** *edge/prob → (meta-label) → Kelly-or-ATR fraction →
clip by fractional-Kelly + per-market cap + portfolio-heat → size in capital.*

---

## 1. Classical sizing methods + OSS implementations

### Methods (what each needs as input)

| Method | Formula (long; short is symmetric) | Inputs |
|---|---|---|
| **Fixed-fractional** | `size = f · capital` (constant f, e.g. 2%) | capital, f |
| **ATR / risk-per-trade** | `units = (risk_pct · capital) / (atr_mult · ATR)`; `size = units · entry` | capital, risk_pct, ATR, stop |
| **% risk to stop** | `units = (risk_pct · capital) / |entry − stop|` | capital, entry, stop |
| **Kelly** | `f* = edge/odds` (bet) or `f* = μ/σ²` (Gaussian returns) | win-rate, payoff **or** μ, σ² |
| **Fractional / Half-Kelly** | `f = λ · f*` (λ = 0.25–0.5) | f*, λ |
| **Volatility targeting** | `f = target_vol / realized_vol` (annualized) | target σ, realized σ |
| **Risk parity / ERC** | weights s.t. each asset contributes equal risk | covariance matrix |
| **Van Tharp** | position = (account·risk%) / (entry−stop) per "R" unit; CPR/expectancy framing | capital, R, stop, expectancy |

### OSS implementations (ranked for our use)

| Library | What it gives for sizing | License | pip (verified) | CPU | Recency | Fit |
|---|---|---|---|---|---|---|
| **riskfolio-lib** ⭐ [repo](https://github.com/dcajasn/Riskfolio-Lib) · [docs](https://riskfolio-lib.readthedocs.io/) | **Logarithmic Mean Risk = Kelly** portfolio opt; HRP/HERC; 26 convex risk measures (CVaR, EVaR, CDaR…); risk-parity / ERC | BSD-3 | ✅ `7.3.0` | ✅ | active 2025 | **Already wired** in `portfolio_risk.py` — keep for portfolio-level Kelly/HRP/CVaR |
| **keeks** [repo](https://github.com/wdm0006/keeks) | **Per-bet sizing classes:** `KellyCriterion`, `FractionalKellyCriterion`, `DrawdownAdjustedKelly`, `OptimalF` (Ralph Vince), `FixedFractionStrategy`, `CPPIStrategy`, `DynamicBankrollManagement`, `MertonShare` | MIT | ✅ `0.3.0` | ✅ | **Oct 2025** | **Best per-trade default** — exactly our `{capital, edge, payoff}` → fraction layer |
| **PyPortfolioOpt** [repo](https://github.com/robertmartin8/PyPortfolioOpt) | Efficient frontier, HRP (`HRPOpt`, already fallback in our code), CVaR/CDaR, max-Sharpe; basic Kelly tooling | MIT | ✅ `1.6.0` | ✅ | active | Portfolio weights; secondary to riskfolio (we already fall back to its `HRPOpt`) |
| **vectorbt** [repo](https://github.com/polakowo/vectorbt) | `size`, `size_type` (Amount/Value/Percent/TargetPercent), ATR-based `sl_stop`, dynamic sizing in `Portfolio.from_signals` | Apache-2.0 (OSS); PRO is paid | ✅ `1.0.0`/`0.28.x` | ✅ | active | Useful for **backtesting** the sizing rule, not as the live sizer |
| **quantstats** [repo](https://github.com/ranaroussi/quantstats) | Kelly criterion metric, risk/return tear-sheets (eval, not sizing) | Apache-2.0 | ✅ `0.0.81` | ✅ | active | **Evaluation** of a sizing policy (Kelly stat, Sharpe, DD) |
| **empyrical** [repo](https://github.com/quantopian/empyrical) | Risk/return stats (Sharpe, Sortino, max-DD, vol) | Apache-2.0 | ✅ `0.5.5` | ✅ | low (legacy) | Stats only; quantstats supersedes |
| **ffn** [repo](https://github.com/pmorissette/ffn) | Performance/risk analytics, ERC (`calc_erc_weights`), inverse-vol | MIT | ✅ `1.1.5` | ✅ | active | ERC / risk-parity weights helper |
| **backtrader / zipline sizers** | `bt.Sizer` subclasses (FixedSize, PercentSizer, AllInSizer); zipline `order_percent`/`order_target_percent` | GPL-3 (backtrader) / Apache (zipline) | n/a (heavy/legacy) | ✅ | low | Pattern reference only — **don't pull as a dep** (GPL/legacy) |
| **scikit-portfolio** | sklearn-style portfolio estimators | BSD | ❌ **not on PyPI** | — | — | Skip (not pip-installable; git-vendor only if needed) |

**Van Tharp** sizing has **no canonical maintained pip library** — it's the
`% risk / (entry−stop)` formula plus expectancy/R-multiple bookkeeping, best
implemented directly (≈10 lines) on top of our trade journal. `keeks`'
`DrawdownAdjustedKelly` + `FixedFractionStrategy` cover the spirit of it.

---

## 2. AI / ML / RL-based sizing

### 2a. Meta-labeling → bet size (López de Prado, AFML Ch. 10) — **recommended AI feature**

The cleanest, lowest-risk "AI sizing" is **meta-labeling**: a primary signal
says *direction*; a secondary ML classifier predicts *P(this trade wins)*; that
probability is mapped to a **bet size** via a calibrated function. This is
Chapter 10 of *Advances in Financial Machine Learning*.

| Library | Module / functions | License | pip | Notes |
|---|---|---|---|---|
| **mlfinpy** [repo](https://github.com/baobach/mlfinpy) · [docs](https://mlfinpy.readthedocs.io/) | `bet_sizing`: `bet_size_probability`, `bet_size_dynamic`, `bet_size_budget`, `avg_active_signals`, `discrete_signal`; plus triple-barrier + meta-labeling to *produce* the probabilities | MIT (open) | ✅ **`0.1.2`** | **Open fork** of the López de Prado bet-sizing code. **Use this.** |
| **mlfinlab** (Hudson & Thames) [repo](https://github.com/hudson-and-thames/mlfinlab) | Original `bet_sizing/bet_sizing.py` (`bet_size_probability`, EF3M, averaging active bets) | **now closed/commercial** | ❌ **No PyPI** (`pip` fails) | Reference for the algorithms; **code is gated** — use `mlfinpy` instead |
| **Meta_Labeling** [repo](https://github.com/dreyhsu/Meta_Labeling) | Worked example of meta-labeling → bet size | MIT | n/a (vendor) | Example/teaching repo |

**How it maps to us:** we already estimate edge/win-rate per strategy. Feed
that probability into `mlfinpy.bet_sizing.bet_size_probability(prob, pred,
num_classes, step_size)` → signed bet size in `[-1, 1]`, multiply by capital
(and our fractional-Kelly / cap overlays). Works for **shorts** natively
(prediction sign).

### 2b. Reinforcement-learning sizing — optional / heavier

In RL trading, the **action itself is the position fraction** (continuous
action ∈ [−1, 1] = short↔long), so the agent *learns* sizing jointly with
timing. Powerful but data-hungry and harder to trust for live capital.

| Library | Sizing angle | License | pip | CPU | Fit |
|---|---|---|---|---|---|
| **FinRL** ⭐ [repo](https://github.com/AI4Finance-Foundation/FinRL) | Continuous-action agents (A2C/DDPG/PPO/TD3/SAC via Stable-Baselines3); action vector = target weights/positions → portfolio allocation **is** the sizing | MIT | ✅ `0.3.7` | ✅ (slow) | Best-supported RL allocator; treat as experiment |
| **TensorTrade** [repo](https://github.com/tensortrade-org/tensortrade) | Composable `ActionScheme` (e.g. proportion of balance) → sizing as action | Apache-2.0 | ✅ `1.0.4` | ✅ | Flexible but less maintained; crypto-friendly |
| **keeks** (again) | Not RL, but `DynamicBankrollManagement` adapts size to recent performance — a lightweight "learning" sizer without an RL stack | MIT | ✅ | ✅ | Cheap middle-ground before full RL |

### 2c. Bayesian / uncertainty-aware Kelly

Full Kelly assumes the edge is *known*; with finite samples it isn't, and full
Kelly can cause >50% drawdowns. **Bayesian Kelly** treats win-prob as a
Beta-distributed belief and shrinks size with uncertainty (reported ~40–60%
lower max-DD while keeping 85–95% of growth — [SSRN 6195358](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6195358),
[Downey sims](https://matthewdowney.github.io/uncertainty-kelly-criterion-optimal-bet-size.html)).
No single maintained pip lib; implement as: shrink `f*` by sample-size
confidence, then take fractional Kelly. `keeks.DrawdownAdjustedKelly` and
fractional-Kelly cover the practical version.

---

## 3. Risk overlays that complement sizing

| Overlay | Source | Where it lives for us |
|---|---|---|
| **Max-drawdown cap** | `riskfolio` CDaR/max-DD objective; `quantstats`/our `max_drawdown()` | gate: cut size when rolling DD breaches limit |
| **Per-market exposure limit** | our own caps (NSE vs crypto capital pools) | hard clip after sizing |
| **Portfolio heat** (∑ capital-at-risk / capital) | **already built**: `portfolio_heat()` in `portfolio_risk.py` | reject/scale trade if heat > threshold |
| **Correlation-aware sizing** across NSE+crypto | pandas corr / `riskfolio` HRP/ERC; `ffn.calc_erc_weights` | scale down correlated concurrent bets |
| **Kelly-with-uncertainty** | fractional Kelly + Bayesian shrink (§2c) | multiply f* by confidence factor |
| **Vol targeting cap** | `target_vol / realized_vol` (numpy) | normalize size to constant risk |

---

## 4. Map to our stack

We already have, in **`trading/advintel/portfolio_risk.py`** (BSD riskfolio +
pypfopt with numpy fallbacks):
- `kelly_fraction()` — Gaussian Kelly `μ/σ²`, half-Kelly, capped
- `var()` / `cvar()` — historical tail risk
- `hrp_weights()` — riskfolio HCPortfolio HRP (→ pypfopt → inverse-var)
- `optimize()` — MinRisk / Sharpe / CVaR weights
- `max_drawdown()`, `portfolio_heat()`

**Gap:** there is **no per-trade sizer** that turns
`{capital, entry, stop/ATR, win-rate/edge, volatility}` into a *dollar/units*
size. Everything above is portfolio-level (weights) or risk metrics. That is
the layer to add.

### Per-trade sizer inputs → method → library

| You have… | Use method | Library / call |
|---|---|---|
| capital + fixed % only | Fixed-fractional | `keeks.FixedFractionStrategy` (or 1 line) |
| capital + entry + **stop/ATR** | ATR / %-risk-to-stop | **numpy formula** `risk_pct·cap / (atr_mult·ATR)` (3 lines) |
| capital + **win-rate + payoff** | (Fractional) Kelly | `keeks.FractionalKellyCriterion` / `KellyCriterion` |
| capital + **ML P(win)** | Meta-label bet size | **`mlfinpy.bet_sizing.bet_size_probability`** |
| capital + **target vol + realized vol** | Vol targeting | numpy `target/realized` |
| multi-asset **returns matrix** (NSE+crypto) | Kelly/HRP/CVaR weights | **`riskfolio`** (already wired) → split capital |
| open positions | Heat / DD / corr overlay | **our `portfolio_heat()`** + pandas corr + `riskfolio` CVaR |

**Build-on-riskfolio plan:** keep riskfolio for the *cross-asset capital split*
(how much of total goes to each market/symbol via Kelly/HRP/CVaR); add a thin
**`position_sizer.py`** that does the *per-trade* `{entry, stop, ATR, edge}` →
units/capital, wrapping `keeks` (Kelly/fractional/DD-adjusted) + a numpy ATR
path + an optional `mlfinpy` probability path, then applies the
fractional-Kelly clip, per-market cap, and `portfolio_heat` gate. Mirror the
existing module's try/except-degrade-to-numpy pattern so it never crashes.

---

## 5. RECOMMENDED stack + decision table

### (a) Solid classical default — **2 libs + 1 formula**
1. **`keeks`** (MIT, fresh) — per-trade `FractionalKellyCriterion` /
   `DrawdownAdjustedKelly` as the default sizer.
2. **`riskfolio-lib`** (already wired) — portfolio-level Kelly/HRP/CVaR to split
   capital across NSE + crypto and feed correlation-aware caps.
3. **numpy ATR formula** — `risk_pct·capital / (atr_mult·ATR)` for the
   stop-based path (no dependency).

### (b) AI / RL sizing feature — **1 primary + 1 optional**
1. **`mlfinpy.bet_sizing`** (MIT) — meta-labeling probability → bet size. This
   is the AI feature to ship: it consumes the edge/prob we already compute and
   outputs a calibrated, signed (long/short) size.
2. **`FinRL`** (MIT, optional/later) — continuous-action RL allocator if we
   want size learned end-to-end; CPU-trainable but slow, treat as experiment.

### Decision table — {inputs → method → library}

| # | Inputs available | Sizing method | Library / implementation | Long/Short |
|---|---|---|---|---|
| 1 | capital, fixed risk % | Fixed-fractional | `keeks.FixedFractionStrategy` | both |
| 2 | capital, entry, stop **or** ATR | % risk to stop / ATR | numpy (3 lines) | both |
| 3 | capital, win-rate, payoff ratio | Fractional Kelly | `keeks.FractionalKellyCriterion` | both |
| 4 | + uncertainty / drawdown limit | DD-adjusted / Bayesian Kelly | `keeks.DrawdownAdjustedKelly` (+ confidence shrink) | both |
| 5 | capital, **ML P(win)** | Meta-label bet size | `mlfinpy.bet_sizing.bet_size_probability` | both (pred sign) |
| 6 | target vol, realized vol | Volatility targeting | numpy `target/realized` | both |
| 7 | multi-asset returns (NSE+crypto) | Kelly / HRP / CVaR weights | `riskfolio-lib` (wired) | weights |
| 8 | open positions + corr | Heat / DD / corr overlay | `portfolio_heat()` + pandas + `riskfolio` CVaR | gate |
| 9 | full data, want learned sizing | RL continuous action | `FinRL` (optional) | both |

### pip verification (against `/home/karan18190164/.venv/bin/pip`)
`riskfolio-lib 7.3.0` ✅ · `keeks 0.3.0` ✅ · `mlfinpy 0.1.2` ✅ ·
`PyPortfolioOpt 1.6.0` ✅ · `vectorbt 1.0.0` ✅ · `quantstats 0.0.81` ✅ ·
`ffn 1.1.5` ✅ · `empyrical 0.5.5` ✅ · `finrl 0.3.7` ✅ · `tensortrade 1.0.4` ✅
· **`mlfinlab` ❌ no PyPI (gated → use `mlfinpy`)** · **`scikit-portfolio` ❌ no
PyPI**.

---

## Sources
- Riskfolio-Lib — https://github.com/dcajasn/Riskfolio-Lib · https://riskfolio-lib.readthedocs.io/
- keeks (Kelly/fractional/DD/OptimalF/CPPI bet sizing, MIT, Oct-2025) — https://github.com/wdm0006/keeks
- mlfinpy (open mlfinlab fork, bet_sizing) — https://github.com/baobach/mlfinpy · https://mlfinpy.readthedocs.io/
- mlfinlab bet_sizing (original, now gated) — https://github.com/hudson-and-thames/mlfinlab/blob/master/mlfinlab/bet_sizing/bet_sizing.py · https://hudsonthames.org/mlfinlab/
- meta-labeling example — https://github.com/dreyhsu/Meta_Labeling · https://hudsonthames.org/meta-labeling-a-toy-example/
- FinRL (RL allocation/sizing) — https://github.com/AI4Finance-Foundation/FinRL
- TensorTrade — https://github.com/tensortrade-org/tensortrade
- PyPortfolioOpt — https://github.com/robertmartin8/PyPortfolioOpt
- vectorbt (sizing, ATR stops) — https://github.com/polakowo/vectorbt · https://www.marketcalls.in/python/mastering-vectorbt-position-sizing-code-snippets-part-4-python-tutorial.html
- quantstats — https://github.com/ranaroussi/quantstats
- ffn — https://github.com/pmorissette/ffn
- Bayesian Kelly with parameter uncertainty — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6195358
- Fractional Kelly under uncertainty (sims) — https://matthewdowney.github.io/uncertainty-kelly-criterion-optimal-bet-size.html
- Kelly variants overview — https://github.com/jpceia/kelly · https://github.com/thk3421-models/KellyPortfolio
- ATR / volatility-based sizing — https://www.quantifiedstrategies.com/volatility-based-position-sizing/
