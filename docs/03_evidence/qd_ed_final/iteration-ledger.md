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
