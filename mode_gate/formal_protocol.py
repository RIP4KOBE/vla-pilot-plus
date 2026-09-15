"""Explicit, hash-checked formal controller migration at a warm attempt boundary."""
from dataclasses import asdict
import ast
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys

from .io_utils import AtomicJsonl, atomic_write_json

REPO = Path(__file__).resolve().parents[1]
REQUIRED_SOURCES = {'main.py', 'mode_gate/config.py', 'mode_gate/state_machine.py',
                    'mode_gate/runtime.py', 'mode_gate/formal_protocol.py',
                    'scripts/run_full_experiment.py', 'mode_gate/slow_loop.py',
                    'mode_gate/expansion_automation.py'}
PLANNER_ROLE_METHODS = {'_init_components', '_init_mode_gate', '_run_mode_gate',
                        'perform_task_for_episode', '_update_stage'}


def _checked_request(request):
    value = json.loads(request.read_text())
    if value.get('pid') != os.getpid() or value.get('schema_version') != 'formal-rollout-protocol-update-v1':
        raise ValueError('formal warm-update process/protocol mismatch')
    if set(value.get('source_sha256', {})) != REQUIRED_SOURCES:
        raise ValueError('formal warm-update source list mismatch')
    for name, expected in value['source_sha256'].items():
        if hashlib.sha256((REPO / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f'formal warm-update source hash mismatch: {name}')
    return value


def prepare_requested_main_methods():
    """Compatible bridge for the already-resident pre-update Main.run hook.

    The old warm hook explicitly reloads the formal driver before resetting a
    new attempt. At that boundary only, replace the five reviewed Main methods
    from the hash-checked local source. No module top-level code, constructor,
    model loader, simulator restore or arbitrary request-supplied code runs.
    Patching the existing class also preserves all existing bound references.
    """
    from .campaign import configuration
    output = Path(configuration()['root']) / 'formal_experiment'
    request = output / 'runtime_protocol_update.request.json'
    if not request.is_file():
        return None
    raw = json.loads(request.read_text())
    if raw.get('pid') != os.getpid() or not raw.get('reload_planner_role_methods', False):
        return None
    value = _checked_request(request)
    module = sys.modules.get('main')
    if module is None:
        return None  # Cold entry will construct Main from the current source.
    if Path(module.__file__).resolve() != (REPO / 'main.py').resolve():
        raise ValueError('resident Main belongs to a different checkout')
    target = module.Main
    digest = value['source_sha256']['main.py']
    if getattr(target, '_planner_role_methods_sha256', None) == digest:
        return None
    parsed = ast.parse((REPO / 'main.py').read_text(), filename=str(REPO / 'main.py'))
    cls = next(node for node in parsed.body if isinstance(node, ast.ClassDef) and node.name == 'Main')
    methods = [node for node in cls.body if isinstance(node, ast.FunctionDef)
               and node.name in PLANNER_ROLE_METHODS]
    if {node.name for node in methods} != PLANNER_ROLE_METHODS:
        raise ValueError('warm Planner role method set mismatch')
    # These compatible methods have no decorators/default expressions; avoid
    # introducing execution at definition time into this maintenance path.
    if any(node.decorator_list or node.args.defaults or any(node.args.kw_defaults) for node in methods):
        raise ValueError('warm Planner role methods contain definition-time expressions')
    namespace = {}
    exec(compile(ast.Module(body=methods, type_ignores=[]), str(REPO / 'main.py'), 'exec'),
         vars(module), namespace)
    for name in PLANNER_ROLE_METHODS:
        setattr(target, name, namespace[name])
    target._planner_role_methods_sha256 = digest
    record = {'event':'ONLINE_PLANNER_METHODS_UPDATED_WARM',
              'event_id':value['event_id'] + ':main-methods', 'pid':os.getpid(),
              'main_source_sha256':digest, 'methods':sorted(PLANNER_ROLE_METHODS),
              'model_constructor_called':False, 'live_simulator_modified':False}
    AtomicJsonl(output / 'protocol_updates.jsonl').append(record)
    return record


def prepare_requested_coordinators():
    """Reenter a revised driver after the existing checked Main reload.

    Without a request addressed to this exact PID this is a read-only no-op.
    Parsing the newly cancelled job must work before the next Main.run entry.
    """
    from .campaign import configuration
    request = Path(configuration()['root']) / 'formal_experiment/runtime_protocol_update.request.json'
    if not request.is_file() or json.loads(request.read_text()).get('pid') != os.getpid():
        return
    _checked_request(request)
    for name in ('mode_gate.slow_loop', 'mode_gate.expansion_automation',
                 'run_full_experiment', 'scripts.run_full_experiment'):
        if name in sys.modules:
            importlib.reload(sys.modules[name])


def apply_requested_warm_update(runner):
    """Keep model objects; update controller methods/config only on an explicit request.

    Called before Main.run resets a prescribed new attempt. Never called from
    an active action chunk, and never restores a live object pose or old label.
    """
    cfg = getattr(runner, 'cfg', None)
    if cfg is None or not getattr(cfg, 'mode_gate', None):
        return None
    root = Path(cfg.mode_gate.registry_root).resolve().parent
    request = root / 'formal_experiment/runtime_protocol_update.request.json'
    if not request.is_file():
        return None
    value = _checked_request(request)
    prepare_requested_main_methods()
    policy = runner.policy
    encoder = runner.theta0_scene_encoder
    runtime = runner.mode_aware_runtime
    verifier = runtime.verifier
    if verifier is None or runner.mode_gate_registry.active().controller_mode != 'learned_verifier':
        raise RuntimeError('formal warm-update needs the existing initialized verifier')
    # No policy/backbone/verifier module is reloaded or constructed here.
    modules = {}
    for name in ('mode_gate.config', 'mode_gate.state_machine', 'mode_gate.runtime',
                 'mode_gate.slow_loop', 'mode_gate.expansion_automation'):
        modules[name] = importlib.reload(importlib.import_module(name))
    for name in ('run_full_experiment', 'scripts.run_full_experiment'):
        if name in sys.modules:
            importlib.reload(sys.modules[name])
    from omegaconf import OmegaConf
    before = OmegaConf.to_container(cfg.mode_gate, resolve=True)
    for key, setting in {'controller_mode': 'learned_verifier', 'require_learned_verifier': True,
                         'require_complete_rollout_before_expansion': True}.items():
        OmegaConf.update(cfg, 'mode_gate.' + key, setting, force_add=True)
    updated = modules['mode_gate.config'].ModeGateConfig.from_mapping(
        OmegaConf.to_container(cfg.mode_gate, resolve=True))
    runtime.__class__ = modules['mode_gate.runtime'].CandidateRuntime
    runtime.config = updated
    runtime.gate.config = updated
    runtime.controller = modules['mode_gate.state_machine'].EpisodeChunkController(updated)
    runner.mode_gate_config = updated
    runner.mode_gate_controller = runtime
    # Main was reloaded by the existing initializer's checked warm-resume hook.
    manager = runner.mode_gate_deployment_manager
    manager.verifier_loader = runner._fresh_load_registry_verifier
    manager.canary = runner._deployment_canary
    if (runner.policy is not policy or runner.theta0_scene_encoder is not encoder
            or runtime.verifier is not verifier):
        raise RuntimeError('formal warm-update changed a resident model')
    record = {'event': 'FORMAL_PROTOCOL_UPDATED_WARM', 'event_id': value['event_id'],
              'pid': os.getpid(), 'source_sha256': value['source_sha256'],
              'previous_config': before, 'applied_config': asdict(updated),
              'policy_object_unchanged': True, 'frozen_encoder_object_unchanged': True,
              'verifier_object_unchanged': True, 'old_labels_modified': False,
              'scheduled_task': False}
    output = root / 'formal_experiment'
    AtomicJsonl(output / 'protocol_updates.jsonl').append(record)
    atomic_write_json(Path(runner.output_dir) / 'config.json', OmegaConf.to_container(cfg, resolve=True))
    request.rename(request.with_suffix('.applied.json'))
    return record
