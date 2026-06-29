"""cognition/multimodal.py — see / hear / speak (Phase P4.8).

The brain's senses + voice, all CPU-only and reuse-first. Each capability uses the real
blueprint-named model by DEFAULT (the models are downloaded) and degrades to a safe stub when a
model/file is absent or ``BRAIN_NO_MODELS=1`` (tests/CI) — so the demo proves real multimodal
while the suite stays fast and offline:

  * **hear (STT):** **faster-whisper** (CTranslate2 int8, CPU) — transcribe speech to text.
  * **speak (TTS):** **kokoro-onnx** (Apache, torch-free ONNX; ``kokoro`` needs py<3.13) —
    synthesize speech to a wav. Models in ``models/kokoro/``.
  * **see (VLM):** **Moondream2** via transformers if it loads on this transformers version, else
    a transformers-5-compatible **BLIP** captioner (equivalent CPU vision capability) — describe
    / answer questions about an image.

Models load lazily and are cached per process. ``BRAIN_NO_MODELS=1`` forces the stubs.
"""
from __future__ import annotations

import os

_KOKORO_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "models", "kokoro")


def _models_off() -> bool:
    return os.getenv("BRAIN_NO_MODELS") == "1"


# ── hear: speech → text ─────────────────────────────────────────────────────────────────
class Ears:
    _MODEL = None

    @classmethod
    def transcribe(cls, audio_path: str, *, model: str = "small") -> dict:
        if _models_off():
            return {"text": "[stt-disabled]", "engine": "stub"}
        try:
            from faster_whisper import WhisperModel
            if cls._MODEL is None:
                cls._MODEL = WhisperModel(os.getenv("BRAIN_STT_MODEL", model),
                                          device="cpu", compute_type="int8")
            segs, info = cls._MODEL.transcribe(audio_path)
            text = " ".join(s.text for s in segs).strip()
            return {"text": text, "engine": "faster-whisper",
                    "language": getattr(info, "language", None)}
        except Exception as e:
            return {"text": "[stt-unavailable]", "engine": "error",
                    "error": f"{type(e).__name__}: {str(e)[:80]}"}


# ── speak: text → speech ────────────────────────────────────────────────────────────────
class Voice:
    _K = None

    @classmethod
    def speak(cls, text: str, *, out_path: str, voice: str = "af_sky", speed: float = 1.0) -> dict:
        if _models_off():
            return {"ok": False, "engine": "stub", "note": "tts-disabled"}
        onnx = os.path.join(_KOKORO_DIR, "kokoro-v1.0.onnx")
        voices = os.path.join(_KOKORO_DIR, "voices-v1.0.bin")
        if not (os.path.exists(onnx) and os.path.exists(voices)):
            return {"ok": False, "engine": "stub", "note": "kokoro model files missing"}
        try:
            import soundfile as sf
            from kokoro_onnx import Kokoro
            if cls._K is None:
                cls._K = Kokoro(onnx, voices)
            samples, sr = cls._K.create(text, voice=voice, speed=speed, lang="en-us")
            sf.write(out_path, samples, sr)
            return {"ok": True, "engine": "kokoro-onnx", "path": out_path,
                    "samples": int(len(samples)), "sample_rate": int(sr)}
        except Exception as e:
            return {"ok": False, "engine": "error", "error": f"{type(e).__name__}: {str(e)[:80]}"}


# ── see: image → description ────────────────────────────────────────────────────────────
class Eyes:
    _MOON = _MOON_TOK = None
    _BLIP = _BLIP_PROC = None
    _MODE = None

    @classmethod
    def _try_moondream(cls):
        from transformers import AutoModelForCausalLM, AutoTokenizer
        cls._MOON = AutoModelForCausalLM.from_pretrained("vikhyatk/moondream2",
                                                         trust_remote_code=True)
        cls._MOON_TOK = AutoTokenizer.from_pretrained("vikhyatk/moondream2")
        cls._MODE = "moondream2"

    @classmethod
    def _try_blip(cls):
        from transformers import BlipForConditionalGeneration, BlipProcessor
        mid = "Salesforce/blip-image-captioning-base"
        cls._BLIP_PROC = BlipProcessor.from_pretrained(mid)
        cls._BLIP = BlipForConditionalGeneration.from_pretrained(mid)
        cls._MODE = "blip"

    @classmethod
    def describe(cls, image_path: str, *, question: str = "Describe this image.") -> dict:
        if _models_off():
            return {"text": "[vlm-disabled]", "engine": "stub"}
        from PIL import Image
        img = Image.open(image_path).convert("RGB")
        if cls._MODE is None:                          # pick a working VLM once, prefer Moondream
            try:
                cls._try_moondream()
            except Exception:
                try:
                    cls._try_blip()
                except Exception as e:
                    return {"text": "[vlm-unavailable]", "engine": "error",
                            "error": f"{type(e).__name__}: {str(e)[:80]}"}
        try:
            if cls._MODE == "moondream2":
                enc = cls._MOON.encode_image(img)
                text = cls._MOON.answer_question(enc, question, cls._MOON_TOK)
                return {"text": str(text).strip(), "engine": "moondream2"}
            inputs = cls._BLIP_PROC(img, return_tensors="pt")
            out = cls._BLIP.generate(**inputs, max_new_tokens=40)
            text = cls._BLIP_PROC.decode(out[0], skip_special_tokens=True)
            return {"text": str(text).strip(), "engine": "blip"}
        except Exception as e:
            return {"text": "[vlm-error]", "engine": "error",
                    "error": f"{type(e).__name__}: {str(e)[:80]}"}


def status() -> dict:
    """Honest capability status (which models are present), without loading them."""
    import importlib.util as _ilu
    kok = (os.path.exists(os.path.join(_KOKORO_DIR, "kokoro-v1.0.onnx"))
           and os.path.exists(os.path.join(_KOKORO_DIR, "voices-v1.0.bin")))
    have = lambda m: _ilu.find_spec(m) is not None
    return {
        "models_off": _models_off(),
        "hear_stt": {"engine": "faster-whisper", "installed": have("faster_whisper")},
        "speak_tts": {"engine": "kokoro-onnx", "installed": have("kokoro_onnx"), "model_files": kok},
        "see_vlm": {"engine": "moondream2→blip", "installed": have("transformers")},
    }
