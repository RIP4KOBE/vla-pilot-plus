# Q0 / C0 baseline restoration and source parity

Run: `rdt-qd-ed-final-20260921T093925Z`. Diagnostic node 3. CPU only; no model,
simulator, GPU evaluation or research-score measurement was performed.

## Outcome

The complete historical Q0 sparse and C0 P2 profiles are restored in
`configs/qd_ed_final/baseline_profiles.json`: 72 profile fields, all 68 EDS YAML
fields, and 135 explicit static Hydra overrides per profile. The manifest also
lists every runtime binding that must be frozen before a job is runnable.

The source comparison and CPU checks support retaining source commit
`744e08ba4398f2f8e34fb05619c829fc01397f69` with all four later mechanisms OFF.
They do **not** establish historical online performance equivalence. New Dev
baselines remain unmeasured. Historical Q0 is 2/10 (tasks 5, 8); same-round C0
is 3/10 (tasks 3, 8, 9), not the 4/10 from another recovery round.

| Setting | Q0 | C0 |
| --- | --- | --- |
| Historical label | `eds_quality_diversity_sparse_primary` | `p2_stage_on_abs_rbf_control` |
| QD archive | `grid_archive` | `none` |
| QD parent sampling | `sparse_priority` | `uniform_cells` (inactive) |
| Bounds policy | `fixed_initial` | `fixed_initial` |
| Global quality anchor | 0 | 0 |
| Protected secondary lane | `none` | `none` |
| Degenerate fallback | `none` | `none` |
| Shadow QD observer | true | true |

Both retain population 16, 10 iterations, non-CEM ED, temperature 0.1, renoise
3-to-1, absolute-EEF RBF initial sampling (scale 20, start 0.8), absolute-EEF
RBF rollouts (scale 20, start 0.6, all iterations), fresh chunk population,
legacy parent weighting/schedule, no carryover, no parent coverage/anchor,
fixed 8-action execution, Stage ON, grounding OFF, 720 steps, and normal reward.
QD uses 4 x 4 cells, capacity 1, quantiles [0.05, 0.95], expand fraction 0.10,
minimum span 0.08 m, clamped overflow, stable action-fingerprint ties.

## Provenance and source audit

The baseline snapshot is `5b0898e53d5b9e16200c17479a74746071215787`.
Its historical report separately identifies QD implementation commit
`53187e6ea8b69e9f830c10be0bc25757db5d2794` and P2 source
`b3db98cf4fd98a6479d92683e33ebe3d032f25d9`. The manifest derives the profiles
from the historical runner source, not from the latest candidate profile.
SHA-256 fingerprints for both revisions of all relevant sources are in the
manifest.

| Source | Difference and disabled-path assessment |
| --- | --- |
| `scripts/eds_quality_diversity_runner.py` | Byte-identical across the two snapshots. Historical common/profile construction is unchanged. Its execution machinery is unsuitable here: GPU5, external colocation allowed, old storage roots and inherited resume/accounting. Its `QD_CONFIG_FIELDS` omits the four later switches. |
| `scripts/rdt_eds_eval_runner.py` | Byte-identical. Main command construction and legacy ED settings are unchanged; using its unconfigured globals would inherit old roots/cache and GPU policy. |
| `configs/config.yaml` | Only four EDS defaults were added: fallback none, secondary none, global anchor zero, fixed-initial bounds. All historical EDS defaults match exactly. Explicit overrides now prevent future default drift. |
| `core/qd_ed.py` | Adds envelope/rebin, anchor allocation and protected secondary lane. With secondary none, update ordering, incumbent tie-break, cumulative visits and elite selection retain their historical code. Anchor zero preserves population, local generator seeding, permutation, largest-remainder counts, parent order and fingerprints. Differential CPU checks below verify old fields exactly. |
| `core/rdt_policy_steer.py` | New fallback branch requires `control_v1`; new envelope/rebin requires `causal_envelope_v1`; new lane/anchor logic is inert under the restored profile. However new diagnostic SSE/overflow/history calculations run even with fixed bounds, and search-accounting checks were added. The selected-action contract is supported by tests, but timing, serialization size and failure surface are not byte-identical to history. |
| `core/eds_eval_metrics.py` | Adds fields and counters, including full search candidate count, bounds histories, anchors/secondary/fallback. Output schema differs; historical metrics equality must compare shared semantic fields, not entire JSON bytes. |
| `configs/policy.yaml`, `configs/backend/libero.yaml`, `configs/perception.yaml`, `main.py` | Byte-identical across snapshots. Checkpoint remains RDT Object EMA, 20 Hz, 8 actions/chunk, observation/action semantics unchanged. Actual checkpoint/cache/provider/input identity still requires runtime fingerprints. |
| `.libero_config/config.yaml` | All absolute roots moved from the old P2 worktree to the old autoresearch worktree. A new Git worktree inherits these old absolute paths. Use an owned LIBERO_CONFIG_PATH with separately audited contents rather than treating a Git checkout as sufficient input isolation. |

