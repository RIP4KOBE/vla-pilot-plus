"""Three CPU-only checks: no actual model, Torch, simulator or GPU imports."""
import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import pytest

DIRECTORY = Path(__file__).parent

def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, DIRECTORY / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

child = load('loader_phase_child', 'libero-task0-model-load-phases.py')
fixtures = load('existing_cpu_scene_fixtures', 'test_libero_task0_render_model.py')


def test_exact_loader_order_arguments_and_sixteen_total_camera_calls():
    guard, emit, events, operations, factory, init_row, _ = fixtures.setup()
    calls = []
    marker = object()
    config = dict(pretrained_path='/frozen/rdt', num_inference_steps=5, vision_encoder='/frozen/vision',
                  text_encoder='/frozen/text', weight_variant='ema', control_frequency=25)
    class Inner:
        def get_text_encoder(self, path):
            calls.append(('get_text_encoder', path))
            return marker
        def reset(self):
            calls.append(('inner_reset',))
            return marker
    original_text, original_reset = Inner.get_text_encoder, Inner.reset
    module = SimpleNamespace(RoboticDiffusionTransformerModel=Inner)
    def original_import(*args, **kwargs):
        assert Inner.get_text_encoder is original_text
        calls.append(('import', args, kwargs))
        return module
    importer = SimpleNamespace(__import__=original_import)
    counts = dict(model_forward_calls=0, text_encoder_forward_calls=0, vision_encoder_forward_calls=0,
                  denoising_invocations=0, model_forward_batch_sizes=[])
    class Policy:
        _episode_compute = counts
        @classmethod
        def from_pretrained(cls, *args, **kwargs):
            assert args == (config['pretrained_path'],)
            assert kwargs == {key: config[key] for key in ('num_inference_steps', 'vision_encoder',
                'text_encoder', 'weight_variant', 'control_frequency')}
            calls.append(('from_pretrained',))
            imported = importer.__import__('scripts.maniskill_model', None, None, ('create_model',), 0)
            assert imported is module and importer.__import__ is original_import
            real_model = imported.RoboticDiffusionTransformerModel()
            assert real_model.get_text_encoder(config['text_encoder']) is marker
            assert real_model.reset() is marker
            return cls()
        def to(self, device):
            assert device == 'cuda:0'
            calls.append(('to',))
            return self
        def eval(self):
            calls.append(('eval',))
            return self
        def post_init(self, **kwargs):
            assert kwargs.keys() == {'adapter', 'postprocessor', 'sample_batch_size', 'policy_config'}
            assert kwargs['adapter'] is None and kwargs['sample_batch_size'] == 1
            assert kwargs['policy_config'] is config and kwargs['postprocessor'](marker) is marker
            calls.append(('post_init',))
        def reset(self):
            calls.append(('outer_reset',))
        def get_episode_compute_counters(self):
            calls.append(('counters',))
            return counts.copy()
    def loader(boundary):
        def production_import():
            calls.append(('production_import',))
            return Policy
        def identity_seed():
            calls.append(('identity_seed',))
        return child.load_in_phases(boundary, guard, emit, production_import, identity_seed, config,
            lambda value: value is module or pytest.fail('wrong import'), importer)
    try:
        evidence = child.workflow(factory, init_row, guard, emit, loader)
        assert evidence['successful_boundaries'] == list(child.BOUNDARIES)
        assert evidence['call_counts'] == dict.fromkeys(child.BOUNDARIES, 1)
        assert evidence['compute'] == counts
        assert evidence['explicit_render_calls'] == 12 and guard.renders == 16
        assert guard.blocked_integrations == 0 and guard.step1 == 1 and guard.forwards == 2
        assert evidence['sim_time_after_init'] == evidence['sim_time_final'] == 0
        assert [event['boundary'] for event in events if event['event'] == 'boundary_exit'] == ['baseline', *child.BOUNDARIES]
        assert [entry[0] for entry in calls] == ['production_import', 'identity_seed', 'from_pretrained', 'import',
            'get_text_encoder', 'inner_reset', 'to', 'eval', 'post_init', 'outer_reset', 'counters']
        assert Inner.get_text_encoder is original_text and Inner.reset is original_reset
        assert importer.__import__ is original_import
        tree = ast.parse((DIRECTORY / 'libero-task0-model-load-phases.py').read_text())
        assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and
            node.func.attr in {'synchronize', '_predict_unguided', 'child_probe', 'install_phase_wrappers'}
            for node in ast.walk(tree))
    finally:
        guard.restore()


def test_owned_wrappers_preserve_original_exception_arguments_and_restore():
    error = RuntimeError('original CPU exception')
    result = object()
    calls, boundaries, counts = [], [], {}
    class Inner:
        def get_text_encoder(self, *args, **kwargs):
            calls.append(('text', args, kwargs))
            raise error
        def reset(self, *args, **kwargs):
            calls.append(('reset', args, kwargs))
            return result
    original_text, original_reset = Inner.get_text_encoder, Inner.reset
    module = SimpleNamespace(RoboticDiffusionTransformerModel=Inner)
    def original_import(*args, **kwargs):
        return module
    importer = SimpleNamespace(__import__=original_import)
    def invoke(name, original, *args, **kwargs):
        child.require(counts.get(name, 0) == 0, 'duplicate')
        counts[name] = 1
        value = original(*args, **kwargs)
        boundaries.append(name)
        return value
    obj = Inner()
    with pytest.raises(RuntimeError) as caught:
        with child.internal_hooks(invoke, lambda _: None, importer):
            assert importer.__import__('scripts.maniskill_model', fromlist=('create_model',)) is module
            assert obj.reset('same', key=result) is result
            with pytest.raises(child.helper.static.ScopeViolation, match='duplicate'):
                obj.reset('never called')
            obj.get_text_encoder('frozen path', marker=result)
    assert caught.value is error
    assert calls == [('reset', ('same',), {'key': result}), ('text', ('frozen path',), {'marker': result})]
    assert boundaries == ['internal_constructor_reset']
    assert Inner.get_text_encoder is original_text and Inner.reset is original_reset
    assert importer.__import__ is original_import
    # A failed original import is also propagated unchanged and importer restored.
    def import_failure(*args, **kwargs):
        raise error
    importer.__import__ = import_failure
    with pytest.raises(RuntimeError) as caught:
        with child.internal_hooks(invoke, lambda _: pytest.fail('no successful import'), importer):
            importer.__import__('scripts.maniskill_model')
    assert caught.value is error and importer.__import__ is import_failure


def test_original_integration_guards_and_render_cap_stop_before_originals():
    guard, emit, events, operations, factory, init_row, mujoco = fixtures.setup(limit=7)
    def loader(boundary):
        for original_forbidden in (mujoco.mj_step, mujoco.mj_step2, guard.forbid_integration):
            with pytest.raises(fixtures.child.static.ScopeViolation, match='outside diagnostic scope'):
                original_forbidden(None, None)
        boundary(child.BOUNDARIES[0])
        pytest.fail('render cap must stop')
    try:
        with pytest.raises(child.helper.static.ScopeViolation, match='insufficient total render budget'):
            child.workflow(factory, init_row, guard, emit, loader)
        assert guard.blocked_integrations == 3 and guard.renders == 7
        assert guard.step1 == 1 and guard.forwards == 2
        assert 'mj_step' not in operations and 'mj_step2' not in operations and 'sim.step' not in operations
        assert operations[-1] == 'close'
        assert len([e for e in events if e.get('event') == 'render_exit']) == 7
    finally:
        guard.restore()
