# N34 patch source closure repair — node15.4

Commit: `fac4719a3acd5e6ba0ef8d2d0033d7ccfff39c45`
Base: `9f817b7c6b7c3861f4789a2d2ad1ab65af7a66a4`
Status: implemented, focused CPU tests passed; pending root review/adoption.

Changed files:

- `scripts/qd_ed_n34_bridge.py`: add recursive `patches/*.py` inventory from Git HEAD and disk. HEAD preserves missing committed paths; disk exposes untracked/staged additions for rejection by the existing committed-byte checks.
- `tests/test_n34_patch_source.py`: 19 focused cases with temporary local Git repositories and inert module origins. Covers package/light/nested Python inventory, non-Python exclusion, valid record/loaded-origin roundtrip, missing/modified/staged/linked bytes, untracked/staged additions, rehashed omissions, and post-record loaded-byte changes.

Validation:

```text
/home/hynx/miniconda3/envs/vla-pilot/bin/python -B -m pytest -q -p no:cacheprovider tests/test_n34_patch_source.py tests/test_n34_dependency_source.py
45 passed in 12.59s (exit 0)
```

The run includes 19 new patch cases and 26 existing dependency source cases. `git diff --cached --check` passed. Post-commit worktree is clean; the commit changes exactly the two files above.

No changes to scientific files, core, patch bytes, thresholds, source/runtime attestors, release gates, or native/reference audits. No driver/coordinator locks, research-state/ledger edits, credentials access, additional executors, GPU execution, model loads, or episodes. The prohibited design document was not opened.

Limitations:

- CPU local Git fixtures and inert module origins only; no GPU, model loading, or episodes.
- The full prospective runtime import probe was not rerun; root owns runtime inventory review and adoption.
- Tests isolate unrelated source inventories; they do not establish full production runtime readiness.
- No scientific score, release claim, or release authorization is provided.
