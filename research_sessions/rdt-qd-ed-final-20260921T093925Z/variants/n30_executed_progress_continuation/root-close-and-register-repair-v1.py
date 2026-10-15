"""Close old N30 execution and register the separate finite CPU continuation."""
from pathlib import Path
import copy,datetime,importlib.util,json,os,sys,yaml
P=Path(__file__).resolve().parent;W=P.parents[1]/'study_worktree';K=P/'repair-continuation-v1';H=P/'initial-observation-repair-v1'
sys.path[:0]=[str(W),str(W/'scripts')]
from scripts import qd_ed_final_runner as r,qd_ed_n23_worker as w,qd_ed_n30_contract as c
spec=importlib.util.spec_from_file_location('arbor_state','/home/hynx/.codex/skills/arbor-agent-tools/scripts/arbor_state.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
run='rdt-qd-ed-final-20260921T093925Z';session=W/'.arbor/sessions'/run;coord=session/'.coordinator'
ref=c.ref;now=datetime.datetime.now(datetime.timezone.utc).isoformat()
review=w.read_ref(ref(P/'root-terminal-review-v1.json'))
assert review['decision']=='INVALID_OR_INTERRUPTED' and review['dispatched']==3 and review['audited_cells']==2
assert review['invalid_attempts'][0]['root_classification']=='ENGINEERING_INITIAL_OBSERVATION_UNBOUNDLOCAL'
assert w.read_ref(ref(H/'root-cpu-repair-review-v1.json'))['disposition']=='ACCEPT_CPU_REPAIR_ONLY'
assert w.read_ref(ref(K/'root-cpu-integration-release-v1.json'))['gpu_release'] is False
out=K/'registration-before-v1';out.mkdir(exist_ok=False)
with r.locked(W/'data/qd-ed-runner.lock',nonblocking=True),r.locked(W/'data/qd-ed-state.lock'),a.state_lock(W,run):
 state=r.read_state(W/'research-state.yaml');cp=r.read_json(coord/'checkpoint.json');tree=a.load_tree(W,run)
 c.require_budget_state(state,vars(r))
 snap=r.budget_snapshot(r.read_events(W/'data/attempt-ledger.jsonl'),r.read_events(W/'data/gpu-healthcheck-ledger.jsonl'))
 assert snap['dispatched']==398 and snap['running']==snap['gpu_healthcheck_inflight']==0
 assert abs(snap['gpu_hours_consumed']-53.38686451724561)<1e-8
 budget=copy.deepcopy(state['budget']);lexical=state['worktree']
 assert state['active_iteration']==c.COHORT and state['current_iteration']['id']=='N30'
 for name,value in [('state',state),('checkpoint',cp),('tree',tree)]:r.durable_json(out/(name+'.json'),value)
 summary={'candidate_id':'N30','cohort_id':c.COHORT,'status':'CLOSED_INVALID_ENGINEERING_INITIAL_OBSERVATION',
  'scientific_outcome':'Unknown','source_commit':review['source_commit'],'counts':review['counts'],
  'result':review['result'],'root_review':ref(P/'root-terminal-review-v1.json'),'closed_at':now,
  'target_achieved':False,'execution_authorized':False,'validation_authorized':False,'formal_authorized':False}
 task={'status':'RUNNING','phase':'N30_REPAIR_CONTINUATION_CPU_INTEGRATION','node_id':'14.1','agent':'/root/n22_cpu_executor',
  'scope':ref(K/'cpu-integration-scope-v1.md'),'release':ref(K/'root-cpu-integration-release-v1.json'),
  'source_base':'7c0d80d734fa8300173e56d9a8de03415bc55fe2','cpu_seconds_limit':1200,'threads':2,'gpu_authorized':False,'registered_at':now}
 next_action='Review separate N30 engineering continuation CPU delivery; retain original2validcontrols/1invalidcost, allow only scoped once-linked recovery plus9unrun cells after new source/plan release. Original3/4gate and578attempt/100GPUh caps unchanged; protected phases closed; Goal active.'
 state.setdefault('closed_executions',{})[c.COHORT]=summary
 state['current_iteration'].update(summary,accepted_cells_observed=2,repair_review=ref(H/'root-cpu-repair-review-v1.json'))
 state['study']['status']='N30_CPU_REPAIR_CONTINUATION_TARGET_NOT_MET'
 state.update(active_iteration=None,active_plan=None,active_controller=None,current_owned_workers=[],current_cpu_task=task,
  last_completed_iteration=c.COHORT,last_completed_plan=review['plan'],next_action=next_action,updated_at=now)
 state['prospective_iteration'].update(status='CPU_REPAIR_CONTINUATION',gpu_execution_authorized=False,
  repair_source_commit=task['source_base'],repair_review=ref(H/'root-cpu-repair-review-v1.json'),continuation_cpu_release=task['release'])
 cp['n30_closed_controller']=cp.get('active_controller')
 cp.update(status=state['study']['status'],phase='DISPATCH_CPU',active_node='14.1',active_node_id='14.1',
  active_iteration=None,active_plan=None,active_controller=None,active_workers=[],owned_gpu_workers=[],
  execution_tool_session=None,automatic_gpu_dispatch_authorized=False,automatic_gpu_dispatch_scope=None,
  in_flight_executor=task,in_flight_executors=[task],inflight_executor=task,inflight_executors=[task],executor_task=task,
  next_action=next_action,budget_snapshot=snap,n30_terminal_review=summary['root_review'],n30_result=summary['result'],
  n30_initial_observation_repair_review=ref(H/'root-cpu-repair-review-v1.json'),n30_repair_continuation_cpu_release=task['release'],
  goal_achieved=False,target_achieved=False,target_met=False,updated_at=now,last_updated_utc=now)
 insight='N30 initial Dev interrupted by engineering UnboundLocalError before first policy decision. C0/Q0 each0/1 valid; N30 has0valid episodes, efficacy Unknown. Original3attempts and0.302817590547234GPUh retained. Three-line raw cache initialization passed7complete-Main CPU regressions; separate scoped continuation in CPU preparation, original gate unchanged.'
 node=a.node(tree,'14.1');node.update(status='running',phase='ENGINEERING_REPAIR',scientific_outcome='Unknown',
  review=summary['root_review'],result=summary['result'],code_ref=review['source_commit'],gpu_execution_authorized=False,
  repair_source_commit=task['source_base'],repair_review=ref(H/'root-cpu-repair-review-v1.json'),cpu_task=task,insight=insight)
 tree['meta'].update(study_status=state['study']['status'],target_achieved=False,automatic_dispatch_authorized=False)
 assert state['budget']==budget and state['worktree']==lexical and Path(lexical).resolve()==W.resolve()
 temp=W/'research-state.yaml.n30-close-tmp'
 with temp.open('x') as f:yaml.safe_dump(state,f,sort_keys=False,allow_unicode=True);f.flush();os.fsync(f.fileno())
 os.replace(temp,W/'research-state.yaml');r.durable_json(coord/'checkpoint.json',cp);a.save_tree(W,run,tree)
 text='\n\n## N30 initial-observation engineering recovery — '+now+'\n\n'+insight+'\n\nBoth old valid controls and their source-bound receipts were independently checked before any source adoption. Original monitor exit1 and all original process identities closed. Stage41logical calls through current managed Codex login,0failed calls; input442178/output2671tokens; internal HTTP unknown. Cumulative398dispatches/53.38686451724561GPUh. Caps578/100 and protected reserves unchanged. All original artifacts and ledger entries retained. CPU-only continuation work starts at accepted7c0d80repair; at most1linked recovery plus9original unrun cells, combined6GPUh includes original costs. No GPU release yet, validation/formal closed, target unmet, active autonomous Goal continues.\n\nReview: '+summary['root_review']['path']+'\nScope: '+task['scope']['path']+'\n'
 for path in (session/'REPORT.md',W/'docs/03_evidence/qd_ed_final/iteration-ledger.md'):
  with path.open('a') as f:f.write(text)
 r.durable_json(K/'root-cpu-registration-v1.json',{'schema':'n30-r1-root-cpu-registration-v1','at':now,'closed_original':summary,'cpu_task':task,'budget_unchanged':True,'snapshot':snap,'goal_active':True,'gpu_release':False})
print(json.dumps({'status':state['study']['status'],'cpu_agent':task['agent'],'active_gpu_workers':0,'dispatched':snap['dispatched'],'gpu_hours':snap['gpu_hours_consumed']}))

