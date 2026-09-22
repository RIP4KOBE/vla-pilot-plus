# Resume this authorized research task

Authority: `research-state.yaml` and `iteration-ledger.md`. Run `rdt-qd-ed-final-20260921T093925Z`; artifact root `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z`.

## Current evidence

Five episodes dispatched: two invalid task failures (original baseline startup and N1 Q0 r3 nativeSIGABRT), three infrastructure aborts. Zero valid outcomes. At this checkpoint no live queue/worker exists; inspect the native queue process/status files for subsequent launch evidence. Closed cost0.4306699061807659 GPU-hours. r3 completed3partialchunks(step0/8/16) and one real Codex Stage query atstep24 (19.772s,10800input/42outputtokens), then crashed. Native causeUnknown; signalconfirmedbyapport butcorelimit0. Neither invalid sample may be ordinarily retried. Candidate/validation/formal remainunmeasured. The zero-simulation policy diagnostic passed37 CPU tests and its GPU7-only durable queue is being frozen; keep it separate from scientificepisodes and chargeitsGPUwalltime.

N1 protocol was committed in `56031d2` before implementation. It changes only the archive descriptor to target distance and eight-action positive gripper-command duty; CPU proxies are not online success evidence. Review `experiments/iteration_001_execution_intent/analysis.md` and the startup/provider/resource amendments before any scientific decision.

## Active resource continuation

The latest user instruction requires all subsequent work on physical GPU7 only, superseding the earlier any-GPU authorization. Keep one worker and exclusive admission because execution specification section9 forbids sharing external research processes. The sharing question has no answer; elapsed time is not authorization.

The reviewed queue queries server inventory every30 seconds but may select only GPU7 and requires no compute process, no detected external declared CUDA mask, less than1024MiB memory, and120 seconds of continuously observed idle state. It queries metadata without allocating CUDA while waiting. Process mask checks are conservative potential-conflict evidence, not official reservations. Recheck before context/episode launch and monitor runtime exclusivity. The reviewed NVIDIA metadata query timeout is15 seconds, with40 seconds termination overhead reserved against the total budget; episode timeout remains1800 seconds. Only terminate our owned worker if a conflict occurs.

Plan `data/qd-ed-n1-monitor-recovery-plan.json` contains30 unique scientific cells and three explicitly linked recovery rows. r3 was already dispatched and ended nonretryable-invalid; do not replay it or automatically run the pairedP2. Recovery r3 linked exact monitor-aborted r2 `...5621b7ebde96`. All dispatch errors stop for review, with no queue-generated retry. Preserve original invalid `...49b1a88877f7` and aborted `...2b5e035fd6bb`/`...1eb8b4580e78` unchanged.

Before any intervention inspect `<artifact-root>/runtime/native-probe-queue-process.json` and `native-probe-queue-status.json` for the bounded diagnostic, plus the historical `available-gpu-queue-process.json` and `available-gpu-queue-status.json`, check PID lifetime, and read the append-only episode/healthcheck journals. Previous queues PID3927573,3969643 and3996172 are dead. Their failed evidence is archived in `runtime/queue-history/a7f3f56-first-recovery` and `runtime/queue-history/32d4d97-monitor-timeout`, and `runtime/queue-history/8fb001b-native-abort`. Never start duplicate queues or change frozen source HEAD while a queue is alive. Status `starting` may mean CPU model-byte validation; `waiting` means resource wait; `running` is a runner handoff and must be checked against the episode journal; `completed` means only the requested pair.

A device change creates a hardware-only child runtime/plan with selected UUID, PCI and actual CUDA/EGL proof. Reuse only matching audited zero-step proof; account new probes otherwise. GPU7 andGPU5 v2 context proofs are available in the healthcheck journal; GPU5 probe completed successfully before r2 dispatch. Scientific profiles, seeds and provider condition remain frozen across controls/candidate.

## Ordered research continuation

1. Verify authoritative state, queue lifetime, no unfinished owned attempt, frozen source/runtime/provider/input hashes and remaining budget. Do not edit historical/main worktrees or secret files.
2. Current Stage condition is `codex_login_astra_low_v1`, official Codex CLI with existing ChatGPT login, model gpt-6-astra/low. Preserve Poe credentials, clear child credential/provider overrides, keep the original Stage template and triggers. The synthetic two-image production probe passed; this is transport evidence, not robot accuracy or whole-study quota assurance. HTTP requests/retries remain unknown; observed logical calls/tokens/latency must be accounted.
3. Review the first Q0/P2 pair for implementation validity and actual cost, not success-based stopping. Then finish all20 same-round controls before authorizing N1's10 candidate cells. The underlying runner does not enforce controls-before-candidate; always specify explicit pending episode keys. Invalid cells remain visible; no automatic iteration reset to erase failure.
4. Evaluate N1 under the original >=5/10 and >=both-controls Dev gate plus substantive-QD and cost requirements. A scientifically valid failure requires bounded outer-loop review, not automatic project termination. Validation and formal remain closed until their preregistered gates pass; never tune on exposed validation or rerun a modified formal candidate.
5. Preserve240 total dispatched attempts and48 GPU-process hours, including all failures, recovery, healthchecks, startup and Codex waiting. Protect validation/formal reservations. Completion requires evidence for the specified formal target; queued work or passing CPU checks is not success.

Arbor authorization continues only for this explicitly invoked task; implicit invocation remains disabled. Never merge or push main.
