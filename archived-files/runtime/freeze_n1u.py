"""CPU-only one-time freeze of the final bounded common-deadline cohort."""
from pathlib import Path
import copy
import datetime
import json
import os
import subprocess
import sys
import yaml

W = Path('/home/hynx/VLA-Pilot++/.worktree/exp/rdt-qd-ed-gpu6-20260922T063626Z')
A = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(W / 'scripts'))
import qd_ed_final_runner as r

now = datetime.datetime.now(datetime.timezone.utc).isoformat()
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=W, text=True).strip()
old_path = W / 'data/qd-ed-n1t-reconnect-stage-plan.json'
old = r.read_json(old_path)
old_rt = r.read_json(old['runtime_manifest_path'])
rt = copy.deepcopy(old_rt)
rt['frozen_stage_provider']['timeout_seconds'] = 180
rt['frozen_stage_provider']['public_config_sha256'] = r.codex_public_config_sha256(rt['frozen_stage_provider'])
label = r.codex_stage_condition(rt)
rt.update(stage_condition=label, controls_label_suffix='__input_repaired__' + label,
    provider_frozen_at=now,
    provider_note='Final bounded common deadline180s; all other Stage and algorithm conditions unchanged. N1T incomplete and excluded; no retries or further replacement cohort.')
protocol = 'experiments/iteration_001_execution_intent/codex-stage-timeout-amendment.md'
rt['deadline_evidence'] = {'protocol': protocol,
    'timeout_audit': str(A / 'analysis/n1t-stage-timeout/audit.json'),
    'timeout_audit_sha256': r.digest(A / 'analysis/n1t-stage-timeout/audit.json'),
    'focused_cpu_tests_passed': 187, 'resource_lock_tests_passed': 6,
    'underlying_service_delay_cause': 'unknown', 'latency_repair_proven': False}
exclude = {'timeout_seconds', 'public_config_sha256'}
assert {k:v for k,v in rt['frozen_stage_provider'].items() if k not in exclude} == {
    k:v for k,v in old_rt['frozen_stage_provider'].items() if k not in exclude}
rt_dir = A / 'runtime/n1u-deadline-stage'
rt_dir.mkdir(parents=True, exist_ok=False)
rt_path = rt_dir / 'runtime-manifest.json'
r.durable_json(rt_path, rt)
p = copy.deepcopy(old)
p.update(source_commit=head, stage_condition=label, runtime_manifest_path=str(rt_path),
    runtime_manifest_sha256=r.digest(rt_path), frozen_at=now, cohort_amendment=protocol)
for row in p['episodes']:
    row['episode_key'] = row['episode_key'].replace('n1t_', 'n1u_', 1)
    row['iteration'] = 'N1U'
exclude = {'episode_key', 'iteration'}
assert all({k:v for k,v in a.items() if k not in exclude} == {
    k:v for k,v in b.items() if k not in exclude} for a,b in zip(p['episodes'], old['episodes']))
p['cohort_context'].update(iteration='N1U', common_intervention='Common Stage deadline90to180seconds; final bounded availability adjustment',
    parent_N1T_status='INCOMPLETE_STAGE_TIMEOUT', parent_N1T_plan=str(old_path),
    parent_N1T_sha256=r.digest(old_path), parent_N1T_valid=17, parent_N1T_dispatched=18,
    final_replacement_cohort=True, remaining_development_slots_after_full_cohort=25,
    conditional_N2_H_not_fundable_after_full_cohort=True)
