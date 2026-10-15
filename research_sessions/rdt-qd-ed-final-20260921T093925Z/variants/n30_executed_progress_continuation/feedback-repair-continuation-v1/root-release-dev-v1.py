"""Root final release for one bounded N30 engineering continuation."""
from pathlib import Path
import datetime,json,os,sys,yaml,subprocess,shutil
K=Path(__file__).resolve().parent;P=K.parent;ROOT=P.parents[1]/'study_worktree'
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from scripts import qd_ed_final_runner as r,qd_ed_n23_worker as w,qd_ed_n30_r2_contract as c,qd_ed_n30_r2_supervise as sup
now=datetime.datetime.now(datetime.timezone.utc).isoformat();h=c.history()
plan_path=c.PLAN;plan,manifest,runtime=r.validate_plan(plan_path,root=ROOT)
source=r.read_json(K/'source-manifest-execution-v1.json')
assert w.read_ref(c.ref(K/'adoption-v1/root-plan-adoption-record-v1.json'))['plan']==c.ref(plan_path)
assert plan['source_commit']==source['commit'] and plan['code_files']==source['files'] and plan['frozen']
assert plan['episodes']==c.expected_rows(h) and len(plan['episodes'])==10
assert plan['phase_authorization']=={'dev':True,'validation':False,'formal':False}
review=w.read_ref(c.ref(K/'real-command-composition-review-v1.json'))
assert review['accepted'] and [x['episode_key'] for x in review['commands']]==[x['episode_key'] for x in plan['episodes']]
r.stage_overrides(runtime)
login=subprocess.run([runtime['frozen_stage_provider']['cli_path'],'login','status'],capture_output=True,text=True,timeout=30)
assert login.returncode==0 and (login.stdout+login.stderr).strip()=='Logged in using ChatGPT'
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
previous=P/'execution/controller-process-v1.json';assert boot==w.read_ref(c.ref(previous))['boot_id']
gpurow=subprocess.check_output(['nvidia-smi','--id=7','--query-gpu=uuid,driver_version,pci.bus_id','--format=csv,noheader,nounits'],text=True,timeout=30).strip()
uuid,driver,pci=[x.strip() for x in gpurow.split(',')]
assert uuid==c.GPU7_UUID and driver==runtime['gpu_mapping']['driver_version'] and pci==runtime['gpu_mapping']['pci_bus_id']
free=shutil.disk_usage(c.ARTIFACT_DIR).free;assert free>=20*1024**3
with r.locked(ROOT/'data/qd-ed-runner.lock',nonblocking=True),r.locked(ROOT/'data/qd-ed-state.lock'):
 state=r.read_state(ROOT/'research-state.yaml');events=r.read_events(ROOT/'data/attempt-ledger.jsonl');resources=r.read_events(ROOT/'data/gpu-healthcheck-ledger.jsonl')
 c.full_capacity(state,events,resources,vars(r))
 assert not any(e.get('identity',{}).get('iteration')==c.COHORT for e in events)
 assert not state.get('current_owned_workers') and not state.get('active_controller')
 sup.device_check();admission=r.gpu_admission(physical_gpu=7,expected_uuid=c.GPU7_UUID)
 assert not (K/'execution/supervisor-status-v1.json').exists() and not (K/'result-v1.json').exists()
 release={'schema':'n30-r2-execution-release-v1','plan':c.ref(plan_path),'source_commit':plan['source_commit'],'cohort_id':c.COHORT,
  'episode_keys':[x['episode_key'] for x in plan['episodes']],'authority':plan['n30_r2_cohort']['authority'],'physical_gpu':7,
  'limits':c.LIMITS,'validation_authorized':False,'formal_authorized':False}
 release_path=K/'execution-release-v1.json';w.atomic_json(release_path,release);sup.release_check(release_path,plan_path,plan)
 prelaunch={'schema':'n30-r2-root-final-prelaunch-review-v1','at':now,'decision':'RELEASE_ONE_FINITE_ENGINEERING_CONTINUATION',
  'plan':c.ref(plan_path),'release':c.ref(release_path),'source_commit':plan['source_commit'],'source_files':len(source['files']),
  'command_review':c.ref(K/'real-command-composition-review-v1.json'),'cpu_review':c.ref(K/'root-cpu-integration-review-v1.json'),
  'original_terminal_review':c.ref(P/'root-terminal-review-v1.json'),'gpu_admission':admission,'gpu_uuid':uuid,
  'driver_version':driver,'pci_bus_id':pci,'boot_id':boot,'same_boot_as_original_controller':c.ref(previous),'artifact_free_bytes':free,
  'login_status':'Logged in using ChatGPT','poe_allowed':False,'fallback_allowed':False,
  'budget_snapshot':r.budget_snapshot(events,resources),'new_dispatches_released':10,'inherited_valid_controls':2,
  'named_engineering_recoveries':1,'additional_retries':0,'total_gpu_hour_cap':100.,
  'combined_original_plus_repair_gpu_hour_cap':6.,'prior_original_and_r1_gpu_seconds_included':h['old_seconds'],
  'budget_changed':False,'validation_authorized':False,'formal_authorized':False,'target_status':'TARGET_NOT_MET',
  'gpu_dispatched_by_this_script':False}
 w.atomic_json(K/'root-final-prelaunch-review-v1.json',prelaunch)
 state['current_iteration'].update(status='N30_R2_DEV_RELEASED',execution_authorized=True,
  execution_release=c.ref(release_path),prelaunch_review=c.ref(K/'root-final-prelaunch-review-v1.json'))
 state['study']['status']='N30_R2_DEV_RELEASED_TARGET_NOT_MET'
 state['prospective_iteration'].update(status='R2_DEV_RELEASED',gpu_execution_authorized=True)
 state['next_action']='Launch exact10-cell N30 engineering continuation on GPU7/currentCodex login. Stop this finite cohort on invalid evidence, complete-triple futility or insufficient full-attempt budget; then independently review and continue research until original target passes.'
 temp=ROOT/'research-state.yaml.n30-r2-release-tmp'
 with temp.open('x') as f:yaml.safe_dump(state,f,sort_keys=False,allow_unicode=True);f.flush();os.fsync(f.fileno())
 os.replace(temp,ROOT/'research-state.yaml')
 cp_path=ROOT/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';cp=r.read_json(cp_path)
 cp.update(status='N30_R2_DEV_RELEASED',phase='DISPATCH',automatic_gpu_dispatch_authorized=True,automatic_gpu_dispatch_scope=c.COHORT,
  n30_r2_execution_release=c.ref(release_path),n30_r2_prelaunch_review=c.ref(K/'root-final-prelaunch-review-v1.json'),next_action=state['next_action'])
 r.durable_json(cp_path,cp)
print(json.dumps({'release':c.ref(K/'execution-release-v1.json'),'gpu':7,'new_cells':10,'inherited_controls':2,'named_recoveries':1,'gpu_dispatched':False}))

