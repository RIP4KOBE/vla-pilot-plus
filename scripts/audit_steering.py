"""Offline cohort evidence checks, with explicit legacy and complete-v2 scopes."""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.steering_runtime import atomic_json, digest
from scripts.audit_steering_contract import audit_run as audit_task_contract, evaluation_directory
from scripts.audit_qd_mechanism import audit_chunk as audit_search_chunk
from scripts.steering_archive import execution_identity, support_asset

SUBMODULE_PINS = {'rdt': 'b896f4dcac8ed1c3fae4a056200db267607f131f',
                 'lerobot': '715debf6c1723a28f1a57d4274a8c4ec35b6a417'}
IMPORTED_MODULES = ('torch', 'torchvision', 'numpy', 'transformers', 'diffusers', 'accelerate',
                    'einops', 'gymnasium', 'PIL', 'psutil', 'mujoco', 'hydra', 'openai', 'cv2', 'lerobot')


def read_json(path):
    return json.loads(Path(path).read_bytes())


def json_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def protocol_config(folder, manifest, actual):
    """Rebuild the effective profile from frozen YAML, without executing source code."""
    expected = yaml.safe_load((folder / 'source/configs/evaluation/libero_object_swap.yaml').read_bytes())
    profile = yaml.safe_load((folder / f"source/configs/steering/{manifest['method']}.yaml").read_bytes())
    def merge(base, changes):
        for key, value in changes.items():
            if isinstance(value, dict):
                merge(base[key], value)
            else:
                base[key] = deepcopy(value)
    merge(expected, profile)
    all_tasks = expected['backend']['libero']['task_ids_filter']
    all_seeds = dict(zip(all_tasks, expected['main']['episode_seed_schedule']))
    tasks = manifest['tasks']
    if tasks != sorted(set(tasks)) or not tasks or any(t not in all_seeds for t in tasks):
        raise ValueError('Task subset differs from frozen protocol')
    if manifest['seeds'] != [all_seeds[t] for t in tasks]:
        raise ValueError('Task seeds differ from frozen protocol')
    expected['main'].update(episode_num=len(tasks), episode_start_index=0,
                            episode_seed_schedule=manifest['seeds'])
    expected['backend']['libero']['task_ids_filter'] = tasks
    scales = expected['backend']['libero'].get('task_guide_scales')
    if scales is not None:
        by_task = dict(zip(all_tasks, scales))
        expected['backend']['libero']['task_guide_scales'] = [by_task[t] for t in tasks]
    expected['steering']['method'] = manifest['method']
    identity = execution_identity(folder, manifest, actual)
    expected['main']['eds_eval'].update(method_label=manifest['method'], job_id=identity['job_id'])
    code_root = Path(manifest['code_root'])
    expected['main']['episode_rng_fixture_manifest'] = str(code_root / expected['main']['episode_rng_fixture_manifest'])
    expected['perception']['vlm_agent']['query_template_dir'] = str(code_root / 'vlm_query/target_distance')
    # The asset receipt separately binds these three machine-specific loader roots.
    for field in ('pretrained_path', 'text_encoder', 'vision_encoder'):
        expected['policy']['rdt'][field] = actual['policy']['rdt'][field]
    expected['hydra']['run']['dir'] = identity['original_output_dir']
    return expected


