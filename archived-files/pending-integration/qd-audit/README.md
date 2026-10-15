# Offline fixed-grid EDS-QD mechanism audit candidate

This directory is a preparation artifact in `/tmp`; it has not been integrated into the repository. It runs on CPU with PyTorch and PyYAML, imports no policy, simulator, repository code, provider, or generated reward code, and makes no network requests. It is not an online EDS-QD result or cohort acceptance report.

## Fixed protocol

Only `target_relative_endpoint_xy`, a 4 × 4 grid, capacity one, and `sparse_priority` are supported. A different descriptor is a protocol mismatch. Each chunk starts with an empty archive and a fresh population of 16; ten iterations plus the initial score require exactly 11 score calls and 176 evaluated candidates. The archive and its candidate visit counts persist within that chunk and are reset at the next chunk. This does not establish cross-chunk or cross-episode learning.

The descriptor is the projected end-effector XY position **after eight commands**, minus the first target's XY position. Reward scoring receives the existing trajectory slice **p1 through p7**. The descriptor endpoint and the scored reward trajectory are deliberately distinct. The tool does not change or reinterpret either definition.

Bounds are frozen from the initial float32 descriptors: 5% and 95% quantiles, expanded by 10% of that span, with a minimum axis span of 0.08 m centered on the median when needed. Out-of-bounds candidates are clamped to an edge cell. Every candidate increments its cell's visit count, including rejected candidates. Each cell retains its highest reward, with ties broken by lexicographically smallest action fingerprint. Parent weights are `1 / (candidate_visits + 1)`; 16 integer slots use largest remainders, with a local seeded CPU permutation for ties. Final selection is the archive-wide highest reward, then fingerprint, then cell id.

The candidate checks the fixed normal reward mode, EDS guidance route, sampler, rollout, no-cache, no-memory, no-anchor, no-secondary-lane and no-fallback settings as well. The current resolved EDS configuration omits `reward_mode`; the reviewed runtime defaults to `normal`, and reports expose that origin. The metric itself must explicitly record `normal`. The current resolved EDS configuration omits `shuffle_seed`; the reviewed runtime's default is zero. Reports expose that origin explicitly. A future resolved configuration should preferably declare zero, and the outer audit must bind the runtime/source version that defines this default.

## What is verified

- The recorded activation flags, QD-selected population source, 160 QD parent slots over ten iterations, and 11 / 176 scoring budget.
- Candidate stream length, float32 finite values, positive finite bounds, fingerprints, checksum, integer iteration ordering, and within-chunk fingerprint consistency.
- Independent reconstruction of initial bounds, per-cell candidate visits, elite insertion/replacement/rejection, sparse weights and integer parent allocation, coverage, overflow, and archive global-best selection.
- Optional saved latent tensors: candidate fingerprints and actual resampled parent tensors for exactly the saved iterations. Loading uses `torch.load(..., map_location='cpu', weights_only=True)`; duplicate stage identities are rejected. Actual trace `initial`/`scored` stages use iteration zero and map to shadow candidate batch minus one. QD offspring sources and sparse-selection labels must agree. Any supplied trace rewards/costs must join the corresponding candidate stream or selected parent rewards; this is record consistency, without reward execution. The existing trace generally saves resampling only at iteration zero. A passing iteration-zero trace does not establish all ten parent tensor paths.
- In `--mode eds`, archive-OFF control settings and records, fresh final population, 160 weighted offspring parents, empty QD selection fields, and no recorded archive updates. The hypothetical archive reconstructed from a shadow observer is never treated as QD activation.

The bounds checksum check remains exact. CPU arithmetic matched all 47 initial bounds/checksums in one existing historical active-archive log (`review/historical-active-xy-bounds.json`). This is historical record compatibility, not a current GPU diagnostic. CPU reference parity alone does not establish CPU/GPU quantile bit identity on the current environment. Before a new online QD cohort, the integration owner plans a short core-versus-audit numeric diagnostic on the authorized GPU after the running EDS cohort ends. Any discrepancy must be resolved before that cohort; this candidate does not relax checks after observing results.

The result is named `recorded_mechanism_valid` intentionally. Descriptors and rewards remain recorded inputs; the tool does not recompute geometric projection or generated reward code. It does not independently capture the final returned/executed action tensor. Reports always expose these boundaries, `descriptor_geometry_verified=false`, `executed_selected_tensor_verified=false`, the exact tensor-covered iterations, and `cohort_valid=null`.

Low coverage, reward ties, clipping overflow, lack of reward improvement, and task failure are valid scientific outcomes. A mismatching protocol or inconsistent record is a mechanism/evidence failure; the tool does not classify task failure as an infrastructure error.

## Invocation

```bash
CUDA_VISIBLE_DEVICES='' /home/hynx/miniconda3/envs/vla-pilot/bin/python \
  /tmp/steering-qd-audit/audit_qd_mechanism.py \
  --metrics /absolute/run/output/eds_eval/eds_metrics.jsonl \
  --config /absolute/run/resolved-config.yaml \
  --mode eds_qd --task 0 \
  --report /tmp/qd-task0-audit.json
```

An optional `--step 0 --trace /absolute/path/trace.pt` requires exactly one selected metric row. JSON configuration containing only `eds_config` fields is also accepted. Exit zero means all selected recorded chunks pass the mechanism checks; it does not mean a completed task or cohort was accepted. Empty selection and duplicate chunk identities fail. Malformed input fails rather than being silently skipped. Read a stable metrics snapshot if the writer may be between JSON writes.

## Required outer integration checks

The cohort audit must separately bind run manifest, frozen source, resolved configuration, task/episode/seed, complete provider and control contracts, and compute rows. It must establish that every expected guided chunk has exactly one metric record, and join any optional trace by task, episode and global step. This tool detects duplicate selected rows but cannot infer missing chunks from the metrics stream alone. Success counts belong to the completed online cohort, not synthetic fixtures or historical references. Config and file hashes, task coverage, contract results, and tensor coverage should accompany any reported mechanism conclusion.

## CPU validation and evidence

`test_audit_qd_mechanism.py` contains manually derived low-coverage and tied-reward examples, sparse-vs-uniform parent allocation, replacement/retention, local RNG isolation, valid overflow, and corruptions of activation, budget, descriptor, bounds, visits, parent allocation, elite/final selection, sampler settings, missing evidence, latent tensors and duplicate trace stages. The real EDS archive-OFF fixture must pass control mode and fail QD-activation mode.

`fixtures/provenance.json` binds the copied first-chunk record and source configuration. `real-eds-control-task0.json` audits all 26 recorded guided chunks for the already completed EDS task 0. This is control evidence only. Independent review also exercised corruption reproducers and compared the arithmetic against the reviewed core implementation on CPU; the receipt links those results with their exact reviewed hashes. No real EDS-QD cohort or QD-enabled tensor trace has been run for this candidate. `validation.json` records the final CPU test result and artifact hashes.
