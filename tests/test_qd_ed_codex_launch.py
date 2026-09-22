"""The managed-login launcher never reads credentials or launches arbitrary commands."""
import importlib.util
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
SPEC = importlib.util.spec_from_file_location('qd_ed_codex_launch',
    Path(__file__).resolve().parents[1] / 'scripts/qd_ed_codex_launch.py')
launch = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(launch)


@pytest.mark.parametrize('command,extra', [
    ('validate-plan', ['--allow-unfrozen']),
    ('print-command', ['--split', 'dev', '--iteration', 'baseline', '--allow-unfrozen']),
    ('run', ['--split', 'dev', '--iteration', 'baseline', '--episode-key', 'a']),
    ('reconcile-ledger', ['--attempt-id', 'owned'])])
def test_launcher_verifies_inputs_and_only_execs_owned_runner(tmp_path, monkeypatch, command, extra):
    manifest = tmp_path / 'runtime.json'; plan = tmp_path / 'plan.json'
    calls = []
    runtime = {'frozen_stage_provider': {'backend': 'codex_cli'}}
    def validate(*args, **kwargs):
        calls.append(('validate', args, kwargs))
        return {'runtime_manifest_path': str(manifest)}, {}, runtime
    monkeypatch.setattr(launch.runner, 'validate_plan', validate)
    monkeypatch.setattr(launch.runner, 'child_environment', lambda value: {'HOME': '/account', 'CUDA_VISIBLE_DEVICES': '7'})
    monkeypatch.setattr(launch.runner, 'verify_provider', lambda *a, **kw: calls.append(('verify', a, kw)))
    monkeypatch.setattr(launch.os, 'execve', lambda *args: calls.append(('exec', args)))
    assert launch.main(['--runtime-manifest', str(manifest), command, '--plan', str(plan), *extra]) == 0
    assert [call[0] for call in calls] == ['validate', 'verify', 'exec']
    executable, argv, env = calls[-1][1]
    assert executable == str(launch.PYTHON)
    assert argv == [executable, str(launch.RUNNER), command, '--plan', str(plan), *extra]
    assert env == {'HOME': '/account', 'CUDA_VISIBLE_DEVICES': '7'}


def test_launcher_manifest_mismatch_and_invalid_inputs_do_not_authenticate(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(launch.runner, 'validate_plan', lambda *a, **kw:
                        ({'runtime_manifest_path': str(tmp_path / 'different')}, {}, {}))
    monkeypatch.setattr(launch.runner, 'verify_provider', lambda *a, **kw: pytest.fail('must not query login'))
    assert launch.main(['--runtime-manifest', str(tmp_path / 'chosen'), 'validate-plan', '--allow-unfrozen']) == 2
    assert 'refused' in capsys.readouterr().err
    with pytest.raises(SystemExit):
        launch.main(['--runtime-manifest', str(tmp_path / 'chosen'), '/bin/sh'])


def test_launcher_error_messages_do_not_echo_arbitrary_account_values(tmp_path, monkeypatch, capsys):
    def invalid(*a, **kw):
        raise launch.runner.GateError('unit-test-placeholder-account-value')
    monkeypatch.setattr(launch.runner, 'validate_plan', invalid)
    assert launch.main(['--runtime-manifest', str(tmp_path / 'runtime'), 'validate-plan']) == 2
    assert 'placeholder' not in capsys.readouterr().err
