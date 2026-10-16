#!/usr/bin/env python3
"""Explicit finite v44 initialization, Planner labels/retrain, with one retained warm policy."""
from pathlib import Path
import argparse
from dataclasses import asdict
import fcntl
import hashlib
import json
import os
import sys
import time
import traceback

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


def reload_main_in_place(runner, expected_sha256):
    """Opt-in, checked method reload at a paused boundary; never construct weights.

    This is only for compatible Main method fixes, not model/config migrations.
    The caller has already left the old episode stack and will restore a new
    prescribed attempt before invoking these methods.
    """
    import importlib
    source = REPO / 'rsi/main.py'
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest != expected_sha256:
        raise ValueError('Main source does not match the explicit warm-reload digest')
    if runner is None:
        return {'source_sha256':digest, 'model_resident':False}
    policy = runner.policy
    encoder = getattr(runner, 'theta0_scene_encoder', None)
    revision = None
    if hasattr(runner, 'mode_gate_source_revision'):
        from mode_gate.preflight import source_revision
        revision = source_revision(REPO)
    module = importlib.reload(importlib.import_module('rsi.main'))
    # Main uses an ordinary instance dictionary; replacing the compatible
    # class changes methods only, preserving policy/encoder tensors and state.
    runner.__class__ = module.Main
    if runner.policy is not policy or getattr(runner, 'theta0_scene_encoder', None) is not encoder:
        raise RuntimeError('warm method reload unexpectedly changed a model object')
    if revision is not None:
        runner.mode_gate_source_revision = revision
    return {'source_sha256':digest, 'model_resident':True, 'weights_reloaded':False}


def wait_for_warm_resume(output, runner, report):
    while not (output/'stop.request').exists():
        request = output/'resume.request'
        if not request.exists():
            time.sleep(2)
            continue
        handled = output/f'resume_{time.time_ns()}.handled'
        request.rename(handled)
        try:
            text = handled.read_text().strip()
            # Existing plain-text operator resume requests remain supported.
            options = json.loads(text) if text.startswith('{') else {}
            digest = options.get('reload_main_sha256')
            reloaded = reload_main_in_place(runner, digest) if digest else None
            report('RESUMING_WARM', model_resident=runner is not None, main_reload=reloaded)
            return True
        except Exception as error:
            # A rejected maintenance request must not unload an otherwise
            # healthy warm model. Wait for a corrected explicit request.
            report('ERROR_WARM', error=f'{type(error).__name__}: {error}',
                   model_resident=runner is not None, resume_path=str(request))
    return False


def initialization_settings():
    from mode_gate.campaign import configuration
    settings = dict(configuration()['initialization'])
    keys = settings.get('task_keys', [])
    if len(keys) != 2 or len(set(keys)) != 2:
        raise ValueError('verifier initialization must be restricted to exactly two tasks')
    return settings


def start_formal_with_warm_runner(args, runner, registry, report):
    """Synchronous phase handoff within this worker, never a scheduler/process."""
    from types import SimpleNamespace
    from mode_gate.io_utils import atomic_write_json
    from scripts.run_full_experiment import run as run_formal
    active = registry.active()
    if active is None or active.controller_mode != 'learned_verifier' or not active.verifier_id:
        raise RuntimeError('formal handoff requires a trained, independently accepted verifier')
    output = args.root.resolve()/'formal_experiment'
    settings = initialization_settings()
    record = {'pid':os.getpid(), 'formal_output':str(output), 'verifier_id':active.verifier_id,
              'policy_id':active.policy_id, 'same_process':True,
              'model_resident':runner is not None, 'scheduled_task':False,
              'started_at':time.time()}
    atomic_write_json(args.root.resolve()/'initialization/formal_handoff.json', record)
    report('FORMAL_HANDOFF', formal_started=True, **{k:v for k,v in record.items() if k!='pid'})
    run_formal(SimpleNamespace(root=args.root, manifest=args.manifest, output=output,
        gpu_index=args.gpu, passes=int(settings.get('formal_passes',1))), warm_runner=runner)


