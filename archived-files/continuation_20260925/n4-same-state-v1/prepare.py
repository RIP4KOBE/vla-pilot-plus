#!/usr/bin/env python3
"""Freeze the single user-approved N4 diagnostic after CPU-only gates."""
from __future__ import annotations
import importlib.util
import json
import pathlib
import subprocess
import sys
import uuid

D = pathlib.Path(__file__).resolve().parent
W = pathlib.Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z')
A = D.parents[1]
B = A / 'continuation_20260924' / 'n4-e1-dev-v1'
SOURCE = A / 'attempts/rdt-qd-ed-final-20260921T093925Z__n4e1_dev_t09_n4_20260924__7a16cf55edcc/.hydra/config.yaml'
spec = importlib.util.spec_from_file_location('qd_ed_final_runner', W / 'scripts/qd_ed_final_runner.py')
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)

def main():
    destination = D / 'plan.frozen.json'
    assert not destination.exists(), 'single diagnostic plan already frozen'
    original = r.read_json(B / 'plan.frozen.json')
    runtime = r.read_json(original['runtime_manifest_path'])
    inventory = r.read_json(original['runtime_inventory_path'])
    row = next(x for x in original['episodes'] if x['profile'] == 'N4' and x['task_id'] == 9)
    assert row['env_seed'] == row['policy_seed'] == 1045350852 and row['init_index'] == 0
    assert row['init_row_sha256'] == 'd8309b31899377d1051f6d7da47edc747b294842a6fec748aff6c9b822d8797e'
    assert runtime['gpu_mapping']['physical_gpu'] == 3
    assert runtime['gpu_mapping']['uuid'] == 'GPU-62052fa1-37e0-79dc-21aa-5c0f25c0c315'
    assert runtime['gpu_mapping']['egl_device_index'] == 0
    assert r.digest(original['runtime_manifest_path']) == original['runtime_manifest_sha256']
    assert r.digest(original['runtime_inventory_path']) == original['runtime_inventory_sha256']
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=W,text=True).strip() == original['source_commit']
    # The frozen N4 code is untouched; docs/state may have newer accounting artifacts.
    changed = subprocess.check_output(['git','diff','--name-only'],cwd=W,text=True).splitlines()
    assert not any(x.startswith(('core/','utils/','vlm_query/','configs/','third_party/','scripts/')) or x == 'main.py' for x in changed), changed
    code = {x['path']:x for x in original['code_files']}
    critical = ('main.py','core/rdt_policy_steer.py','core/qd_ed.py',
                'core/qd_terminal_population.py','core/decision_evidence.py',
                'core/rdt_libero_action_converter.py','core/env_adapters/libero_adapter.py',
                'scripts/qd_ed_final_runner.py','configs/policy.yaml','configs/perception.yaml',
                'configs/backend/libero.yaml','vlm_query/vlm_agent.py')
    r.verify_files([code[x] for x in critical],root=W)
    task = runtime['tasks']['9']
    runtime_files = {x['path']:x for x in runtime['files']}
    task_files = [runtime_files[x] for x in (task['bddl_path'],task['init_path'])]
    task_files += [x for x in runtime['files'] if '/runtime/guidance/task_9/' in x['path']]
    r.verify_files(task_files)
    checkpoint = inventory['checkpoint'][0]
    assert pathlib.Path(checkpoint['path']).is_file() and pathlib.Path(checkpoint['path']).stat().st_size == checkpoint['size_bytes']
    # Rehash the actual RDT checkpoint; retain the already frozen encoder hashes.
    assert r.digest(checkpoint['path']) == checkpoint['sha256']
    assert r.digest(SOURCE) and r.digest(D / 'child.py') and r.digest(D / 'protocol-v1.md')
    attempt = f"rdt-qd-ed-final-20260921T093925Z__n4_same_state_t09_20260925__{uuid.uuid4().hex[:12]}"
    plan = {
        'schema':'n4-same-state-diagnostic-plan-v1','attempt_id':attempt,
        'diagnostic_only':True,'phase':'dev','budget_bucket':'development',
        'task_id':9,'env_seed':1045350852,'policy_seed':1045350852,'init_index':0,
        'init_row_sha256':row['init_row_sha256'],
        'source_config':str(SOURCE),'source_config_sha256':r.digest(SOURCE),
        'source_plan':str(B/'plan.frozen.json'),'source_plan_sha256':r.digest(B/'plan.frozen.json'),
        'runtime_manifest':original['runtime_manifest_path'],
        'runtime_manifest_sha256':original['runtime_manifest_sha256'],
        'protocol':str(D/'protocol-v1.md'),'protocol_sha256':r.digest(D/'protocol-v1.md'),
        'child_sha256':r.digest(D/'child.py'),
        'supervisor_sha256':r.digest(D/'supervisor.py'),
        'source_commit':original['source_commit'],
        'critical_code':[{**code[x],'path':str(W/x)} for x in critical],
        'task_input_files':task_files,
        'checkpoint':checkpoint,
        'encoder_files':[x for e in inventory['hf_encoders'] for x in e['files']],
        'physical_gpu':3,'gpu_uuid':runtime['gpu_mapping']['uuid'],
        'egl_device_index':0,
        'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        'output_dir':str(D/attempt),
        'timeout_seconds':1800,'cleanup_seconds':40,
        'max_diagnostic_transitions':32,'max_settling_steps':40,
        'decision_count_max':1,'contrast_branches_max':2,
        'validation_authorized':False,'formal_authorized':False,
    }
    with destination.open('x') as f:
        json.dump(plan,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps({'plan':str(destination),'sha256':r.digest(destination),'attempt_id':attempt}))

if __name__ == '__main__': main()
