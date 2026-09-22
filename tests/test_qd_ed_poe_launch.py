"""CPU-only launcher tests: all credentials are temporary placeholders."""
import importlib.util
import json
from pathlib import Path

import pytest


SPEC = importlib.util.spec_from_file_location(
    'qd_ed_poe_launch', Path(__file__).resolve().parents[1] / 'scripts/qd_ed_poe_launch.py')
launch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launch)


def manifest(source='OPENAI_API_KEY', **updates):
    return dict(provider_ready=True, frozen_stage_provider={
        'base_url': launch.POE_ENDPOINT, 'model': launch.STAGE_MODEL,
        'credential_env_name': source}, **updates)


def credentials(tmp_path, extra=''):
    path = tmp_path / 'test.env'
    path.write_text('OPENAI_BASE_URL="https://api.poe.com/v1"\n'
                    'export OPENAI_API_KEY="placeholder-openai" # test only\n' + extra)
    return path


def fixture_files(tmp_path):
    env_file = credentials(tmp_path)
    runtime = tmp_path / 'runtime.json'
    runtime.write_text(json.dumps(manifest()))
    plan = tmp_path / 'plan.json'
    plan.write_text(json.dumps({'runtime_manifest_path': str(runtime)}))
    return env_file, runtime, plan


def test_missing_google_key_removes_inherited_provider_and_preserves_other_environment(tmp_path):
    env = launch.bind_environment(credentials(tmp_path), manifest(), {
        'OPENAI_BASE_URL': 'https://unrelated.test/v1', 'OPENAI_API_KEY': 'REDACTED',
        'GOOGLE_API_KEY': 'REDACTED', 'PATH': '/fixed/path'})
    assert env == {'OPENAI_BASE_URL': launch.POE_ENDPOINT, 'OPENAI_API_KEY': 'placeholder-openai',
                   'PATH': '/fixed/path'}


def test_file_and_inherited_google_keys_are_always_excluded(tmp_path):
    path = credentials(tmp_path, "GOOGLE_API_KEY='placeholder-google'\n")
    env = launch.bind_environment(path, manifest(), {'GOOGLE_API_KEY': 'REDACTED'})
    assert 'GOOGLE_API_KEY' not in env
    assert env['OPENAI_API_KEY'] == 'placeholder-openai'
    with pytest.raises(launch.BindingError, match='Poe OpenAI credential'):
        launch.bind_environment(path, manifest('GOOGLE_API_KEY'), {})
    path = credentials(tmp_path, 'GOOGLE_API_KEY= # deliberately empty\n')
    assert 'GOOGLE_API_KEY' not in launch.bind_environment(path, manifest(), {'GOOGLE_API_KEY': 'stale'})


@pytest.mark.parametrize('url', [
    'https://unrelated.test/v1', 'http://api.poe.com/v1', 'https://api.poe.com/v1/',
    'https://api.poe.com:443/v1', 'https://api.poe.com/v1?x=y',
    'https://api.poe.com@unrelated.test/v1', 'https://api.poe.com/v2'])
def test_rejects_any_endpoint_change(tmp_path, url):
    path = tmp_path / 'test.env'
    path.write_text(f'OPENAI_BASE_URL={url}\nOPENAI_API_KEY=placeholder\n')
    with pytest.raises(launch.BindingError, match='Poe HTTPS endpoint'):
        launch.bind_environment(path, manifest(), {})


@pytest.mark.parametrize('change', ['not_ready', 'endpoint', 'model', 'source', 'missing_credential'])
def test_manifest_gate_and_missing_credential(tmp_path, change):
    path = credentials(tmp_path)
    public = manifest()
    if change == 'not_ready':
        public['provider_ready'] = False
    elif change == 'endpoint':
        public['frozen_stage_provider']['base_url'] = 'https://unrelated.test/v1'
    elif change == 'model':
        public['frozen_stage_provider']['model'] = 'different-model'
    elif change == 'source':
        public['frozen_stage_provider']['credential_env_name'] = 'GOOGLE_API_KEY'
    else:
        path.write_text('OPENAI_BASE_URL=https://api.poe.com/v1\n')
    with pytest.raises(launch.BindingError):
        launch.bind_environment(path, public, {'OPENAI_API_KEY': 'REDACTED'})


