"""Close only a root-reviewed terminal N30 r2 execution. Does not release next work."""
from pathlib import Path
import copy,datetime,importlib.util,json,os,sys,yaml
L=Path(__file__).resolve().parent;W=L.parent.parents[1]/'study_worktree'
sys.path[:0]=[str(W),str(W/'scripts')]
from scripts import qd_ed_final_runner as r,qd_ed_n23_worker as w,qd_ed_n30_r2_contract as c
spec=importlib.util.spec_from_file_location('arbor_state','/home/hynx/.codex/skills/arbor-agent-tools/scripts/arbor_state.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
run='rdt-qd-ed-final-20260921T093925Z';session=W/'.arbor/sessions'/run;coord=session/'.coordinator'
ref=c.ref;review=w.read_ref(ref(L/'root-terminal-review-v1.json'))
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
def live(p):
 try:
  f=Path(f"/proc/{p['pid']}/stat").read_text().rsplit(')',1)[1].split()
  return f[0]!='Z' and f[19]==str(p['proc_start_ticks']) and p['boot_id']==boot
 except FileNotFoundError:return False
assert all(review[k] is True for k in ('controller_original_process_exited','monitor_original_process_exited','all_new_workers_original_process_exited'))
for name in ('controller-process-v1.json','monitor-process-v1.json'):assert not live(r.read_json(L/'execution'/name))
for attempt in review['new_attempts']:
 if attempt['process']:assert not live(w.read_ref(attempt['process']))
decision=review['decision'];promoted=decision=='ELIGIBLE_FOR_SEPARATELY_FROZEN_VALIDATION'
rejected=decision in {'REJECT','REJECT_NUMERIC_DEV_FUTILITY'}
classification='DEV_GATE_PASSED_TARGET_NOT_MET' if promoted else 'DEV_REJECTED_TARGET_NOT_MET' if rejected else 'DEV_INCOMPLETE_TARGET_NOT_MET'
next_action=('Independently prepare/freeze protected validation for N30 under original target and remaining authority; no automatic validation release.'
 if promoted else 'Review conditional static hypotheses using this terminal evidence; choose a supported next mechanism or finite diagnostic and freeze scope before execution. No restart of this closed N30 cohort. Continue original Goal.')
next_action+=' Current Codex only; caps578/100 and protected reserves unchanged; unapproved week budget not adopted.'
before_dir=L/'closure-before-v1';before_dir.mkdir(exist_ok=False)
with r.locked(W/'data/qd-ed-runner.lock',nonblocking=True),r.locked(W/'data/qd-ed-state.lock'),a.state_lock(W,run):
 state=r.read_state(W/'research-state.yaml');cp=r.read_json(coord/'checkpoint.json');tree=a.load_tree(W,run)
 assert state['active_iteration']==c.COHORT
 c.require_state(state,vars(r))
 snap=r.budget_snapshot(r.read_events(W/'data/attempt-ledger.jsonl'),r.read_events(W/'data/gpu-healthcheck-ledger.jsonl'))
 assert snap==review['budget_snapshot'] and snap['running']==snap['gpu_healthcheck_inflight']==0
 for name,obj in [('state',state),('checkpoint',cp),('tree',tree)]:r.durable_json(before_dir/(name+'.json'),obj)
 budget=copy.deepcopy(state['budget']);lexical=state['worktree']
 summary={'candidate_id':'N30','cohort_id':c.COHORT,'status':classification,'decision':decision,
  'source_commit':review['source_commit'],'root_review':ref(L/'root-terminal-review-v1.json'),'result':review['result'],
  'counts':review['counts'],'audited_cells':review['audited_cells'],'new_dispatched':review['new_dispatched'],
  'closed_at':now,'dev_gate_promoted':promoted,'target_achieved':False,'execution_authorized':False,
  'validation_authorized':False,'formal_authorized':False}
 state.setdefault('closed_executions',{})[c.COHORT]=summary
 state['current_iteration'].update(summary,accepted_cells_observed_total=review['audited_cells'],accepted_new_cells_observed=review['audited_cells']-2)
 state['study']['status']='N30_R2_'+classification
 state.update(active_iteration=None,active_plan=None,active_controller=None,current_owned_workers=[],
  last_completed_iteration=c.COHORT,last_completed_plan=review['plan'],next_action=next_action,updated_at=now)
 state['prospective_iteration'].update(status='REVIEW_NEXT_ACTION',gpu_execution_authorized=False,previous_cohort_terminal_review=summary['root_review'])
 cpu_task=state.get('current_cpu_task')
 if not cpu_task or cpu_task.get('status') not in {'RUNNING','DISPATCHED'}:cpu_task=None
 cp['n30_r2_closed_controller']=cp.get('active_controller')
 cp.update(status=state['study']['status'],phase='REVIEW',active_iteration=None,active_plan=None,active_controller=None,
  active_workers=[],owned_gpu_workers=[],execution_tool_session=None,automatic_gpu_dispatch_authorized=False,
  automatic_gpu_dispatch_scope=None,in_flight_executor=cpu_task,in_flight_executors=[cpu_task] if cpu_task else [],
  inflight_executor=cpu_task,inflight_executors=[cpu_task] if cpu_task else [],executor_task=cpu_task,
  next_action=next_action,budget_snapshot=snap,n30_r2_terminal_review=summary['root_review'],n30_r2_result=summary['result'],
  goal_achieved=False,target_achieved=False,target_met=False,updated_at=now)
 node=a.node(tree,'14.1');node.update(status='done' if rejected else 'running',phase=classification,
  scientific_outcome=decision,review=summary['root_review'],result=summary['result'],code_ref=review['source_commit'],
  dev_counts=review['counts'],gpu_execution_authorized=False,goal_achieved=False)
 tree['meta'].update(study_status=state['study']['status'],target_achieved=False,automatic_dispatch_authorized=False)
 assert state['budget']==budget and state['worktree']==lexical
 temp=W/'research-state.yaml.n30-r2-close-tmp'
 with temp.open('x') as f:yaml.safe_dump(state,f,sort_keys=False,allow_unicode=True);f.flush();os.fsync(f.fileno())
 os.replace(temp,W/'research-state.yaml');r.durable_json(coord/'checkpoint.json',cp);a.save_tree(W,run,tree)
 note=f"""
### {now} — N30 R2 terminal closure

Decision {decision}; accepted counts {json.dumps(review['counts'])}. New{review['new_dispatched']}dispatches; combined{review['combined_dispatched']}charges (including both preserved old invalids),{review['combined_gpu_hours']:.12f}GPUh. Root verified source480files, settled process identities, accepted receipts/raw evidence hashes/scalar compute and matching journal, native mechanism and actual currentCodex provenance. No root numerical or tensor replay, no old ledger rewrite, no missing outcome filled as failure.

Independent gate: {json.dumps(review['independent_dev_gate'])}. Only accepted cells enter success denominators. Validation/formal remain unreleased and original goal is not achieved. Current budget snapshot {snap['dispatched']}/578 attempts,{snap['gpu_hours_consumed']:.12f}/100GPUh; protected reserves and pending week proposal unchanged.

Next: {next_action}
Review: {summary['root_review']['path']}
"""
 for p in (session/'REPORT.md',W/'docs/03_evidence/qd_ed_final/iteration-ledger.md'):
  with p.open('a') as f:f.write(note)
 r.durable_json(L/'root-closure-registration-v1.json',{'schema':'n30-r2-root-closure-registration-v1','at':now,
  'summary':summary,'budget_snapshot':snap,'cpu_task_preserved':cpu_task,'budget_changed':False,'goal_active':True,'gpu_release':False})
print(json.dumps({'status':state['study']['status'],'decision':decision,'counts':review['counts'],'new_gpu_release':False}))

