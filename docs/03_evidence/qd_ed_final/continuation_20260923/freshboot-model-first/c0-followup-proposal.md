# Prospective production C0 check, conditional on node 5.4 PASS

Prepared on CPU only. No plan was built/frozen, no GPU/provider invocation occurred, and no state or ledger was changed. No validation/formal outcome was opened. This is a proposed engineering child node **5.5**, not a scientific candidate promotion or an N1 retry. Root must freeze its own protocol before enabling the single episode.

**Purpose:** after the unchanged fresh-boot model-first healthcheck passes, test one complete original production C0 task0 episode under the fresh boot. This covers actual main.py ordering, guided EDS, DINO/keypoint depth/segmentation, Stage, action execution and episode reset paths that the synthetic zero-action B1 healthcheck did not cover. Keep all original profile behavior, prompts, policy load sequence, action horizon, reward and success criteria. In particular **do not apply a model-first, warmup, lifecycle, thread or process patch to main**. A model-first healthcheck PASS alone does not establish scene-first production readiness.

## Proposed fixed identity and gates

- Protocol to create/commit: `experiments/iteration_001_execution_intent/gpu3-freshboot-c0-common-condition.md`.
- One row only: episode key `freshboot_c0_t00_20260923`, iteration `FRESHBOOT_C0_20260923`, split/seed_block dev, profile C0 (historical label `p2_stage_on_abs_rbf_control`), task0, env_seed = policy_seed = 1969522881, init_index 0 and the existing frozen init/BDDL hashes.
- Bucket **development**, timeout **1800 seconds**, original episode limits unchanged; `retry_of` absent. A new condition is not an infrastructure retry of an old identity. Its cost and any failure still belong to the original shared 240-attempt/48-GPU-hour study. Require budget for the full 1800 seconds plus runner's 40-second termination allowance; protect 60 validation/40 formal attempts and 14+10 GPU-hours.
- `phase_authorization = {dev:true, validation:false, formal:false}` only on this one-row plan. No N1 rows or active candidate profiles. Preserve every old baseline/Q0/P2/healthcheck result and denominator. Do not count this check as replacement for a missing old N1 control, best candidate, or formal success.
- Require one explicitly named **completed** fresh-boot model-first resource, matching contract/result digests, unchanged worker SHA `63d0acaed3b5c1a3088dab79f49c2f224374406a0d9078c4c3aeeb2364eb2519`, physical GPU3 and boot `2a1fa95f-ab0d-488c-a298-fc488ddd2af7`. Failure does not authorize this episode; root continues the separately planned minimal control instead.
- GPU3 only: UUID `GPU-62052fa1-37e0-79dc-21aa-5c0f25c0c315`, physical CUDA mask 3 / process ordinal 0 / EGL0, exclusive, 120 seconds continuously idle including explicit external CUDA-mask reservations. No fallback, preemption, sharing or killing external workers.
- Wait for the shared runner lock and **all** journal work to become terminal/reconciled. The episode queue is fail-closed on an unfinished journal or a held runner lock; it does not have the native-probe queue's waiting_journal behavior. Do not start it while the external GPU2 job holds this worktree's shared lock, even though GPU3 is idle.

The source C0 profile remains population16, ten EDS iterations, grid archive disabled, original RBF schedules/quality/action decoder, debug trajectory drawing and qualitative mechanism traces. Its first guided chunk must use the real production C0 path, not synthetic unguided B1. Provider remains `codex_cli`, `gpt-6-astra`, reasoning effort `low`, timeout90, condition `codex_login_astra_low_v1`; Poe credentials are preserved and not read. Full checkpoint/HF/DINO bytes and task caches remain frozen.

## Existing tools and exact preparation commands

The adjacent `prepare-freshboot-c0-draft.py` is an unexecuted CPU-only builder. It takes an explicit PASS result/contract and current committed source HEAD. Under the shared runner lock it checks journal quiescence, budget, unused new identity, GPU3 authorization, unchanged profile/model/seed/runtime fingerprints and committed source bytes, then writes only a new **unfrozen** draft. It reuses the immutable `data/qd-ed-gpu3-c0-render-plan.json` for C0 inputs and removes its retry/cohort/preview metadata. Source provenance still points back to that immutable plan. It never loads models, queries GPUs, verifies provider login, freezes a plan or dispatches an episode. Full model-byte verification stays with the queue, whose hash cache is reused for later dispatch checks.

Root fills the three explicit values after node5.4 PASS and committing the new protocol (do not select a latest result implicitly):

```bash
W=/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z
A=/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z
L="$W/docs/03_evidence/qd_ed_final/continuation_20260923/freshboot-model-first"
PY=/home/hynx/miniconda3/envs/vla-pilot/bin/python
C0_SOURCE_HEAD='<full committed HEAD including the new C0 protocol>'
C0_PASS_RESULT='<explicit node5.4 output directory>/healthcheck-result.json'
C0_PASS_CONTRACT="$A/continuation_20260923/freshboot-model-first/frozen-contract.json"
C0_DRAFT="$A/continuation_20260923/freshboot-c0/plan.unfrozen.json"
"$PY" "$L/prepare-freshboot-c0-draft.py" --source-head "$C0_SOURCE_HEAD" \
  --pass-result "$C0_PASS_RESULT" --pass-contract "$C0_PASS_CONTRACT" --output "$C0_DRAFT"
"$PY" "$W/scripts/qd_ed_final_runner.py" validate-plan --allow-unfrozen --plan "$C0_DRAFT"
"$PY" "$W/scripts/qd_ed_final_runner.py" print-command --allow-unfrozen --plan "$C0_DRAFT" \
  --split dev --iteration FRESHBOOT_C0_20260923
```

