"""trading/direction/ope.py — E1: counterfactual policy evaluation over the vote log.

THE PROBLEM IT SOLVES (B2 verdict, 2026-07-16): "does the brain learn?" could never be
measured because the code keeps changing — any before/after comparison needed a code-freeze
window nobody could afford. This module measures WITHOUT freezing: the vote log
(`direction_votes.jsonl`) already stores every lane's full simultaneous vote vector, so any
candidate decider configuration can be REPLAYED over the exact readings production saw and
scored against the realized price move. Paper decisions don't move the market, so the reward
is exogenous — plain outcome replay (direct method) is valid here; no propensity weighting
is needed, unlike ad/RL off-policy settings.

Two halves, two processes (deliberate):
  • label_votes()  — runs INSIDE the funnel (the only process whose in-RAM mirror holds the
    price history needed to resolve outcomes). Incremental cursor; appends labeled rows to
    `ope_labeled.jsonl`, which persists across restarts.
  • evaluate()     — runs in an ISOLATED SUBPROCESS (`python -m trading.direction.ope
    --evaluate`). Candidate configs are applied via the LEARNED_DIR_* env vars; doing that in
    the live funnel would mutate the real decider mid-cycle, so it is forbidden here by
    design. Writes `ope_report.json` for the dashboard/foundry surfaces.

HONESTY NOTES: replay weighs sources by TODAY'S reliability, not decision-time reliability —
the report says so (`caveat` field); rows whose prices can't be resolved are counted in
`skipped`, never silently dropped (no-silent-caps). The report is measurement, not a tuner:
nothing here writes back into the live config — promoting a winning candidate stays a human
decision (CONVENTIONS §16 discipline at the config level).

Env: OPE_ENABLED (1), OPE_EVERY_S (21600), OPE_MAX_ROWS (20000), OPE_HORIZONS ("15m,1h"),
OPE_LABEL_BATCH (4000).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from trading import state

_LABELED = "ope_labeled.jsonl"
_STATE = "ope_state.json"
_REPORT = "ope_report.json"
_MAX_LABELED_LINES = 120_000            # rotate: keep newest
_KEEP_LABELED_LINES = 80_000


def _enabled() -> bool:
    return os.environ.get("OPE_ENABLED", "1") in ("1", "true", "TRUE", "yes", "on")


def _horizons() -> dict[str, int]:
    """{'15m': 900, '1h': 3600} — names must exist in truth_ledger.HORIZONS."""
    from trading.direction.truth_ledger import HORIZONS
    want = [h.strip() for h in
            (os.environ.get("OPE_HORIZONS", "15m,1h") or "15m,1h").split(",") if h.strip()]
    return {h: HORIZONS[h] * 60 for h in want if h in HORIZONS}


def _labeled_path() -> Path:
    return Path(state.STATE_DIR) / _LABELED


def _price(symbol: str, market: str, segment: str, epoch: float) -> float | None:
    """Price at `epoch`: mirror history first (every perp), feather fallback (reuses the
    truth ledger's resolution machinery so OPE labels EXACTLY like the ledger labels)."""
    from trading.direction import truth_ledger as _tl
    if (market or "").upper() == "CRYPTO":
        p = _tl._mirror_price(symbol, epoch)
        if p is not None:
            return p
    try:
        path, _basis = _tl._feather_for(symbol, (segment or "futures").lower())
        if path is not None:
            return _tl._price_at(path, epoch, after=True)
    except Exception:
        pass
    return None


def label_votes(max_rows: int | None = None) -> dict:
    """Incrementally label vote-log rows whose horizons have all matured.

    Rows are appended to the vote log in time order, so a single cursor timestamp suffices.
    A row is processed once its LONGEST horizon is due; each horizon resolves to
    {sign, move_pct} or is skipped (unresolvable prices → the whole row counts in `skipped`
    and the cursor still advances — an unresolvable row never blocks the queue)."""
    if not _enabled():
        return {"labeled": 0, "skipped": 0, "reason": "disabled"}
    hz = _horizons()
    if not hz:
        return {"labeled": 0, "skipped": 0, "reason": "no horizons"}
    max_h = max(hz.values())
    batch = int(max_rows if max_rows is not None
                else float(os.environ.get("OPE_LABEL_BATCH", "4000") or 4000))
    st = state.load_json(_STATE, {}) or {}
    cursor = float(st.get("cursor_ts") or 0.0)
    now = time.time()
    labeled = skipped = 0
    out_rows: list[str] = []
    try:
        from trading.direction.vote_log import _path as _vote_path
        with open(_vote_path(), encoding="utf-8") as fh:
            for line in fh:
                if labeled + skipped >= batch:
                    break
                try:
                    row = json.loads(line)
                except (ValueError, TypeError):
                    continue
                ts = float(row.get("ts") or 0.0)
                if ts <= cursor:
                    continue
                if now < ts + max_h:                 # file is time-ordered → nothing due beyond
                    break
                cursor = ts
                sym = str(row.get("symbol") or "")
                ref = _price(sym, row.get("market") or "CRYPTO",
                             row.get("segment") or "futures", ts)
                if ref is None or not row.get("votes"):
                    skipped += 1
                    continue
                outcomes = {}
                for name, secs in hz.items():
                    tgt = _price(sym, row.get("market") or "CRYPTO",
                                 row.get("segment") or "futures", ts + secs)
                    if tgt is None:
                        continue
                    move = (tgt - ref) / ref if ref else 0.0
                    outcomes[name] = {"sign": (1 if move > 0 else (-1 if move < 0 else 0)),
                                      "move_pct": round(100.0 * move, 5)}
                if not outcomes:
                    skipped += 1
                    continue
                out_rows.append(json.dumps({
                    "ts": ts, "symbol": sym, "market": row.get("market") or "CRYPTO",
                    "segment": row.get("segment") or "futures",
                    "regime": row.get("regime") or "unknown",
                    "lane": row.get("lane") or "", "decided": row.get("decided") or "",
                    "votes": row.get("votes"), "ref": ref, "outcomes": outcomes},
                    separators=(",", ":")))
                labeled += 1
    except FileNotFoundError:
        return {"labeled": 0, "skipped": 0, "reason": "no vote log"}
    except Exception as e:
        return {"labeled": labeled, "skipped": skipped, "error": repr(e)}
    if out_rows:
        p = _labeled_path()
        with open(p, "a", encoding="utf-8") as fh:
            fh.write("\n".join(out_rows) + "\n")
        _rotate(p)
    def _m(d: dict) -> dict:
        d["cursor_ts"] = cursor
        d["labeled_total"] = int(d.get("labeled_total") or 0) + labeled
        d["skipped_total"] = int(d.get("skipped_total") or 0) + skipped
        d["last_run"] = now
        return d
    state.mutate_json(_STATE, _m, default={})
    return {"labeled": labeled, "skipped": skipped, "cursor_ts": cursor}


def _rotate(p: Path) -> None:
    try:
        if p.stat().st_size < _MAX_LABELED_LINES * 220:
            return
        lines = p.read_text(encoding="utf-8").splitlines()
        if len(lines) > _MAX_LABELED_LINES:
            tmp = p.with_suffix(".tmp")
            tmp.write_text("\n".join(lines[-_KEEP_LABELED_LINES:]) + "\n", encoding="utf-8")
            tmp.replace(p)
    except OSError:
        pass


# ── evaluation (subprocess only — mutates LEARNED_DIR_* env per candidate) ──────────

_CANDIDATES: list[tuple[str, dict[str, str] | None]] = [
    ("logged", None),                                # what production actually decided
    ("live_cfg", {}),                                # decide() under the inherited env
    ("shrink_0", {"LEARNED_DIR_SHRINK_K": "0"}),
    ("shrink_8", {"LEARNED_DIR_SHRINK_K": "8"}),
    ("shrink_64", {"LEARNED_DIR_SHRINK_K": "64"}),
    ("edge_02", {"LEARNED_DIR_MIN_EDGE": "0.02"}),
    ("edge_05", {"LEARNED_DIR_MIN_EDGE": "0.05"}),
    ("band_01", {"LEARNED_DIR_BAND": "0.01"}),
    ("band_04", {"LEARNED_DIR_BAND": "0.04"}),
    ("min_n_15", {"LEARNED_DIR_MIN_N": "15"}),
    ("min_n_60", {"LEARNED_DIR_MIN_N": "60"}),
    ("unproven_02", {"LEARNED_DIR_UNPROVEN_W": "0.02"}),
    # MISSION X-A (2026-07-17): the evidence half-life is the highest-leverage knob the
    # clean-window drift measurements exposed — replay the plausible settings.
    ("halflife_off", {"LEDGER_HALF_LIFE_D": "0"}),   # cumulative-only (pre-mission control)
    ("halflife_05", {"LEDGER_HALF_LIFE_D": "0.5"}),
    ("halflife_1", {"LEDGER_HALF_LIFE_D": "1"}),
    ("halflife_5", {"LEDGER_HALF_LIFE_D": "5"}),
]

_ENV_KEYS = ("LEARNED_DIR_SHRINK_K", "LEARNED_DIR_MIN_EDGE", "LEARNED_DIR_BAND",
             "LEARNED_DIR_MIN_N", "LEARNED_DIR_UNPROVEN_W", "LEARNED_DIR_MIN_TOTAL_W",
             "LEDGER_HALF_LIFE_D")


def _score(rows: list[dict], side_of) -> dict:
    """Score one candidate: side_of(row) → 'long'|'short'|None (None = abstain)."""
    from trading.direction.truth_ledger import _wilson
    per_h: dict[str, dict] = {}
    for row in rows:
        side = side_of(row)
        for name, oc in (row.get("outcomes") or {}).items():
            m = per_h.setdefault(name, {"acted": 0, "hits": 0, "capture": 0.0,
                                        "abstain": 0})
            if side not in ("long", "short"):
                m["abstain"] += 1
                continue
            sgn = 1 if side == "long" else -1
            m["acted"] += 1
            if sgn * int(oc.get("sign") or 0) > 0:
                m["hits"] += 1
            m["capture"] += sgn * float(oc.get("move_pct") or 0.0)
    out = {}
    for name, m in per_h.items():
        n = m["acted"]
        rate, lo, hi = _wilson(m["hits"], n)
        out[name] = {"acted": n, "abstain": m["abstain"],
                     "hit_rate": round(rate, 4) if n else None,
                     "ci_low": round(lo, 4) if n else None,
                     "ci_high": round(hi, 4) if n else None,
                     "capture_pct_sum": round(m["capture"], 4),
                     "capture_pct_mean": round(m["capture"] / n, 5) if n else None}
    return out


def evaluate(max_rows: int | None = None) -> dict:
    """Replay every candidate config over the labeled rows; write ope_report.json.

    MUST run in its own process: candidates are applied through the LEARNED_DIR_* env vars
    and learned_direction's cache is cleared between candidates — inside the live funnel
    that would mutate the real decider."""
    from trading.direction import learned_direction as ld
    cap = int(max_rows if max_rows is not None
              else float(os.environ.get("OPE_MAX_ROWS", "20000") or 20000))
    rows: list[dict] = []
    try:
        with open(_labeled_path(), encoding="utf-8") as fh:
            for line in fh:
                try:
                    rows.append(json.loads(line))
                except (ValueError, TypeError):
                    continue
    except FileNotFoundError:
        return {"error": "no labeled rows yet"}
    rows = rows[-cap:]
    if not rows:
        return {"error": "no labeled rows yet"}
    saved = {k: os.environ.get(k) for k in _ENV_KEYS}
    results = []
    try:
        for name, env in _CANDIDATES:
            if env is None:                          # 'logged': production's own decision
                def side_of(row):
                    d = (row.get("decided") or "").lower()
                    return d if d in ("long", "short") else None
            else:
                for k, v in saved.items():           # reset, then apply the candidate diff
                    if v is None:
                        os.environ.pop(k, None)
                    else:
                        os.environ[k] = v
                os.environ.update(env)
                ld.clear_cache()

                def side_of(row):
                    out = ld.decide(list((row.get("votes") or {}).items()),
                                    market=row.get("market") or "CRYPTO",
                                    segment=row.get("segment") or "futures",
                                    regime=row.get("regime") or None,
                                    symbol=row.get("symbol") or "", log=False)
                    return None if out.get("abstained") else out.get("direction")
            results.append({"name": name, "env": env or {},
                            "metrics": _score(rows, side_of)})
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        ld.clear_cache()
    primary = (os.environ.get("OPE_PRIMARY", "1h") or "1h")
    def _rank(r):
        m = (r["metrics"].get(primary) or {})
        return m.get("capture_pct_sum") if m.get("capture_pct_sum") is not None else -1e9
    results.sort(key=_rank, reverse=True)
    st = state.load_json(_STATE, {}) or {}
    report = {"generated": time.time(), "n_rows": len(rows),
              "skipped_total": st.get("skipped_total"),
              "primary_horizon": primary,
              "caveat": ("replay weighs sources by TODAY'S truth-ledger reliability, not "
                         "decision-time reliability; 'logged' is the only row free of that skew"),
              "candidates": results}
    state.save_json(_REPORT, report)
    return report


def maybe_run() -> dict | None:
    """Funnel-side gate: label incrementally every call; spawn the evaluation subprocess
    when OPE_EVERY_S has elapsed since the last report. Never blocks, never raises."""
    if not _enabled():
        return None
    out = {"label": label_votes()}
    try:
        every = float(os.environ.get("OPE_EVERY_S", "21600") or 21600)
        rep = Path(state.STATE_DIR) / _REPORT
        stale = (not rep.exists()) or (time.time() - rep.stat().st_mtime > every)
        if stale and (out["label"].get("labeled", 0) or rep.exists() is False
                      or _labeled_path().exists()):
            subprocess.Popen(
                ["nice", "-n", "10", sys.executable, "-m", "trading.direction.ope",
                 "--evaluate"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True)
            out["evaluate"] = "spawned"
    except Exception as e:
        out["evaluate_error"] = repr(e)
    return out


def status() -> dict:
    st = state.load_json(_STATE, {}) or {}
    rep = state.load_json(_REPORT, {}) or {}
    top = None
    for c in rep.get("candidates") or []:
        if c.get("name") != "logged":
            top = c.get("name")
            break
    return {"enabled": _enabled(), "cursor_ts": st.get("cursor_ts"),
            "labeled_total": st.get("labeled_total"),
            "skipped_total": st.get("skipped_total"),
            "report_generated": rep.get("generated"), "n_rows": rep.get("n_rows"),
            "best_candidate": top}


if __name__ == "__main__":
    if "--evaluate" in sys.argv:
        r = evaluate()
        print(json.dumps({k: r.get(k) for k in ("n_rows", "primary_horizon")}
                         if "candidates" in r else r))
    else:
        print(json.dumps(label_votes()))
