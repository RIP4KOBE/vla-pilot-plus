#!/usr/bin/env python3
"""Run the full controller breadth-first on LIBERO-PRO, keeping models warm.

This is an explicitly launched experiment worker, not a scheduled task. A
completed plan keeps the process resident; increasing --passes in plan.json
and placing resume.request in its output directory continues with new online
states. stop.request releases the worker at an episode boundary.
--pause-after-slow-loop arms a durable pause after an existing slow loop,
without interrupting its evaluation, verifier refresh, or deployment.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import traceback

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

# Compatibility with a running pre-update formal driver: its existing checked
# attempt-boundary hook reloads this module, but not Main's resident class.
# A PID/hash-pinned explicit request is required; ordinary imports are no-ops.
def _prepare_requested_method_update():
    from mode_gate import formal_protocol
    from mode_gate.campaign import configuration
    request = Path(configuration()['root']) / 'formal_experiment/runtime_protocol_update.request.json'
    if request.is_file():
        value = json.loads(request.read_text())
        if value.get('pid') == os.getpid() and value.get('reload_planner_role_methods'):
            import importlib
            importlib.reload(formal_protocol).prepare_requested_main_methods()


_prepare_requested_method_update()


def now():
    return datetime.now(timezone.utc).isoformat()


def contexts_from_manifest(manifest, passes):
    from mode_gate.eval_manifest import validate_libero_pro_manifest
    validate_libero_pro_manifest(manifest)
    from mode_gate.campaign import selected_tasks
    tasks = selected_tasks(manifest)
    if not 1 <= passes <= min(len(task['splits']['demo_online_pool']) for task in tasks):
        raise ValueError('passes must fit the existing non-sealed online-state pool')
    result = []
    for pass_index in range(passes):
        for task in tasks:
            init_state = str(task['splits']['demo_online_pool'][pass_index])
            key = f"full-architecture-v1\0{manifest['manifest_sha256']}\0{task['task_key']}\0{init_state}"
            digest = hashlib.sha256(key.encode()).digest()
            result.append({
                'context_id': digest.hex(), 'pass_index': pass_index,
                'benchmark': 'LIBERO-PRO', 'task_key': task['task_key'],
                'suite': task['suite'], 'runtime_suite': task['runtime_suite'],
                'task_id': task['task_id'], 'task_index': task['task_index'],
                'perturbation_variant': task['perturbation_variant'],
                'init_state_id': init_state, 'source_split': 'demo_online_pool',
                'env_seed': int.from_bytes(digest[:4], 'big'),
                'policy_seed': int.from_bytes(digest[4:12], 'big') % (2**63 - 1),
            })
    return result


def make_config(context, run_dir, root, gpu):
    from hydra import compose, initialize_config_dir
    with initialize_config_dir(version_base=None, config_dir=str(REPO / 'rsi/configs')):
        cfg = compose(config_name='config', overrides=[
            'backend=libero', f'device=cuda:{gpu}',
            f"backend.libero.suite_name={context['runtime_suite']}",
            f"backend.libero.task_ids_filter=[{context['task_index']}]",
            'main.episode_num=1', 'main.use_guidance=true',
            'main.use_vlm_stage_recognition=true', 'main.fail_on_episode_error=true',
            'perception.gemini_grounding.enabled=false',
            f"main.init_state_id={context['init_state_id']}",
            f"main.env_seed={context['env_seed']}",
            f"main.policy_seed={context['policy_seed']}",
            f'main.output_dir={run_dir}',
            'mode_gate.enabled=true', 'mode_gate.controller_mode=learned_verifier',
            'mode_gate.require_learned_verifier=true',
            'mode_gate.require_complete_rollout_before_expansion=true',
            'mode_gate.baseline_kind=', 'mode_gate.auto_start_expansion_worker=true',
            'mode_gate.retry_budget=50', 'mode_gate.label_version=fixed_budget_50-v2',
            f'mode_gate.registry_root={root / "registry"}',
            f'mode_gate.incident_root={root / "incidents"}',
            f'mode_gate.snapshot_root={root / "snapshots"}',
            f'mode_gate.slow_loop_root={root / "slow_loop"}',
            'mode_gate.planner_max_provider_calls=10000',
            f'mode_gate.planner_call_ledger={root / "audit/incidents/fixed_budget_50/factual_gemini_provider_calls.jsonl"}',
            'mode_gate.verifier_thinking_level=medium', 'perception.gemini.thinking_level=ultra',
        ])
        from mode_gate.campaign import apply_baseline_steering
        apply_baseline_steering(cfg)
        from mode_gate.campaign import configuration
        cfg.main.planner_steering_enabled = bool(
            configuration()['formal_execution'].get('planner_steering_enabled', True))
        return cfg


def run(args, *, warm_runner=None):
    # Set graphics/offline options before importing the existing Main runtime.
    os.environ.update(PYOPENGL_PLATFORM='egl', MUJOCO_GL='egl', HF_HUB_OFFLINE='1',
                      TRANSFORMERS_OFFLINE='1', TOKENIZERS_PARALLELISM='false')
    os.environ.setdefault('PYTORCH_CUDA_ALLOC_CONF', 'expandable_segments:True')
    from dotenv import load_dotenv
    load_dotenv(REPO / '.env', override=False)
    from omegaconf import OmegaConf
    from mode_gate.io_utils import AtomicJsonl, atomic_write_json
    from mode_gate.experiment_contract import label_contract_payload
    from mode_gate.registry import PolicyRegistry
    from mode_gate.expansion_automation import wait_for_expansion_demonstrations
    from mode_gate.slow_loop import MANDATORY_DEMOS_PROTOCOL, SlowLoopStore
    from mode_gate.preflight import source_revision
    from mode_gate.planner_account import load_planner_account_config
    from mode_gate.data_pipeline import NATIVE_DEMO_ACCEPTANCE
    from mode_gate.campaign import configuration
    from mode_gate.experiment_supervisor import apply_pause_after_slow_loop
    from rsi.main import Main

    root = args.root.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    lock = (output / 'worker.lock').open('a+b')
    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    manifest = json.loads(args.manifest.read_text())
    contexts = contexts_from_manifest(manifest, args.passes)
    plan_path = output / 'plan.json'
    if plan_path.exists():
        plan = json.loads(plan_path.read_text())
        if plan['manifest_sha256'] != manifest['manifest_sha256'] or plan['gpu_index'] != args.gpu_index:
            raise ValueError('existing experiment identity differs')
        contexts = contexts_from_manifest(manifest, int(plan['passes']))
    else:
        plan = {
            'schema_version': 'libero-pro-full-architecture-plan-v1',
            'experiment_role': 'full_architecture_online', 'created_at': now(),
            'manifest_sha256': manifest['manifest_sha256'], 'manifest_path': str(args.manifest),
            'passes': args.passes, 'gpu_index': args.gpu_index, 'task_count': 20,
            'contexts': contexts, 'label_config': label_contract_payload(),
            'source_revision': source_revision(REPO), 'final_seal_opened': False,
            'initialization_data_used_as_heldout': False, 'keep_models_warm': True,
            'expansion_barrier': 'slow_loop_complete_before_next_fast_loop',
            'slow_loop_auto_execute': True, 'persistent_teleop_portal': False,
            'collection_mode': 'precollected_native_success', 'planner_auth_mode': 'chatgpt',
            'diversity_required': True,
            'slow_loop_protocol': MANDATORY_DEMOS_PROTOCOL,
            'demonstration_trigger': 'EXPANSION_ONLY',
            'signature_reuse_enabled': True,
            'capability_labels': 'planner_revisioned_evidence',
            'top_level_planner': load_planner_account_config(),
            'gemini_api_enabled': False,
            'demo_acceptance_version': NATIVE_DEMO_ACCEPTANCE,
            'demo_success_authority': 'LIBERO-PRO native predicate during collection',
            'demo_replay_role': 'diagnostic_only',
            'demo_replay_state_error_role': 'diagnostic_only',
            'mandatory_current_task_training_after_expansion': 'unless_planner_remedy_passes_current_policy_validation',
            'demonstration_recollection': False,
            'formal_execution': configuration()['formal_execution'],
            'merge_method': 'planner_uniform_language_vision_action',
            'perturbation_variants': ['use_environment', 'use_swap'],
            'skill_collection_config': json.loads((REPO / 'configs/skill_collection.json').read_text()),
        }
        atomic_write_json(plan_path, plan)
    ledger = AtomicJsonl(output / 'episodes.jsonl')
    completed = {row['context_id'] for row in ledger.iter_valid() if row.get('event') == 'EPISODE_COMPLETED'}
    registry = PolicyRegistry(root / 'registry')
    active = registry.active()
    if active is None or active.controller_mode != 'learned_verifier':
        raise RuntimeError('initialize and independently review the candidate verifier before formal experiments')
    from mode_gate.verifier import DeployedVerifierPredictor
    DeployedVerifierPredictor(registry.root / 'verifiers' / str(active.verifier_id))
    status = {'pid': os.getpid(), 'started_at': now(), 'plan_path': str(plan_path),
              'task_count': 20, 'contexts_planned': len(contexts), 'gpu_device': f'cuda:{args.gpu_index}',
              'initial_deployment': asdict(active), 'experiment_role': 'full_architecture_online'}
    pause_path = output / 'pause_after_slow_loop.request.json'
    if pause_path.is_file():
        status['pause_after_slow_loop_job_id'] = json.loads(pause_path.read_text())['slow_loop_job_id']
        status['pause_requires_explicit_resume'] = True

    def report(state, **fields):
        status.update(state=state, updated_at=now(), contexts_completed=len(completed), **fields)
        atomic_write_json(output / 'status.json', status)
        print(json.dumps(status), flush=True)

    report('STARTING')
    runner = warm_runner

    def report_demo_wait(progress):
        report(progress['state'],
               waiting_slow_loop_job_id=progress['slow_loop_job_id'],
               waiting_task_id=progress['task_id'],
               waiting_ticket_id=progress['ticket_id'],
               waiting_slow_loop_state=progress['slow_loop_state'],
               teleop_url=progress.get('teleop_url'), slow_loop_error=progress.get('error'),
               model_resident=runner is not None)

    def pause_requested():
        return any((output / name).exists() for name in ('stop.request', 'park.request'))

    try:
        while not (output / 'stop.request').exists():
            if not (output / 'park.request').exists():
                apply_pause_after_slow_loop(root=root, output=output)
            if (output / 'park.request').exists():
                report('PARKED_WARM', model_resident=runner is not None)
                while (output / 'park.request').exists() and not (output / 'stop.request').exists():
                    time.sleep(2)
                continue
            # A resumed plan must not skip outstanding tickets from its own
            # completed episodes. This also covers pre-barrier run ledgers.
            outstanding_jobs = {job_id for episode in ledger.iter_valid()
                                for job_id in episode.get('slow_loop_jobs', ())}
            # Include a parked episode that triggered expansion but has not
            # yet reached the episode-completed ledger boundary.
            for path in (output / 'rollouts').glob('*/attempt_*/episode_*/mode_gate*expansion*.json'):
                job_id = json.loads(path.read_text()).get('slow_loop_job_id')
                if job_id:
                    outstanding_jobs.add(job_id)
            try:
                for job_id in outstanding_jobs:
                    wait_for_expansion_demonstrations(
                        store=SlowLoopStore(root / 'slow_loop'), job_id=job_id,
                        on_update=report_demo_wait,
                        stop_requested=pause_requested, wait_for_completion=True,
                    )
            except InterruptedError:
                if pause_requested():
                    continue
                raise
            # A recovery may have been waiting for an unfinished slow loop
            # without a resident policy. Do not start a new attempt or task
            # after the user-selected boundary has completed.
            if apply_pause_after_slow_loop(root=root, output=output):
                continue
            # Recover an interrupted review before starting another episode;
            # completed physical rollouts must never be repeated just for this.
            from mode_gate.verifier_refresh import VerifierRefreshCoordinator
            from mode_gate.verifier_training import VerifierTrainingConfig
            from mode_gate.incidents import IncidentMemory
            for finished in ledger.iter_valid():
                if finished.get('event') != 'EPISODE_COMPLETED':
                    continue
                review_root = output / 'verifier_reviews' / finished['context_id']
                if not (review_root / 'refresh_result.json').is_file():
                    report('VERIFIER_REVIEW', review_context=finished['context_id'], model_resident=runner is not None)
                    VerifierRefreshCoordinator(registry=registry,
                        incidents=IncidentMemory(root / 'incidents'), output_root=review_root,
                        config=VerifierTrainingConfig(device=f'cuda:{args.gpu_index}')).run()
            pending = [(index, item) for index, item in enumerate(contexts) if item['context_id'] not in completed]
            if not pending:
                report('COMPLETE_WARM', model_resident=runner is not None)
                while not (output / 'resume.request').exists() and not (output / 'stop.request').exists():
                    time.sleep(2)
                if (output / 'stop.request').exists():
                    break
                (output / 'resume.request').unlink()
                updated = json.loads(plan_path.read_text())
                if updated['manifest_sha256'] != manifest['manifest_sha256'] or updated['gpu_index'] != args.gpu_index:
                    raise ValueError('cannot change the identity of a warm experiment')
                contexts = contexts_from_manifest(manifest, int(updated['passes']))
                status['contexts_planned'] = len(contexts)
                continue
            index, context = pending[0]
            attempts_root = output / 'rollouts' / context['context_id']
            attempts_root.mkdir(parents=True, exist_ok=True)
            attempt = len(list(attempts_root.glob('attempt_*'))) + 1
            run_dir = attempts_root / f'attempt_{attempt:03d}'
            run_dir.mkdir()
            cfg = make_config(context, run_dir, root, args.gpu_index)
            atomic_write_json(run_dir / 'config.json', OmegaConf.to_container(cfg, resolve=True))
            report('LOADING' if runner is None else 'SWITCHING_TASK', current_context=index + 1,
                   current_task=context['task_id'], runtime_suite=context['runtime_suite'],
                   init_state_id=context['init_state_id'], current_output=str(run_dir))
            try:
                if runner is None:
                    runner = Main(cfg)
                else:
                    # Keep the adapter identity: policy, renderer, projectors,
                    # scene encoder, and tracker all retain references to it.
                    env_config = OmegaConf.to_container(cfg.backend.libero, resolve=True)
                    env_config['episode_num'] = 1
                    runner.adapter.close()
                    runner.adapter.__init__(None, env_config, device=runner.device)
                    runner.cfg, runner.config = cfg, cfg.main
                    runner.output_dir = str(run_dir) + '/'
                    # Initialization uses a fixed-budget, no-expansion runtime.
                    # Refresh controller bindings once on entry to formal work,
                    # retaining the already-loaded policy and frozen backbone.
                    if not runner.mode_gate_config.auto_start_expansion_worker:
                        from mode_gate.config import ModeGateConfig
                        runner.mode_gate_config = ModeGateConfig.from_mapping(
                            OmegaConf.to_container(cfg.mode_gate, resolve=True))
                        resident_policy = runner.policy
                        runner._init_mode_gate()
                        if runner.policy is not resident_policy:
                            raise RuntimeError('formal handoff unexpectedly replaced the warm policy')
                        if (runner.config.get('planner_steering_enabled', True)
                                and runner.config.get('use_vlm_stage_recognition', True)
                                and runner.gemini_stage_recognizer is None):
                            from rsi.core.gemini_grounder import create_gemini_stage_recognizer
                            runner.gemini_stage_recognizer=create_gemini_stage_recognizer(
                                OmegaConf.to_container(cfg.perception.gemini,resolve=True))
                if (not runner.config.get('use_guidance')
                        or runner.config.get('initialization_posthoc_only',False)):
                    raise RuntimeError('formal execution requires VLS guidance, not initialization routing')
                if (runner.config.get('planner_steering_enabled', True)
                        and (not runner.config.get('use_vlm_stage_recognition')
                             or runner.gemini_stage_recognizer is None)):
                    raise RuntimeError('online Planner was enabled without an initialized stage recognizer')
                if runner.mode_gate_config.controller_mode != 'learned_verifier':
                    raise RuntimeError('formal execution forbids fixed-budget routing; retain the initialized verifier')
                assert runner.mode_gate_config.auto_start_expansion_worker
                assert not runner.mode_gate_config.baseline_kind
                runner.expansion_wait_callback = report_demo_wait
                runner.expansion_stop_requested = pause_requested
                runner.expansion_full_cycle = True
                report('RUNNING', model_resident=True, active_deployment=asdict(registry.active()),
                       planner_steering_enabled=bool(runner.config.get('planner_steering_enabled', True)),
                       guidance_enabled=bool(runner.config.get('use_guidance')))
                runner.run()
                provenance = runner.adapter.get_context_provenance()
                for key in ('runtime_suite', 'task_id', 'perturbation_variant', 'init_state_id'):
                    if str(provenance[key]) != str(context[key]):
                        raise RuntimeError(f'actual LIBERO-PRO context mismatch: {key}')
                expansion_files = list(run_dir.glob('episode_*/mode_gate*expansion*.json'))
                job_ids = [json.loads(path.read_text()).get('slow_loop_job_id') for path in expansion_files]
                if any(SlowLoopStore(root / 'slow_loop').current(job_id).state.value == 'CANCELLED'
                       for job_id in job_ids if job_id):
                    ledger.append({'event_id': 'excluded:' + str(run_dir),
                        'event': 'ATTEMPT_EXCLUDED', 'context_id': context['context_id'],
                        'output_dir': str(run_dir), 'reason': 'expansion_cancelled_by_protocol_update',
                        'formal_result': False, 'completed_at': now()})
                    report('RETRYING_CONTEXT_AFTER_PROTOCOL_UPDATE', model_resident=True)
                    continue
                event = {
                    'event_id': 'completed:' + context['context_id'], 'event': 'EPISODE_COMPLETED',
                    **context, 'completed_at': now(), 'output_dir': str(run_dir),
                    'success': bool(runner.success_count), 'actual_context': provenance,
                    'deployment': asdict(registry.active()), 'slow_loop_jobs': [x for x in job_ids if x],
                    'metric_role': 'online_full_architecture_not_final_sealed',
                }
                ledger.append(event)
                completed.add(context['context_id'])
                report('EPISODE_COMPLETED', last_success=event['success'], last_slow_loop_jobs=event['slow_loop_jobs'])
                # Planner chooses whether and on which experiences to retrain;
                # this boundary callback is part of this run, not a scheduled task.
                from mode_gate.verifier_refresh import VerifierRefreshCoordinator
                from mode_gate.verifier_training import VerifierTrainingConfig
                VerifierRefreshCoordinator(registry=registry, incidents=runner.mode_gate_incidents,
                    output_root=output / 'verifier_reviews' / context['context_id'],
                    config=VerifierTrainingConfig(device=f'cuda:{args.gpu_index}')).run()
            except Exception as error:
                if isinstance(error, InterruptedError) and pause_requested():
                    continue
                traceback.print_exc()
                report('ERROR_WARM' if runner is not None else 'STARTUP_ERROR',
                       error_type=type(error).__name__, error=str(error), model_resident=runner is not None)
                if runner is None:
                    raise
                while not (output / 'resume.request').exists() and not (output / 'stop.request').exists():
                    time.sleep(2)
                if (output / 'resume.request').exists():
                    (output / 'resume.request').unlink()
    finally:
        if runner is not None:
            runner.adapter.close()
        lock.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('/shared/hengyil6/vls/self_improve/fixed_budget_50/env_position20_20260914'))
    parser.add_argument('--manifest', type=Path, default=Path('/shared/hengyil6/vls/self_improve/protocol/joint_eval_manifest.json'))
    parser.add_argument('--output', type=Path, default=Path('/shared/hengyil6/vls/self_improve/fixed_budget_50/env_position20_20260914/formal_experiment'))
    parser.add_argument('--gpu-index', type=int, default=6)
    parser.add_argument('--passes', type=int, default=1)
    parser.add_argument('--supervise-existing', action='store_true',
                        help='Attach finite recovery/results orchestration without reloading the main model')
    parser.add_argument('--pause-after-slow-loop', metavar='JOB_ID',
                        help='Pause after this existing slow loop completes; do not start a new worker')
    parser.add_argument('--pause-context-id', metavar='CONTEXT_ID',
                        help='Planned context owning the slow loop selected for deferred pause')
    args = parser.parse_args()
    if args.pause_after_slow_loop:
        if not args.pause_context_id or args.supervise_existing:
            parser.error('--pause-after-slow-loop requires --pause-context-id and cannot supervise')
        from mode_gate.experiment_supervisor import request_pause_after_slow_loop
        print(json.dumps(request_pause_after_slow_loop(
            root=args.root.resolve(), output=args.output.resolve(),
            job_id=args.pause_after_slow_loop, context_id=args.pause_context_id,
        )))
    elif args.pause_context_id:
        parser.error('--pause-context-id requires --pause-after-slow-loop')
    elif args.supervise_existing:
        from mode_gate.experiment_supervisor import ExperimentSupervisor
        ExperimentSupervisor(root=args.root.resolve(), output=args.output.resolve(),
                             repo_root=REPO, python_executable=Path(sys.executable)).run()
    else:
        run(args)
