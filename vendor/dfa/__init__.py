"""Vendored single-file Direct Feedback Alignment (DFA) broadcaster.

DFA (Nøkland 2016, "Direct Feedback Alignment Provides Learning in Deep Neural
Networks") replaces backprop's exact transposed-weight error path with a FIXED random
feedback matrix per layer: the output error is projected straight to every layer in
parallel, so the whole network learns from one error signal without a sequential
backward pass. DRTP (Frenkel 2021) is the sign-only / target-projected variant.

CORTEX uses this as the T6 "DFA broadcast" plasticity signal (design §1 T6 item 2):
a single realized trade-outcome error is broadcast through fixed random projections to
EVERY gate/glue layer, so the organism learns from each closed trade with no gradient
through the frozen expert neurons. Kept single-file (no pip) per the design's vendor list.
"""

from .direct_feedback import DFABroadcaster

__all__ = ["DFABroadcaster"]