These commands only prepare/check the draft. `validate-plan --allow-unfrozen` still checks HEAD, required source files, runtime/cache/profile/seed/task identity; it skips full model-byte/readiness checks. For a CPU Hydra preview use the existing `r.build_command(..., 'PREVIEW__freshboot_c0_t00_20260923')` and compose `configs/config.yaml` with the returned overrides. Serialize **only named override fields** and the public device allowlist; never dump full inherited environment/config credentials. Freeze a new copy as `plan.frozen.json` only after source/protocol/preview review, setting `frozen:true`, a fresh `frozen_at` and new preview hashes; never change the old plan.

Once root has supplied that frozen file, admission/supervision and prospective permission, the existing bounded execution command is:

```bash
"$PY" "$L/supervise-freshboot-c0.py" \
  --plan "$A/continuation_20260923/freshboot-c0/plan.frozen.json" \
  --status-path "$A/continuation_20260923/freshboot-c0/queue-status.json"
```

Do not run this command as part of CPU preparation. The queue validates all frozen model/source/input bytes, checks provider policy, obeys the dynamic singleton GPU3 authorization and rechecks resource/retry/budget gates before the existing runner. It will stop after this explicit row; dispatched failure is not an automatic retry. Queue output `completed` only says its requested run returned a valid outcome; it does not mean task success or a candidate threshold was met.

## Source binding and remaining supervisor requirements

Fingerprint current committed `r.REQUIRED_CODE` (all relevant core/utils/Stage paths plus main/config/runner), the queue/GPU-probe/runtime-setup scripts, the base plan's scientific config set, original model-first and fresh-boot protocols, and this new C0 protocol. Preserve the original baseline-profile SHA `75ba829fc29db71ae31669cd803c24fbe8ea96fe347160539a273f9d73551690`, runtime inventory SHA `44d456203ca168eec9eddfb6834d54347153b2c859eb1b4fc0dea02c15138b83`, seed plan, policy source, cache and provider identities. Observational source changes already in the current production branch are common condition changes, not the N1 mechanism. Freeze current installed dependency bytes as an additional sidecar if they are not all in the plan.

The adjacent `supervise-freshboot-c0.py` now fills two generic-tool gaps while calling the original queue in the same process (preserving its model hash cache). The wrapper fixes the explicit episode key, 30-second poll and 120-second idle interval and does not create a second child launcher or ledger writer:

1. The wrapper checks the frozen boot and explicit prerequisite result/contract at startup, pending gates and admission; it checks the committed `native-dependency-freeze.json` and its absolute `files` through the original cached verifier. Existing reusable-probe matching is hardware/source based, so an old context proof is still not described as fresh; the new healthcheck remains separate evidence. The wrapper source and native dependency JSON are required plan fingerprints.
2. The wrapper delegates the original timeout/exclusivity wait through a process proxy, checking kernel records after each wait timeout or normal exit. It matches exact GPU3 PCI/PID, current boot, /proc parent/session/start ticks and the original ledger/process.json linkage; events predating this PID lifetime are ignored. Only allowlisted scalar Xid evidence is saved in the attempt's `freshboot-kernel-monitor.json`. Matching faults raise the original runner's GPU3 GateError, so original `run_plan` finally terminates its owned child and writes one infrastructure-aborted terminal/cost record. No wrapper kill or terminal rewrite occurs. Other PID/GPU faults are ignored. The queue's existing accounted zero-step binding probe, if required, gets the same observation; no extra model probe is added.

Journal queries are capped at5seconds. Combined with the unchanged15-second exclusivity query and two10-second cleanup waits, worst bounded monitor/cleanup overhead fits the existing40-second allowance. SIGTERM becomes KeyboardInterrupt so the runner's finally executes. Six CPU mocks passed, including exact fault attribution, PID/boot rejection, sanitized query errors, both wait outcomes, restoration of temporary function bindings, and a real `run_plan` call with mocked Popen that produces exactly reserved/dispatched/aborted and invokes original cleanup once. No process/GPU/provider was launched in these tests. The root still owns final preview/freeze, one-shot launch and post-run review; the wrapper is not a general resume service.

Keep existing terminal parsing, action/numerical/config/cost checks and task result untouched. For the separate **mechanism coverage** decision require evidence of at least one actual guided C0 chunk with 176/11 search budget and `qd_archive_enabled=false`, observed DINO/keypoint camera processing, actual actions and Stage execution/accounting, complete finite telemetry, and no new owned Xid. If an otherwise valid task legitimately omits a requested path, report coverage incomplete rather than invent a call or change its outcome. Task success remains the original simulator criterion; 0/1 can still supply engineering evidence, while 1/1 is not a success-rate claim. Any failure stops this single node for analysis and preserves all costs; it does not stop the user's overall authorized research objective or authorize success-seeking repetition.
