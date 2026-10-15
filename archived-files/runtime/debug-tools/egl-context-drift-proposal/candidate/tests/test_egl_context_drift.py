"""CPU mocks only. No EGL imports, library loads, contexts or GPU calls."""
import importlib.util
import json
from pathlib import Path
import sys
import threading
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parents[1] / "core"

def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

module = load("core.egl_context_drift", "egl_context_drift.py")
render_module = load("candidate_render_phase_diagnostics", "render_phase_diagnostics.py")


def existing_sim(monkeypatch):
    class GLContext:
        _context = 44
    GLContext.__module__ = "existing_egl_context"
    monkeypatch.setitem(sys.modules, "existing_egl_context", SimpleNamespace(EGL_DISPLAY=22))
    return SimpleNamespace(_render_context_offscreen=SimpleNamespace(gl_ctx=GLContext()))


@pytest.mark.parametrize("display,context,null,match", [
    (22,44,False,True), (22,99,False,False), (22,None,True,False),
])
def test_match_drift_and_null_are_distinct(monkeypatch, display, context, null, match):
    sim = existing_sim(monkeypatch)
    calls = []
    def factory(name):
        def query():
            calls.append(name)
            return {"eglGetCurrentDisplay":display,"eglGetCurrentContext":context}[name]
        return query
    result = module.observe_current_context(sim, query_factory=factory)
    assert calls == ["eglGetCurrentDisplay", "eglGetCurrentContext"]
    assert result["display_matches_reference"] is True
    assert result["current_context_is_null"] is null
    assert result["context_matches_reference"] is match
    assert all(type(value) is bool or value == "Unknown" for value in result.values())


def test_existing_handle_resolution_and_missing_entries_without_library_loading(monkeypatch):
    class LazyPlatform:
        @property
        def EGL(self):
            pytest.fail("must not call a lazy library loader")
    monkeypatch.setitem(sys.modules,"OpenGL.platform",SimpleNamespace(PLATFORM=LazyPlatform()))
    monkeypatch.setattr(module.ctypes,"CDLL",lambda *a,**k: pytest.fail("must not load DLL"))
    sim = existing_sim(monkeypatch)
    result = module.observe_current_context(sim)
    assert result["current_context_is_null"] == "Unknown"
    assert result["context_matches_reference"] == "Unknown"
    assert result["reference_context_available"] is True

    # A loaded DLL may have no cached getter attributes. Resolve exactly the two
    # permitted symbols from that same handle using independent function views.
    library = SimpleNamespace(_handle=123)
    monkeypatch.setitem(sys.modules, "OpenGL.platform",
                        SimpleNamespace(PLATFORM=SimpleNamespace(EGL=library)))
    resolutions, queries = [], []
    def function_type(restype):
        assert restype is module.ctypes.c_void_p
        def resolve(symbol_and_library):
            name, observed_library = symbol_and_library
            assert observed_library is library
            resolutions.append(name)
            def getter():
                queries.append(name)
                return {"eglGetCurrentDisplay": 22, "eglGetCurrentContext": 44}[name]
            return getter
        return resolve
    monkeypatch.setattr(module.ctypes, "CFUNCTYPE", function_type)
    observed = module.observe_current_context(sim)
    assert observed["display_matches_reference"] is True
    assert observed["context_matches_reference"] is True
    assert resolutions == queries == ["eglGetCurrentDisplay", "eglGetCurrentContext"]
    assert vars(library) == {"_handle": 123}
    with pytest.raises(LookupError):
        module._cached_raw_query("eglGetError")
    assert len(resolutions) == 2
    def missing_symbol(restype):
        def resolve(symbol_and_library):
            raise AttributeError("unavailable export")
        return resolve
    monkeypatch.setattr(module.ctypes, "CFUNCTYPE", missing_symbol)
    missing = module.observe_current_context(sim)
    assert missing["current_display_is_null"] == "Unknown"
    assert missing["current_context_is_null"] == "Unknown"