def continue_driver_if_requested(runner):
    """Transfer an older paused driver to this implementation without reloading weights.

    Main calls this only at run entry, after the previous episode stack has
    unwound. The request is pinned to this PID, this script hash and the
    initialization paths; no arbitrary entry point or command is accepted.
    """
    from types import SimpleNamespace
    from mode_gate.io_utils import atomic_write_json
    root = Path(runner.cfg.mode_gate.registry_root).resolve().parent
    if Path(runner.cfg.mode_gate.slow_loop_root).resolve() != root/'initialization/unused_slow_loop':
        return
    request = root/'initialization/driver_handoff.request'
    if not request.is_file():
        return
    options = json.loads(request.read_text())
    if options.get('pid') != os.getpid():
        raise ValueError('warm initialization handoff PID mismatch')
    digest = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    if options.get('driver_sha256') != digest:
        raise ValueError('warm initialization driver hash mismatch')
    manifest = Path(options['manifest']).resolve()
    if not manifest.is_file():
        raise ValueError('warm initialization manifest is missing')
    request.rename(request.with_name(f'driver_handoff_{time.time_ns()}.handled'))
    atomic_write_json(root/'initialization/driver_handoff.json', {
        'pid':os.getpid(), 'driver_sha256':digest, 'model_reloaded':False,
        'old_driver_replaced_in_process':True, 'started_at':time.time()})
    reload_driver_modules()
    # The outer initializer still owns its file lock. It must never resume its
    # old, five-task local plan after the new driver/formal phase finishes.
    run(SimpleNamespace(root=root, manifest=manifest, gpu=int(str(runner.device).split(':')[-1])),
        warm_runner=runner, inherited_lock=True)
    raise SystemExit(0)


def reload_driver_modules():
    """Reload only the coordinator modules changed by a checked warm handoff."""
    import importlib
    for name in ('mode_gate.runtime', 'mode_gate.experience_planner',
                 'mode_gate.verifier_training', 'mode_gate.verifier_refresh',
                 'run_full_experiment', 'scripts.run_full_experiment'):
        if name in sys.modules:
            importlib.reload(sys.modules[name])


def plan_contexts(client, manifest, completed):
    from mode_gate.campaign import selected_tasks
    allowed = set(initialization_settings()['task_keys'])
    tasks = [task for task in selected_tasks(manifest) if task['task_key'] in allowed]
    if {task['task_key'] for task in tasks} != allowed:
        raise ValueError('initialization tasks are missing from the campaign manifest')
    available = {x['task_key']: sorted(set(s for k, values in x['splits'].items()
                    if k.startswith('verifier_') or k == 'demo_online_pool' for s in values), key=int) for x in tasks}
    used = {(x['task_key'], str(x['init_state_id'])) for x in completed}
    available = {key:[str(s) for s in states if (key,str(s)) not in used]
                 for key,states in available.items()}
    available = {key:states for key,states in available.items() if states}
    if not available:
        raise ValueError('initialization state bank exhausted; independent head acceptance still pending')
    schema = {'type':'object','required':['contexts','reason'],'additionalProperties':False,
              'properties':{'reason':{'type':'string'},'contexts':{'type':'array','minItems':1,'items':{
                  'type':'object','required':['task_key','init_state_id'],'additionalProperties':False,
                  'properties':{'task_key':{'enum':list(available)},'init_state_id':{'type':'string'}}}}}}
    response = client.request(purpose='verifier_initialization_plan', schema=schema,
        prompt='从全新的 v44 开始初始化候选轨迹 verifier，不训练 policy。选择下一小批真实经历的任务和初始状态，'
               '只使用列出的两个任务，不扩展到第三个任务；可在这两个任务内选不同初始状态以获取独立经历。'
               '考虑成功/失败证据和独立检查；没有固定数据比例或必须采满的数量。'
               '每条最多50个10步chunk，40个完整候选，baseline实际固定80/10引导。'
               '你将在每次实际经历后查看视频/结果，自主标注、选训练数据和独立经历，决定是否开始训练。'
               '不要用未实际继续的EXPANSION冒充50次失败，不要用正式封存测评状态。'
               '初始化完成并接受新head后，现有worker会自动进入正式20任务实验。\n'
               + json.dumps({'available':available,'completed':completed}, ensure_ascii=False))
    result = json.loads(response.text)
    selected = set()
    rows = []
    for choice in result['contexts']:
        key, state = choice['task_key'], str(choice['init_state_id'])
        if key not in available or state not in available[key] or (key,state) in selected:
            raise ValueError('Planner selected duplicate/out-of-scope initialization context')
        selected.add((key,state))
        task = next(x for x in tasks if x['task_key'] == key)
        token = hashlib.sha256(f'candidate-init-v2:{key}:{state}'.encode()).digest()
        rows.append({**task, 'context_id':token.hex(), 'init_state_id':state,
                     'env_seed':int.from_bytes(token[:4],'big'), 'policy_seed':int.from_bytes(token[4:12],'big') % (2**63-1)})
    return {'contexts':rows,'reason':result['reason'],'planner_provenance':dict(response.planner_metadata)}

