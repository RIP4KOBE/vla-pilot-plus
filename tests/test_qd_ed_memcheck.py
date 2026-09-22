import copy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import qd_ed_final_runner as runner


def contract(tmp_path, monkeypatch):
    folder = tmp_path/'tools'; folder.mkdir()
    tool = folder/'compute-sanitizer'; tool.write_bytes(b'fake executable; never run')
    (folder/'injection.so').write_bytes(b'fake library; never loaded')
    monkeypatch.setattr(runner, 'MEMCHECK_TOOL', tool)
    plan = {'cuda_memcheck': {'tool_path': str(tool), 'files': [
        {'path': str(p), 'sha256': runner.digest(p)} for p in folder.iterdir()]},
        'diagnostic_scope': {'kind': 'cuda_memcheck', 'online_algorithm_comparison': False},
        'episodes': [{'split': 'dev', 'budget_bucket': 'development',
                      'iteration': 'GPU5_CUDA_MEMCHECK_C0', 'profile': 'C0', 'timeout_seconds': 600}]}
    return plan, tool


def test_default_command_untouched(tmp_path):
    command = ['python', 'main.py', 'task=a b']
    assert runner.instrument_command(command, {}, tmp_path) is command


def test_fixed_memcheck_wrapper_preserves_original_arguments(tmp_path, monkeypatch):
    plan, tool = contract(tmp_path, monkeypatch)
    command = ['python', 'main.py', 'task=a b']
    actual = runner.instrument_command(command, plan, tmp_path)
    assert actual == [str(tool), '--tool', 'memcheck', '--target-processes', 'application-only',
                      '--error-exitcode', '86', '--log-file', str(tmp_path/'cuda-memcheck.log'), *command]


@pytest.mark.parametrize('change', [
    {'split': 'formal'}, {'budget_bucket': 'recovery'}, {'retry_of': 'failed'},
    {'iteration': 'N1R'}, {'timeout_seconds': 601}, {'timeout_seconds': True}, {'profile': 'N1'}])
def test_memcheck_cannot_enter_scientific_or_unbounded_conditions(tmp_path, monkeypatch, change):
    plan, _ = contract(tmp_path, monkeypatch); plan['episodes'][0].update(change)
    with pytest.raises(runner.GateError, match='bounded development'):
        runner.validate_memcheck(plan)


def test_tool_or_injection_change_rejected(tmp_path, monkeypatch):
    plan, tool = contract(tmp_path, monkeypatch)
    (tool.parent/'injection.so').write_bytes(b'changed')
    with pytest.raises(runner.GateError, match='frozen file changed'):
        runner.validate_memcheck(plan)


def test_missing_library_and_arbitrary_tool_rejected(tmp_path, monkeypatch):
    plan, tool = contract(tmp_path, monkeypatch)
    bad = copy.deepcopy(plan); bad['cuda_memcheck']['files'].pop()
    with pytest.raises(runner.GateError, match='fingerprint set'):
        runner.validate_memcheck(bad)
    bad = copy.deepcopy(plan); bad['cuda_memcheck']['tool_path'] = '/tmp/arbitrary'
    with pytest.raises(runner.GateError, match='unexpected CUDA'):
        runner.validate_memcheck(bad)


def test_blocking_memcheck_is_distinct_diagnostic_condition(tmp_path, monkeypatch):
    plan, tool = contract(tmp_path, monkeypatch)
    plan['cuda_memcheck']['force_blocking_launches'] = True
    with pytest.raises(runner.GateError, match='bounded development'):
        runner.validate_memcheck(plan)
    plan['episodes'][0]['iteration'] = 'GPU2_CUDA_MEMCHECK_BLOCKING_C0'
    command = ['python', 'main.py', 'task=a b']
    assert runner.instrument_command(command, plan, tmp_path) == [
        str(tool), '--tool', 'memcheck', '--target-processes', 'application-only',
        '--error-exitcode', '86', '--force-blocking-launches',
        '--log-file', str(tmp_path/'cuda-memcheck.log'), *command]
    plan['cuda_memcheck']['force_blocking_launches'] = False
    with pytest.raises(runner.GateError, match='bounded development'):
        runner.validate_memcheck(plan)


@pytest.mark.parametrize('value', ['yes', 1, None, ['--suppressions', '/tmp/ignore']])
def test_blocking_option_rejects_nonboolean_values(tmp_path, monkeypatch, value):
    plan, _ = contract(tmp_path, monkeypatch)
    plan['cuda_memcheck']['force_blocking_launches'] = value
    with pytest.raises(runner.GateError, match='must be boolean'):
        runner.validate_memcheck(plan)


def test_arbitrary_memcheck_flags_rejected(tmp_path, monkeypatch):
    plan, _ = contract(tmp_path, monkeypatch)
    plan['cuda_memcheck']['extra_args'] = ['--report-api-errors', 'no']
    with pytest.raises(runner.GateError, match='invalid CUDA memcheck contract'):
        runner.validate_memcheck(plan)
