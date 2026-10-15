"""CPU-only fake clock/sleep/scene tests; no waiting, GPU or model import."""
import ast
import importlib.util
from pathlib import Path
import pytest

DIRECTORY = Path(__file__).parent

def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, DIRECTORY / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

child = load('idle_child', 'libero-task0-render-idle.py')
fixtures = load('idle_cpu_scene_fixtures', 'test_libero_task0_render_model.py')


def test_fixed_idle_between_camera_boundaries_ten_renders_and_unchanged_factory():
    guard, emit, events, operations, factory, init_row, _ = fixtures.setup()
    clock = [100.0]
    sleeps = []
    def sleep(seconds):
        assert seconds == 75.0 and guard.renders == 7
        sleeps.append(seconds)
        before = operations.copy()
        clock[0] += seconds
        assert before == operations
    try:
        proof = child.workflow(factory, init_row, guard, emit, lambda: False, sleep, lambda: clock[0])
        assert sleeps == [75.0] and proof['idle_elapsed_seconds'] == 75.0
        assert proof['explicit_render_calls'] == 6 and guard.renders == 10
        assert proof['sim_time_after_init'] == proof['sim_time_final'] == 0.0
        assert proof['cuda_initialization_states'] == dict.fromkeys(
            ('before_construct', 'before_idle', 'after_idle', 'after_final_render'), False)
        assert guard.blocked_integrations == 0 and guard.step1 == 1 and guard.forwards == 2
        for name in ('before_idle', 'after_idle'):
            frames = [e for e in events if e.get('event') == 'render_exit' and e['phase'] == name]
            assert [(e['camera'], e['width'], e['depth']) for e in frames] == child.helper.CAMERAS
        start = next(i for i, e in enumerate(events) if e['event'] == 'idle_enter')
        end = next(i for i, e in enumerate(events) if e['event'] == 'idle_exit')
        assert end == start + 1 and operations[-1] == 'close'
    finally:
        guard.restore()
    tree = ast.parse((DIRECTORY / 'libero-task0-render-idle.py').read_text())
    previous = ast.parse((DIRECTORY / 'libero-task0-render-model.py').read_text())
    factory_ast = lambda root: next(n for n in ast.walk(root) if isinstance(n, ast.FunctionDef) and n.name == 'factory')
    assert ast.dump(factory_ast(tree)) == ast.dump(factory_ast(previous))
    cuda_attributes = [ast.unparse(n) for n in ast.walk(tree) if isinstance(n, ast.Attribute) and
                       isinstance(n.value, ast.Attribute) and ast.unparse(n.value) == 'torch.cuda']
    assert cuda_attributes == ['torch.cuda.is_initialized']
    imports = [n.module or '' for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    assert not any(name.startswith(('core.rdt', 'scripts.maniskill_model', 'models.')) for name in imports)
    calls = [ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)]
    assert 'gc.disable' not in calls and not any('predict' in name or 'from_pretrained' in name for name in calls)


@pytest.mark.parametrize('failure', ['cuda_initialized', 'short_wait', 'integration', 'render_cap'])
def test_scope_guards_stop_without_later_renders_or_original_integration(failure):
    guard, emit, events, operations, factory, init_row, mujoco = fixtures.setup(limit=7 if failure == 'render_cap' else 32)
    clock = [0.0]
    def sleep(seconds):
        if failure == 'integration':
            mujoco.mj_step(None, None)
        clock[0] += 74.0 if failure == 'short_wait' else seconds
    try:
        with pytest.raises(RuntimeError):
            child.workflow(factory, init_row, guard, emit, lambda: failure == 'cuda_initialized', sleep, lambda: clock[0])
        assert guard.renders == (0 if failure == 'cuda_initialized' else 7)
        assert 'mj_step' not in operations
        assert not any(e.get('event') == 'render_exit' and e.get('phase') == 'after_idle' for e in events)
        if failure != 'cuda_initialized':
            assert operations[-1] == 'close'
    finally:
        guard.restore()
