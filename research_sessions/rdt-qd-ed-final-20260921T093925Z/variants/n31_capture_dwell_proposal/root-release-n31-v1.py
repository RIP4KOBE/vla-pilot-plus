from pathlib import Path
import json,os,sys,datetime,subprocess
P=Path(__file__).resolve().parent;W=P.parents[1]/'study_worktree';sys.path[:0]=[str(W),str(W/'scripts')];os.environ['CUDA_VISIBLE_DEVICES']=''
from scripts import qd_ed_final_runner as r,qd_ed_n23_worker as w,qd_ed_n31_contract as c,qd_ed_available_gpu_queue as q
plan_path=P/'plan.frozen.v1.gpu7.json';plan=r.read_json(plan_path)
assert plan['frozen'] is True and plan['source_commit']=='7428ce8a51f76c5f641537be9a7614631d82b0d9'
runtime=w.read_ref(c.runtime_ref());device=q.inventory()[7];q.reservation_admission(device);admission=r.gpu_admission(physical_gpu=7,expected_uuid=c.GPU7_UUID)
mapping=q.current_metadata(7,root=W);assert q.same_mapping(mapping,runtime['gpu_mapping'])
probe=q.reusable_probe(runtime,mapping,r.read_events(W/'data/gpu-healthcheck-ledger.jsonl'),root=W);assert probe is not None
provider=runtime['frozen_stage_provider'];assert provider['backend']=='codex_cli' and provider['auth_mode']=='chatgpt'
assert w.sha(provider['cli_path'])==provider['cli_sha256']
login=subprocess.run([provider['cli_path'],'login','status'],capture_output=True,text=True,timeout=20)
assert login.returncode==0 and 'Logged in using ChatGPT' in login.stdout+login.stderr
with r.locked(W/'data/qd-ed-runner.lock',nonblocking=True),r.locked(W/'data/qd-ed-state.lock'):
 state=r.read_state(W/'research-state.yaml');events=r.read_events(W/'data/attempt-ledger.jsonl')
 c.full_capacity(state,events,r.read_events(W/'data/gpu-healthcheck-ledger.jsonl'),vars(r))
 assert not any(e.get('identity',{}).get('iteration')==c.COHORT for e in events)
 assert state['active_controller'] is None and state['current_owned_workers']==[]
 fresh={'schema':'n31-root-execution-admission-v1','recorded_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'plan':c.ref(plan_path),'source_commit':plan['source_commit'],'source_review':c.ref(c.FINAL_REVIEW),'authority':c.ref(c.AUTHORITY),'budget_authority':c.ref(c.BUDGET_AUTHORITY),'gpu_admission':admission,'gpu_mapping':{k:mapping.get(k) for k in ('physical_gpu','uuid','pci_bus_id','egl_device_index','driver_version','boot_id')},'native_probe_reused':runtime['cuda_egl_probe'],'new_cuda_probe':False,'login':'Logged in using ChatGPT','provider_backend':'codex_cli','provider_model':provider['model'],'provider_auth_mode':'chatgpt','artifact_free_bytes':os.statvfs(P/'artifacts').f_bavail*os.statvfs(P/'artifacts').f_frsize,'single_worker':True,'no_peer_state_mutation':True}
 w.atomic_json(P/'root-execution-admission-v1.json',fresh)
 release={'schema':'n31-dev-execution-release-v1','plan':c.ref(plan_path),'source_commit':plan['source_commit'],'cohort_id':c.COHORT,'episode_keys':[x['episode_key'] for x in plan['episodes']],'authority':plan['n31_cohort']['authority'],'physical_gpu':7,'limits':c.LIMITS,'validation_authorized':False,'formal_authorized':False}
 w.atomic_json(P/'execution-release-v1.json',release)
 print(json.dumps({'release':c.ref(P/'execution-release-v1.json'),'admission':admission,'mapping_matches':True,'login':'ChatGPT','source_commit':plan['source_commit']}))

