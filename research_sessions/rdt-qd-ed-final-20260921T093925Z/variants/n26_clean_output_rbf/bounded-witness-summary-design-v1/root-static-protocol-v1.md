# Post-cohort bounded witness measurements — static design only

Purpose: complement the accepted scalar-summary preparation with measurements that scalar operands alone cannot supply. This is a prospective observational design over already recorded N25/N26 first-guided witnesses in the current N26 Dev cohort. It does not select a new algorithm and does not authorize actual evidence reads, numerical replay, GPU/model/API/simulator calls, new observations or environment branches. The current source remains 6026794.

Read only this protocol; ../source-manifest.logical-v1.json; ../conditional-mechanism-review-v1.md; ../conditional-numerical-questions-v1.md; and these exact source files in ../conditional_implementation, checking their hashes against the source manifest before reading:
core/decision_evidence.py
core/qd_actuator_clipped_rbf.py
core/qd_clean_output_rbf.py
core/rdt_policy_steer.py
core/env_adapters/libero_adapter.py
scripts/qd_ed_n25_native.py
scripts/qd_ed_n26_native.py
scripts/qd_ed_n25_reference.py
scripts/qd_ed_n23_worker.py
Also read only the accepted preparation sources ../terminal-review-preparation-v1/terminal_reader_v1.py, bounded_metadata_v1.py, metadata_semantics_v1.py and ../measurement-summary-preparation-v1/scalar_summary_v1.py. No artifact paths embedded in those sources may be followed. Do not import or execute production source or tests, inspect /proc/Git, or read actual records, indices, tensors, protected data, images, Stage prompts or credentials.

Write only design.md and source-scope-v1.json here; with this protocol, <=3 regular files and <=256 KiB. CPU only. No implementation, source edits, plans, releases, state/checkpoint changes or experiment claims.

Define a future closed-input reader that may run only after root accepts N26 terminal reconstruction and authorizes an exact finite inventory. Include every accepted first-valid N25/N26 cell, including failures and zero-guided cells, without selecting by success. At most 20 attempts and the original <=11 first-guided witness calls per nonzero-guided episode; never scan later decisions or backfill missing calls. Explain binding to accepted terminal result/input, per-attempt native receipt, exact source/runtime, index and bundle hashes. Preserve INVALID/Unknown statuses rather than repairing anything.

Important serialization issue: witnesses coexist with unrelated events in a torch.save decision bundle. Design explicitly accounts the entire container's bytes and decoded storage, not only the small witness subset. Propose an exact bounded selection from events index metadata, bounded source/container inventory and CPU weights_only loading; if a selective safe design cannot fit a reasonable finite cap, state a blocker instead of opening broader data. No generic filesystem discovery or unsafe pickle fallback. Do not implement a custom unpickler. Recommend concrete finite caps and failure handling; actual size compatibility is Unknown until later root inventory.

Measurements must use recorded native values, converting to FP64 only for descriptive subtraction/counting, with no claim to reproduce CUDA arithmetic. Suggested quantities: model_output_after minus model_output_before versus recorded update_operand; unchanged components and per-particle delta L2/Linf; pre/post translation out-of-range and exact-boundary fractions; whether source/cast origins are shared among candidates; exact duplicate projected trajectories and distinct clipped input pairs that alias in the recorded projection. Distinguish any projection aliasing from its cause (origin rounding, cumulative rounding, clipping) and from task impact. Do not infer physical action quality or success from latent/model-output measurements.

Report per arm/task/initial-or-rollout with denominators and coverage first, paired task comparisons where available, and zero-guided/missing coverage explicitly. This first-guided-only snapshot cannot characterize later decisions or estimate success-rate improvements. Proposal may simplify to the most informative minimal measurements. Require meaningful synthetic negative tests for identity/coverage substitution, extra/missing slots, sizes/hash changes, dtype/shape/nonfinite values, zero-guided handling, and partial bundle attempts. Preserve all failure logs. Root review and a separate future actual-read release are required.

