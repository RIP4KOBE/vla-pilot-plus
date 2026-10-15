"""Accept the fixed-JSON diagnosis and register a bounded candidate-supply screen."""
from pathlib import Path
import copy,datetime,hashlib,importlib.util,json,os,sys,time,yaml
G=Path(__file__).resolve().parent;P=G.parent;Q=P/'jaw-alignment-pool-screen-v1';W=P.parents[1]/'study_worktree'
started=time.process_time()
def raw(p):
 p=Path(p);assert p.suffix not in {'.pt','.mp4','.png','.jpg'},str(p)
 return p.read_bytes()
def ref(p):return {'path':str(p),'sha256':hashlib.sha256(raw(p)).hexdigest()}
def check(q):
 b=raw(q['path']);assert hashlib.sha256(b).hexdigest()==q['sha256'],q['path']
 if 'bytes' in q:assert len(b)==q['bytes'],q['path']
def put(p,x):
 with Path(p).open('x') as f:json.dump(x,f,indent=2);f.write('\n')
assert ref(G/'output-manifest-v2.json')['sha256']=='2b901eb252f6c9aba38c4075c57a643785cd6ffedddecf690dece7c04e4f4464'
out=json.loads(raw(G/'output-manifest-v2.json'))
for item in out['files']:check(item)
sources=json.loads(raw(G/'source-input-manifest-v1.json'))
for item in sources['refs']:check(item)
decl=json.loads(raw(G/'measurement-declaration-v1.json'));check(decl['input']);check(decl['code'])
ext=json.loads(raw(G/'external-execution-v1.json'));res=json.loads(raw(G/'geometry-resource-v1.json'))
result=json.loads(raw(G/'geometry-result-v1.json'))
assert res['complete'] and res['error'] is None and ext['exit_code']==0 and ext['single_invocation']
assert ext['pid']==res['pid']==3881994 and not (Path('/proc')/str(res['pid'])).exists()
assert res['cpu_seconds']<60 and ext['children_cpu_seconds']<60 and ext['wall_seconds']<180
assert res['affinity']==ext['affinity']==[0,1] and res['threads']==2
assert res['input_json_reads']==1 and res['tensor_video_reads']==res['gpu_model_api_sim_calls']==res['automatic_retries']==0
assert res['production_imports'] is False and result['complete'] is True
assert [(x['task_id'],x['step']) for x in result['rows']]==[(t,i) for t in [0,1] for i in range(16,32)]
assert len(result['groups'])==4 and all(x['valid_rows']==x['rows']==8 for x in result['groups'])
assert all(x['status']=='SOURCE_CALIBRATED_POINT_GEOMETRY' and x['physical_capture']=='Unknown' and x['current_object_geometry']=='Unknown' for x in result['rows'])
review={'decision':'ACCEPT_SOURCE_CALIBRATED_FIXED_JSON_GEOMETRY_WITH_PROXY_LIMITATIONS','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'output_manifest':ref(G/'output-manifest-v2.json'),'result':ref(G/'geometry-result-v1.json'),'source_contract':ref(G/'source-contract-v1.md'),'decision_addendum':ref(G/'mechanism-decision-addendum-v1.md'),'declaration':ref(G/'measurement-declaration-v1.json'),'verified_output_refs':len(out['files']),'verified_source_input_refs':len(sources['refs']),'root_independent_static_checks':['single_arm.py world grip_site position and right_hand xyzw pose observation','panda_gripper.xml fixed rotations, pad centers/half dimensions and slide axes','calculation code standard normalized quaternion transpose and source-derived box intervals'],'root_scientific_calculation_or_native_payload_reads':0,'verified_outcome_rows':32,'process_exited':True,'child_cpu_seconds':ext['children_cpu_seconds'],'external_wall_seconds':ext['wall_seconds'],'historical_instantiated_robot_xml_verified':False,'findings':['Task0 longitudinal point-to-pad offset; task1 lateral offset; fixed old keypoint not object volume.','No true grasp/capture label or efficacy established.','Explicit current-frame approximate proxy remains falsifiable; prior physical efficacy proof is not a condition for a bounded hypothesis test.','Current evidence only concerns selected actions, so inspect a fixed existing candidate supply before nominating another GPU mechanism.'],'n9_source_root_read':ref(W/'core/qd_contact_sweep.py'),'next_scope':ref(Q/'root-scope-v1.md'),'scope_choice':'Root chooses both decision16 final pools, the guided close/near-target handoff states investigated here, rather than adopting the addendum suggestion of decision8 initial pools. All rows included; this is exposed-Dev mechanism selection, not independent success evidence or archive-causal replay.','goal_achieved':False,'root_review_cpu_seconds':time.process_time()-started}
put(G/'root-terminal-review-v1.json',review)
sys.path[:0]=[str(W),str(W/'scripts')]
from scripts import qd_ed_final_runner as r
sp=importlib.util.spec_from_file_location('arbor_state','/home/hynx/.codex/skills/arbor-agent-tools/scripts/arbor_state.py')
a=importlib.util.module_from_spec(sp);sp.loader.exec_module(a)
run='rdt-qd-ed-final-20260921T093925Z';session=W/'.arbor/sessions'/run;coord=session/'.coordinator';now=datetime.datetime.now(datetime.timezone.utc).isoformat()
with r.locked(W/'data/qd-ed-state.lock'),a.state_lock(W,run):
 state=r.read_state(W/'research-state.yaml');cp=r.read_json(coord/'checkpoint.json');tree=a.load_tree(W,run)
 assert state['resource_isolation']['status']=='ACTIVE' and state['resource_isolation']['validation_status']=='PASS'
 assert state['current_cpu_task']['phase']=='N30_CAPTURE_GEOMETRY_SOURCE_AND_FIXED_JSON'
 assert state['current_owned_workers']==[] and state['active_controller'] is None and state['active_plan'] is None
 budget=copy.deepcopy(state['budget']);lex=state['worktree']
 snap=Q/'registration-before-v1';snap.mkdir(exist_ok=False)
 for n,obj in [('state',state),('checkpoint',cp),('tree',tree)]:r.durable_json(snap/(n+'.json'),obj)
 old=copy.deepcopy(state['current_cpu_task'])
 old.update(status='COMPLETE_ACCEPTED_DESCRIPTIVE',closed_at=now,review=ref(G/'root-terminal-review-v1.json'),calculation_allowance_exhausted=True,cpu_seconds=ext['children_cpu_seconds'],wall_seconds=ext['wall_seconds'])
 state.setdefault('closed_cpu_tasks',{})[old['phase']]=old
 task={'status':'DISPATCHED','phase':'N30_FIXED_HANDOFF_JAW_ALIGNMENT_POOL_SCREEN','node_id':'14.1','agent':'/root/n22_cpu_executor','scope':ref(Q/'root-scope-v1.md'),'source_base':'6292fc8cffad2eec0f789e023d835ad3c1df146a','preceding_review':ref(G/'root-terminal-review-v1.json'),'cpu_seconds_limit':120,'wall_seconds_limit':180,'threads':2,'gpu_authorized':False,'tensor_payload_access_authorized':'only after exact within-scope manifests/declaration/code frozen','max_native_containers':8,'max_encoded_bytes':67108864,'max_zip_or_storage_bytes':134217728,'video_image_decode_authorized':False,'tasks':[0,1],'decision_id':'e0:d3:s16','max_plans':34,'automatic_retry_authorized':False,'extra_simulator_steps':0,'registered_at':now}
 state.update(current_cpu_task=task,next_action='Screen all rows of the two fixed decision16 final pools for declared frozen-current-frame point-alignment differences; no extra scoring/simulation or GPU. Use result to decide whether a concrete QD/ED proxy candidate is justified.',updated_at=now)
 state['study']['status']='N30_FIXED_HANDOFF_CANDIDATE_ALIGNMENT_SCREEN_TARGET_NOT_MET'
 cp.update(status=state['study']['status'],phase='DISPATCH_CPU',in_flight_executor=task,in_flight_executors=[task],inflight_executor=task,inflight_executors=[task],executor_task=task,next_action=state['next_action'],automatic_gpu_dispatch_authorized=False,automatic_gpu_dispatch_scope=None,updated_at=now,goal_achieved=False,target_achieved=False,target_met=False)
 tree['meta'].update(study_status=state['study']['status'],target_achieved=False,automatic_dispatch_authorized=False)
 a.node(tree,'14.1')['post_rejection_geometry_review']=ref(G/'root-terminal-review-v1.json')
 assert state['budget']==budget and state['worktree']==lex
 tmp=W/'research-state.yaml.n30-pool-v1'
 with tmp.open('x') as f:yaml.safe_dump(state,f,sort_keys=False,allow_unicode=True);f.flush();os.fsync(f.fileno())
 os.replace(tmp,W/'research-state.yaml');r.durable_json(coord/'checkpoint.json',cp);a.save_tree(W,run,tree)
 note=f"\n### {now} — Calibrated point geometry accepted; bounded candidate-supply screen\n\nOne32-row JSON calculation exit0, childCPU{ext['children_cpu_seconds']}s/wall{ext['wall_seconds']}s. Root verified output/source refs, static robot-frame convention and process exit without numerical replay. Task0 longitudinal versus task1 lateral offsets; arbitrary old keypoint and local-source geometry do not establish object capture. N9 world-XY sweep differs from this hand-frame proxy. No GPU nomination or success evidence.\n\nNext: all16 final-pool candidates plus selected plan if distinct at decision16 in each of the same2 episodes; maximum8 bound native containers, one finite CPU calculation, no new scores/model/sim/GPU. Declare fixed-orientation/qpos proxy and all row/metric comparisons before native reads. Choose mechanism only after candidate-supply distinction; no fit or protection-budget change. Original Goal NOT_MET. Review {G/'root-terminal-review-v1.json'}; scope {Q/'root-scope-v1.md'}.\n"
 for p in [session/'REPORT.md',W/'docs/03_evidence/qd_ed_final/iteration-ledger.md']:
  with p.open('a') as f:f.write(note)
 r.durable_json(Q/'root-registration-v1.json',{'closed_task':old,'task':task,'budget_changed':False})
print(json.dumps({'review':ref(G/'root-terminal-review-v1.json'),'scope':ref(Q/'root-scope-v1.md'),'task':task['phase']}))