No core repair is justified by the observed CPU results. Minimal engineering
work still required before dispatch: owned runner/output/ledger/cache paths,
explicit GPU7 admission and verified EGL mapping, complete profile override
serialization, input/config fingerprints, and strict task-seed-init identity.
The new runner must not call an inherited runner's run/resume/recovery entrypoint.

## CPU verification

Working directory was the NEW worktree. Python was
`/home/hynx/miniconda3/envs/vla-pilot/bin/python`, PyTorch `2.7.1+cu126`, with
`CUDA_VISIBLE_DEVICES=''`. No GPU allocations or episode attempts occurred.

```bash
CUDA_VISIBLE_DEVICES='' /home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest -q \
  tests/test_qd_ed_archive.py tests/test_rdt_steer.py \
  tests/test_eds_quality_diversity_runner.py tests/test_eds_eval_metrics.py \
  -k 'qd or quality_diversity or eds_config or parent_weight_legacy'
```

Result: **173 passed, 269 deselected, 11.04 s**. One existing invalid-escape
SyntaxWarning in `core/fkd_class.py`. Checks include default-off validation,
fixed bounds, full 176/11 QD budget, archive/global-best selection, disabled
fallback keeping the archive path, local RNG, passive C0 observer behavior,
and runner configuration serialization. Existing anchor-zero tests compare
current default and explicit-zero paths; they alone would not prove historical
parity, so a direct cross-revision comparison was also executed.

That differential harness loaded `core/qd_ed.py` directly from the two Git
objects in memory, using `git show <commit>:core/qd_ed.py`. Across CPU generator
seeds 0..23 and both sparse/uniform samplers it performed 11 updates and 10
allocations per scenario (48 scenarios; 528 updates; 8,448 candidate comparisons;
480 allocations). Inputs included narrow and widening Gaussian descriptors,
clamped overflow, tied quantized rewards and all-zero rewards. It compared
update dataclass fields, complete historical archive snapshots, cumulative
visits, all elite tensors, global-best fingerprint/cell, and every historical
parent-allocation field with exact equality, and checked allocation did not
advance global Torch CPU RNG. **All comparisons passed.** This was a synthetic
CPU differential check, not an online rollout or learned-model test.

## Full command overrides and binding rules

For either `profiles.Q0` or `profiles.C0`, `hydra_overrides` is the authoritative
ordered argv list of all 135 static overrides. `static_override_values` is its
typed equivalent. `historical_profile` preserves the original GPU5 provenance;
`restored_profile` changes render GPU to 7 and explicitly sets the four later
mechanisms OFF. Do not pass historical_profile wholesale to a historical runner.

Compose argv as an actual argument list, not a shell string:

```python
argv = ["/home/hynx/miniconda3/envs/vla-pilot/bin/python", "main.py"]
argv += manifest["profiles"][profile_id]["hydra_overrides"]
argv += frozen_attempt_runtime_overrides
```

Runtime overrides must bind task filter, episode seed schedule/count, cache,
unique output/metrics/mechanism directories, method label, attempt ID, and
report directory. Reject duplicate keys and any override that silently changes
a static contract field. Use one episode process per task; check task sorting
does not change the seed association. Init identity is an additional input
contract, not interchangeable with RNG seed. Provider credentials may be
inherited by the process environment but never serialized.

