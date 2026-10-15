"""Close fixed visual evidence; register a finite source/JSON geometry investigation."""
from pathlib import Path
import copy,datetime,hashlib,importlib.util,json,os,sys,time,yaml
V=Path(__file__).resolve().parent
P=V.parent
G=P/'capture-geometry-review-v1'
W=P.parents[1]/'study_worktree'
started=time.process_time()
def raw(p):
 p=Path(p)
 assert p.suffix not in {'.pt','.mp4'},str(p)
 return p.read_bytes()
def ref(p):return {'path':str(p),'sha256':hashlib.sha256(raw(p)).hexdigest()}
def put(p,x):
 with Path(p).open('x') as f:json.dump(x,f,indent=2);f.write('\n')
assert ref(V/'output-manifest-v1.json')['sha256']=='fbe1e077c66d9130de57f112fcd0ee1acce2d84c225e37b180c9ec78b0757dcd'
out=json.loads(raw(V/'output-manifest-v1.json'))
assert len(out['files'])==28
for q in out['files']:
 b=raw(q['path'])
 assert len(b)==q['bytes'] and hashlib.sha256(b).hexdigest()==q['sha256'],q['path']
assert sum(q['bytes'] for q in out['files'])==6206598
frames=json.loads(raw(V/'frames-manifest-v1.json'))['images']
assert [(q['task_id'],q['frame_index_zero_based']) for q in frames]==[(t,i) for t in [0,1] for i in [16,20,24,28,32,40]]
assert all(q['width']==q['height']==640 and q['pre_action_global_step_by_static_mapping']==q['frame_index_zero_based'] for q in frames)
res=json.loads(raw(V/'extraction-resource-v1.json'))
closure=json.loads(raw(V/'extraction-closure-v1.json'))
assert res['complete'] and res['error'] is None and res['image_exports_completed']==12
assert res['aggregate_parent_child_cpu_seconds']<120 and res['external_work_wall_seconds']<120
assert res['affinity']==[0,1] and res['threads_environment']==2
assert res['cuda_visible_devices']=='' and res['ffmpeg_hardware_acceleration']=='none'
assert res['automatic_retries']==0 and res['explicit_gpu_calls']==0
for c in res['commands']:
 assert c['exit_code']==0 and not (Path('/proc')/str(c['pid'])).exists()
