# RDT + QD + ED unified iteration ledger

## iteration_000_intake — ACTIVE

New authorized cycle from `744e08b`; historical Run045 remains no-adoption. GPU7 only; currently blocked for online dispatch by external occupancy. Zero new episodes and zero GPU-hours. Baseline/profile, source evidence, infrastructure and exposure audit pending. Budget reservations: baseline 20, development 100, validation 60, formal 40, recovery 20 (total 240). No new algorithm candidate selected.

### Intake checkpoint 2026-09-21T09:52:11.562866+00:00

- Protocol commit: `7c5fbcf`. New scientific dispatches0; GPU-hours0.
- Q0/C0 algorithm parity: executor reports173 focused tests passed and48 differential archive scenarios matched across historical/latest code; report pending review.
- Runtime engineering findings: task-ambiguous shared cache, stale LIBERO config, empty local gitlinks. Local repair separately authorized by execution prompt; current provider mismatch requires user decision.
- Single-task launcher will freeze both policy RNG and env seed; this differs from historical sequential RNG streams and is applied to every same-round arm.
- Algorithm candidate remains unselected pending bounded historical executable-behavior diagnosis.

- Arbor bookkeeping correction: generic report parser interpreted a diagnostic89.0% as node task score. Cleared node1 score to null immediately, restored root IN_PROGRESS, retained parser correction in metrics. No new episode exists and this number is never performance evidence. Future diagnostic nodes avoid automatic report score extraction.

### Preregistered N1 checkpoint 2026-09-21T10:13:54.407437+00:00

- Protocol and seed plan committed before implementation in `56031d2`; no outcomes revealed. `data/frozen-seed-plan.json` SHA-256 `9bbcf7107f6be4f739870a034ea84c4695819bdc1bffe5aa1148f453acf4a6b1`. Dev10 cells, preallocated unused validation cohorts, and historical formal10 identity mapping use explicit task/env seed/policy seed/init-row hashes.
- Historical evidence: 20/20 Q0 fixed-pool replays reproduce archived outcomes; 82 gripper-discordant eliminations, 73 separated by four fixed positive-command-duty bins. These are behavioral diagnostics, never success-rate or counterfactual evidence.
- N1 is the single preregistered change: projected t8 target distance and exact eight-action positive gripper command duty in a 4x4 capacity-one archive. Quality, sparse parent allocation, and EDS budget stay fixed. Azimuth and within-duty timing information loss are explicit tradeoffs.
- Controls use task-bound Stage descriptions with byte-identical canonical reward functions, owned dependency/LIBERO paths, and explicit per-task policy RNG. Label all arms `input_repaired`; do not attribute these engineering differences to QD.
- Added observed whole-episode model/reward/API-retry counters and conservative failure accounting. GPU healthchecks count toward48h even without an episode; every dispatched episode, including failures and recovery, consumes240-attempt budget.
- Current online dispatches0; GPU-hours0. GPU7 still externally occupied (PID1672968). Historical Poe Stage endpoint and injected rawchat.cn endpoint differ; no request sent and no credential redirected. Required provider question remains pending.

### CPU-ready checkpoint 2026-09-21T10:31:45.715162+00:00

- Integrated regression:631 passed in35.83s; known NetworkX deprecation and expected CUDA-disabled warning in a mocked startup test. Final completion/validity accounting change:51 runner/report/probe tests passed in0.27s. No GPU context was initialized.
- Baseline20 resolved config previews and N1 single-change profile/compose review passed. An initial runtime-manifest duplicate-path failure was fixed by binding lexical symlink identity and owned target hashes; subsequent draft validation passed. Plans remain unfrozen and all phase gates false.
- Actual cost counters now cover RDT DiT and encoders, DINO, reward functions, denoising and API send attempts/retries; inactive SAM/grounding are explicit. Debug scoring overhead is included in actual counters and is not hidden behind176/11.
- N1 approximate radial replay retains27/82 old gripper-discordant eliminations;25 are selected as subsequent parents. Median occupancy16→4,7814 new same-cell pairs versus986 separated: substantial information loss. No new outcome, bin tuning or proxy-only promotion. See candidate analysis for exact/approximate boundaries.
- State:WAITING_RUNTIME_PREREQUISITES, project target IN_PROGRESS, candidate CPU_READY_UNEVALUATED. All online scores null.0 dispatched/valid/invalid/aborted episodes and0 GPU-hours. Last GPU7 snapshot3519MiB with external PID1672968; Stage provider decision pending.
- GPU7-only exclusive worker, explicit recovery lineage, all attempt costs, and protected remaining validation14h/formal10h are enforced. Hour reservation changes require a reasoned journal event before dispatch. Terminal `event: valid` is distinguished from scientific `outcome_valid`; invalid algorithm failures remain in denominator.
- Resume instructions:`docs/03_evidence/qd_ed_final/resume.md`; CPU validation evidence:`/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/iteration_000_intake/cpu-validation.json`. No main merge/push, historical artifact modification, provider request or simulation rollout occurred.

### Runtime and requested provider migration checkpoint 2026-09-22

- GPU7 became available. Two accounted zero-step synthetic context probes consumed0.005810367842075519 GPU-hours. The first exposed a masked CUDA/EGL ordinal assertion bug; the corrected second probe passed actual UUID/render/compute checks. Physical GPU7 maps to logical CUDA0 and EGL4 under the mask. GPU7 remains the only authorized local GPU; admission is rechecked before dispatch. Focused probe/launcher/runner/report checks:88 passed.
- Poe generation requests using both configured credential names returned401 `invalid_api_key`; the two names hold the same value. Credential values were never exposed. GET `/models`200 had incorrectly been labeled authenticated; `runtime/provider-adjudication-20260922.json` explicitly supersedes that inference while preserving the observation. The user confirms Poe is no longer usable and requests the current Codex account instead.
- Saved ChatGPT login via Codex CLI0.155.1 and `gpt-6-astra` passed a CPU-only synthetic image/schema probe in16.908629757352173s, using16735 input and19 output tokens. No benchmark image or simulation was used. This is transport feasibility, not Stage-quality or whole-study quota evidence. See `codex-provider-feasibility.md` and the artifact-root probe summary.
- Old Poe configuration is preserved. Production Stage remains Gemini/Poe and not ready; draft plans remain unfrozen with all phase gates false. Resolve the intended Codex/API credential route, then apply and freeze a common model/provider condition across Q0/P2/N1 before new baseline episodes. Do not attribute the provider change to QD.
- Still0 dispatched/valid/invalid/aborted episodes, all task scores null, project IN_PROGRESS and N1 CPU_READY_UNEVALUATED. GPU context readiness is true; Stage provider readiness remains false. No new episode is admitted merely because the synthetic image probe passed.

### Codex integration checkpoint 2026-09-22T03:39:31Z

