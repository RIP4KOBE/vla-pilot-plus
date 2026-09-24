# N4 CPU runner preparation

This implements a separate, closed N4 Dev entry. It does not launch an episode,
change the ledger/state, read protected-phase outcomes, or authorize validation
or formal evaluation. Integrate the separately reviewed core and native auditor,
the root-owned resource amendment, and these explicit files into W before
preparing the real plan. The isolated source intentionally cannot dispatch.

The exact scientific protocol, Q0 prerequisite protocol, resource amendment,
completed prerequisite certificate and shared resource contract are SHA-bound.
The 12 originals are tasks 0,3,6,9, each C0/Q0/N4 in order. C0 plus Q0 tasks0,3
charge baseline; Q0 tasks6,9 plus N4 charge development. All candidate changes
except `qd_final_selection_mode=terminal_population_v1` are rejected. The
independent common observed manifest fixes the controls to the original
`archive_global_best` consumer. Original profiles and N3 tools remain unchanged.

The builder is CPU-only and writes a new **unfrozen** plan. It uses the existing
frozen Dev seed/init table and GPU3 runtime, verifies declared source bytes
against the supplied current commit, and requires the new terminal-population
helper and deployed native action decoder in the source inventory. It reuses
explicit same-boot engineering proofs and records their prior cost without
recharging it; no automatic GPU probe or hardware revision is provided.

After final source integration/commit, the root can run from W:

```bash
CUDA_VISIBLE_DEVICES='' python scripts/qd_ed_n4_plan.py \
  --base-plan BASE_FROZEN_N3_PLAN.json \
  --runtime-manifest EXISTING_GPU3_RUNTIME.json \
  --source-head FULL_FINAL_SOURCE_COMMIT \
  --prerequisite-review /mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/continuation_20260923/n4-q0-transfer-check-analysis/root-complete-review-v1.json \
  --shared-resource-contract /mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/continuation_20260923/n4-resource-resumption-v1/shared-resource-contract-v1.json \
  --output NEW_ARTIFACT_DIRECTORY/plan.unfrozen.json
```

Use the existing CPU Hydra preview and runner validation/freeze workflow; do
not skip model/input/source/managed-provider verification at real admission.
The new plan is not launch authorization. `data/qd-ed-shared-resource-active.json`
and its immutable contract deliberately retain their own `online_dispatch_authorized=false`
semantics. A separate root-issued release is required **after** exact plan freeze.

The release schema is `qd-ed-n4-execution-release-v1`, status `authorized`, with:
`cohort_id`, exact `plan:{path,sha256}`, `source_commit`, `source_files_sha256`,
`frozen_identity=qd_ed_n4_plan.binding(plan,runtime)`, `candidate_profiles`,
`shared_resource_contract`, exact `limits`, `budget_allocation`, Dev-only
`phase_authorization`, physical_gpu3/max_owned_GPU_workers1, full `gpu_mapping`,
ordered `episode_keys`, and `stage=first3` or `remaining9`. The first stage has
`checkpoint_release:null`. The later stage binds the same non-null checkpoint
reference in the derived plan. No release hash is embedded back into the plan.
Explicit same-cell recovery rows use a new plan/release with the original
frozen identity and an exact eligible predecessor; the runner creates none.

The checkpoint schema is `qd-ed-n4-checkpoint-v1`: source/protocol/file identity,
nonempty SHA-bound evidence, exact first-three accepted attempt IDs, and all
keys in `qd_ed_n4_plan.CHECKS` true. It is a correctness checkpoint. Three valid
task failures and zero selected/reference action differences do not prevent
release when those correctness checks pass. At least one actual guided native
consumer/archive-parent execution is needed to establish correctness.

A concrete first-three command, once the root has frozen and released it, is:

