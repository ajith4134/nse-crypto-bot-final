"""trading/brain/gui — the brain's computer-use / GUI-agent capability.

Gives the brain the ability the chat in research/brain-advanced-features-chat.md asks for:
SEE a dashboard (read its panels/charts/numbers/buttons), DECIDE what to do, ACT on it
(press its buttons / place orders), then EXPERIMENT, REFLECT and LEARN so it gets better
over time — composing real OSS (vendored: browser_use_src for DOM+Playwright, voyager for
the skill library, reflexion for the reflect-and-store loop, omniparser as a GPU-upgrade
slot) onto the brain's NodeProtocol, dashboard and HypothesisLedger.

Design (CPU-first, reuse-first, honest):
  perception.py  SEE   — read a dashboard via its own JSON API + served HTML (stdlib, works
                         today) with Playwright-DOM and PaddleOCR/OmniParser as activate-on-
                         install upgrade layers. ChartReader reads candles the way we read a
                         chart (from the same data the chart draws).
  actions.py     ACT   — drive controls in-process (the reliable path, no new dep) AND/OR
                         press buttons over HTTP exactly like a human user (urllib, stdlib),
                         with Playwright DOM clicks as the pixel-true path. allow_live guarded.
  skills.py      LEARN — Voyager-pattern growing library of validated GUI macros (file-based,
                         no langchain): each skill keeps its success stats so good macros rise.
  reflection.py  LEARN — Reflexion-pattern try→fail→reflect→store-lesson failure DB.
  agent.py       LOOP  — ComputerUseAgent ties it together (observe→decide→act→reflect→learn,
                         practice() to compound), wires EXPERIMENTS into HypothesisLedger, and
                         exposes a ComputerUseNode on the registry/dashboard (dashboard-sync).
  targets.py           — the dashboards it operates: our own (:8000) + Freqtrade/FreqUI (:8080).

Everything is offline-safe: missing optional deps degrade to honest capability flags, never
crash. Secrets stay in .env (config loaders only). State persists via trading.state so the
agent's skills/lessons compound across sessions.
"""
from __future__ import annotations

from trading.brain.gui.actions import ActionExecutor, ActionResult
from trading.brain.gui.agent import (ComputerUseAgent, ComputerUseNode,
                                     register_computer_use_agent)
from trading.brain.gui.perception import DashboardPerception, Perception
from trading.brain.gui.reflection import GuiReflector
from trading.brain.gui.skills import GuiSkill, GuiSkillLibrary
from trading.brain.gui.targets import DashboardTarget, TargetRegistry, default_targets

__all__ = [
    "ActionExecutor", "ActionResult",
    "ComputerUseAgent", "ComputerUseNode", "register_computer_use_agent",
    "DashboardPerception", "Perception",
    "GuiReflector",
    "GuiSkill", "GuiSkillLibrary",
    "DashboardTarget", "TargetRegistry", "default_targets",
]
