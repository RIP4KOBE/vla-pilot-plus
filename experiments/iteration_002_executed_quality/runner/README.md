# N2 runner integration (CPU preparation; no dispatch performed)

This engineering commit preserves the original N1 descriptor-only contract and adds the closed N2 `qd_quality_mode=executed_prefix_v1` contract. `baseline_profiles.json` is unchanged. The separately named observed manifest copies C0 and Q0 and adds only their common passive collector flag; N2 copies this Q0 and changes only the declared quality mode. All 30 original cells are new Dev identities, task0..9 × C0,Q0,N2 in that order, frozen original seed/init, observer=true, 1800s +40s cleanup. The template is intentionally unfrozen and not runnable.

Integrate the production N2 commit (including `core/qd_executed_quality.py`, config, metrics and dual-channel auditor), this commit, the protocol and accounting clarification before preparation. The builder includes these dependencies, its own code, the independent shared-lock/Xid support, and the native dependency snapshot in source fingerprints. It does not edit state/ledger, inspect model bytes, freeze, or dispatch. Root must verify the integrated source and full models once when launching; per-dispatch checks reuse the runner's inode/mtime/ctime hash cache.

Run in the authoritative worktree. Set `N2_HEAD` to the integrated commit, `N2_RUNTIME` to the frozen GPU3 runtime, and `N2_REVIEW` to the accepted fixed-candidate review described below. Output paths must be new paths inside the original artifact root. Existing plans and all prior outcomes stay immutable.

```bash
python scripts/qd_ed_n2_plan.py \
  --base-plan /mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/continuation_20260923/observed-pairs-v1/plan.frozen.json \
  --runtime-manifest "$N2_RUNTIME" --source-head "$N2_HEAD" \
  --recorded-candidate-review "$N2_REVIEW" --output "$N2_DRAFT"
python scripts/qd_ed_final_runner.py validate-plan --plan "$N2_DRAFT" --allow-unfrozen
python scripts/qd_ed_final_runner.py print-command --plan "$N2_DRAFT" --allow-unfrozen \
  --split dev --iteration N2_EXECUTED_QUALITY_DEV_20260923
```

Root must inspect the resulting 30 per-row argv and resolved CPU configuration previews using the existing preflight interface. Freeze a new plan with its source/config/runtime/input SHA and preflight evidence; the builder intentionally provides no implicit freeze. Then use the N2 entry, rather than direct multi-row `run_plan`, so each original terminal is followed immediately by the frozen complete collector audit:

```bash
python scripts/qd_ed_n2_supervise.py --plan "$N2_FROZEN" \
  --episode-key n2_dev_t00_c0_20260923 \
  --episode-key n2_dev_t00_q0_20260923 \
  --episode-key n2_dev_t00_n2_20260923 \
  --status-path "$N2_FIRST_STATUS"
```

The entry holds the real shared runner flock across the 120s GPU3 idle window and all selected cells, waiting with a <=30s heartbeat if another session owns the lock. It uses existing exact-owner reentrant nesting, journal reconciliation gates, original runner termination/accounting, and owned PID/startticks/boot/PCI Xid monitoring. It cannot terminate or bypass an external session. It requires candidate_indices=[3]. N2 binding permits only the already frozen compatible proof/runtime; an unavailable proof fails before new probe dispatch or runtime mutation. A separately authorized new proof requires an explicit newly frozen plan/local resource attribution, never an automatic retry.

`n2_cohort.runtime_prerequisites` retains the prior freshboot model-first PASS and valid full-production C0 process/kernel/result SHA references. It verifies boot, GPU UUID/PCI/driver/EGL, model inventory/seed identity and frozen native dependencies. This is reuse of prior engineering evidence only: prior production source is not represented as N2 source or algorithm evidence. Old CUDA/EGL proof and freshboot health resource IDs are explicitly `reused_prior`; neither gets charged again. Newly incurred health GPU time must be declared `new_n2`. Global240 counts episode attempts only; all GPU work counts against48h. N2 caps34 episode attempts, at most4 recoveries,2dispatch/cell,18 newly charged GPUh, with global protected budgets unchanged.

## Explicit release evidence

`recorded_candidate_review` is a `{path,sha256}` reference under the artifact root. Its JSON requires schema `qd-ed-n2-recorded-check-v1`, cohort_id `N2_EXECUTED_QUALITY_DEV_20260923`, exact source_commit and protocol_sha256, `passed:true`, `changed_recorded_choice:true`, and nonempty `evidence:[{path,sha256},...]` linking the separately reviewed CPU results. This is mandatory before the first dispatch.

After the first3 valid cells and complete accepted audits, root writes a new artifact with schema `qd-ed-n2-checkpoint-v1`, the same identity fields and evidence references, ordered first3 `attempt_ids`, and `checks:{finite_action:true,source_compute:true,raw_stage_separation:true,substantive_qd_activation:true}`. Link its SHA as `checkpoint_release` in a new derived frozen plan; keep source/config/runtime/protocol/scientific identities unchanged. Select only the remaining27 keys in frozen order. Unknown applicability alone is not substantive activation. Success or failure of the task is not a checkpoint correctness criterion. Later admission also checks every earlier cell's valid completion and complete accepted audit. An audit error stops later rows and leaves the original task terminal unchanged; it cannot create recovery eligibility.

Recovery requires an explicit copied original row with a new key, `retry_of` equal to its original dispatched attempt, bucket `recovery`, and `n2_recovery_contract` exactly equal to `qd_ed_n2_plan.binding(plan,runtime)`. Only one row per original cell and four total are allowed. Ordinary eligible infrastructure aborts retain original behavior; the only additional exception is the exact Codex transport gate below with new prospective N2 binding/eligibility. No automatic recovery rows or repeat dispatches are created. Source/config/runtime/inventory/transport drift, valid task failure, action/nonfinite/qpos error and ordinary timeout remain nonrecoverable.

## Actual terminal shape review and test limits

Read-only comparison used the old fourth observation terminal `...__observed_pairs_t05_q0_20260923__e47f3979b453/attempt-result.json`, SHA `7687d27fd8fa79864b88b3599796753ba1bc7abc26edeb558fadc93061efa68d`. It has `event:valid`, `outcome_valid:false`, `failure_class:task_failure`, `compute_outcome:completed`, `required_cost_telemetry_complete:true`, backend codex_cli, provider_failed_calls=stage_failed_queries=1, and exact reason `Codex Stage call failure invalidates the frozen transport condition`. It lacks the new N2 identity/eligibility and remains nonretryable. The original terminal is never changed to aborted. Its bundle was not read.

CPU tests use synthetic files/journals and mocked GPU metadata. They verify compatibility, limits, first3 release, exact transport exception with unchanged old rejection, prior complete audits, immutable runtime binding, boot/driver/native drift, and audit error/terminal ordering. They do not establish N2 task benefit, real GPU readiness, online activation, or a complete integrated model freeze. There is no automatic promotion/validation/formal scheduling.
