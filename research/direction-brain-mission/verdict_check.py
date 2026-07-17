"""Direction Brain Mission — the one-day verdict check (read-only).

Run:  .venv/bin/python research/direction-brain-mission/verdict_check.py

Prints every pre-registered scoreboard section with its threshold. The DECISION RULES
(stated 2026-07-17, BEFORE the data — honor them, including reverting):

  V1  learned_direction vs learned_direction_ctl (labeled rows, ts ≥ 1784282640):
      need ≥100 labeled per variant at 15m+1h. Live must beat control on sign accuracy
      (Wilson CIs non-overlapping, OR ≥ +3pp with n ≥ 200 per variant) AND on capture.
      LOSS ⇒ revert: LEDGER_HALF_LIFE_D=0 COST_GATE=0 HORIZON_SPECIALIZED=0
      LEARNED_DIR_MAG_CAP=0.5 in the loop env + write the negative result in LOG.md.
  V2  learned_direction_costcut (the refused trades) must score WORSE than
      learned_direction at the same horizons (≥50 labeled costcut rows). NOT worse ⇒ the
      cost gate is theater: set COST_GATE=0 and log it.
  V3  4h-tagged trades must hold direction better than 15m-tagged (closed trades whose
      exit_policy assignment carried the horizon; ≥30 per group).
  V4  OPE grid (trading/state/ope_report.json): read candidate ranking, especially
      halflife_* and magcap_* vs live_cfg and logged. A dial that beats live_cfg with a
      meaningful capture gap is a PROPOSAL for the owner — never auto-promote.
  V5  Exit bandit standings (informational until arms have n ≥ 30 each).

Health preconditions printed first — if OPE labeled_total is still ~0 or uptime is short,
say INSUFFICIENT DATA rather than forcing a verdict. (CONVENTIONS §16: underpowered ≠ wrong.)
"""
from __future__ import annotations

import json
import math
import time
from collections import Counter, defaultdict
from pathlib import Path

STATE = Path(__file__).resolve().parents[2] / "trading" / "state"
CUT = 1784282640.0            # session-1 restart 2026-07-17 10:04 UTC — variant-split epoch


def _wilson(c: float, n: float, z: float = 1.96):
    if n <= 0:
        return 0.0, 0.0, 1.0
    p = c / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / den
    return p, centre - half, centre + half


def _rows(name):
    p = STATE / name
    if not p.exists():
        return
    with open(p, encoding="utf-8") as fh:
        for line in fh:
            try:
                yield json.loads(line)
            except ValueError:
                continue


def main() -> None:
    now = time.time()
    print(f"=== Direction Brain Mission verdict check — {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime(now))} ===")
    print(f"variant-split epoch: {CUT} ({(now - CUT) / 3600:.1f}h of race so far)\n")

    # health
    try:
        st = json.loads((STATE / "ope_state.json").read_text())
        print(f"[health] OPE labeled_total={st.get('labeled_total')} "
              f"skipped_total={st.get('skipped_total')}")
    except OSError:
        print("[health] no ope_state.json")

    # V1 variant race + V2 costcut (labeled rows)
    acc = defaultdict(lambda: [0, 0])
    for r in _rows("direction_truth_train.jsonl"):
        if r.get("ts", 0) < CUT or r.get("horizon") == "exit":
            continue
        s = r.get("source")
        if s in ("learned_direction", "learned_direction_ctl", "learned_direction_costcut"):
            k = (s, r["horizon"])
            acc[k][0] += 1
            acc[k][1] += int(bool(r.get("correct")))
    print("\n[V1/V2] labeled variant rows (need ≥100/variant for V1, ≥50 costcut for V2):")
    tot = defaultdict(lambda: [0, 0])
    for (s, h), (n, c) in sorted(acc.items()):
        p, lo, hi = _wilson(c, n)
        print(f"  {s:28} {h:4} n={n:5} acc={p:.3f} [{lo:.3f},{hi:.3f}]")
        tot[s][0] += n
        tot[s][1] += c
    for s, (n, c) in sorted(tot.items()):
        p, lo, hi = _wilson(c, n)
        print(f"  {s:28} ALL  n={n:5} acc={p:.3f} [{lo:.3f},{hi:.3f}]")
    if not acc:
        print("  none yet → INSUFFICIENT DATA")

    # V3 horizon hold-rate via exit assignments + bandit-learned outcomes are in the
    # journal; approximate with assignment records that closed (consumed by learn()).
    try:
        a = json.loads((STATE / "exit_policy_assign.json").read_text())
        print(f"\n[V3] OPEN assignments by horizon: {dict(Counter(v.get('horizon') for v in a.values()))}")
        print("     (closed-trade hold-rates: mine journal rows whose decision_snapshot"
              " .brain.learned_direction.horizon is set — ≥30/group)")
    except OSError:
        print("\n[V3] no assignment file")

    # V4 OPE report
    try:
        rep = json.loads((STATE / "ope_report.json").read_text())
        print(f"\n[V4] OPE report ({rep.get('n_rows')} rows, "
              f"generated {(now - (rep.get('generated') or now)) / 3600:.1f}h ago, "
              f"primary={rep.get('primary_horizon')}):")
        for c in (rep.get("candidates") or [])[:8]:
            m = (c.get("metrics") or {}).get(rep.get("primary_horizon") or "1h") or {}
            print(f"  {c['name']:14} acted={m.get('acted')} hit={m.get('hit_rate')} "
                  f"capture_sum={m.get('capture_pct_sum')}")
        print(f"  caveat: {rep.get('caveat')}")
    except OSError:
        print("\n[V4] no ope_report.json yet")

    # V5 bandit
    try:
        bd = json.loads((STATE / "exit_policy_bandit.json").read_text())
        t = defaultdict(lambda: [0, 0])
        for k, b in bd.items():
            arm = k.split("|")[0]
            t[arm][0] += b.get("a", 0) + b.get("b", 0)
            t[arm][1] += b.get("a", 0)
        print("\n[V5] exit bandit (n, wins):",
              {k: tuple(v) for k, v in sorted(t.items())})
    except OSError:
        print("\n[V5] no bandit file")

    print("\nDecision rules + revert actions: see this file's docstring and "
          "research/direction-brain-mission/LOG.md (pre-registered verdicts).")


if __name__ == "__main__":
    main()