The coordinator subsequently froze a repaired-input baseline contract:
`Q0_input_repaired` / `C0_input_repaired`. Canonical reward guidance bytes are
unchanged, task-bound cache metadata is checked by
`+main.require_task_cache_identity=true`, and each one-task process explicitly
sets `seed=policy_seed` and `main.episode_seed_schedule=[env_seed]`. This differs
from historical sequential-process policy RNG. The two seeds are separately
recorded and paired across arms; historical scores are not asserted to replay.

Every GPU process must be bound to physical GPU7. The historical mapping is
`CUDA_VISIBLE_DEVICES=7`, `MUJOCO_EGL_DEVICE_ID=4`, `MUJOCO_GL=egl`,
`PYOPENGL_PLATFORM=egl`, `JOBLIB_MULTIPROCESSING=0`. EGL4 is inherited mapping
evidence only and must be verified on this host. GPU5 and external colocation
settings in old runners are not authorized.

## Compute identity and limits

Each full guided chunk scores 16 initial candidates plus 16 candidates in each
of 10 ED iterations: **176 candidate evaluations in 11 score batches** for
both Q0 and C0. Q0 archive evaluations are 176; C0 archive evaluations are 0,
with shadow candidate observation active in both. Legacy truncation requests
are `[3,2,2,2,2,1,1,1,1,1]` (sum 16). Initial denoising uses the checkpoint
scheduler because `policy.rdt.num_inference_steps=null`; freeze that resolved
number before execution.

176 is not the number of diffusion model forward calls. Actual forward,
RBF-gradient/fallback, reward, VLM/retry, and wall-clock costs must be measured
separately. Diagnostic overhead also differs from the old snapshot. Real-run
cost accounting must include aborted GPU work and every dispatched attempt.

**Score:** unmeasured (`null`), no new success claim. **Insight:** explicitly
disabled later mechanisms preserve historical synthetic archive/allocation
behavior; the remaining parity risks are input/provider/runtime identity,
new diagnostics/hard gates, and hardware/timing. The restored source is an
audited starting point, not a demonstrated performance improvement.

## Owned runner handoff

`scripts/qd_ed_final_runner.py` now provides `validate-plan`, `print-command`,
`run`, and `reconcile-ledger`. It imports no historical runner. `--help` succeeds;
Q0 and C0 each compose with Hydra using all 135 static overrides. A scalar
camera-name string containing a comma is explicitly quoted to prevent accidental
Hydra sweep parsing.

CPU verification:

```bash
CUDA_VISIBLE_DEVICES='' /home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest -q tests/test_qd_ed_final_runner.py
```

Current result: **31 runner tests passed**; the final combined runner, report,
and GPU-probe CPU suite passed **48 tests in 0.25 s**. Tests exercise duplicate-key rejection,
hash invalidation, provider precedence/endpoint binding, GPU7 admission/external
process detection, task/env/policy-seed pairing, input/model/seed-plan gates,
protected attempt reserves, remaining GPU deadline, interrupted-state accounting,
Stage-query failure accounting, candidate-only descriptor changes, health-probe
costs, protected GPU hours, and rejection of retries for legal failed episodes. They launch no real child,
model, simulator, GPU workload, or provider request.

The plan schema is `qd-ed-final-plan-v1`. Required top-level fields are `frozen`,
`run_name`, `worktree`, `artifact_root`, `source_commit`, `code_files`,
`profiles_path`/`profiles_sha256`, `runtime_manifest_path`/`runtime_manifest_sha256`,
`runtime_inventory_path`/`runtime_inventory_sha256`, `seed_plan_path`/`seed_plan_sha256`,
`input_contract_label="input_repaired"`, `egl_mapping_verified`,
`phase_authorization`, and `episodes`. Every episode has `episode_key`, `split`,
`iteration`, `profile`, `seed_block`, `task_id`, `env_seed`, `policy_seed`,
`init_index=0`, `bddl_sha256`, `init_file_sha256`, `init_row_sha256`,
`budget_bucket`, and `timeout_seconds`. N1 plans separately bind
`candidate_profiles.N1={path,sha256}` and list that candidate config in
`scientific_config_files` plus `code_files`; its full profile must differ from
Q0 only in `qd_descriptor`. Baseline plans need not bind unused candidate files.
Infrastructure retries additionally
require an explicit `retry_of` and consume the recovery allocation. Source
fingerprint paths are relative to the new worktree; use the runner's
`REQUIRED_CODE` constant as the minimum set.