def asset_checks(folder, manifest, config):
    """Cross-check frozen preflight attestations; do not reread 50 GB of weights."""
    environment = read_json(folder / 'environment.json')
    local = yaml.safe_load((folder / 'local-config.yaml').read_bytes())
    libero_paths = environment.get('libero_paths', {})
    benchmark = Path(local['libero_root']) / 'libero/libero'
    expected_bindings = {name: str(benchmark / suffix) for name,suffix in
                         (('benchmark_root',''),('assets','assets'),('bddl_files','bddl_files'),('init_states','init_files'))}
    assets = environment['model_assets']
    expected_file = folder / 'source/scripts/steering_model_assets_manifest.json'
    expected = read_json(expected_file)
    expected_rows = sorted(({k: x[k] for k in ('root', 'path', 'bytes', 'sha256')}
                            for x in expected['files']), key=lambda x: (x['root'], x['path']))
    actual_rows = sorted(assets.get('files', []), key=lambda x: (x['root'], x['path']))
    normalization = expected['repository_contract']['normalization_files']
    policy = config['policy']['rdt']
    selected = {'rdt_weight': str(Path(policy['pretrained_path']) / 'ema/model.safetensors'),
                'rdt_config': str(Path(policy['pretrained_path']) / 'config.json'),
                'text_encoder_weight': str(Path(policy['text_encoder']) / 'pytorch_model.bin'),
                'vision_encoder_weight': str(Path(policy['vision_encoder']) / 'model.safetensors')}
    imported = environment.get('imported_packages', {})
    return {
        'local_config_snapshot_hash': digest(folder/'local-config.yaml') == manifest.get('local_config_sha256'),
        'device_binding': type(local.get('gpu')) is int and type(local.get('egl_device_id')) is int
            and local['gpu'] >= 0 and local['egl_device_id'] >= 0
            and manifest.get('physical_gpu') == local['gpu'] and manifest.get('egl_device_id') == local['egl_device_id'],
        'local_model_loader_binding': all(local.get(k)==policy.get(v) for k,v in
            (('rdt_checkpoint','pretrained_path'),('text_encoder','text_encoder'),('vision_encoder','vision_encoder'))),
        'libero_loader_path_binding': libero_paths.get('valid') is True
            and libero_paths.get('config_path') == str(Path(local['libero_config'])/'config.yaml')
            and bool(re.fullmatch('[0-9a-f]{64}',str(libero_paths.get('config_sha256',''))))
            and libero_paths.get('bindings') == expected_bindings
            and environment.get('libero',{}).get('root') == local['libero_root'],
        'environment_manifest_hash': digest(folder / 'environment.json') == manifest.get('environment_sha256'),
        'clean_pinned_submodules': all(environment.get('submodules', {}).get(name) == {'commit': commit, 'dirty': False}
                                       for name, commit in SUBMODULE_PINS.items()),
        'imported_dependency_entrypoints_recorded': all(
            isinstance(imported.get(name), dict) and isinstance(imported[name].get('module_version'), str)
            and bool(imported[name]['module_version']) and Path(imported[name].get('file', '')).is_absolute()
            and bool(re.fullmatch('[0-9a-f]{64}', str(imported[name].get('sha256', ''))))
            for name in IMPORTED_MODULES),
        'model_assets_verified': assets.get('valid') is True
            and assets.get('schema') == 'steering_model_verification_v1'
            and assets.get('expected_manifest_sha256') == digest(expected_file)
            and assets.get('verifier_sha256') == manifest['source_sha256'].get('scripts/steering_model_assets.py')
            and actual_rows == expected_rows and assets.get('files_checked') == len(expected_rows)
            and assets.get('bytes_hashed') == sum(x['bytes'] for x in expected_rows),
        'model_loader_paths_bound': assets.get('selected') == selected,
        'model_normalization_verified': assets.get('normalization_checked') is True
            and assets.get('normalization_files') == normalization,
        'libero_assets_verified': environment.get('libero', {}).get('valid') is True
            and environment['libero'].get('manifest_sha256') == manifest['source_sha256'].get('scripts/steering_assets_manifest.json'),
        'rng_assets_verified': environment.get('rng', {}).get('valid') is True
            and environment['rng'].get('fixture_count') == 20
            and environment['rng'].get('sha256') == config['main'].get('episode_rng_fixture_manifest_sha256'),
    }


