from pathlib import Path
import copy,datetime,hashlib,importlib.util,json,os,sys,yaml
P=Path(__file__).resolve().parent;W=P.parents[1]/'study_worktree';V=P.parent/'n30_executed_progress_continuation/jaw-alignment-pool-screen-v1/repair-v2'
def ref(p):return {'path':str(p),'sha256':hashlib.sha256(Path(p).read_bytes()).hexdigest()}
sys.path[:0]=[str(W),str(W/'scripts')]
from scripts import qd_ed_final_runner as r
sp=importlib.util.spec_from_file_location('arbor_state','/home/hynx/.codex/skills/arbor-agent-tools/scripts/arbor_state.py');a=importlib.util.module_from_spec(sp);sp.loader.exec_module(a)
run='rdt-qd-ed-final-20260921T093925Z';session=W/'.arbor/sessions'/run;coord=session/'.coordinator';now=datetime.datetime.now(datetime.timezone.utc).isoformat()
with r.locked(W/'data/qd-ed-state.lock'),a.state_lock(W,run):
 state=r.read_state(W/'research-state.yaml');cp=r.read_json(coord/'checkpoint.json');tree=a.load_tree(W,run)
 assert state['current_cpu_task'] is None and state['current_owned_workers']==[] and state['active_plan'] is None and state['active_controller'] is None
 assert state['resource_isolation']['status']=='ACTIVE' and state['resource_isolation']['validation_status']=='PASS'
 budget=copy.deepcopy(state['budget']);lex=state['worktree']
 snap=P/'registration-before-v1';snap.mkdir(exist_ok=False)
 for n,obj in [('state',state),('checkpoint',cp),('tree',tree)]:r.durable_json(snap/(n+'.json'),obj)
 task={'status':'DISPATCHED','phase':'N31_CAPTURE_DWELL_CPU_PHASE_A','node_id':'15.1','agent':'/root/n22_cpu_executor','scope':ref(P/'hypothesis-and-cpu-phase-a-v1.md'),'executor_prompt':ref(P/'executor-prompt-v1.md'),'implementation_worktree':str(P/'implementation'),'branch':'codex/n31-capture-dwell','source_base':'6292fc8cffad2eec0f789e023d835ad3c1df146a','test_cpu_seconds_limit':600,'test_wall_seconds_limit':900,'threads':2,'historical_tensor_or_video_reads_authorized':False,'new_exposed_data_measurements_authorized':False,'gpu_authorized':False,'production_hookup_authorized':False,'registered_at':now}
 state.update(current_cpu_task=task,active_iteration={'candidate_id':'N31','arbor_node':'15.1','status':'CPU_PHASE_A','source_base':task['source_base'],'hypothesis':task['scope'],'execution_authorized':False,'validation_authorized':False,'formal_authorized':False,'target_achieved':False},next_action='Implement and synthetically test one current-search capture-dwell proposal helper; statically bind integration placement/cache/compute/observation contracts. No GPU or production hookup in phaseA. Prepare concrete Dev plan/budget only after CPU review.',updated_at=now)
 state['study']['status']='N31_CAPTURE_DWELL_CPU_PHASE_A_TARGET_NOT_MET'
 cp.update(status=state['study']['status'],phase='DISPATCH_CPU',in_flight_executor=task,in_flight_executors=[task],inflight_executor=task,inflight_executors=[task],executor_task=task,next_action=state['next_action'],automatic_gpu_dispatch_authorized=False,automatic_gpu_dispatch_scope=None,updated_at=now,goal_achieved=False,target_achieved=False,target_met=False)
 tree['meta'].update(study_status=state['study']['status'],target_achieved=False,automatic_dispatch_authorized=False,dataset_info='Original exposed Dev ten-task map; N31 prospective same-round C0/Q0/N31 full10 with frozen task-block futility. CPU phaseA only; no Dev plan released. Validation/formal remain protected under original gates.')
 parent=a.node(tree,'15');parent.update(status='running')
 leaf=a.node(tree,'15.1');assert leaf['status']=='pending';leaf.update(status='running',phase='CPU_PHASE_A',hypothesis_protocol=task['scope'],cpu_task=task,code_ref=task['source_base'],gpu_execution_authorized=False,preceding_evidence_review=ref(V/'root-terminal-review-v2.json'),target_achieved=False)
 assert state['budget']==budget and state['worktree']==lex
 tmp=W/'research-state.yaml.n31-phase-a-v1'
 with tmp.open('x') as f:yaml.safe_dump(state,f,sort_keys=False,allow_unicode=True);f.flush();os.fsync(f.fileno())
 os.replace(tmp,W/'research-state.yaml');r.durable_json(coord/'checkpoint.json',cp);a.save_tree(W,run,tree)
 note=f"\n### {now} — N31 capture-dwell proposal nominated; CPU phaseA\n\nArbor constraints/probe/four ideation moves/conflict checks completed in {P/'hypothesis-and-cpu-phase-a-v1.md'}. Current-search temporal completion differs from failed lift scoring, close-content rescue and past-tail continuity. Original Q0 plus at most one constructed offspring proposal per canonical iteration; no forced selection, external Stage/quality/executor changes or extra model/scoring calls intended. Approximate arrival and real grasp effects remain unproven. Isolated worktree {P/'implementation'}, branch codex/n31-capture-dwell. Pure helper/synthetic tests and static integration review only, CPU600s/wall900s,2threads; no new historical measurements/GPU. Full30-cell Dev needs8baseline+12development extra slots; no budget adopted. Goal NOT_MET.\n"
 for path in [session/'REPORT.md',W/'docs/03_evidence/qd_ed_final/iteration-ledger.md']:
  with path.open('a') as f:f.write(note)
 r.durable_json(P/'root-cpu-phase-a-registration-v1.json',{'task':task,'budget_changed':False,'previous_review':ref(V/'root-terminal-review-v2.json')})
print(json.dumps({'task':task['phase'],'scope':task['scope'],'branch':task['branch']}))