paths = {v['path'] for v in p['code_files']} | {protocol, 'tests/test_codex_stage.py', 'tests/test_qd_ed_final_runner.py'}
p['code_files'] = [{'path':f, 'sha256':r.digest(W/f), 'size_bytes':(W/f).stat().st_size} for f in sorted(paths)]
plan_path = W / 'data/qd-ed-n1u-deadline-stage-plan.json'
assert not plan_path.exists()
r.durable_json(plan_path, p)
resource = A / 'resource/n1u-cohort-lock'
resource.mkdir(parents=True, exist_ok=False)
wrapper = A / 'runtime/n1u_cohort_queue.py'
prefix = A / 'runtime/n1u-gpu2-cohort-queue'
m = {'schema':'qd-ed-resource-cohort-lock-v1', 'created_at':now, 'worktree':str(W),
    'plan_path':str(plan_path), 'plan_sha256':r.digest(plan_path), 'source_commit':head,
    'wrapper_path':str(wrapper), 'wrapper_sha256':r.digest(wrapper),
    'test_sha256':r.digest(A/'runtime/test_n1u_cohort_queue.py'), 'cpu_tests_passed':6,
    'episode_keys':[row['episode_key'] for row in p['episodes']],
    'status_path':str(prefix)+'-status.json', 'lease_events_path':str(resource/'lease-events.jsonl'),
    'physical_gpu':2, 'max_concurrent_gpu_workers':1, 'application_retries_added':0,
    'episode_retries_added':0, 'final_replacement_cohort':True}
r.durable_json(resource/'manifest.json', m)
with r.locked(W/'data/qd-ed-state.lock'):
    events = r.read_events(W/'data/attempt-ledger.jsonl')
    r.sync_state_from_journal(W, events)
    s = r.read_state(W/'research-state.yaml')
    s['source_commit'] = head
    s['study']['status'] = 'N1U_FROZEN_READY_GPU2'
    s['gpu_pool'] = [2]
    s['stage_condition'].update(label=label, timeout_seconds=180, runtime_manifest=str(rt_path))
    s['n1t_live_progress'].update(observed_at=now, valid_completed=17, C0='0/8', Q0='1/9',
        successful_stage_calls=309, failed_stage_calls=0, recovered_reconnect_calls=2,
        next_key=None, cohort_status='INCOMPLETE_STAGE_TIMEOUT', dispatched=18,
        invalid_terminal=1, all_dispatched_stage_calls=330, all_dispatched_stage_failed_calls=1,
        all_dispatched_recovered_reconnect_calls=3, queue_alive=False)
    s['n1t_plan']['status'] = 'closed_incomplete'
    s['n1u_plan'] = {'path':str(plan_path), 'sha256':r.digest(plan_path), 'source_commit':head,
        'episodes':30, 'stage_condition':label, 'physical_gpu':2, 'status_prefix':str(prefix),
        'resource_manifest':str(resource/'manifest.json'), 'status':'frozen_ready'}
    q = W/'research-state.yaml.progress-tmp'
    with q.open('w') as f:
        yaml.safe_dump(s, f, sort_keys=False); f.flush(); os.fsync(f.fileno())
    os.replace(q, W/'research-state.yaml')
folder = A/'analysis/n1u-preflight'
folder.mkdir(parents=True, exist_ok=True)
r.durable_json(folder/'cpu-checks.json', {'observed_at':now, 'source_commit':head,
    'production_tests':{'passed':187, 'elapsed_seconds':9.14,
        'suites':['test_codex_stage','test_qd_ed_final_runner','test_qd_ed_available_gpu_queue',
                  'test_qd_ed_shared_queue','test_qd_ed_unverified_gpu_queue','test_qd_ed_codex_launch','test_stage_recognition_trace']},
    'resource_lock_tests':{'passed':6, 'elapsed_seconds':0.28},
    'only_provider_contract_diff':['timeout_seconds','public_config_sha256'],
    'original_task_seed_init_order_preserved':True})
print(json.dumps({'plan':str(plan_path), 'plan_sha256':r.digest(plan_path), 'source_commit':head,
    'runtime_sha256':r.digest(rt_path), 'public_config_sha256':rt['frozen_stage_provider']['public_config_sha256'],
    'manifest':str(resource/'manifest.json'), 'manifest_sha256':r.digest(resource/'manifest.json')}))
