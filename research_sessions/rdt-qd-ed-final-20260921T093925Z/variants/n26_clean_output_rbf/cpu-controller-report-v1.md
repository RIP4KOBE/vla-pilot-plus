# N26 Phase B conditional CPU delivery

Status: **CPU preparation passed; native CUDA arithmetic and research score UNKNOWN.** Nothing here authorizes integration, budget adoption, a resource process, Dev, validation or formal evaluation. The active N25 source and all real research state/ledgers/outcomes were untouched. No real historical proof was read or passed to `bridge.build()`.

Frozen source is `c09dffe956c391d85ecc02e3288b9fa982e86ce7` on `codex/n26-clean-output-rbf`, clean. Protocol precommits are `c3fc62d` and `491c361`. The 286-file manifest is `source-manifest-controller-v1.json` (file SHA256 `8cae3e7bb0104cb978237b5d4323909e13ffc8a03036958717c5378960ca9bdf`, record digest `4565c435feaee85b6ce3aed72a6900ebeafcad7603556b516174704d6d483eb8`).

## Change and source boundary

The Phase A science/profile at `8fd01eb77e2e83a100e54b21dc955c34bda9a3cc` is unchanged. Of its 263 files, 261 remain byte-identical. The only shared changes are explicit routes in `scripts/qd_ed_final_runner.py` (13 existing functions, one new predicate; 77 existing functions unchanged) and `scripts/qd_ed_n23_worker.py` (validate_context/run_worker/verify_receipt; 13 others unchanged). `cpu-source-bridge-controller-v1.json` and the tracked reverse edit record restore both whole files exactly to Phase A. This CPU record has no real runtime/proof references and is not the executable source-equivalence bridge.

Ten new N26 modules implement the independent reference, profile-bound native audit, tensor resource proof, source bridge, contract, prepare, supervise, report and typed recovery. Six test/support files and seven frozen protocol/contract/source-index documents complete the 23 added files. `source-diff-controller-v1.patch` contains the Phase B diff. The detailed source/profile list is in the manifest; no core/model/provider/controller numerical function or scientific profile changed in this phase.

## Evidence and limits

The independent reference reconstructs only the three frozen full-input strides: contiguous `(8192,128,1)`, transpose `(8192,1,64)` and model-like slice `(8576,128,1)`. Unknown strides fail. The slice uses a representative synthetic backing offset 384; the actual episode storage offset is unrecorded and remains UNKNOWN. Each actual future bounded witness must pass native byte comparisons, including clean input equal to model_output_before, cast origins, projection, raw and normalized gradients, native norm, update operand, and actual after values. Operand and measured before/after remain separate. Independent reference values do not call the production helper as their oracle.

The future fixed proof contains 6 cases × 2 dtypes × 3 layouts = 36 checks, with strict interior parity and deliberately corrupted inputs/outputs rejected. Synthetic layouts are constructed after device transfer. CPU execution validates the code and wiring, not CUDA reductions. There is no tolerance relaxation and no extrapolation from rounded summaries. Coincident/all-saturated zero gradients are valid. Later calls outside the predefined first-guided 11 witnesses receive scalar consistency checks, not a claim of full independent tensor replay.

All four arms retain the owned same-process wrapper; C0/Q0 audit on CPU, N25/N26 arithmetic on the assigned CUDA backend. Every actual worker would remain on GPU7. The supervisor consumes receipt/report JSON and hashes without another CUDA replay. N25 control audit is delegated unchanged. N26 markers cannot all disappear and silently downgrade to the N25 gate. Strict zero-guided metrics omission and the exact existing Codex timeout recovery conditions are preserved.

## CPU verification

All four guarded test runs passed: 36, 236, 2 and 20 executions. These cover **283 distinct final tests**, with 11 necessary affected regressions repeated (294 successful executions total). Phase B has no failed test run. The fifth guarded run closes all 286 source files with zero missing. Every run reports 2 compute/inter-op threads, CUDA uninitialized and zero blocked operations. The guard is a Python audit/import/path policy, not an OS sandbox.