def audit_vls_chunk(metric, config):
    """Validate recorded VLS telemetry; zero gradients and ESS skips are legal."""
    from math import isfinite, isclose
    checks = {}
    def check(name, condition):
        checks[name] = bool(condition)
    def finite(value):
        return type(value) in (int, float) and isfinite(value)
    cfg = config['main']['vls_config']
    try:
        batch = cfg['sample_batch_size']
        check('schema_and_route', metric.get('schema') == 'rdt_vls_metrics_v1' and metric.get('guidance_type') == 'vls')
        check('population_and_horizon', metric.get('sample_batch_size_observed') == batch
              and metric.get('action_chunk_horizon') == config['policy']['rdt']['action_chunk_horizon'])
        check('effective_scales', metric.get('guide_scale') == cfg['guide_scale']
              and metric.get('diversity_enabled') is cfg['use_diversity']
              and metric.get('diversity_scale') == cfg['diversity_scale'])
        check('schedule_config', metric.get('start_ratio') == cfg['start_ratio']
              and metric.get('sigmoid_k') == cfg['sigmoid_k'] and metric.get('sigmoid_x0') == cfg['sigmoid_x0'])
        steps = metric.get('num_inference_steps')
        # The content-pinned checkpoint declares five inference steps and 1000 train steps.
        # Exact scheduler timestep values are not independently replayed by this audit.
        check('inference_budget', steps == (config['policy']['rdt'].get('num_inference_steps') or 5))
        check('denoising_completed', type(steps) is int and steps > 0 and metric.get('denoising_steps_executed') == steps)
        for kind in ('gradient', 'rbf'):
            item = metric[kind]; events = item['events']; counts = Counter(e.get('status') for e in events)
            check(kind + '/events_and_counts', isinstance(events, list) and item.get('attempted') == len(events)
                  and set(counts) <= {'finite', 'zero', 'nonfinite', 'unavailable', 'exception'}
                  and item.get('applied') == counts['finite'] + counts['zero']
                  and all(type(item.get(key)) is int and item[key] >= 0 for key in ('attempted','applied','zero','nonfinite','exception','unavailable'))
                  and all(item.get(key) == counts[key] for key in ('zero','nonfinite','exception','unavailable')))
            check(kind + '/finite_execution', item.get('nonfinite') == item.get('exception') == item.get('unavailable') == 0)
            check(kind + '/numeric_events', all(
                all(finite(e.get(k)) for k in ('norm', 'masked_norm', 'scale'))
                and e['norm'] >= 0 and e['masked_norm'] >= 0 and e['scale'] >= 0
                and all(finite(e[k]) for k in ('raw_reward',) if k in e)
                and (kind != 'gradient' or finite(e.get('raw_reward')))
                and ((e['status'] == 'zero' and e['norm'] <= 1e-8) or (e['status'] == 'finite' and e['norm'] > 1e-8))
                for e in events))
        grad = [e['timestep'] for e in metric['gradient']['events']]
        rbf = [e['timestep'] for e in metric['rbf']['events']]
        start_index = steps // 3 if cfg['start_ratio'] is None else min(steps-1,max(0,int(steps*cfg['start_ratio'])))
        check('gradient_schedule', len(grad) == steps-start_index and len(set(grad)) == len(grad)
              and grad == sorted(grad, reverse=True) and grad[0] == metric.get('resolved_start_timestep'))
        expected_rbf = start_index if cfg['use_diversity'] and batch > 1 else 0
        check('rbf_schedule', len(rbf) == expected_rbf and len(set(rbf)) == len(rbf)
              and rbf == sorted(rbf, reverse=True) and all(t > metric['resolved_start_timestep'] for t in rbf))
        check('scheduler_timestep_range', all(type(t) is int and 0 <= t < 1000 for t in rbf+grad)
              and len(set(rbf+grad)) == len(rbf+grad))
        fkd = metric['fkd']; effective = cfg['use_fkd'] and batch > 1
        check('fkd_config', fkd.get('configured_enabled') is cfg['use_fkd']
              and fkd.get('effective_enabled') is effective and fkd.get('config') == cfg.get('fkd'))
        if effective:
            d = fkd['diagnostics']; events = d['events']
            check('fkd_diagnostics', fkd.get('diagnostics_available') is True
                  and d.get('calls') == len(events)
                  and d.get('score_opportunities') == sum(e.get('scored') is True for e in events)
                  and d.get('actual_resamples') == sum(e.get('resampled') is True for e in events)
                  and d.get('ess_skips') == sum(e.get('reason') == 'ess_sufficient' for e in events))
            scheduled = set(grad[::max(1,cfg['fkd']['resample_frequency'])]) - {grad[-1]}
            check('fkd_schedule', [e.get('timestep') for e in events] == grad[:-1]
                  and all(e.get('scored') is (e.get('timestep') in scheduled) for e in events))
            def lineage(e):
                if e.get('terminal') is not False or e.get('terminal_sort_indices') is not None:
                    return False
                if type(e.get('scored')) is not bool or type(e.get('resampled')) is not bool:
                    return False
                if not e['scored']:
                    return e['reason']=='not_scheduled' and not e['resampled'] and e.get('parent_indices') is None and e.get('ess') is None
                ess=e.get('ess'); adaptive=cfg['fkd']['adaptive_resampling']
                if adaptive and not (finite(ess) and 0 < ess <= batch+1e-5): return False
                if not adaptive and ess is not None: return False
                if not e['resampled']:
                    return adaptive and ess >= .5*batch and e['reason']=='ess_sufficient' and e.get('parent_indices') is None
                return (e['reason']=='multinomial' and (not adaptive or ess < .5*batch)
                        and isinstance(e.get('parent_indices'),list) and len(e['parent_indices'])==batch
                        and all(type(i) is int and 0<=i<batch for i in e['parent_indices']))
            check('fkd_parent_lineage', all(lineage(e) for e in events))
        else:
            check('fkd_disabled', fkd.get('diagnostics') is None and fkd.get('diagnostics_available') is False)
        delta=metric['compute_delta']
        check('compute_budget', delta.get('model_forward_calls')==steps
              and delta.get('model_denoising_steps')==steps and delta.get('denoising_invocations')==1
              and delta.get('model_batch_rows')==batch*steps and delta.get('denoising_step_batch_rows')==batch*steps
              and delta.get('model_forward_batch_sizes')==[batch]*steps
              and delta.get('renoise_invocations')==0 and delta.get('guided_chunks')==1 and delta.get('unguided_chunks')==0
              and delta.get('rbf_gradient_calls')==len(rbf) and delta.get('rbf_gradient_batch_rows')==len(rbf)*batch)
        selection = metric['selection']
        check('selection', selection.get('source') == ('reward_argmax' if batch > 1 else 'single_particle')
              and selection.get('score_source') == ('existing_final_selection' if batch > 1 else 'extra_selected_score')
              and selection.get('latent_fingerprint_scope') == 'before_final_action_mask'
              and selection.get('score_status') == 'finite_selected_score'
              and type(selection.get('index')) is int and 0 <= selection['index'] < batch
              and selection.get('reward_slice') == 'p1_to_p_horizon_minus_1'
              and selection.get('score_valid') is True and finite(selection.get('raw_score'))
              and all(re.fullmatch('[0-9a-f]{64}', str(selection.get(k, ''))) for k in ('latent_fingerprint','action_chunk_fingerprint')))
        outer = metric['outer_reward']; reference=outer.get('reference'); progress=outer.get('progress')
        check('outer_progress', finite(reference) and finite(progress) and outer.get('available') is True
              and outer.get('reason') == 'finite_selected_score'
              and isclose(progress,max(0.,min(1.2,1.-selection['raw_score']/reference)) if reference < -1e-6 else 0.,rel_tol=2e-5,abs_tol=2e-6))
        check('outer_reward_raw', finite(outer.get('raw_score'))
              and isclose(outer['raw_score'], selection['raw_score'], rel_tol=2e-5, abs_tol=2e-6))
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError, IndexError):
        checks['evidence_structure'] = False
    return {'recorded_mechanism_valid': bool(checks) and all(checks.values()), 'checks': checks,
            'scope': 'Recorded VLS telemetry consistency; no independent model execution, exact scheduler replay, or tensor replay'}


