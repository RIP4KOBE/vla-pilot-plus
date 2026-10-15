# N26 independent terminal reader — CPU delivery

Status: **CPU preparation complete; actual metadata read and all downstream execution remain closed pending root review.** The experiment remains frozen at `6026794cd5d52f3a5054bf2704ebb3c516f9f47e`. No study/implementation/source/state/budget/ledger file was changed, no Git integration was performed, and no real attempt/proof/plan/result or protected input was read.

The three external modules independently reconstruct the existing terminal result from a closed JSON inventory. They bind the original 315-file source, final source review, historical source bridge and metered 36-case arithmetic proof, ordered cell/attempt journal, command/context/process/receipt/native metadata, all costs and typed recoveries. They do not import production modules or replay native tensors/Stage classification. Detailed provenance assumptions and schemas are in `reader-contract-v1.md`; `metadata-input-disabled-v1.json` is deliberately non-executable.

Important checks include global task-major chronology, at most two exact typed recoveries, earliest whole-quad futility, explicit status/journal disagreement, complete first-valid denominators, partial/unknown token costs, profile-bound native markers, legal zero-gradient/zero-guided cases, finite inventory limits, immutable review output and public process cleanup. Missing PID remains null/Unknown and does not satisfy the downstream cleanup gate. The pure reconstruction makes no cleanup observation; only the root CLI inspects `/proc` under the existing locks.

The original supervisor/writer discrepancy at a first futility on cell 40 has an exact synthetic case: the original result remains INVALID with reconstructed REJECT, rather than being silently relabeled. Full valid REJECT is tested separately with N26 five successes below a six-success control. No experiment rule or active source was repaired by this work.

## Test evidence and preserved failures

| Evidence | Outcome | Interpretation |
|---|---:|---|
| cpu-initial-v1.log / guard-initial-v1.json | Pytest internal error before tests; 4 blocked writes | Test bootstrap attempted global temporary paths and `/dev/null`. Preserved; not clean evidence. |
| cpu-second-v1.log / guard-second-v1.json | 28 assertions passed; 3 blocked writes | Global tempfile probing remained. Preserved; not clean evidence. |
| cpu-third-v1.log / guard-third-v1.json | 17 passed, 11 failed; guard 0 | Reader implementation defect: presence-loop variable shadowed the scientific cell key. Corrected without changing gates. |
| cpu-fourth-v1.log / guard-fourth-v1.json | 45 passed, 8 failed; guard 0 | Negative-test expectations assumed a returned rejection, while stricter fail-closed checks raised on invented status prefixes/later attempts. Assertions corrected; gates retained. |
| cpu-fifth-v1.log / guard-fifth-v1.json | 53 passed, 5.05 s; guard 0 | Main corrected metadata matrix. |
| cpu-sixth-v1.log / guard-sixth-v1.json | 65 passed, 6.70 s; guard 0 | Added chronology, futility boundary, interrupted persistence, absent process and unsettled cost checks. |
| cpu-cli-v1.log / guard-cli-v1.json | 20 passed, 49 deselected, 4.71 s; guard 0 | Four new CLI composition/source/path/live-process cases plus affected fixture/order/disposition checks. |

There are **69 distinct test cases** in the final file. The final necessary evidence is the 65-case suite plus the 20-case targeted follow-up, with overlap; this is not claimed as 85 distinct cases or one final 69-case invocation. The follow-up changes only synthetic collector/stat fixtures and adds CLI tests; production modules are the same as in the 65-case run. No unaffected science/math suites were run.

All guard-clean runs used guard v3, two CPU threads, invisible CUDA, disabled pytest plugin autoload and bytecode writes. They imported no Torch and allowed no actual experiment input, network, subprocess, API, model or simulator activity. Guard v3 fixes bootstrap paths by assigning the owned `tmp/` to `tempfile.tempdir` and using an owned pytest log path; it does not widen permission to global temporary writes. Previous guards/logs remain untouched.

Reproducible main selection, from this directory (use new log/basetemp names to preserve prior evidence):

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /home/hynx/miniconda3/envs/vla-pilot/bin/python cpu_guard_v3.py guard-review-new.json test_terminal_reader_v1.py
```

Exact final targeted selection:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /home/hynx/miniconda3/envs/vla-pilot/bin/python cpu_guard_v3.py guard-cli-v1.json test_terminal_reader_v1.py -k 'root_cli or recovery_global_cap or dispositions or cross_cell or futility or reserved_then'
```

The three production module hashes are in `reader-source-manifest-v1.json`. Static source input hashes are in the original index and additive supplement (the supplement records the inherited six case-name source). The final delivery manifest hashes source, contract, disabled template, synthetic tests/fixtures/guards and every success/failure log. Generated synthetic basetemp trees are retained locally but excluded from the compact delivery manifest; they contain no experiment data.

## Remaining root work and limitations

Root must independently accept this delivery, await immutable terminal/controller death, collect and authorize the exact bounded metadata manifest, bind the original source/runtime/prerequisite command attestation and current filtered journal/resource projections, then execute the locked external CLI. Its decision verifies the existing result; it cannot create a missing result, rerun a failed episode, release validation/N26 successors or change a budget.

Original native tensor correctness, restricted Stage classification and metadata projection completeness remain explicit attestation dependencies. This CPU work establishes JSON binding and reconstruction behavior only; no real schema acceptance, actual cleanup, terminal outcome, GPU arithmetic or efficacy claim is made. A malformed immutable result may cause a fail-closed CLI error rather than a newly written review; its log must be preserved. Null historical PID stays Unknown even after an empty current process scan.
