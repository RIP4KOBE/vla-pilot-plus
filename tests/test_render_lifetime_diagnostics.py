import ast
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from utils.render_lifetime_diagnostics import install


def fixture(tmp_path, *, fail=False):
    calls, callbacks = [], []
    token = object()
    error = ValueError('original error')

    class Context:
        def __init__(self, arg):
            calls.append(('init', arg))
            self.gl_ctx = SimpleNamespace(_context='owned')
            self.con = SimpleNamespace(offFBO=3)

        def render(self, *args, **kwargs):
            calls.append(('render', args, kwargs))
            if fail:
                raise error
            return token

        def update_offscreen_size(self, width, height):
            calls.append(('resize', width, height))

        def __del__(self):
            calls.append(('destroy',))
            self.gl_ctx = None
            self.con = None

    class Sim:
        def free(self):
            calls.append(('free',))
            return token

    bindings = SimpleNamespace(MjRenderContext=Context, MjSim=Sim)
    kwargs = dict(bindings=bindings, current_context=lambda: 'another',
                  handle=lambda v: v, callbacks=callbacks)
    observer = install(tmp_path, **kwargs)
    return bindings, calls, callbacks, token, error, kwargs, observer


def test_observer_preserves_operations_and_detects_cleanup_in_wrong_context(tmp_path):
    bindings, calls, callbacks, token, _, _, observer = fixture(tmp_path)
    ctx = bindings.MjRenderContext(token)
    assert ctx.render(token, camera_id=2) is token
    ctx.update_offscreen_size(640, 480)
    ctx.__del__()
    sim = bindings.MjSim()
    assert sim.free() is token
    assert calls == [('init', token), ('render', (token,), {'camera_id': 2}),
                     ('resize', 640, 480), ('destroy',), ('free',)]
    callbacks[0]('start', {'generation': 1})
    observer('episode_phase', name='select_action_fresh', boundary='enter')
    rows = [json.loads(s) for s in (tmp_path/'render_lifetime.jsonl').read_text().splitlines()]
    cleanup = next(r for r in rows if r.get('method') == '__del__' and r['event'] == 'enter')
    assert cleanup['current_context_matches'] is False and cleanup['offFBO'] == 3
    assert rows[-2]['event'] == 'gc_start' and rows[-1]['name'] == 'select_action_fresh'
    assert not any('args' in r or 'kwargs' in r for r in rows)


def test_original_exception_survives_diagnostics(tmp_path):
    bindings, calls, _, token, error, _, _ = fixture(tmp_path, fail=True)
    ctx = bindings.MjRenderContext(token)
    with pytest.raises(ValueError) as caught:
        ctx.render()
    assert caught.value is error and len(calls) == 2


def test_reinstall_does_not_add_callbacks_or_duplicate_wrappers(tmp_path):
    bindings, calls, callbacks, token, _, kwargs, observer = fixture(tmp_path)
    assert install(tmp_path, **kwargs) is observer
    assert len(callbacks) == 1
    assert bindings.MjRenderContext(token).render() is token
    assert sum(c[0] == 'render' for c in calls) == 1


def test_failed_io_does_not_break_original_operation(tmp_path):
    occupied = tmp_path/'occupied'; occupied.write_text('file')
    bindings, _, _, token, _, _, _ = fixture(occupied)
    assert bindings.MjRenderContext(token).render() is token


def test_disabled_early_hook_does_not_import_simulator():
    root = Path(__file__).resolve().parents[1]
    tree = ast.parse((root/'main.py').read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Main')
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_enable_render_lifetime_diagnostics')
    namespace = {'os': SimpleNamespace(environ={})}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])), '<observer>', 'exec'), namespace)
    namespace[method.name](SimpleNamespace())


def test_runner_flag_cannot_leak_from_parent_shell(monkeypatch):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
    import qd_ed_final_runner as runner
    monkeypatch.setenv('QD_ED_RENDER_LIFETIME', '1')
    runtime = {'environment': {}, 'gpu_mapping': {'physical_gpu': 5, 'egl_device_index': 7}}
    assert runner.child_environment(runtime)['QD_ED_RENDER_LIFETIME'] == '0'
    runtime['environment']['QD_ED_RENDER_LIFETIME'] = '1'
    assert runner.child_environment(runtime)['QD_ED_RENDER_LIFETIME'] == '1'
