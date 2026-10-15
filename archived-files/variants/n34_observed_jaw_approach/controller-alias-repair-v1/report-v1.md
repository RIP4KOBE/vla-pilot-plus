# N34 node15.4 bounded CPU audit repair

Committed `3f4ec9e27aeb139db246831e8ffc0325a8ea731c` on `codex/n34-production-integration`. Source base: `d93129b24d09711458975c5964c2127e01442a4f`; owning source from authority/prereview: `c14e1e92870a51b92d70d21e01a0ffaf1a14534b`.

Only `scripts/qd_ed_n34_controller.py` and `tests/test_n34_source_controller.py` changed. Scientific code and frozen protocols were preserved.

Attestation now reads the explicit reviewed robosuite 1.4.0 mapping: `control_delta -> use_delta`, `control_ori -> use_ori`, `policy_freq -> control_freq`, and `uncouple_pos_ori -> uncoupling`. All other fields have explicit identity mappings. Proof and receipt names remain canonical. Existing module/class/source path/source hash/config comparisons and semantics proof checks remain intact. Missing attributes still raise; there is no discovery, default, or fallback.

The authority-bound prereview hash and installed OSC source hash matched. Installed source was inspected as text only. Tests use synthetic controller modules/objects and local source fixtures, not deployed runtime evidence.

Focused test command:

```sh
env CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 NUMEXPR_NUM_THREADS=2 VECLIB_MAXIMUM_THREADS=2 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 taskset -c 0,1 /home/hynx/miniconda3/envs/vla-pilot/bin/python3.12 -m pytest -q -p no:cacheprovider tests/test_n34_source_controller.py
```

Result: **62 passed in 2.31s**, exit code 0, wall time 2.763 seconds. CPU affinity was 0,1; numerical thread limits were two; CUDA visibility and pytest plugin autoload were disabled. Coverage includes mapped deployed shape, all missing/wrong config attributes, canonical-name decoys, wrong module/class/source path/hash/bytes, proof schema regressions, canonical receipt shape, and constructor restoration on failure. Existing source/runtime closure fixture checks also passed. `git diff --check` passed; the commit parent matches the authority base and the worktree is clean.

Evidence is recorded in `test-command-v1.txt`, `test-output-v1.log`, `test-result-v1.json`, and `implementation-result-v1.json` alongside this report.

Unresolved release/runtime closure:

- External ROOT_REVIEWED deployed-controller semantics proof and runtime/source closure remain release-owner responsibilities; this repair does not issue or update them.
- Full postprocessor/module closure remains pending as identified by the prereview.
- Release source inventories/hashes must bind the repaired commit before any separately authorized runtime use; frozen protocols and existing release artifacts were not changed.
- Actual simulator/controller construction and same-process runtime attestation were not executed. Fixture tests establish adapter behavior only.
- Physical gain is not certified; GPU authorization remains false. No scientific score, promotion, validation/formal study, or target-met claim is produced.

No simulator/model run, GPU experiment, Stage/provider experiment, validation/formal study, credentials/API/Poe access, nested agent, or coordinator/driver/state/ledger mutation was performed. The prohibited design document and Superpowers were not accessed. No scientific score or promotion is reported. This bounded engineering task is complete and stopped.
