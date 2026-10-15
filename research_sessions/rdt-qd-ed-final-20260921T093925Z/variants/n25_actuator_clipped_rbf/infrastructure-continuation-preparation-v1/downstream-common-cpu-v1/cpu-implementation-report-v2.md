# Conditional common evidence adapter — CPU delivery v2

Status: **CPU preparation complete; no execution or downstream authorization.** Source is clean `ff285373cc69a898cb1f5e6ed9cbbfe370a2972a` on `codex/n25-continuation-downstream-evidence`, based on `6f796358aa84d53e9c8a04859f7d19352c9db7fe`. Protocol was precommitted as `b4e59d0`; initial implementation `db1f020` and every prior artifact are preserved. Scientific score is Unknown; this change performs metadata verification only.

The adapter reconstructs the logical Dev evidence from immutable original/continuation metadata, independently checks all costs and unknown usage, and binds the independent terminal review, original 257-file source, continuation 271-file source, exact historical administrative reverse bridge and original settled resource proof. It accepts only complete valid promotion/rejection or valid whole-quad numerical futility. Original INVALID, any new invalidity, status disagreement, late evidence, live ownership, or changed matching journal blocks creation. Every output has `allow_validation=false`, `allow_n26=false`, `gpu_authorized=false`.

The final source manifest has 276 entries: all 271 base files are byte-identical and exactly five files are added (adapter, two synthetic test/fixture files, protocol, contract). No W, validation, N26, science, controller, provider, budget or state changes occurred. The v2 follow-up binds the transitive original N25 contract bytes and same module identity plus owning paths of contract, reference and UUID helpers. No original helper was edited.

68 distinct synthetic cases have passing evidence across six clean guarded runs; this is not a single full-suite run at final HEAD. The root-requested final check was 10 passed, 58 deselected, 16.38 seconds; it covered seven new drift/shadow negatives and three positive disposition/proof paths. All six accepted logs have zero guard denials, CUDA uninitialized, two intra/inter-op CPU threads. No actual history, protected content, tensors, model, API or simulator was read or executed.

One additional startup run had 10 passing assertions but **failed the isolation check**: pytest plugin autoload attempted to read a historical worktree's `lerobot.egg-info/entry_points.txt` twice. The unchanged guard blocked both before content access. Its original log `transitive-v2.log` remains, excluded from clean evidence. The only rerun change was `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`; `transitive-final-v2.log` is clean. No paths were newly allowed. This was a test-launch configuration defect, not a scientific result or a passed isolation run.

The implementation contract specifies the exact 15 input refs, bounded reader (512 files, 16 MiB/file, 128 MiB total), source-object allowlist, c.SEAL/owning-study dependency, process checks and deferred CLI. Four templates remain disabled and unresolved. Neither real terminal refs nor an authority are manufactured here. Metadata/native evidence digests rely on prior metered audits and explicit root extraction attestations; this is not a fresh numerical audit. Old six unknown-token calls and unmeasured failed-attempt native/safety gates remain Unknown.

Root-generated Dev/resource projections may be prepared only after immutable terminal plus independent review. Underlying complete-ledger/collector refs are never followed. The pure `check_current_matching_events` hook must be called by future admission using its already-read, correctly filtered current events; unrelated ledger appends do not invalidate historical evidence. Completeness of root extraction remains an explicit trust boundary. The common adapter adds no runner hook, validation gate, N26 gate, budget decision or GPU release.

Root next steps are to review this delivery, retain active 6f until terminal review, and only then separately authorize integration and a closed metadata input manifest/projections. Run the adapter from the approved owning study under existing ownership locks; ensure the operational execution directory exists before opening its lock. CLI scripts automatically include `scripts/`; root import helpers must provide that path explicitly. No controller is resumed by this adapter. Later V25/N26 integration requires separate source review and mutually exclusive gates, plus current capacity/freshness checks.

Reproducible focused test command (use a new synthetic basetemp name; no need to repeat the already passing check):

```bash
cd /home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n25_actuator_clipped_rbf/downstream_common_implementation
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /home/hynx/miniconda3/envs/vla-pilot/bin/python -B - <<'PYTEST'
import sys, runpy
from pathlib import Path
w = Path.cwd()
h = w.parent / 'infrastructure-continuation-preparation-v1/downstream-common-cpu-v1'
sys.path[:0] = [str(w), str(w / 'scripts'), str(w / 'tests')]
runpy.run_path(str(h / 'cpu_guard_v1.py'))
import pytest
raise SystemExit(pytest.main(['-q', '-p', 'no:cacheprovider', '--basetemp', str(h / 'tmp/root-review-new'), 'tests/test_qd_ed_n25_cont_downstream.py', '-k', 'transitive_proof or three_valid_non_authorizing']))
PYTEST
```

No actual metadata execution has been performed. Actual historical Git-object verification inside the adapter, real metadata schema acceptance and future admission integration remain root review work; synthetic tests use an explicit fake Git reader. Source-only packaging separately verified all current committed bytes and unchanged base files.
