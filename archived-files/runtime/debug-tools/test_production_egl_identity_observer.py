"""CPU mocks only: no ctypes library is loaded and no native context is queried."""
import importlib.util
import json
from pathlib import Path
import threading
import ctypes
from types import SimpleNamespace

import pytest


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('production_egl_identity_observer', HERE / 'production_egl_identity_observer.py')
observer_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer_module)


EXPECTED = {'physical_gpu': 7, 'uuid': 'GPU-frozen', 'pci_bus_id': '00000000:E1:00.0',
            'egl_device_index': 4, 'cuda_visible_devices': '7', 'cuda_device_order': 'PCI_BUS_ID',
            'process_cuda_ordinal': 0}


class MockQueries:
    def __init__(self, *, context=0x44, display=0x22, missing=None):
        self.context, self.display, self.missing = context, display, missing
        self.calls = []
    def current_display(self):
        self.calls.append('current_display')
        return self.display
    def current_context(self):
        self.calls.append('current_context')
        return self.context
    def gl_string(self, enum):
        self.calls.append(('gl_string', enum))
        if self.missing == 'gl_renderer' and enum == 0x1F01:
            raise RuntimeError('query failure')
        return {0x1F00: 'NVIDIA Corporation', 0x1F01: 'Mock NVIDIA GPU', 0x1F02: 'Mock GL 4.6'}[enum]
    def display_device(self, display):
        assert display == 0x22
        self.calls.append('display_device')
        if self.missing == 'display_device':
            raise LookupError('extension unavailable')
        return 0x66
    def device_cuda_ordinal(self, device):
        assert device == 0x66
        self.calls.append('cuda_ordinal')
        return 0
    def device_indices(self, device):
        assert device == 0x66
        self.calls.append('device_indices')
        return [4]


def test_mock_query_records_actual_metadata_without_inventing_physical_uuid():
    queries = MockQueries()
    result = observer_module.query_current_context(lambda: queries)
    actual = result['observed']
    assert actual['egl_current_context'] == '0x44'
    assert actual['egl_current_display'] == '0x22'
    assert actual['egl_display_device'] == '0x66'
    assert actual['egl_device_index'] == 4 and actual['egl_device_cuda_ordinal'] == 0
    assert actual['gl_vendor'] == 'NVIDIA Corporation'
    assert actual['gl_renderer'] == 'Mock NVIDIA GPU'
    assert actual['drm_pci_bus_id'] == 'Unknown'
    assert actual['physical_gpu'] == actual['gpu_uuid'] == observer_module.UNKNOWN
    assert observer_module.comparisons(EXPECTED, actual) == {
        'egl_device_index_matches': True, 'process_cuda_ordinal_matches': True,
        'drm_pci_bus_id_matches': 'Unknown', 'physical_gpu_index_matches': 'Unknown', 'gpu_uuid_matches': 'Unknown'}
    assert queries.calls == ['current_display', 'current_context', ('gl_string', 0x1F00),
        ('gl_string', 0x1F01), ('gl_string', 0x1F02), 'display_device', 'cuda_ordinal',
        'device_indices']


@pytest.mark.parametrize('display,context', [(0, 0x44), (0x22, 0), (0, 0)])
def test_missing_current_context_does_not_query_gl_or_any_device(display, context):
    queries = MockQueries(context=context, display=display)
    result = observer_module.query_current_context(lambda: queries)
    assert queries.calls == ['current_display', 'current_context']
    assert result['observed']['gl_renderer'] == 'Unknown'
    assert result['observed']['egl_device_index'] == 'Unknown'


@pytest.mark.parametrize('missing', ['display_device', 'gl_renderer'])
def test_optional_query_failure_records_unknown_but_retains_other_observations(missing):
    result = observer_module.query_current_context(lambda: MockQueries(missing=missing))
    assert result['observed']['gl_vendor'] == 'NVIDIA Corporation'
    if missing == 'display_device':
        assert result['observed']['egl_display_device'] == result['observed']['egl_device_index'] == 'Unknown'
    else:
        assert result['observed']['gl_renderer'] == 'Unknown'
        assert result['observed']['egl_device_index'] == 4
    assert result['unavailable']


