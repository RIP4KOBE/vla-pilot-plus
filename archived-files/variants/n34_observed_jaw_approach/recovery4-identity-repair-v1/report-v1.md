N34R4 identity repair completed on `codex/n34-production-integration`.

Base: `38a723c303e1a69993b6ec1c97bdc26195e44a56` (clean at start).
Commit: `b9f20b8a25766138843b691136ce143566567d3c` (clean after commit).
Scientific implementation remains `71ffff1a0f70d9874b309db9ef1843c02bf17ebf`.

The strict contract now requires all 30 fresh `n34r4_dev_tXX_PROFILE_20261008` keys with lowercase profiles and cohort `N34R4_OBSERVED_JAW_APPROACH_DEV_20261008`. Task0 C0 explicitly replaces `n34r3_dev_t00_c0_20261008`, bound to turn644's exact terminal-closure path and SHA-256 from authority-v1.json. The mapping remains 1 recovery / 9 baseline / 20 development with zero automatic retries.

All four invalid generations remain required history with their original charges, unknowns, and terminal records. N34R3's computed C0 remains INVALID for missing torch.utils.serialization runtime coverage and cannot enter the fresh matrix. Frozen tasks, seeds, scientific behavior, thresholds, promotion/futility, caps, and strict audits are unchanged.

Changed files:

- `scripts/qd_ed_n34_contract.py`
- `scripts/qd_ed_n34_release.py`
- `tests/test_n34_lifecycle.py`
- `tests/test_n34_recovery_identity.py`
- `tests/test_n34_release_boundary.py`

Validation: **230 focused CPU tests passed in 2.38s**. Coverage includes all 30 stale N34R3 rows, stale parent terminal/context/closure bindings, replacement and bucket enforcement, each prior invalid generation, retained charges and unknowns, historical resource costs, every fresh admission, frozen seed checks, and unchanged promotion and complete-valid-triple futility. Source comparison confirms only the specified identity/provenance/history substitutions; `git diff --check` passed.

Test command (PYTHONDONTWRITEBYTECODE=1; TMPDIR and pytest basetemp inside this output directory):

```sh
python -m pytest -q -p no:cacheprovider --basetemp=/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n34_observed_jaw_approach/recovery4-identity-repair-v1/pytest-identity tests/test_n34_recovery_identity.py tests/test_n34_release_boundary.py::test_stale_n34r3_release_matrix_rejected tests/test_n34_lifecycle.py::test_generic_historical_charges_and_health_preserved tests/test_n34_lifecycle.py::test_unsettled_or_unknown_never_zero_cost tests/test_n34_lifecycle.py::test_admission_boundaries tests/test_n34_lifecycle.py::test_full_episode_weekly_and_protected_seconds tests/test_n34_lifecycle.py::test_explicit_caps_do_not_inherit_old_private_budget
```

Detailed results: `implementation-result-v1.json`, `test-results-v1.json`, `focused-tests-v1.log`, and `scope-verification-v1.json`.

No GPU/provider experiment calls, subagents, protected guidance/results access, owning state/ledger writes, APPROVED release generation, runtime preparation, or runtime inventory edits occurred. Tests use synthetic fixtures; they do not certify current owning balances or release authority. Historical source remains in Git. The reviewed turn645 runtime preparation retains OLD identities and is untouched; root separately reviews/adopts this commit and regenerates the runtime composition.
