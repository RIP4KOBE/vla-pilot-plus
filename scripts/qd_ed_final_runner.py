#!/usr/bin/env python3
"""Owned, single-GPU QD/ED evaluation with frozen inputs and attempt accounting.

No historical runner is imported and no run is resumed implicitly. A plan is
data, never executable shell text. Each child runs exactly one task/seed/init.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import uuid

import yaml
from qd_ed_gpu_faults import KernelXidMonitor, MonitorError

ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path('/home/hynx/miniconda3/envs/vla-pilot/bin/python')
SCHEMA = 'qd-ed-final-plan-v1'
BUCKETS = {'baseline': 20, 'development': 100, 'validation': 60, 'formal': 40, 'recovery': 20}
TERMINAL = {'valid', 'aborted'}
REQUIRED_CODE = {
    'main.py', 'core/rdt_policy_steer.py', 'core/qd_ed.py', 'core/eds_eval_metrics.py',
    'scripts/qd_ed_final_runner.py', 'configs/config.yaml', 'configs/policy.yaml',
    'configs/backend/libero.yaml', 'configs/perception.yaml',
    'configs/qd_ed_final/baseline_profiles.json',
    'core/gemini_grounder.py', 'vlm_query/stage_template.txt',
    'vlm_query/vlm_agent.py', 'scripts/qd_ed_final_report.py',
    'scripts/qd_ed_codex_launch.py',
    'scripts/qd_ed_gpu_faults.py',
    'core/codex_stage.py', 'core/codex_stage_policy.py',
}
REQUIRED_CODE.update(str(p.relative_to(ROOT)) for folder in ('core','utils','vlm_query')
                     for p in (ROOT/folder).rglob('*') if p.is_file() and p.suffix in {'.py','.txt'})
RUNTIME_ENV_ALLOW = {
    'LIBERO_CONFIG_PATH', 'PYTHONPATH', 'TORCH_HOME', 'HF_HOME', 'HF_HUB_CACHE',
    'TRANSFORMERS_CACHE', 'XDG_CACHE_HOME', 'NUMBA_CACHE_DIR', 'TMPDIR',
    'TOKENIZERS_PARALLELISM', 'HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE',
    'PYTHONDONTWRITEBYTECODE',
    'QD_ED_CUDA_EGL_SERIALIZE',
    'QD_ED_RENDER_LIFETIME',
    'PYTORCH_NO_CUDA_MEMORY_CACHING',
}
_HASH_CACHE = {}
CODEX_CONFIG_KEYS = ('backend', 'model', 'reasoning_effort', 'timeout_seconds', 'cli_path', 'disabled_skill_paths')
CODEX_STAGE_CONDITION = 'codex_login_astra_low_v1'
GPU_MONITOR_QUERY_TIMEOUT_SECONDS = 15
# Covers a 15s metadata timeout and two possible 10s child-cleanup waits.
TERMINATION_GRACE_SECONDS = 40
MEMCHECK_TOOL = Path('/usr/local/cuda-12.8/compute-sanitizer/compute-sanitizer')
COMPUTE_FIELDS = (
    'model_forward_calls','model_batch_rows','denoising_invocations','model_denoising_steps',
    'denoising_step_batch_rows','reward_calls','reward_evaluations','reward_scoring_batches',
    'guided_chunks','unguided_chunks','stage_api_request_attempts','stage_api_sdk_retry_attempts',
    'guidance_api_request_attempts','guidance_api_sdk_retry_attempts','grounding_api_request_attempts',
    'grounding_api_sdk_retry_attempts','provider_request_attempts','provider_sdk_retry_attempts',
    'rbf_gradient_calls','rbf_gradient_batch_rows','renoise_invocations',
    'vision_encoder_forward_calls','vision_encoder_batch_rows',
    'text_encoder_forward_calls','text_encoder_batch_rows',
    'dino_forward_calls','dino_batch_rows',
)
CODEX_UNKNOWN_HTTP_FIELDS = {
    'stage_api_request_attempts', 'stage_api_sdk_retry_attempts',
    'provider_request_attempts', 'provider_sdk_retry_attempts',
}
CODEX_COUNT_SUFFIXES = ('logical_call_attempts', 'completed_turns', 'failed_calls',
                        'usage_complete_calls', 'input_tokens', 'cached_input_tokens', 'output_tokens')


class GateError(RuntimeError):
    pass


class LockBusyError(GateError):
    def __init__(self, path):
        self.lock_path = Path(path).resolve()
        super().__init__('another owned runner holds the lock')


def require(condition, message):
    if not condition:
        raise GateError(message)


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f'duplicate key: {key}')
        result[key] = value
    return result


class UniqueLoader(yaml.SafeLoader):
    pass


def unique_yaml(loader, node, deep=False):
    loader.flatten_mapping(node)
    return unique_pairs((loader.construct_object(k, deep=deep), loader.construct_object(v, deep=deep)) for k, v in node.value)


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_yaml)


def read_json(path):
    return json.loads(Path(path).read_text(), object_pairs_hook=unique_pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(GateError(f'nonfinite JSON: {value}')))


def read_state(path):
    return yaml.load(Path(path).read_text(), Loader=UniqueLoader)


def read_events(path):
    if not Path(path).exists():
        return []
    return [json.loads(line, object_pairs_hook=unique_pairs,
                       parse_constant=lambda value: (_ for _ in ()).throw(GateError(f'nonfinite JSONL: {value}')))
            for line in Path(path).read_text().splitlines() if line.strip()]


def digest(path):
    stat = Path(path).stat()
    identity = (str(Path(path).resolve()), stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
    if identity in _HASH_CACHE:
        return _HASH_CACHE[identity]
    hasher = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            hasher.update(block)
    result = hasher.hexdigest()
    after = Path(path).stat()
    require((after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns) == identity[1:], f'file changed while hashing: {path}')
    _HASH_CACHE[identity] = result
    return result


def owned(path, base):
    path = Path(path).resolve()
    require(path != Path(base).resolve() and path.is_relative_to(Path(base).resolve()), f'path escapes owned root: {path}')
    return path


def hydra(value):
    if isinstance(value, bool):
        return str(value).lower()
    if value is None:
        return 'null'
    if isinstance(value, list):
        return '[' + ','.join(hydra(v) for v in value) + ']'
    # Hydra comma is a sweep separator unless quoted. Preserve scalar strings.
    if isinstance(value, str) and any(c in value for c in ', []{}:='):
        return json.dumps(value)
    return str(value)


def verify_files(records, *, root=None, allowed_roots=None):
    require(isinstance(records, list) and records, 'fingerprint list missing')
    seen = set()
    for record in records:
        path = Path(record['path'])
        if not path.is_absolute():
            require(root is not None, 'relative input path has no root')
            path = root / path
        path=Path(os.path.abspath(path))
        key = str(path)
        require(key not in seen, f'duplicate fingerprint path: {path}')
        seen.add(key)
        if allowed_roots:
            require(any(path.is_relative_to(Path(base).resolve()) for base in allowed_roots) and
                    any(path.resolve().is_relative_to(Path(base).resolve()) for base in allowed_roots), f'input symlink escapes owned roots: {path}')
        if 'resolved_path' in record:
            require(str(path.resolve())==record['resolved_path'], f'input link resolution changed: {path}')
        if 'link_target' in record:
            require(path.is_symlink() and os.readlink(path)==record['link_target'], f'input symlink target changed: {path}')
        require(path.is_file(), f'frozen file missing: {path}')
        require(digest(path) == record['sha256'], f'frozen file changed: {path}')
        if 'size_bytes' in record:
            require(path.stat().st_size == record['size_bytes'], f'frozen file size changed: {path}')


def episode_identity(row):
    return {key: row[key] for key in ('split', 'iteration', 'profile', 'task_id', 'env_seed', 'policy_seed', 'init_index')}


def validate_plan(path, *, root=ROOT, require_frozen=True, allow_unverified_gpu=False):
    root = Path(root).resolve()
    plan = read_json(path)
    require(plan.get('schema') == SCHEMA, 'plan schema mismatch')
    require(plan.get('frozen') is True or not require_frozen, 'plan is not frozen')
    require(Path(plan['worktree']).resolve() == root, 'plan worktree mismatch')
    state = read_state(root / 'research-state.yaml')
    require(plan['run_name'] == state['run_name'], 'run identity mismatch')
    artifact_root = Path(plan['artifact_root']).resolve()
    require(artifact_root == Path(state['artifacts']).resolve(), 'artifact root mismatch')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    require(head == plan['source_commit'], 'source HEAD changed after freeze')
    code_paths = {str(Path(r['path'])) for r in plan.get('code_files', [])}
    require(REQUIRED_CODE <= code_paths, 'required source fingerprints missing')
    require(set(plan.get('scientific_config_files', [])) <= code_paths, 'scientific configuration fingerprints missing')
    for record in plan['code_files']:
        owned(root / record['path'], root)
    verify_files(plan['code_files'], root=root)
    profile_path = owned(plan['profiles_path'], root)
    require(digest(profile_path) == plan['profiles_sha256'], 'profiles fingerprint mismatch')
    manifest = read_json(profile_path)
    for candidate_id,reference in plan.get('candidate_profiles',{}).items():
        require(candidate_id not in manifest['profiles'], 'candidate shadows a baseline identity')
        candidate_path=owned(reference['path'],root)
        relative=str(candidate_path.relative_to(root))
        require(relative in plan.get('scientific_config_files',[]) and relative in code_paths, 'candidate scientific fingerprint binding missing')
        require(digest(candidate_path)==reference['sha256'], 'candidate profile fingerprint mismatch')
        candidate=read_json(candidate_path)
        require(candidate.get('baseline_reference')=='Q0', 'N1 must reference Q0')
        baseline=manifest['profiles']['Q0']; candidate_profile=candidate['profile']
        require(set(candidate_profile)==set(baseline['restored_profile']), 'N1 profile field set differs')
        require({k for k in candidate_profile if candidate_profile[k]!=baseline['restored_profile'][k]}=={'qd_descriptor'}, 'N1 must change only qd_descriptor')
        active=copy.deepcopy(baseline)
        active['historical_label']=str(candidate['label'])
        active['restored_profile']=candidate_profile
        active['resolved_eds_config']['qd_descriptor']=candidate_profile['qd_descriptor']
        active['static_override_values']['main.eds_config.qd_descriptor']=candidate_profile['qd_descriptor']
        active['hydra_overrides']=[f'{key}={hydra(value)}' for key,value in active['static_override_values'].items()]
        manifest['profiles'][candidate_id]=active
    runtime_path = owned(plan['runtime_manifest_path'], artifact_root)
    require(digest(runtime_path) == plan['runtime_manifest_sha256'], 'runtime manifest fingerprint mismatch')
    runtime = read_json(runtime_path)
    require(runtime.get('schema') == 'qd-ed-runtime-setup-v1', 'runtime schema mismatch')
    require(Path(runtime['worktree']).resolve() == root, 'runtime worktree mismatch')
    require(Path(runtime['artifact_root']).resolve() == artifact_root, 'runtime artifact root mismatch')
    stage_overrides(runtime)
    physical_gpu = runtime_gpu(runtime, state)
    if require_frozen:
        validate_gpu_readiness(plan, runtime, allow_unverified_gpu=allow_unverified_gpu)
        require(runtime.get('provider_ready') is True, 'frozen Stage provider is not ready')
    verify_files(runtime['files'],allowed_roots=(root,artifact_root))
    inventory_path = owned(plan['runtime_inventory_path'], root)
    require(digest(inventory_path) == plan['runtime_inventory_sha256'], 'model/input inventory fingerprint mismatch')
    inventory = read_json(inventory_path)
    require(inventory.get('schema') == 'qd-ed-runtime-inventory-v1', 'inventory schema mismatch')
    if require_frozen:
        # SHA checks are cached only while inode/size/mtime/ctime remain identical
        # in this process. Initial dispatch verifies the actual model bytes.
        verify_files(inventory['checkpoint'])
        for encoder in inventory['hf_encoders']:
            verify_files(encoder['files'])
            if 'snapshot' in encoder:
                snapshot=Path(encoder['snapshot'])
                require({p.resolve() for p in snapshot.parent.iterdir() if p.is_dir()}=={snapshot.resolve()}, 'encoder snapshot set changed; newest-directory resolver could drift')
        verify_files([inventory['dinov2']['weights']])
    task_inputs = {item['task_id']: item for item in inventory['libero_tasks']}
    seed_path = owned(plan['seed_plan_path'], root)
    require(digest(seed_path) == plan['seed_plan_sha256'], 'seed plan fingerprint mismatch')
    seeds = read_json(seed_path)
    require(seeds.get('schema') == 'qd-ed-frozen-seed-plan-v1' and seeds['run_name'] == plan['run_name'], 'seed plan identity mismatch')
    require(set(runtime.get('environment', {})) <= RUNTIME_ENV_ALLOW, 'unapproved runtime environment name')
    require(str(runtime.get('environment', {}).get('QD_ED_RENDER_LIFETIME', '0')) in {'0', '1'},
            'invalid render lifetime diagnostic flag')
    require(str(runtime.get('environment', {}).get('QD_ED_CUDA_EGL_SERIALIZE', '0')) in {'0', '1'},
            'invalid CUDA/EGL diagnostic serialization setting')
    require('LIBERO_CONFIG_PATH' in runtime.get('environment', {}), 'owned LIBERO_CONFIG_PATH missing')
    owned(runtime['environment']['LIBERO_CONFIG_PATH'], artifact_root)
    require(plan.get('input_contract_label') == 'input_repaired', 'task-bound cache repair must be disclosed')
    require(isinstance(plan.get('episodes'), list) and plan['episodes'], 'empty episode plan')
    keys, identities = set(), set()
    for row in plan['episodes']:
        require(isinstance(row.get('episode_key'), str) and re.fullmatch(r'[A-Za-z0-9_.-]+', row['episode_key']), 'unsafe episode_key')
        require(row['episode_key'] not in keys, 'duplicate episode_key')
        keys.add(row['episode_key'])
        require(row['split'] in {'dev', 'validation', 'formal'}, 'invalid split')
        require(isinstance(row['iteration'], (str, int)) and not isinstance(row['iteration'], bool), 'invalid iteration')
        require(row['profile'] in manifest['profiles'], 'unknown profile')
        require(type(row['task_id']) is int and 0 <= row['task_id'] < 10, 'invalid task_id')
        for seed_field in ('env_seed', 'policy_seed'):
            require(type(row[seed_field]) is int and 0 <= row[seed_field] < 2**31, f'invalid {seed_field}')
        require(row['init_index'] == 0 and type(row['init_index']) is int, 'single-episode backend currently requires init_index=0')
        require(row['budget_bucket'] in BUCKETS, 'unknown budget bucket')
        if not row.get('retry_of'):
            require((row['split'] == 'dev' and row['budget_bucket'] in {'baseline', 'development'}) or row['split'] == row['budget_bucket'], 'split/budget mismatch')
        else:
            require(row['budget_bucket'] == 'recovery', 'retry must consume recovery reserve')
        require(type(row['timeout_seconds']) is int and 0 < row['timeout_seconds'] <= 48*3600, 'invalid timeout')
        identity = json.dumps(episode_identity(row), sort_keys=True)
        require(identity not in identities or row.get('retry_of'), 'duplicate planned episode identity')
        identities.add(identity)
        task = runtime['tasks'].get(str(row['task_id']))
        require(task is not None, 'task runtime binding missing')
        require(task['init_index'] == row['init_index'], 'task init mismatch')
        require(task_inputs[row['task_id']]['used_init_index'] == row['init_index'], 'frozen init-row index mismatch')
        require(row.get('init_row_sha256') == task_inputs[row['task_id']]['used_init_row_sha256'], 'frozen init-row identity mismatch')
        seed_block = row['seed_block']
        require((row['split'] in {'dev','formal'} and seed_block == row['split']) or
                (row['split'] == 'validation' and re.fullmatch(r'validation_c[1-4]_b[12]',seed_block)), 'seed block/split mismatch')
        matching = [item for item in seeds['blocks'][seed_block] if item['task_id'] == row['task_id']]
        require(len(matching) == 1, 'frozen seed task missing/ambiguous')
        for field in ('env_seed','policy_seed','init_index','init_row_sha256','init_file_sha256','bddl_sha256'):
            require(row.get(field) == matching[0][field], f'episode differs from frozen seed plan: {field}')
        require(digest(task['bddl_path']) == row['bddl_sha256'] and digest(task['init_path']) == row['init_file_sha256'], 'runtime task inputs differ from frozen seed plan')
        owned(task['cache_dir'], artifact_root)
    validate_memcheck(plan)
    validate_memcheck_environment(plan, runtime)
    return plan, manifest, runtime


def validate_gpu_readiness(plan, runtime, *, allow_unverified_gpu=False):
    """Queue preparation can wait for a probe; real episode dispatch cannot."""
    if allow_unverified_gpu:
        require(type(plan.get('egl_mapping_verified')) is bool
                and type(runtime.get('cuda_egl_verified')) is bool
                and runtime.get('metadata_mapping_verified') is True,
                'queued GPU mapping lacks explicit readiness or verified metadata')
    else:
        require(plan.get('egl_mapping_verified') is True and runtime.get('cuda_egl_verified') is True,
                f'GPU{runtime_gpu(runtime)}/EGL mapping not verified')


def validate_memcheck(plan):
    diagnostic = plan.get('cuda_memcheck')
    if diagnostic is None:
        return
    require({'tool_path', 'files'} <= set(diagnostic)
            <= {'tool_path', 'files', 'force_blocking_launches', 'disable_caching_allocator'},
            'invalid CUDA memcheck contract')
    blocking = diagnostic.get('force_blocking_launches', False)
    require(type(blocking) is bool, 'CUDA memcheck blocking launch flag must be boolean')
    no_cache = diagnostic.get('disable_caching_allocator', False)
    require(type(no_cache) is bool, 'CUDA memcheck allocator flag must be boolean')
    require(not no_cache or blocking, 'uncached memcheck retains blocking launches')
    iteration = ('GPU2_CUDA_MEMCHECK_NOCACHE_C0' if no_cache else
                 'GPU2_CUDA_MEMCHECK_BLOCKING_C0' if blocking else 'GPU5_CUDA_MEMCHECK_C0')
    require(diagnostic['tool_path'] == str(MEMCHECK_TOOL), 'unexpected CUDA memcheck executable')
    require(plan.get('diagnostic_scope', {}).get('kind') == 'cuda_memcheck'
            and plan['diagnostic_scope'].get('online_algorithm_comparison') is False,
            'CUDA memcheck requires a diagnostic-only plan')
    rows = plan.get('episodes', [])
    require(len(rows) == 1 and rows[0].get('split') == 'dev'
            and rows[0].get('budget_bucket') == 'development' and not rows[0].get('retry_of')
            and rows[0].get('iteration') == iteration
            and rows[0].get('profile') == 'C0'
            and type(rows[0].get('timeout_seconds')) is int
            and 0 < rows[0]['timeout_seconds'] <= 600,
            'CUDA memcheck is limited to one bounded development diagnostic')
    records = diagnostic['files']
    expected = {str(p) for p in MEMCHECK_TOOL.parent.iterdir() if p.is_file()}
    require({r['path'] for r in records} == expected and str(MEMCHECK_TOOL) in expected,
            'CUDA memcheck package fingerprint set changed')
    verify_files(records, allowed_roots=(MEMCHECK_TOOL.parent,))


def validate_memcheck_environment(plan, runtime):
    no_cache = (plan.get('cuda_memcheck') or {}).get('disable_caching_allocator', False)
    value = runtime.get('environment', {}).get('PYTORCH_NO_CUDA_MEMORY_CACHING')
    require(value == '1' if no_cache else value is None,
            'CUDA allocator environment differs from frozen diagnostic condition')


def instrument_command(command, plan, output):
    if plan.get('cuda_memcheck') is None:
        return command
    validate_memcheck(plan)
    blocking = ['--force-blocking-launches'] if plan['cuda_memcheck'].get('force_blocking_launches') else []
    return [str(MEMCHECK_TOOL), '--tool', 'memcheck', '--target-processes', 'application-only',
            '--error-exitcode', '86', *blocking, '--log-file', str(Path(output)/'cuda-memcheck.log'), *command]


def selected_rows(plan, split, iteration):
    rows = [r for r in plan['episodes'] if r['split'] == split and str(r['iteration']) == str(iteration)]
    require(rows, 'no episodes match split/iteration')
    # Do not sort parallel arrays: every child command receives its own pair.
    return rows


def build_command(plan, manifest, runtime, row, attempt_id):
    profile = manifest['profiles'][row['profile']]
    values = dict(profile['static_override_values'])
    provider_values = stage_overrides(runtime)
    if provider_values:
        require(not any(key.startswith(('perception.gemini.', '+perception.gemini.'))
                        and key not in provider_values for key in values),
                'unapproved static Codex provider override')
        require(all(key not in values or values[key] == value for key, value in provider_values.items()),
                'static/runtime Codex provider binding differs')
    values.update(provider_values)
    # Explicit per-episode policy RNG replaces historical run seed 0. All arms
    # use this new contract; this is not replay of the sequential historic RNG.
    values['seed'] = row['policy_seed']
    output = owned(Path(plan['artifact_root']) / 'attempts' / attempt_id, plan['artifact_root'])
    task = runtime['tasks'][str(row['task_id'])]
    bindings = {
        'main.episode_num': 1,
        'main.episode_seed_schedule': [row['env_seed']],
        'backend.libero.task_ids_filter': [row['task_id']],
        'main.cached_functions_dir': task['cache_dir'],
        'hydra.run.dir': str(output),
        'main.eds_eval.output_dir': str(output / 'eds_eval'),
        'main.eds_eval.report_dir': str(Path(plan['worktree']) / 'docs/03_evidence/qd_ed_final'),
        'main.eds_eval.job_id': attempt_id,
        'main.eds_eval.method_label': profile['historical_label'] + '__input_repaired' +
            ('__' + codex_stage_condition(runtime) if provider_values else ''),
        'main.eds_mechanism_pretest.output_dir': str(output / 'mechanism'),
        'main.eds_mechanism_pretest.run_id': attempt_id,
    }
    # A runtime setup may provide the named, opt-in cache identity guard only.
    require(runtime.get('main_overrides') == ['+main.require_task_cache_identity=true'], 'task-cache identity guard missing or modified')
    bindings['+main.require_task_cache_identity'] = True
    require(not (set(values) & set(bindings)), 'duplicate static/runtime override')
    values.update(bindings)
    command = [str(PYTHON), str(Path(plan['worktree']) / 'main.py')]
    command += [f'{key}={hydra(value)}' for key, value in values.items()]
    return instrument_command(command, plan, output), output


def authorized_gpu(state):
    """Return the one explicitly authorized physical device; never pick an idle GPU."""
    pool = state.get('gpu_pool')
    require(isinstance(pool, list) and len(pool) == 1 and type(pool[0]) is int
            and pool[0] >= 0 and type(state.get('max_concurrent_gpu_workers')) is int
            and state['max_concurrent_gpu_workers'] == 1,
            'GPU policy requires one authorized physical device and one worker')
    return pool[0]


def runtime_gpu(runtime, state=None):
    mapping = runtime.get('gpu_mapping', {})
    physical = mapping.get('physical_gpu')
    egl = mapping.get('egl_device_index')
    require(type(physical) is int and physical >= 0 and type(egl) is int and egl >= 0,
            'invalid frozen GPU mapping')
    if state is not None:
        require(authorized_gpu(state) == physical,
                'GPU policy/runtime physical device mismatch')
    return physical


def child_environment(runtime):
    env = dict(os.environ)  # Existing provider credentials are inherited, never serialized.
    env.pop('PYTORCH_NO_CUDA_MEMORY_CACHING', None)
    if runtime.get('frozen_stage_provider', {}).get('backend') == 'codex_cli':
        for name in codex_removed_environment():
            env.pop(name, None)
    env.update({k: str(v) for k, v in runtime['environment'].items()})
    # This opt-in diagnostic must never leak in from the launching shell.
    env['QD_ED_CUDA_EGL_SERIALIZE'] = str(runtime['environment'].get('QD_ED_CUDA_EGL_SERIALIZE', '0'))
    env['QD_ED_RENDER_LIFETIME'] = str(runtime['environment'].get('QD_ED_RENDER_LIFETIME', '0'))
    mapping=runtime['gpu_mapping']
    physical_gpu = runtime_gpu(runtime)
    # Historical p2_render_gpu_index is profile provenance, not a main.py
    # override. This frozen EGL binding selects the actual renderer device.
    env.update(CUDA_VISIBLE_DEVICES=str(physical_gpu), MUJOCO_EGL_DEVICE_ID=str(mapping['egl_device_index']), MUJOCO_GL='egl',
               CUDA_DEVICE_ORDER='PCI_BUS_ID', PYOPENGL_PLATFORM='egl', JOBLIB_MULTIPROCESSING='0', PYTHONUNBUFFERED='1')
    return env


def codex_policy_module():
    # This module contains only standard-library public configuration helpers.
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from core import codex_stage_policy
    return codex_stage_policy


def codex_removed_environment():
    return set(codex_policy_module()._REMOVED_ENVIRONMENT)


def codex_public_config(frozen):
    """Effective public invocation contract, never a hash of account files."""
    return codex_policy_module().public_invocation_policy(
        **{key: frozen[key] for key in CODEX_CONFIG_KEYS if key != 'backend'},
        output_format=frozen.get('output_format', 'legacy_text'))


def codex_stage_condition(runtime):
    mode = runtime.get('frozen_stage_provider', {}).get('output_format', 'legacy_text')
    require(mode in {'legacy_text', 'json_schema_v1'}, 'unknown frozen Stage output format')
    return 'codex_login_astra_low_json_v1' if mode == 'json_schema_v1' else CODEX_STAGE_CONDITION


def codex_public_config_sha256(frozen):
    return codex_policy_module().policy_sha256(codex_public_config(frozen))


def stage_overrides(runtime):
    frozen = runtime.get('frozen_stage_provider', {})
    if frozen.get('backend') != 'codex_cli':
        return {}
    codex_stage_condition(runtime)
    require(frozen.get('model') == 'gpt-6-astra' and frozen.get('auth_mode') == 'chatgpt',
            'Codex Stage model/auth differs from authorized contract')
    require(frozen.get('reasoning_effort') == 'low' and type(frozen.get('timeout_seconds')) is int
            and frozen['timeout_seconds'] == 90, 'Codex Stage reasoning/timeout differs from frozen contract')
    require(isinstance(frozen.get('cli_path'), str) and Path(frozen['cli_path']).is_absolute(),
            'Codex CLI path must be absolute')
    require(str(Path(frozen['cli_path']).resolve()) == frozen['cli_path'], 'Codex CLI path must identify the resolved executable')
    require(frozen.get('cli_version') == '0.155.1', 'Codex CLI version differs from frozen contract')
    disabled = frozen.get('disabled_skill_paths')
    require(isinstance(disabled, list) and disabled and all(isinstance(path, str) and Path(path).is_absolute()
            for path in disabled) and disabled == sorted(set(disabled)), 'Codex disabled skill paths must be a nonempty sorted absolute set')
    require(re.fullmatch(r'[0-9a-f]{64}', str(frozen.get('cli_sha256', ''))) is not None,
            'Codex CLI fingerprint missing')
    require(frozen.get('public_config_sha256') == codex_public_config_sha256(frozen),
            'Codex public invocation fingerprint mismatch')
    require(not any(key in frozen for key in ('api_key', 'base_url', 'credential_env_name', 'access_token')),
            'Codex managed login contract must not contain API credentials/endpoints')
    overrides = {f'perception.gemini.{key}': frozen[key] for key in CODEX_CONFIG_KEYS}
    if 'output_format' in frozen:
        overrides['perception.gemini.output_format'] = frozen['output_format']
    return overrides


def verify_provider(runtime, env, *, root=ROOT, run=subprocess.run):
    frozen=runtime['frozen_stage_provider']
    require(runtime.get('provider_ready') is True, 'Stage provider is not ready')
    perception=read_state(Path(root)/'configs/perception.yaml')['gemini']
    require(perception.get('api_key') is None, 'Stage credentials must remain environment-only')
    if frozen.get('backend') == 'codex_cli':
        stage_overrides(runtime)
        require(not any(env.get(name) for name in codex_removed_environment()), 'Codex child environment contains alternate authentication/provider binding')
        require(bool(env.get('HOME')), 'Codex managed login HOME is missing')
        installed = codex_policy_module().discover_disabled_skill_paths(
            codex_home=env.get('CODEX_HOME') or Path(env['HOME']) / '.codex', user_home=env['HOME'])
        require(installed == frozen['disabled_skill_paths'], 'Codex installed skill metadata differs from frozen disabled set')
        cli = Path(frozen['cli_path'])
        require(cli.is_file() and os.access(cli, os.X_OK) and digest(cli) == frozen['cli_sha256'],
                'Codex CLI executable changed or is unavailable')
        # Public CLI status only: never inspect, copy, hash or log auth.json.
        try:
            version = run([str(cli), '--version'], capture_output=True, text=True, timeout=15, env=env)
            login = run([str(cli), 'login', 'status'], capture_output=True, text=True, timeout=15, env=env)
        except (OSError, subprocess.TimeoutExpired):
            raise GateError('Codex managed login status unavailable') from None
        require(version.returncode == 0 and version.stdout.strip() == 'codex-cli ' + frozen['cli_version'],
                'Codex installed CLI version mismatch')
        status = (login.stdout + login.stderr).strip().lower()
        require(login.returncode == 0 and 'logged in using chatgpt' in status,
                'Codex CLI requires the authorized managed ChatGPT login')
        return
    effective_url=perception.get('base_url') or env.get('OPENAI_BASE_URL')
    require(isinstance(effective_url,str) and effective_url.rstrip('/')==frozen['base_url'].rstrip('/'), 'Stage provider endpoint differs from frozen contract')
    require(perception.get('model','gemini-2.5-flash')==frozen['model'], 'Stage model differs from frozen contract')
    credential_source='GOOGLE_API_KEY' if env.get('GOOGLE_API_KEY') else 'OPENAI_API_KEY'
    require(frozen.get('credential_env_name')==credential_source, 'Stage credential precedence differs from frozen binding')
    require(bool(env.get(credential_source)), 'Stage credential is absent')


def gpu_admission(run=subprocess.run, *, physical_gpu=7, expected_uuid=None):
    require(type(physical_gpu) is int and physical_gpu >= 0, 'invalid physical GPU index')
    apps = run(['nvidia-smi', '-i', str(physical_gpu), '--query-compute-apps=pid', '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=15)
    memory = run(['nvidia-smi', '-i', str(physical_gpu), '--query-gpu=memory.used', '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=15)
    require(apps.returncode == 0 and memory.returncode == 0, f'GPU{physical_gpu} admission probe failed')
    pids = [s.strip() for s in apps.stdout.splitlines() if s.strip() and 'no running' not in s.lower()]
    require(not pids, f'GPU{physical_gpu} has external compute processes')
    try:
        used = int(memory.stdout.strip())
    except ValueError as exc:
        raise GateError(f'GPU{physical_gpu} memory response invalid') from exc
    require(0 <= used < 1024, f'GPU{physical_gpu} memory is {used} MiB; requires <1024 MiB')
    if expected_uuid:
        identity=run(['nvidia-smi','-i',str(physical_gpu),'--query-gpu=uuid','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=15)
        require(identity.returncode==0 and identity.stdout.strip()==expected_uuid, f'GPU{physical_gpu} UUID differs from frozen mapping')
    return {'physical_gpu': physical_gpu, 'memory_used_mib': used, 'external_compute_processes': 0}


def check_exclusive_gpu(process, run=subprocess.run, *, physical_gpu=7):
    require(type(physical_gpu) is int and physical_gpu >= 0, 'invalid physical GPU index')
    probe=run(['nvidia-smi','-i',str(physical_gpu),'--query-compute-apps=pid','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=GPU_MONITOR_QUERY_TIMEOUT_SECONDS)
    require(probe.returncode==0, f'GPU{physical_gpu} exclusivity probe failed')
    for line in probe.stdout.splitlines():
        if not line.strip() or 'no running' in line.lower():
            continue
        require(line.strip().isdigit(), f'GPU{physical_gpu} exclusivity probe returned unknown PID')
        pid=int(line)
        try:
            own_group=os.getpgid(pid)==process.pid
        except ProcessLookupError:
            continue
        require(pid==process.pid or own_group, f'external GPU{physical_gpu} process appeared during owned attempt')


def check_kernel_faults(monitor, physical_gpu):
    if monitor is not None:
        try:
            monitor.check()
        except MonitorError as exc:
            raise GateError(f'GPU{physical_gpu} kernel monitor: {exc}') from exc


def start_kernel_monitor(runtime, output):
    physical_gpu = runtime_gpu(runtime)
    try:
        return KernelXidMonitor(runtime['gpu_mapping'], output)
    except MonitorError as exc:
        raise GateError(f'GPU{physical_gpu} kernel monitor: {exc}') from exc


def wait_exclusively(process, timeout, *, physical_gpu=7, fault_monitor=None):
    deadline=time.monotonic()+timeout
    while True:
        remaining=deadline-time.monotonic()
        if remaining<=0:
            raise subprocess.TimeoutExpired('owned episode',timeout)
        try:
            code = process.wait(timeout=min(5.,remaining))
        except subprocess.TimeoutExpired:
            check_kernel_faults(fault_monitor, physical_gpu)
            check_exclusive_gpu(process, physical_gpu=physical_gpu)
        else:
            check_kernel_faults(fault_monitor, physical_gpu)
            return code


@contextlib.contextmanager
def locked(path, *, nonblocking=False):
    with Path(path).open('a+') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | (fcntl.LOCK_NB if nonblocking else 0))
        except BlockingIOError as exc:
            raise LockBusyError(path) from exc
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def event_groups(events):
    groups = {}
    for event in events:
        require(event.get('event') in {'reserved', 'dispatched', 'valid', 'aborted'}, 'unknown ledger event')
        group = groups.setdefault(event['attempt_id'], [])
        require(not group or group[-1]['event'] not in TERMINAL, 'event after terminal attempt')
        require(event['event'] not in {e['event'] for e in group}, 'duplicate attempt event')
        require((not group and event['event'] == 'reserved') or
                (group and group[-1]['event'] == 'reserved' and event['event'] in {'dispatched','aborted'}) or
                (group and group[-1]['event'] == 'dispatched' and event['event'] in TERMINAL), 'illegal attempt transition')
        group.append(event)
    return groups


def budget_snapshot(events, resource_events=()):
    result = {'dispatched': 0, 'aborted': 0, 'valid': 0, 'invalid': 0, 'completed': 0,
              'running': 0, 'gpu_hours_consumed': 0.0,
              'by_bucket': {key: 0 for key in BUCKETS}, 'reserved_attempts': 0,
              'gpu_hours_by_bucket':{key:0. for key in BUCKETS},
              'gpu_healthcheck_hours':0.,'gpu_healthcheck_inflight':0}
    for group in event_groups(events).values():
        result['reserved_attempts'] += 1
        dispatched = next((e for e in group if e['event'] == 'dispatched'), None)
        if dispatched:
            result['dispatched'] += 1
            result['by_bucket'][dispatched['budget_bucket']] += 1
            result['running'] += int(group[-1]['event'] == 'dispatched')
        final = group[-1]
        if final['event'] in TERMINAL:
            if final['event'] == 'valid':
                # The journal terminal name means an adjudicated task outcome;
                # scientific validity remains separate from completion/success.
                result['completed'] += 1
                result['valid' if final.get('outcome_valid') is True else 'invalid'] += 1
            else:
                result['aborted'] += 1
            require('gpu_process_wall_seconds' in final, 'terminal episode GPU duration missing')
            elapsed = final['gpu_process_wall_seconds']
            require(isinstance(elapsed, (int,float)) and math.isfinite(elapsed) and elapsed >= 0, 'invalid recorded GPU duration')
            result['gpu_hours_consumed'] += elapsed / 3600
            result['gpu_hours_by_bucket'][final['budget_bucket']] += elapsed/3600
    normalized=[]
    for event in resource_events:
        require(event.get('event') in {'reserved','dispatched','completed','aborted'}, 'unknown GPU healthcheck event')
        normalized.append({**event,'attempt_id':event['resource_id'],'event':'valid' if event['event']=='completed' else event['event']})
    for group in event_groups(normalized).values():
        last=group[-1]
        if last['event'] not in TERMINAL:
            result['gpu_healthcheck_inflight']+=1
        else:
            require('gpu_process_wall_seconds' in last, 'terminal healthcheck GPU duration missing')
            seconds=last['gpu_process_wall_seconds']
            require(isinstance(seconds,(int,float)) and math.isfinite(seconds) and seconds>=0, 'invalid healthcheck GPU duration')
            result['gpu_healthcheck_hours']+=seconds/3600
    result['gpu_hours_consumed']+=result['gpu_healthcheck_hours']
    result['gpu_hours_by_bucket']['recovery']+=result['gpu_healthcheck_hours']
    return result


def check_budget(state, events, row, resource_events=(), reservation_events=(), *, physical_gpu=None):
    budget = state['budget']; snap = budget_snapshot(events,resource_events)
    selected_gpu = authorized_gpu(state)
    require(physical_gpu is None or (type(physical_gpu) is int and physical_gpu == selected_gpu),
            'GPU policy/runtime physical device mismatch')
    require(budget['max_episode_attempts'] <= 240 and budget['max_gpu_hours'] <= 48, 'budget exceeds authorization')
    require(snap['running'] == 0, 'unfinished dispatched attempt must be reconciled first')
    require(snap['gpu_healthcheck_inflight']==0, 'unfinished GPU healthcheck reservation must be reconciled first')
    require(budget['dispatched'] == snap['dispatched'], 'state/ledger dispatched mismatch')
    require(abs(budget['gpu_hours_consumed']-snap['gpu_hours_consumed']) < 1e-8, 'state/ledger GPU accounting mismatch')
    require(snap['dispatched'] < budget['max_episode_attempts'], 'episode budget exhausted')
    require(snap['gpu_hours_consumed'] < budget['max_gpu_hours'], 'GPU budget exhausted')
    require(budget['reserved']['validation'] >= 60 and budget['reserved']['formal'] >= 40, 'validation/formal reserve was reduced')
    bucket = row['budget_bucket']
    require(snap['by_bucket'][bucket] < min(BUCKETS[bucket], budget['reserved'][bucket]), f'{bucket} reserve exhausted')
    if bucket not in {'validation', 'formal'}:
        protected = max(0,60-snap['by_bucket']['validation']) + max(0,40-snap['by_bucket']['formal'])
        require(snap['dispatched'] + 1 + protected <= budget['max_episode_attempts'], 'would consume protected validation/formal reserve')
    default_reservations={'validation':14.,'formal':10.}
    reservations=budget.get('gpu_hour_reservations',default_reservations)
    require(isinstance(reservations,dict) and set(reservations)<=set(BUCKETS) and all(type(v) in (int,float) and math.isfinite(v) and v>=0 for v in reservations.values()), 'GPU-hour reservation policy invalid')
    require(sum(reservations.values())<=budget['max_gpu_hours'], 'GPU-hour reservations exceed total budget')
    if reservations!=default_reservations:
        require(bool(reservation_events) and reservation_events[-1].get('event')=='gpu_hour_reservations_changed' and
                reservation_events[-1].get('gpu_hour_reservations')==reservations and
                bool(reservation_events[-1].get('rationale')) and 'time_unix' in reservation_events[-1], 'GPU-hour reallocation requires matching reservation ledger event')
    protected_hours=sum(max(0.,hours-snap['gpu_hours_by_bucket'][name]) for name,hours in reservations.items() if name!=bucket)
    available=int((budget['max_gpu_hours']-snap['gpu_hours_consumed']-protected_hours)*3600)-TERMINATION_GRACE_SECONDS
    require(available>0, 'GPU budget cannot cover process termination grace')
    return min(row['timeout_seconds'],available)


def check_retry(events, row):
    groups = event_groups(events)
    prior = [g for g in groups.values() if g[0]['identity'] == episode_identity(row) and any(e['event']=='dispatched' for e in g)]
    require(not any(g[-1]['event'] == 'valid' for g in prior), 'legal completed outcome cannot be retried')
    if prior:
        retry_of = row.get('retry_of')
        require(retry_of in groups and groups[retry_of] in prior, 'repeat requires explicit matching retry_of')
        require(groups[retry_of][-1]['event'] == 'aborted' and groups[retry_of][-1].get('retryable_infrastructure') is True, 'only infrastructure abort is retryable')
        require(not any(g[0].get('retry_of') == retry_of for g in groups.values()), 'retry_of already consumed')
    else:
        require(not row.get('retry_of'), 'retry_of has no matching dispatched identity')


def append_event(root, event):
    root = Path(root); ledger = root/'data/attempt-ledger.jsonl'; state_path = root/'research-state.yaml'
    with locked(root/'data/qd-ed-state.lock'):
        events = read_events(ledger)
        event_groups([*events,event])
        with ledger.open('a') as stream:
            stream.write(json.dumps(event,sort_keys=True,allow_nan=False)+'\n'); stream.flush(); os.fsync(stream.fileno())
        # Journal first; a crash before replace is repaired explicitly from the durable ledger.
        sync_state_from_journal(root,[*events,event])


def sync_state_from_journal(root,events):
    """Caller holds qd-ed-state.lock. The journal is the transaction recovery source."""
    state_path=Path(root)/'research-state.yaml'; state=read_state(state_path)
    snapshot=budget_snapshot(events,read_events(Path(root)/'data/gpu-healthcheck-ledger.jsonl'))
    for key in ('dispatched','aborted','valid','invalid','completed','running','gpu_hours_consumed'):
        state['budget'][key]=snapshot[key]
    state['runner']={'by_bucket':snapshot['by_bucket'],'reserved_attempts':snapshot['reserved_attempts'],
                     'gpu_hours_by_bucket':snapshot['gpu_hours_by_bucket'],
                     'gpu_healthcheck_hours':snapshot['gpu_healthcheck_hours'],'gpu_healthcheck_inflight':snapshot['gpu_healthcheck_inflight'],
                     'last_attempt_id':events[-1]['attempt_id'] if events else None,
                     'last_event':events[-1]['event'] if events else None}
    temp=state_path.with_suffix('.yaml.runner-tmp')
    with temp.open('w') as stream:
        yaml.safe_dump(state,stream,sort_keys=False); stream.flush(); os.fsync(stream.fileno())
    os.replace(temp,state_path)


def append_healthcheck_event(root,event):
    """CPU-safe journal helper for an explicitly owned GPU probe; does not launch."""
    root=Path(root); path=root/'data/gpu-healthcheck-ledger.jsonl'
    with locked(root/'data/qd-ed-state.lock'):
        events=read_events(root/'data/attempt-ledger.jsonl'); resources=read_events(path)
        budget_snapshot(events,[*resources,event])
        with path.open('a') as stream:
            stream.write(json.dumps(event,sort_keys=True,allow_nan=False)+'\n'); stream.flush(); os.fsync(stream.fileno())
        sync_state_from_journal(root,events)


def episode_compute(output,row,runtime=None):
    records=read_events(Path(output)/'eds_eval/episode_compute.jsonl')
    require(len(records)==1, 'exactly one complete episode compute record required')
    record=records[0]
    codex = (runtime or {}).get('frozen_stage_provider', {}).get('backend') == 'codex_cli'
    require(record.get('schema') == ('qd-ed-episode-compute-v2' if codex else 'qd-ed-episode-compute-v1'), 'episode compute schema mismatch')
    require(record.get('episode_id')==0 and record.get('task_id')==row['task_id'] and record.get('episode_seed')==row['env_seed'], 'episode compute identity mismatch')
    require(all(record.get(name) is True for name in
                ('policy_counters_available','provider_counters_available','perception_counters_available')),
            'required cost counters unavailable')
    for key in COMPUTE_FIELDS:
        if codex and key in CODEX_UNKNOWN_HTTP_FIELDS:
            require(key in record and record[key] is None, f'Codex HTTP counts must be unknown: {key}')
            continue
        require(type(record.get(key)) is int and record[key]>=0, f'cost counter missing/invalid: {key}')
    batches=record.get('model_forward_batch_sizes')
    require(isinstance(batches,list) and all(type(n) is int and n>0 for n in batches), 'model batch histogram invalid')
    require(len(batches)==record['model_forward_calls'] and sum(batches)==record['model_batch_rows'], 'model forward/batch accounting mismatch')
    result = {**{key:record[key] for key in COMPUTE_FIELDS},'compute_outcome':record.get('outcome'),
              'required_cost_telemetry_complete':True}
    if not codex:
        return result
    stage_overrides(runtime)
    transport = record.get('stage_transport')
    require(isinstance(transport, dict), 'Codex Stage transport metadata missing')
    frozen = runtime['frozen_stage_provider']
    require(all(transport.get(key) == frozen[key] for key in CODEX_CONFIG_KEYS), 'Codex observed Stage transport differs from frozen binding')
    require(transport.get('auth_mode') == 'chatgpt' and
            transport.get('public_config_sha256') == frozen['public_config_sha256'],
            'Codex observed public invocation policy differs from frozen binding')
    mode = frozen.get('output_format', 'legacy_text')
    require(transport.get('output_format', 'legacy_text') == mode,
            'Codex observed Stage output format differs from frozen binding')
    if mode == 'json_schema_v1':
        require(transport.get('output_schema_sha256') == codex_public_config(frozen)['output_schema_sha256'],
                'Codex observed Stage output schema differs from frozen binding')
    require(transport.get('application_max_attempts') == 1 and
            transport.get('internal_http_retry_observation_available') is False and
            transport.get('internal_retry_policy') == 'cli_managed_unknown', 'Codex retry observation contract missing')
    require(record.get('provider_http_counters_available') is False and
            record.get('provider_logical_counters_available') is True, 'Codex HTTP/logical observation labels missing')
    for key in ('guidance_api_request_attempts', 'guidance_api_sdk_retry_attempts',
                'grounding_api_request_attempts', 'grounding_api_sdk_retry_attempts'):
        require(record[key] == 0, 'Codex study requires cached guidance and inactive grounding transport')
    for prefix in ('stage_codex_', 'provider_'):
        for suffix in CODEX_COUNT_SUFFIXES:
            key = prefix + suffix
            require(type(record.get(key)) is int and record[key] >= 0, f'Codex logical/token counter missing/invalid: {key}')
            result[key] = record[key]
        attempts = record[prefix + 'logical_call_attempts']
        require(all(record[prefix + suffix] <= attempts for suffix in ('completed_turns', 'failed_calls', 'usage_complete_calls')),
                'Codex call accounting exceeds actual logical attempts')
        require(record[prefix + 'cached_input_tokens'] <= record[prefix + 'input_tokens'], 'Codex cached token accounting mismatch')
        reasoning = record.get(prefix + 'reasoning_output_tokens')
        require(reasoning is None or (type(reasoning) is int and reasoning >= 0), 'Codex optional reasoning token counter invalid')
        latency = record.get(prefix + 'call_latency_s')
        require(type(latency) in (int, float) and math.isfinite(latency) and latency >= 0,
                'Codex call latency counter missing/invalid')
        result[prefix + 'reasoning_output_tokens'] = reasoning
        result[prefix + 'call_latency_s'] = latency
    require(all(record['stage_codex_' + suffix] == record['provider_' + suffix]
                for suffix in (*CODEX_COUNT_SUFFIXES, 'call_latency_s', 'reasoning_output_tokens')),
            'Codex aggregate/Stage observation accounting mismatch')
    usage_complete = record['provider_usage_complete_calls'] == record['provider_logical_call_attempts']
    require(record.get('provider_token_usage_complete') is usage_complete, 'Codex token usage completeness label mismatch')
    result.update(stage_transport=transport, stage_backend='codex_cli', stage_model=frozen['model'],
                  stage_condition=codex_stage_condition(runtime),
                  provider_http_counters_available=False, provider_logical_counters_available=True,
                  provider_http_observation='not_observable_through_codex_cli',
                  provider_token_usage_complete=usage_complete,
                  required_cost_telemetry_complete=usage_complete)
    return result


def validate_video(path):
    """Decode one frame on CPU; a filename or nonempty placeholder is insufficient."""
    import cv2
    capture=cv2.VideoCapture(str(path))
    try:
        ok,frame=capture.read()
        require(ok and frame is not None and frame.size>0, 'episode video first frame is not decodable')
    finally:
        capture.release()


def stage_query_summary(output,row):
    stages=read_events(Path(output)/'eds_eval/stage_events.jsonl')
    successful=failed=0
    for event in stages:
        require(event.get('episode_id')==0 and event.get('task_id')==row['task_id'] and event.get('episode_seed')==row['env_seed'], 'Stage identity mismatch')
        status=event.get('query_status')
        require(status in {'ok','error','completed_without_result_metadata','skipped'}, 'Stage query status missing/invalid')
        if status=='ok' and event.get('query_ok') is True:
            successful+=1
        elif status!='skipped' or (event.get('api_request_attempts') or 0)>0:
            failed+=1
    return {'stage_query_events':len(stages),'stage_successful_queries':successful,'stage_failed_queries':failed,
            'stage_skipped_queries':len(stages)-successful-failed,'stage_activity_observed':successful>0,
            'stage_all_queries_failed':failed>0 and successful==0}


def validate_codex_stage_events(output, costs):
    """Reconcile actual call events with whole-episode logical/token deltas."""
    actual = [event for event in read_events(Path(output) / 'eds_eval/stage_events.jsonl')
              if event.get('query_status') != 'skipped']
    require(len(actual) == costs['provider_logical_call_attempts'], 'Codex Stage event/logical call count mismatch')
    for event in actual:
        require(event.get('api_request_attempts') is None and event.get('api_sdk_retry_attempts') is None
                and event.get('api_request_counter_available') is False, 'Codex Stage event must disclose unobservable HTTP counts')
        require(event.get('codex_logical_call_attempts') == 1 and event.get('codex_usage_complete_calls') == 1,
                'Codex Stage event lacks one measured call with complete usage')
        require(event.get('transport', {}).get('public_config_sha256') == costs['stage_transport']['public_config_sha256'],
                'Codex Stage event public invocation differs from frozen contract')
    for suffix in CODEX_COUNT_SUFFIXES:
        values = [event.get('codex_' + suffix) for event in actual]
        require(all(type(value) is int and value >= 0 for value in values) and
                sum(values) == costs['provider_' + suffix], 'Codex Stage event/episode call or token accounting mismatch')
    latency = [event.get('codex_call_latency_s') for event in actual]
    require(all(type(value) in (int, float) and math.isfinite(value) and value >= 0 for value in latency) and
            math.isclose(sum(latency), costs['provider_call_latency_s'], rel_tol=1e-9, abs_tol=1e-6),
            'Codex Stage event/episode latency accounting mismatch')


def validate_result(output, row, profile, runtime=None):
    output=Path(output)
    require(not list(output.glob('episode_*/error.txt')), 'episode error artifact')
    require(not list(output.glob('episode_*/*fail_error.txt')), 'episode preparation/execution failure')
    resolved=read_state(output/'.hydra/config.yaml')
    for key,value in {**profile['static_override_values'], **stage_overrides(runtime or {}), 'seed':row['policy_seed'],
                       'main.episode_num':1,'main.episode_seed_schedule':[row['env_seed']],
                       'backend.libero.task_ids_filter':[row['task_id']],
                       'main.require_task_cache_identity':True}.items():
        if key=='backend':
            require(resolved['backend']['backend']==value, 'resolved backend mismatch')
            continue
        actual=resolved
        for part in key.lstrip('+').split('.'):
            actual=actual[part]
        require(actual==value, f'resolved configuration mismatch: {key}')
    result=(output/'results.txt').read_text()
    counts=re.findall(r'^Success count: ([01])/1$',result,re.M)
    rates=re.findall(r'^Success rate: ([0-9.]+)%$',result,re.M)
    require(len(counts)==len(rates)==1, 'results must describe exactly one episode')
    success=int(counts[0]); require(float(rates[0])==success*100., 'result count/rate mismatch')
    status='success' if success else 'fail'
    videos=[p for p in (output/'episode_1').glob(f'episode_1_{status}*.mp4') if p.is_file() and not p.is_symlink() and p.stat().st_size>0]
    require(videos, 'matching nonempty episode outcome video missing')
    validate_video(videos[0])
    metadata=read_events(output/'eds_eval/episode_metadata.jsonl')
    require(len(metadata)==1 and all(type(metadata[0].get(key)) is int and metadata[0][key]==value for key,value in
            {'episode_id':0,'episode_seed':row['env_seed'],'task_id':row['task_id']}.items()), 'episode metadata identity mismatch')
    metrics=read_events(output/'eds_eval/eds_metrics.jsonl')
    seen=set(); eds=profile['resolved_eds_config']; expected=eds['population_size']*(eds['cem_iters']+1)
    for record in metrics:
        require(record.get('episode')==0 and record.get('task_id')==row['task_id'], 'metric task identity mismatch')
        step=record.get('global_step'); require(type(step) is int and 0<=step<=720 and step not in seen, 'duplicate/invalid metric step'); seen.add(step)
        require(record.get('score_call_count')==eds['cem_iters']+1 and record.get('search_evaluation_count')==expected, 'search compute budget mismatch')
        require(record.get('qd_archive_enabled') is (eds['qd_archive_mode']=='grid_archive'), 'QD enabled identity mismatch')
        for key in ('nonfinite_count','gripper_qpos_violation_count','qd_accounting_violation_count','qd_elite_monotonicity_violation_count','qd_final_selection_mismatch_count','qd_secondary_invariant_violation_count'):
            require(type(record.get(key)) is int and record[key]==0, f'metric violation or missing field: {key}')
        require(type(record.get('action_mask_violation_max')) in (int,float) and math.isfinite(record['action_mask_violation_max']) and 0<=record['action_mask_violation_max']<=1e-6, 'action mask violation or missing field')
        for key,value in record.items():
            require(not (key.endswith('_fallback_used') and value is True), f'unapproved fallback: {key}')
        if eds['qd_archive_mode']=='grid_archive':
            require(record.get('qd_evaluation_count')==expected, 'archive accounting mismatch')
    stage_summary=stage_query_summary(output,row)
    require(not stage_summary['stage_all_queries_failed'], 'all actual Stage queries failed')
    safety=read_events(output/'eds_eval/safety_events.jsonl')
    require(not any(e.get('event')=='gripper_qpos_violation' and e.get('count',0)>0 for e in safety), 'gripper qpos safety violation')
    costs=episode_compute(output,row,runtime)
    require(costs['required_cost_telemetry_complete'], 'Codex token usage incomplete')
    if costs.get('stage_backend') == 'codex_cli':
        require(costs['provider_failed_calls'] == 0 and stage_summary['stage_failed_queries'] == 0,
                'Codex Stage call failure invalidates the frozen transport condition')
        validate_codex_stage_events(output, costs)
    require(costs['compute_outcome']=='completed', 'episode compute records an execution/preparation failure')
    require(costs['guided_chunks']==len(metrics), 'guided chunk/metric record accounting mismatch')
    require(costs['reward_scoring_batches']>=sum(m['score_call_count'] for m in metrics), 'actual scoring batches cannot be fewer than recorded search batches')
    return {'success':bool(success),'task_failure':not bool(success),'outcome_valid':True,
            'metric_chunks':len(metrics),'qd_activity_observed':any(m.get('qd_archive_active_for_chunk') is True for m in metrics),
            'candidate_evaluations':sum(m['search_evaluation_count'] for m in metrics),
            'score_batches':sum(m['score_call_count'] for m in metrics),**stage_summary,
            **costs,'cost_counter_caveat':('Codex logical calls, observed token usage and CLI wall latency are measured; internal HTTP requests/retries and optional reasoning tokens may be unknown.'
                if costs.get('stage_backend') == 'codex_cli' else
                'Forward calls are DiT invocations, not encoder inference; provider retry field classifies SDK retries only.')}


def failed_outcome(exc, output, row, *, launch_failed=False, runtime=None):
    monitor_timeout=isinstance(exc,subprocess.TimeoutExpired) and isinstance(exc.cmd,list) and exc.cmd[:1]==['nvidia-smi']
    infrastructure=(launch_failed and isinstance(exc,OSError)) or monitor_timeout or (isinstance(exc,GateError) and (re.search(r'GPU[0-9]+', str(exc)) is not None or 'exclusivity' in str(exc)))
    event='aborted' if infrastructure or isinstance(exc,KeyboardInterrupt) else 'valid'
    outcome={'reason':str(exc) if isinstance(exc,GateError) else type(exc).__name__,
             'retryable_infrastructure':infrastructure,'success':False,'task_failure':event=='valid',
             'outcome_valid':False,'failure_class':'infrastructure' if infrastructure else 'task_failure',
             'required_cost_telemetry_complete':False}
    if monitor_timeout:
        # TimeoutExpired can contain arbitrary argv/stdout/stderr. Retain only
        # the numeric device/timeout, never its raw string or subprocess data.
        physical_gpu = None
        try:
            value = exc.cmd[exc.cmd.index('-i') + 1]
            if isinstance(value, str) and re.fullmatch(r'[0-9]{1,6}', value):
                physical_gpu = int(value)
        except (ValueError, IndexError):
            pass
        seconds = exc.timeout if (type(exc.timeout) in (int, float)
                  and math.isfinite(exc.timeout) and exc.timeout > 0) else None
        device_label = f'GPU{physical_gpu}' if physical_gpu is not None else 'GPU'
        timeout_label = f' after {seconds:g} seconds' if seconds is not None else ''
        outcome.update(reason=f'{device_label} nvidia-smi monitor query timed out{timeout_label}',
                       failure_detail='gpu_monitor_timeout',
                       gpu_monitor_timeout={'physical_gpu': physical_gpu, 'timeout_seconds': seconds})
    try:
        outcome.update(episode_compute(output,row,runtime))
    except (GateError,OSError,ValueError,KeyError):
        pass
    try:
        outcome.update(stage_query_summary(output,row))
    except (GateError,OSError,ValueError,KeyError):
        pass
    return event,outcome


def terminate_owned(process):
    if process is not None and process.poll() is None:
        os.killpg(process.pid,signal.SIGTERM)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGKILL); process.wait(timeout=10)


def durable_json(path, value):
    path=Path(path); temp=path.with_suffix(path.suffix+'.tmp')
    with temp.open('w') as stream:
        json.dump(value,stream,indent=2,allow_nan=False); stream.write('\n')
        stream.flush(); os.fsync(stream.fileno())
    os.replace(temp,path)
    fd=os.open(path.parent,os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def run_plan(plan_path, *, split, iteration, episode_keys=None, root=ROOT):
    root=Path(root)
    with locked(root/'data/qd-ed-runner.lock',nonblocking=True):
        plan,manifest,runtime=validate_plan(plan_path,root=root)
        require(plan.get('phase_authorization', {}).get(split) is True, f'{split} has not passed its preregistered phase gate')
        rows=selected_rows(plan,split,iteration)
        if episode_keys:
            require(set(episode_keys)<={r['episode_key'] for r in rows}, 'requested episode key is not in selected plan')
            rows=[r for r in rows if r['episode_key'] in episode_keys]
        summaries=[]
        for row in rows:
            # Revalidate hashes per dispatch; no silent reuse after edits or cache mutation.
            plan,manifest,runtime=validate_plan(plan_path,root=root)
            events=read_events(root/'data/attempt-ledger.jsonl')
            check_retry(events,row)
            state = read_state(root/'research-state.yaml')
            physical_gpu = runtime_gpu(runtime, state)
            timeout=check_budget(state,events,row,read_events(root/'data/gpu-healthcheck-ledger.jsonl'),read_events(root/'data/gpu-hour-reservation-ledger.jsonl'),physical_gpu=physical_gpu)
            admission=gpu_admission(physical_gpu=physical_gpu,expected_uuid=runtime['gpu_mapping']['uuid'])
            attempt_id=f"{plan['run_name']}__{row['episode_key']}__{uuid.uuid4().hex[:12]}"
            command,output=build_command(plan,manifest,runtime,row,attempt_id)
            require(not output.exists(), 'attempt output already exists')
            output.mkdir(parents=True)
            base={'attempt_id':attempt_id,'identity':episode_identity(row),'episode_key':row['episode_key'],
                  'budget_bucket':row['budget_bucket'],'plan_sha256':digest(plan_path),'profile_manifest_sha256':plan['profiles_sha256'],
                  'runtime_manifest_sha256':plan['runtime_manifest_sha256'],'source_commit':plan['source_commit'],
                  'runtime_inventory_sha256':plan['runtime_inventory_sha256'],
                  'init_row_sha256':row['init_row_sha256'],
                  'retry_of':row.get('retry_of'),'output_dir':str(output),'physical_gpu':physical_gpu}
            if runtime.get('frozen_stage_provider', {}).get('backend') == 'codex_cli':
                base.update(stage_backend='codex_cli', stage_model=runtime['frozen_stage_provider']['model'],
                            stage_condition=codex_stage_condition(runtime))
            append_event(root,{**base,'event':'reserved','time_unix':time.time(),'admission':admission})
            durable_json(output/'command.json',{'argv':command,'environment_public':{**runtime['environment'],'CUDA_VISIBLE_DEVICES':str(physical_gpu),'CUDA_DEVICE_ORDER':'PCI_BUS_ID','MUJOCO_EGL_DEVICE_ID':str(runtime['gpu_mapping']['egl_device_index'])}})
            process=None; started=time.monotonic(); process_finished=None; dispatched=False
            outcome={'retryable_infrastructure':False}; final_event='aborted'
            try:
                # Recheck immediately before dispatch; the global runner lock prevents owned concurrency.
                runtime_gpu(runtime, read_state(root/'research-state.yaml'))
                gpu_admission(physical_gpu=physical_gpu,expected_uuid=runtime['gpu_mapping']['uuid'])
                env=child_environment(runtime)
                verify_provider(runtime,env,root=root)
                runtime_gpu(runtime, read_state(root/'research-state.yaml'))
                fault_monitor = start_kernel_monitor(runtime, output)
                append_event(root,{**base,'event':'dispatched','time_unix':time.time(),'timeout_seconds':timeout})
                dispatched=True; started=time.monotonic()
                with (output/'runner.log').open('w') as log:
                    process=subprocess.Popen(command,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                    fault_monitor.pid = process.pid
                    try:
                        start_ticks=Path(f'/proc/{process.pid}/stat').read_text().rsplit(')',1)[1].split()[19]
                    except FileNotFoundError:
                        start_ticks=None
                    durable_json(output/'process.json',{'pid':process.pid,'time_unix':time.time(),'attempt_id':attempt_id,
                                 'proc_start_ticks':start_ticks,'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip()})
                    code=wait_exclusively(process,timeout,physical_gpu=physical_gpu,fault_monitor=fault_monitor)
                    process_finished=time.monotonic()
                require(code==0, f'child exit code {code}')
                outcome=validate_result(output,row,manifest['profiles'][row['profile']],runtime); final_event='valid'
            except BaseException as exc:
                # Fail closed: parser/gate/scientific invalidity is never an automatic recovery retry.
                final_event,outcome=failed_outcome(exc,output,row,launch_failed=dispatched and process is None,runtime=runtime)
                if not dispatched:
                    final_event='aborted'; outcome['task_failure']=False; outcome['failure_class']='predispatch_gate'
                if isinstance(exc,(KeyboardInterrupt,SystemExit)):
                    raise
            finally:
                terminate_owned(process)
                elapsed=(process_finished or time.monotonic())-started if dispatched else 0.0
                terminal={**base,**outcome,'event':final_event,'time_unix':time.time(),
                          'gpu_process_wall_seconds':elapsed,'gpu_time_measurement':f'exclusive GPU{physical_gpu} process wall-time upper bound, includes startup/abort'}
                append_event(root,terminal)
                durable_json(output/'attempt-result.json',terminal)
                summaries.append(terminal)
            require(final_event=='valid' and outcome.get('outcome_valid') is True, f'attempt stopped after failure; no automatic retry: {attempt_id}')
        return summaries


def reconcile_ledger(plan_path, attempt_id, *, root=ROOT):
    """Close a provably dead interrupted child; never terminate another process.

    Unknown SIGKILL end time is conservatively charged through reconciliation.
    A completed valid task remains valid, so reconciliation cannot launder a
    legal failure into a retry. Invalid completed artifacts are not retryable.
    """
    root=Path(root)
    with locked(root/'data/qd-ed-runner.lock',nonblocking=True):
        plan,manifest,runtime=validate_plan(plan_path,root=root,require_frozen=False)
        events=read_events(root/'data/attempt-ledger.jsonl'); groups=event_groups(events)
        require(attempt_id in groups, 'unknown attempt')
        group=groups[attempt_id]; last=group[-1]
        if last['event'] in TERMINAL:
            with locked(root/'data/qd-ed-state.lock'):
                sync_state_from_journal(root,events)
            return {'attempt_id':attempt_id,'event':last['event'],'state_reconciled_from_existing_terminal':True}
        require(last['plan_sha256']==digest(plan_path), 'interrupted attempt requires its original frozen plan')
        output=owned(last['output_dir'],plan['artifact_root'])
        # A child may exist in the launch-to-PID-journal window. Inspect cmdline
        # without relying on a PID that could have been reused after reboot.
        for proc in Path('/proc').iterdir():
            if not proc.name.isdigit():
                continue
            try:
                args=(proc/'cmdline').read_bytes().split(b'\0')
            except (FileNotFoundError,ProcessLookupError,PermissionError):
                continue
            require(not (str(root/'main.py').encode() in args and any(attempt_id.encode() in arg for arg in args)), 'interrupted child is still alive')
        physical_gpu = runtime_gpu(runtime, read_state(root/'research-state.yaml'))
        require(last.get('physical_gpu') == physical_gpu, 'interrupted attempt GPU differs from its frozen runtime')
        gpu_admission(physical_gpu=physical_gpu,expected_uuid=runtime['gpu_mapping']['uuid'])
        dispatched=next((e for e in group if e['event']=='dispatched'),None)
        rows=[r for r in plan['episodes'] if r['episode_key']==last['episode_key']]
        require(len(rows)==1, 'interrupted episode no longer uniquely in plan')
        outcome={'reason':'interrupted process no longer alive','retryable_infrastructure':True}; event='aborted'
        if (output/'results.txt').exists():
            try:
                outcome=validate_result(output,rows[0],manifest['profiles'][rows[0]['profile']],runtime); event='valid'
            except (GateError,OSError,ValueError,KeyError) as exc:
                event,outcome=failed_outcome(exc,output,rows[0],runtime=runtime)
        terminal={**group[0],**outcome,'event':event,'time_unix':time.time(),
                  'gpu_process_wall_seconds':max(0.,time.time()-dispatched['time_unix']) if dispatched else 0.,
                  'gpu_time_measurement':'conservative upper bound through explicit dead-process reconciliation'}
        append_event(root,terminal); durable_json(output/'attempt-result.json',terminal)
        return terminal


def main(argv=None):
    def interrupted(_signum,_frame):
        raise KeyboardInterrupt('owned runner interrupted')
    signal.signal(signal.SIGTERM,interrupted)
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    for name in ('validate-plan','print-command','run'):
        item=sub.add_parser(name)
        item.add_argument('--plan',type=Path,default=ROOT/'data/qd-ed-final-plan.json')
        if name!='validate-plan':
            item.add_argument('--split',choices=('dev','validation','formal'),required=True)
            item.add_argument('--iteration',required=True)
        if name=='run':
            item.add_argument('--episode-key',action='append',help='Execute only explicitly named pending episodes; never resume completed outcomes')
        if name!='run':
            item.add_argument('--allow-unfrozen',action='store_true',help='CPU review only; never enables a launch')
    reconcile=sub.add_parser('reconcile-ledger',help='Close a dead interrupted process with conservative GPU time, never rerun it')
    reconcile.add_argument('--plan',type=Path,required=True)
    reconcile.add_argument('--attempt-id',required=True)
    args=parser.parse_args(argv)
    try:
        if args.command=='run':
            result=run_plan(args.plan,split=args.split,iteration=args.iteration,episode_keys=args.episode_key)
        elif args.command=='reconcile-ledger':
            result=reconcile_ledger(args.plan,args.attempt_id)
        else:
            plan,manifest,runtime=validate_plan(args.plan,require_frozen=not args.allow_unfrozen)
            if args.command=='validate-plan':
                result={'valid':True,'frozen':plan.get('frozen') is True,'episodes':len(plan['episodes']),'GPU_launches':0}
            else:
                result=[{'episode_key':r['episode_key'],'argv':build_command(plan,manifest,runtime,r,'PREVIEW__'+r['episode_key'])[0]} for r in selected_rows(plan,args.split,args.iteration)]
        print(json.dumps(result,indent=2,allow_nan=False))
        return 0
    except (GateError,KeyError,ValueError,OSError) as exc:
        print(json.dumps({'error':str(exc),'command':args.command}),file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print(json.dumps({'error':'owned runner interrupted; child terminated and attempt accounted'}),file=sys.stderr)
        return 130


if __name__=='__main__':
    raise SystemExit(main())