- User explicitly chose current Codex login. Common provider amendment: `experiments/iteration_001_execution_intent/codex-provider-amendment.md`. All arms use `codex_login_astra_low_v1`; original algorithm, seeds and budgets remain fixed, Poe configuration preserved.
- Fresh executor work separated Stage transport/policy, main startup/telemetry and runner/launcher/report changes. Integrated validation:673 CPU tests passed in40.74s. No GPU/episode use by tests or API probes.
- A first adapter probe failed closed on a CLI skill-context warning. Local no-inference prompt inspection established that CLI0.155.1 requires disabled skill FILE paths rather than folder paths. Corrected public policy disables116 skills within each Stage invocation; global skill policies remain unchanged.
- Production-adapter probev2 passed unchanged Stage-template/two-image transport, one turn, complete usage and no tool/warning item.33.5436s,9780 input/69 output/21 reasoning tokens. This is not task-success or quota evidence. Full artifacts and fixed identities in `codex-integration.md`.
- New runtime manifest is `runtime/codex-setup-manifest.json`; original setup and pre-migration draft remain preserved. Next freeze refreshed source/config plan and dispatch the initial paired baseline cells on exclusive GPU7. At this checkpoint episodes remain0 and GPU-hours0.005810367842075519.

### Counted baseline startup failure 2026-09-22T03:55:55.226809+00:00

- Source `4d9cd5d31e8dde6d298ec10805cde4542d5765a2`; frozen plan SHA256 `2d12ceb95b51a6d8bea317864b801711cdc138fd685382e23d5b4526192432ac`, archived unchanged at `frozen_plans/baseline-codex-4d9cd5d31e8d.json`.
- Attempt `rdt-qd-ed-final-20260921T093925Z__baseline_dev_t00_q0__49b1a88877f7` dispatched on physical GPU7 and failed before episode execution: zero actions and zero Stage queries. Stage configuration was overwritten by the grounding section, causing the legacy client factory to fail on missing API credentials. The Codex fail-closed guard stopped startup; no credential fallback was added.
- Retain the terminal invalid failed sample, its baseline denominator cell, and70.7454865318723 GPU seconds. No automatic retry or infrastructure reclassification. Total1 dispatched,0 valid,1 invalid,0 aborted; total GPU-hours0.025461891878706712 including both healthchecks. No scientific robot-success or N1 mechanism inference follows from this failure.
- A bounded startup routing repair and real-factory CPU regression are assigned to the existing executor. The old source/plan/output remain preserved; any subsequent dispatch requires a newly frozen source version and explicit selection of pending identities.

### Prospective repair/control ordering 2026-09-22T03:57:56.998355+00:00

- Startup executor separated Stage/grounding configuration;118 CPU tests passed, including real factory construction without API keys and default-provider regressions. No GPU or network in these tests.
- Original baseline closed as1 invalid and19 not dispatched; expected20 retained and complete success rates null. Report:`iteration_000_intake/closed-incomplete-baseline-report.json`. No failed identity retry or outcome replacement.
- Freeze `startup-repair-amendment.md` before further dispatch: the already planned N1 Dev allowance≤30 now runs all Q0/P2 controls first, then N1. New full cohort iteration `N1`, development bucket; identical repaired source/runtime for every arm. This establishes a valid repaired common baseline without spending another20 reserved baseline episodes. No reservation transfer or promotion-threshold change.

### N1 repaired common-source freeze 2026-09-22T04:00:38.011380+00:00

- Source `71b5880c3dac41a5d26ba678b366f962b5a4af1f`; plan `data/qd-ed-n1-dev-plan.json` SHA256 `080985fead54fac3806702c0d8db51904ef94c6aa2231b21cecbf38c7f7bcbfd`; immutable snapshot `frozen_plans/n1-dev-codex-71b5880c3dac.json`.30 complete Hydra configurations composed and checked without GPU; provider login and all input/model/runtime hashes verified. No nonempty credential fields in previews.
- Existing runtime/profile/seed/provider policy unchanged. First dispatch `n1_dev_t00_q0`; subsequent paired control `n1_dev_t00_c0`. All20 control cells must be valid before any candidate dispatch; candidate and validation/formal gates remain closed.

### GPU admission block 2026-09-22T04:03:35.349714+00:00

- Repaired N1 plan and saved Codex login passed full launcher verification. Runner rejected dispatch because GPU7 acquired external compute PID3726503 (`wholebodywam`), approximately7396MiB process memory. No experiment reservation/dispatch was appended, no GPU sharing/termination occurred, and no owned worker remains live.
- State WAITING_GPU7; totals unchanged:1 dispatched,0 valid,1 invalid,0 aborted;0.025461891878706712 GPU-hours. Project IN_PROGRESS, N1 task score unknown, validation/formal unopened. Frozen source71b5880 and plan remain ready; recheck admission before first N1-round pair.

### User-authorized hardware change 2026-09-22T04:31:51.394735+00:00

- User explicitly instructs “改用5”; physicalGPU5 only now supersedes the earlier GPU7-only resource restriction for future work in this study. Single exclusive worker, no sharing/preemption/substitution, all budgets and scientific gates unchanged.
- Initial read-only GPU5 observation: H200NVL, UUID `GPU-048017bf-c58f-b622-ca2e-000b668c651b`, PCI `00000000:A1:00.0`,5MiB/0%, no compute process. This is not actual CUDA/EGL verification; admission must be rechecked.
- Old GPU7 manifests/plans/probe evidence/failed baseline remain immutable and counted. New GPU5 mapping, healthcheck, source and common N1 plan will be frozen before dispatch. N1 cohort still has zero dispatched cells; no score or seed changes.

### GPU5 binding and initial admission 2026-09-22T04:37:01.603807+00:00

- Runner/launcher CPU checks61 passed; generic metadata/probe checks64 passed. Runtime authorization, admission, exclusivity monitoring, environment and accounting bind the same selected device; historicalGPU7 evidence remains compatible.
- Read-only enumeration binds GPU5 UUID `GPU-048017bf-c58f-b622-ca2e-000b668c651b`, PCI `00000000:A1:00.0`, EGL7. New manifest:`runtime/codex-gpu5-setup-manifest.json`; originalGPU7 files unchanged. Actual CUDA/EGL readiness is false until a new healthcheck succeeds.
- Attempted probe was rejected before reservation/dispatch: external compute PID3816377 appeared on GPU5 (612MiB process memory at observation). No healthcheck or episode event was appended, no additional GPU time spent. Budget unchanged1 dispatched/1 invalid and0.025461891878706712 GPU-hours.

### GPU5 ready except exclusive context admission 2026-09-22T04:40:02.466796+00:00

- Source `8fdf85b8b4071cff8d57721e183543546d9fc1eb`; draft plan `data/qd-ed-n1-dev-gpu5-plan.json` SHA256 `5ae8bf3acf903e0c335d61f30982734a9cea87c0a2fec4c5f3d3f59bfe214604`.30 full Hydra configs composed; model/input bytes and existing Codex login verified. Child environment explicitlyCUDA_VISIBLE_DEVICES=5,CUDA_DEVICE_ORDER=PCI_BUS_ID,MUJOCO_EGL_DEVICE_ID=7.
- GPU5 still has external compute PID(s)3816377 and623MiB device memory. No owned worker or actualGPU5 context; no additional healthcheck/episode dispatch or GPU cost. State WAITING_GPU5. The plan remains unfrozen with all phase gates false until the real context probe passes.