def test_no_observation_or_native_load_during_import_or_construction(tmp_path, monkeypatch):
    monkeypatch.setattr(observer_module.ctypes, 'CDLL', lambda *args: pytest.fail('must not load EGL'))
    observer = observer_module.CurrentContextIdentityObserver(tmp_path / 'identity.json', EXPECTED)
    assert observer.last_record is None
    assert not (tmp_path / 'identity.json').exists()


def test_native_facade_reuses_loaded_raw_entries_without_wrappers_or_extension_fallback(monkeypatch):
    calls = []
    # All addresses below are CPU ctypes callbacks, not driver/library functions.
    display = ctypes.CFUNCTYPE(ctypes.c_void_p)(lambda: 0x22)
    context = ctypes.CFUNCTYPE(ctypes.c_void_p)(lambda: 0x44)
    display.errcheck = lambda *args: pytest.fail('must not call original errcheck')
    strings = {enum: ctypes.create_string_buffer(value) for enum, value in (
        (0x1F00, b'loaded vendor'), (0x1F01, b'loaded renderer'), (0x1F02, b'loaded version'))}
    empty_extensions = ctypes.create_string_buffer(b'')
    def get_string(enum):
        calls.append(enum)
        return ctypes.addressof(strings[enum])
    gl_string = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_uint)(get_string)
    query_string = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int)(
        lambda display, enum: ctypes.addressof(empty_extensions))
    egl = SimpleNamespace(eglGetCurrentDisplay=display, eglGetCurrentContext=context,
        eglQueryString=query_string,
        eglGetError=lambda: pytest.fail('must not consume errors'),
        eglGetProcAddress=lambda *args: pytest.fail('must not resolve extension entries'),
        eglQueryDisplayAttribEXT=lambda *args: pytest.fail('must not query unsupported attributes'))
    gl = SimpleNamespace(glGetString=gl_string, glGetError=lambda: pytest.fail('must not consume errors'))
    platform = SimpleNamespace(EGL=egl, GL=gl)
    monkeypatch.setitem(observer_module.sys.modules, 'OpenGL.platform', SimpleNamespace(PLATFORM=platform))
    monkeypatch.setattr(observer_module.ctypes, 'CDLL', lambda *args: pytest.fail('must not load libraries'))
    result = observer_module.query_current_context()
    assert result['observed']['egl_current_display'] == '0x22'
    assert result['observed']['egl_current_context'] == '0x44'
    assert result['observed']['gl_renderer'] == 'loaded renderer'
    assert result['observed']['egl_display_device'] == 'Unknown'
    assert calls == [0x1F00, 0x1F01, 0x1F02]


def test_missing_cached_library_never_triggers_platform_lazy_loader(monkeypatch):
    class Platform:
        @property
        def EGL(self):
            pytest.fail('must not trigger EGL lazy loader')
    monkeypatch.setitem(observer_module.sys.modules, 'OpenGL.platform', SimpleNamespace(PLATFORM=Platform()))
    result = observer_module.query_current_context()
    assert set(result['observed'].values()) == {'Unknown'}


def test_cuda_attribute_is_not_queried_without_observed_device_extension(monkeypatch):
    queries = object.__new__(observer_module.ReadOnlyEGLQueries)
    queries._display_extensions = {'EGL_EXT_device_query'}
    queries._device_extensions = {0x66: {'EGL_EXT_device_drm'}}
    monkeypatch.setattr(queries, 'raw', lambda *args: pytest.fail('unsupported CUDA attribute must not be queried'))
    with pytest.raises(LookupError, match='support not proven'):
        queries.device_cuda_ordinal(0x66)


def test_wrapping_preserves_render_pixel_calls_locks_arguments_and_object_identity(tmp_path):
    calls, expected_result = [], object()
    render_lock = threading.Lock()
    def query():
        # Wrapped at the existing read_pixels success boundary, still inside
        # MjSim.render's original lock. The observer does not acquire this lock.
        assert render_lock.locked()
        calls.append('query')
        return observer_module.query_current_context(lambda: MockQueries())
    observer = observer_module.CurrentContextIdentityObserver(tmp_path / 'identity.json', EXPECTED, query_fn=query)
    def read_pixels(*args, **kwargs):
        assert render_lock.locked()
        calls.append(('read_pixels', args, kwargs))
        return expected_result
    wrapped_read_pixels = observer_module.wrap_render_once(read_pixels, observer)
    def original_render(*args, **kwargs):
        calls.append(('render', args, kwargs))
        with render_lock:
            calls.append('existing_context_render')
            return wrapped_read_pixels(*args, **kwargs)
    for _ in range(2):
        assert original_render(640, 640, depth=True) is expected_result
    assert calls.count('query') == 1
    assert calls.count('existing_context_render') == 2
    assert [entry for entry in calls if isinstance(entry, tuple)] == [
        ('render', (640, 640), {'depth': True}), ('read_pixels', (640, 640), {'depth': True}),
        ('render', (640, 640), {'depth': True}), ('read_pixels', (640, 640), {'depth': True})]
    assert not render_lock.locked()
    record = json.loads((tmp_path / 'identity.json').read_text())
    assert record['extra_render_calls'] == record['extra_simulation_steps'] == 0
    assert record['context_create_calls'] == record['make_current_calls'] == 0


