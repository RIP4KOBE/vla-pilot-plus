# Node 15.6 lexical-reference repair

Status: **PASS — bounded CPU engineering repair only**. No production release or scientific result is claimed.

Source before: `d01bc1e2e7acc876653a43ddf157d0b4a641f88a`  
Source after: `e36f8b945f6b2fde9e81010b3d16987b8c771dd0`  
Branch: `exp/n36r3-generated-import-001299`  
Worktree: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r3_generated_import_001299/implementation_worktree`

## Change

`scripts/qd_ed_n36_runner.py:197` now forwards the exact supplied absolute plan and release path strings with unchanged supplied SHA-256 values. Relative paths fail through argparse before launch. The production diff is six added lines and two removed lines; only `main()` changes. All release, source, runtime, health, hash and exact-equality consumers remain unchanged. No frozen evidence was canonicalized or rewritten.

`tests/test_n36_cli_references.py` adds 12 CPU cases using temporary synthetic files. Both references traverse a symlinked parent, including a case preserving literal `//./` spelling. Tests cover relative-path rejection, bad plan/release digests, mismatched plan path/hash in the detached release, root-review plan mismatch, and runtime receipt rejection of changed release path/hash.

## Validation

- `PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' python -m pytest -q -p no:cacheprovider tests/test_n36_cli_references.py` — **12 passed in 1.51s**.
- Original authorized-source `main()` loaded in memory: both lexical-forwarding cases fail as expected (**2 failed in 0.05s**). No checkout rollback was needed.
- Initial fixture iteration: 10 passed and 2 failed at an earlier schema gate; adding the required synthetic receipt schema fixed the tests. Production verification was not altered.
- Committed diff whitespace check passes; commit parent matches the authorized source; exactly the two requested code/test files changed; worktree clean.

The release-boundary tests stub plan governance only and use real reference hashing and detached release/review comparisons. Their valid synthetic path deliberately stops at the frozen-protocol gate. Runtime-binding negatives stop before runtime inspection. This is focused regression evidence, not full release/source/runtime/health acceptance. No broad historical suites, GPU/eval/provider calls, production bootstrap launch, or provenance reconstruction were run.

## Adjacent entrypoints

N36 bootstrap argument slicing, source command argument forwarding, supervisor forwarding, worker context handling, and healthcheck CLI preserve reference strings. The CPU receipt diagnostic also preserves its context string. No additional repair is needed on the inspected first-C0 forwarding path.

N32/N34/N35 runner `main()` functions contain the same path-resolution pattern. They are predecessor CLIs outside this N36 first-C0 path; N36 imports N32 helpers only. They remain unchanged. N36 contract `ref()` constructs new artifact references; it does not rebuild the supplied plan/release references, so artifact creation semantics remain unchanged.

## Remaining root gates

- Root source review/adoption of this candidate commit is pending and was not performed. Old source evidence remains bound to the previous commit.
- Root must determine and authorize prospective bindings for the adopted source: plan, root review, detached release, source/scientific-source inventories, native build, controller semantics, runtime and manifest closure must satisfy unchanged consumers. No binding refresh or old evidence rewrite was performed.
- The production bootstrap and full release/source/runtime checks must pass for the exact adopted source and actual process. These focused CPU tests do not replace runtime attestation, inventory verification, or provider/device readiness.
- N36R3 health readiness remains exact-bound to plan, health release, source commit, runtime, timestamps and durably charged resource events. Existing health evidence cannot be assumed valid for changed source or references. Root must resolve compatible evidence under separate authority; no health replay is authorized here.
- First-C0 remains pending: separately authorized launch, locked STOP/deadline/accounting/admission checks, and mandatory root G3 after first-C0 remain required. No scientific gate or threshold is changed or passed by this repair.

## Scope and provenance

The supplied authority and its hash-linked terminal reconciliation were read; the diagnosis hash matched. The prior launch failure was before reservation according to that reconciliation. No old plan, health, release, runtime, protocol, owner state or ledger was edited. No prohibited guidance file, credential file, or protected validation/formal result was read. No delegation or Superpowers use occurred. Explicit Arbor entrypoint/orchestrator/executor instructions were read solely for this continuation; the user's bounded repair scope controls.

Authority-reported retained totals remain 505 attempts and 75.53335346582918 GPU hours; these were not remeasured. Scientific score: null. Source adoption: not performed. First-C0 and mandatory root G3: pending.

The executor stops after this commit and report. This report grants no launch, health replay, binding refresh, adoption or scientific approval authority.
