import ast
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from utils.cuda_egl_guard import install


def fixture_guard(tmp_path, *, initialized=True, current='other', sync_error=None, bind_ok=True, render_error=None):
    calls = []
    active = [current]
    token = object()
    def synchronize(*, device):
        calls.append(('cuda_sync', device))
        if sync_error:
            raise sync_error
    class Context:
        def render(self, *args, **kwargs):
            calls.append(('render', args, kwargs))
            if render_error:
                raise render_error
            return token
    def make_current():
        calls.append(('egl_bind',))
        if bind_ok:
            active[0] = 'owned'
    context = Context()
    context.gl_ctx = SimpleNamespace(_context='owned', make_current=make_current)
    kwargs = dict(bindings=SimpleNamespace(MjRenderContext=Context),
                  torch_module=SimpleNamespace(cuda=SimpleNamespace(is_initialized=lambda: initialized, synchronize=synchronize)),
                  current_context=lambda: active[0], handle=lambda value: value)
    install(tmp_path, **kwargs)
    return context, calls, token, kwargs


def test_wait_bind_render_order_preserves_arguments_and_return(tmp_path):
    context, calls, token, _ = fixture_guard(tmp_path)
    assert context.render(token, width=640, height=480) is token
    assert calls == [('cuda_sync',0), ('egl_bind',), ('render',(token,),{'width':640,'height':480})]
    events = [json.loads(line) for line in (tmp_path/'cuda_egl_guard.jsonl').read_text().splitlines()]
    assert [e['event'] for e in events] == ['enter','cuda_complete','egl_current']
    assert events[0]['current_context_matches'] is False


def test_already_current_context_is_recorded_without_changing_render(tmp_path):
    context, calls, token, _ = fixture_guard(tmp_path, current='owned')
    assert context.render() is token
    assert json.loads((tmp_path/'cuda_egl_guard.jsonl').read_text().splitlines()[0])['current_context_matches']


def test_no_cuda_initialization_if_no_context_exists(tmp_path):
    context, calls, token, _ = fixture_guard(tmp_path, initialized=False)
    assert context.render() is token
    assert calls == [('egl_bind',), ('render',(),{})]


def test_cuda_failure_propagates_before_any_gl_operation(tmp_path):
    error = RuntimeError('original CUDA failure')
    context, calls, _, _ = fixture_guard(tmp_path, sync_error=error)
    with pytest.raises(RuntimeError) as caught:
        context.render()
    assert caught.value is error and calls == [('cuda_sync',0)]


def test_failed_context_binding_prevents_render(tmp_path):
    context, calls, _, _ = fixture_guard(tmp_path, bind_ok=False)
    with pytest.raises(RuntimeError, match='failed to bind'):
        context.render()
    assert calls == [('cuda_sync',0), ('egl_bind',)]


def test_original_render_exception_is_preserved(tmp_path):
    error = ValueError('original render failure')
    context, _, _, _ = fixture_guard(tmp_path, render_error=error)
    with pytest.raises(ValueError) as caught:
        context.render()
    assert caught.value is error


def test_reinstallation_does_not_duplicate_sync_or_render(tmp_path):
    context, calls, token, kwargs = fixture_guard(tmp_path)
    install(tmp_path, **kwargs)
    assert context.render() is token
    assert len(calls) == 3


def test_disabled_main_guard_has_no_import_or_io(tmp_path):
    tree = ast.parse((Path(__file__).resolve().parents[1]/'main.py').read_text())
    main = next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Main')
    method = next(n for n in main.body if isinstance(n,ast.FunctionDef) and n.name=='_enable_runtime_render_guard')
    namespace = {'os':SimpleNamespace(environ={})}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[])), '<guard>','exec'),namespace)
    namespace['_enable_runtime_render_guard'](SimpleNamespace())


def test_runner_does_not_inherit_guard_flag_from_shell(monkeypatch):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
    import qd_ed_final_runner as runner
    monkeypatch.setenv('QD_ED_CUDA_EGL_SERIALIZE','1')
    runtime={'environment':{},'gpu_mapping':{'physical_gpu':5,'egl_device_index':7}}
    assert runner.child_environment(runtime)['QD_ED_CUDA_EGL_SERIALIZE']=='0'
    runtime['environment']['QD_ED_CUDA_EGL_SERIALIZE']='1'
    assert runner.child_environment(runtime)['QD_ED_CUDA_EGL_SERIALIZE']=='1'