### Any available server GPU authorized 2026-09-22T04:58:53.637965+00:00

- User authorizes any usable GPU on this server, superseding fixedGPU5/GPU7 restrictions. Still one exclusive worker with per-dispatch identity/admission checks, no sharing/preemption and unchanged scientific/budget gates.
- Current all-device scan:GPU7 free, other seven have external compute processes. SelectGPU7; existing actual CUDA logical0/EGL4 proof and frozen UUID validate unchanged. No redundant healthcheck needed for this same binding. Previous GPU5 preparation never dispatched a healthcheck or episode.
- Freeze `available-gpu-amendment.md` and a new source-bound plan; all thirty N1 cells and provider/non-hardware inputs remain identical. No task retries or historical record replacement.

### Available-GPU plan frozen 2026-09-22T05:00:10.407382+00:00

- Source `16f7fae1d948ad8359fa1b64d56352a1914e89ac`; plan `data/qd-ed-n1-dev-available-plan.json` SHA256 `56f41cfe5eabe706076a85c44d093c4aff7252308f11fe2ab7467573da967f5f`; snapshot `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/frozen_plans/n1-dev-available-gpu7-16f7fae1d948.json`.30 resolved configs, current GPU7/driver/EGL mapping, model/input/runtime hashes and Codex login verified. First selected control pair:task0 Q0/P2; candidate gate remains closed.

### Counted external-device race 2026-09-22T05:03:31.281023+00:00

- N1-round Q0 task0 attempt `rdt-qd-ed-final-20260921T093925Z__n1_dev_t00_q0__2b5e035fd6bb` dispatched onGPU7, then external PID3879749 appeared during startup. Existing exclusive monitor stopped only our worker. No Stage query or policy rollout outcome was recorded.
- Terminal `aborted`, failure_class infrastructure, retryable_infrastructure true;12.277869774959981 GPU seconds charged. Total2 dispatched,1 invalid originalbaseline,1 infrastructureabort; GPU-hours0.028872411260640045. Never reclassify the originalbaseline implementation failure.
- Prepare explicit linked recovery key `n1_dev_t00_q0_r1`, sameprofile/task/envseed/policyseed/init/iteration, retry_of the exact aborted ID, recovery budgetbucket. This replaces only the unresolved infrastructure attempt for cohort accounting; everyattemptcost remains. All8GPUcards now haveexternalprocesses. A persistent CPU-only availabilityqueue will select anidlecard and run this recovery plusP2, then stopforreview; postdispatcherrors willnotauto-repeat.

### Persistent available-GPU queue implementation 2026-09-22T05:13:23.226072+00:00

- Scoped executor added only `scripts/qd_ed_available_gpu_queue.py` and20 CPU regression tests, all passed in0.23s. No GPU/network or runtime mutation by executor.
- Queue waits using NVIDIA metadata, selects only explicitly authorized idle cards, records hardware-only new manifests/plans, and uses existing accounted probes/runner. It retains nonhardware/provider/source/seed identities. GPU admission races before any dispatch return to CPU waiting; any error after a dispatched probe/episode stops for review. Source/input/auth drift and exhausted budgets stop explicitly.
- Current request queued for exact linked infrastructure recovery `n1_dev_t00_q0_r1` plus paired `n1_dev_t00_c0`, then review before remaining controls. Original baseline invalid never retried. A separate user clarification asks whether to relax the original no-sharing rule; no answer yet, so exclusive mode remains mandatory.

### Recovery queue source/input freeze 2026-09-22T05:14:28.335787+00:00

- Source `a7f3f56129fdca92f01b1d97b607eb4c1d432814`; plan SHA256 `76dd6c65d473c4b6386c22ff7b8fb364db5cba8c909c51f3e718ae33d9c72b6e`; immutable snapshot `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/frozen_plans/n1-recovery-queue-a7f3f56129fd.json`.31 fully resolved rows represent30 unique original scientific cells, including one explicit infrastructure recovery. All model/runtime/input hashes and existing Codex login reverified. Selected recovery/P2 keys only; no candidate dispatch authorized.

### Persistent queue started 2026-09-22T05:17:55.476835+00:00

- Detached CPU queue PID3927573 launched for the explicit Q0 infrastructure recovery and pairedP2. Default polling30seconds over all eight authorized server GPUs. Process record:`runtime/available-gpu-queue-process.json`; status:`runtime/available-gpu-queue-status.json`; queue log:`runtime/available-gpu-queue.log`. No extra GPU/episode dispatch at launch.
- Sharing clarification unanswered; original section9 exclusive-device constraint remains. Queue status currently `running`; it must reach actual runtime/attempt evidence before claiming model execution. Pair completion is not study completion.

### Second external-device startup conflict 2026-09-22T05:22:06.551622+00:00

- Queue sourcea7f3f56 foundGPU7 temporarily idle, completed actual v2 CUDA/EGL probe `rdt-qd-ed-final-20260921T093925Z__gpu7_cuda_egl__4fafff3673e5` in13.493207043036819s, then dispatched linkedrecovery `rdt-qd-ed-final-20260921T093925Z__n1_dev_t00_q0_r1__1eb8b4580e78`. External PID3930135 appeared during RDT loading; the monitor stopped only our worker after37.324454808142036s. No Stage query or policy-rollout outcome. Queue exited failed as designed, not running in background now. Archived queue evidence:`runtime/queue-history/a7f3f56-first-recovery`.
- Total3 dispatched,1 invalid,2 infrastructureaborted,0 valid; GPU-hours0.04298842844152306. Actual probe and both abort costs remain counted.
- Read-only diagnostic of ONLY CUDA-visible-device declarations found external CPU-starting workers already naming the eventual GPU UUID before NVIDIA listed a compute context. This explains the apparent idle window. Add conservative declared-device conflict checks and a continuous120s idle window, all CPU-only and before any dispatch. These masks are potential resource conflicts, not proof of an official scheduler lease. No other environment fields may be logged.
- Root explicitly prepares exact linked `n1_dev_t00_q0_r2` recovery ofr1 using the recovery reserve; no source/seed/profile/task/init changes. Queue itself still never retries dispatched failures. Oldinvalidbaseline remains unretryable. Sharing question remains unanswered.

## 2026-09-22T05:27:55.330369+00:00 — conservative any-GPU queue admission

