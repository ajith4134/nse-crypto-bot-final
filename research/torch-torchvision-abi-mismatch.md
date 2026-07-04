# torch/torchvision ABI mismatch — "operator torchvision::nms does not exist"

**Date:** 2026-07-04 (CORTEX B6 dep install)

## Symptom
Installing `granite-tsfm` bumped torch to `2.10.0+cu128`; after forcing `torch==2.10.0+cpu`,
`import tsfm_public` failed with a masked error:
`ModuleNotFoundError: Could not import module 'PreTrainedModel'` (from transformers' lazy loader).

## Root cause
The lazy mask hid the real chained exception:
`from transformers.modeling_utils import PreTrainedModel` → transformers imports `torchvision`
→ `torchvision/_meta_registrations.py` runs `@torch.library.register_fake("torchvision::nms")`
→ `RuntimeError: operator torchvision::nms does not exist`.

torchvision ships compiled C++ ops built against a SPECIFIC torch ABI. Bumping torch
2.9.1 → 2.10.0 left torchvision at 0.24.1+cpu (built for 2.9) → its ops never register →
any transformers import that touches torchvision dies.

## Fix (dependency alignment, not our code)
Reinstall torchvision to the wheel that matches the torch minor:
```
~/.venv/bin/pip install "torchvision==0.25.0+cpu" --index-url https://download.pytorch.org/whl/cpu
```
Pairing: torch 2.10.0 ↔ torchvision 0.25.0. Verify: `from torchvision.ops import nms`.

## Gotcha for next time
When a dep forces a torch upgrade on this CPU VM:
1. It pulls the CUDA build by default (`+cu128`) — reinstall `torch==<v>+cpu` from the CPU index.
2. ALSO reinstall the matching `torchvision==<paired>+cpu` — else transformers/tsfm imports break
   with the misleading `PreTrainedModel` / `nms does not exist` error.
See also memory: brain-ultra-upgrade CPU-torch reinstall gotcha.
