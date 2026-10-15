# N25 selected-cell measurement schema v1

This is a descriptive reader of already accepted, terminated N25 Dev cells. The root agent must separately freeze their exact input paths and SHA-256s, attest their accepted terminal identities, and release one read. The selected list is not automatically the entire cohort denominator. No real inputs are authorized by this preparation.

## Inputs and binding

Source commit is 5a65ef15968cc68c82314e8c0773b3365ad45fa0; plan SHA-256 is 1f0c94ccd3458a3a786acb9525728a1b64e3df439e4f920731f6566dd3a95eb3. The disabled manifest supplies 1–10 distinct task IDs in 0–9 and unique attempt IDs. Every cell has exactly four roles: eds_metrics.jsonl, episode_compute.jsonl, in-worker-audit-receipt.json, and decision-evidence-audit.json.

Each present payload is opened once, hashed from the same bytes that are parsed, and never revisited. Limits are 40 present files, 16 MiB per file, 128 MiB total, 60 seconds wall time, at most two CPU threads. The implementation is standard-library-only and normally single threaded. A timer failure retains a separate error-schema output with the read counts and forbids automatic retry. Oversized files fail before reading their payload bytes.

The receipt binds attempt/episode/profile, exact commit and plan SHA, metric presence/hash/path, audit hash/path, and the compute hash from its evidence list. Those linked source, plan, context, event and tensor files are never followed. Existing receipt/audit acceptance is required; root supplies scientific accepted-cell status. This reader does not replace the original transport/native/outcome acceptance gates.

Metrics may be absent only when explicit compute, profile-bound audit, and receipt guided counts are zero and the audit's existing observed-counts map has zero canonical batches. A missing canonical key in an existing Counter-derived map means zero by the frozen auditor's schema; a missing map is Unknown. An absent metric file must remain absent.

## Output

output-schema-v1.json fixes the successful CLI output. Every selected cell and the aggregate expose:

- all_calls;
- phase_totals.initial and phase_totals.rollout;
- groups in the fixed order initial/-1 followed by rollout/0 through rollout/9.

All three are alternative views of the same rows, not additive denominators. Each call represents 16 candidates × 8 prefix steps × 3 translation coordinates = 384 components. clipped_components means strictly outside [-1,1], boundary_components means exactly ±1, and interior_components means strictly inside. Their sum must be 384. Only rows with complete, nonnegative integer components enter the observed component denominator; excluded rows and entirely missing decision groups are separately counted. No missing value is imputed as zero.

zero_gradient.true / known_calls is the reported ratio. An empty known denominator yields null. The frozen Boolean is authoritative: a recorded norm of zero with zero=false may be underflow and is not reclassified. Zero gradients, including coincident or all-saturated inputs, are legal.

For gradient_before_normalization, gradient_after_normalization, masked_gradient and update_operand, norms are split by recorded torch.float32 and torch.bfloat16. Each distribution contains observed, mean, median, p90, min and max; p90 uses sorted value at ceil(0.9*n)-1. Statistics use Python arithmetic over recorded native scalar norms. They do not recompute native tensors. Missing, nonfinite, malformed or unsupported-dtype entries enter unknown_calls; empty distributions contain null statistics. The update operand is the intended operand of the original += operation, **not measured model-output delta**.

cost_consistency preserves measured guided/unguided/RBF call and batch-row counters. It compares guided metric count, RBF calls, 16 batch rows per call, native canonical batches, the fixed 11/176/10/10/10 decision counters, profile markers, and receipt/audit summaries. Missing/inconsistent fields produce explicit issues, not a new experimental validity or promotion decision. Receipt worker/audit seconds are labeled as receipt measurements; ledger GPU seconds are Unknown and are not inferred.

bounded_witness gives first-guided expected slots, existing verified-call count/numeric bytes and verified/all-observed-call coverage. It checks the existing auditor's ≤11 expected calls and ≤225280-byte episode cap. The JSON witness checks do not expose slot identities, so slot_identity_independently_verified=false. Exact backend arithmetic is credited only as the original accepted bounded witness audit; this reader performs no replay, and later scalar calls are not promoted to exact tensor proof.

## Interpretation and failures

The report measures the input subset, not task efficacy, contact, causal benefit or promotion. It cannot pair N25 gradients with nonexistent N23 raw-gradient telemetry. It cannot establish that gradients reached the model as the same numerical output delta. The source's global norm normalization may concentrate force on the remaining interior coordinates; these measurements alone do not establish reduced physical saturation.

Structural identity/hash/release failures stop the read. Descriptive missing measurements remain Unknown. The error schema is n25-terminal-measurement-summary-error-v1 with error, payload_read_counts, guard, elapsed_seconds and automatic_retry_allowed=false. Existing results are not overwritten. No tensor, image, Stage response, protected input, old-round payload, model, API, subprocess, simulator or CUDA import is allowed.
