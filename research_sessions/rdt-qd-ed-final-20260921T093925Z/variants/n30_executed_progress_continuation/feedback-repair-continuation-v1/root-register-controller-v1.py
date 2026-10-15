"""Register/refresh the already launched N30 repair controller; never dispatch."""
from pathlib import Path
import datetime,importlib.util,json,os,sys,yaml
K=Path(__file__).resolve().parent;P=K.parent;W=P.parents[1]/'study_worktree'
sys.path[:0]=[str(W),str(W/'scripts')]
from scripts import qd_ed_final_runner as r,qd_ed_n23_worker as w,qd_ed_n30_r2_contract as c
now=datetime.datetime.now(datetime.timezone.utc).isoformat();run='rdt-qd-ed-final-20260921T093925Z'
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
def live(p):
 try:
  fields=Path(f"/proc/{p['pid']}/stat").read_text().rsplit(')',1)[1].split()
  return fields[0]!='Z' and fields[19]==str(p['proc_start_ticks']) and p['boot_id']==boot
 except FileNotFoundError:return False
controller=w.read_ref(c.ref(K/'execution/controller-process-v1.json'))
monitor=w.read_ref(c.ref(K/'execution/monitor-process-v1.json'))
assert live(controller) and live(monitor),'Controller/monitor is terminal; use terminal review, do not restart'
assert controller['plan']==c.ref(c.PLAN) and controller['release']==c.ref(K/'execution-release-v1.json')
plan=w.read_ref(controller['plan'])
assert controller['maximum_live_gpu_workers']==1 and plan['source_commit']==r.read_json(K/'source-manifest-execution-v1.json')['commit']
refresh=sys.argv[1:]==['--refresh'];assert sys.argv[1:] in ([],['--refresh'])
record_path=K/'root-controller-registration-v1.json'
if refresh:
 old=r.read_json(record_path);assert old['controller']==c.ref(K/'execution/controller-process-v1.json')
else:assert not record_path.exists()
spec=importlib.util.spec_from_file_location('arbor_state','/home/hynx/.codex/skills/arbor-agent-tools/scripts/arbor_state.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
with r.locked(W/'data/qd-ed-state.lock'),a.state_lock(W,run):
 events=r.read_events(W/'data/attempt-ledger.jsonl');resources=r.read_events(W/'data/gpu-healthcheck-ledger.jsonl')
 local=[e for e in events if e.get('identity',{}).get('iteration')==c.COHORT]
 owned=[];unsettled=[]
 for aid,g in r.event_groups(local).items():
  if g[-1]['event']!='dispatched':continue
  final=g[-1];out=Path(final['output_dir']);procpath=out/'process.json'
  if not procpath.exists():unsettled.append({'attempt_id':aid,'reason':'awaiting_worker_process_record'});continue
  proc=r.read_json(procpath)
  if not live(proc):unsettled.append({'attempt_id':aid,'reason':'exited_worker_pending_terminal_journal'});continue
  owned.append({'attempt_id':aid,'episode_key':final['episode_key'],'profile':final['identity']['profile'],
   'pid':proc['pid'],'proc_start_ticks':proc['proc_start_ticks'],'boot_id':proc['boot_id'],
   'physical_gpu':7,'process':c.ref(procpath),'output_dir':str(out),'observed_at':now})
 assert len(owned)<=1
 state=r.read_state(W/'research-state.yaml')
 assert state['current_iteration']['cohort_id']==c.COHORT and state['current_iteration']['execution_authorized']
 if refresh:assert state['active_iteration']==c.COHORT
 controller_record={**controller,'record':c.ref(K/'execution/controller-process-v1.json'),
  'monitor':c.ref(K/'execution/monitor-process-v1.json'),'verified_at':now}
 statuspath=K/'execution/supervisor-status-v1.json';status=r.read_json(statuspath) if statuspath.exists() else {}
 completed=status.get('completed_keys',[])
 state['study']['status']='N30_R2_DEV_RUNNING_GPU7_TARGET_NOT_MET'
 state.update(active_iteration=c.COHORT,active_plan=c.ref(c.PLAN),active_controller=controller_record,
  current_owned_workers=owned,updated_at=now)
 state['current_iteration'].update(status='N30_R2_DEV_RUNNING_GPU7',controller=controller_record['record'],
  monitor=controller_record['monitor'],accepted_cells_observed_total=len(completed),
  accepted_new_cells_observed=max(0,len(completed)-2),observed_successes=status.get('successes'),
  last_observed_at=now,unsettled_exited_handles=unsettled)
 state['next_action']='Monitor this exact existing GPU7 N30 repair controller; no duplicate launch. Independently review terminal/new receipts and all costs, then continue outer-loop research until original goal passes. CurrentCodex login only, unchanged budget/protected gates.'
 temp=W/'research-state.yaml.n30-r2-live-tmp'
 with temp.open('x') as f:yaml.safe_dump(state,f,sort_keys=False,allow_unicode=True);f.flush();os.fsync(f.fileno())
 os.replace(temp,W/'research-state.yaml')
 coord=W/'.arbor/sessions'/run/'.coordinator';cp=r.read_json(coord/'checkpoint.json')
 snap=r.budget_snapshot(events,resources)
 cpu_task=state.get('current_cpu_task')
 if not cpu_task or cpu_task.get('status') not in {'DISPATCHED','RUNNING'}:cpu_task=None
 cp.update(status=state['study']['status'],phase='EXECUTE',active_iteration=c.COHORT,active_plan=c.ref(c.PLAN),
  active_controller=controller_record,active_workers=owned,owned_gpu_workers=owned,worker_observation_at=now,
  active_node='14.1',active_node_id='14.1',next_action=state['next_action'],budget_snapshot=snap,
  in_flight_executor=cpu_task,in_flight_executors=[cpu_task] if cpu_task else [],
  inflight_executor=cpu_task,inflight_executors=[cpu_task] if cpu_task else [],executor_task=cpu_task,
  automatic_gpu_dispatch_authorized=True,automatic_gpu_dispatch_scope=c.COHORT,unsettled_exited_handles=unsettled,updated_at=now)
 r.durable_json(coord/'checkpoint.json',cp)
 tree=a.load_tree(W,run);a.node(tree,'14.1').update(status='running',phase='R2_DEV_EXECUTION',
  code_ref=plan['source_commit'],gpu_execution_authorized=True,continuation_plan=c.ref(c.PLAN))
 tree['meta'].update(study_status=state['study']['status'],automatic_dispatch_authorized=True,target_achieved=False)
 a.save_tree(W,run,tree)
 if not refresh:w.atomic_json(record_path,{'schema':'n30-r2-root-controller-registration-v1','at':now,
  'controller':c.ref(K/'execution/controller-process-v1.json'),'monitor':c.ref(K/'execution/monitor-process-v1.json'),
  'source_commit':plan['source_commit'],'plan':c.ref(c.PLAN),'release':c.ref(K/'execution-release-v1.json'),
  'initial_owned_workers':owned,'initial_unsettled_handles':unsettled,'budget_snapshot':snap,'target_achieved':False})
print(json.dumps({'controller_live':True,'controller_pid':controller['pid'],'owned_workers':owned,
 'inherited_plus_new_accepted':len(completed),'dispatched':snap['dispatched'],'refresh':refresh}))

