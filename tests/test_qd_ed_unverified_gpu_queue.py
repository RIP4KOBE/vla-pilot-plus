import ast
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import qd_ed_final_runner as runner


def test_unprobed_gpu_accepted_only_for_explicit_queue_preparation():
    plan = {'egl_mapping_verified': False}
    runtime = {'cuda_egl_verified': False, 'metadata_mapping_verified': True,
               'gpu_mapping': {'physical_gpu': 2, 'egl_device_index': 1}}
    with pytest.raises(runner.GateError, match='GPU2/EGL mapping not verified'):
        runner.validate_gpu_readiness(plan, runtime)
    runner.validate_gpu_readiness(plan, runtime, allow_unverified_gpu=True)


@pytest.mark.parametrize('field,value', [('cuda_egl_verified', None),
    ('cuda_egl_verified', 'true'), ('metadata_mapping_verified', False)])
def test_queue_never_accepts_unknown_mapping_readiness(field, value):
    runtime = {'cuda_egl_verified': False, 'metadata_mapping_verified': True}
    runtime[field] = value
    with pytest.raises(runner.GateError, match='verified metadata'):
        runner.validate_gpu_readiness({'egl_mapping_verified': False}, runtime, allow_unverified_gpu=True)


def test_dispatch_and_post_probe_validation_keep_strict_default():
    root = Path(__file__).resolve().parents[1]
    tree = ast.parse((root/'scripts/qd_ed_final_runner.py').read_text())
    run = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run_plan')
    calls = [n for n in ast.walk(run) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Name) and n.func.id == 'validate_plan']
    assert len(calls) >= 2
    assert all('allow_unverified_gpu' not in {kw.arg for kw in call.keywords} for call in calls)
    tree = ast.parse((root/'scripts/qd_ed_available_gpu_queue.py').read_text())
    bind = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'bind_plan')
    calls = [n for n in ast.walk(bind) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute) and n.func.attr == 'validate_plan']
    final = next(call for call in calls if isinstance(call.args[0], ast.Name) and call.args[0].id == 'destination')
    assert 'allow_unverified_gpu' not in {kw.arg for kw in final.keywords}