The two N1 Q0 infrastructure aborts were caused by external processes entering CUDA after a short apparent idle interval. Queue admission now observes accessible live-process CUDA_VISIBLE_DEVICES/CUDA_DEVICE_ORDER declarations (UUID masks or provable PCI_BUS_ID ordinals only), stores only per-device PID metadata, and requires 120 seconds of continuously observed idle state. This is a potential-conflict heuristic, not a scheduler lease. Existing NVIDIA admission and runtime exclusivity monitoring remain in force. No sharing permission has been received. The executor and root each passed all 26 queue CPU tests; no additional GPU probe or episode was dispatched during this repair.

One explicit recovery row n1_dev_t00_q0_r2 is linked to aborted attempt rdt-qd-ed-final-20260921T093925Z__n1_dev_t00_q0_r1__1eb8b4580e78, preserving identity and all costs. Only this recovery and paired P2 control may run before root reviews implementation and cost. The queue itself never retries a dispatched failure. Current totals: 3 dispatched, 0 valid, 1 invalid, 2 infrastructure aborts, 0.04298842844152306 GPU-hours including all healthchecks. Source and scientific inputs will be frozen before launch; actual model bytes are rechecked by the queue before dispatch.

## 2026-09-22T05:30:52.465794+00:00 — stable-idle continuation frozen and queued

Source 32d4d97c9773a2099b59c3128b3476e6980e95d5;32 resolved Hydra previews; frozen plan SHA256 10c280b86d48b25d5e750100103ae1771d1771e87eb22ba26a25b0026420c269. The first preview utility invocation lacked HydraConfig runtime context and failed before any dispatch; composing with the explicit preflight output directory then completed all32 previews. This was a CPU-only preparation error and consumed no GPU/episode budget. Model-byte verification is performed by the queue startup, not inferred from preview composition.

Detached queue PID3969643, process start ticks 373042546, is alive with initial status starting. It selects among GPU0..7, requires120 seconds stable exclusive idle and runs only n1_dev_t00_q0_r2 then n1_dev_t00_c0. It stops on any post-dispatch error or after the requested pair. All previous attempts, frozen plans, provider files and costs are preserved. Process/status/log files reside in the artifact runtime directory.

## 2026-09-22T05:36:06.296982+00:00 — actual GPU5 context and recovery dispatch

GPU5 was continuously idle and passed context proof resource `rdt-qd-ed-final-20260921T093925Z__gpu5_cuda_egl__a5ad637fabe8`: physical5, CUDA logical0, EGL7, expected UUID/PCI, rendered nonzero frame, zero simulation steps,14.246595337986946 accounted seconds. Hardware-only frozen child plan SHA256 `981ba8b4172cc236efb81bdb43d1a5b9ea74b79d7073a40155c181ff57b4b178`. Dispatched r2 Q0 `...5621b7ebde96` with current Codex login; model startup is in progress and no outcome is claimed. Source remains32d4d97c9773a2099b59c3128b3476e6980e95d5.

## 2026-09-22T05:39:47.403067+00:00 — r2 NVIDIA monitor timeout review

Recovery r2 `...5621b7ebde96` ended infrastructure-aborted after165.5755500169471 GPU-process seconds; both owned queue3969643 and episode3981276 are dead. Terminal evidence classified TimeoutExpired as infrastructure. In this source, that combination requires the nvidia-smi metadata query; the ordinary1800-second episode deadline has separate task-failure classification. The original exception message was not retained, so this attribution comes from the frozen exception classifier and code path. No external-GPU collision was recorded for r2.

The partial record contains one chunk at global_step0 with population16,11 score calls, and no Stage query. It is implementation-only evidence and no task result is inferred. A bounded resource monitor repair is being tested:15-second metadata timeout instead of5, explicit sanitized timeout cause, and40-second termination reserve to cover query+cleanup while preserving total48-hour budget. The configured scientific episode timeout remains1800 seconds. One explicit r3 row retains identical seeds/task/init/profile/iteration and links r2; no dispatch occurs before repair/source freeze. Current totals4 dispatched,3 infrastructure aborts,1 invalid,0 valid,0.09293902437344917 GPU-hours.

Monitor repair review completed:122 CPU tests passed across runner, context probe and available-GPU queue. Root reviewed the complete runner/test diff; actual episode deadline remains1800 seconds and nonretryable on expiry, external-PID detection remains fail-closed, and40-second cleanup headroom preserves budget safety. No scientific parameter or prior attempt evidence changed.

## 2026-09-22T05:46:18.754391+00:00 — monitor repair frozen and queued

Source8fb001b7903c5e6a2a74a5ef6a7f2845ca7e9fe2 and33 Hydra previews frozen in data/qd-ed-n1-monitor-recovery-plan.json, SHA256456c2c992c07b528909fdda892ce49890d3e18f17f6bbe99d1e2a736e6ee8f33. Detached queue PID3996172 completed full model/input/provider validation and now waits for the120-second exclusive idle admission window. GPU4/5/6 currently have no compute/declared-mask process. Only linked r3 recovery then pairedP2 are authorized for this queue. No new attempt is claimed by queue startup alone.

## 2026-09-22T05:50:03.249730+00:00 — GPU6 recovery dispatched

Queue detected new external masks/processes on GPU4/5 before admission and selected continuously idle GPU6. Actual zero-step context proof `rdt-qd-ed-final-20260921T093925Z__gpu6_cuda_egl__f77b064574fb` completed in 14.449357177130878 seconds. Hardware child plan `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/runtime/resource_queue/89d2dd719e0346bd9011931cc66731a0/plan.json`, SHA256 `6e08d9783d3e66fade7bb75b11da4145b76e186301fb2530bfea86c001e990d3`. Linked r3 Q0 `...6df33a24c65f` dispatched on physicalGPU6, Codex CLI gpt-6-astra, source8fb001b7903c5e6a2a74a5ef6a7f2845ca7e9fe2. Model initialization is in progress. Total5 dispatched,3 infrastructure aborts,1 invalid,1 running,0 valid; closed GPU cost0.09695273470042998 hours, with current episode time to be added at terminal accounting. No outcome is claimed.

## 2026-09-22T06:19:36.975062+00:00 — r3 native failure after successful real Codex Stage call

On physicalGPU6, r3 `...6df33a24c65f` terminated with child exit-6 after1201.3818173292093 GPU-process seconds. Apport entry for ownedPID4006998 confirms SIGABRT, corelimit0; no corefile exists. Queue3996172 and worker4006998 are dead. Existing frozen runner classified this as a nonretryable invalid task failure (eventvalid means adjudicated, not scientifically valid). Do not reclassify or retry the cell.

One real Codex Stage query atglobal_step24 succeeded:19.772138726897538s,10800input/42output/0reasoning tokens,1logicalcall,0failedcalls; HTTPrequests/retries remainUnknown. It changed stage1 guidanceTrue→False. The stage event was durable at06:07:45.497 and terminal result at06:07:48.574. Adapter audit found its successful subprocess exit/cleanup completed before Stage return, no parent environment mutation or SIGABRT emission, and the chunk-memory reset completed before event write. Subsequent model inference versus EGL/render/env.step cannot be distinguished without new instrumentation. Scheduler stale-history hypothesis was not supported by installed code.

