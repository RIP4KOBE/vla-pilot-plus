import json,sys,os,yaml
from pathlib import Path
from datetime import datetime,timezone
A=Path(__file__).resolve().parent;N26=A.parent;W=N26.parent.parent/'study_worktree'
sys.path[:0]=[str(W/'scripts'),str(W)]
from scripts import qd_ed_final_runner as r,qd_ed_n23_worker as w,qd_ed_n26_contract as c
record=w.read_ref(c.ref(N26/'execution/controller-process-v1.json'))
proc=record['process'];fields=Path('/proc/'+str(proc['pid'])+'/stat').read_text().rsplit(')',1)[1].split()
assert fields[19]==proc['proc_start_ticks'] and fields[0]!='Z'
assert proc['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip()
assert record['plan']==c.ref(N26/'plan.frozen.v1.gpu7.json') and record['release']==c.ref(N26/'execution-release-v1.json')
admission={'schema':'n26-root-actual-controller-admission-v1','controller_record':c.ref(N26/'execution/controller-process-v1.json'),
 'process':proc,'exec_session':11622,'plan':record['plan'],'release':record['release'],
 'entrypoint':record['entrypoint'],'wrapper':record['wrapper'],'physical_gpu':7,
 'source_commit':record['source_commit'],'started':True,'first_episode_dispatch_observed':False,
 'provider_policy':'Current managed Codex CLI login only; no Poe/account/provider fallback.',
 'recorded_at':datetime.now(timezone.utc).isoformat()}
w.atomic_json(N26/'execution/root-controller-admission-v1.json',admission)
with r.locked(W/'data/qd-ed-state.lock'):
 state=r.read_state(W/'research-state.yaml')
 state['current_iteration'].update(status='DEV_CONTROLLER_ADMISSION',active_controller=admission,execution_authorized=True)
 tmp=W/'research-state.yaml.root-n26-tmp'
 with tmp.open('w') as f:yaml.safe_dump(state,f,sort_keys=False);f.flush();os.fsync(f.fileno())
 os.replace(tmp,W/'research-state.yaml')
p=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json'
cp=json.loads(p.read_text());cp.update(status='N26_DEV_CONTROLLER_ADMISSION',phase='MONITOR',active_controller=admission,
 n26_status='DEV_RELEASED_CONTROLLER_LIVE',n26_plan=record['plan'],n26_release=record['release'],
 n26_actual_proof_review=c.ref(A/'root-actual-proof-review-v1.json'),
 n26_dev_authority=c.ref(c.AUTHORITY),n26_command_release_review=c.ref(A/'root-command-release-review-v1.json'),
 n26_validation_static_design_review=c.ref(N26/'conditional-validation-preparation-v1/root-design-review-v1.json'),
 n26_terminal_reader_protocol=c.ref(N26/'terminal-review-preparation-v1/root-implementation-protocol-v1.md'),
 in_flight_executor='/root/n22_cpu_executor',target_met=False,target_achieved=False,
 updated_at=datetime.now(timezone.utc).isoformat())
cp['automatic_gpu_dispatch_scope']='Only frozen N26 Dev40/max42 cohort on GPU7; validation/formal closed.'
p.write_text(json.dumps(cp,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'admission':c.ref(N26/'execution/root-controller-admission-v1.json'),'controller':proc,'session':11622}))

