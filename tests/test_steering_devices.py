"""Do not silently guess an EGL device when CUDA/EGL enumeration is ambiguous."""
import pytest

from scripts.list_steering_devices import unique_egl_index


def test_egl_mapping_uses_visible_cuda_identity_not_matching_index():
    devices = [{'egl_index': 0, 'visible_cuda_ordinal': None},
               {'egl_index': 4, 'visible_cuda_ordinal': -1},
               {'egl_index': 6, 'visible_cuda_ordinal': 0}]
    assert unique_egl_index(devices) == 6


@pytest.mark.parametrize('devices', [[], [{'egl_index': 0, 'visible_cuda_ordinal': None}],
    [{'egl_index': 2, 'visible_cuda_ordinal': 0}, {'egl_index': 3, 'visible_cuda_ordinal': 0}]])
def test_missing_or_ambiguous_egl_mapping_fails(devices):
    with pytest.raises(RuntimeError, match='Expected one EGL device'):
        unique_egl_index(devices)
