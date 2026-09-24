# N4 native consumer audit contract

This is CPU implementation of the consumer audit in the frozen N4 protocol
(`b8562e3f9fffc77efc803c6b056441f7b426333a97eb176b52fdb0fe42088db2`).
It does not authorize an online run, change task outcomes, or revisit historical
native inputs. The finite prerequisite is separately frozen and reviewed.

`scripts/audit_decision_evidence.py` retains its existing generic/default and N3
checks. After the generic provider, bundle, sequence and pre-reset lifecycle
checks, N4 records trigger `_audit_n4_terminal_population`. The dedicated output
is `n4_terminal_population_audit`, schema `n4-native-terminal-population-audit-v1`.
Every guided N4 decision must have this certificate; a generic accepted audit
alone is insufficient for a candidate-specific runner.

The additional checks bind eleven ordered native canonical batches of sixteen,
their exact original provider aggregates and stored costs, all ten prior-only
archive parent allocations, the final batch/score/occurrence, every native minimum
cost tie and the first-index argmin. Parent and archive actions retain every
matching canonical occurrence; unique archive insertion ancestry is not claimed.
The final archive reference is separately checked against its recorded pool using
the original quality/fingerprint/cell global-best tie rule. It need not equal the
actually selected action. Default global-best execution is not changed.

The audit loads only the deployed pure `core/rdt_libero_action_converter.py`,
whose bytes must be included in the runner's frozen source inventory. It verifies
the selected native-to-FP32 return, actual policy decode and every sent command.
It separately decodes the simultaneously available archive-global-best action.
Exact finite FP32 numerical comparisons treat signed zeros as equal. The output
keeps first-eight and actual-prefix differences distinct, including partial
terminal chunks; the reference is not an executed counterfactual or a simulator
result. Gripper zero follows the original decoder's positive branch.

The original same-call selected raw reward is bound to the original archive-cost
reference and the post-update `terminal_population_stage_binding` locals. The
original Stage normalization branch and clamp are checked. The actual normalized
Stage API input remains unobserved. GPU FP32 mean is not recreated bit-for-bit by
a CPU reduction and no tolerance is introduced: the unchanged scale-call source
and real-call CPU test (archive and terminal spreads deliberately differ) bind
the captured archive vector to the scale update. A finite nonnegative recorded
scale alone does not prove that call-site contract without the frozen source.

No separate checkpoint native reader is needed. The runner should join each
native decision's `global_step`, selected index/occurrence/cost/raw/cell, archive
reference and counts to its already-validated metrics/compute and immutable
episode identity. Require `checked_decisions == guided_chunks == metric_chunks`,
and per decision 11/176/10; require accepted and complete original evidence.
Retain all original outcome/cost records separately. The first triplet is a
correctness checkpoint even if its decoded-reference difference count is zero.
The completed twelve-cell gate separately requires at least one verified
`decoded_reference_actual_prefix_different_decisions`, plus the unchanged task,
source, compute and resource gates. Neither scalar changes nor first-eight-only
differences can satisfy that executed-prefix requirement.

Focused validation uses invented CPU tensors through the real collector and
SHA-verified bundle loader. It covers native dtype/sign/source mismatches, original
provider/parent linkage, selected occurrence/tie rules, archive truthfulness,
raw/normalization binding, deployed decode/dispatch, signed zero, inactive and
suffix-only changes, gripper zero, and short terminal/reset boundaries. Existing
generic and N3 tests guard default-mode behavior. No provider, projector, model,
simulator or GPU is invoked by this audit.
