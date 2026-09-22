"""CPU checks for task cache identity and frozen reward preservation."""
import ast
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('qd_ed_runtime_setup', ROOT / 'scripts/qd_ed_runtime_setup.py')
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


def validator():
    # Extract the pure helper to avoid importing main's simulator dependencies.
    tree = ast.parse((ROOT / 'main.py').read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_validate_task_cache_identity')
    namespace = {}
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<task-cache-validator>', 'exec'), namespace)
    return namespace[node.name]


def identity():
    return {'task_id': 7, 'expected_target_object': 'milk_1_main',
            'expected_basket_object': 'basket_1_main', 'target_description': 'milk'}


@pytest.mark.parametrize('task_id,mapping', [
    (6, {0: 'milk_1_main', 1: 'basket_1_main'}),
    (7, {0: 'alphabet_soup_1_main', 1: 'basket_1_main'}),
    (7, {0: 'milk_1_main', 1: 'other_object'}),
])
def test_identity_rejects_wrong_task_target_or_missing_basket(task_id, mapping):
    with pytest.raises(ValueError):
        validator()({'qd_ed_task_identity': identity()}, task_id, mapping)


def test_identity_allows_multiple_target_keypoints_and_nonfixed_basket_index():
    mapping = {0: 'milk_1_main', 1: 'milk_1_main', 2: 'basket_1_main', 3: 'basket_1_main'}
    before = dict(mapping)
    validator()({'qd_ed_task_identity': identity()}, 7, mapping)
    assert mapping == before


def test_cache_repair_keeps_canonical_reward_bytes_and_binds_only_description(tmp_path):
    canonical = tmp_path / 'canonical'
    authentic = tmp_path / 'authentic'
    canonical.mkdir()
    authentic.mkdir()
    rewards = {'stage1_guidance.txt': b'def stage1_guidance(k, a):\n    return -a.sum()\n',
               'stage2_guidance.txt': b'def stage2_guidance(k, a):\n    return 0\n'}
    for name, content in rewards.items():
        (canonical / name).write_bytes(content)
    (canonical / 'output_raw.txt').write_text('# Stage 1: Grasp alphabet soup can (keypoint 0).\n# Stage 2: Move alphabet soup can to basket (keypoint 1). No guidance needed.\n# Other frozen content\n')
    (authentic / 'metadata.json').write_text(json.dumps({'key_points_objects_map': {'0': 'milk_1_main'}, 'num_stages': 2}))
    (authentic / 'output_raw.txt').write_text('historical milk guidance')
    (authentic / 'prompt.txt').write_text('historical prompt')
    (authentic / 'query_img.png').write_bytes(b'example-image')
    target = tmp_path / 'owned'
    setup.prepare_task_cache(authentic, canonical, target, identity())
    assert all((target / name).read_bytes() == content for name, content in rewards.items())
    output = (target / 'output_raw.txt').read_text()
    assert 'Grasp milk (keypoint 0)' in output
    assert 'basket (basket keypoints in the current mapping)' in output
    assert output.endswith('# Other frozen content\n')
    assert json.loads((target / 'metadata.json').read_text())['qd_ed_task_identity']['task_id'] == 7


def test_cache_refuses_wrong_authentic_identity(tmp_path):
    source = tmp_path / 'wrong'
    source.mkdir()
    (source / 'metadata.json').write_text(json.dumps({'key_points_objects_map': {'0': 'alphabet_soup_1_main'}}))
    with pytest.raises(ValueError, match='does not match'):
        setup.prepare_task_cache(source, source, tmp_path / 'output', identity())
    assert not (tmp_path / 'output').exists()


def test_manifest_detects_post_freeze_tampering(tmp_path):
    path = tmp_path / 'cache'
    path.write_text('frozen')
    manifest = {'files': [setup.fingerprint(path)]}
    setup.verify_manifest(manifest)
    path.write_text('changed')
    with pytest.raises(RuntimeError, match='identity changed'):
        setup.verify_manifest(manifest)


def test_symlink_alias_retains_lexical_identity_and_rejects_retargeting(tmp_path):
    target = tmp_path / 'actual'
    target.write_text('same-data')
    alias = tmp_path / 'alias'
    alias.symlink_to('actual')
    records = [setup.fingerprint(p, tmp_path) for p in [target, alias]]
    assert records[0]['path'] != records[1]['path']
    assert records[0]['resolved_path'] == records[1]['resolved_path']
    assert records[1]['link_target'] == 'actual'
    setup.verify_manifest({'files': records})
    alias.unlink()
    replacement = tmp_path / 'replacement'
    replacement.write_text('same-data')
    alias.symlink_to('replacement')
    with pytest.raises(RuntimeError, match='resolution changed'):
        setup.verify_manifest({'files': records})


def test_symlink_export_cannot_escape_owned_dependency(tmp_path):
    owner = tmp_path / 'owned'
    owner.mkdir()
    outside = tmp_path / 'outside'
    outside.write_text('data')
    alias = owner / 'alias'
    alias.symlink_to('../outside')
    with pytest.raises(ValueError, match='escapes'):
        setup.fingerprint(alias, owner)


def test_gpu_metadata_mapping_never_claims_render_probe():
    rows = [{'index': '7', 'uuid': 'GPU-test', 'pci_bus_id': '00000000:85:00.0', 'driver_version': 'test'}]
    devices = [{'egl_device_index': 4, 'physical_cuda_ordinal': 7, 'cuda_attribute_ok': True,
                'drm_pci_bus_id': '0000:85:00.0'}]
    result = setup.bind_gpu7_metadata(devices, rows)
    assert result['metadata_mapping_verified'] is True
    assert result['cuda_egl_verified'] is False
    assert result['historical_gpu7_egl4_holds'] is True
    assert result['drm_pci_verified'] is True


@pytest.mark.parametrize('devices', [
    [],
    [{'egl_device_index': 4, 'physical_cuda_ordinal': 7, 'cuda_attribute_ok': False}],
    [{'egl_device_index': 4, 'physical_cuda_ordinal': 7, 'cuda_attribute_ok': True,
      'drm_pci_bus_id': '0000:66:00.0'}],
    [{'egl_device_index': x, 'physical_cuda_ordinal': 7, 'cuda_attribute_ok': True} for x in [4, 5]],
])
def test_gpu_metadata_mapping_rejects_missing_ambiguous_or_conflicting_device(devices):
    rows = [{'index': '7', 'uuid': 'GPU-test', 'pci_bus_id': '00000000:85:00.0', 'driver_version': 'test'}]
    with pytest.raises(RuntimeError):
        setup.bind_gpu7_metadata(devices, rows)


@pytest.mark.parametrize('physical_gpu,egl_index', [(5, 7), (7, 4)])
def test_selected_gpu_metadata_uses_queried_mapping(physical_gpu, egl_index):
    rows = [{'index': str(physical_gpu), 'uuid': 'GPU-selected',
             'pci_bus_id': '00000000:A1:00.0', 'driver_version': 'test'}]
    devices = [{'egl_device_index': egl_index, 'physical_cuda_ordinal': physical_gpu,
                'cuda_attribute_ok': True, 'drm_pci_bus_id': '0000:a1:00.0'}]
    result = setup.bind_gpu_metadata(devices, rows, physical_gpu)
    assert result['physical_gpu'] == physical_gpu
    assert result['egl_device_index'] == egl_index
    assert result['uuid'] == 'GPU-selected'
    assert result['cuda_egl_verified'] is False
    assert result['drm_pci_verified'] is True
    if physical_gpu == 5:
        assert 'historical_gpu7_egl4_holds' not in result


@pytest.mark.parametrize('physical_gpu', [True, -1, '5', None])
def test_invalid_physical_gpu_is_rejected(physical_gpu):
    with pytest.raises(RuntimeError, match='nonnegative integer'):
        setup.bind_gpu_metadata([], [], physical_gpu)


@pytest.mark.parametrize('change', [
    {'index': '7'}, {'uuid': ''}, {'pci_bus_id': 'invalid'},
    {'pci_bus_id': '00000001:A1:00.0'},
])
def test_gpu5_metadata_rejects_spoofed_or_incomplete_identity(change):
    rows = [{**{'index': '5', 'uuid': 'GPU-selected', 'pci_bus_id': '00000000:A1:00.0',
                'driver_version': 'test'}, **change}]
    devices = [{'egl_device_index': 7, 'physical_cuda_ordinal': 5,
                'cuda_attribute_ok': True, 'drm_pci_bus_id': '0000:a1:00.0'}]
    with pytest.raises(RuntimeError):
        setup.bind_gpu_metadata(devices, rows, 5)


@pytest.mark.parametrize('mask,order', [('5', 'PCI_BUS_ID'), ('', 'PCI_BUS_ID'), (None, 'FASTEST_FIRST')])
def test_metadata_query_requires_unmasked_pci_namespace(monkeypatch, mask, order):
    if mask is None:
        monkeypatch.delenv('CUDA_VISIBLE_DEVICES', raising=False)
    else:
        monkeypatch.setenv('CUDA_VISIBLE_DEVICES', mask)
    monkeypatch.setenv('CUDA_DEVICE_ORDER', order)
    monkeypatch.setattr(setup, 'enumerate_egl_devices_metadata', lambda: pytest.fail('must reject before EGL query'))
    with pytest.raises(RuntimeError, match='requires no CUDA_VISIBLE_DEVICES'):
        setup.query_gpu_egl_metadata(5)


def test_metadata_query_only_uses_metadata_and_records_namespace(monkeypatch):
    monkeypatch.delenv('CUDA_VISIBLE_DEVICES', raising=False)
    monkeypatch.setenv('CUDA_DEVICE_ORDER', 'PCI_BUS_ID')
    devices = [{'egl_device_index': 7, 'physical_cuda_ordinal': 5, 'cuda_attribute_ok': True}]
    monkeypatch.setattr(setup, 'enumerate_egl_devices_metadata', lambda: devices)
    monkeypatch.setattr(setup.subprocess, 'check_output', lambda *args, **kwargs:
                        '5, GPU-selected, 00000000:A1:00.0, mock-driver\n')
    result = setup.query_gpu_egl_metadata(5)
    assert result['physical_gpu'] == 5
    assert result['egl_device_index'] == 7
    assert result['metadata_cuda_ordinal_namespace'] == 'unmasked_pci_bus_id'
    assert result['enumeration_only'] is True
    assert result['display_or_context_calls'] is False
    assert result['cuda_egl_verified'] is False