Coverage includes FP32/BF16 full synthetic guided loops across all three layouts, independent audit acceptance and corruption rejection; real serializer/zero-guided omission shapes; exact task-major matrix/profile/source/runtime closure; N25 valid rejection admission and promotion/invalid/active rejection; resource one-shot accounting, cleanup and capacity; same-process audit ownership/receipt binding; typed recovery caps and all terminal/cost paths; status lag preserving independently reconstructed accepted journal prefix as INVALID; unchanged control routing; historical proof bytes and settlement; strict reverse bridge and source drift rejection. Unmodified core/fkd_class.py docstrings emit the six invalid-escape SyntaxWarnings in the large run.

Logs and exact summaries are in `cpu-results/phase-b-*.log` and `cpu-controller-test-results-v1.json`. Phase A's initial failure was an implementation/config-field defect: the new configuration gate referenced the nonexistent use_ed_cache field. Its original failure log and accepted correction remain unchanged and are explicitly linked in the new test summary; the failures are not reclassified as Phase B passes.

A reproducible focused numeric command, run from this variant directory, is:

```bash
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /home/hynx/miniconda3/envs/vla-pilot/bin/python - <<'PYTEST'
import runpy, sys
runpy.run_path('n26_cpu_guard_v2.py')
sys.path.insert(0, 'implementation')
import pytest
raise SystemExit(pytest.main(['-q', '-p', 'no:cacheprovider', '--basetemp=tmp/review-numeric-unique', 'implementation/tests/test_qd_ed_n26_backend.py', '-k', 'actual_preflight_numerical']))
PYTEST
```

No additional rerun is required for this delivery. The guard permits only synthetic fixtures/static source dependencies; it does not authorize reading the real proof, runtime, Dev or protected records.

## Closed admission and next root steps

The three frozen Phase B documents are bound unchanged, including admission clarification. Only a root-accepted **valid N25 Dev REJECT or REJECT_NUMERIC_FUTILITY** admits this N26 protocol. N25 promotion prioritizes its validation. INVALID, active, missing/inconsistent records, or a later validation rejection do not admit N26.

The prospective matrix is exactly task0..9 × C0/Q0/N25/N26, 40 primaries and at most two existing typed whole-episode sole-timeout recoveries. Promotion requires all 40 valid, N26 at least 5/10 and at least each control, plus substantive QD/ED and all evidence gates. Futility is evaluated only after a complete quadruple. Zero-gradient/clipping/activity counters are descriptive, not arbitrary efficacy gates. Capacity failure closes incomplete/INVALID with original results and costs, without automatic resume.

Current 494 attempts/100 GPUh and buckets 55/199/180/40/20 remain unchanged. Future finite root budget authority is mandatory; no claim is made that this cohort already fits available buckets. Before launch the full primary/recovery slot capacity must fit. At every dispatch full 1840 seconds must fit local and cumulative unprotected hours. The local cap is frozen later at no more than min(22h, actual remaining unprotected hours), preserving 32h validation and 12h formal reserves.

The separate, future one-process tensor proof is capped at 60+40 seconds and zero episodes/model/API/simulator calls. Its entire time is charged to the health ledger and cumulative GPU hours (recovery GPU-hour accounting); it does not consume an episode recovery-attempt slot. Reservation/failure consumes the sole opportunity. Dev reservations block another proof. Existing historical N23 and N25 proof costs must already be settled; they do not replace N26's independent proof.

`disabled-templates-v1/` contains nine review blueprints with executable=false, authorization=false and unresolved references. They are not live authority/plan files. Exact record schemas and root CLI order are in `implementation/experiments/qd_ed_n26/controller-contract-v1.md`: after valid N25 rejection, root reviews/integrates this exact source, constructs predecessor and finite budget authority, checks actual runtime and historical settled proofs, builds the real source bridge, then issues the one-resource review/authority/release. Only a strict native PASS permits final review/adoption, exact Dev plan freeze, command review and Dev release. Current Codex managed login remains the only provider; Poe credentials are untouched and never called. Validation/formal launch remains closed.

The executor stops after this CPU delivery for independent root review. No algorithm benefit, live readiness, actual CUDA proof or task success is claimed.
