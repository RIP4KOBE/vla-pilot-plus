# N23 CPU backend preparation report

Status: **CPU_BACKEND_PLUMBING_READY / GPU_PREFLIGHT_PENDING**. Commit `c60629bbb7bbe2ae2c3eb453cceb04dcde51f371` on `codex/rdt-qd-ed-n23-clipped-quality-20260930` preserves strict scientific prototype `cebed8f17122395a31866ac739e4dace0221bc04`. The implementation worktree is clean. No CUDA, simulator or external provider call was performed; no owning study source, budget, ledger or research tree was changed. N22 retains priority.

## Implemented

The independent native auditor now accepts an explicit arithmetic backend. N23 reconstruction transfers recorded native tensors without dtype changes and origins directly to the assigned device/dtype. Its exact raw projection/raw seven-point/clip score/mask and Stage association checks remain; no tolerance was added and the production clipping helper is not imported by the auditor. Earlier modes retain their existing audit arithmetic.

The new wrapper executes unchanged main.py with the original Hydra argv via runpy, then audits inside the same owned PID before exit. All future C0/Q0/N7/N23 arms must use it; only N23 arithmetic uses CUDA. Main failures propagate without later audit masking. Start and receipt bind attempt, PID/start ticks/boot, source commit and bytes, runtime UUID, argv, evidence and audit report hashes. CPU-only receipt verification never starts a second audit GPU process. A zero-guided N23 episode does not invent a per-episode activity veto; the later cohort still enforces its own frozen activity requirements.

Backend preparation provides a non-executable plan builder and an arithmetic-only worker for one conditional recovery preflight: 120 seconds + 40 cleanup, GPU7, original SHA-bound N21 task0 corpus 176 batches/2816 candidates plus two four-candidate FP32/BF16 adversarial batches. Wrong-score and wrong-bound controls use the actual independent verifier. Every mismatch is retained. The start marker prevents reuse of an interrupted attempt. The future admission layer still owns global one-attempt enforcement, resource exclusivity, timeout, reserve checks and budget charging; none is implemented in this commit.

Exact APIs/schemas and future integration requirements are in [backend-runtime-contract-v1.md](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n23_actuator_clipped_quality/implementation/experiments/iteration_023_actuator_clipped_quality/backend-runtime-contract-v1.md). This includes root-owned predecessor schema `n23-n22-prerequisite-v1`; valid aggregate N22 Dev rejection or valid aggregate validation rejection after Dev promotion is required. There is no generic INVALID/resolved shortcut and no protected per-task validation read. Validation `cohort_id` binds the predecessor lineage `N22_HOLD_LIFT_DEV_20260930`.

Future readiness is dynamic equality of the preflight's source commit and every manifest byte with the final Dev source. No report hash is embedded in source. Finish later dispatch code before freezing/running the one GPU preflight. Source changes after preflight invalidate it.

## Verification

174 regression cases passed (`cpu-backend-final-v1.log`); 20 full-loop/original early-gate cases passed (`cpu-backend-native-v1.log`); 5 current early-gate cases passed, including one new Stage2 case (`cpu-backend-stage2-v1.log`). These cover 195 unique cases. A final 62-case backend rerun passed after manifest/document additions (`cpu-backend-manifest-final-v1.log`). The native suite ran before the Stage2-only test addition; the five early gates were rerun afterward. No arithmetic source changed after that native suite.

Native FP32/BF16 fixtures each passed with 176 verified candidates/11 batches, 160 clipped-prefix candidates and 10 changed-ranking batches. Explicit audit backend reports CPU and the corresponding dtype. Both deliberate wrong-quality fixtures failed at `n23_native_clipped_quality`; both malformed-bound fixtures failed at `n23_controller_bounds`. Existing N20/N21/N22 focused loops passed. Full fixture paths, hashes and counters are in [the JSON report](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n23_actuator_clipped_quality/cpu-backend-implementation-report-v1.json).

Reproducible commands from `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n23_actuator_clipped_quality/implementation`:

```bash
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest tests/test_qd_ed_n23_backend.py tests/test_qd_actuator_clipped_quality.py tests/test_decision_evidence_audit.py tests/test_qd_ed_final_runner.py -q
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest tests/test_rdt_steer.py -k 'n23 or n22_hold_condition or n21_positive_lift or n20_exact_profile' -q
```

Wrapper plumbing tests deliberately mock backend identity while all computation remains CPU; their synthetic CUDA metadata is not readiness evidence. Tests cover argument/exit preservation, no-retry marker, malformed process/attempt/runtime/source/evidence/report bindings, wrong device visibility/count/current UUID, unchanged native CPU bits, metering/proof/source mismatch, valid-only predecessor transitions and draft closure. `git diff --check` passed before commit.

## Draft and remaining limits

The committed pure builder produced [backend-preflight-plan.draft-v1.json](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n23_actuator_clipped_quality/backend-preflight-plan.draft-v1.json), SHA `85587690f73bbc20cbfa1f35c1dd26252e8ad44798372c0cbec3e8dcd95493ba`, binding 184 source files and 2250 original bundle hashes. Its `predecessor_review=null` deliberately fails execution validation (`invalid file reference`); CPU validation confirmed `torch.cuda.is_initialized()==False`. The draft is not an adopted plan, budget amendment, recovery attempt or release.

The frozen backend protocol and tracked byte-copy both retain SHA `ada387aa1320f76239a7d4db43e8e4d9c1734ed735667113bcd6b6abcf543dfe`. Original scientific protocol, original failure logs and strict CPU/GPU mismatch report were preserved. The earlier actual-GPU BF16 evidence had 22/6512 raw-score and 5718/6512 raw-projection CPU replay mismatches; this commit relocates future audit arithmetic, but does not demonstrate that assigned-GPU reconstruction passes. **Actual CUDA preflight and controller-instance validity are still unproven.** No task success or likely SR gain is claimed.

The root's static provider result is [provider-compatibility-result-v1.json](/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n23_actuator_clipped_quality/provider-compatibility-result-v1.json), SHA `e0eea1642cab4cb765993cb6356edf0bbd709af2814a218ab4e1320f844a4d76`. It supports 10/10 frozen Stage1 compatibility (weighted target0 SHA `d374557f569b8c69f898a1596dfefd32a21774929511bb969d5d27e0050d4830`). Constant-zero Stage2 SHA `ca058cc1dcf87ce5910181800bb2f65b8cd4d92788b27f3b10b1e33dbc103f84` remains unsupported when guidance activates it. The new loader-attached synthetic constant-zero test fails before canonical reward work, with no fallback or Stage change. It is a semantic fixture, not a byte-identical copy of Stage2. This boundary can truthfully invalidate a later attempt and must not be mistaken for full two-stage provider compatibility.

The next separately assigned CPU task may prepare the closed 40-cell dispatcher and separately charged one-attempt recovery admission. It was not started here; root review precedes it.
