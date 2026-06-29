"""run_embodiment_p48.py — Phase P4.8 (Multimodal + identity + society + affect) demo.

Drives the brain's "personality with senses" end to end. Unlike the earlier phases this one uses
the REAL downloaded models by default (you asked for them active, not deferred): it actually
SPEAKS a sentence (kokoro-onnx → wav), HEARS it back (faster-whisper), SEES a generated image
(Moondream2→BLIP), FEELS emotional text (GoEmotions→NRCLex), holds an INTERNAL DEBATE (specialist
roles → vote), and keeps a persistent IDENTITY (Letta persona/human blocks). Set
``BRAIN_NO_MODELS=1`` to run the fast, model-free stub path (used by the test suite).

``build_demo_embodiment()`` returns a JSON-able snapshot for the dashboard
(GET /api/brain/embodiment/status), cached at module level like the other P4.x demos.

Usage:
    .venv/bin/python run_embodiment_p48.py            # real models (see/hear/speak)
    BRAIN_NO_MODELS=1 .venv/bin/python run_embodiment_p48.py   # fast stub path
"""
from __future__ import annotations

import json
import os
import tempfile
import warnings

warnings.filterwarnings("ignore")

from cognition.embodiment import Embodiment


def build_demo_embodiment() -> dict:
    """Offline/real deterministic P4.8 snapshot. Uses real models unless BRAIN_NO_MODELS=1."""
    work = tempfile.mkdtemp(prefix="p48_")
    idp = os.path.join(work, "identity.json")
    emb = Embodiment(identity_path=idp)

    # ── AFFECT: read emotionally-charged text; the mood shifts ───────────────────────
    feelings = [emb.perceive_text(t) for t in (
        "We won a huge profit today — a great success, I'm thrilled!",
        "A scary crash wiped out gains; heavy loss and real fear now.",
        "The market is flat and quiet.")]

    # ── IDENTITY: accrue a durable fact, introspect ─────────────────────────────────
    emb.remember("Operator prefers heavy blueprint-named tools when they win on capability.")
    introspection = emb.introspect()

    # ── SOCIETY: internal debate → vote (offline = deterministic heuristic vote) ─────
    debate = emb.deliberate("Should the brain add a new gradient-boosting node to the network?",
                            context="Recent OOS accuracy gains; some overfitting risk on noise.")

    # ── SENSES: speak → hear (round-trip) + see a generated chart ───────────────────
    senses: dict = {}
    spoken = emb.speak("The market is calm and the brain is content.",
                       out_path=os.path.join(work, "speech.wav"))
    senses["speak"] = {k: spoken[k] for k in spoken if k != "path"}
    if spoken.get("ok"):
        senses["hear"] = emb.hear(spoken["path"])           # transcribe what it just said
    try:
        from PIL import Image, ImageDraw
        img = os.path.join(work, "chart.png")
        im = Image.new("RGB", (220, 130), "white")
        d = ImageDraw.Draw(im)
        d.line([(10, 110), (70, 70), (130, 85), (210, 20)], fill="green", width=3)
        im.save(img)
        senses["see"] = emb.see(img, question="What does this chart show?")
    except Exception as e:
        senses["see"] = {"text": "[vlm-skip]", "error": str(e)[:60]}

    return {
        "phase": "P4.8",
        "title": "Multimodal + identity + society + affect",
        "tagline": "see/hear/speak · a persistent personality · internal debate · mood",
        "affect": {"reads": feelings, "running_mood": emb.mood.status()},
        "identity": introspection["identity"],
        "society": debate,
        "senses": senses,
        "status": emb.status(),
        "models_active": os.getenv("BRAIN_NO_MODELS") != "1",
    }


_DEMO_CACHE = None


def demo_snapshot() -> dict:
    global _DEMO_CACHE
    if _DEMO_CACHE is None:
        _DEMO_CACHE = build_demo_embodiment()
    return _DEMO_CACHE


def main() -> None:
    snap = build_demo_embodiment()
    print("=" * 78)
    print("P4.8 — Multimodal + identity + society + affect (models active:",
          snap["models_active"], ")")
    print("=" * 78)
    print("\n[AFFECT] reading emotional text shifts the mood:")
    for f in snap["affect"]["reads"]:
        fe = f["feeling"]
        print(f"  [{fe['engine']:10}] '{f['text'][:42]}' → {fe['top_emotions']} "
              f"→ mood={f['mood']} (val {f['valence']:+.2f})")
    print(f"  running mood now: {snap['affect']['running_mood']['mood']} "
          f"(valence {snap['affect']['running_mood']['valence']})")

    print("\n[IDENTITY] persistent self-model (Letta blocks):")
    idc = snap["identity"]
    print(f"  engine={idc['engine']}  notes={len(idc['notes'])}")
    print(f"  persona: {idc['persona'][:90]}...")

    print("\n[SOCIETY] internal debate → vote:")
    db = snap["society"]
    print(f"  Q: {db['question']}")
    for role, vote in db["votes"].items():
        print(f"    {role:5} → {'yes' if vote > 0 else 'no'}")
    print(f"  VERDICT: {db['verdict'].upper()} (tally {db['tally']}, mode {db['mode']})")

    print("\n[SENSES] see / hear / speak:")
    s = snap["senses"]
    print(f"  speak: {s['speak'].get('engine')} ({s['speak'].get('samples','-')} samples)")
    if "hear" in s:
        print(f"  hear (round-trip): {s['hear'].get('engine')} → \"{s['hear'].get('text','')[:55]}\"")
    print(f"  see: {s['see'].get('engine')} → \"{s['see'].get('text','')[:60]}\"")

    print("\nDONE — it sees, hears, speaks, feels, debates, and knows who it is. (P4.8)")


if __name__ == "__main__":
    import sys
    if "--json" in sys.argv:                 # subprocess mode for the dashboard (models in child)
        print(json.dumps(build_demo_embodiment(), default=str))
    else:
        main()