def run(args, *, warm_runner=None, inherited_lock=False):
    os.environ.update(PYOPENGL_PLATFORM='egl', MUJOCO_GL='egl', HF_HUB_OFFLINE='1',
                      TRANSFORMERS_OFFLINE='1', TOKENIZERS_PARALLELISM='false')
    os.environ.setdefault('PYTORCH_CUDA_ALLOC_CONF','expandable_segments:True')
    from dotenv import load_dotenv
    load_dotenv(REPO / '.env', override=False)
    from omegaconf import OmegaConf
    from mode_gate.campaign import demonstration_bank, baseline_steering_profile
    from mode_gate.io_utils import AtomicJsonl, atomic_write_json
    from mode_gate.checkpoint_math import checkpoint_digest
    from mode_gate.registry import PolicyRegistry
    from mode_gate.planner_account import CodexPlannerClient
    from mode_gate.incidents import IncidentMemory
    from mode_gate.verifier_refresh import VerifierRefreshCoordinator
    from mode_gate.verifier_training import VerifierTrainingConfig
    from run_full_experiment import make_config
    import torch
    from mode_gate.verifier import GroundedCapabilityVerifier

    root, output = args.root.resolve(), args.root.resolve() / 'initialization'
    output.mkdir(parents=True,exist_ok=True)
    lock = None
    if not inherited_lock:
        lock = (output/'worker.lock').open('a+b')
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    def report(state, **fields):
        value={'state':state,'pid':os.getpid(),'updated_at':time.time(),'phase':'verifier_initialization',
               'gpu':args.gpu,'formal_started':False,**fields}
        atomic_write_json(output/'status.json',value)
        print(json.dumps(value,ensure_ascii=False),flush=True)
    settings = initialization_settings()
    allowed_task_keys = set(settings['task_keys'])
    report('PREPARING', model_resident=warm_runner is not None)
    atomic_write_json(output/'scope.json', settings)
    manifest=json.loads(args.manifest.read_text())
    bank=demonstration_bank(manifest)
    atomic_write_json(root/'demonstration_bank.json',{'tasks':bank,'task_count':len(bank),
        'demonstrations':sum(x['demonstrations'] for x in bank),'videos':sum(x['video_count'] for x in bank)})
    profile=baseline_steering_profile()
    atomic_write_json(root/'steering_parity.json',profile)
    registry=PolicyRegistry(root/'registry')
    checkpoint=Path(profile['policy']['pretrained_path'])
    if registry.active() is None:
        report('INITIALIZING_V44_REGISTRY')
        registry.bootstrap_base_policy(checkpoint_path=checkpoint,digest=checkpoint_digest(checkpoint),
            metadata={'source':'v44_original','campaign':'env_position20_20260914'},policy_id='pi05_v44_original',
            manifest_hash=manifest['manifest_sha256'])
    if registry.active().policy_id != 'pi05_v44_original':
        raise ValueError('initialization must start from original v44, not a merged policy')
    seed_path=output/'untrained_head.pt'
    if not seed_path.exists():
        torch.manual_seed(20260914)
        head=GroundedCapabilityVerifier().to(f'cuda:{args.gpu}')
        torch.save({'state_dict':{k:v.detach().cpu() for k,v in head.state_dict().items()},
                    'trained':False,'backbone_frozen':True,'role':'initialization_only'},seed_path)
        del head
    client=CodexPlannerClient()
    ledger=AtomicJsonl(output/'episodes.jsonl')
    runner=warm_runner
    round_index=0
    try:
        while not (output/'stop.request').exists():
          try:
            if (output/'completion.json').is_file() and settings.get('auto_start_formal'):
                start_formal_with_warm_runner(args, runner, registry, report)
                return
            completed=list(ledger.iter_valid())
            if any(row['task_key'] not in allowed_task_keys for row in completed):
                raise ValueError('completed initialization includes a task outside the user-selected pair')
            plan_path=output/f'plan_{round_index:03d}.json'
            if not plan_path.exists():
                report('PLANNER_SELECTING_INITIALIZATION_CONTEXTS',completed_contexts=len(completed))
                atomic_write_json(plan_path,plan_contexts(client,manifest,completed))
            plan=json.loads(plan_path.read_text())
            contexts=[context for context in plan['contexts'] if context['task_key'] in allowed_task_keys]
            atomic_write_json(output/f'effective_plan_{round_index:03d}.json', {
                **plan, 'contexts':contexts, 'task_keys':settings['task_keys'],
                'original_plan':str(plan_path), 'user_scope_override':True})
            for context in contexts:
                if (output/'stop.request').exists():
                    break
                done=next((x for x in completed if x['context_id']==context['context_id']),None)
                context_dir=output/'rollouts'/context['context_id']
                if not done:
                    # A failed infrastructure attempt is retained separately,
                    # never overwritten or counted as a completed experience.
                    attempt=1
                    while (context_dir/f'attempt_{attempt:03d}').exists():
                        attempt+=1
                    run_dir=context_dir/f'attempt_{attempt:03d}'
                    cfg=make_config(context,run_dir,root,args.gpu)
                    cfg.mode_gate.auto_start_expansion_worker=False
                    cfg.mode_gate.controller_mode='fixed_budget_50'
                    cfg.mode_gate.require_learned_verifier=False
                    cfg.mode_gate.require_complete_rollout_before_expansion=False
                    cfg.mode_gate.slow_loop_root=str(output/'unused_slow_loop')
                    cfg.main.initialization_posthoc_only=True
                    cfg.main.use_vlm_stage_recognition=False
                    # Preserve a separate initialization ledger; never count these as formal outcomes.
                    run_dir.mkdir(parents=True,exist_ok=True)
                    atomic_write_json(run_dir/'config.json',OmegaConf.to_container(cfg,resolve=True))
                    report('LOADING_V44' if runner is None else 'SAMPLING_INITIALIZATION',
                           task=context['task_key'],init_state_id=context['init_state_id'],output=str(run_dir))
                    if runner is None:
                        from rsi.main import Main
                        runner=Main(cfg)
                    else:
                        was_posthoc = bool(runner.config.get('initialization_posthoc_only',False))
                        runner.adapter.close()
                        runner.adapter.__init__(None,OmegaConf.to_container(cfg.backend.libero,resolve=True),device=runner.device)
                        runner.cfg,runner.config=cfg,cfg.main
                        runner.output_dir=str(run_dir)+'/'
                        if not was_posthoc:
                            from mode_gate.config import ModeGateConfig
                            runner.mode_gate_config=ModeGateConfig.from_mapping(
                                OmegaConf.to_container(cfg.mode_gate,resolve=True))
                            policy=runner.policy
                            runner._init_mode_gate()
                            if runner.policy is not policy:
                                raise RuntimeError('initialization reconfiguration reloaded the policy')
                    report('SAMPLING_INITIALIZATION', task=context['task_key'],
                           init_state_id=context['init_state_id'],output=str(run_dir),
                           attempt=attempt,model_resident=True,completed_contexts=len(completed))
                    runner.run()
                    done={'event_id':context['context_id'],'context_id':context['context_id'],
                          'task_key':context['task_key'],'init_state_id':context['init_state_id'],
                          'native_success':bool(runner.success_count),'policy_id':'pi05_v44_original',
                          'output_dir':str(run_dir),'formal_result':False}
                    ledger.append(done)
                    completed.append(done)
                report('PLANNER_LABELING_AND_RETRAIN_REVIEW',context_id=context['context_id'],
                       completed_contexts=len(completed),model_resident=runner is not None)
                refresh=VerifierRefreshCoordinator(registry=registry,incidents=IncidentMemory(root/'incidents'),
                    output_root=output/'reviews'/context['context_id'],
                    config=VerifierTrainingConfig(device=f'cuda:{args.gpu}',warm_start_artifact=None),
                    allowed_task_keys=tuple(settings['task_keys'])).run(current={
                        'initialization_only':True, 'allowed_task_keys':settings['task_keys'],
                        'completed_tasks':sorted({row['task_key'] for row in completed}),
                        'auto_start_formal_after_acceptance':bool(settings.get('auto_start_formal'))})
                if refresh['refreshed']:
                    report('INITIALIZED_WARM',verifier_id=registry.active().verifier_id,
                           completed_contexts=len(completed),model_resident=runner is not None)
                    atomic_write_json(output/'completion.json',refresh)
                    if settings.get('auto_start_formal'):
                        start_formal_with_warm_runner(args, runner, registry, report)
                        return
                    while not (output/'stop.request').exists():
                        time.sleep(2)
                    return
            round_index+=1
          except Exception as error:
            traceback.print_exc()
            report('ERROR_WARM',error=f'{type(error).__name__}: {error}',model_resident=runner is not None,
                   resume_path=str(output/'resume.request'))
            if runner is not None and getattr(runner, 'mode_aware_runtime', None) is not None:
                runner.mode_gate_incidents.record_fact(
                    episode_id=runner.mode_aware_runtime.episode_id, context_id='',
                    kind='initialization_infrastructure_abort', payload={
                        'error':f'{type(error).__name__}: {error}',
                        'native_failure_label_allowed':False,'formal_result':False})
            # Explicit finite worker recovery, not a scheduler. Retry the
            # interrupted context on its prescribed initial state, retaining
            # the exact same loaded policy and frozen feature backbone.
            wait_for_warm_resume(output, runner, report)
    finally:
        if runner is not None:
            runner.adapter.close()
        if lock is not None:
            lock.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path('/shared/hengyil6/vls/self_improve/fixed_budget_50/env_position20_20260914'))
    parser.add_argument('--manifest',type=Path,default=Path('/shared/hengyil6/vls/self_improve/protocol/joint_eval_manifest.json'))
    parser.add_argument('--gpu',type=int,default=6)
    run(parser.parse_args())
