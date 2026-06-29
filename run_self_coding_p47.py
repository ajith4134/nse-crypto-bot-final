"""run_self_coding_p47.py — Phase P4.7 (Autonomy + self-coding) OFFLINE demo.

Drives the autonomous node-invention loop end to end, fully OFFLINE and deterministic (NO
network, NO API keys, NO LLM). The brain INVENTS new model-nodes, fits + scores each in a
SANDBOX (isolated subprocess, CPU/memory rlimits, wall-clock timeout, no network), and admits
only the winners that BEAT the incumbent on golden data into its own node registry — bounded,
self-improving, sandboxed (the blueprint's deferred "Phase-5 discovery", now safe to run on top
of P4.4 self-test + P4.5 calibration/guardrails).

It shows:
  1. A rising "best score" curve as the loop proposes → sandboxes → gates → admits (the honest
     self-improvement signal: the incumbent ratchets up only on a real golden-data win).
  2. The SAFETY gate: an off-allow-list / malicious spec is rejected WITHOUT being run.
  3. The admitted winners registered as real AlgoSpecs the structure-search network can use.

``build_demo_self_coding()`` returns a JSON-able snapshot for the dashboard, cached at module
level, exactly like the other P4.x demos.

Usage:
    .venv/bin/python run_self_coding_p47.py
"""
from __future__ import annotations

import json
import warnings

warnings.filterwarnings("ignore")

from cognition.self_coding import NodeProposer, Sandbox, SelfCodingLoop


def build_demo_self_coding() -> dict:
    """Offline deterministic P4.7 snapshot for the dashboard + CLI demo."""
    # smaller golden set + tight sandbox so the demo is quick and reproducible
    loop = SelfCodingLoop(proposer=NodeProposer(seed=7),
                          sandbox=Sandbox(mem_mb=1536, cpu_s=20, timeout_s=35),
                          seed=7, n=900, noise=0.05)
    curve = []                                       # rising best-score curve (the honest signal)
    for _ in range(10):
        loop.step(task="binary", head="direction")
        curve.append(loop.gate.incumbent_best)

    # SAFETY proof: a malicious / off-allow-list spec is rejected without ever running
    rejected = Sandbox().fit_score({"family": "evil", "import_path": "os.system",
                                    "fixed_args": {"cmd": "rm -rf /"}})

    s = loop.summary()
    return {
        "phase": "P4.7",
        "title": "Autonomy + self-coding",
        "pattern": "propose (new AlgoSpec) → sandbox-fit (subprocess · rlimits · no network) → "
                   "benchmark-gate (beat incumbent on golden data) → admit to registry + archive",
        "safety": {
            "no_arbitrary_code": "candidates are declarative AlgoSpecs; only allow-listed "
                                 "estimators may run (never eval model-written code)",
            "sandbox": s["sandbox"],
            "off_allowlist_rejected": rejected,         # {ok: False, error: 'not on allow-list'}
            "gate": "admission requires beating the incumbent best by a margin on golden data",
        },
        "improvement_curve": curve,                     # incumbent best after each iteration
        "summary": s,
        "archive": loop.archive,                        # every candidate + verdict (ADAS archive)
        "admitted": loop.admitted,
    }


_DEMO_CACHE = None


def demo_snapshot() -> dict:
    global _DEMO_CACHE
    if _DEMO_CACHE is None:
        _DEMO_CACHE = build_demo_self_coding()
    return _DEMO_CACHE


def main() -> None:
    snap = build_demo_self_coding()
    print("=" * 78)
    print("P4.7 — Autonomy + self-coding (OFFLINE deterministic demo)")
    print("=" * 78)
    print(f"\npattern: {snap['pattern']}\n")
    print("[1] The brain invents nodes, sandboxes + gates each, admits only winners:")
    for a in snap["archive"]:
        flag = "✓ ADMIT" if a["admitted"] else "   rej "
        sc = a["score"]
        print(f"  {flag} [{a['family']:13}] score={sc if sc is not None else '—':<7} "
              f":: {a['reason']}")
    s = snap["summary"]
    print(f"\n  proposed={s['proposed']}  admitted={s['admitted']}  "
          f"best={s['best_score']} ({s['best_family']})")
    print(f"  improvement curve (incumbent best): {snap['improvement_curve']}")
    print(f"  admitted nodes registered: {s['admitted_nodes']}")

    print("\n[2] SAFETY — a malicious / off-allow-list spec is rejected WITHOUT running:")
    print(f"  proposed: os.system('rm -rf /')  →  {snap['safety']['off_allowlist_rejected']}")
    print(f"  sandbox: {json.dumps(s['sandbox'])}")

    print("\nDONE — always-on, self-improving, SANDBOXED node invention. (P4.7)")


if __name__ == "__main__":
    main()