def test_static_values_never_expand_or_execute(tmp_path):
    path = tmp_path / 'test.env'
    path.write_text("OPENAI_API_KEY='placeholder-$OTHER-$(touch never-run)'\nIGNORED=other\n")
    values = launch.read_provider_variables(path)
    assert values['OPENAI_API_KEY'] == 'placeholder-$OTHER-$(touch never-run)'
    assert 'IGNORED' not in values
    assert launch.dotenv_value('placeholder#literal # comment') == 'placeholder#literal'


def test_unrelated_google_field_is_not_parsed_or_used(tmp_path):
    path = credentials(tmp_path, 'GOOGLE_API_KEY="unclosed-unrelated-placeholder\n')
    values = launch.read_provider_variables(path)
    assert set(values) == {'OPENAI_API_KEY', 'OPENAI_BASE_URL'}
    env = launch.bind_environment(path, manifest(), {'GOOGLE_API_KEY': 'REDACTED'})
    assert 'GOOGLE_API_KEY' not in env


@pytest.mark.parametrize('bad', ['OPENAI_API_KEY="placeholder-unclosed',
                                'OPENAI_API_KEY="placeholder" invalid',
                                'OPENAI_API_KEY=placeholder-duplicate'])
def test_bad_credentials_never_appear_in_diagnostics(tmp_path, monkeypatch, capsys, bad):
    path, runtime, plan = fixture_files(tmp_path)
    if 'duplicate' not in bad:
        path.write_text(f'OPENAI_BASE_URL={launch.POE_ENDPOINT}\n{bad}\n')
    else:
        with path.open('a') as stream:
            stream.write(bad + '\n')
    def forbidden(*args):
        pytest.fail('Rejected binding must not exec')
    monkeypatch.setattr(launch.os, 'execve', forbidden)
    assert launch.main(['--credentials-file', str(path), '--runtime-manifest', str(runtime),
                        'validate-plan', '--plan', str(plan)]) == 2
    output = capsys.readouterr()
    assert not output.out and 'placeholder' not in output.err


@pytest.mark.parametrize('command,extra', [
    ('validate-plan', ['--allow-unfrozen']),
    ('print-command', ['--split', 'dev', '--iteration', 'baseline', '--allow-unfrozen']),
    ('run', ['--split', 'dev', '--iteration', 'baseline', '--episode-key', 'a', '--episode-key', 'b']),
    ('reconcile-ledger', ['--attempt-id', 'owned-attempt'])])
def test_only_fixed_runner_is_execed_with_structured_arguments(tmp_path, monkeypatch, capsys, command, extra):
    path, runtime, plan = fixture_files(tmp_path)
    seen = []
    monkeypatch.setattr(launch.os, 'execve', lambda *args: seen.append(args))
    monkeypatch.setenv('GOOGLE_API_KEY', 'stale-google')
    assert launch.main(['--credentials-file', str(path), '--runtime-manifest', str(runtime),
                        command, '--plan', str(plan), *extra]) == 0
    executable, argv, env = seen[0]
    assert executable == '/home/hynx/miniconda3/envs/vla-pilot/bin/python'
    assert argv == [executable, str(launch.RUNNER), command, '--plan', str(plan), *extra]
    assert env['OPENAI_API_KEY'] == 'placeholder-openai' and 'GOOGLE_API_KEY' not in env
    assert not capsys.readouterr().out
    assert all('placeholder' not in arg for arg in argv)


def test_mismatched_manifest_or_arbitrary_command_cannot_exec(tmp_path, monkeypatch, capsys):
    path, runtime, plan = fixture_files(tmp_path)
    other = tmp_path / 'other.json'
    other.write_text(runtime.read_text())
    seen = []
    monkeypatch.setattr(launch.os, 'execve', lambda *args: seen.append(args))
    common = ['--credentials-file', str(path), '--runtime-manifest', str(other)]
    assert launch.main([*common, 'validate-plan', '--plan', str(plan)]) == 2
    with pytest.raises(SystemExit):
        launch.main([*common, '/bin/sh', '-c', 'true'])
    assert not seen and 'placeholder' not in capsys.readouterr().err


def test_exec_error_message_does_not_render_environment(tmp_path, monkeypatch, capsys):
    path, runtime, plan = fixture_files(tmp_path)
    def error(*args):
        raise OSError('placeholder-openai must never escape')
    monkeypatch.setattr(launch.os, 'execve', error)
    assert launch.main(['--credentials-file', str(path), '--runtime-manifest', str(runtime),
                        'validate-plan', '--plan', str(plan)]) == 2
    assert 'placeholder' not in capsys.readouterr().err
