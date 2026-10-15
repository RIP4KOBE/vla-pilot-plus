import os, sys, json, time, hashlib
from pathlib import Path
os.sched_setaffinity(0, sorted(os.sched_getaffinity(0))[:2])
sys.path.insert(0, str(Path.cwd()))
from scripts import qd_ed_final_runner as r, qd_ed_n27_cont_contract as c, qd_ed_n23_worker as w
from hydra import initialize_config_dir, compose
from omegaconf import OmegaConf
start = time.monotonic()
plan = r.read_json(c.PLAN)
seal = c.history()
manifest = r.read_json(plan['profiles_path'])
runtime = r.read_json(plan['runtime_manifest_path'])
for arm, reference in plan['candidate_profiles'].items():
    manifest['profiles'][arm] = r.expand_candidate(arm, r.read_json(reference['path']), manifest['profiles']['Q0'])
assert plan['episodes'] == c.rows(seal) and len(plan['episodes']) == 13
frozen = runtime['frozen_stage_provider']
assert frozen['backend'] == 'codex_cli' and frozen['auth_mode'] == 'chatgpt'
rows = []
for row in plan['episodes']:
    argv, output = r.build_command(plan, manifest, runtime, row, 'ROOT_COMPOSE_ONLY__' + row['episode_key'])
    with initialize_config_dir(version_base=None, config_dir=str(Path.cwd() / 'configs')):
        cfg = compose(config_name='config', overrides=argv[2:])
        eds = OmegaConf.to_container(cfg.main.eds_config, resolve=True)
        stage = OmegaConf.to_container(cfg.perception.gemini, resolve=False)
    assert eds['diversity_update_mode'] == ('feasible_ray_v1' if row['profile'] == 'N27' else 'legacy_additive')
    assert all(stage[key] == frozen[key] for key in r.CODEX_CONFIG_KEYS)
    assert not any(v.startswith(('perception.gemini.api_key=', 'perception.gemini.base_url=')) for v in argv[2:])
    rows.append({'episode_key': row['episode_key'], 'profile': row['profile'], 'task_id': row['task_id'], 'composed': True,
                 'update_mode': eds['diversity_update_mode'], 'argv_sha256': hashlib.sha256(json.dumps(argv, separators=(',', ':')).encode()).hexdigest(),
                 'stage_backend': stage['backend'], 'frozen_stage_auth': frozen['auth_mode']})
assert 'main' not in sys.modules
torch = sys.modules.get('torch')
assert torch is None or not torch.cuda.is_initialized()
record = {'schema': 'n27-hydra-continuation-root-command-review-v1', 'accepted': True, 'plan': c.ref(c.PLAN), 'source_commit': plan['source_commit'],
          'commands': rows, 'wall_seconds': time.monotonic()-start, 'main_executions': 0, 'api_calls': 0, 'gpu_calls': 0,
          'torch_imported': torch is not None, 'cuda_initialized': False, 'old_three_valid_controls_inherited': True,
          'one_named_recovery_only': True, 'new_budget_counts': {'baseline': 3, 'development': 9, 'recovery': 1},
          'provider': 'codex_cli/chatgpt/current_managed_login', 'protected_phases_authorized': False,
          'root_harness_failures': [
              {'error': 'KeyError: auth_mode', 'cause': 'Queried Hydra config for a field bound in runtime and Stage transport, not a Hydra override.'},
              {'error': 'AssertionError', 'cause': 'All 13 compositions passed; final harness incorrectly required torch absent. Pure native validation imports torch without initializing CUDA.'}],
          'root_harness_failure_gpu_api_main_calls': 0}
path = c.RUN_DIR / 'root-command-review-v1.json'
assert not path.exists()
w.atomic_json(path, record)
print(json.dumps({'review': c.ref(path), 'composed': len(rows), 'wall_seconds': record['wall_seconds'], 'cuda_initialized': False}))
