"""trading/direction/truth_ledger.py — D1: the Direction Truth Ledger (goal Pillar 27).

Every directional decision the brain makes — whether a trade was OPENED on it or the
candidate was skipped — gets recorded here and later labeled with what price ACTUALLY
did over fixed horizons (15m/1h/4h). Aggregated per (source × regime × horizon), the
ledger answers the only question that decides profit: *who is right about direction,
when, and how often* — with Wilson confidence intervals so 3-for-4 luck never looks
like an edge.

Why it exists (measured 2026-07-10, 1,665 closed trades): direction correct 40.3%,
confidence≈1.0 bucket 29% — an anti-signal nobody could see because per-source
direction accuracy was never measured. D2 (Mirror Gate) and D6 (meta-labeler) read
this ledger; without it they are blind.

Design:
  record(...)          → one JSONL line (O_APPEND, atomic) in the state dir; callers
                         are trading loops, so it NEVER raises and does no network.
  tick(budget_s=15)    → resolve due pending rows: local feather candles first
                         (crypto, zero network), else one cheap quote probe at the
                         horizon moment (label_method is stamped honestly); fold
                         resolved labels into bucket aggregates (state.update_json,
                         cross-process safe); flock-guarded so two funnel processes
                         never double-resolve.
  backfill_journal()   → one-shot idempotent label pass over the closed-trade journal
                         (entry→exit sign = horizon "exit"; fixed horizons from
                         feathers where data exists — missing data is counted, never
                         faked).
  hit_rates()/status() → aggregates + Wilson bounds for gates and the dashboard.

Levers: DIRECTION_TRUTH=0 kills recording; DIRECTION_CANDLE_DIR overrides the feather
root; probe tolerance per horizon below.
"""
from __future__ import annotations

import fcntl
import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from trading import state

_PENDING = "direction_truth_pending.jsonl"     # unresolved decisions (append-only)
_AGG = "direction_truth.json"                  # bucket aggregates + rollups
_SEEN = "direction_truth_seen.json"            # backfill idempotency (journal row ids)
_TRAIN = "direction_truth_train.jsonl"         # labeled examples → D6 meta-labeler
_TRAIN_MAX_LINES = 60_000                      # rotate: keep the newest 40k

# fixed label horizons (minutes) + how late a probe may run and still count honestly.
# tick() cadence is one funnel cycle (2-15 min), so tolerances match horizon scale.
HORIZONS: dict[str, int] = {"15m": 15, "1h": 60, "4h": 240}
_PROBE_TOL_MIN: dict[str, int] = {"15m": 6, "1h": 15, "4h": 30}
_MAX_PENDING_AGE_S = 16 * 3600                 # unresolvable rows expire honestly as no_data
_NEUTRAL = ("", "neutral", "flat", "none")


def _enabled() -> bool:
    return os.environ.get("DIRECTION_TRUTH", "1") in ("1", "true", "TRUE", "yes", "on")


def _pending_path() -> Path:
    return Path(state.STATE_DIR) / _PENDING


# ── recording (called from trading loops — never raises, no network) ─────────────


def current_conditioners(symbol: str, market: str = "CRYPTO") -> dict:
    """E8 (2026-07-17): the two conditioners the book-state research says direction edges
    depend on — liquidity regime (flow only predicts STRESSED, ~10x power swing) and clock
    phase (power concentrates AT quarter-hour marks). Deliberately tiny label sets
    (calm|mixed|stressed × at_mark|off_mark) so conditioner buckets stay dense. Cheap
    (one RAM book read + time modulo); missing evidence → key omitted, never guessed."""
    out: dict = {}
    try:
        s = time.time() % 900.0
        out["clock"] = "at_mark" if (s < 60.0 or s > 840.0) else "off_mark"
    except Exception:
        pass
    try:
        if (market or "CRYPTO").upper() == "CRYPTO":
            from trading.brain.entry_vector import liquidity_regime
            from trading.broker_sense.binance_stream import get_mirror
            flat = str(symbol or "").replace("/", "").split(":")[0].upper()
            book = get_mirror().book(flat)
            if book and book.get("bids") and book.get("asks"):
                bid, ask = float(book["bids"][0][0]), float(book["asks"][0][0])
                mid = (bid + ask) / 2.0
                if mid > 0 and ask > bid:
                    liq = liquidity_regime((ask - bid) / mid * 1e4)
                    if liq:
                        out["liq"] = liq
    except Exception:
        pass
    return out


