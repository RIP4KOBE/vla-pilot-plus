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
