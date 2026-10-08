# N34 detached release boundary wiring

This operational change is for independent root review/adoption at node 15.4.
It issues no production approval, accepts no real release, and performs no
owning-state adoption, dispatch, model loading, or simulator execution. Scientific
source remains `71ffff1a0f70d9874b309db9ef1843c02bf17ebf`. The implementation base
is `dc327becc00cd205bda0bd7905c24e6ade8efd6b`.

## Consumer contract

`qd_ed_n34_release.validate_release(plan_ref, release_ref)` returns the existing
`verify_prospective_release` result `(plan, runtime, authority)`. Both references
must be caller-supplied absolute regular-file paths with external SHA-256 hashes.
No consumer computes a trusted release hash from an untrusted path, infers release
from plan booleans, or turns a draft into approval. The bare-plan
`qd_ed_n34_contract.require_release` remains unconditionally rejecting.

The full verifier retains the exact released-plan matrix, phase flags, limits,
deadline, detached-release fields, root review, protocol, finite budget authority,
approval basis, imported checkout, operational/scientific source, loaded source,
runtime closure, controller semantics, provider contract, checkpoint/input/seed
inventory, task caches, and all 30 prospective command/config manifest checks.
Only plan validation moves before reading the detached release, so disabled drafts
are rejected on their own contract before considering a claimed release.

| Consumer | Release boundary |
| --- | --- |
| `supervise.launch` | Missing references reject; delegates to the runner. |
| `runner.main/launch/execute_one` | External CLI hashes flow unchanged; full validation precedes any lock and repeats under existing locks and before reservation. |
| `worker.context_for` | Full validation before producing a context; explicit detached reference always included. |
| `worker.validate_context` | Requires the exact context field set including `release`; full validation precedes row/manifest/command checks. No draft fallback. |
| `worker.main` | Validates context before reading the parent `G` gate. |
| `worker.run_worker/_run_in_process` | Revalidates after the gate and before process identity, durable dispatch-record checks, writes, model/Main execution, or environment changes. |
| `worker.verify_receipt` | Full release/context validation before consuming the worker receipt. |
| `worker.verify_terminal` | Requires the caller's detached reference, validates first, and always checks context/terminal/process release bindings before receipt/result checks. |

A direct call to the internal worker implementation also requires release and a
matching durable parent dispatch record. Receipt verification cannot silently
accept a draft. Pure reconciliation, draft validation, and `next_dispatch` remain
non-executing recommendation/inspection helpers; they grant no release.

The existing runner's locks, ledger snapshots/prefixes, historical charges,
resource isolation, protected reserves, full 1840-second admission, STOP checks,
unique attempts, live-handle rejection, complete-triple futility and zero automatic
recovery are unchanged. A valid detached document is necessary but insufficient
for dispatch. Revalidation costs remain inside the existing worker/process timeout;
no deadline or budget is extended to compensate for them.

## Exact root construction order (not executed here)

1. Independently review/adopt the intended commit into the execution checkout.
   Freeze that checkout's actual committed operational source via
   `b.closure.source_record(root, b.source_paths(root))`; do not reuse the previous
   operational commit or any source/config manifest that binds earlier bytes.
   Materialized pinned dependencies must satisfy the existing source verifier.
   Freeze scientific source with `b.scientific_paths(root)` at
   `b.SCIENTIFIC_COMMIT`; operational bytes must still match every scientific
   record. Never alter scientific code to satisfy this operational repair.
2. Select the exact reviewed runtime reference and external hash for this checkout,
   owned artifact paths, official current-login Codex `gpt-6-astra` condition, and
   GPU7 UUID/EGL4 mapping. Independently bind the reviewed runtime closure and
   deployed controller semantics/source-review evidence. Preserve the reviewed
   lazy tokenizer imports and generated-module rules; see
   `n34-generated-runtime-binding-v1.md`. Source changes require regenerating the
   affected source/manifests; they do not authorize a broad import survey or a
   recursive provenance rebuild. Unseen later runtime source remains fail-closed.
3. Freeze an exact `n34-production-protocol-v1` document matching the dictionary in
   `verify_prospective_release`: `c.expected_rows(root)`, `c.LIMITS`,
   `c.WORKER_CONTRACT`, episode-key identity, unchanged deadline, promotion
   `{all_valid_cells: 30, n34_min_successes: 5, at_least_both_controls: true,
   matched_controls_required: true}`, `complete_valid_triples_only` futility,
   validation/formal unauthorized. A `CANDIDATE` protocol is not this document.
