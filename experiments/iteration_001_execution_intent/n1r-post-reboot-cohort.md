# N1R common post-reboot cohort — 2026-09-23

The user-authorized next-round protocol and GPU2-only execution remain in force.
After the explicitly requested reboot, the production-path diagnostic
GPU2_POST_REBOOT_C0/task0 completed720steps in879.081084423seconds, with valid
outcome/cost telemetry,28/28 successful Stage calls and no monitored Xid.
Its task result was failure(0/1), preserved and excluded from this new cohort.
Audit: artifact analysis/gpu2-post-reboot/audit.json. Previously observed
post-inference rendering faults did not recur across this complete episode;
this supports restoring execution but does not identify their root cause or
guarantee future hardware stability. No driver, model or algorithm change.

Freeze iteration N1R with30 development cells, C0/Q0/N1 each10, using the
original frozen Dev task/env_seed/policy_seed/init map. Keep the existing
order from data/qd-ed-n1-dev-plan.json: Q0,C0 on even tasks; C0,Q0 on odd tasks,
tasks0..9; then N1 tasks0..9. New keys n1r_dev_tXX_PROFILE. This common
engineering cohort was authorized before the diagnostic and is reported
separately from the closed original N1 cohort. No diagnostic/old-cohort cell
can be substituted, pooled or relabeled into it, including C0task0.

All arms use the same frozen source, weights, inputs, runtime and Stage
contract(input_repaired + codex_login_astra_low_v1), physicalGPU2/CUDAlogical0/
EGLindex1, normal caching allocator, no sanitizer, no serialization/lifetime
intervention. Keep720environment steps,1800second per-episode ceiling,
RDT EMA/five diffusion steps/pred64/execute8, fixed ED budget and existing
trace/plot limits. Q0 remains original sparse QD; N1 changes only its
descriptor to target_distance_gripper_duty_v1. C0 disables QD at matching
search budget. No tuning from the diagnostic outcome.

The first two N1 cells are the already-planned implementation/finite checks,
not extra trials or success-based screening. Existing per-episode validators
check resolved parameters, task/seed identity, finite actions,176evaluations/
11score batches per guided chunk, archive accounting, video, Stage results
and complete cost telemetry. Preserve traces for descriptor/activity review.
Stop for any invalid result/infrastructure abort; never automatically repeat
a dispatched cell. Valid task failures continue the frozen sequence.

Use the shared append-only ledgers and single-worker lock. Before this cohort:
14total dispatched,9aborted,4invalid,1valid(the excluded diagnostic); 8development
attempts consumed. The new30fit within100development attempts and240total.
Protect14validation+10formal GPUhours within the unchanged48GPU-hour cap.
Thirty1800second ceilings plus cleanup need at most about15.34GPUhours;
the currently available unprotected allowance exceeds22GPUhours.

No validation/formal dispatch in this plan. After all30 valid cells, report
per-task C0/Q0/N1 outcomes, gained/lost tasks, mechanism evidence and all costs.
Dev promotion remains N1>=5/10 and >=both same-round controls with necessary
validity/activity checks; otherwise choose only the previously authorized N2/H
route supported by results and remaining budget. Preserve the parent's
historical TARGET_NOT_MET/NO_ADOPTION report and its original accounting cutoff.

ETA remains a provisional8–15hours including Stage waits, plus GPU admission
waits. The single completed diagnostic took14.65minutes, of which11.18minutes
were Stage latency; this alone cannot establish all-arm/all-task throughput.
Refine after2–3 complete cohort episodes. Progress is reported in the current
conversation and durable queue status files; no tmux action is required.
