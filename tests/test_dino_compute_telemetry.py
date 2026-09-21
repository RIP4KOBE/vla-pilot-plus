"""CPU-only observations at actual DINO feature call boundaries, without loading models."""
import ast
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch
from torch.nn.functional import interpolate


def detector_methods():
    tree = ast.parse((Path(__file__).resolve().parents[1] / 'core/keypoint_detector.py').read_text())
    names = {'get_compute_counters', '_record_dino_forward', '_get_features_dinov2', '_get_features_dinov3'}
    nodes = [node for cls in tree.body if isinstance(cls, ast.ClassDef)
             for node in cls.body if isinstance(node, ast.FunctionDef) and node.name in names]
    cls = ast.ClassDef(name='Detector', bases=[], keywords=[], body=nodes, decorator_list=[])
    module = ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[]))
    namespace = {'torch': torch, 'np': np, 'interpolate': interpolate}
    exec(compile(module, '<dino-cpu-methods>', 'exec'), namespace)
    return namespace['Detector']


@pytest.mark.parametrize('version', ['dinov2', 'dinov3'])
@pytest.mark.parametrize('fails', [False, True])
def test_dino_counts_actual_calls_and_failed_attempts_without_rng_changes(version, fails):
    detector = detector_methods()()
    detector.device = torch.device('cpu')
    detector.patch_size = 2
    observed = []

    def forward(*args, **kwargs):
        image = args[0] if args else kwargs['pixel_values']
        observed.append(tuple(image.shape))
        assert detector.get_compute_counters() == {'dino_forward_calls': len(observed), 'dino_batch_rows': len(observed)}
        if fails:
            raise RuntimeError('mock feature failure')
        if version == 'dinov2':
            return {'x_norm_patchtokens': torch.ones(1, 4, 3)}
        return SimpleNamespace(last_hidden_state=torch.ones(1, 5, 3))

    detector.dino_model = SimpleNamespace(forward_features=forward) if version == 'dinov2' else forward
    detector.dinov3_processor = lambda **kwargs: {'pixel_values': torch.zeros(1, 3, 4, 4)}
    rgb = np.zeros((4, 4, 3), dtype=np.float32)
    torch_rng = torch.get_rng_state().clone()
    numpy_rng = np.random.get_state()
    assert detector.get_compute_counters() == {'dino_forward_calls': 0, 'dino_batch_rows': 0}
    for _ in range(2):
        call = (lambda: detector._get_features_dinov2(rgb, 4, 4, 2, 2)) if version == 'dinov2' else (
            lambda: detector._get_features_dinov3(rgb, 4, 4))
        if fails:
            with pytest.raises(RuntimeError, match='mock feature failure'):
                call()
        else:
            assert torch.equal(call(), torch.ones(16, 3))
    assert observed == [(1, 3, 4, 4)] * 2
    assert detector.get_compute_counters() == {'dino_forward_calls': 2, 'dino_batch_rows': 2}
    snapshot = detector.get_compute_counters()
    snapshot['dino_forward_calls'] = 999
    assert detector.get_compute_counters()['dino_forward_calls'] == 2
    assert torch.equal(torch.get_rng_state(), torch_rng)
    after_numpy_rng = np.random.get_state()
    assert numpy_rng[0] == after_numpy_rng[0]
    assert np.array_equal(numpy_rng[1], after_numpy_rng[1])
    assert numpy_rng[2:] == after_numpy_rng[2:]


def test_dino_preprocessing_failure_does_not_count_a_model_call():
    detector = detector_methods()()
    detector.device = torch.device('cpu')
    with pytest.raises(AssertionError, match='unexpected image shape'):
        detector._get_features_dinov2(np.zeros((4, 4, 2), dtype=np.float32), 4, 4, 2, 2)
    assert detector.get_compute_counters() == {'dino_forward_calls': 0, 'dino_batch_rows': 0}
