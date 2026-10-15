"""Close N29 independently reviewed metadata, preserve costs and resume outer-loop work."""
from pathlib import Path
import copy,datetime,json,os,sys,yaml
V=Path(__file__).resolve().parent;ROOT=V.parents[1]/'study_worktree';sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from scripts import qd_ed_final_runner as r,qd_ed_n23_worker as w,qd_ed_n29_contract as c
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
review=w.read_ref(c.ref(V/'root-terminal-review-v1.json'));result=w.read_ref(c.ref(V/'result-v1.json'))
assert review['result']==c.ref(V/'result-v1.json') and review['decision']==result['decision']=='REJECT_NUMERIC_DEV_FUTILITY'
assert review['audited_cells']==result['audited_cells']==24 and all(x=={'audited':6,'success':0} for x in result['counts'].values())
assert review['observed_valid_stage_logical_calls']==482 and review['observed_valid_stage_failed_calls']==0
assert review['controller_original_process_exited'] and len(review['worker_original_processes_exited'])==24
out=V/'terminal-admin-v1';out.mkdir(exist_ok=False)
session=ROOT/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z';coord=session/'.coordinator'
def atomic_yaml(path,data):
    tmp=path.with_suffix(path.suffix+'.n29-close-tmp')
    with tmp.open('x') as f:yaml.safe_dump(data,f,allow_unicode=True,sort_keys=False);f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)