Three partial guided chunks atsteps0/8/16 had select-action times3.413/3.292/3.575s. Approximately345s between chunk artifacts arises outside these calls. Isolated CPU microbenchmarks:8image conversions default0.452646s vsone-thread0.002114s;32inv/pinv pairs0.001780s vs0.002674s; exact outputs matched. Thread overhead alone cannot explain the observed delay, so no thread parameter is changed. Nonblocking py-spy diagnostic was denied by kernelptrace policy; no elevated attach was attempted and no worker state was changed. The standalone debugtool install is outside the frozen runtimeenvironment.

Totals5 dispatched,3 infrastructure aborts,2 invalid task failures,0valid,0running;0.4306699061807659 GPU-hours including all probes. No N1candidate/validation/formal score exists. A prospective phase timing patch and separately accounted zero-simulation B1 policy diagnostic are being reviewed; neither authorizes a scientific retry or erasure of failedcohorts.

## 2026-09-22T06:27:02.547214+00:00 — bounded native diagnostic CPU-ready

The standalone scripts/qd_ed_policy_native_probe.py and its37 passing CPU tests were reviewed. It uses frozen realRDT/T5/SigLIP, the production observation processor and _predict_unguided(B=1), deterministic synthetic images/proprioception/task text, no simulator instance/step/action, no Stage/API call, and an audit hook rejecting network/simulator imports. Real gym type imports remainallowed. CUDAidentity, source/model/runtime/provider fingerprints, runnerlock, exclusiveadmission/monitor and protectedGPUbudget are reused. All childstartup/inference/cleanup seconds enter the healthcheckledger; no scientific episode or successmetric is created. Phaseboundaries and faulthandler capture nativefailures; B1-only scope cannotestablish transition/EGL cause.

The prospective main phase-timing/faulthandler patch remains unapplied at runtime/debug-tools/phase-timing-proposal.patch (SHA25631b7f003f609442832f066a3335eb2858ab811c78e3d4d9d799c097ddbda7ede);6 CPU tests passed in memory and existing Main AST is unchanged after removing prospective diagnostic statements. No scientific run is newlyauthorized by these checks. Latest all-eight-GPU scan shows externalcompute on everycard; no GPUdiagnostic has been dispatched.

## 2026-09-22T06:36:54.904959+00:00 — user narrows all subsequent GPU work to physical GPU7

The latest instruction supersedes any-GPU authorization for future work. Authoritative candidate_indices and selected singleton are now [7]. No owned GPU worker or queue is running during this update. Historical GPU5/GPU6 attempts, outcomes and costs remain unchanged. The forthcoming native diagnostic queue must wait for GPU7 exclusively and never fall back to another card. Codex saved-login provider and retained Poe credentials are unchanged.

## 2026-09-22T06:39:39.500261+00:00 — GPU7 diagnostic queue reviewed

The independent native queue passed17 focused tests and80 combined CPU tests with the native probe and existing resource selector. Root reviewed the source and test boundaries. It requires all scientific gates false, frozen diagnostic scope/configuration/source, and dynamic GPU authorization. Only GPU7 is authorized. The original undispatched C0 row is used solely as a resource-binding budget/retry preflight anchor; runner.run_plan is never called. CPU waiting allocates no CUDA context; one diagnostic runs after120-second stable idle and then stops. Any dispatched resource failure stops without retry. Thirty-second atomic heartbeat continues during input verification and diagnostic execution. No GPU probe or episode was dispatched by testing.

## 2026-09-22T06:41:08.383396+00:00 — GPU7 native diagnostic queue frozen

Source b43ddd653d94f69b0e42259e31486d9e4db8ef58; plan qd-ed-native-gpu7-queue-v1-plan.json; SHA256 1f42729daf579393c7d292f3f1735b22983f41fcf44188e252e6e2d288860996. The first CPU-only freeze assertion found the older configuration preview wrapped its policy leaves in metadata. A new plain policy-configuration artifact now matches the queue contract exactly; the old preview and unlaunched preliminary plan remain preserved. No GPU process or episode was dispatched. Frozen runtime binds physical7/CUDA0/EGL4 and reuses audited GPU7v2 context proof. Full model-byte verification is performed by queue startup.

## 2026-09-22T06:43:20.949185+00:00 — GPU7 native queue launched

Detached queue PID4111605, start ticks373483170, plan SHA2561f42729daf579393c7d292f3f1735b22983f41fcf44188e252e6e2d288860996. Initial status starting means CPU input/model-byte validation, not a GPU dispatch. OnlyGPU7 authorized. The first launcher refused while a concurrent GPU6 probe from a separate artifact namespace was unfinished. That resource ...74d84549721c completed in15.178619010839611 seconds; its append-only evidence and cost are retained conservatively, without treating it as this continuation or changing GPU7 authorization. Total conservative closed GPU-hours now0.4348861892393325; scientific attempts unchanged5.

## 2026-09-22T06:47:36.812681+00:00 — native queue stopped before GPU dispatch on concurrent unfinished resource

PID4111605 completed full input/model verification and observed GPU7 idle, but a separate-namespace GPU6 native diagnostic ...b689d3b01c36 appeared unfinished in the shared resource journal. The queue stopped before any resource dispatch of its own; archived process/status/log evidence: /mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/runtime/queue-history/b43ddd6-concurrent-resource-journal. Do not bypass the single-worker/reconciliation gate. A minimal CPU-wait repair will keep a queue alive while this exact journal gate remains closed; it will not reconcile another task, ignore other gate failures, run in parallel or retry a dispatched sample.

## 2026-09-22T06:49:51.451825+00:00 — CPU-only journal wait repair reviewed

22 queue CPU tests pass. Root reviewed the14-line control-flow change: only the exact unfinished journal gate at the preselection loop enters waiting_journal, clearing old idle observations and selectedGPU. Other gates and any post-dispatch failure still stop. This is no scientific retry and consumes no GPU while waiting.

## 2026-09-22T06:51:25.427051+00:00 — journal-aware GPU7 queue launched

Source8771eaa74ede4159efb004e0709232175a6c0b8d; immutable v2 plan SHA2561ca7b9d970fc9b014820fc69596ec28100c55aed63a1416d23e7c1873d6d55a5; detached PID4127385, start ticks373525473. Startup verifies actual model bytes before waiting. Exact unfinished journal gate causes CPU-only waiting with idle history reset. GPU7 alone may dispatch one diagnostic; all scientific gates remain false. Earlier queue failures and separate-namespace resource costs remain preserved.

## 2026-09-22T06:55:26.355675+00:00 — concurrent scientific journal conflict, scope clarification pending

A separate artifact namespace dispatched GPU6 attempt gpu6_native_c0_t00/...6e57273c45b3 under source5cafac6586e2b2d5f05468de466fbd56c8334405 into this journal. It was not launched by this continuation. Global conservative accounting now sees6 dispatches, of which1 is this newly observed concurrent attempt; our queue has dispatched no GPU resource. PID4127385 remains alive with statuswaiting_journal; it must not bypass the journal or original episode-set guards. User was asked whether the separate GPU6 attempt also belongs to the GPU7 migration scope. Do not kill an unconfirmed concurrent task or claim GPU7 inference.

