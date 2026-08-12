# Run 034 protocol — paired Dev-A transfer gate

Date: 2026-08-12

## Objective and authorization

Run 033 validly improved paired online success from control `0/3` to candidate `1/3`, gained task 9 and lost none. Per the frozen v3 design, this authorizes exactly one Dev-A transfer test of the unchanged `eds_qd_global_quality_anchor_v1` candidate. The sole purpose is to decide whether the direct success gain transfers strongly enough toward the `>=5/10` primary target to justify validation.

This protocol authorizes no algorithm/core/config change, adjacent candidate, anchor-count variation, sparse-ratio change, fallback, horizon, Stage, prompt, perception, checkpoint, environment, executor or evaluator change. Rescue count remains attribution evidence and cannot override the task-success gate.

## Frozen matrix and profiles

- Suite: LIBERO-PRO `libero_object_swap`, strict perturbations, 720-step limit.
- Tasks: `[0,1,2,4,6,7]`.
- Episode seeds: `[307995,262892,731741,14859,648306,960581]`, paired in order.
- Control: `p2_stage_on_abs_rbf_control`, QD off.
- Candidate: `eds_qd_global_quality_anchor_v1` exactly as Run 033 — grid archive, causal envelope, sparse priority, one global-quality anchor, fallback `none`.
- Compute: unchanged population 16, 10 search iterations, `176 search / 176 QD / 11 score calls` per complete candidate chunk; control retains its frozen compute contract.
- Maximum mechanism horizon/configuration is unchanged from Run 033. There are 12 unique scientific cells.

The tasks and seeds are frozen before execution, do not overlap v3 Run 033, v1/v2 development/validation splits, v3 validation, or reuse-limited formal seeds. They cannot be reused for tuning after reveal.

## Task-first hard gates

Run 034 is PASS only if all conditions hold:

1. Both jobs exit 0 and are valid with 6/6 exact task/seed metadata, 6 videos, strict perturbation/suite verification, successful Stage evidence and complete artifacts.
2. Candidate success count is at least `3/6`.
3. Candidate success count exceeds control by at least 1.
4. `lost control-success tasks == []`; gained, retained and failed tasks are reported explicitly.
5. Every candidate record satisfies active archive, fallback none, anchor count 1, 10 activations, exact 1+15/16 parent accounting, 176/176/11, source/fingerprint/final-selection/finite/mask/qpos/archive gates. At least one real rescue must occur across the candidate run.
6. Control records satisfy QD-off and frozen compute/accounting gates.
7. Disallowed safety outcomes are empty for both profiles: qpos/execution error, target pushed away, target dropped after grasp, basket collision/displacement, or clutter/wrong-object interaction.
8. Candidate/control selection-latency P95 ratio is finite and `<=1.25`.
9. Attempt, GPU-hour, artifact, credential and write-boundary audits pass with no secret value/fingerprint and no mutation outside this worktree or owned artifact root.
10. `formal_authorized=false`; no validation/formal input or outcome is read during Run 034 decision-making.

Task-level success, gained/lost tasks, candidate-control delta, gap to five, and audited failure class are the first reported results. A valid failure of any gate yields `CONCLUDE_H4_V3_DEV_A_FAIL_NO_ADOPTION`; validation and formal remain forbidden, and no fourth candidate or Run 034-driven tuning is allowed. PASS yields `KEEP_H4_V3_DEV_A_PASS_AND_AUTHORIZE_VALIDATION_PROTOCOL_ONLY`.

## Implementation, manifest and transaction order

Only these new files may be implemented after this protocol commit:

- `scripts/eds_qd_autoresearch_v3_dev_runner.py`
- `tests/test_eds_qd_autoresearch_v3_dev_runner.py`

They may reuse committed v1/v2/v3 execution and audit infrastructure, but must freeze the exact Run 034 matrix/profiles/gates, bind the immutable Run 033 PASS audit, and fail closed. Existing core/config/runners/tests and historical artifacts remain unchanged.

After runner/test commit, create immutable `run_034_global_quality_anchor_dev_a/manifests/dev_a_manifest.json` under the owned artifact root. It must bind protocol and runner commits, source/config/profile/command/code-state hashes, Run 033 audit/result identity, checkpoint, LIBERO input, cached functions, DINO seed, GPU reference, tasks/seeds, budgets, exact expected IDs 79–90 and `formal_authorized=false`. Manifest must precede health, admission, reservation and execution.

Runtime order is: pause/storage checks -> manifest validation -> runtime-only credential validation -> real Poe health -> fresh two-snapshot GPU 0–7 admission -> immediate dispatch snapshot -> append-only reservation IDs 79–90 -> dispatch -> completion -> audit. Use at most two admitted GPUs, one worker per GPU; never co-locate, preempt, terminate or interfere with external processes.

Health/admission failure before reservation consumes no ID and may wait. A pre-episode infrastructure failure after reservation may be retried only through a new protocol-first exact-cell amendment and the remaining recovery reserve; any initialized policy outcome is final and never retryable.

## Budget, evidence and stop boundary

Before Run 034: 54 effective online episodes, 78 global reservations, `4.183103444444445` GPU-hours, 6/19 recovery slots used, formal episodes 0. Successful reservation makes global reservations `90/143` and effective online episodes at most 66. The 48 GPU-hour cap remains hard. The remaining 13 recovery slots cannot become new science; a full Dev-A infrastructure recovery would consume 12 and leave one.

Large artifacts may be written only below:

`/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-qd-autoresearch-libero-swap-ood/run_034_global_quality_anchor_dev_a`

All process, task, mechanism, failure, safety, latency, budget, hash and decision details must be appended to the canonical ledger `docs/03_evidence/eds_qd_autoresearch/iteration-ledger.md`. The protected untracked design remains unread, unmodified, unstaged and uncommitted. The user may pause at any time; after pause, create no new reservation and preserve owned state/evidence.
