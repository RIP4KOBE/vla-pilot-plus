"""CPU only: execute installed robosuite AST with fake native functions."""
import ast
from pathlib import Path
from types import SimpleNamespace as NS
import threading

import numpy as np
import pytest

from native_render_lifetime import NativeLifetimeError, NativeRenderLifetime


BINDING = Path('/home/hynx/miniconda3/envs/vla-pilot/lib/python3.12/site-packages/robosuite/utils/binding_utils.py')


@pytest.fixture
def system():
    calls, faults, all_cons = [], {}, []
    current = [None]
    egl = NS()
    def make_current(display, draw, read, handle):
        calls.append('egl_unbind')
        current[0] = handle
        return True
    def destroy(display, handle):
        calls.append('egl_destroy')
        fault = faults.get('destroy')
        if isinstance(fault, BaseException):
            raise fault
        return fault is not False
    def release():
        calls.append('egl_release')
        return True
    egl.eglMakeCurrent = make_current
    egl.eglDestroyContext = destroy
    egl.eglReleaseThread = release
    class GL:
        def __init__(self, *, max_width, max_height, device_id):
            calls.append(('gl_create', max_width, max_height, device_id))
            self._context = None
            if 'factory' in faults:
                raise faults['factory']
            self._context = object()
        def make_current(self):
            calls.append('gl_bind')
            if 'bind' in faults:
                raise faults['bind']
            current[0] = self._context
        def free(self):
            if self._context is not None:
                calls.append('gl_free')
                # Same swallowed-exception semantics as installed EGLGLContext.
                try:
                    if current[0] is self._context:
                        egl.eglMakeCurrent('display', None, None, None)
                    egl.eglDestroyContext('display', self._context)
                    egl.eglReleaseThread()
                except Exception:
                    pass
                self._context = None
        def __del__(self):
            self.free()
    class Con:
        def __init__(self, model, scale):
            calls.append('mjr_create')
            self.offWidth = model.vis.global_.offwidth
            self.offHeight = model.vis.global_.offheight
            self.free_count = 0
            all_cons.append(self)
        def free(self):
            calls.append('mjr_free')
            self.free_count += 1
            if 'con_free' in faults:
                raise faults['con_free']
    def set_buffer(mode, con):
        calls.append('set_buffer')
        if 'set_buffer' in faults:
            raise faults['set_buffer']
    def update_scene(*args):
        calls.append('update_scene')
        if 'reenter' in faults:
            try:
                sim.render(2, 2)
            except NativeLifetimeError:
                calls.append('reentry_rejected')
    def render(**kwargs):
        calls.append('render')
        if 'render' in faults:
            raise faults['render']
    def read_pixels(*, rgb, depth, viewport, con):
        calls.append('read_pixels')
        if 'read' in faults:
            raise faults['read']
        rgb[:] = [1, 0, 0]
        if depth is not None:
            depth[:] = .5
    mujoco = NS(
        MjvScene=lambda *args, **kwargs: NS(flags={}, ngeom=1, geoms=[NS(segid=0, objtype=1, objid=7)]),
        MjvCamera=NS, MjvOption=lambda: NS(geomgroup=np.array([1, 1, 1, 0, 0, 0])), MjvPerturb=NS,
        MjrContext=Con, MjrRect=lambda *args: args, mjr_setBuffer=set_buffer,
        mjv_updateScene=update_scene, mjr_render=render, mjr_readPixels=read_pixels,
        mjtCamera=NS(mjCAMERA_FIXED=2, mjCAMERA_FREE=0),
        mjtFontScale=NS(mjFONTSCALE_150=150), mjtFramebuffer=NS(mjFB_OFFSCREEN=1),
        mjtCatBit=NS(mjCAT_ALL=7), mjtRndFlag=NS(mjRND_SEGMENT=7, mjRND_IDCOLOR=8))
    tree = ast.parse(BINDING.read_text())
    context_ast = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'MjRenderContext')
    sim_ast = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'MjSim')
    render_ast = next(n for n in sim_ast.body if isinstance(n, ast.FunctionDef) and n.name == 'render')
    namespace = {'mujoco': mujoco, 'np': np, 'GLContext': GL, '_MjSim_render_lock': threading.Lock()}
    exec(compile(ast.Module(body=[context_ast, render_ast], type_ignores=[]), str(BINDING), 'exec'), namespace)
    class Sim:
        render = namespace['render']
        def __init__(self):
            self._render_context_offscreen = None
            native = NS(vis=NS(global_=NS(offwidth=4, offheight=4)))
            self.model = NS(_model=native, vis=native.vis, camera_name2id=lambda name: {'agentview': 0, 'wrist': 1}[name])
            self.data = NS(_data=object())
            self.forward_calls = 0
            self.add_calls = 0
        def forward(self):
            self.forward_calls += 1
        def add_render_context(self, context):
            self._render_context_offscreen = context
            self.add_calls += 1
    sim = Sim()
    context = namespace['MjRenderContext'](sim, device_id=3)
    owner = NativeRenderLifetime(sim, egl=egl)
    calls.clear()
    value = NS(sim=sim, context=context, owner=owner, calls=calls, faults=faults, egl=egl, cons=all_cons)
    yield value
    try:
        owner.close()
    except NativeLifetimeError:
        pass
    context.__del__()


