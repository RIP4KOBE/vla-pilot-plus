"""Reject different assets before writing machine configuration or contacting a service."""
from types import SimpleNamespace
import json
import sys

import pytest

from scripts import prepare_steering_assets, steering_model_assets, check_steering


def test_configure_refuses_changed_model_before_writing_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(prepare_steering_assets, 'verify_libero', lambda _: {'valid': True})
    monkeypatch.setattr(prepare_steering_assets, 'model_files', lambda *args: [])
    def reject(*args, **kwargs):
        raise steering_model_assets.ModelAssetsError('model bytes differ')
    monkeypatch.setattr(steering_model_assets, 'verify_model_assets', reject)
    args = SimpleNamespace(**{name: tmp_path / name for name in (
        'libero_root', 'rdt_checkpoint', 'text_encoder', 'vision_encoder',
        'torch_home', 'libero_config', 'output')}, gpu=2, egl_device_id=1,
        allocator_limit_gib=48, replace_config=False, hash_weights=False, report=None)
    with pytest.raises(steering_model_assets.ModelAssetsError, match='model bytes differ'):
        prepare_steering_assets.configure(args)
    assert not args.output.exists()
    assert not args.libero_config.exists()


def test_preflight_asset_failure_is_recorded_before_api_or_gpu(tmp_path, monkeypatch):
    destination = tmp_path / 'preflight'
    monkeypatch.setattr(sys, 'path', list(sys.path))
    monkeypatch.setattr(sys, 'argv', ['check_steering', '--local-config', 'unused',
                                    '--output-dir', str(destination), '--api', '--gpu'])
    monkeypatch.setattr(check_steering, 'load_local', lambda _: {})
    import os
    # main replaces the environment; preserve its original contents for this test.
    monkeypatch.setattr(os, 'environ', dict(os.environ))
    monkeypatch.setattr(check_steering, 'runtime_environment', lambda _: dict(os.environ, PYTHONPATH=''))
    def reject(*args, **kwargs):
        raise steering_model_assets.ModelAssetsError('model bytes differ')
    monkeypatch.setattr(steering_model_assets, 'verify_model_assets', reject)
    with pytest.raises(steering_model_assets.ModelAssetsError, match='model bytes differ'):
        check_steering.main()
    report = json.loads((destination / 'report.json').read_text())
    assert report['status'] == 'fail'
    assert report['error_type'] == 'ModelAssetsError'
    assert 'api' not in report and 'gpu' not in report
    assert not (destination / 'api_requests').exists()


def test_libero_loader_paths_must_match_content_verified_tree(tmp_path):
    root = tmp_path / 'libero'
    benchmark = root / 'libero/libero'
    path = tmp_path / 'config.yaml'
    bindings = dict(benchmark_root=str(benchmark), assets=str(benchmark/'assets'),
                    bddl_files=str(benchmark/'bddl_files'), init_states=str(benchmark/'init_files'))
    path.write_text(json.dumps(bindings))
    local = dict(libero_root=str(root), libero_config=str(tmp_path))
    report = prepare_steering_assets.verify_libero_paths(local)
    assert report['valid'] and report['bindings'] == bindings
    bindings['bddl_files'] = str(tmp_path/'different-tree/bddl_files')
    path.write_text(json.dumps(bindings))
    with pytest.raises(ValueError, match='bddl_files does not point'):
        prepare_steering_assets.verify_libero_paths(local)
