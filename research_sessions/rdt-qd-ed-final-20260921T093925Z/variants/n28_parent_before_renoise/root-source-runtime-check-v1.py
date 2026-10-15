"""Read-only actual owning source/runtime inventory check before any N28 release."""
from pathlib import Path
import json,sys,time,datetime,subprocess,hashlib
V=Path(__file__).resolve().parent;ROOT=V.parents[1]/'study_worktree'
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from scripts import qd_ed_final_runner as r,qd_ed_n23_worker as w,qd_ed_n28_contract as c,qd_ed_n28_bridge as bridge
started=time.monotonic()
source=w.source_record(ROOT,c.source_paths(vars(r)))
assert source==json.loads((V/'source-manifest-execution-v1.json').read_text())
runtime_ref=c.runtime_ref();runtime=w.read_ref(runtime_ref)
c.require_protocols(ROOT);c.validate_runtime(runtime,ROOT,vars(r));r.stage_overrides(runtime)
original=c.original_plan()
ip=Path(original['runtime_inventory_path'])
assert w.sha(ip)==original['runtime_inventory_sha256']
inventory=json.loads(ip.read_text())
assert inventory['schema']=='qd-ed-runtime-inventory-v1'
r.verify_files(inventory['checkpoint'])
for encoder in inventory['hf_encoders']:
    r.verify_files(encoder['files'])
    if 'snapshot' in encoder:
        snapshot=Path(encoder['snapshot'])
        assert {p.resolve() for p in snapshot.parent.iterdir() if p.is_dir()}=={snapshot.resolve()}
r.verify_files([inventory['dinov2']['weights']])
seed_path=Path(original['seed_plan_path'])
assert w.sha(seed_path)==original['seed_plan_sha256']
seeds=json.loads(seed_path.read_text());rows=c.expected_rows()
for row in rows:
    task=runtime['tasks'][str(row['task_id'])]
    assert w.sha(task['bddl_path'])==row['bddl_sha256']
    assert w.sha(task['init_path'])==row['init_file_sha256']
    seed=next(x for x in seeds['blocks']['dev'] if x['task_id']==row['task_id'])
    for key in ('env_seed','policy_seed','init_index','init_row_sha256','init_file_sha256','bddl_sha256'):assert row[key]==seed[key]
provider=runtime['frozen_stage_provider']
assert provider['backend']=='codex_cli' and provider['auth_mode']=='chatgpt'
assert provider['model']=='gpt-6-astra' and provider['reasoning_effort']=='low' and provider['timeout_seconds']==180
login=subprocess.run([provider['cli_path'],'login','status'],capture_output=True,text=True)
assert login.returncode==0 and (login.stdout+login.stderr).strip()=='Logged in using ChatGPT'
with r.locked(ROOT/'data/qd-ed-state.lock'):
    state=r.read_state(ROOT/'research-state.yaml')
    events=r.read_events(ROOT/'data/attempt-ledger.jsonl');resources=r.read_events(ROOT/'data/gpu-healthcheck-ledger.jsonl')
    snap=r.budget_snapshot(events,resources)
assert snap['running']==snap['gpu_healthcheck_inflight']==0
assert snap['dispatched']==355 and abs(snap['gpu_hours_consumed']-48.11473511024311)<1e-8
assert (V/'artifacts').is_symlink() and (V/'artifacts').resolve()==Path(state['artifacts']).resolve()/'variants/n28_parent_before_renoise'
actual_bridge=bridge.build(source,runtime_ref,ROOT)
w.atomic_json(V/'source-equivalence-bridge-v1.json',actual_bridge)
report={'schema':'n28-root-current-source-runtime-check-v1','accepted':True,'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'source':c.ref(V/'source-manifest-execution-v1.json'),'owning_worktree':str(ROOT),'source_commit':source['commit'],'source_files_verified':len(source['files']),
 'source_bridge':c.ref(V/'source-equivalence-bridge-v1.json'),'runtime':runtime_ref,
 'inventory':{'path':str(ip),'sha256':original['runtime_inventory_sha256']},'checkpoint_and_encoder_bytes_verified':True,
 'runtime_input_task_ids':[0,1,2,3],'seed_init_bddl_bindings_verified':16,
 'provider':{k:provider[k] for k in ('backend','auth_mode','model','reasoning_effort','timeout_seconds','cli_path')},
 'login_status':'Logged in using ChatGPT','poe_allowed':False,'credential_files_read_or_modified':False,
 'budget_snapshot':snap,'native_proof_run':False,'gpu_dispatch_authorized':False,'root_gpu_model_api_sim_calls':0,
 'wall_seconds':time.monotonic()-started}
w.atomic_json(V/'root-source-runtime-check-v1.json',report)
print(json.dumps({'accepted':True,'source_files':len(source['files']),'source_commit':source['commit'],'dispatched':snap['dispatched'],'gpu_hours':snap['gpu_hours_consumed'],'wall_seconds':report['wall_seconds']}))