def test_actual_render_reuses_then_recreates_without_forward_and_keeps_cpu_fields(system):
    s = system
    identities = {name: id(getattr(s.context, name)) for name in ('scn', 'cam', 'vopt', 'pert')}
    s.context.vopt.geomgroup[0] = 0
    rgb, depth = s.sim.render(2, 3, camera_name='agentview', depth=True)
    assert np.all(rgb == [1, 0, 0]) and np.all(depth == .5)
    assert s.calls == ['update_scene', 'render', 'read_pixels', 'mjr_free', 'gl_free', 'egl_unbind', 'egl_destroy', 'egl_release']
    assert not hasattr(s.context, 'con') and not hasattr(s.context, 'gl_ctx')
    s.calls.clear()
    rgb = s.sim.render(2, 3, camera_name='wrist')
    assert s.calls[:4] == [('gl_create', 640, 480, 3), 'gl_bind', 'mjr_create', 'set_buffer']
    assert s.context.cam.fixedcamid == 1
    assert identities == {name: id(getattr(s.context, name)) for name in identities}
    assert s.context.vopt.geomgroup[0] == 0
    assert s.sim.forward_calls == s.sim.add_calls == 1
    assert all(con.free_count == 1 for con in s.cons)
    assert s.owner.snapshot()['last_cleanup_success'] is True
    assert s.owner.snapshot()['failed'] is False


def test_actual_segmentation_and_original_resize_are_preserved(system):
    s = system
    segmentation, depth = s.sim.render(6, 7, camera_name='agentview', depth=True, segmentation=True)
    assert segmentation.shape == (7, 6, 2) and np.all(segmentation == [1, 7])
    assert np.all(depth == .5)
    assert s.context.scn.flags == {7: 0, 8: 0}
    assert (s.sim.model.vis.global_.offwidth, s.sim.model.vis.global_.offheight) == (6, 7)
    assert s.sim.forward_calls == 1 and all(con.free_count == 1 for con in s.cons)


@pytest.mark.parametrize('stage', ['render', 'read'])
def test_primary_exception_identity_preserved_and_no_retry(system, stage):
    s = system
    error = ValueError(stage)
    s.faults[stage] = error
    with pytest.raises(ValueError) as caught:
        s.sim.render(2, 2)
    assert caught.value is error
    assert s.owner.failed and s.owner.last_cleanup_success
    count = len(s.calls)
    with pytest.raises(NativeLifetimeError, match='closed_or_failed'):
        s.sim.render(2, 2)
    assert len(s.calls) == count


@pytest.mark.parametrize('stage', ['factory', 'bind', 'set_buffer'])
def test_partial_creation_preserves_exception_and_records_uncertainty(system, stage):
    s = system
    s.sim.render(2, 2)
    error = ValueError(stage)
    s.faults[stage] = error
    with pytest.raises(ValueError) as caught:
        s.sim.render(2, 2)
    assert caught.value is error and s.owner.failed
    assert not hasattr(s.context, 'con') and not hasattr(s.context, 'gl_ctx')
    assert s.owner.snapshot()['unreturned_factory_allocation_unknown'] is (stage == 'factory')
    assert s.owner.last_cleanup_success is (stage != 'factory')


