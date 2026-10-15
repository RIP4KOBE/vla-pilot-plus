# Bounded first-guided witness summary — prospective design

This is a **static design, with actual reads closed**. It proposes descriptive measurements of recorded N25/N26 witnesses after independent N26 terminal review. It authorizes neither an algorithm nor evidence extraction. The original scalar-only authorization does **not** cover tensor containers.

Nine production files were hash-checked against the 315-file source manifest at `6026794cd5d52f3a5054bf2704ebb3c516f9f47e`; four named preparation sources were also inspected (13 sources, 641,125 bytes total). Exact inputs are in `source-scope-v1.json`. No actual record, index, tensor, Git history or process was read; no production code, test, numerical replay, GPU/API/model or simulator was run.

## What is actually available

[Policy capture](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n26_clean_output_rbf/conditional_implementation/core/rdt_policy_steer.py:3050) records `model_output_before`, the already computed `update_operand`, and `model_output_after` on opposite sides of the original in-place addition. The rollout path does the same at lines 3942–3948. Therefore an output difference can be measured separately from the operand. These are the 16 × 8 × 3 translation-prefix values, **not** full outputs, post-scheduler actions, executed commands or physical motion.

[BoundedWitness](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n26_clean_output_rbf/conditional_implementation/core/qd_actuator_clipped_rbf.py:140) selects the first active call in initial slot −1 and rollout slots 0…9 of the first guided decision. It never backfills later decisions. The nine tensors are `input_xyz`, `source_origins`, `cast_origins`, `projected_xyz`, `gradient_before`, `gradient_after`, `update_operand`, `model_output_before`, and `model_output_after`. Origins are 16 × 3; the others are 16 × 8 × 3. Numeric payload caps are 20 KiB/call and 220 KiB/episode, plus 16 KiB identity metadata/call. N26 additionally checks input bytes equal the unmodified model-output prefix ([clean witness](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n26_clean_output_rbf/conditional_implementation/core/qd_clean_output_rbf.py:59)). N25's input instead represents the noisy sample.

The helper records source origin, native-cast origin and actual projected tensor from the same projector invocation (helper lines 65–104). The adapter reads the source origin once and constructs native `origin + cumsum(delta × .01)` ([adapter](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n26_clean_output_rbf/conditional_implementation/core/env_adapters/libero_adapter.py:1657)). These are proxy trajectories, not measured EEF motion.

## Serialization is a whole-container boundary

[Recorder snapshot](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n26_clean_output_rbf/conditional_implementation/core/decision_evidence.py:25) clones tensor values onto CPU. [flush](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n26_clean_output_rbf/conditional_implementation/core/decision_evidence.py:274) saves **all pending events together** with `torch.save`. The index records bundle hash and event sequence/type/decision/global-step/reset metadata; it contains neither tensor storage sizes nor witness phase/iteration.

Thus 220 KiB is not a bundle-size, decoded-memory or total-read bound. A selected bundle can contain canonical populations, scoring/provider metadata and other unrelated event values. `weights_only=True` is not field-selective: it still materializes the entire permitted container. A future release must explicitly authorize this bounded incidental decoding; the reader may use/export only witness statistics and necessary index identities. No unrelated event values, prompts, images or tensors may be exported. If incidental decoding cannot be authorized, this format is a blocker; there is no selective-safe workaround proposed here.

Do not call the existing `audit_output`, base event loader, `audit_witness`, `reconstruct` or worker verification functions. They read broader histories or replay arithmetic. No unsafe-pickle fallback, added safe globals or custom unpickler is permitted.

## Closed inventory and selection

A separate root release is required **after** `n26-root-terminal-review-v1` accepts terminal reconstruction with no unresolved discrepancies/costs. Preserve its exact scientific disposition. An accepted reconstruction of an INVALID cohort permits description of its independently accepted prefix only; it does not turn that prefix into a complete valid experiment.

Select every accepted **first-valid** N25/N26 cell in frozen plan order, including task failures and zero-guided cells; maximum 20 attempts. Do not substitute a failed primary for its accepted recovery, choose by activity/success, or consult older cohorts. Controls C0/Q0 contribute no tensor inputs.

