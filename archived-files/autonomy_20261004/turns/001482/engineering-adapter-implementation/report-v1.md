# Node 15.6 — disabled partial implementation

**Status: PARTIAL_DISABLED_IMPLEMENTATION_COMMITTED.** No completion, release, adoption, B5 acceptance or runtime success is claimed.

Base `813f25bc89a3920149739a2bf957b2e1b3db29c4` → commit `3b05c0b557b59bf3dc9ddbb11593a41a4e49f4d1` on `exp/n36-engineering-adapter-001482`.

Implemented separate pinned scope/accounting schemas, exact task0/C0 mapping, the full 40-manifest audit view and separate engineering manifest, strict worker/health schema routes, prospective authority/accounting checks, and one-use journal reconstruction. The shared scientific closure is an exact AST extraction of 21 top-level statements. Scientific source/configs, full-cohort identities/limits, thresholds and stopping rules remain unchanged. Changed paths and exact evidence are in [report-v1.json](report-v1.json).

**Dispatch is unconditionally vetoed in code.** The engineering runner route, public one-shot entry, health route/reservation and worker launch guard cannot run, even with approval-like flags. A subsequent reviewed implementation commit is required to lift the veto.

**CPU checks:** final focused command passed **190 tests** (114 new engineering cases, 76 unchanged regressions), in 43.15 seconds:

```sh
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q tests/test_n36_engineering.py tests/test_n36r4_admission.py tests/test_n36_release.py tests/test_n36_runner.py --basetemp=.cpu-test-artifacts/final-focused > .cpu-test-artifacts/final-focused.log 2>&1
```

All 40 audit manifests and the extra engineering manifest were composed/compared with production Hydra/comparison code. Temporary actual lock/fsync/journal/state primitives cover reservation, dispatch, abort and terminal-before-artifact crashes. Synthetic outcomes are not GPU receipts. The fixtures contain stale/disabled runtime/source metadata and cannot establish final-source runtime closure, DINO construction or native/GPU validity.

Broader shared tests reported **43 passed / 49 failed including subtests**. The production-repair fixture omits `owner_root`; exact base copies reproduce its 47 errors across six unittest tests. Two stop-guard fixtures omit `bind_dino`, whose call already exists at the base; those two full tests were not separately rerun on a base checkout. Existing tests and production guards were not weakened. All commands, failed iterations, hashes and fixture limitations are retained in the JSON report.

**Remaining implementation/verification work:** complete closure-backed health/episode release mutation tests; actual released engineering runner/health lifecycle and receipt/readiness fixtures; full authority/adoption/snapshot checks; independent review of routing, one-use accounting, lock transfer and crash semantics. This exceeds the remaining bounded window, so the partial commit stays disabled. Future final-source inventories, 40 refreshed audit manifests plus engineering manifest, B5/root adoptions and separate releases remain owner/reviewer responsibilities.

Disabled inputs: [scope](scope.disabled-v1.json), [accounting](accounting.disabled-v1.json). Source checks: [source-equivalence-v1.json](source-equivalence-v1.json). These grant no authority.

No GPU/model/download/evaluation, protected outcomes, prohibited design file, credentials, extra agents, foreign writes, owner-state/ledger writes or driver/lease acquisition occurred. Only intended source/test files were committed; new test artifacts remain under the authorized checkout. The executor skill was followed within the user's CPU-only override; no coordinator/tree-state workflow ran.
