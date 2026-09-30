# N22 conditional protected validation runtime contract

This is CPU preparation of the frozen conditional validation protocol, not execution authorization. Scientific base: `60425750c41c8a46e1102e02e2e4e4d2f97fb242`; Dev plan SHA: `30846268778c46f2d9ad25a92abe7869395d3ead218da1a97dbf24fae4d07218`. Protocol SHA: `b2e94ebd3a79495a6a12db052ddd8ca6db764f65b2632fa092c31d593cd7c51b`.

## Scope and immutable science

Only `scripts/qd_ed_final_runner.py` may differ from the Dev source among existing files. The seven additions are the validation contract/prepare/supervise/report scripts, `tests/test_qd_ed_n22_validation.py`, the exact validation protocol copy, and this document. `source_record` requires committed HEAD bytes, the sorted complete parent manifest plus these additions, and no tracked commit delta outside this allowlist. Main/core/policy/native auditor/provider, external Stage templates, all profiles and runtime inputs stay exact. The expanded active arms are C0, Q0, N22; no N21/N7 route is reused. N22 Dev routing remains unchanged.

The inherited runtime uses current Codex CLI ChatGPT login, unchanged frozen model/transport/E2 semantics, no alternate provider fallback, GPU7 UUID `GPU-48473162-9548-1a19-04aa-ea86c5349187`, EGL4, and existing CUDA/EGL proof `rdt-qd-ed-final-20260921T093925Z__gpu7_cuda_egl__4fafff3673e5`. No Poe request is authorized; existing credentials are preserved. Validation uses the existing independent CPU native auditor after each metered model worker; N23 arithmetic/CUDA auditing is not involved.

## External review and authorization schemas

All `{path, sha256}` references use absolute paths and current byte SHA256. No review or later release digest is compiled into source. JSON below describes exact field sets; values in angle brackets are placeholders, not executable drafts.

`validation-dev-promotion-review-v1.json` in this variant directory:

```json
{
  "schema": "n22-dev-promotion-review-v1",
  "disposition": "promoted",
  "dev_plan": {"path": "<variant>/plan.frozen.v1.gpu7.json", "sha256": "<fixed Dev plan SHA>"},
  "dev_status": {"path": "<variant>/execution/supervisor-status-gpu7-v1.json", "sha256": "<terminal status SHA>"},
  "dev_result": {"path": "<variant>/result-v1.json", "sha256": "<immutable result SHA>"},
  "cell_audits": [{"attempt_id": "<exact attempt>", "report": {"path": "<exact attempt output>/eds_eval/decision-evidence-audit.json", "sha256": "<audit SHA>"}}],
  "allow_validation": true
}
```

There must be exactly 40 cell references. The current Dev plan, status, append-only journal identities/terminals, accepted native audits and actual `n22-dev-cohort-result-v1` result must agree. The result must report `ELIGIBLE_FOR_SEPARATELY_FROZEN_VALIDATION`, full 40 dispatched/audited/planned cells, no missing costs, exact source/cohort/plan/status/ordered rows/counts and current terminal-reader SHA. Every guided N22 cell must independently bind its actual canonical candidate/score counts to `176*n`, `11*n`, and native QD parent rounds `10*n`; legal zero-guidance cells remain allowed. N22 must reach at least 5/10 and not trail any Dev comparator; aggregate QD/ED activity must be positive. Invalid, partial, futility, or merely manually labelled promotion does not admit validation.

`validation-source-review-v1.json`:

```json
{
  "schema": "n22-validation-source-review-v1",
  "disposition": "accepted",
  "dev_plan": {"path": "<Dev plan>", "sha256": "<SHA>"},
  "protocol": {"path": "<variant>/protocol-validation-conditional-v1.md", "sha256": "<fixed protocol SHA>"},
  "source": {"commit": "<integrated HEAD>", "files": [{"path": "<relative path>", "sha256": "<SHA>"}], "changed_paths": ["<sorted exact delta>"], "scientific_unchanged": true},
  "allowed_modified": ["scripts/qd_ed_final_runner.py"],
  "allowed_added": ["<sorted exact seven additions from contract.ADDITIONS>"],
  "runtime": {"path": "<original N22 Dev runtime>", "sha256": "<unchanged SHA>"},
  "no_execution_release": true
}
```

Private state requires a separate root-authored field. The existing N22 amendment, Dev binding, cumulative/bucket caps and reservations remain unchanged:

```json
{
  "n22_validation_authorization": {
    "schema": "n22-validation-authorization-v1",
    "cohort_id": "N22_VALIDATION_20260930",
    "seed_cohort": "<freshly selected c1..c4>",
    "protocol_sha256": "b2e94ebd3a79495a6a12db052ddd8ca6db764f65b2632fa092c31d593cd7c51b",
    "dev_review": {"path": "<root Dev promotion review>", "sha256": "<SHA>"},
    "source_review": {"path": "<root source review>", "sha256": "<SHA>"},
    "run_once": true,
    "physical_gpu": 7
  }
}
```

No script adopts this field, amends the budget, or reconciles historical exposures. The root owns those operations after terminal review.

## Cohort selection and capacity

