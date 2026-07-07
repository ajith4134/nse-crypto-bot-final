"""trading/strategy/generators — the Strategy-Generator Portfolio.

A portfolio of complementary strategy generators (DEAP genetic, LLM-mutation, symbolic
regression, quality-diversity, formulaic-alpha mining, RD-Agent) that ALL emit candidates
scored through the one existing CPCV+Deflated-Sharpe+PBO guardrail and admitted into the
shared SkillLibrary the brain reads. See base.py for the design rationale.
"""
from __future__ import annotations

from trading.strategy.generators.base import (Candidate, StrategyGenerator,
                                              evaluate_and_admit, rebuild,
                                              register_candidate_type)
from trading.strategy.generators.expression import ExpressionStrategy
from trading.strategy.generators.portfolio import StrategyPortfolio, default_generators

__all__ = ["Candidate", "StrategyGenerator", "evaluate_and_admit", "rebuild",
           "register_candidate_type", "ExpressionStrategy", "StrategyPortfolio",
           "default_generators"]
