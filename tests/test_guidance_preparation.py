"""Reward-code preparation repairs stay outside physical rollout and Planner."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch


VALID = '''def stage1_guidance(keypoints, action_sequence):
    source = keypoints[0]
    target = source + torch.tensor([-0.1, 0.0, 0.0], device=source.device, dtype=source.dtype)
    return -((action_sequence - target) ** 2).mean()
'''
CLONE = '''def stage1_guidance(keypoints, action_sequence):
    target = keypoints[0].clone()
    target[0] -= 0.1
    return -((action_sequence - target) ** 2).mean()
'''
INDEX_WRITE = '''def stage1_guidance(keypoints, action_sequence):
    target = keypoints[0] + 0.0
    target[0] -= 0.1
    return -((action_sequence - target) ** 2).mean()
'''


def make_app(tmp_path, outputs, attempts=3):
    from main import Main
    calls = []
    agent = SimpleNamespace(task_dir=str(tmp_path / 'vlm_agent'), prompt_template='original task template')

    def generate(image, instruction, metadata):
        calls.append({'directory':agent.task_dir, 'prompt':agent.prompt_template,
                      'image':image, 'instruction':instruction, 'metadata':dict(metadata)})
        value = outputs[min(len(calls) - 1, len(outputs) - 1)]
        if isinstance(value, Exception):
            raise value
        directory = Path(agent.task_dir)
        metadata['num_stages'] = 1
        (directory / 'metadata.json').write_text(json.dumps(metadata))
        (directory / 'stage1_guidance.txt').write_text(value)
        (directory / 'output_raw.txt').write_text(value)
        return str(directory)

    agent.generate_guidance = generate
    app = Main.__new__(Main)
    app.vlm_agent = agent
    app.config = {'guidance_code_generation_attempts':attempts}
    app.cached_functions_dir = None
    app.policy = object()
    return app, calls


@pytest.mark.parametrize('invalid', [CLONE, INDEX_WRITE])
def test_invalid_generated_code_is_repaired_without_weakening_ast_or_loading_policy(tmp_path, invalid):
    from utils.guidance_utils import UnsafeGuidanceCode, validate_guidance_ast
    app, calls = make_app(tmp_path, [invalid, VALID])
    policy = app.policy
    image, metadata = object(), {'num_keypoints':4}
    directory, info, functions = app._prepare_guidance_program(image, 'open drawer', metadata)
    assert len(calls) == 2 and all(c['image'] is image for c in calls)
    assert all(c['instruction'] == 'open drawer' for c in calls)
    assert all(c['metadata'] == metadata for c in calls)
    assert 'Previous output failed runtime validation' in calls[1]['prompt']
    assert 'assign or augment tensor elements/slices/attributes' in calls[0]['prompt']
    assert Path(directory).name == 'generation_002' and info['num_stages'] == 1
    assert (Path(calls[0]['directory']) / 'stage1_guidance.txt').read_text() == invalid
    rejected = json.loads((Path(calls[0]['directory']) / 'validation_error.json').read_text())
    assert rejected['executed_steps'] == 0 and not rejected['native_failure_label_allowed']
    trajectory = torch.randn(2, 10, 3, requires_grad=True)
    functions[1][0](torch.randn(4, 3), trajectory).backward()
    assert trajectory.grad is not None and torch.isfinite(trajectory.grad).all()
    assert app.policy is policy and app.vlm_agent.prompt_template == 'original task template'
    with pytest.raises(UnsafeGuidanceCode):
        validate_guidance_ast(invalid)


def test_generation_repair_is_bounded_and_keeps_every_rejected_program(tmp_path):
    from utils.guidance_utils import UnsafeGuidanceCode
    app, calls = make_app(tmp_path, [CLONE])
    with pytest.raises(UnsafeGuidanceCode):
        app._prepare_guidance_program(None, 'task', {})
    assert len(calls) == 3
    assert len({c['directory'] for c in calls}) == 3
    assert all((Path(c['directory']) / 'validation_error.json').is_file() for c in calls)
    assert not list(tmp_path.rglob('validation_result.json'))
    assert app.vlm_agent.prompt_template == 'original task template'


def test_cached_guidance_is_validated_read_only_and_never_regenerated(tmp_path):
    from utils.guidance_utils import UnsafeGuidanceCode
    cached = tmp_path / 'cached'
    cached.mkdir()
    (cached / 'metadata.json').write_text('{"num_stages":1}')
    (cached / 'stage1_guidance.txt').write_text(CLONE)
    app, calls = make_app(tmp_path, [VALID])
    app.cached_functions_dir = str(cached)
    before = {p.name:p.read_bytes() for p in cached.iterdir()}
    with pytest.raises(UnsafeGuidanceCode):
        app._prepare_guidance_program(None, 'task', {})
    assert not calls and {p.name:p.read_bytes() for p in cached.iterdir()} == before


def test_provider_error_is_not_misclassified_as_a_code_repair(tmp_path):
    app, calls = make_app(tmp_path, [RuntimeError('provider credentials unavailable')])
    with pytest.raises(RuntimeError, match='provider credentials'):
        app._prepare_guidance_program(None, 'task', {})
    assert len(calls) == 1
    assert app.vlm_agent.prompt_template == 'original task template'
    assert not list(tmp_path.rglob('validation_error.json'))


def test_preparation_failure_never_reuses_previous_completed_episode_identity(tmp_path):
    from main import Main
    app = Main.__new__(Main)
    app.mode_aware_runtime = SimpleNamespace(episode_id='previous-completed-episode')
    facts = []
    app.mode_gate_incidents = SimpleNamespace(record_fact=lambda **value:facts.append(value))
    app._record_preparation_failure(str(tmp_path / 'new-attempt'), ValueError('bad reward code'))
    assert app.mode_aware_runtime.episode_id.startswith('preparation-')
    assert facts[0]['episode_id'] == app.mode_aware_runtime.episode_id
    assert facts[0]['payload']['executed_steps'] == 0
    assert not facts[0]['payload']['native_failure_label_allowed']
    assert facts[0]['payload']['output_dir'] == str(tmp_path / 'new-attempt')
