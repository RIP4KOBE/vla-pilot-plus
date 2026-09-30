# N23 closed runtime admission implementation

This extends the historical CPU backend preparation contract with conditional runtime code. It grants no adoption or execution authority by itself. N22 retains priority; its valid aggregate rejection, or valid aggregate validation rejection after Dev promotion, is required. INVALID does not authorize N23. No provider, Stage, quality, descriptor, selector, decoder or controller semantics change here.

## Frozen finite scope

- Matrix: original Dev tasks 0..9, task-major C0/Q0/N7/N23; N7 is comparator only. All 40 valid native-audited outcomes, N23 >=5 and >= each comparator, substantive QD/ED with176/11 are required. After each complete quadruple only, candidate successes + unrun tasks <5 stops for numeric futility. Invalid/missing receipts stop; no retries. Zero clipping/rank changes are descriptive, not new vetoes.
- Dev: 40 attempts, 21 actual exclusive-process GPU hours, 1800 seconds whole-worker timeout +40 cleanup per attempt. All four arms use the same-process audit wrapper. Supervisor and admission recheck bound receipts using only CPU hashes/JSON, never a second CUDA audit.
- Backend: one recovery attempt, 120 seconds +40 cleanup, no task outcome. The original source-bound N21 task0 corpus and synthetic arithmetic inputs are unchanged. No provider verification, model load, simulator call or new probe occurs. Only metadata enumeration and reuse of the existing accounted CUDA/EGL proof are allowed.
- GPU7: UUID `GPU-48473162-9548-1a19-04aa-ea86c5349187`, EGL index4, reused probe `rdt-qd-ed-final-20260921T093925Z__gpu7_cuda_egl__4fafff3673e5`; exact inherited runtime, task order and E2 Stage conditions.
- Root-only adoption: cumulative478 attempts /100 GPU hours; baseline51, development187, validation180, formal40, recovery20; protected hours32/12 unchanged. Full unspent local21-hour ceiling plus the preflight's160 seconds (before preflight) and remaining protected hours must fit. Full remaining matrix attempts/buckets must fit. No borrowing.

## External review and state gates

`final-source-runtime-review-v1.json` is a root-owned file under the N23 variant directory, outside the source tree. Exact schema:

```json
{
  "schema": "n23-final-source-runtime-review-v1",
  "disposition": "accepted",
  "source": {"commit": "FINAL_HEAD", "files": [{"path": "relative", "sha256": "..."}], "sha256": "canonical-files-digest"},
  "runtime": {"path": "absolute frozen runtime", "sha256": "..."},
  "dev_protocol": {"path": "absolute protocol-dev-conditional-v1.md", "sha256": "638e43e8a7ab2b7accd13d7e772ed54e21b10ad84ac80c6decdee36a02066ed2"},
  "backend_protocol": {"path": "absolute backend-arithmetic-protocol-v1.md", "sha256": "ada387aa1320f76239a7d4db43e8e4d9c1734ed735667113bcd6b6abcf543dfe"},
  "amendment": {"path": "absolute budget-autonomous-amendment-20260930-n23.md", "sha256": "921d1e319d6ce7f3a9b8d79358c986b1640d31f8590d8abaf720ddea5b15cfb9"},
  "no_gpu_release": true
}
```

`worker.source_record(ROOT, contract.source_paths(vars(runner)))` constructs the actual complete sorted manifest and verifies every byte against Git HEAD. Both final Dev and backend plans use exactly this record. Root review and backend report hashes are external data and are not compiled into that source manifest, avoiding a circular freeze.

The predecessor review schema remains exactly the prior backend runtime contract's `n23-n22-prerequisite-v1`. Its source plan must equal the immutable N22 plan. Validation uses only a terminal, valid, aggregate rejection linked to predecessor cohort `N22_HOLD_LIFT_DEV_20260930` and `dev_promoted=true`; no protected per-task data is read.

