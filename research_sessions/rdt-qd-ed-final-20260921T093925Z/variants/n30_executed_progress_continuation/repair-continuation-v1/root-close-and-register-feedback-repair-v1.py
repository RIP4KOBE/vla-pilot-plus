"""Close r1's invalid audited episode and register a finite CPU-only repair."""
from pathlib import Path
import copy,datetime,importlib.util,json,os,sys,yaml
K=Path(__file__).resolve().parent;P=K.parent;W=P.parents[1]/'study_worktree';J=P/'terminal-feedback-binding-repair-v1'
sys.path[:0]=[str(W),str(W/'scripts')]
from scripts import qd_ed_final_runner as r,qd_ed_n23_worker as w,qd_ed_n30_r1_contract as c
spec=importlib.util.spec_from_file_location('arbor_state','/home/hynx/.codex/skills/arbor-agent-tools/scripts/arbor_state.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
run='rdt-qd-ed-final-20260921T093925Z';session=W/'.arbor/sessions'/run;coord=session/'.coordinator'
ref=c.ref;now=datetime.datetime.now(datetime.timezone.utc).isoformat()
review=w.read_ref(ref(K/'root-terminal-review-v1.json'))
assert review['decision']=='INVALID_OR_INTERRUPTED' and review['new_dispatched']==1 and review['audited_cells']==2
release=w.read_ref(ref(J/'root-cpu-repair-release-v2.json'));assert release['gpu_release'] is False and release['cpu_seconds_limit']==900
out=J/'registration-before-v1';out.mkdir(exist_ok=False)
with r.locked(W/'data/qd-ed-runner.lock',nonblocking=True),r.locked(W/'data/qd-ed-state.lock'),a.state_lock(W,run):
 state=r.read_state(W/'research-state.yaml');cp=r.read_json(coord/'checkpoint.json');tree=a.load_tree(W,run)
 c.require_state(state,vars(r))
 snap=r.budget_snapshot(r.read_events(W/'data/attempt-ledger.jsonl'),r.read_events(W/'data/gpu-healthcheck-ledger.jsonl'))
 assert snap['dispatched']==399 and snap['running']==snap['gpu_healthcheck_inflight']==0
 assert snap==review['budget_snapshot']
 budget=copy.deepcopy(state['budget']);lexical=state['worktree']
 assert state['active_iteration']==c.COHORT and state['current_iteration']['id']=='N30'
 for name,value in [('state',state),('checkpoint',cp),('tree',tree)]:r.durable_json(out/(name+'.json'),value)
 summary={'candidate_id':'N30','cohort_id':c.COHORT,'status':'CLOSED_INVALID_NATIVE_TERMINAL_FEEDBACK_BINDING',
  'scientific_outcome':'Unknown','source_commit':review['source_commit'],'counts':review['counts'],
  'result':review['result'],'root_review':ref(K/'root-terminal-review-v1.json'),'closed_at':now,
  'target_achieved':False,'execution_authorized':False,'validation_authorized':False,'formal_authorized':False}
 task={'status':'RUNNING','phase':'N30_TERMINAL_FEEDBACK_CPU_DIAGNOSIS_REPAIR','node_id':'14.1','agent':'/root/n22_cpu_executor',
  'scope':release['scope'],'release':ref(J/'root-cpu-repair-release-v2.json'),
  'source_base':review['source_commit'],'cpu_seconds_limit':900,'threads':2,'gpu_authorized':False,'registered_at':now}
 next_action='Independently review the bounded N30 terminal-feedback CPU diagnosis/repair. Preserve original and r1 invalid attempts, no existing-controller resume or GPU retry; any later execution requires separate frozen source/plan/release. Continue active Goal toward unchanged original targets, current Codex only, caps578/100 unchanged.'
 state.setdefault('closed_executions',{})[c.COHORT]=summary
 state['current_iteration'].update(summary,accepted_cells_observed=2,accepted_new_cells_observed=0)
 state['study']['status']='N30_NATIVE_FEEDBACK_CPU_REPAIR_TARGET_NOT_MET'
 state.update(active_iteration=None,active_plan=None,active_controller=None,current_owned_workers=[],current_cpu_task=task,
  last_completed_iteration=c.COHORT,last_completed_plan=review['plan'],next_action=next_action,updated_at=now)
 state['prospective_iteration'].update(status='CPU_NATIVE_FEEDBACK_REPAIR',gpu_execution_authorized=False,
  feedback_repair_scope=task['scope'],feedback_repair_release=task['release'])
 cp['n30_r1_closed_controller']=cp.get('active_controller')
 cp.update(status=state['study']['status'],phase='DISPATCH_CPU',active_node='14.1',active_node_id='14.1',
  active_iteration=None,active_plan=None,active_controller=None,active_workers=[],owned_gpu_workers=[],
  execution_tool_session=None,automatic_gpu_dispatch_authorized=False,automatic_gpu_dispatch_scope=None,
  in_flight_executor=task,in_flight_executors=[task],inflight_executor=task,inflight_executors=[task],executor_task=task,
  next_action=next_action,budget_snapshot=snap,n30_r1_terminal_review=summary['root_review'],n30_r1_result=summary['result'],
  n30_feedback_cpu_release=task['release'],goal_achieved=False,target_achieved=False,target_met=False,updated_at=now,last_updated_utc=now)
 insight='N30 r1 completed720steps but same-worker native audit rejected terminal-feedback binding. New1recovery charged355.277567527seconds, original+new4attempts0.401505803749GPUh retained. C0/Q0 each0/1 valid; N30 zero valid episodes, efficacy Unknown. Suspected scalar boolean representation mismatch needs bounded CPU proof; no automatic second retry.'
 node=a.node(tree,'14.1');node.update(status='running',phase='NATIVE_FEEDBACK_REPAIR',scientific_outcome='Unknown',
  review=summary['root_review'],result=summary['result'],code_ref=review['source_commit'],gpu_execution_authorized=False,
  cpu_task=task,insight=insight)
 tree['meta'].update(study_status=state['study']['status'],target_achieved=False,automatic_dispatch_authorized=False)
 assert state['budget']==budget and state['worktree']==lexical and Path(lexical).resolve()==W.resolve()
 temp=W/'research-state.yaml.n30-feedback-close-tmp'
 with temp.open('x') as f:yaml.safe_dump(state,f,sort_keys=False,allow_unicode=True);f.flush();os.fsync(f.fileno())
 os.replace(temp,W/'research-state.yaml');r.durable_json(coord/'checkpoint.json',cp);a.save_tree(W,run,tree)
 note='\n\n## N30 r1 terminal audit failure and CPU repair — '+now+'\n\n'+insight+'\n\nSource b277/457files independently rehashed; controller/monitor/worker original process identities all exited. This execution completed15currentCodex logical Stage calls with0failures, input161798/output899tokens. Online24guided/14active counts are explicitly unverified. Original receipts and all history remain untouched; no candidate outcome accepted. Cumulative399dispatches/'+str(snap['gpu_hours_consumed'])+'GPUh, caps578/100 and protected reserves unchanged. Dedicated CPU diagnostic permits this one existing episode, guarded900CPU seconds/2threads, noGPU/API/model/simulator; source changes conditional on proven boolean representation issue. Autonomous Goal remains active; protected sets closed.\n\nReview: '+summary['root_review']['path']+'\nScope: '+task['scope']['path']+'\n'
 for path in (session/'REPORT.md',W/'docs/03_evidence/qd_ed_final/iteration-ledger.md'):
  with path.open('a') as f:f.write(note)
 r.durable_json(J/'root-cpu-registration-v1.json',{'schema':'n30-feedback-root-cpu-registration-v1','at':now,
  'closed_execution':summary,'cpu_task':task,'budget_unchanged':True,'snapshot':snap,'goal_active':True,'gpu_release':False})
print(json.dumps({'status':state['study']['status'],'cpu_agent':task['agent'],'active_gpu_workers':0,'dispatched':snap['dispatched'],'gpu_hours':snap['gpu_hours_consumed']}))