## 2026-09-22T07:24:24.103366+00:00 — user requests persistence until completion; GPU7 continuation resumed

The previously observed GPU6 C0 attempt already infrastructure-aborted after695.8362217219546seconds due to an external process. No external process was terminated by this continuation. Read-only inspection found the GPU6 branch journals symlink to this branch but its state file is separate, explaining the canonical state/ledger mismatch. Canonical accounting was resynced conservatively from append-only records: {'max_gpu_hours': 48.0, 'gpu_hours_consumed': 0.6606320209925374, 'max_episode_attempts': 240, 'reserved': {'baseline': 20, 'development': 100, 'validation': 60, 'formal': 40, 'recovery': 20}, 'dispatched': 6, 'aborted': 4, 'valid': 0, 'running': 0, 'invalid': 2, 'completed': 2, 'gpu_hour_reservations': {'validation': 14.0, 'formal': 10.0}}. PID4127385 had stopped before GPU dispatch on that mismatch; evidence archived. New CPU queue PID4193300, start ticks373729486, uses unchanged frozen8771eaa/v2 plan and physicalGPU7 only. Prior queue startup failures dispatched no resource and are not scientific retries.

## 2026-09-22T07:47:15.346241+00:00 — bounded runtime evidence review and unapplied observer ready

Read-only review of GPU6 C0 source5cafac6:13 completed steps used236.709s visualization overlay and261.282s adapter stepping; fresh policy calls3.904/3.085s; artifacts20.240/41.111s. Last open phase was step13 overlay before external-device abort. No Stage call/nativecrash observed in this diagnostic. Shared paths enter sim.render from rawVLMimage and camera observables during physics substeps; get_observations at the end mostly reads cache. IndependentB1 inference itself took1.222s, total116.849s with loading; it does not resolve transition/rendering cause.

Production create_env passes default render_gpu_device_id=-1, while installed custom EGL context prioritizes numeric MUJOCO_EGL_DEVICE_ID over CUDA masks. Existing C0 command expectedEGL5/CUDA6; no GPU0-misbinding evidence exists. Actual production context identity was not recorded, so remainsUnknown. Synthetic nativeMuJoCo probe is a separate context proof.

Root reviewed unapplied main/shared-render instrumentation patch SHA2567d62df655c630a318c28f28ea7a99765ab1482880a179e3a63fcd7207ae927da:18CPU tests pass, apply-check passes, original-operation Main AST preserved. Instance wrappers retain calls/arguments/results/exceptions; files append without per-record fsync and report measured observer overhead. Nested times are inclusive and must not be summed. Patch remains outside frozen source while native GPU7 queue is live; no new simulator/GPU execution. Production identity query proposal remains separately under review.

## 2026-09-22T07:50:03.582779+00:00 — unapplied production-context observer reviewed

Final artifact patch SHA256ccfe8ede68fe20e9c190078e1864f2fd17c9f3f575a3ff835f8808d134d51f33 passed17CPU mocks/callbacktests and apply-check. It reuses already-loaded raw EGL/GL DLL entrypoints without lazy loading or error-checking wrappers, and gates device attributes on known extension support. Missing exports/display-only versus client extension evidence remainUnknown. It observes once after an existing successful render/read_pixels; no context creation, make_current, render or simulation step is added. Expected values remain separate; physical index/UUID are not fabricated. Python failure isolation is tested; native driver faults/side effects remain a disclosed limit. This is a separately reviewed proposal, not applied orGPU-tested.

## 2026-09-22T08:17:43.179597+00:00 — reuse identical completed B1 evidence and focus GPU7 on pipeline diagnosis

Root compared completed resource ...b689d3b01c36 to the current frozen native plan: identical diagnostic scope, seed/task, policy configuration, native script hash, model/input inventory and all common source fingerprints; evidence hash verifies, output finite[1,64,128],5B1modelcalls, no simulator/Stage/actions. Reuse it only as bare-B1 implementation evidence, not transition/rendering or GPU7 execution evidence. Repeating the same synthetic probe is unnecessary. Owned CPU queue4193300 was terminated whilewaiting, before any resource dispatch, and its evidence archived. No GPUworker/external process was interrupted. Next bounded diagnostic will recover the already infrastructure-aborted C0 identity once onGPU7 with reviewed observational instrumentation; no failed Q0 or cohort reset.

## GPU3 continuation authorization 2026-09-22T08:25:04.726856+00:00

User explicitly moved subsequent execution to physical GPU3 only. Previous GPU7 CPU queue is already stopped before any GPU dispatch; all historical device labels and costs are preserved. Timing-only instrumentation applied after 18 CPU tests and unchanged-original-operation AST review. One exact-identity C0 infrastructure recovery is being prepared; invalid N1 Q0 is not retried.

## Concurrent C0 recovery consumed and failed on GPU5

Other worktree dispatched gpu6_native_c0_t00_r1__03c5d2b4a1df from source79cdce092b4e9c32b42634262cc9d1f7e14bec4b on physicalGPU5. Matched graphics Xid31 stopped it after132.6506171328947seconds. Both queue107052 and worker115030 exited without this continuation terminating them. Migration-scope question no longer needed. Preserve its journal terminal infrastructure classification and conservative cost, but causal diagnosis remains Unknown. Revised prospective GPU3 diagnostic r2 links this immediate parent; no duplicate retry of originalparent.

## GPU3 render diagnostic result — native graphics fault retained

Attempt gpu3_native_c0_t00_r2__79342697c4d2 (source e131ff6, plan6b434d45) consumed179.21637980407104 GPU seconds and one attempt. Root interrupted only owned queue134110 after exact admitted GPU3/worker142266 graphics Xid31; subsequent Xid109 confirmed context-switch timeout. Queue and worker exited. Ledger terminal aborted/KeyboardInterrupt is nonretryable; preserve it unchanged. One action completed before cleanup; one fresh policy call3.91354seconds; no Stage call. No scientific outcome is valid.

Across28 completed renders, read_pixels summed23.01167seconds (maximum21.29537) while29 host offscreen_render calls summed0.018719seconds;25 physics steps summed0.004087seconds. Inclusive parent/child intervals must not be summed. Several readbacks returned after the graphics fault, so return alone is not evidence of valid images. Diagnostic-artifact phase20.5326seconds contains rendering and CPU visualization; do not attribute it all to the renderer. Physics/controller computation is not the observed21-second step bottleneck.

Static review found robosuite render assumes its constructor/current context remains bound: per-render code does not call make_current. Firstartifact reads image before2Dkeypoint drawing, with no geometry mutation. No explicit EGL/context operation was found in RDT code; actualcurrent context remains Unknown. Next bounded diagnostic tests that concrete hidden precondition; no force-rebind fix, driver change or scientific cohort reset is yet supported.