def vls_reference_continuity(events, metrics):
    """Bind outer progress consumed at each boundary, then apply Stage resets."""
    from math import isclose, isfinite
    by_key = {(m.get('episode'), m.get('task_id'), m.get('global_step')): m for m in metrics}
    references, previous_progress, previous_guidance = {}, {}, {}
    for event in events:
        identity=(event['episode_id'],event['task_id'])
        before=event['guidance_before']
        if type(before) is not bool or type(event.get('guidance_after')) is not bool:
            return False
        if identity in previous_guidance and before is not previous_guidance[identity]:
            return False
        expected_progress=previous_progress.get(identity,0.) if before else None
        diagnostic=event['normalized_reward_diagnostic']
        if expected_progress is None:
            if diagnostic is not None: return False
        elif not (type(diagnostic) in (float,int) and isfinite(diagnostic)
                  and isclose(diagnostic,expected_progress,rel_tol=2e-5,abs_tol=2e-6)):
            return False
        previous_guidance[identity]=event['guidance_after']
        if event['reward_reference_reset']:
            references.pop(identity, None)
        if event.get('guidance_after') is not True:
            previous_progress[identity]=None
            continue
        metric=by_key[identity+(event['global_step'],)]
        raw=metric['selection']['raw_score']; reference=metric['outer_reward']['reference']
        if not all(type(x) in (float,int) and isfinite(x) for x in (raw,reference)):
            return False
        progress=metric['outer_reward']['progress']
        if not (type(progress) in (float,int) and isfinite(progress)): return False
        previous_progress[identity]=progress
        expected=references.setdefault(identity,raw)
        if not isclose(reference,expected,rel_tol=2e-5,abs_tol=2e-6):
            return False
    return bool(metrics)