```bash
python scripts/qd_ed_n4_supervise.py --plan EXACT_FROZEN_PLAN.json \
  --execution-release FIRST3_RELEASE.json --execution-release-sha256 EXACT_RELEASE_SHA256 \
  --episode-key n4_dev_t00_c0_20260924 \
  --episode-key n4_dev_t00_q0_20260924 \
  --episode-key n4_dev_t00_n4_20260924 \
  --status-path NEW_ARTIFACT_DIRECTORY/first3-status.json
```

The supervisor holds the original real shared flock across the selected rows,
uses the existing 120-second continuous-idle check, frozen GPU3/boot/UUID/native
proof, owned-process Xid monitor, original child/finally accounting and CPU
audit after every terminal. Direct runner/generic queue dispatch cannot create
a reservation or touch the GPU without this verified scope and exact release.
It checks remaining originals/recovery slots against the unchanged source/state
caps, all costs, protected100 originals/24h, local16 dispatches/8.5h and full
1800+40 seconds. Unknown Xid/algorithm errors, ordinary timeout, valid failure,
audit failure and identity drift cannot obtain an infrastructure retry.

Every N4 guided metric must have the new mode and its full native audit. The
wrapper matches steps,11/176/10 counts, actual prefix lengths, and metrics'
selected/reference identities/scalars/ties/source occurrence/cost dtype/vector
to the independently audited native summary. Missing new events cannot fall
back to generic acceptance. Actual-prefix difference counts are distinct from
first8 differences and are not a first-three effect gate. No native bundle is
reopened by the stdlib report.

`qd_ed_n4_report.py` consumes an explicit root-authorized report manifest:
`schema=qd-ed-n4-report-input-v1`, script/protocol SHA, authorization reference,
base plan and all plan revisions, exact full N4 journal excerpt, every terminal
reference, separate accepted audit/compute/metrics references for valid rows,
and every declared health reference. Its authorization schema is
`qd-ed-n4-report-authorization-v1`, binding script/protocol/base-plan/journal
excerpt SHA. The excerpt schema is `qd-ed-n4-journal-excerpt-v1` with
`extraction=all_events_all_n4_attempts_through_snapshot`, immutable source journal
SHA, all events and exact terminal/inflight ID inventories. Invalid and
predispatch records are retained; inflight costs remain incomplete.

Run only on a newly authorized, named snapshot with empty CUDA:

```bash
CUDA_VISIBLE_DEVICES='' python scripts/qd_ed_n4_report.py \
  --manifest REVIEWED_REPORT_MANIFEST.json --execute-reviewed \
  --output NEW_SEPARATE_ARTIFACT_REPORT.json
```

All 12 accepted cells are required for the numeric criterion N4>=2/4 and>=both
controls; an independent aggregate gate requires at least one actual-prefix
difference from the stored archive reference. Neither a partial matrix nor
this report authorizes promotion or protected evaluation. Selection differences
never imply counterfactual success. The archive distance diagnostic stays
separate from the unmeasured selected distance (`None`, not zero).


## Concrete review-time JSON construction

These snippets are recipes for the root, not executed by this CPU preparation.
Use the final integrated W Python interpreter with `CUDA_VISIBLE_DEVICES=''`.
`r.validate_plan(path, root=W, require_frozen=False)` is the existing public
validation API. Compose all 12 commands with `r.build_command` and the existing
CPU Hydra preview before making a distinct frozen copy (`frozen=true`, fresh
`frozen_at`). Validate that copy with `require_frozen=True`. There is no new
freeze command and no implicit execution release in this builder.

For a frozen plan `P`, runtime `M`, its resolved `plan_path`, and imported
`qd_ed_final_runner as r`, `qd_ed_n4_plan as n`, create the first release from
exact values (write a **new** JSON path under the artifact root):