Select the first wholly untouched cohort in frozen c1, c2, c3, c4 order using task/environment-seed pairs from frozen seeds, historical inventory, exposure registry and **every** reserved/dispatched journal identity, independent of arm, outcome, or budget bucket. Current c2 snapshots have no release authority. Prior validation dispatches missing from the exposure registry block release; root must review/apply its pending C1 metadata reconciliation separately. Only this exact current cohort's already journaled identities are ignored during ongoing per-cell validation. Any foreign overlap invalidates the selection; any prior N22 protected cohort prevents a second one.

Order is b1 then b2, task0 through9, C0/Q0/N22. All 60 rows use original frozen seed/init/file/BDDL bytes. No retry, replacement, early futility stop, or new-layout claim. Complete 60-cell capacity and the remaining full 32-hour local ceiling must fit current 438 attempts/100 GPU hours, validation bucket180, and remaining formal40-attempt/12-hour reserves; no reserve is silently reduced. Every charge, launch failure, timeout and interruption stays in the existing append-only ledger. A row already reserved cannot be reused. Existing runner ownership/exclusivity/timeout cleanup applies, with 1800 seconds plus 40 seconds cleanup per worker. Exposure metadata is appended after the durable dispatch journal; a crash leaves the journal as authoritative exposure evidence.

The sole frozen plan filename is `<variant>/validation-plan.frozen.v1.gpu7.json`. Every audit checkpoint is independently bound to its actual file SHA, terminal/source/profile/runtime/inventory fingerprints, complete frozen row, attempt ID and native audit SHA. A valid terminal without a matching native checkpoint cannot admit the next cell. The script refuses resume or a second cohort.

Root execution release exact fields:

```json
{
  "schema": "n22-validation-execution-release-v1",
  "plan": {"path": "<variant>/validation-plan.frozen.v1.gpu7.json", "sha256": "<frozen SHA>"},
  "source_commit": "<integrated HEAD>",
  "cohort_id": "N22_VALIDATION_20260930",
  "seed_cohort": "<selected cohort>",
  "episode_keys": ["<all 60 exact ordered keys>"],
  "dev_review": {"path": "<review>", "sha256": "<SHA>"},
  "source_review": {"path": "<review>", "sha256": "<SHA>"},
  "physical_gpu": 7,
  "uuid": "GPU-48473162-9548-1a19-04aa-ea86c5349187",
  "validation_authorized": true,
  "formal_authorized": false
}
```

Release rechecks metadata, capacity and separate authorization under existing private locks. Each actual cell rechecks GPU ownership/UUID/EGL/probe and normal frozen model/runtime/provider conditions. Missing/changed prerequisites stop before a new charge. Audit failure or interruption stops immediately and yields invalid aggregate disposition, never valid rejection.

## Protected evidence and aggregate reporting

Full `protected-detail.json` preserves all 60 planned cells, actual terminal/checkpoint records, denominators, paired gains/losses and cost summaries including canonical work, model/reward, Stage/provider attempts, tokens, failures and process wall time. Missing costs are explicit and invalidate complete adjudication; they are not treated as measured zero. Corrupt adjudication preserves raw protected rows/events separately in `protected-unadjudicated-evidence.json`. These are evaluator evidence and must not be used for tuning or exposed to the root iteration-selection channel.

`aggregate-progress.json` reports only phase, completed count, expected60 and final validity/gate. The independently saved root-facing disposition has exactly these fields:

```json
{"schema":"n22-validation-aggregate-disposition-v1","cohort_id":"N22_HOLD_LIFT_DEV_20260930","aggregate_only":true,"terminal":true,"gate_passed":false,"outcome_valid":false,"dev_promoted":true}
```

The Dev cohort ID intentionally matches the existing conditional successor gate. Valid complete rejection is terminal=true/outcome_valid=true/gate_passed=false. Invalid/interrupted is outcome_valid=false and cannot activate a successor. Promotion requires all60 accepted cells, N22>=10/20 and>=C0/Q0, substantive native QD/ED with fixed176/11. No per-task result, arm success count or paired outcome appears in the aggregate file or CLI stdout. Formal remains closed; there is no formal launcher.

## Prospective integration sequence (root only; not executed here)

1. Wait for terminal Dev and create the immutable actual Dev result with the existing reader. If Dev does not truly promote, do not activate this branch.
2. Integrate the evaluation-only commit into the owning study after Dev has stopped. Recompute `contract.source_record` against the frozen parent and review all byte differences; create the external Dev and source reviews.
3. Apply the separately reviewed C1 metadata reconciliation if still required. Recompute metadata-only first-unused choice under private lock. Verify full capacity and create the separate state authorization. This is not a budget amendment.
4. Run the prepare CLI from the integrated study with `--freeze --output <variant>/validation-plan.frozen.v1.gpu7.json`. It reselects fresh metadata and refuses snapshot overrides. A CPU-only `--preview-cohort c2 --output <new preview>` is illustrative, frozen=false, with absent reviews; it cannot dispatch.
5. Review the frozen plan and create the external exact execution release, then run `scripts/qd_ed_n22_validation_supervise.py --plan <frozen plan> --release <root release> --output-dir <owned new protected evaluation directory>`. Do not concurrently run N23 or another worker. No automatic retries/resume.
6. Supply only `aggregate-disposition.json` to the root algorithm-selection process. Preserve detailed protected artifacts for final reporting. Any invalidity requires explicit root review; no new cohort or successor is automatically authorized.