def record(*, symbol: str, market: str, segment: str, direction: str, source: str,
           confidence: float | None = None, regime: str | None = None,
           ts: float | None = None, taken: bool = False, trade_id: str | None = None,
           ref_price: float | None = None, features: dict | None = None,
           conditioners: dict | None = None) -> bool:
    """Append one directional decision for later truth-labeling.

    `direction` LONG/SHORT (call/put callers map CE→LONG, PE→SHORT on the underlying);
    neutral/flat verdicts are not directional claims and are skipped. `source` is the
    signal's name (strategy label, picker, fusion lens…) — the bucket key everything
    hangs off. `ref_price` (price seen at decision time) makes labeling exact; without
    it the labeler uses the candle close at ts."""
    try:
        if not _enabled():
            return False
        d = (direction or "").strip().upper()
        if d in ("BUY", "CALL", "CE"):
            d = "LONG"
        if d in ("SELL", "PUT", "PE"):
            d = "SHORT"
        if d not in ("LONG", "SHORT") or (source or "").strip() == "":
            return False
        if (str(direction).lower() in _NEUTRAL):
            return False
        if regime is None:
            try:                                  # D5: bucket by the DIRECTION regime
                if (market or "").upper() == "CRYPTO":
                    from trading.direction.regime import classify
                    regime = classify(symbol, (segment or "futures").lower()
                                      ).get("regime") or "unknown"
                else:                              # NSE: the cross-broker regime is the
                    from trading.broker_sense.broker_features import current_regime
                    regime = current_regime()      # honest market-wide label there
            except Exception:
                regime = "unknown"
        _ts = float(ts if ts is not None else time.time())
        _mkt = (market or "").upper() or "CRYPTO"
        # 100% coverage (2026-07-13): lock the entry price AT decision time from the
        # live all-market mirror mark. Without this, ref_price stays null and resolution
        # must back-fill ref from per-process in-RAM history — which a fresh/other process
        # (or a funnel restart that wipes RAM history) can't do for an old ts, leaving the
        # claim permanently no_data. Stamping here makes every crypto claim resolvable:
        # only the target price at maturity is then needed, not the ref.
        if not ref_price and _mkt == "CRYPTO":
            _mp = _mirror_price(str(symbol), _ts)
            if _mp:
                ref_price = _mp
        row = {"ts": _ts,
               "symbol": str(symbol), "market": _mkt,
               "segment": (segment or "futures").lower(), "direction": d,
               "source": str(source)[:80], "confidence": confidence,
               "regime": str(regime), "taken": bool(taken),
               "trade_id": str(trade_id) if trade_id else None,
               "ref_price": float(ref_price) if ref_price else None}
        if features:                                   # M1 stacking lens features (flat numeric)
            row["features"] = {k: features[k] for k in features if features[k] is not None}
        try:                                           # E8: stamp the decision-time conditioners
            # X-D (2026-07-17): explicit conditioners MERGE over the auto ones (liq/clock) —
            # callers add dimensions like sel:<preset> (why the scanner picked this symbol)
            # without losing the automatic stamps.
            cond = {**current_conditioners(symbol, _mkt), **(conditioners or {})}
            if cond:
                row["cond"] = {str(k): str(v) for k, v in cond.items() if v}
        except Exception:
            pass
        line = json.dumps(row, separators=(",", ":")) + "\n"
        p = _pending_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(p, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            os.write(fd, line.encode())           # single small write → atomic append
        finally:
            os.close(fd)
        return True
    except Exception:
        return False                              # trading loop safety: never raise


# ── candle access: local feathers first (zero network), tiny LRU ─────────────────

_CANDLE_CACHE: dict[str, tuple[float, object]] = {}
_CANDLE_CACHE_MAX = 24


def _candle_dir() -> Path:
    env = os.environ.get("DIRECTION_CANDLE_DIR")
    if env:
        return Path(env)
    return (Path(__file__).resolve().parent.parent
            / "crypto" / "freqtrade" / "user_data" / "data" / "binance")


def _feather_for(symbol: str, segment: str) -> tuple[Path | None, str]:
    """Map a pair to its local 5m feather. Options label their UNDERLYING perp (the
    direction claim is about the underlying); NSE has no local feathers → probe path.
    Returns (path_or_None, label_basis)."""
    try:
        sym = symbol or ""
        if sym.startswith("NSE:") or "/" not in sym:
            return None, "probe"
        base = sym.split("/")[0]
        root = _candle_dir()
        if segment == "options" or "-" in sym.split(":")[-1]:
            p = root / "futures" / f"{base}_USDT_USDT-5m-futures.feather"
            return (p if p.exists() else None), "underlying_perp"
        if ":" in sym:                             # perp futures
            quote = sym.split("/")[1].split(":")[0]
            p = root / "futures" / f"{base}_{quote}_{quote}-5m-futures.feather"
            return (p if p.exists() else None), "perp"
        quote = sym.split("/")[1]
        p = root / f"{base}_{quote}-5m.feather"    # spot
        return (p if p.exists() else None), "spot"
    except Exception:
        return None, "probe"


def _closes(path: Path):
    """(epoch_seconds_array, close_array) for a 5m feather, LRU-cached by mtime."""
    key = str(path)
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    hit = _CANDLE_CACHE.get(key)
    if hit and hit[0] == mtime:
        return hit[1]
    try:
        import pandas as pd
        df = pd.read_feather(path, columns=["date", "close"])
        ts = (df["date"].astype("int64") // 10**9).to_numpy()
        out = (ts, df["close"].to_numpy())
    except Exception:
        return None
    if len(_CANDLE_CACHE) >= _CANDLE_CACHE_MAX:
        _CANDLE_CACHE.pop(next(iter(_CANDLE_CACHE)))
    _CANDLE_CACHE[key] = (mtime, out)
    return out


def _price_at(path: Path, epoch: float, *, after: bool = False) -> float | None:
    """Close of the last candle at-or-before `epoch` (ref), or the first candle
    at-or-after it (horizon target, `after=True`); None when outside data range."""
    data = _closes(path)
    if not data:
        return None
    ts, close = data
    import bisect
    if after:
        i = bisect.bisect_left(ts.tolist(), int(epoch))
        if i >= len(ts) or ts[i] - epoch > 2 * 300:        # >2 candles late → no data
            return None
        return float(close[i])
    i = bisect.bisect_right(ts.tolist(), int(epoch)) - 1
    if i < 0 or epoch - ts[i] > 2 * 300:
        return None
    return float(close[i])


# ── training-example sink (D6 meta-labeler reads this) ───────────────────────────


def _append_train(folds) -> None:
    """One JSONL example per resolved (decision, horizon): the decision's features +
    the truth label. Best-effort (never blocks labeling); rotated so the file stays
    bounded while keeping the newest 40k examples."""
    if not folds:
        return
    try:
        p = Path(state.STATE_DIR) / _TRAIN
        p.parent.mkdir(parents=True, exist_ok=True)
        lines = []
        for row, hz, ok, method in folds:
            lines.append(json.dumps(
                {"ts": row.get("ts"), "symbol": row.get("symbol"),
                 "market": row.get("market"), "segment": row.get("segment"),
                 "direction": row.get("direction"), "source": row.get("source"),
                 "confidence": row.get("confidence"), "regime": row.get("regime"),
                 "taken": bool(row.get("taken")), "horizon": hz,
                 "features": row.get("features"),          # M1 stacking lens features
                 "correct": bool(ok), "method": method},
                separators=(",", ":")))
        fd = os.open(p, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            os.write(fd, ("\n".join(lines) + "\n").encode())
        finally:
            os.close(fd)
        try:                                   # occasional rotation, cheap line count
            if p.stat().st_size > _TRAIN_MAX_LINES * 160:
                keep = p.read_text(encoding="utf-8").splitlines()[-40_000:]
                tmp = p.with_suffix(".tmp")
                tmp.write_text("\n".join(keep) + "\n", encoding="utf-8")
                os.replace(tmp, p)
        except OSError:
            pass
    except Exception:
        pass


# ── label resolution + aggregation ────────────────────────────────────────────────


# Bucket key carries MARKET so a source firing in BOTH crypto and NSE never pools its
# hit-rate across markets (multi-market isolation, 2026-07-13). Format:
#   source | market | regime | horizon   (rsplit on '|' from the right → 4 parts).
def _bucket_key(source: str, market: str, regime: str, horizon: str) -> str:
    return f"{source}|{(market or 'CRYPTO').upper()}|{regime or 'neutral'}|{horizon}"


def _fold(agg: dict, row: dict, horizon: str, correct: bool, method: str) -> None:
    b = agg.setdefault("buckets", {}).setdefault(
        _bucket_key(row["source"], row.get("market"), row.get("regime"), horizon),
        {"n": 0, "correct": 0})
    b["n"] += 1
    b["correct"] += int(correct)
    for roll_key in (f"market|{row['market']}|{horizon}",
                     f"segment|{row['market']}|{row['segment']}|{horizon}",
                     f"direction|{row['direction']}|{horizon}",
                     f"taken|{'taken' if row.get('taken') else 'skipped'}|{horizon}"):
        r = agg.setdefault("rollups", {}).setdefault(roll_key, {"n": 0, "correct": 0})
        r["n"] += 1
        r["correct"] += int(correct)
    m = agg.setdefault("methods", {})
    m[method] = m.get(method, 0) + 1
    # MEASUREMENT QUALITY IS AUDITABLE (2026-07-16). `methods` counted HOW each label was resolved
    # but threw the outcome away — so the ledger structurally could not audit its own measurement.
    # It matters: only ~15% of 174k labels came from real candle feathers; 36% from mirror MARK
    # price (an index, not the traded price) and 44% from timing-sensitive PROBES that read the price
    # when the resolver tick fires, not at the horizon. Re-resolving the journal from feathers alone
    # gave 1h accuracy 0.5149 (+2.4σ) where the mixed ledger reported 0.4952 — a ~2pp gap, i.e. the
    # "brain is a coin flip" headline was PARTLY a measurement artifact. Rolled up per
    # (method, horizon) so any future claim can be split by the quality of its evidence.
    # Additive on purpose: the bucket key stays `source|market|regime|horizon` because hit_rates()
    # and every dashboard reader parse it — adding a 5th field there would break them and explode
    # cardinality.
    ma = agg.setdefault("method_acc", {}).setdefault(f"{method}|{horizon}", {"n": 0, "correct": 0})
    ma["n"] += 1
    ma["correct"] += int(correct)
    # E8 (2026-07-17): conditioner SUB-buckets — additive, in their own dict (the main bucket
    # key stays 4-part per the warning above). source|market|<kind>:<value>|horizon, so the
    # driver can ask "how reliable is this source when the book is STRESSED / at a clock mark"
    # and shrink toward the broader pools when the sub-bucket is thin.
    for kind, val in (row.get("cond") or {}).items():
        cb = agg.setdefault("cond_buckets", {}).setdefault(
            f"{row['source']}|{row.get('market') or 'CRYPTO'}|{kind}:{val}|{horizon}",
            {"n": 0, "correct": 0})
        cb["n"] += 1
        cb["correct"] += int(correct)
    # MISSION X-A (2026-07-17): DAY buckets — the drift evidence is unambiguous (river_online
    # 0.680→0.525, filter:momentum 0.672→0.576 across two ~6h halves of ONE clean day), so a
    # cumulative bucket that weighs a week-old outcome equal to an hour-old one systematically
    # mis-weights every source. Additive dict keyed source|market|regime|horizon|YYYYMMDD;
    # source_reliability_decayed() reads it with an exponential half-life. Bounded by pruning
    # the oldest day keys.
    try:
        day = time.strftime("%Y%m%d", time.gmtime(float(row.get("ts") or time.time())))
        db = agg.setdefault("day_buckets", {})
        dk = (f"{row['source']}|{row.get('market') or 'CRYPTO'}|"
              f"{(row.get('regime') or 'unknown').lower()}|{horizon}|{day}")
        d = db.setdefault(dk, {"n": 0, "correct": 0})
        d["n"] += 1
        d["correct"] += int(correct)
        if len(db) > 30_000:                        # prune the oldest days wholesale
            days = sorted({k.rsplit("|", 1)[-1] for k in db})
            for old in days[:max(1, len(days) - 14)]:
                for k in [k for k in db if k.endswith(f"|{old}")]:
                    db.pop(k, None)
    except Exception:
        pass


def _mirror_price(symbol: str, epoch: float) -> float | None:
    """100% price coverage (2026-07-13): the binance_stream all-market mirror holds EVERY
    perp's mark price with a rolling history — read it so ANY claimed symbol resolves, not
    just the handful with local feather candles. Flat-symbol keyed; fail-open."""
    try:
        from trading.broker_sense.binance_stream import get_mirror
        flat = str(symbol or "").upper().split(":", 1)[0].replace("/", "")
        return get_mirror().price_at(flat, epoch)
    except Exception:
        return None


def _resolve_row(row: dict, now: float) -> tuple[list[tuple[str, bool, str]], bool]:
    """→ ([(horizon, correct, method)…], done). done=True once every horizon is either
    labeled or permanently unresolvable (expired) — the row then leaves pending."""
    out: list[tuple[str, bool, str]] = []
    ts = float(row["ts"])
    labeled: dict = row.setdefault("_labeled", {})
    path, basis = _feather_for(row["symbol"], row["segment"])
    ref = row.get("ref_price")
    if ref is None and path is not None:
        ref = _price_at(path, ts)
    if ref is None:                                    # 100% coverage: all-market mirror history
        ref = _mirror_price(row["symbol"], ts)
    pending_left = False
    for hz, mins in HORIZONS.items():
        if hz in labeled:
            continue
        due = ts + mins * 60
        if now < due:
            pending_left = True
            continue
        target = None
        method = ""
        if path is not None and ref is not None:
            target = _price_at(path, due, after=True)
            method = f"feather:{basis}"
        if target is None and ref is not None:         # 100% coverage: mirror price @ horizon
            mp = _mirror_price(row["symbol"], due)
            if mp is not None:
                target, method = mp, "mirror:markprice"
        if target is None and ref is not None:
            if abs(now - due) <= _PROBE_TOL_MIN[hz] * 60:
                try:                                # one cheap cached quote, in-window
                    from trading.broker_sense import data_failsafe
                    q = data_failsafe.quote(row["symbol"], row["market"].lower())
                    if q and q.get("last"):
                        target = float(q["last"])
                        method = f"probe:{q.get('source', 'quote')}"
                except Exception:
                    target = None
        if target is None:
            if now - due > _MAX_PENDING_AGE_S:      # expired: count honestly as no-data
                labeled[hz] = "no_data"
            else:
                pending_left = True                 # feather may still catch up
            continue
        move = target - float(ref)
        correct = (move > 0) if row["direction"] == "LONG" else (move < 0)
        labeled[hz] = "ok"
        out.append((hz, bool(correct), method))
    if ref is None and now - ts > _MAX_PENDING_AGE_S:
        for hz in HORIZONS:
            labeled.setdefault(hz, "no_data")
        pending_left = False
    return out, not pending_left


def tick(budget_s: float = 15.0) -> dict:
    """Resolve due pending decisions and fold them into the aggregates. Runs inside
    the funnel loops next to funnel-learn; flock-guarded so concurrent processes
    never double-count. Returns a small report for the loop log."""
    rep = {"resolved": 0, "no_data": 0, "still_pending": 0, "expired": 0}
    if not _enabled():
        return rep
    p = _pending_path()
    if not p.exists():
        return rep
    t0, now = time.monotonic(), time.time()
    lock = open(p.with_suffix(".lock"), "w")
    try:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return rep                              # another process is on it
        rows, keep, folds = [], [], []
        with open(p, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue                    # torn line: drop, appends are small
        # NEWEST-first (2026-07-13 fix): resolve recently-due claims FIRST so they land inside
        # their short live-quote probe window even when an old backlog is present. Processing
        # oldest-first let a large backlog consume the whole budget on stale/no_data rows and
        # starve fresh claims → every source stuck unproven. Sort is cheap vs the price lookups.
        rows.sort(key=lambda r: float(r.get("ts") or 0), reverse=True)
        for row in rows:
            if time.monotonic() - t0 > budget_s:
                keep.append(row)
                rep["still_pending"] += 1
                continue
            labels, done = _resolve_row(row, now)
            folds.extend((row, hz, ok, m) for hz, ok, m in labels)
            rep["resolved"] += len(labels)
            no_data = sum(1 for v in (row.get("_labeled") or {}).values()
                          if v == "no_data")
            rep["no_data"] += no_data
            if not done:
                keep.append(row)
                rep["still_pending"] += 1
            elif no_data and not labels:
                rep["expired"] += 1
        if folds:
            def _merge(agg: dict) -> dict:
                for row, hz, ok, method in folds:
                    _fold(agg, row, hz, ok, method)
                agg["updated"] = now
                return agg
            state.mutate_json(_AGG, _merge, default={})
            _append_train(folds)
        tmp = p.with_suffix(".tmp")                 # atomic pending rewrite
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.writelines(json.dumps(r, separators=(",", ":")) + "\n" for r in keep)
        os.replace(tmp, p)
    finally:
        try:
            fcntl.flock(lock, fcntl.LOCK_UN)
        except OSError:
            pass
        lock.close()
    return rep


# ── one-shot journal backfill (idempotent) ────────────────────────────────────────


def _parse_dt(s: str) -> float | None:
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)   # journal datetimes are UTC
        return dt.timestamp()
    except (ValueError, TypeError):
        return None


def backfill_journal(limit: int | None = None, journal=None) -> dict:
    """Label every closed journal trade not yet seen: the entry→exit price sign is the
    'exit' horizon (always available); fixed horizons come from local feathers where
    the data exists. Missing candle data is COUNTED (no_data), never faked. Safe to
    re-run: seen ids persist. flock-guarded: the live-loop ingest seam AND the learn-loop
    safety net both call this continuously (the exit horizon froze for 5 days when this
    had no production caller, found 2026-07-16) — concurrent runs must never double-fold
    the same unseen trade, so a second caller returns immediately with locked=True.
    `journal` accepts an already-loaded TradeJournal to skip re-reading the 50MB+ file."""
    rep = {"scanned": 0, "labeled": 0, "no_data": 0, "skipped_seen": 0}
    lock_p = Path(state.STATE_DIR) / "direction_truth_backfill.lock"
    lock_p.parent.mkdir(parents=True, exist_ok=True)
    lock = open(lock_p, "w")
    try:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            rep["locked"] = True                    # another process is mid-backfill
            return rep
        return _backfill_journal_locked(rep, limit, journal)
    finally:
        try:
            fcntl.flock(lock, fcntl.LOCK_UN)
        except OSError:
            pass
        lock.close()


def _backfill_journal_locked(rep: dict, limit: int | None, journal) -> dict:
    if journal is None:
        from trading.journal.journal import TradeJournal
        journal = TradeJournal()
    trades = [t.to_dict() for t in journal.trades]
    if limit:
        trades = trades[-limit:]
    seen: set = set(state.load_json(_SEEN, {}).get("ids") or [])
    folds: list[tuple[dict, str, bool, str]] = []
    new_seen: list[str] = []
    for t in trades:
        rep["scanned"] += 1
        tid = str(t.get("entry_order_id") or "") or (
            f"{t.get('symbol')}|{t.get('entry_datetime')}")
        if tid in seen:
            rep["skipped_seen"] += 1
            continue
        d = (t.get("direction") or "").upper()
        ep, xp = t.get("entry_price"), t.get("exit_price")
        ts = _parse_dt(t.get("entry_datetime") or "")
        try:
            ep = float(ep) if ep is not None else None
            xp = float(xp) if xp is not None else None
        except (TypeError, ValueError):
            ep = xp = None
        if d not in ("LONG", "SHORT") or not ep or ts is None:
            new_seen.append(tid)
            continue
        snap = t.get("decision_snapshot")
        if isinstance(snap, str):
            try:
                snap = json.loads(snap)
            except json.JSONDecodeError:
                snap = {}
        snap = snap if isinstance(snap, dict) else {}
        row = {"ts": ts, "symbol": t.get("symbol") or "",
               "market": (t.get("market") or ("CRYPTO" if t.get("exchange") in
                          ("binance", "BINANCE") else "NSE")).upper(),
               "segment": (t.get("segment") or snap.get("segment") or "futures").lower(),
               "direction": d,
               "source": str(snap.get("strategy") or t.get("strategy")
                             or t.get("signal_source") or "unknown")[:80],
               "confidence": t.get("brain_confidence_entry"),
               "regime": str(snap.get("regime") or t.get("regime") or "any"),
               "taken": True, "ref_price": ep}
        if xp:                                     # horizon "exit": what the trade got
            folds.append((row, "exit", (xp > ep) if d == "LONG" else (xp < ep),
                          "journal:exit_sign"))
            rep["labeled"] += 1
        path, basis = _feather_for(row["symbol"], row["segment"])
        for hz, mins in HORIZONS.items():
            target = _price_at(path, ts + mins * 60, after=True) if path else None
            if target is None:
                rep["no_data"] += 1
                continue
            correct = (target > ep) if d == "LONG" else (target < ep)
            folds.append((row, hz, correct, f"feather:{basis}"))
            rep["labeled"] += 1
        new_seen.append(tid)
    if folds:
        def _merge(agg: dict) -> dict:
            for row, hz, ok, method in folds:
                _fold(agg, row, hz, ok, method)
            agg["updated"] = time.time()
            return agg
        state.mutate_json(_AGG, _merge, default={})
        _append_train(folds)
    if new_seen:
        def _merge_seen(s: dict) -> dict:
            ids = set(s.get("ids") or [])
            ids.update(new_seen)
            s["ids"] = sorted(ids)
            return s
        state.mutate_json(_SEEN, _merge_seen, default={})
    return rep


def rebuild_from_train() -> dict:
    """Rebuild the WHOLE bucket/rollup aggregate from the labeled train JSONL, re-keying every
    resolved decision by MARKET. One-shot migration for the 2026-07-13 market-scoping change:
    the pre-market aggregate pooled crypto+NSE under `source|regime|horizon`; the train log
    (`_append_train`) carries `market` per row and already includes journal-backfilled labels,
    so folding it fresh reconstructs full per-market history with the new key. Idempotent
    (fully replaces the aggregate). Returns a small report."""
    rep = {"rows": 0, "folded": 0, "skipped": 0}
    p = Path(state.STATE_DIR) / _TRAIN
    if not p.exists():
        return rep
    folds: list[tuple[dict, str, bool, str]] = []
    with open(p, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rep["rows"] += 1
            try:
                ex = json.loads(line)
            except json.JSONDecodeError:
                rep["skipped"] += 1
                continue
            hz = ex.get("horizon")
            if hz is None or ex.get("correct") is None or not ex.get("source"):
                rep["skipped"] += 1
                continue
            row = {"source": str(ex.get("source")),
                   "market": (ex.get("market") or "CRYPTO"),
                   "segment": (ex.get("segment") or "futures"),
                   "direction": (ex.get("direction") or "LONG"),
                   "regime": (ex.get("regime") or "neutral")}
            folds.append((row, str(hz), bool(ex.get("correct")),
                          str(ex.get("method") or "rebuild")))
            rep["folded"] += 1
    # rebuild from scratch: replace the aggregate entirely (drops legacy pooled keys)
    def _rebuild(_old: dict) -> dict:
        agg: dict = {}
        for row, hz, ok, method in folds:
            _fold(agg, row, hz, ok, method)
        agg["updated"] = time.time()
        agg["rebuilt_market_scoped"] = True
        return agg
    state.mutate_json(_AGG, _rebuild, default={})
    return rep


# ── read side: Wilson-bounded hit rates for gates + dashboard ─────────────────────


def _wilson(correct: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    """(rate, lower, upper) Wilson score interval — small-n honest."""
    if n <= 0:
        return 0.0, 0.0, 1.0
    p = correct / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return p, max(0.0, centre - half), min(1.0, centre + half)


def hit_rates(*, min_n: int = 1, market: str | None = None) -> list[dict]:
    """Per (source, market, regime, horizon) accuracy rows, Wilson-bounded, worst first.
    `market` (CRYPTO|NSE) filters to one market's buckets."""
    agg = state.load_json(_AGG, {})
    want_m = (market or "").upper() or None
    rows = []
    for key, b in (agg.get("buckets") or {}).items():
        try:
            source, mkt, regime, horizon = key.rsplit("|", 3)
        except ValueError:
            continue                                 # legacy 3-part key (pre-market) → skip
        if want_m is not None and mkt.upper() != want_m:
            continue
        n, c = int(b.get("n", 0)), int(b.get("correct", 0))
        if n < min_n:
            continue
        rate, lo, hi = _wilson(c, n)
        rows.append({"source": source, "market": mkt, "regime": regime, "horizon": horizon,
                     "n": n, "correct": c, "rate": round(rate, 4),
                     "ci_low": round(lo, 4), "ci_high": round(hi, 4)})
    rows.sort(key=lambda r: (r["rate"], -r["n"]))
    return rows


def source_reliability(source: str, *, market: str | None = None, regime: str | None = None,
                       horizon: str | None = None, min_n: int = 1) -> dict:
    """Measured accuracy of one directional SOURCE, aggregated across the buckets that match.

    Reads the same live aggregate `hit_rates()` serves, but rolls a single source up into ONE
    honest number the direction driver can weight by: sums (n, correct) over every bucket whose
    source matches (optionally filtered to a `market`, regime and/or horizon), then Wilson-bounds
    it. `market` (CRYPTO|NSE) keeps crypto and NSE reliability APART so a source that trades in
    both never has one market's outcomes poison the other's decisions (isolation, 2026-07-13).

    Returns {n, correct, rate, ci_low, ci_high, edge} where `edge = rate - 0.5` (signed: negative
    means the source is measured WRONG more than half the time → the caller should invert it).
    Empty/absent source → n=0 (caller treats as unproven). Never raises, no network.
    """
    agg = state.load_json(_AGG, {})
    n = c = 0
    reg = (regime or "").lower() or None
    want_m = (market or "").upper() or None
    for key, b in (agg.get("buckets") or {}).items():
        try:
            s, mkt, r, h = key.rsplit("|", 3)
        except ValueError:
            continue                                 # legacy 3-part key (pre-market) → skip
        if s != source:
            continue
        if want_m is not None and mkt.upper() != want_m:
            continue
        if reg is not None and r.lower() != reg:
            continue
        if horizon is not None and h != horizon:
            continue
        n += int(b.get("n", 0))
        c += int(b.get("correct", 0))
    if n < min_n:
        return {"n": n, "correct": c, "rate": None, "ci_low": None,
                "ci_high": None, "edge": None}
    rate, lo, hi = _wilson(c, n)
    return {"n": n, "correct": c, "rate": round(rate, 4), "ci_low": round(lo, 4),
            "ci_high": round(hi, 4), "edge": round(rate - 0.5, 4)}


def source_reliability_decayed(source: str, *, market: str | None = None,
                               regime: str | None = None, horizon: str | None = None,
                               half_life_days: float = 3.0) -> dict:
    """MISSION X-A: reliability with an exponential evidence half-life over the day buckets.
    Each day's (n, correct) is weighted 0.5^(age_days / half_life) — yesterday's regime shift
    stops poisoning today's weights, and a source must KEEP being right to stay trusted.
    Effective counts feed the same Wilson interval (conservative: decayed n shrinks power).
    n=0 when no day-bucket evidence exists (caller falls back to the cumulative pools)."""
    agg = state.load_json(_AGG, {})
    want_m = (market or "").upper() or None
    reg = (regime or "").lower() or None
    today = time.time()
    hl = max(0.1, float(half_life_days))
    n_eff = c_eff = 0.0
    for key, b in (agg.get("day_buckets") or {}).items():
        try:
            s, mkt, r, h, day = key.rsplit("|", 4)
        except ValueError:
            continue
        if s != source:
            continue
        if want_m is not None and mkt.upper() != want_m:
            continue
        if reg is not None and r != reg:
            continue
        if horizon is not None and h != horizon:
            continue
        try:
            import calendar
            day_ts = calendar.timegm(time.strptime(day, "%Y%m%d"))
        except Exception:
            continue
        age_d = max(0.0, (today - day_ts) / 86400.0 - 0.5)   # mid-day anchor
        w = 0.5 ** (age_d / hl)
        n_eff += w * int(b.get("n", 0))
        c_eff += w * int(b.get("correct", 0))
    if n_eff <= 0:
        return {"n": 0, "correct": 0, "rate": None, "ci_low": None,
                "ci_high": None, "edge": None, "decayed": True}
    rate, lo, hi = _wilson(c_eff, n_eff)
    return {"n": int(round(n_eff)), "correct": int(round(c_eff)),
            "rate": round(rate, 4), "ci_low": round(lo, 4), "ci_high": round(hi, 4),
            "edge": round(rate - 0.5, 4), "decayed": True}


def backfill_day_buckets(train_path: Path | None = None, *,
                         min_ts: float = 1784236980.0) -> dict:
    """One-shot cold-start for the day buckets from the per-row labeled train log
    (backfill-before-wire): folds every CLEAN-window row (ts ≥ min_ts — earlier rows carry
    the measured contaminations) so the decayed reader is dense from day one. Idempotent via
    a marker in the aggregate."""
    p = train_path if train_path is not None else Path(state.STATE_DIR) / _TRAIN
    if not p.exists():
        return {"folded": 0, "reason": "no train log"}
    marker = state.load_json(_AGG, {}).get("day_backfill_ts")
    if marker:
        return {"folded": 0, "reason": "already backfilled"}
    rows = []
    try:
        with open(p, encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except (ValueError, TypeError):
                    continue
                if float(r.get("ts") or 0) >= min_ts and r.get("horizon") != "exit" \
                        and r.get("source") and r.get("correct") is not None:
                    rows.append(r)
    except OSError:
        return {"folded": 0, "reason": "unreadable train log"}
    if not rows:
        return {"folded": 0, "reason": "no clean rows"}

    def _m(agg: dict) -> dict:
        db = agg.setdefault("day_buckets", {})
        for r in rows:
            day = time.strftime("%Y%m%d", time.gmtime(float(r["ts"])))
            dk = (f"{r['source']}|{(r.get('market') or 'CRYPTO').upper()}|"
                  f"{(r.get('regime') or 'unknown').lower()}|{r['horizon']}|{day}")
            d = db.setdefault(dk, {"n": 0, "correct": 0})
            d["n"] += 1
            d["correct"] += int(bool(r["correct"]))
        agg["day_backfill_ts"] = time.time()
        return agg
    state.mutate_json(_AGG, _m, default={})
    return {"folded": len(rows)}


def source_reliability_conditioned(source: str, *, market: str | None = None,
                                   kind: str, value: str,
                                   horizon: str | None = None) -> dict:
    """E8: one source's measured accuracy INSIDE a conditioner bucket (e.g. liq:stressed).
    Same contract as source_reliability; n=0 when the sub-bucket has no evidence."""
    agg = state.load_json(_AGG, {})
    want_m = (market or "").upper() or None
    n = c = 0
    for key, b in (agg.get("cond_buckets") or {}).items():
        try:
            s, mkt, cond, h = key.rsplit("|", 3)
        except ValueError:
            continue
        if s != source or cond != f"{kind}:{value}":
            continue
        if want_m is not None and mkt.upper() != want_m:
            continue
        if horizon is not None and h != horizon:
            continue
        n += int(b.get("n", 0))
        c += int(b.get("correct", 0))
    if n <= 0:
        return {"n": 0, "correct": 0, "rate": None, "ci_low": None,
                "ci_high": None, "edge": None}
    rate, lo, hi = _wilson(c, n)
    return {"n": n, "correct": c, "rate": round(rate, 4), "ci_low": round(lo, 4),
            "ci_high": round(hi, 4), "edge": round(rate - 0.5, 4)}


def status() -> dict:
    """Dashboard snapshot: overall + rollups + best/worst sources + pipeline health."""
    agg = state.load_json(_AGG, {})
    rollups = {}
    for key, b in (agg.get("rollups") or {}).items():
        n, c = int(b.get("n", 0)), int(b.get("correct", 0))
        rate, lo, hi = _wilson(c, n)
        rollups[key] = {"n": n, "rate": round(rate, 4),
                        "ci_low": round(lo, 4), "ci_high": round(hi, 4)}
    rows = hit_rates(min_n=10)
    pending = 0
    try:
        with open(_pending_path(), encoding="utf-8") as fh:
            pending = sum(1 for line in fh if line.strip())
    except OSError:
        pending = 0
    return {"enabled": _enabled(), "updated": agg.get("updated"),
            "n_buckets": len(agg.get("buckets") or {}),
            "pending": pending, "methods": agg.get("methods") or {},
            "rollups": rollups,
            "worst_sources": rows[:8], "best_sources": rows[-8:][::-1],
            "honest_note": ("accuracy is precision on labeled decisions; "
                            "no_data horizons are excluded, never guessed")}