assert closure['decoder_invocations']==closure['headers_only_probe_invocations']==2
assert all(d['frames_decoded']==44 and d['frames_exported']==6 and d['packets_read']==46 and d['exit_code']==0 for d in closure['decoder_details'])
review={'decision':'ACCEPT_FIXED_VIDEO_EXTRACTION_AND_BOUNDED_VISUAL_OBSERVATIONS','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'manifest':ref(V/'output-manifest-v1.json'),'frames':ref(V/'frames-manifest-v1.json'),'resource':ref(V/'extraction-resource-v1.json'),'observations':ref(V/'root-visual-observations-v1.md'),'verified_output_count':28,'verified_output_bytes':6206598,'root_native_tensor_or_encoded_video_reads':0,'root_viewed_exported_images':12,'all_overlay_steps_match':True,'all_recorded_processes_exited':True,'decoded_frames_each_video':44,'exported_frames_each_video':6,'cpu_seconds':res['aggregate_parent_child_cpu_seconds'],'wall_seconds':res['external_work_wall_seconds'],'administrative_packaging_assertion_failure_preserved':True,'finding':'Task0 can not visibly carried in selected samples; task1 capture/contact unresolved due occlusion. No causal handoff or grasp label inferred.','next_scope':ref(G/'root-scope-v1.md'),'goal_achieved':False,'root_review_cpu_seconds':time.process_time()-started}
put(V/'root-terminal-review-v1.json',review)
sys.path[:0]=[str(W),str(W/'scripts')]
from scripts import qd_ed_final_runner as r
sp=importlib.util.spec_from_file_location('arbor_state','/home/hynx/.codex/skills/arbor-agent-tools/scripts/arbor_state.py')
a=importlib.util.module_from_spec(sp);sp.loader.exec_module(a)
run='rdt-qd-ed-final-20260921T093925Z'
session=W/'.arbor/sessions'/run
coord=session/'.coordinator'
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
with r.locked(W/'data/qd-ed-state.lock'),a.state_lock(W,run):
 state=r.read_state(W/'research-state.yaml');cp=r.read_json(coord/'checkpoint.json');tree=a.load_tree(W,run)
 assert state['resource_isolation']['status']=='ACTIVE' and state['resource_isolation']['validation_status']=='PASS'
 assert state['current_cpu_task']['phase']=='N30_EXISTING_VIDEO_PREFIX_EXTRACTION'
 assert state['current_owned_workers']==[] and state['active_controller'] is None and state['active_plan'] is None
 budget=copy.deepcopy(state['budget']);lex=state['worktree']
 snap=G/'registration-before-v1';snap.mkdir(exist_ok=False)
 for n,obj in [('state',state),('checkpoint',cp),('tree',tree)]:r.durable_json(snap/(n+'.json'),obj)
 old=copy.deepcopy(state['current_cpu_task'])
 old.update(status='COMPLETE_ACCEPTED_DESCRIPTIVE',closed_at=now,review=ref(V/'root-terminal-review-v1.json'),video_allowance_exhausted=True,cpu_seconds=res['aggregate_parent_child_cpu_seconds'],wall_seconds=res['external_work_wall_seconds'])
 state.setdefault('closed_cpu_tasks',{})[old['phase']]=old
 task={'status':'DISPATCHED','phase':'N30_CAPTURE_GEOMETRY_SOURCE_AND_FIXED_JSON','node_id':'14.1','agent':'/root/n22_cpu_executor','scope':ref(G/'root-scope-v1.md'),'source_base':'6292fc8cffad2eec0f789e023d835ad3c1df146a','preceding_review':ref(V/'root-terminal-review-v1.json'),'cpu_seconds_limit':60,'wall_seconds_limit':180,'threads':2,'gpu_authorized':False,'tensor_payload_access_authorized':False,'video_image_decode_authorized':False,'existing_json_outcomes':32,'automatic_retry_authorized':False,'extra_simulator_steps':0,'registered_at':now}
 state.update(current_cpu_task=task,next_action='Establish calibrated gripper-frame source contract, then one declared fixed-JSON geometry calculation if supported; nominate at most one substantive QD/ED mechanism. No GPU or new data.',updated_at=now)
 state['study']['status']='N30_CAPTURE_GEOMETRY_FEASIBILITY_TARGET_NOT_MET'
 cp.update(status=state['study']['status'],phase='DISPATCH_CPU',in_flight_executor=task,in_flight_executors=[task],inflight_executor=task,inflight_executors=[task],executor_task=task,next_action=state['next_action'],automatic_gpu_dispatch_authorized=False,automatic_gpu_dispatch_scope=None,updated_at=now,goal_achieved=False,target_achieved=False,target_met=False)
 tree['meta'].update(study_status=state['study']['status'],target_achieved=False,automatic_dispatch_authorized=False)
 a.node(tree,'14.1')['post_rejection_visual_review']=ref(V/'root-terminal-review-v1.json')
 assert state['budget']==budget and state['worktree']==lex
 tmp=W/'research-state.yaml.n30-geometry-v1'
 with tmp.open('x') as f:yaml.safe_dump(state,f,sort_keys=False,allow_unicode=True);f.flush();os.fsync(f.fileno())
 os.replace(tmp,W/'research-state.yaml');r.durable_json(coord/'checkpoint.json',cp);a.save_tree(W,run,tree)
 note=f"\n### {now} — Fixed visual evidence accepted; calibrated geometry investigation\n\nRoot verified28 output hashes and inspected12 fixed frames. Task0 can remains on surface in selected frames as hand lifts; task1 capture remains occluded/Unknown. Overlay timing reconciled; FAIL overlay not used as per-frame evidence. Both video decoders exited0,44frames decoded/6exported each; CPU{res['aggregate_parent_child_cpu_seconds']}s, wall{res['external_work_wall_seconds']}s; packaging assertion preserved. No new video/tensor read by root.\n\nNext finite CPU scope: local robot/gripper coordinate contract and one declared calculation over the existing32 outcomes, only if supported. No generic replay framework, GPU, new simulation or budget change. At most one QD/ED mechanism nomination; no new candidate yet. Original Goal NOT_MET. Review {V/'root-terminal-review-v1.json'}; scope {G/'root-scope-v1.md'}.\n"
 for p in [session/'REPORT.md',W/'docs/03_evidence/qd_ed_final/iteration-ledger.md']:
  with p.open('a') as f:f.write(note)
 r.durable_json(G/'root-registration-v1.json',{'closed_task':old,'task':task,'budget_changed':False})
print(json.dumps({'review':ref(V/'root-terminal-review-v1.json'),'scope':ref(G/'root-scope-v1.md'),'task':task['phase']}))
