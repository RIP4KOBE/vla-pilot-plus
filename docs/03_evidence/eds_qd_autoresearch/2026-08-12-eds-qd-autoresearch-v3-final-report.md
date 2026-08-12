# EDS-QD Autoresearch v3 Final Report

Date: 2026-08-12
Decision: `CONCLUDE_NO_ADOPTION_WITHIN_V3_CYCLE_TARGET_NOT_MET`

## Outcome

V3 did not achieve the primary objective of `>=5/10` valid successes on LIBERO-PRO `libero_object_swap`. The sole candidate, `eds_qd_global_quality_anchor_v1`, passed offline and online mechanism gates and produced a limited Run033 gain (`0/3 -> 1/3`, task 9), but failed to transfer on frozen Dev-A: control and candidate both scored `0/6` on tasks `[0,1,2,4,6,7]`.

Run034 failed both preregistered success gates: candidate `0 < 3/6` and candidate-control delta `0 < +1`. Validation and formal evaluation were correctly not authorized or run. Historical formal EDS-QD best therefore remains `2/10`, leaving gap 3 to the required target.

## What changed and what was learned

The v3 candidate made one narrow QD-core change: reserve one of 16 parent slots for the current archive global-best lineage and allocate the remaining 15 with unchanged sparse priority. All parents retained the original renoise/rollout path and each complete chunk remained at `176 search / 176 QD / 11 score calls`.

Evidence accumulated in order:

- Run030 replayed 3,205 eligible historical transitions exactly and found that sparse allocation gave the prior global-best cell zero descendants in 2,151 transitions (`67.11%`). The frozen `1+15` counterfactual removed all such omissions while retaining median occupied-cell coverage 1.0.
- Run031 implemented the candidate behind a default-off setting; Run032 verified real integrated omission rescue, overlap-without-deduplication, deterministic behavior, safety, final selection and compute identity.
- Run033 produced candidate `1/3` versus control `0/3`, gaining task 9 with no loss. The candidate logged 1,100 activations and 751 rescues in 110 records.
- Run034 produced candidate `0/6` versus control `0/6`. The candidate logged another 1,060 activations and 425 rescues in 106 records, yet every task timed out without completion.

The central conclusion is therefore bounded: global-best lineage omission is a real QD allocation defect, and the anchor reliably repairs it, but this repair alone does not align archive quality/final selection with manipulation completion. Rescue frequency is not a success proxy. Run033's task-9 gain was insufficiently transferable to justify validation or formal evaluation.

## Run034 task and hard-gate result

| Task | Control | Candidate | Delta |
|---|---:|---:|---:|
| 0 | fail | fail | 0 |
| 1 | fail | fail | 0 |
| 2 | fail | fail | 0 |
| 4 | fail | fail | 0 |
| 6 | fail | fail | 0 |
| 7 | fail | fail | 0 |

Every one of the 12 cells was valid, exited 0, and produced exact metadata/video evidence under strict perturbations. The audited failure class for each unsuccessful episode is only `timeout without completion`; no unsupported finer cause is claimed.

All non-task gates passed:

- candidate exact `1+15` allocation and 10 activations per record;
- fixed `176/176/11` compute and complete source/fingerprint/final-selection telemetry;
- no nonfinite, action-mask, execution-qpos, fallback or disallowed safety event;
- candidate/control selection-latency P95 ratio `1.052894 <= 1.25`;
- exact attempt, manifest, artifact, credential and write-boundary integrity.

Run034 audit SHA-256 is `2e590656dd60a18a17bf45ff7a2e1e9209daaaa34980a5d686b9d6f8879a0e68`. Its only hard failures are the two success gates.

## Infrastructure, accounting and integrity

Run033's first IDs 67–72 stopped before episode 0 because an isolated DINOv2 cache attempted GitHub validation and received HTTP 403. The failure produced no task result. A protocol-first runner-only cache repair preserved the incident read-only and used exact-cell IDs 73–78 after fresh admission; no scientific setting changed.

Final accounting:

- effective online episodes: `66`;
- global reservations: `90/143`;
- infrastructure recovery slots consumed: `6/19`, leaving 13;
- cumulative GPU device wall: `5.447063166666667/48 h`;
- validation episodes in v3: `0`;
- formal episodes: `0`.

The final v3 decision manifest is mode 0444 with SHA-256 `5363af6996404c573f989c6c729d64a0f2c89a48a365e1e271b508654cec75a8`. Exact scans found zero copies of the approved runtime credential in the Run034 artifact tree or tracked worktree; no credential value or reversible fingerprint was recorded. The protected untracked design was excluded throughout.

## Stop boundary

The frozen design permits one H4-v3 candidate and requires a valid Dev-A failure to end the cycle. Accordingly, there is no validation, formal run, fourth candidate, anchor-count/sparse-ratio/threshold sweep or Run034-driven tuning. No algorithm or online execution remains authorized.

Any future work requires a new versioned design, new leakage-safe development/validation splits, an explicit remaining budget and explicit user approval. V3 may be used only as historical evidence. The next research diagnosis remains QD-first and inside EDS+QD: lineage retention is insufficient while archive quality and final execution selection are weakly aligned with observable task progress. That diagnosis is not an authorized implementation.

The complete append-only chronology is in `docs/03_evidence/eds_qd_autoresearch/iteration-ledger.md`; detailed Run034 evidence is in `experiments/run_034_global_quality_anchor_dev_a/analysis.md`.
