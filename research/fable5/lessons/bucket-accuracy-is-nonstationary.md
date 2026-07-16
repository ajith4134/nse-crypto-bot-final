# Trailing bucket accuracy does NOT persist — measure persistence before gating on it

2026-07-16: chrono split-half persistence of source×horizon accuracy across 39 cells (n≥40 both
halves) = corr **−0.214**. Cells below 0.45 reverted to a mean of 0.487. This is why the Mirror
Gate failed (paired z=+4.1: on its own samples the "reliably wrong" source scored 0.64+) despite a
conservative Wilson-CI bar. Rule: any invert/abstain/trust mechanism keyed on trailing accuracy
must FIRST demonstrate out-of-sample persistence of that accuracy; estimation rigor cannot rescue
a non-stationary quantity. Applies to: mirror_gate (retired), edge-weighting in learned_direction,
the equation ensemble's invert flags, Direction Colosseum promotion bars.