The private state must retain ACTIVE/PASS/private_budget, one GPU7 worker, no external hold, and exact `GPU7_N23_AMENDMENT`. Root records `n23_gpu7_binding` with scope `N23_CLIPPED_QUALITY_DEV_20260930_and_backend_preflight_only`, selected_gpu7, the continuing user reply, and the exact Dev protocol absolute path/hash. This code has no adoption helper and never overwrites the amendment automatically.

## Accounting and closure

Preflight uses the normal append-only attempt ledger, budget bucket recovery, identity iteration `N23_BACKEND_PREFLIGHT_20260930`. Admission takes the existing private runner lock and state lock, checks source/runtime/reviews/capacity and idle GPU ownership, then writes reserved. Immediately before Popen it rechecks authority/budget/device and journals dispatched under the state lock. Launch failures are charged. Timeout/error cleanup targets only its owned process group. A reserved, invalid, interrupted or successful preflight anywhere in that iteration blocks another ID; the later Dev cohort also closes preflight admission.

Its worker context/release schemas are unchanged. The terminal ledger row binds PID/start ticks/boot, the actual report SHA and root final-review ref. `backend_proof()` resolves that single terminal record directly from the owning ledger before calling CPU-only `verify_preflight_proof()`. A caller-supplied result file cannot substitute for the ledger. Every native input bundle is rehashed. After valid completion, an external `backend-proof-reference.json` containing `{plan, report, attempt_id}` is emitted for Dev preparation.

An explicitly requested `--reconcile-attempt` checks that no owned process remains and closes an interrupted preflight as aborted, never as success. Wall time is conservatively charged through reconciliation, even if it exceeds the original160-second reserve. Such an attempt cannot retry. Standard live timeout/cleanup stays bounded; a crash does not erase historical cost.

The normal Dev runner keeps original Hydra arguments and provider/runtime checks, wraps main.py in the same owned PID, and requires its bound receipt before a valid outcome. Whole process wall includes audit. Missing audit cannot be rescued from results.txt during dead-child reconciliation. The supervisor reads the receipt again without CUDA and reports per-task/arm outcomes, actual denominators, paired gains/losses, clipping counters/time and model/reward/Stage/GPU costs. On a runner exception, its terminal attempt ledger remains the authoritative invalid/aborted cost record; the status identifies that ledger. No incomplete cohort receives a full ten-task rate.

## Prospective root activation order (not executed by CPU preparation)

1. Finish N22's valid frozen disposition; if it promotes, its priority validation comes first. Create root predecessor review only after that scientific decision.
2. Integrate/review the final committed source in the owning worktree; build its exact source record and create the external final-source/runtime review above. Root alone adopts the finite amendment under existing private locks and records the matching state/authorization. Preserve all historical charges and reserves.
3. Build a preflight draft with `qd_ed_n23_backend_prepare.py --source-plan N22_PLAN --protocol BACKEND_PROTOCOL --corpus-index READONLY_INDEX --draft-output NEW_PLAN`. Add `--freeze` only after prerequisites exist; it rechecks adopted state, source, reviews and full capacity under locks, then freezes without dispatch.
4. Root invokes `qd_ed_n23_preflight_admit.py --plan FROZEN_PREFLIGHT_PLAN` once. It performs real idle-device/probe checks, charges before launch and returns the actual terminal record. Any failure leaves Dev closed. No retry under another ID.
5. On success, `qd_ed_n23_dev_prepare.py --freeze --backend-proof ATTEMPT/backend-proof-reference.json --output NEW_DEV_PLAN` requires proof from that actual recovery ledger and same committed source/runtime. Without `--freeze`, the builder creates only a non-executable draft with missing predecessor/review/proof.
6. Root supplies external `n23-dev-execution-release-v1` with exact plan path/SHA, source_commit, cohort_id, all ordered episode_keys, physical_gpu7 and validation_authorized=false/formal_authorized=false. Invoke `qd_ed_n23_dev_supervise.py --plan FROZEN_DEV_PLAN --release RELEASE --status NEW_STATUS` only after review. No validation/formal launcher is added.

All commands use `/home/hynx/miniconda3/envs/vla-pilot/bin/python`. A source change after preflight invalidates its proof; no extra attempt or tolerance relaxation follows automatically.