def test_original_exception_propagates_unchanged_without_identity_query(tmp_path):
    exception = ValueError('original render failed')
    observer = observer_module.CurrentContextIdentityObserver(tmp_path / 'identity.json', EXPECTED,
        query_fn=lambda: pytest.fail('no successful original render'))
    calls = []
    def original(*args, **kwargs):
        calls.append((args, kwargs))
        raise exception
    wrapped = observer_module.wrap_render_once(original, observer)
    with pytest.raises(ValueError) as raised:
        wrapped(1, depth=False)
    assert raised.value is exception
    assert calls == [((1,), {'depth': False})]
    assert observer.last_record is None and observer._attempted is False


def test_identity_failure_and_unwritable_artifact_cannot_change_original_result(tmp_path):
    expected_result = object()
    queries = []
    def failed_query():
        queries.append(1)
        raise OSError('identity unavailable')
    # A directory cannot be opened as the create-only artifact; failure ignored.
    observer = observer_module.CurrentContextIdentityObserver(tmp_path, EXPECTED, query_fn=failed_query)
    calls = []
    def original(value):
        calls.append(value)
        return expected_result
    wrapped = observer_module.wrap_render_once(original, observer)
    assert wrapped(1) is expected_result and wrapped(2) is expected_result
    assert calls == [1, 2] and queries == [1]
    assert observer.last_record['observed']['egl_current_context'] == 'Unknown'


def test_failed_identity_query_is_written_as_unknown_and_not_retried(tmp_path):
    calls = []
    def query():
        calls.append(1)
        raise RuntimeError('failure')
    observer = observer_module.CurrentContextIdentityObserver(tmp_path / 'identity.json', EXPECTED, query_fn=query)
    observer.after_successful_render()
    observer.after_successful_render()
    record = json.loads((tmp_path / 'identity.json').read_text())
    assert calls == [1]
    assert set(record['observed'].values()) == {'Unknown'}
    assert set(record['comparison'].values()) == {'Unknown'}


def test_expected_environment_never_becomes_observed_identity_and_secrets_are_not_copied(tmp_path):
    expected = {**EXPECTED, 'api_key': 'REDACTED'}
    observer = observer_module.CurrentContextIdentityObserver(tmp_path / 'identity.json', expected,
        query_fn=lambda: observer_module.query_current_context(lambda: MockQueries(context=0)))
    observer.after_successful_render()
    text = (tmp_path / 'identity.json').read_text()
    record = json.loads(text)
    assert 'api_key' not in text and 'must-never-be-recorded' not in text
    assert record['expected']['physical_gpu'] == 7
    assert record['observed']['physical_gpu'] == record['observed']['gpu_uuid'] == 'Unknown'


def test_prior_identity_artifact_is_never_overwritten(tmp_path):
    output = tmp_path / 'identity.json'
    output.write_text('prior-record')
    observer = observer_module.CurrentContextIdentityObserver(output, EXPECTED,
        query_fn=lambda: observer_module.query_current_context(lambda: MockQueries()))
    observer.after_successful_render()
    assert output.read_text() == 'prior-record'


def test_comparison_distinguishes_mismatch_and_unknown():
    observed = {'egl_device_index': 2, 'egl_device_cuda_ordinal': 0, 'drm_pci_bus_id': '0001:e1:00.0'}
    result = observer_module.comparisons(EXPECTED, observed)
    assert result['egl_device_index_matches'] is False
    assert result['drm_pci_bus_id_matches'] is False
    assert result['process_cuda_ordinal_matches'] is True
    assert result['gpu_uuid_matches'] == 'Unknown'
