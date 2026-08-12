# Protocol v4 — outer-loop cycle-3 conclusion and v2 evidence freeze

Status: `LOCKED AFTER RUN023 RESULT COMMIT AND BEFORE CYCLE DECISION MANIFEST OR FINAL REPORT`

This protocol authorizes no algorithm/config change, threshold adjustment, new candidate, API/model call, GPU admission, LIBERO episode, attempt reservation, Dev-A/B, validation reuse, or formal evaluation.

## Trigger

Run023 immutable audit `7f123ecdf3ffb7fbbb881ffebe197ddb2ae8e4b1237233dd2316f6f67e832c54` is a valid online mechanism FAIL. The candidate produced zero fallback chunks and 74 active-QD chunks, scored 0/3, and lost the contemporaneous control success on task 9. The result commit is `00964434d2a5e245758c26f25dbc77e17c182dce` and analysis SHA-256 is `19061e925bbfe1f97772ae8ee526ce4a06c8b8328bcca36bedc05f7e4e390806`.

The v2 design permits one H2 candidate only. A promotion failure stops subsequent splits and forbids adjacent threshold tuning. Therefore Dev-A/B, validation, and formal are unavailable in this cycle.

## Read-only evidence packet

- Run020 retrospective calibration: 473 exact-zero historical chunks across all ten tasks.
- Run021/022 implementation and integrated offline identity evidence.
- Run023 manifests v1/v2/v3, ledger, admission, raw metrics, task outputs, audit, and analysis.
- Prior cycle H1 mechanism/Dev/validation evidence and immutable decision manifest.
- Historical search-budget and stage/guidance reports already checksum-bound in the ledger.
- Canonical append-only state, log, findings, trajectory, and iteration ledger.

All external workspace/worktree/shared2 history remains read-only. The protected untracked Stage-transition design remains unread, unmodified, unstaged, and uncommitted.

## Deterministic synthesis and decision

1. Preserve H1's partition-resolution mechanism evidence but reject it as insufficient after validation 1/10.
2. Preserve H2 offline exact-equality identity evidence but reject `reward_degenerate_control_fallback_v1`: its predicate did not occur prospectively and active QD lost control task 9.
3. Do not reinterpret positive reward/distance/overflow proxies as task progress. On task 9 the candidate had competitive proxy values but failed while control succeeded, strengthening the reward-to-completion misalignment diagnosis.
4. Do not relax exact equality, sweep tolerances, reuse Run023 seeds, or promote to Dev-A.
5. Conclude the v2 cycle with no adoption. Historical formal best remains 2/10; formal remains unrun.
6. Further execution requires a versioned redesign, new leakage-safe holdout seeds, explicit budget, and explicit user approval.

The frozen outer-loop decision label is `CONCLUDE_NO_ADOPTION_WITHIN_V2_CYCLE_REQUEST_VERSIONED_REDESIGN`.

The sole evidence-supported future proposal is still inside EDS+QD and QD-first: replace task-agnostic reward/fingerprint quality and final selection with a preregistered, observation-derived stage-progress quality signal or guarded retention rule that directly addresses the repeated loss of control-success tasks. This is a redesign request, not an authorized candidate. It must not change the Stage recognizer, prompt, checkpoint, perception, environment, executor, or evaluator.

## Required outputs

- immutable owned `run_023.../manifests/cycle_decision_manifest.json`, mode `0444`;
- v2 cycle final report in `docs/03_evidence/eds_qd_autoresearch/`;
- updated human current status and a new progress page;
- append-only state/log/findings/trajectory/ledger reflection;
- strict credential scan and Git/write-boundary verification;
- one result/reflection commit.

The decision manifest must bind v2 design/protocol/result commits, manifests/audit/analysis hashes, algorithm fingerprints, task-level outcomes, reservation/GPU accounting, zero formal use, protected-file exclusion, and the redesign boundary. It must contain no credential value or reversible fingerprint.