The future manifest binds five control JSONs: terminal review, result, frozen plan, source manifest and the accepted terminal input inventory. For each selected attempt, bind its receipt, audit report and events index. Resolve these through the already accepted cell's `worker_receipt`/`audit` refs and terminal-input attempt refs; check receipt identity, source, plan and runtime against that chain. Runtime is an exact ref already checked by the original terminal reader, not a reason to follow all runtime files.

Validate the receipt's canonical evidence-list digest. Its exact index and selected bundle hashes must match both that list and the index. Never rehash every nested evidence file. Reject undeclared paths, aliases/symlinks, inconsistent identities, duplicate records, changed hashes or missing accepted-attempt bindings.

Read each authorized index once. Select the minimal union of bundles containing that arm's witness or coverage events; every such event must belong to one decision/global-step/reset identity. Never load later decisions to fill a gap. Preserve index identities for sequence checks. First-guided status, first-active-slot selection and same-call origin association rely on the **bound original same-worker native audit**, which already compared those events and origins (`qd_ed_n25_native.py:108–152`, N26:121–168). The index alone cannot independently prove guidance or slots. Do not open extra origin-only/context bundles to make that claim.

For a genuinely zero-guided cell, require the accepted terminal and profile-bound native report to agree on zero guidance/zero witnesses; its index must contain neither witness nor coverage events. Keep the cell with zero measured calls and null distributions. For nonzero guidance, actual event counts and coverage slots must agree with the native audit. N26's accepted terminal semantics require 11 witnesses when guided; N25 retains its original ≤11/active-slot coverage semantics. Missing, duplicated or cross-arm slots are extraction inconsistencies, not permission to repair original evidence.

After decoding, check the index/event envelope and only the selected witness/coverage values. Compare declared dtype, shape, byte counts, slots, step/timestep and source/input schema. N26 input/before equality can be checked directly on contiguous byte views; this is stored-value binding, not arithmetic replay. Input/projection/gradient types must match their original native metadata; before/after/operand must agree with their recorded output dtype. Do not assume all fields share one dtype or that source origins are always FP64. Unsupported/nonfinite/malformed values stop extraction; no imputation.

## Proposed finite limits and loading procedure

These are proposed ceilings, **not a claim that actual files fit**:

| Resource | Ceiling |
|---|---:|
| Accepted attempts / witness calls | 20 / 220 total; ≤11 per attempt |
| Control + receipt/audit/index metadata | 65 files plus one release/input manifest; 16 MiB/file, 128 MiB total |
| Selected tensor containers | ≤2 per nonzero-guided attempt, ≤40 total |
| Entire serialized container bytes | 64 MiB/file, 1 GiB total |
| ZIP entries / pickle metadata member | 8,192 per container / 8 MiB |
| Declared uncompressed ZIP bytes | 128 MiB/container, 2 GiB aggregate |
| Unique decoded tensor-storage bytes | 128 MiB/container, 2 GiB aggregate |
| Decoded graph | 500,000 nodes, depth 64, 20,000 events/container |
| Execution | CPU ≤2 threads, CUDA invisible/uninitialized; 180 s total |
| Process memory / output | externally enforced 2 GiB resident-memory ceiling / 16 MiB statistics and logs |

Root inventory can take on-disk sizes from explicit paths and hashes from accepted receipts/indexes without opening additional tensors. If the required minimal bundle union or size declarations exceed a cap, block before payload extraction; do not choose a smaller favorable subset. Actual ZIP layout, decoded storage and memory compatibility remain Unknown.

For each selected container, in fixed order: precheck declared/actual size and ownership, read at most its bound plus a sentinel, hash **those same bytes**, then inspect the ZIP directory from the in-memory buffer. Reject legacy/non-ZIP, encrypted/compressed or unknown layouts, duplicate/traversal members, excessive member counts/sizes or inconsistent storage records. A supported installed Torch archive layout must be established first on synthetic files; do not infer it solely from the `.pt` suffix.