```python
keys = [row['episode_key'] for row in P['episodes'][:3]]
release = {
    'schema': 'qd-ed-n4-execution-release-v1', 'status': 'authorized',
    'cohort_id': n.COHORT,
    'plan': {'path': str(plan_path.resolve()), 'sha256': r.digest(plan_path)},
    'source_commit': P['source_commit'],
    'source_files_sha256': n.source_identity(P),
    'frozen_identity': n.binding(P, M),
    'candidate_profiles': P['candidate_profiles'],
    'shared_resource_contract': P['n4_cohort']['shared_resource_contract'],
    'limits': n.LIMITS, 'budget_allocation': n.BUDGET_ALLOCATION,
    'phase_authorization': {'dev': True, 'validation': False, 'formal': False},
    'physical_gpu': 3, 'max_owned_GPU_workers': 1,
    'gpu_mapping': M['gpu_mapping'], 'episode_keys': keys,
    'stage': 'first3', 'checkpoint_release': None,
}
```

`health_resources` copies exactly the runtime CUDA/EGL proof ID and the freshboot
model-first health-result ID as `scope=reused_prior`; duplicate IDs are removed.
The five inherited `runtime_prerequisites.references` are `health_result`,
`health_contract`, `common_result`, `common_process`, and `common_kernel`. They
bind same boot/GPU/driver/native dependencies, frozen model inventory and seed,
and the previous valid full C0's process/kernel attribution. Their evidence is
engineering reuse only: the old algorithm/source is not represented as N4
validation. Report `health_resources` adds the exact SHA-bound health terminal
reference for each ID, in declaration order. Their original wall seconds appear
in `reused_prior_health_seconds_not_recharged`; N4 new health remains separately
charged and must be prospectively declared. There is no automatic probe.

After all first-three accepted audits are reviewed, checkpoint JSON has:

```python
checkpoint = {
    'schema': 'qd-ed-n4-checkpoint-v1', 'cohort_id': n.COHORT,
    'source_commit': P['source_commit'],
    'source_files_sha256': n.source_identity(P),
    'protocol_sha256': P['n4_cohort']['protocol']['sha256'],
    'attempt_ids': accepted_first_three_ids_in_task_major_order,
    'checks': dict.fromkeys(n.CHECKS, True),
    'evidence': reviewed_nonempty_path_sha256_references,
}
```

Only the root can attest those checks from actual accepted evidence. A new
plan copy adds the checkpoint reference; its other source/scientific/runtime
fields stay exact. A separate `remaining9` release then binds that new plan SHA,
keys 3..11, and the same checkpoint reference. Do not set booleans to true merely
to construct a runnable file; these are evidence-backed root attestations.

A report manifest uses this concrete shape (each reference is `{path,sha256}`):

```json
{
  "schema": "qd-ed-n4-report-input-v1",
  "script_sha256": "SHA of frozen qd_ed_n4_report.py",
  "protocol_sha256": "b8562e3f9fffc77efc803c6b056441f7b426333a97eb176b52fdb0fe42088db2",
  "authorization": {"path": "NEW_REPORT_AUTH", "sha256": "SHA"},
  "base_plan": {"path": "FIRST_FROZEN_PLAN", "sha256": "SHA"},
  "plan_revisions": [],
  "journal_excerpt": {"path": "FROZEN_N4_ONLY_EXCERPT", "sha256": "SHA"},
  "attempts": [],
  "health_resources": [],
  "input_scope_complete": false
}
```

For each valid accepted terminal, `attempts[]` supplies `terminal`, `audit`,
`compute`, `metrics` references; for invalid/predispatch records only `terminal`;
for an unaudited valid row only `terminal`, or `terminal`+rejected `audit`. Exact
standard filenames and compute/Stage/cost identity are checked. Supply all and
only completed N4 terminals in the immutable excerpt, including failed
reservations/recoveries; its explicit inflight inventory remains distinct.
Report authorization binds `schema=qd-ed-n4-report-authorization-v1`,
`status=authorized`, exact `script:{path,sha256}`, `protocol_sha256`,
`base_plan_sha256`, and `journal_excerpt_sha256`. No report gate creates an
execution release, checkpoint or protected-phase authorization.