Example CPU review (once a plan file has been produced):

```bash
CUDA_VISIBLE_DEVICES='' /home/hynx/miniconda3/envs/vla-pilot/bin/python scripts/qd_ed_final_runner.py validate-plan --plan data/qd-ed-final-plan.json --allow-unfrozen
CUDA_VISIBLE_DEVICES='' /home/hynx/miniconda3/envs/vla-pilot/bin/python scripts/qd_ed_final_runner.py print-command --plan data/qd-ed-final-plan.json --split dev --iteration 0 --allow-unfrozen
```

`--allow-unfrozen` exists only for CPU review. `run` requires the frozen phase,
source, profiles, seed plan, actual model files, input files, verified CUDA/EGL
mapping and ready provider. Provider checks compare the actual inherited URL,
model, and credential-source name (`GOOGLE_API_KEY` precedes `OPENAI_API_KEY`)
with the frozen contract; key values are never serialized or redirected.

The runner serializes writers with `flock`, writes an append-only
reserved/dispatched/valid/aborted journal, and atomically updates
`research-state.yaml`. Every dispatched ID consumes one attempt and all owned
GPU-process wall time, including abort/startup, is charged. It preserves 60
Validation and 40 formal attempts within the 240-attempt/48-GPU-hour cap and
reserves the unconsumed 14 Validation and 10 formal GPU hours, plus 30 seconds
of termination/monitoring grace, before each launch. Prospective hour
reallocation requires both `budget.gpu_hour_reservations` and a matching
`data/gpu-hour-reservation-ledger.jsonl` event with rationale. GPU health probes
use `data/gpu-healthcheck-ledger.jsonl`, consume GPU hours in recovery, and
consume no episode count; unfinished probe reservations block episode launch.
One task per subprocess
fixes task-to-seed binding. SIGTERM/interrupt terminates only the owned process
group. GPU7 compute PIDs are checked every five seconds while running; an
external process causes the owned child to stop without touching the external
process. This detects sharing at sampling boundaries rather than providing
an exclusive scheduler reservation against unrelated launchers.

`run --episode-key KEY` executes a specifically named pending plan row;
completed legal outcomes cannot be resumed or retried. `reconcile-ledger`
checks that no child with the attempt identity remains, requires GPU7 admission,
and closes a dead interrupted attempt. Missing end timestamps are conservatively
charged through reconciliation. A completed valid task failure remains valid.
Journal-to-state repair after an interrupted atomic state write is idempotent.

Completed event `valid` means a final scientific observation, not necessarily
success or safety acceptance: wall timeout, simulator/action/nonfinite errors,
missing results, and other unproven failures are recorded as
`success=false,task_failure=true,outcome_valid=false` and remain in the task
denominator. Only proven launch/monitor/external-GPU infrastructure problems
are retryable `aborted` events. A legal episode with no guided chunks remains
in the denominator; actual QD and Stage activity are separate aggregate gates.
All failed Stage queries invalidate the outcome, partial query failures remain
counted, and no query events do not imply successful Stage activity. Matching
outcome video must exist and have a CPU-decodable first frame; safety metric
fields must be present and valid.

The unified `eds_eval/episode_compute.jsonl` schema
`qd-ed-episode-compute-v1` is integrated. Normal completed outcomes require
matching episode/task/env seed and available nonnegative policy/provider
counters, including DiT and encoder forwards/batch rows, denoising, renoise,
RBF gradient, reward calls/evaluations/scoring batches, guided/unguided chunks,
and actual provider request/SDK-retry counts. Model batch-list sums must agree
with forward counts. Guided chunk count must equal saved metric records.
Actual reward scoring batches must be at least the search score-batch total:
mechanism trace/pretest calls are additional real cost, so equality is not
assumed. Failed outcomes retain any available counters and disclose missing
telemetry; they are not silently removed.

At this checkpoint no episode has been launched. The provider and exclusive
CUDA/EGL checks remain real-dispatch gates. This worker has not changed the
authoritative state, dispatched work, committed files, or touched old artifacts.
