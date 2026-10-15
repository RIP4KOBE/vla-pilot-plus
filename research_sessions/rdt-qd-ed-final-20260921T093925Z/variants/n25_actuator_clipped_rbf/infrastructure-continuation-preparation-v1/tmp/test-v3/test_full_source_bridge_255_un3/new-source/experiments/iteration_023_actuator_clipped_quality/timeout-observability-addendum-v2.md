# N23 v2 prospective timeout observability clarification

This immutable addendum clarifies the new, not-yet-released N23 v2 protocol (`protocol-dev-v2-prospective.md`, SHA256 `11a311d46f62c809160ba18b7960c6eb36ad612450601b32998a3d6e21f95e0d`). It applies to its narrowly named N22 predecessor admission and to its prospective typed infrastructure-recovery eligibility only. It does not change N22, any valid-result gate, algorithm, provider, scientific-cell identity, budget, or protected-phase rule. Bind this addendum by hash in v2 plans, root reviews and eligibility records.

## Observable costs and one explicitly unobservable component

For exactly one failed Codex Stage call with `codex_timeout`, zero completed turns and no agent message, token usage is not returned by the managed Codex transport. The existing episode telemetry therefore reports `required_cost_telemetry_complete=false` and the existing validator may reject first with `Codex token usage incomplete`. That derivative rejection is included in the same narrow infrastructure fault class only when the evidence proves it arises exclusively from the one qualifying timeout.

Every other required measurement must exist and reconcile: actual GPU-process wall time, logical call attempts, completed/failed/usage-complete call counts, model/reward/canonical work, and the independent native audit. Every other Stage call must succeed and have complete token usage. Guidance/grounding and other providers must satisfy their unchanged requirements. The one failed call must have no completed turn or agent message in its retained Codex event evidence; missing evidence, an additional failed/incomplete call, arithmetic/nonfinite/identity/source/ownership fault, interruption or process timeout remains ineligible. A lifecycle timeout and retained thread/turn-start events do not establish an unseen successful result.

The failed call's unobservable input/cached/output token usage remains unknown, never inferred as zero and never filled in. Preserve the original record, its observed aggregate token counters and its `required_cost_telemetry_complete=false`. Add explicit unknown-token-call counts and mark all-attempt aggregate token usage partial/unknown in eligibility and cohort reporting. Observed counters are lower bounds, not complete bills. This uncertainty does not remove the attempt or its measured GPU hours from accounting. No monetary or token upper limit is asserted from these observations.

## Gates remain distinct

The predecessor and any eligible primary remain invalid. This addendum permits their narrowly evidenced infrastructure classification; it cannot make them accepted scientific cells. A prospective recovery can be dispatched only under all other v2 restrictions (at most two cohort-wide, one per cell, recovery bucket, identical scientific identity, new attempt and explicit retry linkage). The first valid recovery must pass the normal, unchanged complete-telemetry and independent-native gates. A failed recovery stops the cohort. Primary and accepted-cell denominators and costs remain separate.

For the predecessor, only the already named N22 task4 C0 attempt and its step112 timeout qualify. Actual terminal evidence must prove all these conditions after the original N22 worker exits. Until that review, the N23 entry remains closed. No N22 retry, continuation, reclassification as a scientific rejection, or reuse of its outcomes as N23 observations is authorized.

Recorded prospectively before any N23 backend preflight or online scientific attempt, under the user's standing instruction for autonomous, finite, auditable continuation. The immutable parent documents remain intact; this explicit clarification is not a silent loosening of their eligibility checks.
