# Frozen evaluation and budget policy — revision 1

Frozen before any new online dispatch. Source: user execution prompt and GPU7-only steering.

## Budget and dispatch

240 dispatched episode attempts maximum; 48 GPU-hours aggregate. Physical GPU7 only, maximum one live worker. No process sharing, external termination, or opportunistic use of other GPUs. GPU admission requires no external compute processes and less than 1024 MiB used; repeat directly before CUDA/EGL/model startup. Waiting and CPU-only audit consume no GPU allocation; every owned GPU process interval (including startup, failures and healthchecks) counts. Maintain append-only events per unique attempt ID and derive counts by identity.

| Phase | Reserved episode attempts | GPU-hour planning envelope |
| --- | ---: | ---: |
| Starting Q0 + C0 baseline | 20 | 4 |
| Development and mechanism checks | 100 | 16 |
| Validation: candidate/P2/Q0 x20 | 60 | 14 |
| Formal: candidate/P2/Q0/QD ablation x10 | 40 | 10 |
| Infrastructure recovery allowance | 20 | 4 |

Phase envelopes are reservations, not new independent budgets. Reallocation is permitted only before the next dispatch, with an explicit ledger event; preserve 60 validation +40 formal attempts until their gates close. No post-outcome threshold relaxation. Later validation candidates require a new preregistered seed block and a feasible full reservation; do not reuse revealed validation for tuning. Total maximums never expand automatically.

Attempt lifecycle: reserved -> dispatched -> completed or aborted. Count every dispatched ID once even if aborted before first action. Record valid=true/false independently of task success. Legal task failures are not recovery cases. For a multi-episode process all assigned episode IDs count at dispatch, and unstarted IDs on process failure remain aborted rather than disappearing. Retries get fresh IDs linked to the exact prior scientific identity; never overwrite outputs. GPU-hours are process-time, not summed duplicated per episode when a process runs several.

## Evaluation structure

- Freeze task->seed map before outcomes, build execution order from sorted backend task IDs, and validate observed task IDs. Never zip independent lists.
- Historical fixed acceptance map: {0:44,1:235,2:43,3:546,4:6,5:621,6:197,7:87,8:151,9:548}. This set is historically exposed and is not an unseen test set.
- Dev: freeze a separate seed block after exposure inventory. Baseline Q0 and P2 cover all 10 tasks. For every candidate's evaluated tasks, run paired same-round P2. Include Q0 at baseline and promotions.
- Validation: candidate, P2 and Q0 on 10 tasks x2 frozen new seeds (60 attempts). Candidate must achieve >=10/20 and no fewer successes than either control; disclose both complete blocks and all regressions.
- Formal: one frozen candidate, all 10 fixed acceptance records. Run P2, Q0 and compute-matched candidate QD removal/replacement. Candidate >=5/10 and >= each P2/Q0. No candidate changes or second formal candidate after reveal.
- Backend currently fixes init-state row0 irrespective of seed (`core/env_adapters/libero_adapter.py:621,939`). New seeds test stochastic robustness at the same layout; no unseen-layout claim. Bind actual init-file and row hashes for every task.

## Validity and execution gates

Before online dispatch: freeze source, complete resolved config, checkpoint/encoder, BDDL/init-state, dependencies and guidance-cache fingerprints; verify cache target identity and Stage input contract. Engineering correction is separately labeled and rebaselined. Freeze 720-step maximum,20 Hz,8 executed actions,strict perturbation and deployment-visible information.

Hard checks: expected task/seed/init/config identity; finite tensors/rewards/actions; legal action shape and unmodified converter contract; no algorithm-caused qpos/physics/action execution errors; no information leakage; valid ordered unique accounting; complete video/metric/result artifact records or an explicit invalid record; no protected input mutation. Any algorithm numerical/execution failure counts as a failed episode and remains in safety reporting, never discarded as infrastructure.

QD semantics: retain actual behavioral differentiation, quality-based archive/replacement or selection, and EDS proposal/renoise search; trace actual path use. Per complete guided chunk keep population16,iterations10,176 candidate evaluations,11 score batches. Report model batch/denoising/reward/VLM calls, latency and full-episode GPU-hours. Coverage/overflow/rescue are explanatory, not arbitrary task-disconnected rejection thresholds. Only enforce a retention invariant if that candidate preregisters it.

## Promotion and stopping

Candidate mechanism/CPU checks first, then paired Dev; no automatic promotion from proxy improvement. Freeze the candidate-specific Dev promotion rule before any of its Dev outcomes. Outer-loop after 3 valid candidates, two consecutive no-task-improvement candidates, or mechanism/outcome contradiction. One bounded targeted evidence review may justify a different in-scope mechanism; otherwise conclude TARGET_NOT_MET. A single failed candidate does not terminate the study. Target achieved stops new exploration. No main merge/push/publication.
