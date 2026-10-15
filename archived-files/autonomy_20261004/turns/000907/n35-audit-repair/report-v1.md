**CPU_REPAIRED_PENDING_INDEPENDENT_REVIEW — node15.5.**

Base `c3730e5287fe659dffc95c40bf6d8b7ba95d1da9` → separately reviewable fix `52a87af0bf11f95b21ce17aba456dc98944d9774`. Scientific score: **null**. No implementation or GPU acceptance is claimed.

Authority SHA-256: `54c04e3a0dd201cb802c2c4ed52ccf72fc4b3dca9c7f79b85217111c769ed9aa`. Frozen protocol SHA-256: `b8ac519a02623a7f033c5ce4b9c805bf1970f10224e29c0f851ba8568b000345`. Accounting SHA-256: `0e6925d214c7613ef2f6a7ffe5b8ec04d6f90fb134b40f0e77e111a67204491c`. All authority direct references, bounded ledger prefixes, original reproduction source and four original failed logs verified; originals remain unchanged. See [verification](verification-v1.json).

- **N35-IR-001:** replay ordered reset epochs through actual recorder outcomes, automatic reset and returned flags. Guided acknowledgements must follow their matching returns. The automatic-reset record retains the old epoch; return, acknowledgement and terminal memory reset use the incremented epoch. Truncation does not increment it.
- **N35-IR-002:** terminal acknowledgement requires exactly one following reset matching episode, decision, step and epoch. Missing, duplicate, premature, delayed, wrong-reason or mismatched reset evidence is rejected before another boundary or end.

Policy proposal, memory implementation, recorder, Main, adapter, scientific thresholds and protocol remain unchanged. Only two audit sources and two relevant test files changed.

**Validation:** final run: 22 passed, including both original review reproductions, termination/truncation at prefixes 1/4/8, 159 corrupted traces, lifecycle/Main regressions and N35 same-process worker regression. Earlier supporting runs: 61 lifecycle/unit/terminal tests, four same-process arm tests, and two reproductions passed. Those earlier runs predate final acknowledgement-order hardening; no single final broad-suite pass is claimed. `git diff --check` passed. CUDA visibility empty; bytecode disabled; OMP/MKL/OpenBLAS threads bounded to 1; pytest cache disabled.

Exact commands, exits and log hashes are in [test results](test-results-v1.json) and [full report](report-v1.json).

`reproductions` — exit 0: 2 passed, 2 warnings in 6.57s
Log SHA-256: `b610958adc1a60f6439f8fbcdb3f0c57bcb6a3a995f7e0e125eb996b23b3bdd0`.
```sh
env CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONPATH=.:tests /home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest -q -p no:cacheprovider --basetemp=/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/000907/n35-audit-repair/fixtures-reproductions-v1 /mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/000904/n35-implementation-review/test_review_reproductions.py > /mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/000907/n35-audit-repair/test-reproductions-v1.log 2>&1
```

`targeted` — exit 0: 61 passed, 19 warnings in 62.74s
Log SHA-256: `c7fbf728e84e6d1f0ac275ac76e71f46e7c1b5384d58c75ad09ad0c26f349a54`.
```sh
env CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONPATH=.:tests /home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest -q -s -p no:cacheprovider --basetemp=/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/000907/n35-audit-repair/fixtures-targeted-v1 tests/test_n35_terminal_reset_audit.py tests/test_n35_closure_intent.py tests/test_n35_closure_intent_integration.py > /mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/000907/n35-audit-repair/test-targeted-v1.log 2>&1
```

`worker` — exit 0: 4 passed, 4 warnings in 28.64s
Log SHA-256: `1f3bbef3923cbc05c2dfe8c4284f4d6cc71080c629b152302e1c1767ce9e3b0c`.
```sh
env CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONPATH=.:tests /home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest -q -p no:cacheprovider --basetemp=/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/000907/n35-audit-repair/fixtures-worker-v1 tests/test_n35_production.py::test_same_process_mandatory_audits_and_tampered_receipts > /mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/000907/n35-audit-repair/test-worker-v1.log 2>&1
```

`final` — exit 0: 22 passed, 22 warnings in 88.17s; 159 corrupted-trace rejections within six parametrized terminal-prefix cases.
Log SHA-256: `bfce000168faaea806f79d5171282fd779fef31db94ac0b0800f1900d8bbb10d`.
```sh
env CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONPATH=.:tests /home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest -q -s -p no:cacheprovider --basetemp=/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/000907/n35-audit-repair/fixtures-final-v1 tests/test_n35_terminal_reset_audit.py tests/test_n35_closure_intent_integration.py 'tests/test_n35_production.py::test_same_process_mandatory_audits_and_tampered_receipts[N35]' /mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/000904/n35-implementation-review/test_review_reproductions.py > /mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/000907/n35-audit-repair/test-final-v1.log 2>&1
```

Changed-file SHA-256 bindings:

- `scripts/qd_ed_n35_lifecycle.py`: `d56c93bc49a15734e3c95b05aa1d008f4cc218e2ddf3156c50930841a8bc1b81`
- `scripts/qd_ed_n35_native.py`: `9e412f940746876c6690fd8064b303bd91eea694580d06242c72614d2997fc39`
- `tests/test_n35_closure_intent_integration.py`: `052e8d19f220a8a2f9092af585bd92c075e5caa05fb0d2bdc5d0b7d7a3d954fc`
- `tests/test_n35_terminal_reset_audit.py`: `ca7ffa2d340b3744ee2a1d42a8592b6712111889f95040e0eb5554883b46ce1c`

Limitations:

- CPU synthetic policy/model/observations only; actual recorder and memory helper emit the tested traces. No LIBERO simulator episode, model/provider service or GPU execution.
- Worker regression uses mocked Main execution, source/runtime/controller/dispatch attestation and CUDA identity. It exercises same-process audit composition and receipts, not installed runtime or deployment acceptance.
- Ordered adjacency checks follow the frozen recorder/Main paths: pre-reset outcome -> automatic reset when terminated -> returned outcome -> guided acknowledgement -> terminal memory reset. Truncation alone does not increment the epoch.
- The final 22-case run covers all changed audit behavior, integration, N35 worker and original reproductions. Earlier 61-case lifecycle/unit and four-arm worker runs predate the final acknowledgement-order hardening; retained as scoped supporting evidence, not a single final full-suite claim.
- Pre-existing SyntaxWarning in core/fkd_class.py (invalid escape sequence) remains outside repair scope.
- Native arithmetic still relies on source-bound recorded GPU cell assignments and other15 commitments; these CPU tests establish no scientific efficacy or installed-runtime/GPU readiness.
- Independent implementation review, source adoption and any execution release remain separate coordinator obligations; this executor performs none.

No source adoption, state/ledger/resource changes, GPU work, protected-phase access, credential reads, external messages, delegation, alternate provider/account use or prohibited-document access occurred. Pre-existing untracked `AGENTS.md` is preserved. Independent review remains required.