@pytest.mark.parametrize('destroy_result', [False, RuntimeError('native destroy')])
def test_swallowed_gl_free_failure_is_not_success_and_egl_hooks_restore(system, destroy_result):
    s = system
    originals = dict(vars(s.egl))
    s.faults['destroy'] = destroy_result
    with pytest.raises(NativeLifetimeError, match='retirement_not_verified'):
        s.sim.render(2, 2)
    assert s.owner.failed and s.owner.last_cleanup_success is False
    assert vars(s.egl) == originals
    assert s.cons[0].free_count == 1
    count = len(s.calls)
    s.context.__del__()
    s.context.__del__()
    assert len(s.calls) == count
    assert not any(hasattr(s.context, name) for name in ('scn', 'cam', 'vopt', 'pert'))


def test_cleanup_failure_does_not_replace_readback_exception(system):
    s = system
    error = ValueError('readback')
    s.faults.update(read=error, con_free=RuntimeError('free'), destroy=False)
    with pytest.raises(ValueError) as caught:
        s.sim.render(2, 2)
    assert caught.value is error
    assert s.owner.failed and s.owner.last_cleanup_success is False
    assert s.calls.count('mjr_free') == 1


def test_finalize_live_initial_context_once_and_clear_cpu_fields(system):
    s = system
    s.context.__del__()
    s.context.__del__()
    assert s.calls == ['mjr_free', 'gl_free', 'egl_unbind', 'egl_destroy', 'egl_release']
    assert not any(hasattr(s.context, name) for name in ('con', 'gl_ctx', 'scn', 'cam', 'vopt', 'pert'))
    assert s.owner.snapshot()['finalized'] and not s.owner.failed


def test_wrong_thread_rejected_without_native_calls(system):
    s = system
    errors = []
    def other_thread():
        try:
            s.sim.render(2, 2)
        except NativeLifetimeError as error:
            errors.append(str(error))
    thread = threading.Thread(target=other_thread)
    thread.start()
    thread.join(timeout=2)
    assert not thread.is_alive()
    assert errors == ['different_render_thread'] and s.calls == [] and s.owner.failed
    s.owner.close()
    assert s.owner.last_cleanup_success


def test_reentry_caught_inside_original_still_fails_closed(system):
    s = system
    s.faults['reenter'] = True
    with pytest.raises(NativeLifetimeError, match='failure_observed_during_render'):
        s.sim.render(2, 2)
    assert 'reentry_rejected' in s.calls
    assert s.owner.failed and s.owner.last_cleanup_success


def test_observer_holding_stable_context_does_not_retain_native_resources(system):
    s = system
    retained = [s.context, s.context.render, s.context.read_pixels]
    observed = []
    original = s.context.read_pixels
    def read(*args, **kwargs):
        observed.append('read')
        return original(*args, **kwargs)
    s.context.read_pixels = read
    for _ in range(2):
        s.sim.render(2, 2)
        assert not hasattr(retained[0], 'con') and not hasattr(retained[0], 'gl_ctx')
    assert observed == ['read', 'read'] and s.sim.forward_calls == 1
    count = len(s.calls)
    s.owner.close()
    s.context.__del__()
    assert len(s.calls) == count and s.owner.last_cleanup_success


@pytest.mark.parametrize('entry', ['render', 'close', 'finalizer'])
def test_replaced_context_before_first_render_quarantines_without_native_free(system, entry):
    s = system
    s.sim._render_context_offscreen = object()
    if entry == 'render':
        with pytest.raises(NativeLifetimeError, match='managed_context_replaced'):
            s.sim.render(2, 2)
    elif entry == 'close':
        with pytest.raises(NativeLifetimeError, match='retirement_not_verified'):
            s.owner.close()
    else:
        s.context.__del__()
    assert s.calls == [] and s.owner.failed and s.owner.last_cleanup_success is False
    assert not hasattr(s.context, 'con') and not hasattr(s.context, 'gl_ctx')
    assert any(event['event'] == 'ownership_drift_quarantined' for event in s.owner.events)
