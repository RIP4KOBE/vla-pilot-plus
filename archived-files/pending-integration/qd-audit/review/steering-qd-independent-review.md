# Independent offline QD audit review

Final reviewed auditor: `/tmp/steering-qd-audit/audit_qd_mechanism.py`, SHA-256 `1a11ec87d1c2f542fb5f948ccdaf6cb32ca93d330f2911e3b3afad10c8a225fd`.

Conclusion: the actionable false-pass cases identified in this review are fixed in this version. No remaining blocking issue was found within the declared fixed XY / 4×4 / capacity-one / sparse-priority / no-anchor profile. This is a review of recorded-mechanism validation, not an online QD result or cohort acceptance.

## Fixed findings, independently reproduced before and after the change

The initial auditor SHA `817d51aa13f062bca9d2bc129c6aa6022c30d0b31f6985131eddbe79d9fa50b3` accepted each of these inconsistent records. The final version rejects every case:

1. `initial` trace stage with `iter_idx=999` was joined to the initial candidate batch and counted as tensor evidence. Runtime `core/rdt_policy_steer.py:5070–5088` records both `initial` and `scored` stages at iteration **0**, while the shadow initial batch is labelled **-1**. The fix distinguishes those schemas, validates the iteration/type and does not add invalid coverage.
2. A `resampled` trace labelled `weighted_offspring` while claiming QD selection kinds passed and received parent tensor coverage. Runtime source/kind construction at `core/rdt_policy_steer.py:5144–5272` and trace emission at `5509–5518` give `qd_archive_offspring` / `qd_sparse_priority` for this profile. Contradictory source labels are now rejected.
3. Metric `guidance_type='vls'` passed an EDS/QD audit. The reviewed runtime records `eds` at `core/rdt_policy_steer.py:4721`; the final audit checks the route label.
4. Metric `selected_parent_source='weighted_offspring'` passed despite a QD final population source. Runtime `core/rdt_policy_steer.py:6498` sets the selected parent source to `qd_archive` for active QD; the final audit joins both labels.
5. `reward_mode='inverted'` in configuration and metric passed the fixed normal-reward profile. The final audit requires normal mode and explicitly records the reviewed runtime default when config omits it. This preserves the existing valid EDS config rather than pretending it explicitly contains a missing key.
6. Archive-OFF control records could claim 160 QD parents, `qd_archive` selected sources and a selected QD cell. The final control check requires the fresh/weighted-offspring control route, no active archive update/selection evidence, and preserves the distinction between a hypothetical shadow archive and active QD.
7. Python-finite descriptor values such as `1e100` overflowed when cast to float32 but control audit still reported valid. The reconstruction contained NaNs and could not be JSON-serialized. The fix checks float32 finiteness and positive finite bounds consistently with `core/qd_ed.py:110–169,249–274`; the failure report is now serializable.
8. Available trace reward/cost tensors could contradict the shadow candidate rewards and still pass. The final audit joins the provided reward/cost fields with the corresponding candidate or parent snapshot. It does not demand missing tensor logs or execute reward code.

Original repro evidence: `/tmp/steering-qd-independent-review.json` and `/tmp/steering-qd-extra-review.json`.
Final repro evidence: `/tmp/steering-qd-independent-review-final.json` and `/tmp/steering-qd-extra-review-final.json`. Each binds the reviewed source SHA. The invalid trace cases now have empty corresponding tensor coverage.

## Independent positive checks at the same final SHA

- **100 CPU reference cases:** bounds and checksum, float32 cell mapping including lower/upper/mid boundaries and overflow, seed/tie permutation, weights, integer slot counts and ordered parent cells all agree with actual `core/qd_ed.py`. See `/tmp/steering-qd-independent-review-final.json`.
- **40 complete CPU archive cases, each initial + 10 iterations:** insertion/replacement/rejection accounting, cumulative candidate visits, sparse parent allocation, ordered parent fingerprints, per-cell elites and final global-best fingerprint/reward/index all agree. Includes low spread, repeated endpoints and tied rewards. See `/tmp/steering-qd-archive-parity.json`. The source was captured into a `/tmp` snapshot before importing, and this final rerun is bound to the final auditor SHA rather than an intermediate patch.
- **77 tests passed in 1.47s**, exit 0; auditor source unchanged during execution. See `/tmp/steering-qd-review-pytest.log` and `/tmp/steering-qd-review-pytest.json`. This includes the static copied real EDS archive-OFF first-chunk fixture. The owner separately re-audited all 26 task-0 control chunks; this reviewer does not relabel that as an independently rerun full-task result.
- An additional finite-float32 extreme cancellation example compared core insertion-order averaging with auditor sorted-order averaging under the actual Python 3.12 implementation; both returned 1/3. See `/tmp/steering-qd-mean-order-review.json`. This does not claim identical operation order or GPU numerical execution.

Reference `core/qd_ed.py` SHA: `4415ea7f16029e2fa2e7528c1f7065ba673b7a5a512723bfa9611f992298daa4`.
All executed review commands had `CUDA_VISIBLE_DEVICES=''`, `PYTHONDONTWRITEBYTECODE=1` and the offline audit-hook guard. CUDA remained uninitialized. No GPU, API, download, model execution, shared environment changes or frozen repository writes occurred. Only review files and temporary test outputs were written under `/tmp`; the auditor owner made all candidate fixes under `/tmp`.

## Deliberately retained evidence boundaries

Descriptors and rewards are still recorded inputs. The audit does not establish the geometry projection, generated reward correctness, missing parent tensor iterations, or actual final returned/executed action tensor. Per-cell/accounting agreement alone is not tensor-path proof. The explicit coverage lists and `cohort_valid=null` should remain visible in the final integration. The outer audit must still bind the frozen source/config, task/episode/seed, expected guided chunks and provider/control contracts. No full-tensor logging requirement was introduced in this review.

The exact initial-bounds checksum also assumes CPU reconstruction and the actual GPU float32 quantile/bounds path agree bit-for-bit. CPU reference tests alone do **not** establish that CUDA parity. Before the final source freeze or any QD cohort, the root owner plans a separately recorded short GPU2 diagnostic using deterministic descriptor batches to compare the fixed-profile core and independent audit; that diagnostic was not executed by this reviewer and is not a task outcome. Any numeric evidence-handling change must be settled before scientific outcomes, not by weakening gates after seeing results. The owner’s separate read-only comparison against historical active records can provide additional sample evidence, but cannot prove universal CUDA parity.
