"""Current experiment scope, baseline steering parity and precollected demonstration bank."""
from pathlib import Path
import json
from .io_utils import sha256_file
from .experiences import artifact_ref

CONFIG = Path(__file__).resolve().parents[1] / 'configs/candidate_experiment.json'
STEERING_KEYS = ('guide_scale', 'guide_scale_max', 'diversity_scale', 'diversity_scale_max',
                 'MCMC_steps', 'sigmoid_k', 'sigmoid_x0', 'start_ratio', 'use_fkd', 'use_diversity', 'fkd')

def configuration():
    return json.loads(CONFIG.read_text())

def configured_merge_selection():
    """Read the user's editable coefficient policy at each slow-loop boundary.

    This only selects alpha; it does not change delta composition, SFT sources,
    already accepted lineage or the baseline/control experiment's merge grid.
    """
    policy = configuration().get('merge_coefficients', {'mode': 'planner_uniform'})
    if policy.get('mode') == 'planner_uniform':
        return None
    if policy.get('mode') != 'fixed_uniform':
        raise ValueError('unknown merge coefficient selection mode')
    alpha = float(policy['alpha'])
    if isinstance(policy['alpha'], bool) or not 0 <= alpha <= 1:
        raise ValueError('fixed uniform alpha must be finite and in [0,1]')
    return {'schema_version': 'configured-uniform-merge-selection-v1',
            'alpha_values': [alpha], 'alpha_map': dict(language=alpha, vision=alpha, action=alpha),
            'selection_owner': 'user_configuration', 'search_enabled': False,
            'coefficient_policy': policy,
            'configuration': artifact_ref(CONFIG, kind='experiment_merge_configuration'),
            'reason': f'用户配置：语言、视觉、动作统一 alpha={alpha:g}，仅生成这一种合并候选；SFT 配方不变。'}

def selected_tasks(manifest):
    cfg = configuration()
    tasks = sorted((x for x in manifest['tasks'] if x['perturbation_variant'] in cfg['variants']),
                   key=lambda x: x['task_key'])
    if len(tasks) != cfg['task_count'] or any(sum(x['perturbation_variant'] == v for x in tasks) != 10 for v in cfg['variants']):
        raise ValueError('experiment requires exactly the 10 environment and 10 position tasks')
    return tasks

def baseline_steering_profile():
    cfg = configuration()
    source, runtime = Path(cfg['baseline_config']), Path(cfg['baseline_runtime'])
    baseline, template = json.loads(source.read_text()), json.loads(runtime.read_text())
    if baseline['method'] != 'v44_vls':
        raise ValueError('steering reference must be the measured v44+VLS baseline')
    chunk_paths = sorted(source.parent.glob('episode_*/chunks.jsonl'))
    chunks = [json.loads(line) for path in chunk_paths for line in path.read_text().splitlines() if line]
    guide_values = {float(row['guide_scale']) for row in chunks}
    if len(guide_values) != 1:
        raise ValueError('baseline effective guidance must be resolved from its actual sampling records')
    effective_guide = next(iter(guide_values))
    return {'main': {**{k: template['main'][k] for k in STEERING_KEYS},
                     'guide_scale': effective_guide,
                     'sample_batch_size': baseline['sample_count'], 'use_guidance': True,
                     'use_vlm_stage_recognition': True, 'vlm_query_limit': baseline['stage_query_limit'],
                     'max_episode_steps': baseline['max_episode_steps']},
            'policy': {'num_inference_steps': baseline['inference_steps'],
                       'action_chunk_horizon': baseline['execution_horizon'],
                       'pretrained_path': baseline['checkpoint'], 'tokenizer_path': baseline['tokenizer']},
            'backend': {**{k: baseline[k] for k in ('max_episode_steps', 'num_steps_wait', 'observation_width', 'observation_height')},
                        'task_guide_scales': [effective_guide] * 10},
            'sources': [artifact_ref(source, kind='baseline_config'), artifact_ref(runtime, kind='baseline_config')],
            'configured_guide_scale': template['main']['guide_scale'],
            'effective_guide_scale': effective_guide,
            'observed_chunks': len(chunks),
            'sampling_evidence': [artifact_ref(path, kind='baseline_sampling') for path in chunk_paths],
            'provider_difference': 'top-level semantic/stage/ticket Planner remains the designated Codex account',
            'retry_multiplier': [1.0, 1.0]}

def apply_baseline_steering(cfg):
    from omegaconf import OmegaConf
    profile = baseline_steering_profile()
    for key, value in profile['main'].items():
        OmegaConf.update(cfg, 'main.' + key, value, merge=False)
    for key, value in profile['policy'].items():
        OmegaConf.update(cfg, 'policy.pi05.' + key, value, merge=False)
    for key, value in profile['backend'].items():
        OmegaConf.update(cfg, 'backend.libero.' + key, value, merge=False, force_add=True)
    OmegaConf.update(cfg, 'mode_gate.sample_count', profile['main']['sample_batch_size'])
    OmegaConf.update(cfg, 'mode_gate.retry_schedule', [[1., 1.]] * 50)
    return profile

def demonstration_bank(manifest, *, verify_hdf5=False):
    """Read native-success curation as-is; never replay, relabel or rewrite existing demos."""
    completion_path = Path(configuration()['demo_completion'])
    completion = json.loads(completion_path.read_text())
    by_key = {x['task_key']: x for x in completion['contexts'].values()}
    result = []
    for task in selected_tasks(manifest):
        row = by_key[task['task_key']]
        ticket_path = Path(row['ticket_path'])
        ticket = json.loads(ticket_path.read_text())
        if any(str(ticket[k]) != str(task[k]) for k in ('suite', 'task_id', 'perturbation_variant')):
            raise ValueError('precollection task identity mismatch')
        curation_path = ticket_path.parent / 'curation.json'
        curation = json.loads(curation_path.read_text())
        dataset = Path(curation['export_root'])
        info = json.loads((dataset / 'meta/info.json').read_text())
        if (curation.get('needs_more_demos') is not False or not curation['accepted']
                or curation.get('demo_success_authority') != 'LIBERO-PRO native predicate during collection'
                or info['total_episodes'] != len(curation['accepted'])):
            raise ValueError('precollected native-success dataset incomplete')
        for path, identity in curation['accepted'].items():
            p = Path(path)
            if not p.is_file() or p.stat().st_size != identity['bytes']:
                raise ValueError('precollected demonstration missing/changed')
            if verify_hdf5 and sha256_file(p) != identity['sha256']:
                raise ValueError('precollected demonstration hash mismatch')
        videos = sorted((ticket_path.parent / 'videos').glob('*.success.mp4'))
        if len(videos) != int(row['video_count']) or any(p.stat().st_size == 0 for p in videos):
            raise ValueError('precollected viewing-video index is missing or incomplete')
        result.append({'task_key': task['task_key'], 'ticket_id': ticket['ticket_id'],
                       'ticket_path': str(ticket_path), 'dataset_root': str(dataset), 'repo_id': curation['repo_id'],
                       'demonstrations': len(curation['accepted']), 'video_count': len(videos),
                       'video_paths': list(map(str, videos)),
                       'evidence_refs': [artifact_ref(curation_path, kind='curation_result'),
                                         artifact_ref(dataset / 'meta/info.json', kind='dataset_info')],
                       'accepted': curation['accepted']})
    return result