def audit(folder, *, exit_code=None, output_path=None, write=True, archive_support=None):
    """Return audit results; write=False never changes a historical run or audit file."""
    folder = Path(folder).resolve()
    destination = Path(output_path).resolve() if output_path is not None else folder / 'audit.json'
    details = destination.with_name(destination.stem + '-details')
    checks, errors, invalid_jsonl = {}, {}, []
    def check(name, predicate):
        try:
            checks[name] = bool(predicate() if callable(predicate) else predicate)
        except Exception as exc:
            checks[name] = False; errors[name] = type(exc).__name__
    def persist(name, value):
        data = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        path = details / name
        if write:
            atomic_json(path, value)
            identity = digest(path)
        else:
            identity = hashlib.sha256(data).hexdigest()
        return {'path': str(path) if write else None, 'sha256': identity,
                'hash_encoding': 'file_bytes' if write else 'canonical_json', 'written': bool(write)}
    def strict_rows(path):
        if not path.exists(): return []
        records = []
        for number, line in enumerate(path.read_text().splitlines(), 1):
            if not line.strip(): continue
            try:
                item = json.loads(line)
                if not isinstance(item, dict): raise ValueError('Expected object')
            except (ValueError, TypeError):
                invalid_jsonl.append(f'{path.name}:{number}')
                item = {'invalid_jsonl_line': number}
            records.append(item)
        return records
    try:
        manifest = read_json(folder / 'manifest.json'); status = read_json(folder / 'status.json')
        config = yaml.safe_load((folder / 'resolved-config.yaml').read_bytes())
        v2 = manifest.get('schema') == 'steering_cohort_v2'
        evaluation = evaluation_directory(folder, manifest); out = folder / 'output'
        streams = {name: strict_rows(evaluation / (name + '.jsonl')) for name in
                   ('stage_events','episode_metadata','episode_compute','eds_metrics','vls_metrics','episode_rng_events')}
        events, metadata, compute = (streams[x] for x in ('stage_events','episode_metadata','episode_compute'))
        metrics, restores = streams['eds_metrics'], streams['episode_rng_events']
        tasks, seeds = manifest['tasks'], manifest['seeds']
        expected = [(i,t,s) for i,(t,s) in enumerate(zip(tasks,seeds))]
        queries = [r for r in events if r.get('query_status') in ('ok','error')]
        code = status.get('exit_code') if exit_code is None else exit_code
        check('worker_exit', code == status.get('exit_code') == 0 and status.get('state') in ('finished','exited'))
        check('runtime_source_unchanged', status.get('source_unchanged') is True)
        check('config_unchanged', lambda: digest(folder / 'resolved-config.yaml') == manifest.get('config_sha256'))
        check('complete_jsonl', not invalid_jsonl)
        check('tasks_and_seeds', bool(tasks) and len(tasks)==len(seeds)==len(set(tasks)) and
              [(r.get('task_id'),r.get('episode_seed')) for r in metadata]==list(zip(tasks,seeds)))
        check('completed_episodes', len(compute)==len(tasks) and all(r.get('outcome')=='completed' for r in compute))
        check('compute_episode_identity', [(r.get('episode_id'),r.get('task_id'),r.get('episode_seed')) for r in compute]==expected)
        check('no_episode_errors', not list(out.glob('episode_*/error.txt')))
        check('online_queries_valid', bool(queries) and all(r.get('query_ok') is True for r in queries))
        check('online_query_for_every_task', all(any(q.get('task_id')==t and q.get('query_ok') is True for q in queries) for t in tasks))
        check('reward_gate', bool(events) and all(not r.get('guidance_after') or r.get('reward_capability',{}).get('available') is True for r in events))
        check('reward_reference_reset_only_on_stage_change', bool(events) and all(r.get('reward_reference_reset')==(r.get('stage_before')!=r.get('stage_after')) for r in events))
        check('rng_restore_order', lambda: [(r['metadata']['task_id'],r['metadata']['episode_seed'],r['metadata']['phase']) for r in restores]==[(t,s,p) for t,s in zip(tasks,seeds) for p in ('prepare','rollout')])
        check('source_snapshot_intact', lambda: bool(manifest['source_sha256']) and all(digest(folder/'source'/p)==h for p,h in manifest['source_sha256'].items()))
        fixture=read_json(support_asset(folder, 'rng_manifest', archive_support=archive_support, manifest=manifest, config=config)) if v2 else read_json(ROOT/'tests/fixtures/steering_rng/fixture-manifest.json')
        check('rng_states_match', lambda: bool(restores) and all(r['sha256']==fixture['fixtures'][f"{r['metadata']['task_id']}:{r['metadata']['phase']}"]['sha256'] and r['state_signature']==fixture['fixtures'][f"{r['metadata']['task_id']}:{r['metadata']['phase']}"]['state_signature'] for r in restores))
        from core.stage_fused_carry_hold import audit_checks as carry_checks
        from core.stage_failed_contact_recheck import audit_checks as contact_checks
        check('carry_check_structure', lambda: all(carry_checks(events).values()))
        check('contact_check_structure', lambda: all(contact_checks(events).values()))
        task_rows=[]
        for i,task in enumerate(tasks,1):
            episode=out/f'episode_{i}'; videos=list(episode.glob('*agentview.mp4'))
            video_valid=len(videos)==1 and not (episode/'error.txt').exists() and '_error' not in videos[0].name
            contracts=list(episode.rglob('target_distance_reward.json'))
            contract_valid=len(contracts)==1 and read_json(contracts[0]).get('valid') is True
            row=dict(task_id=task,episode=i,seed=seeds[i-1],valid=video_valid and contract_valid,
                     success=video_valid and '_success' in videos[0].name,reward_contract_valid=contract_valid,
                     videos=[str(v.relative_to(folder)) for v in videos])
            if v2:
                try:
                    report=audit_task_contract(folder,task=task,model=manifest['model'],effort=manifest['reasoning_effort'],archive_support=archive_support)
                    json.dumps(report,allow_nan=False)
                except Exception as exc:
                    report={'task_id':task,'task_contract_valid':False,'task_evidence_complete':False,
                            'summary':{'fail':1},'checks':{'evidence_structure':{'status':'fail','error_type':type(exc).__name__}}}
                valid=report.get('task_contract_valid') is True and report.get('task_evidence_complete') is True
                row['extended_contract']=dict(valid=valid,summary=report.get('summary'),**persist(f'task{task}-contract.json',report))
                row['valid']=row['valid'] and valid
            task_rows.append(row)
        check('videos_and_reward_contracts', all(r['valid'] for r in task_rows))
        successes=sum(r['success'] for r in task_rows)
        text=(out/'results.txt').read_text() if (out/'results.txt').exists() else ''
        count=re.search(r'Success count:\s*(\d+)/(\d+)',text)
        check('environment_success_count_matches', bool(count) and (int(count[1]),int(count[2]))==(successes,len(tasks)))
        method_summary=None
        if v2:
            check('new_schema_evaluation_directory', manifest.get('evaluation_directory')=='output/evaluation')
            required_sources=('configs/evaluation/libero_object_swap.yaml',f"configs/steering/{manifest['method']}.yaml",
                'scripts/steering_runtime.py','scripts/steering_worker.py','scripts/run_steering.py',
                'scripts/steering_model_assets.py','scripts/steering_model_assets_manifest.json',
                'scripts/steering_assets_manifest.json','scripts/prepare_steering_assets.py','core/episode_rng_hooks.py','core/rdt_policy_steer.py','core/qd_ed.py','core/fkd_class.py')
            check('protocol_sources_frozen',all(p in manifest.get('source_sha256',{}) for p in required_sources))
            check('fixed_protocol_config', lambda: config==protocol_config(folder,manifest,config))
            check('provider_manifest', manifest.get('provider')=='codex_cli' and manifest.get('model')=='gpt-6-astra'
                  and manifest.get('reasoning_effort')=='low' and manifest.get('online_stage') is True and manifest.get('fresh_reward') is True)
            try: checks.update(asset_checks(folder,manifest,config))
            except Exception as exc: checks['asset_evidence_structure']=False;errors['asset_evidence_structure']=type(exc).__name__
            check('extended_task_contracts', all(r['extended_contract']['valid'] for r in task_rows))
            method=manifest['method']; selected=streams['vls_metrics'] if method=='vls' else metrics
            check('method_matches_config', method in ('vls','eds','eds_qd') and config.get('steering',{}).get('method')==method
                  and config['main'].get('guidance_type')==('vls' if method=='vls' else 'eds'))
            check('no_other_method_chunks', not (metrics if method=='vls' else streams['vls_metrics']))
            stage_identity=lambda r:(r.get('episode_id'),r.get('task_id'),r.get('global_step'))
            metric_identity=lambda r:(r.get('episode',r.get('episode_id')),r.get('task_id'),r.get('global_step'))
            expected_seeds={(i,t):s for i,t,s in expected}
            check('stage_task_seed_identity', all((r.get('episode_id'),r.get('task_id')) in expected_seeds
                  and r.get('episode_seed')==expected_seeds[(r.get('episode_id'),r.get('task_id'))] for r in events))
            guided=[r for r in events if r.get('guidance_after') is True]
            expected_keys=[stage_identity(r) for r in guided];actual_keys=[metric_identity(r) for r in selected]
            identity_shapes=all(all(type(v) is int for v in key) for key in expected_keys+actual_keys)
            check('guided_chunks_complete_unique', bool(guided) and identity_shapes and expected_keys==actual_keys
                  and len(set(expected_keys))==len(expected_keys)==len(set(actual_keys)))
            check('compute_stage_chunk_counts', all(r.get('guided_chunks')==sum(e.get('episode_id')==r.get('episode_id') and e.get('guidance_after') is True for e in events)
                  and r.get('unguided_chunks')==sum(e.get('episode_id')==r.get('episode_id') and e.get('guidance_after') is False for e in events) for r in compute))
            if method=='vls':
                check('vls_stage_reference_continuity',lambda:vls_reference_continuity(events,selected))
            chunk_reports=[]
            for number,metric in enumerate(selected):
                key=metric_identity(metric); identity_valid=all(type(v) is int for v in key)
                bound=identity_valid and key in expected_keys and key[:2] in expected_seeds
                bound=bound and ('episode_seed' not in metric or metric['episode_seed']==expected_seeds[key[:2]])
                bound=bound and metric.get('method_label')==method and metric.get('job_id')==execution_identity(folder,manifest,config)['job_id']
                bound=bound and metric.get('suite')==config['backend']['libero']['suite_name']
                try:
                    report=(audit_vls_chunk(metric,config) if method=='vls' else
                            audit_search_chunk(metric,config['main']['eds_config'],expected_mode=method))
                    if method!='vls':
                        sampler_valid=(metric.get('initial_sampling_mode')=='rbf_diverse_denoise'
                            and metric.get('initial_diversity_steps')==4 and metric.get('initial_diversity_fallback_used') is False
                            and metric.get('rollout_diversity_mode')=='rbf_diverse' and metric.get('rollout_diversity_fallback_used') is False
                            and metric.get('rollout_diversity_iters_applied')==10
                            and metric.get('rollout_rbf_steps_by_iter')==[dict(
                                iter_idx=i,n_trunc_steps=n,step_count=count,step_flags=[True]*count+[False]*(n-count),
                                step_indices=list(range(count)),final_step_rbf_applied=count==n,fallback_used=False)
                                for i,(n,count) in enumerate(zip([3,2,2,2,2,1,1,1,1,1],[2,2,2,2,2,1,1,1,1,1]))])
                        report['checks']['fixed_rbf_sampler_execution']='pass' if sampler_valid else 'fail'
                        report['recorded_mechanism_valid']=report['recorded_mechanism_valid'] and sampler_valid
                    json.dumps(report,allow_nan=False)
                except Exception as exc:
                    report={'recorded_mechanism_valid':False,'checks':{'evidence_structure':False},'error_type':type(exc).__name__}
                chunk_reports.append(dict(row_number=number+1,identity=key,episode_seed=expected_seeds.get(key[:2]) if identity_valid else None,
                                          stage_binding_valid=bool(bound),**report))
            valid=bool(chunk_reports) and all(r['stage_binding_valid'] and r.get('recorded_mechanism_valid') is True for r in chunk_reports)
            check('independent_method_audit',valid)
            method_summary=dict(valid=valid,chunks=len(chunk_reports),failed_chunks=sum(not(r['stage_binding_valid'] and r.get('recorded_mechanism_valid') is True) for r in chunk_reports),
                **persist('method-chunks.json',{'method':method,'chunks':chunk_reports,'cohort_valid':None}))
        elif manifest['method'] in ('eds','eds_qd'):
            check('guided_search_matches_gate', [(r.get('episode_id'),r.get('global_step')) for r in events if r.get('guidance_after')]==[(r.get('episode'),r.get('global_step')) for r in metrics])
            check('eds_search_mechanism', bool(metrics) and all(r.get('population_size')==16 and r.get('population_size_observed')==16
                and r.get('eds_iters_executed')==10 and r.get('execution_horizon_resolved')==8 and r.get('initial_sampling_mode')=='rbf_diverse_denoise'
                and r.get('initial_diversity_fallback_used') is False and r.get('rollout_diversity_fallback_used') is False
                and r.get('rollout_diversity_iters_applied')==10 and r.get('qd_archive_enabled') is (manifest['method']=='eds_qd') for r in metrics))
        result=dict(schema='steering_cohort_audit_v2',method=manifest['method'],valid=bool(checks) and all(checks.values()),
            scope='full_v2_contract_and_recorded_method_evidence' if v2 else 'legacy_basic_only',full_audit_performed=v2,
            checks=checks,errors=errors,completed=sum(r['valid'] for r in task_rows),planned=len(tasks),successes=successes,
            success_task_ids=[r['task_id'] for r in task_rows if r['success']],tasks=task_rows,stage_queries=len(queries),
            infrastructure_error_episodes=len(list(out.glob('episode_*/error.txt'))),invalid_jsonl=invalid_jsonl,
            evaluation_directory=str(evaluation.relative_to(folder)),method_audit=method_summary,
            limits=['Model-asset identity checks bind recorded preflight hashing and loader choices; weights are not reread during this audit.',
                    'Imported dependency fields attest module entrypoints, not a hash of every installed dependency file.',
                    'Recorded method consistency does not establish all tensor paths or independent simulator execution.'])
    except Exception as exc:
        result=dict(schema='steering_cohort_audit_v2',valid=False,full_audit_performed=False,scope='failed_evidence_read',
                    checks={**checks,'evidence_structure':False},errors={**errors,'evidence_structure':type(exc).__name__},invalid_jsonl=invalid_jsonl)
    if write: atomic_json(destination,result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('run_dir')
    parser.add_argument('--output',type=Path);parser.add_argument('--no-write',action='store_true');parser.add_argument('--archive-support',type=Path)
    args=parser.parse_args();result=audit(args.run_dir,output_path=args.output,write=not args.no_write,archive_support=args.archive_support)
    print(json.dumps(result,indent=2));raise SystemExit(0 if result['valid'] else 1)
