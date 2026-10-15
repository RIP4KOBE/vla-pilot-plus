"""Register accepted Boolean repair and the separate CPU continuation task."""
from pathlib import Path
import copy,datetime,importlib.util,json,os,sys,yaml
L=Path(__file__).resolve().parent;P=L.parent;W=P.parents[1]/'study_worktree';J=P/'terminal-feedback-binding-repair-v1'
sys.path[:0]=[str(W),str(W/'scripts')]
from scripts import qd_ed_final_runner as r,qd_ed_n23_worker as w,qd_ed_n30_r1_contract as c
spec=importlib.util.spec_from_file_location('arbor_state','/home/hynx/.codex/skills/arbor-agent-tools/scripts/arbor_state.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
run='rdt-qd-ed-final-20260921T093925Z';session=W/'.arbor/sessions'/run;coord=session/'.coordinator'
ref=c.ref;now=datetime.datetime.now(datetime.timezone.utc).isoformat()
review=w.read_ref(ref(J/'root-cpu-repair-review-v1.json'));release=w.read_ref(ref(L/'root-cpu-integration-release-v1.json'))
assert review['disposition']=='ACCEPT_CPU_REPAIR_ONLY' and release['accepted_repair_review']==ref(J/'root-cpu-repair-review-v1.json')
assert not release['gpu_release'] and release['cpu_seconds_limit']==1200
out=L/'registration-before-v1';out.mkdir(exist_ok=False)
with r.locked(W/'data/qd-ed-runner.lock',nonblocking=True),r.locked(W/'data/qd-ed-state.lock'),a.state_lock(W,run):
 state=r.read_state(W/'research-state.yaml');cp=r.read_json(coord/'checkpoint.json');tree=a.load_tree(W,run)
 c.require_state(state,vars(r))
 snap=r.budget_snapshot(r.read_events(W/'data/attempt-ledger.jsonl'),r.read_events(W/'data/gpu-healthcheck-ledger.jsonl'))
 assert snap['dispatched']==399 and snap['running']==snap['gpu_healthcheck_inflight']==0
 budget=copy.deepcopy(state['budget']);lexical=state['worktree']
 assert state['active_iteration'] is None and not state['current_owned_workers']
 assert state['current_cpu_task']['phase']=='N30_TERMINAL_FEEDBACK_CPU_DIAGNOSIS_REPAIR'
 for name,value in [('state',state),('checkpoint',cp),('tree',tree)]:r.durable_json(out/(name+'.json'),value)
 previous=copy.deepcopy(state['current_cpu_task']);previous.update(status='COMPLETED_ACCEPTED',review=ref(J/'root-cpu-repair-review-v1.json'),
  completed_source_commit=review['source_commit'],completed_at=now,diagnostic_and_tests_cpu_seconds=review['diagnostic_and_tests_cpu_seconds'],
  real_guard_clean=False,blocked_dependency_probes=6,source_adopted=False)
 state.setdefault('closed_cpu_tasks',{})['N30_TERMINAL_FEEDBACK_CPU_DIAGNOSIS_REPAIR']=previous
 task={'status':'RUNNING','phase':'N30_R2_CPU_CONTINUATION_INTEGRATION','node_id':'14.1','agent':'/root/n22_cpu_executor',
  'scope':release['scope'],'release':ref(L/'root-cpu-integration-release-v1.json'),
  'source_base':review['source_commit'],'cpu_seconds_limit':1200,'threads':2,'historical_tensor_reads_authorized':False,
  'gpu_authorized':False,'registered_at':now}
 next_action='Independently review N30 R2 CPU continuation delivery from accepted strict-Boolean audit repair. Preserve2originalcontrols/2invalidattempts/all4costs; any next GPU work requires separate final source adoption, exact plan/history/commands and current resource/login release. Same3/4Dev gate, caps578/100, combined6h, protected phases closed. Active Goal continues.'
 state['study']['status']='N30_R2_CPU_CONTINUATION_TARGET_NOT_MET'
 state.update(active_iteration=None,active_plan=None,active_controller=None,current_owned_workers=[],current_cpu_task=task,
  next_action=next_action,updated_at=now)
 state['prospective_iteration'].update(status='R2_CPU_PREPARATION',cohort_id='N30_TERMINAL_BOOLEAN_REPAIR_DEV_20261003',
  gpu_execution_authorized=False,repair_source_commit=review['source_commit'],repair_review=previous['review'],
  continuation_cpu_release=task['release'],continuation_scope=task['scope'],source_adopted=False)
 cp.update(status=state['study']['status'],phase='DISPATCH_CPU',active_node='14.1',active_node_id='14.1',
  active_iteration=None,active_plan=None,active_controller=None,active_workers=[],owned_gpu_workers=[],
  execution_tool_session=None,automatic_gpu_dispatch_authorized=False,automatic_gpu_dispatch_scope=None,
  in_flight_executor=task,in_flight_executors=[task],inflight_executor=task,inflight_executors=[task],executor_task=task,
  next_action=next_action,budget_snapshot=snap,n30_terminal_feedback_repair_review=previous['review'],
  n30_r2_cpu_release=task['release'],goal_achieved=False,target_achieved=False,target_met=False,updated_at=now,last_updated_utc=now)
 insight='Strict Pythonbool/0DCPUbool equivalence repaired only N30 auditor;463sourcefiles independently rehashed,456/457basefiles unchanged,21tests pass. One real2250bundle offline diagnostic reproduced old failure and verified14active/24prefix/192acks after repair;6dependency probes blocked and disclosed. Original GPU receipt remains invalid. New finite R2 integration only; no GPU released.'
 node=a.node(tree,'14.1');node.update(status='running',phase='R2_CPU_PREPARATION',scientific_outcome='Unknown',
  code_ref=review['base_commit'],repair_source_commit=review['source_commit'],repair_review=previous['review'],
  gpu_execution_authorized=False,cpu_task=task,insight=insight)
 tree['meta'].update(study_status=state['study']['status'],target_achieved=False,automatic_dispatch_authorized=False)
 assert state['budget']==budget and state['worktree']==lexical and Path(lexical).resolve()==W.resolve()
 temp=W/'research-state.yaml.n30-r2-cpu-tmp'
 with temp.open('x') as f:yaml.safe_dump(state,f,sort_keys=False,allow_unicode=True);f.flush();os.fsync(f.fileno())
 os.replace(temp,W/'research-state.yaml');r.durable_json(coord/'checkpoint.json',cp);a.save_tree(W,run,tree)
 note='\n\n## N30 strict Boolean repair accepted; R2 CPU integration — '+now+'\n\n'+insight+'\n\nAccepted source debda23 is frozen in its variant worktree; owningW staysb277until integrated-source review/adoption. Measured diagnostic+tests41.170220063CPU seconds, source packaging0.232985141 and rootmetadatareview0.141472155 separately recorded. No task-success evidence gained: C0/Q0 each0/1, N30 zero valid episodes. Plan prospectively retains two controls and both invalid costs; sole proposed new recovery links to r1failure, then9untouchedsuffix cells. Existing578attempt/100GPUh caps, localcombined6h, original3/4gate and protected reserves unchanged. Cumulative399dispatches/53.485552730447566GPUh. NewCPU task1200seconds/2threads, no historicaltensors/model/API/sim/GPU. AutonomousGoal active.\n\nRepairreview: '+previous['review']['path']+'\nContinuationscope: '+task['scope']['path']+'\n'
 for path in (session/'REPORT.md',W/'docs/03_evidence/qd_ed_final/iteration-ledger.md'):
  with path.open('a') as f:f.write(note)
 r.durable_json(L/'root-cpu-registration-v1.json',{'schema':'n30-r2-root-cpu-registration-v1','at':now,'accepted_cpu_repair':previous,
  'cpu_task':task,'budget_unchanged':True,'snapshot':snap,'goal_active':True,'gpu_release':False})
print(json.dumps({'status':state['study']['status'],'cpu_agent':task['agent'],'active_gpu_workers':0,'dispatched':snap['dispatched'],'gpu_hours':snap['gpu_hours_consumed']}))