## Context hypothesis evidence and observer lifecycle repair

Own GPU3 context queue164924 exited before dispatch because another worktree started GPU5_EGL_SERIAL_C0. It added no episode or GPU cost. That separately recorded attempt00baf2a27328 aborted after87.51905658841133seconds with exact-worker Xid31. Its first render already had current_context_matches=true; explicit CUDA synchronization and make_current completed before the fault. Five observed render entries matched. Thus simple persistent wrong-current-context/CUDA-outstanding-work explanation is not supported, and own three-boundary plan is retired unexecuted rather than duplicated.

The owned observer held old renderer bound methods until after the next adapter.reset. Pure CPU lifecycle audit proved wrong-context release possible on later episodes, while ordinary single-environment hard reset was correctly ordered. Close before reset and in episode finally is now implemented; native context getter integration is removed from default timing path, helper remains dormant.30 CPU tests and existing run-seed regression pass. First episode had no previous observer, so this repair does not establish the cause or fix of current Xid31. Next bounded question is whether the real frozen scene reproduces graphics failure without any neural model or task action.

## GPU3 static real-scene result and next isolation

Resource rdt-qd-ed-final-20260921T093925Z__gpu3_static_scene__b8f0b3b6214f completed:12 finite nonuniform camera frames,zero actions/Stage/integration calls,1 mj_step1 and5 mj_forward calls; accounted lifetime10.327968017198145seconds,no owned Xid. Simulation time stayed unchanged. Script237f1c4125488379f2230c3cd854808c3bc330979d09c120ad10dfb7497fd115,contract a080ed9625989cef5b0de19321fc367e14bfbaf0ed934ffb0a62b6b84ff98695. No scientific outcome. Static initialization lacks adapter.reset/five settling transitions and neural components,so pass does not establish full pipeline health. Next separately preregistered zero-integration healthcheck observes the same scene before/after frozen model load and after one synthetic B1 prediction. Source and all new artifacts will be frozen before admission.

## GPU3 scene plus model result — failure localized before prediction

Resource rdt-qd-ed-final-20260921T093925Z__gpu3_scene_model__c83cfb349cba from source9b1b472 and contract30b237ff4171bf0e49fd0f80e5234868ee73f62dc414e9507386dc34563f11bb aborted after73.72699015820399seconds on ownedPID249138 graphicsXid31. Child exited and onlyownedworker cleaned up.7preloadrenders passed; production import/CUDA identity+seed/load/to/eval/post_init/reset phase67.65424seconds completed with allcompute counters0. Firstpostload128depth frame hadnonfinite depth andchangedRGBhash; guardrefused continuation. NoB1prediction,DINO,Stage,reset,actions orintegration occurred. Thus these are notnecessary to reproduce thisfault; exactsuboperation ofloading remainsUnknown. Allcosts retained inhealthledger,scientificattemptcountunchanged. Next boundedquestion subdivides theloadingphase,not a repeatofinvalidscience.

## 2026-09-22T09:53:10.943336+00:00 — GPU3 restriction reconfirmed

User explicitly requires all subsequent execution of this task on physical GPU3. Persist candidate pool[3],oneexclusiveworker,noautomaticfallback,andwaitifGPU3unavailable. Newhealthcheckchild independently checks CUDA mask3,logicalCUDA0 UUID andEGL0 binding. NoGPUworker is currently dispatched. Loadingprotocol corrected beforedispatch to match actual82981d priorcode: no extra observation-processor import or phase-wrapper installation occurred initsloadingphase; nextprobe doesnotadd eitheroperation.

## GPU3 phase diagnostic — failure before model loading

Resource rdt-qd-ed-final-20260921T093925Z__gpu3_model_load_phases__52ec6c4eb068 (source d9416fb,script741c087a,contractf8713967) aborted after42.836270067840815seconds. Baseline and after-production-import images matched earlier static success. CUDA identity/seeding took10.402814seconds; next128depth readback21.732028seconds returnednonfinite depth andchangedRGBhash. Guard stopped beforefrom_pretrained/T5/checkpoint loading. No model forward,actions or integration occurred. Live and postrun GPU3 kernel checks recorded noXid for this resource. Retain childexit1/imagecontractfailure andcost,not an inventedkernelclassification. Nextprospectiveintervention initializesCUDA beforeanyexplicitapplication scene/context while retainingthenineoriginal loaderboundaries. No algorithm score/promotion.

## 2026-09-22T10:31:01.328229+00:00 — CUDA-first isolation negative, GPU3-only continued

Resource rdt-qd-ed-final-20260921T093925Z__gpu3_cuda_first__c40589cf6c65 (source be658cd, script b0c4dd04, contract 5dc28f10b3bc99a12e9d917c0efcfb12f550d953ccd206a342e31681b8d4c502) aborted after 82.97216953756288 seconds. CUDA was initialized before context construction. Baseline, production-import and CUDA identity/seed boundaries passed; after get_text_encoder returned, the next128depth frame had nonfinite depth and corrupt RGB. No model forward, action or integration occurred. Both live monitor and postrun GPU3 kernel checks found no Xid. Child exited1 under image guard. Early-CUDA production patch is not applied because this intervention was insufficient. Preserve all costs; no scientific score. Next bounded hypothesis isolates scene/context work from model loading/inference on separate host threads, synchronously, with the original scene/model/B1 sequence. This task remains restricted to physical GPU3 with no fallback; current owned workers none.

## 2026-09-22T10:37:22.170217+00:00 — dedicated render-thread probe CPU-ready

Executor artifact ce9457f5e184e6cad285a1444f97fefbaa1b8c353346e310b7c738cf76855ed0 passed4 CPU tests for ordered calls, scene/context cycles released on one render worker, failure cleanup, render/integration guards, library-map filtering, and unchanged factory/load/predict/compute-validation AST. Root reviewed source, protocol and supervisor 51e604cecf10f8eca134ba4edc6eba5354453ac94149892667fb680cd528792f. Supervisor separately checks actual Python/native thread identity at phase/render/release boundaries, successful weak-reference release/join/GC restoration, original B1 compute and camera hashes. No benchmark production patch, GPU resource or episode has yet been launched. Physical GPU3 only.

## 2026-09-22T10:45:05.150545+00:00 — render-thread isolation negative

Resource rdt-qd-ed-final-20260921T093925Z__gpu3_render_thread__be460ba14398 (source5192e5d, scriptce9457f5, contract1eba79779c181c19774ddab2980cc5e0b2518ab651c6b014b6b7c7fc06343a83) aborted after72.35227173706517seconds on exact GPU3/PID360797 graphicsXid31.7 preload frames passed; full model loading63.52414347510785seconds completed with zero forward calls. First post-load frame8 had nonfinite depth and changed RGB; readback0.233943s. No prediction/action/integration. Managed environment,sim,context references were released on render thread360879 and join/GC restoration succeeded. Thus a persistent separate rendering thread is insufficient; no production thread patch applied. Loaded library maps show system580.65.06 driver and two CUDA12 runtime library paths afterload; no causal conclusion from this observation. Next distinct process-isolation healthcheck retains physicalGPU3 for both owned processes, original frozen scene/model/B1 and budgets.

