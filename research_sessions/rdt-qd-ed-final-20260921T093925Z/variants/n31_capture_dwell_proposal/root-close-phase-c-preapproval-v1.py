from pathlib import Path
import copy,datetime,hashlib,importlib.util,json,os,sys,yaml
P=Path(__file__).resolve().parent;W=P.parents[1]/'study_worktree';R=W.parent;I=P/'implementation'
sys.path[:0]=[str(W),str(W/'scripts')]
from scripts import qd_ed_final_runner as r
sp=importlib.util.spec_from_file_location('arbor_state','/home/hynx/.codex/skills/arbor-agent-tools/scripts/arbor_state.py');a=importlib.util.module_from_spec(sp);sp.loader.exec_module(a)
def ref(p):
 p=Path(p);b=p.read_bytes();return {'path':str(p),'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}
run='rdt-qd-ed-final-20260921T093925Z';session=W/'.arbor/sessions'/run;coord=session/'.coordinator';now=datetime.datetime.now(datetime.timezone.utc).isoformat()
D=r.read_json(P/'delivery-manifest-phase-c-v1.json')
for x in D['files']:assert ref(x['path'])==x
review={'schema':'n31-root-phase-c-review-v1','reviewed_at':now,'decision':'ACCEPT_CPU_IMPLEMENTATION_AND_DISABLED_DEV_PLAN','commit':D['commit'],'delivery':ref(P/'delivery-manifest-phase-c-v1.json'),'report':ref(P/'cpu-phase-c-report-v1.md'),'independent_source_review':ref(P/'root-phase-c-source-bytes-review-v1.json'),'independent_test_review':ref(P/'root-phase-c-test-resource-review-v1.json'),'source_adoption':ref(P/'root-source-adoption-v1.json'),'runtime_check':ref(P/'root-runtime-preapproval-check-v1.json'),'source_bridge':ref(P/'source-equivalence-bridge-v1.json'),'owning_disabled_plan':ref(P/'plan.preview.owning.disabled.v1.json'),'delivery_files_rehashed':64,'source_files':511,'final_synthetic_tests':121,'root_reran_tests':False,'guard_failures_5_6_7_retained':True,'static_packaging_failures_retained':True,'score':'Unknown','gpu_execution_authorized':False,'budget_adopted':False,'target_achieved':False,'remaining':'User budget audit, authority binding and unchanged-science freeze, fresh resource admission. No algorithm implementation work remains before N31 Dev.','limitations':['No N31 robot performance yet.','Synthetic correctness does not establish task benefit.','Prior cell IDs are native witnesses rather than fresh CPU/GPU equivalence proof.','N31 remains a competing proposal; chosen content does not establish unique ancestry or grasp.']}
reviewpath=P/'root-phase-c-review-v1.json';assert not reviewpath.exists();r.durable_json(reviewpath,review)
proposal=R/'week-autonomy-budget-proposal-20261004-v3.md'
with r.locked(W/'data/qd-ed-state.lock'),a.state_lock(W,run):
 state=r.read_state(W/'research-state.yaml');cp=r.read_json(coord/'checkpoint.json');tree=a.load_tree(W,run)
 oldtask=copy.deepcopy(state['current_cpu_task']);assert oldtask['phase']=='N31_CAPTURE_DWELL_CPU_PHASE_C'
 assert state['current_owned_workers']==[] and state['active_plan'] is None and state['active_controller'] is None
 budget=copy.deepcopy(state['budget']);lex=state['worktree']
 snap=P/'phase-c-acceptance-before-v1';snap.mkdir(exist_ok=False)
 for n,obj in [('state',state),('checkpoint',cp),('tree',tree)]:r.durable_json(snap/(n+'.json'),obj)
 task={**oldtask,'status':'COMPLETED_CPU_ACCEPTED','completed_at':now,'source_commit':D['commit'],'root_review':ref(reviewpath)}
 status='N31_CPU_READY_BUDGET_AUDIT_PENDING_TARGET_NOT_MET'
 next_action='Submit completed one-week v3 budget audit packet. Current baseline2/development8 cannot admit full30 N31 Dev. Do not adopt either alternative or launch GPU without explicit approval; source and disabled owning plan ready.'
 pending={'status':'READY_FOR_USER_AUDIT','proposal':ref(proposal),'weekly_alternative':{'attempts':1800,'gpu_hours':224,'week_increment_gpu_hours':168,'original_week_origin':53.08404692669838,'ends_at':'2026-10-10T17:42:00Z'},'finite_alternative':{'attempts':598,'gpu_hours':100},'approved':False}
 state.update(current_cpu_task=task,pending_budget_audit=pending,next_action=next_action,updated_at=now)
 state['study']['status']=status;state['active_iteration'].update(status='CPU_ACCEPTED_AWAITING_BUDGET_AUDIT',source_commit=D['commit'],phase_c_review=ref(reviewpath),execution_authorized=False,validation_authorized=False,formal_authorized=False,target_achieved=False)
 cp.update(status=status,phase='BUDGET_AUDIT',in_flight_executor=None,in_flight_executors=[],inflight_executor=None,inflight_executors=[],executor_task=None,next_action=next_action,pending_budget_audit=pending,automatic_gpu_dispatch_authorized=False,automatic_gpu_dispatch_scope=None,updated_at=now,goal_achieved=False,target_achieved=False,target_met=False)
 tree['meta'].update(study_status=status,target_achieved=False,automatic_dispatch_authorized=False)
 leaf=a.node(tree,'15.1');assert leaf['status']=='running'
 leaf.update(phase='CPU_ACCEPTED_AWAITING_BUDGET_AUDIT',cpu_task=task,code_ref=D['commit'],phase_c_review=ref(reviewpath),gpu_execution_authorized=False,target_achieved=False)
 leaf['result']='N31 CPU complete:121 final clean synthetic cases,511 source files verified and adopted. Complete disabled30-cell Dev plan ready; robot efficacy Unknown. Await explicit finite/week budget audit; no GPU worker.'
 assert state['budget']==budget and state['worktree']==lex
 tmp=W/'research-state.yaml.n31-c-accepted-v1'
 with tmp.open('x') as f:yaml.safe_dump(state,f,sort_keys=False,allow_unicode=True);f.flush();os.fsync(f.fileno())
 os.replace(tmp,W/'research-state.yaml');r.durable_json(coord/'checkpoint.json',cp);a.save_tree(W,run,tree)
 note=f"\n### {now} — N31 CPU complete; source adopted; budget audit packet ready\n\nCommit {D['commit']},121 clean synthetic cases,511 source files. Independent root review: {reviewpath}. Budget remains403dispatch/53.80872756284531GPUh and existing caps unchanged. Source-only adoption preserved all11 operational files before this explicit state update. Official Codex ChatGPT login and3291 runtime files checked; GPU7 idle observation is not reservation. Full30 disabled plan ready; weekly/finite alternatives not adopted. Proposal: {proposal}. Target NOT_MET; no GPU experiment running.\n"
 for path in [session/'REPORT.md',W/'docs/03_evidence/qd_ed_final/iteration-ledger.md']:
  with path.open('a') as f:f.write(note)
print(json.dumps({'review':ref(reviewpath),'proposal':ref(proposal),'budget_unchanged':True,'executor_complete':True}))