4. Root must independently construct/review the finite
   `n34-budget-authority-v1`, with approved external `approval_basis`, cohort,
   limits, dev-only authority, exact coordinator end, explicit validated caps,
   protected 32/12 GPU-hour and 180/40 attempt reserves, finite weekly origin and
   increment (at most 168 hours), timezone-aware weekly end no later than the
   deadline, `starts_at`, `amendment`, and exact historical ledger prefixes.
   Caps must come from current owning accounting, never these test fixtures or
   inherited stale balances. Prefix names are restricted by `runner.snapshot`;
   attempt and health ledgers are required. This implementation provides neither
   the approval basis nor authority to issue it.
5. Assemble a new plan with schema `n34-released-plan-v1`, `frozen: true`,
   `release_enabled: true`, exact worktree/artifact root, the frozen source,
   scientific source, runtime, runtime closure, controller semantics, protocol,
   and authority references. Set phase authorization exactly to
   `{dev: true, validation: false, formal: false}`, `attempt_identity: episode_key`,
   and preserve matrix, limits, contract, deadline, STOP path. Remove the draft's
   `root_review` and `execution_release` keys entirely. Include owning `run_name`,
   `runtime_inventory_path`/`runtime_inventory_sha256`,
   `seed_plan_path`/`seed_plan_sha256`, and `input_contract_label: input_repaired`
   required by the unchanged runtime-input validator. Paths/hashes must bind the
   existing authorized frozen inputs, with no protected-result access added.
6. Before hashing the final plan, regenerate all 30 external manifests with
   `b.manifest(plan, runtime, row)` and populate `expected_manifests` with their
   exact path/hash references. Their contents bind source, scientific source,
   runtime, closure, controller, row, output directory and resolved configuration.
   Changing any of those inputs invalidates the manifests. Write the final plan
   once and independently obtain its external SHA-256. It must contain neither
   its own hash nor review/release hashes.
7. Construct the shared release fields exactly as `expected` in
   `verify_prospective_release`: schema `n34-execution-release-v1`, `approved:
   true`, final plan reference, authority, protocol, source, scientific source,
   runtime closure, controller semantics, runtime, limits and phase authorization.
   Root's independent review document must be exactly those fields with schema
   `n34-root-production-review-v1` and the additional `decision: APPROVED`.
   After real review, freeze its bytes/hash. The detached release is exactly the
   shared release fields plus `root_review` pointing to those frozen review bytes.
   Freeze the detached release and supply its external hash independently. Neither
   code execution nor setting `approved` produces the underlying authorization.
8. Independently call `validate_release(plan_ref, release_ref)` on those externally
   anchored documents and actual source/runtime inputs. This task has not done so.
   Root must adopt the same authority reference into owning state, reconcile
   current journals/reservations and historical charges, and verify fresh IDs,
   protected balances, finite weekly/cohort allowance, private isolation, STOP,
   deadlines, unresolved/live handles and required GPU probe/provider readiness
   through the existing admission path. No stale candidate/test snapshot proves
   these checks. Only root may decide to invoke the existing runner with the exact
   four plan/release path/hash CLI arguments; no invocation is part of this work.

## Focused evidence and limitations

`tests/test_n34_release_boundary.py` executes the public validator and all consumer
paths with temporary synthetic documents. Positive tests prove that full release
orchestration reaches each next gate; execution paths stop before a real lock or
worker process action, and receipt paths stop before consuming a synthetic result.
The installed source, loaded-module, runtime, controller, stage, file/input and
manifest leaf checks have explicit test stand-ins. Each substantive leaf rejection
is propagated through every public consumer. Real reference hashes, released-plan,
review, protocol, authority/caps, phase, ownership and provider-device selection
checks still run. These positives do **not** certify real closure or approval.

Tampering covers plan/release hashes and bytes, missing detached files/references,
drafts including enabled booleans, review hash/decision, authority hash/approval/
caps/basis, protocol threshold, source binding/bytes, runtime/closure/controller
hashes, phase expansion, recovery limits and manifest hashes. Contexts without
release reject through main, direct execution and receipt paths. Actual `python
-B -m` worker/runner subprocesses reject draft/missing/hash-invalid plans without a
parent gate or execution. They do not construct or accept production documents.

Prior same-worker native-audit tests now explicitly substitute only their
synthetic context/dispatch setup instead of relying on a production draft bypass.
Their tiny tensors and audit evidence are unit fixtures, not simulator episodes.
The existing disabled-draft tests retain rejection with the new contract error.
Focused lifecycle tests use fake processes and temporary journals exclusively;
no owning locks, state, ledger writes, admission, or dispatch occur in these tests.

No claims are made about full model/env readiness, GPU execution, real release
acceptance, current accounting, performance, target attainment, or scientific
outcomes. Root must independently review and adopt. File/hash checks retain their
existing point-in-time trust model; this change adds no signature system or defense
against a caller able to forge all external trust anchors.