Load exactly once from that buffer using `torch.load(BytesIO(...), map_location='cpu', weights_only=True)`. Inspect structural counts and all unique storage sizes, accounting for storage sharing, strides and backing storage rather than only tensor `numel`. Release the complete container and buffers before loading the next. Raw bytes, buffer copies, all co-resident tensor storage, Python metadata and conversions count toward peak memory, even when only nine witness fields are analyzed.

ZIP declarations are only prechecks; they do not prove unpickling memory safety. The whole-load memory ceiling must be enforceable externally and demonstrated on synthetic oversized/deceptive-container cases. A blindly chosen virtual-address-space limit is not evidence of a resident-memory bound. If safe full-container loading cannot be bounded on this host without custom unpickling, **stop with a blocker**. This static scope does not establish installed Torch storage-allocation behavior.

No automatic extraction retry. On a read/hash/shape/coverage/memory/time failure preserve the error, completed statistics, attempted/read byte counts and explicit partial coverage, mark extraction incomplete, and require fresh root review for any later attempt. Do not alter the scientific disposition.

## Minimal measurements and denominators

Use recorded values; FP64 is only the descriptive subtraction/counting space. Do not rerun clipping-based trajectory integration, RBF gradients, normalization, the denoiser, scheduler or CUDA arithmetic.

1. **Actual update.** Per call compute `delta64 = after64 − before64` and `residual64 = delta64 − operand64`. Report each particle's 24-component delta/residual L2 and Linf, exact numerically unchanged components, byte-unchanged components separately, and nonzero operands absorbed into a numerically unchanged output. Denominators are 384 components/call, 16 particles/call and the actual nonzero-operand count for absorption. Zero denominators produce null ratios. These are observed addition effects, not an executed-action or efficacy measure.
2. **Output range.** Count strict interior, exact ±1 boundary and outside values in before and after, plus the complete 3×3 transition table. Keep all increases and decreases. No fitted thresholds or inferred “harmful” overshoot.
3. **Recorded projection aliasing.** For all 120 unordered particle pairs per call, report exact-equal source origins, cast origins and recorded projected trajectories. Distinguish numerical equality from byte equality/signed-zero differences. Classify raw-input-distinct pairs that become equivalent under componentwise mathematical clipping, and **clipped-input-distinct** pairs whose recorded full 8-step projections are exactly equal. Computing this clipping equivalence is descriptive element classification, not a native projector replay. Stratify by equal/unequal source and cast origins. A pair with unequal source origins but equal cast origins shows cast-level loss in the stored representation; it does not establish the cause of trajectory aliasing. Scaling, cumulative rounding, origin addition and clipping cannot be causally separated from these measurements alone.

No substep storage offset or original CUDA layout is inferred from a deserialized tensor. Capture-stride metadata is not proof of full historical storage identity. No post-update projected trajectory is reconstructed: only the recorded projection used by that original RBF call is available.

## Output and later synthetic checks

Coverage comes first: original disposition and accepted prefix, all selected attempts, guided/zero-guided status, expected/recorded slots, per-call identity/dtype, full container/storage/read totals, missing/Unknown fields. Report per arm/task and initial versus rollout (retain rollout iteration), with counts and descriptive mean/median/p90 distributions. Pair only available same-task/same-slot summaries; missing phases remain null. They are not same-state or same-particle counterfactual pairs. Keep call-weighted totals distinct from task summaries.

The snapshot contains at most the first guided decision of each accepted attempt. It cannot characterize later calls, estimate success-rate improvements, prove physical grasp quality or validate a successor algorithm. Legal zero gradients and unchanged outputs stay in every denominator.

Before any actual read, synthetic tests must cover wrong attempt/source/runtime/receipt/index binding; recovery substitution; extra/missing/cross-decision slots; zero-guided presence contradictions; entire-file hash/size drift; tensor shape/dtype/nonfinite corruption; N26 input/before byte mismatch; oversized backing storage/compressed archive/metadata graph; partial-container failures; and hand-computed delta/alias cases including signed zero, absorbed operands, unequal origins and both gains/losses in range. Preserve all failed logs. Tests and implementation are future work, not performed or authorized by this design.