def test_missing_reference_does_not_turn_null_into_matching(monkeypatch):
    sim = SimpleNamespace(_render_context_offscreen=None)
    result = module.observe_current_context(sim,query_factory=lambda name: lambda: None)
    assert result["current_display_is_null"] is True
    assert result["current_context_is_null"] is True
    assert result["context_matches_reference"] == "Unknown"
    assert result["reference_context_available"] is False


def test_three_boundaries_once_and_python_query_failure_is_isolated(tmp_path):
    calls=[]
    def query(sim):
        calls.append(sim)
        raise RuntimeError("secret-error-canary")
    sim=object()
    observer=module.ContextDriftObserver(tmp_path/'events.jsonl',sim,query=query)
    assert calls==[] and not observer.path.exists()
    for boundary in module.BOUNDARIES*2:
        observer.observe(boundary)
    observer.observe("unrecognized")
    records=[json.loads(s) for s in observer.path.read_text().splitlines()]
    assert len(records)==6
    assert [r['event'] for r in records]==['enter','exit']*3
    rows=[r for r in records if r['event']=='exit']
    assert calls==[sim]*3
    assert [r['boundary'] for r in rows]==list(module.BOUNDARIES)
    assert all(r['thread_id']==threading.get_ident() for r in rows)
    assert all(r['native_thread_id']==threading.get_native_id() for r in rows)
    assert all(r['context_matches_reference']=='Unknown' for r in rows)
    assert 'secret-error-canary' not in observer.path.read_text()


def test_existing_artifact_is_preserved(tmp_path):
    path=tmp_path/'events.jsonl'
    path.write_text('existing\n')
    observer=module.ContextDriftObserver(path,object(),query=lambda sim: {})
    for boundary in module.BOUNDARIES: observer.observe(boundary)
    assert path.read_text()=='existing\n'


def test_proposed_integration_preserves_render_calls_result_and_exception(monkeypatch,tmp_path):
    calls=[]
    queries=[]
    result=object()
    failure=RuntimeError('original failure')
    class Context:
        def render(self,*args,**kwargs): calls.append(('draw',args,kwargs))
        def read_pixels(self,*args,**kwargs):
            calls.append(('pixels',args,kwargs))
            if kwargs.get('fail'): raise failure
            return result
    class Sim:
        _render_context_offscreen=Context()
        def forward(self): pass
        def step(self): pass
        def render(self,*args,**kwargs):
            calls.append(('render',args,kwargs))
            self._render_context_offscreen.render(*args,**kwargs)
            return self._render_context_offscreen.read_pixels(*args,**kwargs)
    class Domain:
        sim=Sim()
        def _pre_action(self,*a,**k): pass
        def _update_observables(self,*a,**k): pass
    class Env:
        _env=SimpleNamespace(env=Domain())
        def _format_raw_obs(self,*a,**k): pass
    adapter=SimpleNamespace(_env=[Env()],current_task_idx=0)
    sim=adapter._env[0]._env.env.sim
    def query(value):
        queries.append(value)
        return {'current_context_is_null':False,'context_matches_reference':True}
    monkeypatch.setattr(render_module,'ContextDriftObserver',
        lambda path,value: module.ContextDriftObserver(path,value,query=query))
    observer=render_module.RenderPhaseDiagnostics(tmp_path/'render_phase_timing.jsonl')
    observer.install(adapter)
    assert queries==[]
    observer.set_phase(0,0,'select_action_fresh','enter')
    observer.set_phase(0,0,'select_action_fresh','exit')
    observer.set_phase(0,0,'diagnostic_artifacts','enter')
    assert sim.render(64,height=64) is result
    with pytest.raises(RuntimeError) as caught:
        sim.render(64,height=64,fail=True)
    assert caught.value is failure
    observer.set_phase(0,0,'diagnostic_artifacts','exit')
    observer.close()
    assert observer._context_drift is None
    assert queries==[sim]*3
    assert [call[0] for call in calls]==['render','draw','pixels']*2
    assert all(call[1]==(64,) for call in calls)
    assert all(call[2]=={'height':64} for call in calls[:3])
