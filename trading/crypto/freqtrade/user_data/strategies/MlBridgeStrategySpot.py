"""MlBridgeStrategySpot — the SPOT-segment variant of MlBridgeStrategy.

Spot markets cannot short, and Freqtrade refuses to BOOT a can_short strategy in spot
mode ("Short strategies cannot run in spot markets") — that refusal inside the spot
segment's Worker construction is what silently killed the multi-segment worker loop on
2026-07-06/07 (see vendor/freqtrade worker_multi.py mlnb note). Everything else is
inherited unchanged: the brain drives entries via /forceenter, this class only relaxes
the shorting capability so the spot bot can boot; short signals are ignored by design.
"""
from MlBridgeStrategy import MlBridgeStrategy


class MlBridgeStrategySpot(MlBridgeStrategy):
    can_short = False                # spot: longs only — shorts are ignored, boot succeeds
