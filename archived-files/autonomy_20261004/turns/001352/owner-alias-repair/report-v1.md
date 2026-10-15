# Node 15.6 owner alias repair

Committed on `exp/n36r3-generated-import-001299` in the existing isolated worktree. No merge to owner.

- Source before: `bee9f6a4703e9d5d802d6b8c7950b69beefac4c0`
- Source after: `21fc93e5667a83520401282d4ba8e945f954f99b`
- Changed paths: `scripts/qd_ed_n36_release.py`, `tests/test_n36r3_owner_alias.py`
- Post-commit worktree: clean.

Previously, N36R3 required literal `state.worktree == owner`. It now requires exact `canonical_worktree == owner` for both accepted spellings, and admits only the canonical owner or `/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z`. The historical alias must pass strict resolution to owner, directory and samefile checks on every call. Filesystem errors fail closed. All other state gates and lexical plan routing remain in place. No state is rewritten.

The supplied alias evidence digest was verified. A fresh metadata-only check confirmed strict resolution to `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/study_worktree` and samefile identity. Real state contents were not opened.

## Validation

`PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p no:cacheprovider tests/test_n36r3_owner_alias.py`

Result: **44 passed in 1.49s** (exit 0). Tests use temporary filesystem fixtures and in-memory state, with no real state/journal writes. Coverage includes both positive spellings, metadata mismatches, arbitrary aliases, missing/dangling/retargeted aliases, loops, file substitution, filesystem failures, unchanged lexical routing and remaining admission gates. `git diff --check` and staged diff checks passed. Existing accepted tests stand; no broad rerun occurred.

## Review implications and remaining work

This is an engineering repair, with no scientific score or fabricated scientific evidence. The source commit changed, so **fresh B5 review and source/runtime binding refresh are still required** before progression. Refresh exact source inventories/hashes, preparation/review inputs, runtime/runtime-closure bindings and downstream source-bound evidence. This executor has not granted release authority or performed source/accounting adoption, release generation, or runtime/GPU validation.

Canonical metadata is now mandatory for both N36R3 spellings. Older synthetic admission fixtures lacking that metadata need separate alignment before a future wider rerun; those fixtures were not changed or rerun. The identity check observes the filesystem at validation time and does not lock against later external retargeting.

No science/protocol edits, GPU/provider calls, credential reads, protected evaluation reads, prohibited design document reads, subagents, coordinator lease, or driver lock. Reports are the only requested outputs written outside the isolated worktree.

## Exact production source diff

```diff
diff --git a/scripts/qd_ed_n36_release.py b/scripts/qd_ed_n36_release.py
index 8068109..1e066cc 100644
--- a/scripts/qd_ed_n36_release.py
+++ b/scripts/qd_ed_n36_release.py
@@ -9,6 +9,7 @@ from scripts import qd_ed_final_runner as r, qd_ed_n23_worker as w
 from scripts import qd_ed_n36_contract as c, qd_ed_n36_bridge as b
 
 COORDINATOR_END = '2026-10-11T11:13:13Z'
+N36R3_OWNER_ALIAS = '/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z'
 
 
 def validate_plan(plan):
@@ -282,7 +283,19 @@ def validate_state(plan, authority, state):
     """Shared owning state gate for independent health and episode transactions."""
     if c.cohort(plan) == c.DRAFT_N36R3_COHORT:
         from scripts.qd_ed_n36r3_admission import owner_root
-        w.require(state.get('worktree') == str(owner_root(plan)), 'N36R3 owning state worktree differs')
+        owner = owner_root(plan)
+        lexical = state.get('worktree')
+        w.require(state.get('canonical_worktree') == str(owner), 'N36R3 owning state canonical worktree differs')
+        w.require(lexical in (str(owner), N36R3_OWNER_ALIAS), 'N36R3 owning state worktree differs')
+        if lexical == N36R3_OWNER_ALIAS:
+            # Admit only the historical spelling, without rewriting state or routing.
+            # Recheck live identity each time; cached alias evidence is not authority.
+            alias = Path(lexical)
+            try:
+                matches = alias.resolve(strict=True) == owner and alias.is_dir() and alias.samefile(owner)
+            except (OSError, RuntimeError):
+                matches = False
+            w.require(matches, 'N36R3 owning state alias identity differs')
     caps, budget = authority['caps'], state['budget']
     validate_caps(caps)
     w.require(state.get('n36_budget_authority') == plan['authority'] and r.authorized_gpu(state) == 7
```

Per-file before/after SHA-256 values and structured evidence are in `report-v1.json`.