with r.locked(ROOT/'data/qd-ed-runner.lock',nonblocking=True):
  with r.locked(ROOT/'data/qd-ed-state.lock'):
    state=r.read_state(ROOT/'research-state.yaml');c.require_budget_state(state,vars(r))
    snapshot=r.budget_snapshot(r.read_events(ROOT/'data/attempt-ledger.jsonl'),r.read_events(ROOT/'data/gpu-healthcheck-ledger.jsonl'))
    assert snapshot['dispatched']==395 and snapshot['running']==snapshot['gpu_healthcheck_inflight']==0
    assert abs(snapshot['gpu_hours_consumed']-53.08404692669838)<1e-8
    budget=copy.deepcopy(state['budget']);assert budget['dispatched']==snapshot['dispatched'] and abs(budget['gpu_hours_consumed']-snapshot['gpu_hours_consumed'])<1e-8
    cp_path=coord/'checkpoint.json';tree_path=coord/'idea_tree.json';config_path=ROOT/'research_config.yaml'
    cp=json.loads(cp_path.read_text());tree=json.loads(tree_path.read_text());config=r.read_state(config_path)
    w.atomic_json(out/'state-selected-before-v1.json',{k:state.get(k) for k in ('study','budget','current_iteration','active_iteration','active_plan','next_action','prospective_iteration','current_owned_workers','worktree','canonical_worktree')})
    w.atomic_json(out/'checkpoint-before-v1.json',cp);w.atomic_json(out/'tree-before-v1.json',tree)
    summary={'candidate_id':'N29','cohort_id':c.COHORT,'status':'CLOSED_REJECT_NUMERIC_DEV_FUTILITY','scientific_decision':result['decision'],'source_commit':result['source_commit'],'counts':result['counts'],'result':c.ref(V/'result-v1.json'),'root_review':c.ref(V/'root-terminal-review-v1.json'),'closed_at':now,'target_achieved':False,'execution_authorized':False,'validation_authorized':False,'formal_authorized':False}
    next_action='Continue active one-week Goal: bounded outer-loop diagnosis of proposal, selection and temporal closed-loop evidence after N29 rejection; choose a distinct falsifiable QD/ED mechanism. No new GPU release or protected phase yet; week budget proposal pending.'
    state['closed_candidates']['N29']=summary;state['current_iteration'].update(summary)
    state['study']['status']='N29_CLOSED_OUTER_LOOP_ACTIVE_TARGET_NOT_MET'
    state.update(active_iteration=None,active_plan=None,current_owned_workers=[],last_completed_iteration=c.COHORT,last_completed_plan=review['plan'],next_action=next_action,updated_at=now)
    state['prospective_iteration'].update(status='CLOSED_REJECT_NUMERIC_DEV_FUTILITY',gpu_execution_authorized=False)
    state['autonomous_goal']={'status':'active','thread_id':'01a0c2b2-30cd-7ac3-b9b4-f14d36e9c18d','start_at':'2026-10-03T17:42:00+00:00','week_end_at':'2026-10-10T17:42:00+00:00','user_timezone':'Asia/Shanghai','budget_proposal':c.ref(V.parents[1]/'week-autonomy-budget-proposal-20261004-v1.md'),'budget_proposal_approved':False,'continuous_uptime_guaranteed':False,'target_achieved':False}
    assert state['budget']==budget and Path(state['worktree']).resolve()==ROOT.resolve()
    cp['n29_closed_controller']=copy.deepcopy(cp.get('active_controller'))
    cp.update(status=state['study']['status'],phase='OBSERVE',active_node='13',active_controller=None,execution_tool_session=None,owned_gpu_workers=[],automatic_gpu_dispatch_authorized=False,automatic_gpu_dispatch_scope=None,in_flight_executor=None,in_flight_executors=[],next_action=next_action,budget_snapshot=snapshot,n29_terminal_review=summary['root_review'],n29_result=summary['result'],goal_achieved=False,target_achieved=False,autonomous_goal=state['autonomous_goal'])
    insight='N29 rejected by valid complete-task-block futility: C0/Q0/N28/N29 all0/6, tasks6..9 unrun Unknown. Population scaling was active (100684 trust-limited rows); box-limited rows fell to13919 across6510calls but no task benefit. N29 had465 guided decisions versus N28 199, so equal full-episode compute is not claimed. N27 feasible box and N28 placement also failed earlier; further distance/proxy-only tweaks need new task-related evidence. Current managed Codex login only; protected phases closed; active one-week Goal continues.'
    tree['nodes']['13.1'].update(status='pruned',phase='CLOSED',scientific_decision=result['decision'],score=0.0,result=summary['result'],review=summary['root_review'],counts=result['counts'],insight=insight,gpu_execution_authorized=False)
    tree['nodes']['13'].update(status='done',insight=insight)
    tree['meta'].update(study_status=state['study']['status'],target_achieved=False,automatic_dispatch_authorized=False)
    tree['nodes'][tree['root_id']]['insight']=insight+' Cumulative395attempts/53.08404692669838GPUh, current caps578/100, protected remaining36.240824002430815GPUh. Week expansion is pending, not adopted.'
    config['task']=next_action
    atomic_yaml(ROOT/'research-state.yaml',state);atomic_yaml(config_path,config)
    r.durable_json(cp_path,cp);r.durable_json(tree_path,tree)
    text='''# N29 terminal conclusion

N29 is **REJECT_NUMERIC_DEV_FUTILITY**. All24 original dispatched cells are valid. C0, Q0, N28 and N29 each succeeded0/6 on tasks0..5. At the complete sixth task block, even success on every remaining candidate task would yield at most4/10, below the preregistered5/10 gate. Tasks6..9 are unrun and Unknown; do not report a full-ten success rate. There are no paired gains or losses among the four arms in this cohort, and no retry.

The new per-row population-relative cap was substantively active:100684 trust-limited rows; N29 box-limited rows13919/104160 versus N28 40214/44576. N29 ran465 guided decisions and81840 scored candidates versus N28 199 and35024. These are descriptive mechanism/compute measures, not success surrogates or proof of why failure occurred. The bounded first-guided witnesses and same-worker CUDA audit passed; task utility was not established. A still-needed distinction is whether usable proposals are missing, selection loses them, or closed-loop continuation loses progress; unexecuted outcomes remain Unknown.

All482 completed Stage calls used codex_cli/chatgpt/gpt-6-astra through the current managed login, with0failed calls and complete observed usage. Input5210452 tokens, of which2729472 were cached; output26599. Internal HTTP request/retry counts remain Unknown. No Poe/fallback; saved credentials untouched.

Episode GPU process wall11107.552780834725seconds plus the once-only17.575451474054717second native proof yields3.0903133978635497GPUh. Cumulative395dispatches/53.08404692669838GPUh; no live owned worker. Current caps578/100 and all prior costs remain unchanged. Wrapper exit-status file is absent; root does not infer an exit code. Independent identity checks confirm the controller and all24 original workers have exited, terminal journal and native receipts reconcile, and the frozen controller produced the mathematical-futility result.

The original research goal remains unmet. The user has now explicitly requested a week of continuous autonomous work, and a thread Goal is active. This candidate's rejection closes only N29. Continue the outer loop with bounded task-related evidence, preserve protected phases and existing limits pending the concrete week budget audit, and never lower the target to manufacture completion.
'''
    (V/'terminal-conclusion-v1.md').open('x').write(text)
    for path in (session/'REPORT.md',ROOT/'docs/03_evidence/qd_ed_final/iteration-ledger.md'):
        with path.open('a') as f:f.write('\n\n'+text+'\nClosed at '+now+'; review: '+summary['root_review']['path']+'\n')
    with (coord/'idea_tree.md').open('a') as f:f.write('\n'+now+' — Node13.1 pruned, all four arms0/6; node13 closed. Active Goal continues outer-loop OBSERVE; target unmet.\n')
    w.atomic_json(out/'completion-v1.json',{'schema':'n29-terminal-administration-v1','recorded_at':now,'result':summary['result'],'root_review':summary['root_review'],'conclusion':c.ref(V/'terminal-conclusion-v1.md'),'budget_unchanged':True,'snapshot':snapshot,'new_gpu_dispatch':False,'goal_active':True,'target_achieved':False,'wrapper_exit_code':None})
print(json.dumps({'closed':'N29','decision':result['decision'],'goal_active':True,'budget_unchanged':True,'next_phase':'OBSERVE'}))
