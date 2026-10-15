# N23 backend runtime preparation contract

This is CPU-tested plumbing, not dispatch authority or GPU readiness. Scientific prototype `cebed8f17122395a31866ac739e4dace0221bc04` remains preserved. The frozen backend arithmetic protocol has SHA256 `ada387aa1320f76239a7d4db43e8e4d9c1734ed735667113bcd6b6abcf543dfe`. No arithmetic tolerance or scientific intervention changes here.

## Assigned backend and ownership

`qd_ed_audit_backend.create_backend('cuda', binding=...)` requires exactly `{physical_gpu: 7, uuid: 'GPU-...', logical_device: 'cuda:0'}`. It verifies one visible device, current logical zero and actual PyTorch device UUID, retaining PyTorch/CUDA versions and encountered native dtypes. CPU is explicit; it does not fall back from CUDA. Imports and CPU-only receipt verification do not initialize CUDA.

N23's independent auditor reconstructs raw projection, raw seven-point reward and clipped quality on that assigned device. The auditor does not import the production clipping helper. Recorded native values retain their dtype; origins transfer directly to the target device/dtype. All existing provider, source, static controller/reset, raw/effective/selected and Stage association checks remain enforced. C0/Q0/N7 use their existing CPU audit arithmetic.

## Future cohort runner integration (not implemented or authorized here)

After the future finite 40-cell Dev release is reviewed, all C0/Q0/N7/N23 arm commands must use `worker.build_context(...)` and `worker.wrapped_command(...)`. The frozen plan must include `n23_cohort.worker_audit == WORKER_CONTRACT`, exact `source_commit` and `code_files`, runtime path/hash, output artifact root and a matching Dev row with 1800-second timeout. The unchanged original command must begin with absolute `ROOT/main.py`; every Hydra argument is preserved. Actual OS argv retains main.py for ownership checks.

Worker context schema `n23-metered-worker-context-v1` has exactly: `schema, attempt_id, episode_key, profile, output_dir, worktree, main_argv, plan, runtime, source`. File references are exact `{path, sha256}`. Source is exact `{commit, files, sha256}`: files are sorted `{path, sha256}` entries, digest is canonical JSON SHA, and every source byte must equal the named current Git commit. Context and attempt output must associate with the same frozen plan row and `<artifact_root>/attempts/<attempt_id>`.

`runpy.run_path(main.py, run_name='__main__')` executes in the wrapper PID. Original main exits/errors are propagated; no audit runs after a main failure. The wrapper checks physical CUDA identity inside that same process, audits and synchronizes before it exits, and includes hashing/audit time in its process wall. The future runner must enforce 1800 seconds over the whole process and charge all process wall time. There is no second audit GPU process.

The wrapper writes exclusive `eds_eval/in-worker-audit-start.json`, `decision-evidence-audit.json` and `in-worker-audit-receipt.json`. Start/receipt bind Linux PID/start ticks/boot ID, attempt, context, runtime, plan, source, original argv, indexed evidence bytes and audit/report hashes. An interrupted start cannot be reused. The parent must record the same owned process and invoke `verify_receipt(context_path, process_record)` after exit; it must not rerun CUDA audit. This consumer only checks committed source, JSON and file hashes. Native arithmetic coverage is required whenever N23 canonical candidates occurred. A legitimately zero-guided episode may have zero native arithmetic coverage; this does not replace the separately frozen cohort activity gate.

## One conditional arithmetic preflight (no dispatcher here)

`backend_prepare.build_draft(...)` consumes the frozen N22 plan's source/runtime records and the bounded read-only diagnostic index. Its missing predecessor review deliberately makes the draft non-executable. Preparing it neither charges nor reserves anything.

Plan schema `n23-backend-preflight-plan-v1` has exactly: `schema, worktree, artifact_root, limits, protocol, runtime, source, corpus, predecessor_review, synthetic_cases, task_outcome, requires_separate_release`. Limits are one recovery attempt, 120 seconds plus 40 cleanup, physical GPU7, reserved hours `160/3600`; `task_outcome=false` and `requires_separate_release=true`. Corpus SHA-binds exactly the exposed original GPU7 N21 task0 attempt, 2250 bundle files / 176 canonical batches / 2816 candidates. Synthetic FP32/BF16 arithmetic adds two four-candidate batches with both-sign clipping, exact bounds, unmodified rows and t8-only clipping. No model, provider or simulator is invoked.

Root-owned predecessor review schema `n23-n22-prerequisite-v1` has exactly:

```json
{
  "schema": "n23-n22-prerequisite-v1",
  "source_plan": {"path": "...N22 plan...", "sha256": "..."},
  "source_status": {"path": "...terminal status or aggregate validation disposition...", "sha256": "..."},
  "phase": "dev or validation",
  "disposition": "rejected",
  "allow_n23": true,
  "rationale": "Root scientific review"
}
```

The source plan must identify `N22_HOLD_LIFT_DEV_20260930`. Dev status must be `rejected_numeric_futility` or `completed_all_forty_audited`, with `dev_gate_promoted=false`. The alternate validation status is strictly aggregate-only schema `n22-validation-aggregate-disposition-v1`, with exactly `schema, cohort_id, aggregate_only, terminal, gate_passed, outcome_valid, dev_promoted`: cohort_id is the predecessor lineage `N22_HOLD_LIFT_DEV_20260930`; the booleans are respectively true, true, false, true, true. No protected per-task outcomes are read. Invalid, interrupted, pending, or promoted-only Dev is not authorization. An INVALID predecessor requires a separately preregistered transition, not an `invalid_resolved` shortcut.

The future admission code must independently enforce idle/exclusive GPU7, source review, remaining cumulative budget and protected reserves, charge one recovery attempt before launch, and set the process timeout/cleanup. None of that admission or budget mutation is implemented here. It must create:

- Release schema `n23-backend-preflight-release-v1`: exactly `schema, plan, source, runtime, limits, attempt_id, predecessor_review`, all copied from the frozen finite plan.
- Attempt context schema `n23-recovery-attempt-context-v1`: exactly `schema, attempt_id, output_dir, budget_bucket, plan, timeout_seconds, cleanup_seconds`; recovery/120/40 and owned artifact attempt directory are mandatory.

The preflight command retains an explicit main.py ownership marker but never executes main.py. Before CUDA it writes an exclusive start file, preventing reuse after interruption. It independently compares every native batch and exact helper slice/layout, unchanged-row bits and deliberate wrong-score/wrong-bound rejection. It preserves all mismatches in `n23-backend-preflight-report.json`. A successful report still requires `verify_preflight_proof(...)` against a valid separately metered recovery terminal record with matching process/report, no more than 160 seconds charged process wall and no more than 120 seconds worker wall.

Future Dev source must equal the preflight's complete commit-and-byte manifest. This is dynamic equality, not a report hash embedded in source. Finish and review all future dispatch source changes before the one preflight; later source changes invalidate the proof. The proof consumer rechecks all input bundle bytes and never replays CUDA. Passing establishes only arithmetic readiness on the recorded backend, not actual future controller validity or task success.

## Provider boundary

The root's read-only compatibility audit found all ten frozen Stage1 sources use the recognized weighted target0 provider; Stage2 is constant zero and is unsupported by this opt-in quality mode. The loader does not filter constant-zero callables. A guided Stage2 therefore fails closed before canonical reward/model work. `test_n23_invalid_contract_fails_before_canonical_search[constant_zero_stage2]` covers a loader-attached zero source; it is a synthetic semantic fixture, not a byte copy of the frozen Stage2 provider. There is no zero-provider fallback and no Stage/provider modification. An unguided episode does not activate the quality mode.
