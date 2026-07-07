"""trading/uq/conformal.py — conformal trade-outcome calibration (Pillar 17).

The brain must know *what it does not know*, with a distribution-free guarantee.
This module calibrates on the CLOSED-TRADES JOURNAL (the ground truth of what the
brain's entries actually returned) and gives every candidate entry:

  * ``p_up``            — calibrated P(trade nets > 0), from a crepes Conformal
                          Predictive System (calibrated CDF of ``net_pnl_pct``)
                          over features [confidence, side, market, psychology].
  * ``interval``        — coverage-guaranteed return interval (default 90%);
                          its WIDTH is the honest uncertainty of the forecast.
  * ``self_uncertainty``— normalized vote entropy of the strategy ensemble
                          (how much the brain disagrees with itself).
  * ``abstain``         — the gate. ``p_up < θ`` or interval width above the
                          adaptive cap or extreme self-uncertainty → the brain
                          stays flat, and the abstention is LOGGED as a
                          first-class decision (never a silent skip).

Reused OSS (never reimplemented): ``crepes`` WrapRegressor/CPS (calibrated CDF →
p_up + intervals), ``MAPIE`` SplitConformalRegressor (auxiliary cross-check
interval), ``netcal`` ECE (nightly reliability), plus the project's existing
``cognition.calibration.CalibratedAbstainer`` (MAPIE+netcal selective gate on
confidence→win history) once it has ≥30 (confidence, outcome) pairs.

Degrades honestly: with a thin journal (<_MIN_FIT rows) or a missing library the
engine reports ``fallback`` (Beta-posterior win-rate + raw pnl quantiles) and
still gates — it never crashes and never blocks a tick (>200 ms rule: the first
fit runs in a background thread; callers get the fallback until it is ready).
"""
from __future__ import annotations

import math
import os
import threading
import time

import numpy as np

from trading import state

STATE_FILE = "uq_calibration.json"        # last calibration summary (reliability, ECE…)
ABSTAIN_FILE = "uq_abstentions.json"      # rolling log of first-class abstentions
_MIN_FIT = 120                            # journal rows needed for the conformal engine
_MAX_ABSTAIN = 300
_PNL_CLIP = 30.0                          # clip net_pnl_pct into [-30, 30] for fitting


def self_uncertainty_from_votes(longs, shorts) -> float | None:
    """Normalized binary entropy of the ensemble's long/short vote split ∈ [0, 1].

    1.0 = perfect 50/50 disagreement (the brain has no idea), 0.0 = unanimous.
    This is the honest CPU stand-in for LLM semantic entropy: it measures how
    much the strategy ensemble disagrees with itself on THIS decision.
    """
    try:
        l, s = float(longs), float(shorts)
    except (TypeError, ValueError):
        return None
    n = l + s
    if n <= 0:
        return None
    p = l / n
    if p <= 0.0 or p >= 1.0:
        return 0.0
    return round(-(p * math.log2(p) + (1 - p) * math.log2(1 - p)), 4)


def _feat(conf, direction, market, psych) -> list[float]:
    side = -1.0 if str(direction or "LONG").upper() in ("SHORT", "SELL") else 1.0
    mkt = 1.0 if str(market or "CRYPTO").upper() == "CRYPTO" else 0.0
    c = 0.5 if conf is None else min(1.0, max(0.0, float(conf)))
    ps = 0.0 if psych is None else min(1.0, max(-1.0, float(psych)))
    return [c, side, mkt, ps]


def _trade_conf(t: dict):
    """Entry confidence of a closed-trade dict (column, else decision snapshot)."""
    c = t.get("brain_confidence_entry")
    if c is None:
        snap = t.get("decision_snapshot") or {}
        brain = snap.get("brain") if isinstance(snap, dict) else None
        if isinstance(brain, dict):
            c = brain.get("confidence")
    try:
        c = float(c)
        return c / 100.0 if c > 1.0 else c
    except (TypeError, ValueError):
        return None


