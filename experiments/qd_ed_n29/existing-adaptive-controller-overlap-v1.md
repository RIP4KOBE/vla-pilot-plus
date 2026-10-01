# N29 overlap check against the existing adaptive rollout controller

Static source52b9eb0, core/rdt_policy_steer.py:2416–2576, already contains _eds_adaptive_rollout_diversity_decision. Therefore N29 must not be described as the first adaptive-diversity mechanism in this repository.

That existing controller compares current diversity with a target band derived from a reference, uses reward confidence, an iteration decay and configured min/max scales, can turn a whole rollout intervention off, and falls back to a fixed scale on errors. It is not enabled in the frozen N28 profile (rollout_diversity_control_mode=fixed).

N29's proposed distinction is narrower: at each of the14 existing actual initial/parent calls, cap each particle's raw proposal distance by the same-call before-population RMS radius, then retain the box ray. It adds no reward-confidence/reference-band/decay parameter, does not invoke the old controller, and rejects invalid arithmetic rather than falling back. The observed initial12.984x/rollout2.887x/parent1.287x distance-to-spread imbalance motivates testing this particular bound; it does not establish that every adaptive scale mechanism was unexplored or that N29 will succeed.

This is a static mechanism comparison only. Historical adaptive-controller experiments were not independently reopened here; no claim about their outcomes or scientific novelty is added.

