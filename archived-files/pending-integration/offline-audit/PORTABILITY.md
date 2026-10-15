# Proposed offline audit integration

Nothing here is applied to the repository or running cohort. The scientific runtime,
configuration, sampling, RNG behavior and online provider are unchanged.

Recommended repository paths:

- `scripts/audit_steering_contract.py`: final audit draft plus packaging-only patch.
- `scripts/steering_transport_audit.py`: unchanged pure offline transport helper.
- `tests/test_steering_contract_offline.py`: 25 completed-fixture cases plus two real
  prefix/path-relocation checks. Completed examples explicitly synthesize closure.
- `tests/test_steering_transport_audit.py`: 25 transport cases.
- `tests/test_steering_audit_fixture.py`: three integrity/relocation/provenance checks.
- `tests/steering_audit_fixture.py`: relative-path materializer; never loads Torch.
- `tests/fixtures/steering_contract/`: immutable blob store, file index, provenance,
  README. Use the copy provided here, identical to `/tmp/steering-audit-fixtures`.

The candidate `tests/conftest.py` provides a local project import root and an original
run/asset read guard. When merging into the real suite, keep the guard scoped to
these tests (fixture or dedicated test subdirectory), not to unrelated runtime tests.
The actual paths to reject are derived from fixture provenance; no host path is
hard-coded into test Python. There are no missing-path skips.

Two packaging changes are isolated in `packaging-only.patch`: support both package
and direct-script helper imports; remove the draft-only `/tmp` report restriction so
CLI tests work with any pytest temporary directory. They do not alter audit checks.
The CLI writes only its explicit report argument and fails nonzero on bad evidence.

The content store is 4,173,951 bytes; metadata brings the fixture to about 4.2 MB.
Materialization reconstructs 58 logical files (4,836,322 bytes before path rewrites)
from 52 unique blobs. Two queries/40 action steps replace 38 queries/720 steps;
full-size original PNG bytes are deliberately retained for exact marker checks.
The status and completed receipt are test scaffolding, never an online trial result.

From this candidate directory, with CPU dependencies in the active environment:

```bash
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 python -m pytest -q tests -p no:cacheprovider
```

From the eventual repository:

```bash
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 python -m pytest -q tests/test_steering_contract_offline.py tests/test_steering_transport_audit.py tests/test_steering_audit_fixture.py -p no:cacheprovider
```

CPU dependencies: pytest, PyYAML, NumPy, Pillow, OpenCV. Model weights, LIBERO install,
Torch, CUDA, Codex login, source study worktrees and historical output trees are not
required. This suite validates evidence and the audit, not episode success.

Validation: 55 passed in 3.59 seconds; `cpu-test.log`, `results.xml`, `validation.json`
retain the command, result and hashes. The first version also passed 55 tests in
3.71 seconds before packaging-import and report-path adjustments.