class TradeUQ:
    """Conformal p_up + interval + abstention gate over the closed-trades journal."""

    def __init__(self, *, confidence_level: float = 0.9,
                 p_up_min: float | None = None, width_cap: float | None = None):
        self.confidence_level = float(confidence_level)
        self.p_up_min = float(p_up_min if p_up_min is not None
                              else os.environ.get("UQ_P_UP_MIN", 0.55))
        self._width_cap_override = (float(width_cap) if width_cap is not None else
                                    (float(os.environ["UQ_WIDTH_CAP"])
                                     if os.environ.get("UQ_WIDTH_CAP") else None))
        # UQ_GATE=0 → advisory mode: assess/log everything but never block an entry
        # (paper-mode data collection). Default ON — Pillar 17 gate is the norm. Env wins; else
        # config.json 'uq_gate' (live-truth) so a restart keeps the operator's choice.
        _uqg = os.environ.get("UQ_GATE")
        if _uqg is None:
            try:
                import json
                with open("/home/karan18190164/trading/crypto/freqtrade/config.json") as _fh:
                    _uqg = str(json.load(_fh).get("uq_gate", "1"))
            except Exception:
                _uqg = "1"
        self.enforce = _uqg not in ("0", "false", "off")
        self.engine = "warming"
        self._alpha_t = 1.0 - float(confidence_level)   # ACI-adapted miscoverage
        self._wrap = None                 # crepes WrapRegressor (CPS-calibrated)
        self._mapie_width = None          # MAPIE aux mean interval width (cross-check)
        self._abstainer = None            # cognition CalibratedAbstainer (conf→win gate)
        self._width_cap = None            # adaptive: 1.25 × p90 of holdout widths
        self._fallback = {"win_rate": 0.5, "q_lo": -5.0, "q_hi": 5.0, "n": 0}
        self._summary: dict = {}
        self._fitted_at = 0.0
        self._lock = threading.Lock()
        self._fitting = False

    # ── calibration ────────────────────────────────────────────────────────────────
    def _load_trades(self) -> list[dict]:
        from trading.journal.journal import TradeJournal
        rows = [t.to_dict() for t in TradeJournal().trades]
        rows.sort(key=lambda t: str(t.get("exit_datetime") or ""))   # chronological
        return rows

    def recalibrate(self, trades: list[dict] | None = None) -> dict:
        """(Re)fit on the journal. Chronological 60/20/20 train/calibrate/evaluate
        split (no shuffling — respects the time series). Returns the summary."""
        rows = trades if trades is not None else self._load_trades()
        X, y, won, confs = [], [], [], []
        for t in rows:
            pnl = t.get("net_pnl_pct")
            if pnl is None:
                continue
            c = _trade_conf(t)
            market = "CRYPTO" if "/" in str(t.get("symbol", "")) else "NSE"
            X.append(_feat(c, t.get("direction"), market, t.get("trader_psychology")))
            y.append(max(-_PNL_CLIP, min(_PNL_CLIP, float(pnl))))
            won.append(1 if float(t.get("net_pnl") or 0.0) > 0 else 0)
            confs.append(c)
        n = len(y)
        self._fit_fallback(np.asarray(y, float), np.asarray(won, int))
        summary = {"ts": time.time(), "n_trades": n, "confidence_level": self.confidence_level,
                   "p_up_min": self.p_up_min, "pnl_clip_pct": _PNL_CLIP}
        if n >= _MIN_FIT:
            try:
                summary.update(self._fit_conformal(np.asarray(X, float),
                                                   np.asarray(y, float),
                                                   np.asarray(won, int)))
                self.engine = "crepes_cps"
            except Exception as e:
                self.engine = "fallback"
                summary["fit_error"] = f"{type(e).__name__}: {e}"[:160]
        else:
            self.engine = "fallback"
            summary["fit_error"] = f"only {n} rows (<{_MIN_FIT}) — quantile fallback"
        self._fit_abstainer(confs, won)
        summary["engine"] = self.engine
        summary["width_cap"] = self.width_cap()
        self._summary = summary
        self._fitted_at = time.time()
        try:
            state.save_json(STATE_FILE, summary)
        except Exception:
            pass
        return summary

    def _fit_conformal(self, X, y, won) -> dict:
        from crepes import WrapRegressor
        from sklearn.ensemble import HistGradientBoostingRegressor
        n = len(y)
        cut, cut2 = int(n * 0.6), int(n * 0.8)
        wrap = WrapRegressor(HistGradientBoostingRegressor(max_iter=80))
        wrap.fit(X[:cut], y[:cut])
        wrap.calibrate(X[cut:cut2], y[cut:cut2], cps=True)
        # ── held-out evaluation: empirical coverage + adaptive width cap + reliability ──
        Xe, ye, we = X[cut2:], y[cut2:], won[cut2:]
        lohi = wrap.predict_int(Xe, confidence=self.confidence_level)
        static_coverage = float(np.mean((ye >= lohi[:, 0]) & (ye <= lohi[:, 1])))
        # ── ACI (Gibbs & Candès adaptive conformal): replay the holdout in time order,
        # updating α_t so the intervals ADAPT to distribution shift. Static split
        # conformal under-covers on non-stationary markets (observed 0.64 vs 0.90);
        # the adapted α_t is what live predictions use. ──
        self._wrap = wrap
        alpha, gamma = 1.0 - self.confidence_level, 0.02
        alpha_t, errs = alpha, 0
        for i in range(len(ye)):
            conf_t = min(0.99, max(0.5, 1.0 - alpha_t))
            lh = wrap.predict_int(Xe[i:i + 1], confidence=conf_t)[0]
            err = 0 if lh[0] <= ye[i] <= lh[1] else 1
            errs += err
            alpha_t = min(0.5, max(0.005, alpha_t + gamma * (alpha - err)))
        self._alpha_t = alpha_t
        aci_coverage = round(1.0 - errs / max(1, len(ye)), 4)
        lohi = wrap.predict_int(Xe, confidence=min(0.99, max(0.5, 1.0 - alpha_t)))
        widths = lohi[:, 1] - lohi[:, 0]
        p_up = 1.0 - np.asarray(wrap.predict_p(Xe, y=np.zeros(len(Xe)))).ravel()
        self._width_cap = float(np.percentile(widths, 90) * 1.25)
        out = {"coverage_holdout_static": round(static_coverage, 4),
               "coverage_holdout_aci": aci_coverage,
               "alpha_adapted": round(alpha_t, 4),
               "mean_width": round(float(np.mean(widths)), 3),
               "n_holdout": int(len(ye)),
               "reliability": self._reliability_bins(p_up, we)}
        out["ece_p_up"] = self._ece(p_up, we)
        out["mapie_mean_width"] = self._fit_mapie_aux(X, y, cut, cut2)
        return out

    def _fit_mapie_aux(self, X, y, cut, cut2):
        """MAPIE split-conformal as an auxiliary cross-check on interval width."""
        try:
            from mapie.regression import SplitConformalRegressor
            from sklearn.linear_model import Ridge
            m = SplitConformalRegressor(estimator=Ridge(),
                                        confidence_level=self.confidence_level,
                                        prefit=False)
            m.fit(X[:cut], y[:cut])
            m.conformalize(X[cut:cut2], y[cut:cut2])
            _, iv = m.predict_interval(X[cut2:])
            w = float(np.mean(iv[:, 1, 0] - iv[:, 0, 0]))
            self._mapie_width = round(w, 3)
            return self._mapie_width
        except Exception:
            return None

    @staticmethod
    def _ece(p_up, won):
        try:
            from netcal.metrics import ECE
            return round(float(ECE(10).measure(np.asarray(p_up, float),
                                               np.asarray(won, int))), 4)
        except Exception:
            return None

    @staticmethod
    def _reliability_bins(p_up, won, n_bins: int = 10) -> list[dict]:
        """Predicted-vs-realized bins for the dashboard reliability diagram."""
        bins = []
        edges = np.linspace(0.0, 1.0, n_bins + 1)
        for i in range(n_bins):
            m = (p_up >= edges[i]) & (p_up < edges[i + 1] if i < n_bins - 1
                                      else p_up <= edges[i + 1])
            k = int(m.sum())
            bins.append({"bin": round(float((edges[i] + edges[i + 1]) / 2), 2),
                         "n": k,
                         "predicted": round(float(np.mean(p_up[m])), 4) if k else None,
                         "realized": round(float(np.mean(won[m])), 4) if k else None})
        return bins

    def _fit_fallback(self, y, won) -> None:
        if len(y):
            self._fallback = {"win_rate": float((won.sum() + 1) / (len(won) + 2)),  # Beta(1,1)
                              "q_lo": float(np.quantile(y, (1 - self.confidence_level) / 2)),
                              "q_hi": float(np.quantile(y, 1 - (1 - self.confidence_level) / 2)),
                              "n": int(len(y))}

    def _fit_abstainer(self, confs, won) -> None:
        """The project's existing MAPIE+netcal selective gate, on (confidence, win)
        pairs — engaged only once ≥30 real confidence-carrying trades exist."""
        pairs = [(c, w) for c, w in zip(confs, won) if c is not None]
        if len(pairs) < 30:
            self._abstainer = None
            return
        try:
            from cognition.calibration import CalibratedAbstainer
            ab = CalibratedAbstainer(confidence_level=self.confidence_level)
            ab.calibrate([p[0] for p in pairs], [p[1] for p in pairs])
            self._abstainer = ab if ab.engine.startswith("conformal") else None
        except Exception:
            self._abstainer = None

    # ── lazy, non-blocking readiness (no tick may block >200 ms) ───────────────────
    def _ensure_fit_async(self) -> None:
        if self._wrap is not None or self.engine == "fallback":
            return
        with self._lock:
            if self._fitting:
                return
            self._fitting = True

        def _bg():
            try:
                self.recalibrate()
            except Exception:
                self.engine = "fallback"
            finally:
                self._fitting = False

        threading.Thread(target=_bg, daemon=True, name="uq-calibrate").start()

    def maybe_recalibrate(self, max_age_h: float = 6.0) -> dict | None:
        """Refit when the calibration is older than ``max_age_h`` (learn-loop hook)."""
        if time.time() - self._fitted_at < max_age_h * 3600:
            return None
        return self.recalibrate()

    def width_cap(self) -> float:
        if self._width_cap_override is not None:
            return self._width_cap_override
        if self._width_cap is not None:
            return self._width_cap
        return max(1.0, (self._fallback["q_hi"] - self._fallback["q_lo"]) * 1.25)

    # ── the per-decision assessment ─────────────────────────────────────────────────
    def assess(self, *, confidence=None, direction="LONG", market="CRYPTO",
               psych=None, longs=None, shorts=None, symbol: str = "") -> dict:
        """Calibrated {p_up, interval, width, self_uncertainty, abstain, size_scale}
        for ONE candidate entry. Never raises; never blocks on fitting."""
        self._ensure_fit_async()
        su = self_uncertainty_from_votes(longs, shorts)
        if su is None and confidence is not None:
            # derive from confidence: agreement a=conf → p=(1+a)/2 vote split entropy
            p = min(1.0 - 1e-9, max(1e-9, (1.0 + float(confidence)) / 2.0))
            su = round(-(p * math.log2(p) + (1 - p) * math.log2(1 - p)), 4)
        p_up, lo, hi = self._predict(confidence, direction, market, psych)
        width = round(hi - lo, 4)
        cap = self.width_cap()
        abstain, reason = False, ""
        if p_up < self.p_up_min:
            abstain, reason = True, (f"p_up {p_up:.2f} < θ {self.p_up_min:.2f} "
                                     f"(calibrated win probability too low)")
        elif width > cap:
            abstain, reason = True, (f"interval width {width:.1f}% > cap {cap:.1f}% "
                                     f"(forecast too uncertain to size)")
        elif su is not None and su >= 0.97:
            abstain, reason = True, (f"self-uncertainty {su:.2f} (ensemble ~50/50 split "
                                     f"— the brain disagrees with itself)")
        elif self._abstainer is not None and confidence is not None:
            d = self._abstainer.decide(float(confidence))
            if d.get("abstain"):
                abstain, reason = True, f"confidence gate: {d.get('reason', 'below τ')}"
        would_abstain = abstain
        if abstain and not self.enforce:
            abstain, reason = False, f"advisory (UQ_GATE=0): {reason}"
        size_scale = 1.0
        if not abstain and su is not None and su >= 0.85:
            size_scale = 0.5           # high (not extreme) disagreement → half size
        out = {"p_up": round(float(p_up), 4), "interval": [round(lo, 3), round(hi, 3)],
               "interval_width": width, "width_cap": round(cap, 3),
               "self_uncertainty": su, "abstain": abstain,
               "would_abstain": would_abstain, "abstain_reason": reason,
               "size_scale": size_scale, "p_up_min": self.p_up_min,
               "confidence_level": self.confidence_level, "engine": self.engine}
        if would_abstain and symbol:
            self.log_abstention(symbol=symbol, market=market, direction=direction, uq=out)
        return out

    def _predict(self, confidence, direction, market, psych):
        if self._wrap is not None:
            try:
                x = np.asarray([_feat(confidence, direction, market, psych)], float)
                conf_t = min(0.99, max(0.5, 1.0 - self._alpha_t))
                lohi = self._wrap.predict_int(x, confidence=conf_t)
                p_up = 1.0 - float(np.asarray(
                    self._wrap.predict_p(x, y=np.zeros(1))).ravel()[0])
                return p_up, float(lohi[0, 0]), float(lohi[0, 1])
            except Exception:
                pass
        fb = self._fallback
        c = 0.5 if confidence is None else min(1.0, max(0.0, float(confidence)))
        # Beta-posterior base rate, nudged by the (uncalibrated) confidence — honest
        # small weight since the fallback has no per-feature model.
        p_up = min(0.99, max(0.01, fb["win_rate"] + (c - 0.5) * 0.3))
        return p_up, fb["q_lo"], fb["q_hi"]

    # ── first-class abstention log ──────────────────────────────────────────────────
    def log_abstention(self, *, symbol: str, market: str, direction: str, uq: dict) -> None:
        try:
            log = state.load_json(ABSTAIN_FILE, [])
            log.append({"ts": time.time(), "symbol": symbol, "market": str(market).upper(),
                        "direction": direction, "p_up": uq.get("p_up"),
                        "interval_width": uq.get("interval_width"),
                        "self_uncertainty": uq.get("self_uncertainty"),
                        "reason": uq.get("abstain_reason"), "engine": uq.get("engine")})
            state.save_json(ABSTAIN_FILE, log[-_MAX_ABSTAIN:])
        except Exception:
            pass

    def abstentions(self, limit: int = 50) -> list[dict]:
        try:
            return list(state.load_json(ABSTAIN_FILE, []))[-limit:][::-1]
        except Exception:
            return []

    def status(self) -> dict:
        s = dict(self._summary) if self._summary else dict(
            state.load_json(STATE_FILE, {}) or {})
        s.update({"engine": self.engine, "p_up_min": self.p_up_min,
                  "gate_enforced": self.enforce,
                  "alpha_adapted": round(self._alpha_t, 4),
                  "width_cap": round(self.width_cap(), 3),
                  "fitted_at": self._fitted_at or s.get("ts"),
                  "fallback": self._fallback,
                  "abstainer_active": self._abstainer is not None,
                  "n_abstentions_logged": len(state.load_json(ABSTAIN_FILE, []) or [])})
        return s


_UQ: TradeUQ | None = None
_UQ_LOCK = threading.Lock()


def get_uq() -> TradeUQ:
    """Process-wide singleton (mirrors get_brain()/get_memory() conventions)."""
    global _UQ
    with _UQ_LOCK:
        if _UQ is None:
            _UQ = TradeUQ()
        return _UQ