## 2026-09-22T10:57:06.659212+00:00 — process isolation CPU-ready

Child9eff1e42185316c5070b1d581e6238169657d1bdff9f4e20ebb76ac583e1a390 passed6 CPU spawn/IPC/ordering/error/guard tests with original model/factory operation AST preserved. Supervisor588e568057e54006a5b8e4b1b7002328647129c6006dacc29ad2509c6c05fc24 passed9 CPU ownership/cleanup/Xid/XML race tests; root reviewed helpers, execution/finalization and child workflow. It covers model parent plus renderer identities, numeric PID/birth/boot/group checks, graphics as well as compute processes, metadata appearing during query, renderer exiting during query, and leader-exit/orphan cleanup without signalling unknown/reused identities. Root read-only XML check confirmed one GPU3 UUID and empty graphics/compute list. CPU validation does not establish native health. No GPU resource dispatched yet; source/protocol will be frozen before one GPU3-only run.

## 2026-09-22T11:05:46.678717+00:00 — process isolation also insufficient

Resourcerdt-qd-ed-final-20260921T093925Z__gpu3_render_process__7a179aced1de (sourcec1da591,script9eff1e42,contractf7bbb68c2515413a89ce7869dd06a698c1d9224e247a36fb5ebfba9f9dfd5d6c) aborted on rendererPID381438 graphicsXid31 after72.52888720668852charged seconds. Modelparent381365 loaded models in60.58352625602856seconds with zero forward calls.7preload frames completed; first postload render entered but did not produce render_exit before supervisor cleanup. No B1/action/integration. Supervisor identified bothprocesses on GPU3,terminated only verifiedgroup381365 includingCPUtracker,andconfirmed no ownedGPUprocess remains; no finalmonitor errors. Thus process separation on thisGPU is insufficient; no production proxy implemented. A75-second no-model idle control is the next prospectively fixed temporal test. It addresses an untested confound of all postload observations without asserting model-loading causality.

## 2026-09-22T11:08:32.603979+00:00 — no-model idle control CPU-ready

Artifactec415acee0e57f29603bdf7dc6771ca6d55bdad31e22c28e9ab1463a6767ad05 passed5 CPU tests with injected wait/clock: exact six explicit cameras around75s, original factory AST, scope/finite-frame/CUDA-not-initialized/integration/render-cap guards. Root reviewed workflow and cloned single-process supervisorbde008e92f2bbb96ef1cac1d7887d58a2fd3fd95b8ee2b9813c0da47106a6ae1; it requires total10 frames, zero model/prediction/action/Stage/integration, all four CUDA initialization observations false, and both camera boundaries matching static references. Hardware monitoring includes graphics+compute XML entries onGPU3. Parent model-inventory byte verification is CPU-only and loads no model in the diagnostic. No GPU dispatch yet.

## 2026-09-22T11:16:46.121044+00:00 — idle temporal control passes

Resourcerdt-qd-ed-final-20260921T093925Z__gpu3_render_idle__8d9503386162 (sourcea850f97,script ec415ace,contracta0688ad3ebc0d732606b546614d052ca685f438fcd82d627113548cffdcc460b) completed in82.93174356641248charged seconds. Fixed idle75.0000788778998seconds; all10frames valid, both3-camera boundaries bit-identical to earlier static reference. TorchCUDA remaineduninitialized atallfour checks; no model/forward/Stage/action/integration;1mj_step1/5mj_forward;simulation time0 unchanged. No ownedXid.75seconds idle alone is insufficient to reproduce failure inthiscondition; do not claim alltime/power effects excluded. Nextprospective ordering test loads thecomplete originalmodels beforethe first applicationEGLcontext (earlier CUDA-first loadedT5 afterEGL). PolicyCPU RNG willbe preserved acrosssceneconstruction; noextraCUDA RNGoperations. No productionrepair orscientificpromotion yet.

## 2026-09-22T11:24:25.106698+00:00 — model-first diagnostic frozen for GPU3

Child 63d0acaed3b5c1a3088dab79f49c2f224374406a0d9078c4c3aeeb2364eb2519 passed3 CPU tests; original loader/predict/factory/compute AST preserved. All new RNG operations are CPU-only within scene scope; transparent context observer requires complete model load before graphics. Supervisor e834d28838e0e9c324af42b7fcb8aa67f789f61963e36952b0cc41f5816edfde enforces GPU3-only graphics+compute exclusivity, frozen bytes, one finite B1/five model calls and rows, ten valid frames and six exact static hashes, zero integration/actions/DINO/Stage. Prospective protocol added; production code unchanged.

## 2026-09-22T11:32:31.051354+00:00 — model-first separates loading from inference failure

Resource rdt-qd-ed-final-20260921T093925Z__gpu3_model_first__256bd92ec777 (source c97b1395f14c9d027ed2e88180b0820b7b888e24, contract cf240423e1bc27969425d963cb9c208bf0a02011fc02abd2591ee66de0e0e1e1) charged 73.69034509593621 seconds. Model load 64.78850958216935s completed before observed context creation.7 pre-B1 frames passed; all3 explicit camera hashes exactly match static control. Original B1 yielded finite[1,64,128],SHAe47036194c7e9007cf4d17b3fbc18ac7b2afb4227551624e14eb5f8ebd90f7ca,5modelcalls/rows,1vision/1text/1denoise. First post-B1 render8 produced nonfinite depth and ownedPID414431 Xid31;0actions/integration;1mj_step1/5mj_forward. Worker cleaned and GPU3empty. Model-first alone is insufficient; no production patch. Next context-lifetime intervention retires graphics before B1 and recreates matching context afterward. This is a new falsifiable scope, not a retry of invalid scientific episodes.

## 2026-09-22T11:41:04.402172+00:00 — context lifetime CPU-ready

Child 76c600819d57cc7179b3ba75c3f88ba5901053e68f38523ebbbe021c9785784f passed6 CPU lifecycle/scope tests. Supervisor 995dcaae05ada01d445aadbee8ed9eae16b30f2216fd71e88a79dd63e78e6e69 verifies successful original EGL destruction, no unraisable exceptions, same constructor/settings/qpos-qvel-act-ctrl-time hashes,2 contexts,6mj_forward/1mj_step1/0integration,original B1 and static camera hashes. Read-only production audit notes full-context rebuild adds forward; only DINO/policy boundaries miss CUDA action operations. Retaining CPU rendering objects while recreating con/gl_ctx per full render/readback may avoid extra forward, but native/destructor cleanup,segmentation/depth fidelity and asynchronous kernel scheduling still require separate validation. Existing B1 explicitly synchronizes; production overlay may precede action.cpu synchronization. No production change now.
