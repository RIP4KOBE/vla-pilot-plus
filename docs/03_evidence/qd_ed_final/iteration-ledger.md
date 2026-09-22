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
