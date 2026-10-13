import json
from types import SimpleNamespace

import pytest

from utils.mujoco_phase_diagnostics import install


def test_observer_preserves_call_count_arguments_return_and_exception(tmp_path):
    calls = []
    token = object()
    error = RuntimeError('original error')
    def render(*args, **kwargs):
        calls.append((args, kwargs))
        return token
    def read(*args, **kwargs):
        raise error
    module = SimpleNamespace(mjr_render=render, mjr_readPixels=read)
    assert install(tmp_path, modules={'mujoco': module})
    assert module.mjr_render(token, con=token) is token
    assert calls == [((token,), {'con': token})]
    with pytest.raises(RuntimeError) as caught:
        module.mjr_readPixels(token)
    assert caught.value is error
    records = [json.loads(line) for line in (tmp_path/'mujoco_phase_timing.jsonl').read_text().splitlines()]
    assert [(r['name'], r['event']) for r in records] == [
        ('mjr_render','enter'), ('mjr_render','exit'), ('mjr_readPixels','enter'), ('mjr_readPixels','exception')]
    assert all('args' not in r and 'kwargs' not in r and 'error' not in r for r in records)


def test_reinstallation_does_not_duplicate_calls_or_logs(tmp_path):
    module = SimpleNamespace(mjr_render=lambda: 42)
    install(tmp_path, modules={'mujoco': module})
    wrapped = module.mjr_render
    install(tmp_path, modules={'mujoco': module})
    assert module.mjr_render is wrapped and module.mjr_render() == 42
    assert len((tmp_path/'mujoco_phase_timing.jsonl').read_text().splitlines()) == 2


def test_write_failure_does_not_change_original_operation(tmp_path):
    occupied = tmp_path/'file'; occupied.write_text('data')
    module = SimpleNamespace(mjr_render=lambda: 7)
    install(occupied, modules={'mujoco': module})
    assert module.mjr_render() == 7


def test_no_simulator_import_or_output_when_module_is_absent(tmp_path):
    assert not install(tmp_path/'absent', modules={})
    assert not (tmp_path/'absent').exists()
