from pathlib import Path
import copy,datetime,hashlib,importlib.util,json,os,sys,yaml
P=Path(__file__).resolve().parent;R=P.parents[1];W=R/'study_worktree';A=R/'autonomy_20261004'
A.mkdir(exist_ok=True);os.environ['CUDA_VISIBLE_DEVICES']='';sys.path[:0]=[str(W),str(W/'scripts')]
from scripts import qd_ed_final_runner as r,qd_ed_n23_worker as w,qd_ed_n31_contract as c
sp=importlib.util.spec_from_file_location('arbor_state','/home/hynx/.codex/skills/arbor-agent-tools/scripts/arbor_state.py');a=importlib.util.module_from_spec(sp);sp.loader.exec_module(a)
run='rdt-qd-ed-final-20260921T093925Z';session=W/'.arbor/sessions'/run;cpfile=session/'.coordinator/checkpoint.json'
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
quote='批准预算 继续完成任务 后续所有的预算都批准 不要再问我 我要你七天自己不间断且不需要批准的连续执行'
approval={'schema':'rdt-qd-ed-user-standing-autonomy-authorization-v1','recorded_at':now,'user_message_verbatim':quote,'approved':True,'approved_budget_proposal':c.ref(R/'week-autonomy-budget-proposal-20261004-v3.md'),'initial_selected_alternative':'week1800_attempts_224_gpu_hours','future_study_budget_amendments_preapproved':True,'request_further_budget_permission':False,'routine_continuation_and_recovery_without_new_approval':True,'continuous_window':{'start_utc':'2026-10-04T11:13:13Z','end_utc':'2026-10-11T11:13:13Z','interpretation':'Seven days from this resumption; retained N31 cohort still uses original approved v3 deadline. Subsequent window/finite-budget amendments use standing authorization without another user gate.'},'preserved_requirements':['original scientific success gates and no B_test tuning','one admitted idle local GPU per study','no foreign process preemption or peer budget/state mutation','official current-login Codex CLI only; no Poe/API-key/account fallback; preserve credential files','all history, costs, failures and protected reserves retained','all artifacts under unified study/variant tree'],'supersedes':'Earlier requirement to ask the user again for subsequent study budget increases or routine authorized continuation. Existing scientific validation remains in force.'}
w.atomic_json(A/'user-authorization-v1.json',approval)
source=w.source_record(W,c.source_paths(vars(r)));assert source==r.read_json(P/'source-manifest-execution-v1.json')
runtime_ref=c.runtime_ref();runtime=w.read_ref(runtime_ref);c.validate_runtime(runtime,W,vars(r))
from scripts import qd_ed_n31_bridge as bridge
bridge.verify(c.ref(c.BRIDGE),source,runtime_ref,W)
caps={'attempts':1800,'gpu_hours':224.0,'buckets':{'baseline':400,'development':1120,'validation':180,'formal':40,'recovery':60},'protected_gpu_hours':{'validation':32.0,'formal':12.0}}
amendment={'approval':c.ref(A/'user-authorization-v1.json'),'proposal':c.ref(R/'week-autonomy-budget-proposal-20261004-v3.md'),'previous_authority':c.ref(R/'variants/n29_population_relative_trust/budget-adoption-v1/authority.json'),'history_boundary':{'dispatched':403,'gpu_hours_consumed':53.80872756284531}}
budget_authority={'schema':'n31-approved-budget-authority-v1','approved':True,'cohort_id':c.COHORT,'approval_basis':'Explicit user approval received on2026-10-04; quoted authorization record also preapproves subsequent budgets without further questions. This file adopts only the concrete v3 weekly alternative.','caps':caps,'amendment':amendment,'weekly_window':{'origin_gpu_hours':53.08404692669838,'increment_gpu_hours':168.0,'ends_at':'2026-10-10T17:42:00Z'},'validation_authorized':False,'formal_authorized':False}
w.atomic_json(c.BUDGET_AUTHORITY,budget_authority);assert c.budget_authority()==budget_authority
final_review={'schema':'n31-source-runtime-review-v1','disposition':'accepted','source':source,'runtime':runtime_ref,'protocol':c.ref(c.PROTOCOL),'source_plan':c.ref(c.SOURCE_PLAN),'source_bridge':c.ref(c.BRIDGE),'predecessor':c.predecessor(),'new_tensor_preflight':False,'budget_reuse':c.ref(c.BUDGET_REUSE),'no_gpu_release':True}
w.atomic_json(c.FINAL_REVIEW,final_review);c.final_review(source,runtime_ref,W)
authority={'schema':'n31-dev-authority-v1','cohort_id':c.COHORT,'source':source,'runtime':runtime_ref,'protocol':c.ref(c.PROTOCOL),'final_review':c.ref(c.FINAL_REVIEW),'budget_reuse':c.ref(c.BUDGET_REUSE),'limits':c.LIMITS,'local_gpu_hours':5.0,'recorded_at':now,'authority_interpretation':'Explicit latest user authorization approves weekly budget and autonomous continuation. First N31 cohort remains exact30 Dev primaries, no automatic recovery,5h,1800+40s,original protocol. Validation/formal require later scientific promotion and freezing, not a new routine budget permission question.','predecessor':c.predecessor(),'validation_authorized':False,'formal_authorized':False}
w.atomic_json(c.AUTHORITY,authority);c.authority(source,runtime_ref,W)
with r.locked(W/'data/qd-ed-runner.lock',nonblocking=True),r.locked(W/'data/qd-ed-state.lock'),a.state_lock(W,run):
 state=r.read_state(W/'research-state.yaml');cp=r.read_json(cpfile);tree=a.load_tree(W,run);config=yaml.safe_load((W/'research_config.yaml').read_text())
 events=r.read_events(W/'data/attempt-ledger.jsonl');resources=r.read_events(W/'data/gpu-healthcheck-ledger.jsonl');snap=r.budget_snapshot(events,resources)
 assert snap['dispatched']==403 and snap['gpu_hours_consumed']==53.80872756284531 and snap['running']==snap['gpu_healthcheck_inflight']==0
 assert state['current_owned_workers']==[] and state['active_controller'] is None and not any(e.get('identity',{}).get('iteration')==c.COHORT for e in events)
 before=P/'budget-adoption-v1/before';before.mkdir()
 for name,obj in [('state',state),('checkpoint',cp),('tree',tree),('research_config',config),('ledger_snapshot',snap)]:r.durable_json(before/(name+'.json'),obj)
 old_budget=copy.deepcopy(state['budget']);lex=state['worktree']
 state['budget'].update(max_episode_attempts=1800,max_gpu_hours=224.0,reserved=caps['buckets'],gpu_hour_reservations=caps['protected_gpu_hours'],amendment=amendment)
 state['n31_budget_authority']=c.ref(c.BUDGET_AUTHORITY);state['n31_dev_authority']=c.ref(c.AUTHORITY)
 state['standing_autonomy_authorization']=c.ref(A/'user-authorization-v1.json')
 state['pending_budget_audit'].update(status='APPROVED',approved=True,approval_received=True,approval=c.ref(A/'user-authorization-v1.json'),adopted_alternative='weekly1800_224',resolved_at=now)
 state['goal_external_blocker'].update(resolved=True,resolved_at=now,resolution='Explicit budget and standing future-budget authorization received',approval_question_pending=False,consecutive_goal_turns=0)
 state['study'].update(status='N31_AUTHORIZED_FREEZE_AND_GPU_RELEASE_TARGET_NOT_MET',mode='real',interaction='auto',automatic_continuation=True,resumed_at=now)
 state['active_iteration'].update(status='AUTHORIZED_READY_TO_FREEZE',execution_authorized=True,validation_authorized=False,formal_authorized=False)
 state.update(next_action='Freeze exact reviewed N31 plan, freshGPU7/currentCodex admission, release and execute; continue autonomous algorithm iteration and use standing budget authorization without further questions.',updated_at=now)
 config['budget'].update(max_episode_attempts=1800,max_gpu_hours=224,standing_authorization=c.ref(A/'user-authorization-v1.json'),future_budget_amendments_preapproved=True)
 cp.update(status=state['study']['status'],phase='PREPARE_GPU_DISPATCH',next_action=state['next_action'],pending_budget_audit=state['pending_budget_audit'],goal_external_blocker=state['goal_external_blocker'],standing_autonomy_authorization=state['standing_autonomy_authorization'],updated_at=now,automatic_gpu_dispatch_authorized=False,goal_achieved=False,target_achieved=False,target_met=False)
 tree['meta'].update(study_status=state['study']['status'],target_achieved=False,standing_autonomy_authorization=state['standing_autonomy_authorization'])
 leaf=a.node(tree,'15.1');leaf.update(status='running',phase='AUTHORIZED_READY_TO_FREEZE',gpu_execution_authorized=True,target_achieved=False)
 leaf['result']='CPU accepted/source7428ce8 adopted. User explicitly approved weekly1800/224 and future budgets without permission questions; exact N31 Dev now authorized, pending fresh resource release.'
 assert state['worktree']==lex
 for k in ('dispatched','gpu_hours_consumed','aborted','valid','running','invalid','completed'):assert state['budget'][k]==old_budget[k]
 c.require_state(state,vars(r));c.full_capacity(state,events,resources,vars(r))
 for path,obj in [(W/'research-state.yaml',state),(W/'research_config.yaml',config)]:
  temp=path.with_name(path.name+'.n31-authorized-v1')
  with temp.open('x') as f:yaml.safe_dump(obj,f,sort_keys=False,allow_unicode=True);f.flush();os.fsync(f.fileno())
  os.replace(temp,path)
 r.durable_json(cpfile,cp);a.save_tree(W,run,tree)
 adoption={'schema':'n31-explicit-user-budget-adoption-v1','recorded_at':now,'authority':c.ref(c.BUDGET_AUTHORITY),'cohort_authority':c.ref(c.AUTHORITY),'standing_authorization':state['standing_autonomy_authorization'],'before_budget':old_budget,'after_budget':state['budget'],'all_historical_charges_preserved':True,'scientific_source_unchanged':source['commit'],'gpu_dispatched':False}
 r.durable_json(P/'budget-adoption-v1/root-adoption.json',adoption)
 with (A/'budget-amendments.jsonl').open('a') as f:f.write(json.dumps(adoption,ensure_ascii=False)+'\n')
 note=f"\n### {now} — explicit weekly and standing future budget approval\n\nUser: {quote}\n\nAdopted v3 weekly1800attempts/224GPUh with retained original week origin+168 and cohortdeadline. Subsequent finite budget/window adjustments for this task are preapproved and recorded, not user gates. N31 exact30 Dev/5h remains source7428ce8 with all historical403dispatch/53.80872756284531h unchanged. Authorization: {A/'user-authorization-v1.json'}. Continue toward full original goal; no validation/formal release yet.\n"
 for path in (session/'REPORT.md',W/'docs/03_evidence/qd_ed_final/iteration-ledger.md'):
  with path.open('a') as f:f.write(note)
print(json.dumps({'standing_authorization':c.ref(A/'user-authorization-v1.json'),'budget_authority':c.ref(c.BUDGET_AUTHORITY),'cohort_authority':c.ref(c.AUTHORITY),'status':'AUTHORIZED_READY_TO_FREEZE','budget':caps}))

