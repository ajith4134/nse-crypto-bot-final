# mlnb: multi-segment fork — run several FreqtradeBot instances (futures / spot / option /
# prediction) inside ONE process, one shared database and one ApiServer, so every segment
# lives behind the single public URL. Reuses Worker unchanged for the per-segment loop; this
# module only adds config fan-out, thread supervision and segment context stamping.
"""
Multi-segment Freqtrade worker.

Config: the base config.json gains an ``mlnb_segments`` object::

    "mlnb_segments": {
        "futures":    {"enabled": true},
        "spot":       {"enabled": true,  "overrides": {"trading_mode": "spot", ...}},
        "option":     {"enabled": true,  "overrides": {"exchange": {"name": "deribit"}, ...}},
        "prediction": {"enabled": true,  "overrides": {"exchange": {"name": "predictionpaper"}, ...}}
    }

Each segment config = deepcopy(base) + recursive overrides + ``mlnb_segment`` stamp.
The first enabled segment keeps the api_server config; the shared ApiServer then registers
every further segment's RPC under its name (see rpc/api_server multi-RPC fork changes).
"""

import logging
import signal
import threading
import time
from copy import deepcopy
from typing import Any

from freqtrade.constants import Config
from freqtrade.enums import State
from freqtrade.persistence.segment_context import set_segment
from freqtrade.worker import Worker


logger = logging.getLogger(__name__)

# Segment name -> hard requirements applied on top of user overrides. Non-futures segments
# are dry-run ONLY for now: live execution there is a deliberate later step.
_SEGMENT_FORCED: dict[str, dict[str, Any]] = {
    # segment names match the dashboard registry ("options" plural); trading_mode is the
    # enum value ("option" singular).
    "futures": {},
    # spot/options/prediction are dry-run ONLY for now — going live there is a separate,
    # deliberate step (never implicitly inherit a live futures switch).
    "spot": {"trading_mode": "spot", "margin_mode": "", "dry_run": True},
    "options": {"trading_mode": "option", "margin_mode": "", "dry_run": True},
    "prediction": {"trading_mode": "prediction", "margin_mode": "", "dry_run": True},
}


def _deep_update(base: dict, overrides: dict) -> dict:
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_update(base[key], value)
        else:
            base[key] = value
    return base


class MultiWorker:
    """Supervises one Worker (thread) per enabled segment."""

    def __init__(self, args: dict[str, Any], base_config: Config) -> None:
        self._args = args
        self._base_config = base_config
        self._workers: dict[str, Worker] = {}
        self._threads: dict[str, threading.Thread] = {}
        self._stopping = False

        seg_cfg = base_config.get("mlnb_segments") or {"futures": {"enabled": True}}
        enabled = [s for s, c in seg_cfg.items() if c.get("enabled", False)]
        if not enabled:
            enabled = ["futures"]
        logger.info(f"MultiWorker: enabled segments: {enabled}")

        for segment in enabled:
            config = self._segment_config(segment, seg_cfg.get(segment, {}))
            set_segment(segment)  # stamp bot construction happening on this (main) thread
            try:
                self._workers[segment] = Worker(self._args, config)
            # mlnb (2026-07-07): ISOLATE per-segment boot failures. One segment's
            # construction error (e.g. a can_short strategy refused in spot mode)
            # previously propagated out of __init__, so run() never started ANY worker
            # loop — while the first segment's already-built ApiServer kept the process
            # alive and serving RPC. Result: forceenter/forceexit worked but no
            # exit_positions ever ran (no max/min_rate, no strategy exits) — silently,
            # for days. A sick segment must never take down the healthy ones.
            except Exception:
                logger.exception(
                    f"Segment '{segment}' failed to boot — continuing WITHOUT it"
                )
            finally:
                set_segment(None)
        if not self._workers:
            raise RuntimeError("MultiWorker: no segment could boot — see errors above")

    def _segment_config(self, segment: str, seg_cfg: dict) -> Config:
        config: Config = deepcopy(self._base_config)
        config.pop("mlnb_segments", None)
        _deep_update(config, seg_cfg.get("overrides", {}))
        _deep_update(config, deepcopy(_SEGMENT_FORCED.get(segment, {})))
        config["mlnb_segment"] = segment
        # One shared DB for all segments — isolation happens via Trade.bot_segment.
        config["db_url"] = self._base_config["db_url"]
        # ApiServer is a singleton owned by the first segment's bot; later bots construct
        # it too but its __init__ no-ops while the server is live — they only attach their
        # RPC handler (rpc_manager passes mlnb_segment). Nothing to change here.
        return config

    def run(self) -> None:
        for segment, worker in self._workers.items():
            thread = threading.Thread(
                target=self._run_segment, args=(segment, worker), name=f"seg-{segment}", daemon=True
            )
            self._threads[segment] = thread
            thread.start()

        # Supervise: exit when all threads die or on SIGTERM/SIGINT (marshalled to all bots).
        signal.signal(signal.SIGTERM, self._term_handler)
        try:
            while any(t.is_alive() for t in self._threads.values()) and not self._stopping:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            self.exit()

    def _run_segment(self, segment: str, worker: Worker) -> None:
        # ContextVar is per-thread here: every Trade created/read on this thread is scoped.
        set_segment(segment)
        try:
            worker.run()
        except Exception:
            logger.exception(f"Segment '{segment}' worker died")

    def _term_handler(self, signum, frame) -> None:
        logger.info("SIGTERM received — stopping all segment bots")
        self._stopping = True

    def exit(self) -> None:
        self._stopping = True
        for segment, worker in self._workers.items():
            try:
                worker.freqtrade.state = State.STOPPED
                worker.exit()
            except Exception:
                logger.exception(f"Error stopping segment '{segment}'")
        for thread in self._threads.values():
            thread.join(timeout=15)
