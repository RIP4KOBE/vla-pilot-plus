# Exact98-case invocation

Recorded command, not re-executed. Cwd: `/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n26_clean_output_rbf/conditional_implementation`. Preserve original fixtures; any future reproduction must use a new owned basetemp. No numerical36-case test selected.

```bash
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /home/hynx/miniconda3/envs/vla-pilot/bin/python -B - <<'PYTEST'
import sys,runpy
from pathlib import Path
w=Path.cwd();h=w.parent/'conditional-controller-cpu-v1'
sys.path[:0]=[str(w),str(w/'scripts'),str(w/'tests')]
runpy.run_path(str(h/'cpu_guard_v1.py'))
import pytest
args=['-q','-p','no:cacheprovider','--basetemp',str(h/'tmp/composition-regression-v1')]
args += ['tests/test_qd_ed_n26_logical.py::test_prospective_matrix_and_logical_gate_remain_disabled', 'tests/test_qd_ed_n26_logical.py::test_final_review_and_authority_close_new_provenance', 'tests/test_qd_ed_n26_controller.py::test_finite_future_budget_requires_exact_root_record', 'tests/test_qd_ed_n26_controller.py::test_per_dispatch_full_1840_local_and_protected_capacity', 'tests/test_qd_ed_n26_controller.py::test_n26_routing_and_exact_two_modes_default_controls', 'tests/test_qd_ed_n26_controller.py::test_admission_exact_prefix_and_only_complete_quad_futility', 'tests/test_qd_ed_n26_backend.py::test_fixed_native_proof_gates', 'tests/test_qd_ed_n26_backend.py::test_settled_once_proof_and_same_dev_source', 'tests/test_qd_ed_n26_backend.py::test_resource_admission_no_retry_and_capacity', 'tests/test_qd_ed_n26_recovery.py::test_real_runner_wrapper_charge_cleanup_and_same_cell', 'tests/test_qd_ed_n26_recovery.py::test_one_recovery_per_cell_two_total']
raise SystemExit(pytest.main(args))
PYTEST
```
