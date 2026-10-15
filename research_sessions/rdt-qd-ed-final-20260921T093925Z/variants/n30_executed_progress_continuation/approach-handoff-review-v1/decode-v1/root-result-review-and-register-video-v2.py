"""Accept fixed handoff metadata result without native re-decode; dispatch existing-video check."""
from pathlib import Path
import copy,datetime,hashlib,importlib.util,json,os,sys,time,yaml
H=Path(__file__).resolve().parent;C=H.parent;P=C.parent;V=P/'handoff-visual-check-v1';W=P.parents[1]/'study_worktree';started=time.process_time()
def read(p):
 p=Path(p);assert p.suffix not in {'.pt','.mp4','.png','.jpg'},str(p);return p.read_bytes()
def ref(p):return {'path':str(p),'sha256':hashlib.sha256(read(p)).hexdigest()}
def check(q):
 b=read(q['path']);assert hashlib.sha256(b).hexdigest()==q['sha256'],q['path']
 if 'bytes' in q:assert len(b)==q['bytes']
def put(p,x):
 with Path(p).open('x') as f:json.dump(x,f,indent=2);f.write('\n')
assert ref(H/'output-manifest-v2.json')['sha256']=='0270c6aa87a3297ab79393fe5e5c3f72a0e6a824f1a1b07d1ce4eb25843b3317'
out=json.loads(read(H/'output-manifest-v2.json'))
for q in out['files']:check(q)
for k in ['reader','manual_authorization','scientific_release','preserved_failure_manifest']:check(out[k])
result=json.loads(read(H/'result-v1.json'));res=json.loads(read(H/'resource-v1.json'));ext=json.loads(read(H/'external-execution-v2.json'));bind=json.loads(read(C/'handoff-bindings.disabled.v1.json'))
assert result['complete'] and res['complete'] and res['error'] is None and ext['exit_code']==0 and ext['process_reaped']
assert res['pid']==ext['reader_process_identity']['pid']==3858764
for pid in [3856346,3858763,3858764]:assert not (Path('/proc')/str(pid)).exists()
assert ext['automatic_retries']==0 and ext['manual_launch_ordinal']==2
assert ext['external_wall_seconds_including_process_start_exit']<120 and ext['child_cpu_seconds_including_wrapper']<120
assert res['cpu_seconds']<120 and res['affinity']==[0,1] and res['threads']==2 and res['cuda_initialized'] is False
assert not res['guard_clean'] and len(res['denied_probes'])==2
assert {x['event'] for x in res['denied_probes']}=={'open','os.listdir'}
assert res['zip_uncompressed_bytes']<=64*1024**2 and res['decoded_cpu_storage_bytes']<=64*1024**2
expected={b['path']:b for ep in bind['episodes'] for b in ep['containers']}
actual=[r for r in res['reads'] if r['kind']=='payload']
assert len(actual)==len(expected)==68 and len({r['path'] for r in actual})==68
assert sum(r['bytes'] for r in actual)==24429984
for r in actual:
 e=expected[r['path']]
 assert r['sha256']==e['existing_index_sha256']==e['existing_receipt_sha256'] and r['bytes']==e['stat_bytes']
 assert r['filesystem_opens']==r['load_invocations']==1 and r['decode_succeeded']
assert res['payload_open_counts']=={p:1 for p in expected}
assert [e['task_id'] for e in result['episodes']]==[0,1]
for ep,be in zip(result['episodes'],bind['episodes']):
 assert ep['attempt_id']==be['cell']['attempt_id'] and ep['complete']
 assert [d['global_step'] for d in ep['decisions']]==[16,24]
 for d,bp in zip(ep['decisions'],be['first_realized_eds_handoff']):
  assert d['complete'] and d['decision_id']==bp['decision']['decision_id']
  assert [r['step'] for r in d['observed_steps']]==list(range(d['global_step'],d['global_step']+8))
  assert [r['command']['values'] for r in d['observed_steps']]==d['recorded_first8_commands']
  for row,ix in zip(d['observed_steps'],bp['ordered_actual_feedback']):
   assert row['event_sequences']['dispatch_index']==ix['action_dispatch']['sequence']
   for k in ['executed_action','pre_reset_outcome','step_returned']:assert row['event_sequences'][k]==ix[k]['sequence']
  assert d['stage']==d['previous_stage']==1 and not d['stage_changed']
 assert [d['use_guidance'] for d in ep['decisions']]==[True,False]
 assert [d['provider_count'] for d in ep['decisions']]==[1,0]
 assert ep['decisions'][1]['start24_vs_step23_outcome_native_equal']
manifest=json.loads(read(H/'decoder-source-manifest-v1.json'))
for q in manifest['scientific_source_files']:check(q)
review={'decision':'ACCEPT_BOUNDED_HANDOFF_DESCRIPTIVE_DIAGNOSTIC','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'result':ref(H/'result-v1.json'),'resource':ref(H/'resource-v1.json'),'output_manifest':ref(H/'output-manifest-v2.json'),'external_receipt':ref(H/'external-execution-v2.json'),'preserved_startup_failure':ref(H/'failure-output-manifest-v1.json'),'root_verified_output_refs':len(out['files']),'verified_payload_read_records':68,'payload_record_bytes':24429984,'verified_decisions':4,'verified_actual_steps':32,'root_native_payload_reads_hashes_decodes':0,'all_recorded_processes_exited':True,'child_cpu_seconds':ext['child_cpu_seconds_including_wrapper'],'external_wall_seconds':ext['external_wall_seconds_including_process_start_exit'],'guard_clean':False,'denied_probes':res['denied_probes'],'findings':['Both same Stage1 and tracked target identity, final guidance true->false/providers1->0. Original query disable cause remainsUnknown.','Task0 already withdrew30.385mm from fixed target during guided close prefix; later off-guidance open prefix withdrew18.985mm. Not a reversal first introduced by handoff.','Task1 approached34.211mm during guided open prefix; continued3.743mm after handoff, close starts29. Handoff did not universally interrupt approach.','No true grasp/contact, semantic target correctness, causal Stage fault or candidate benefit established.'],'next_decision':'Targeted native-frame inspection of same fixed handoffs to assess visible gripper/object alignment before nominating another QD/ED change.','root_metadata_review_v1_error':'TypeError joining two strings for /proc process check; v2 fixes Path construction only, no native payload read and no state/review output existed before error.','root_review_cpu_seconds':time.process_time()-started,'goal_achieved':False}
put(H/'root-terminal-review-v1.json',review)
sys.path[:0]=[str(W),str(W/'scripts')]
from scripts import qd_ed_final_runner as r
sp=importlib.util.spec_from_file_location('arbor_state','/home/hynx/.codex/skills/arbor-agent-tools/scripts/arbor_state.py');a=importlib.util.module_from_spec(sp);sp.loader.exec_module(a)
run='rdt-qd-ed-final-20260921T093925Z';session=W/'.arbor/sessions'/run;coord=session/'.coordinator';now=datetime.datetime.now(datetime.timezone.utc).isoformat()
with r.locked(W/'data/qd-ed-state.lock'),a.state_lock(W,run):
 state=r.read_state(W/'research-state.yaml');cp=r.read_json(coord/'checkpoint.json');tree=a.load_tree(W,run)
 assert state['current_cpu_task']['phase']=='N30_FIRST_HANDOFF_CPU_MANUAL_STARTUP_RECOVERY' and state['current_owned_workers']==[] and state['active_controller'] is None
 budget=copy.deepcopy(state['budget']);lex=state['worktree']
 snap=V/'registration-before-v1';snap.mkdir(exist_ok=False)
 for n,obj in [('state',state),('checkpoint',cp),('tree',tree)]:r.durable_json(snap/(n+'.json'),obj)
 old=copy.deepcopy(state['current_cpu_task']);old.update(status='COMPLETE_ACCEPTED_DESCRIPTIVE',closed_at=now,review=ref(H/'root-terminal-review-v1.json'),result=ref(H/'result-v1.json'),tensor_allowance_exhausted=True,child_cpu_seconds=ext['child_cpu_seconds_including_wrapper'],wall_seconds=ext['external_wall_seconds_including_process_start_exit'])
 state.setdefault('closed_cpu_tasks',{})[old['phase']]=old
 task={'status':'DISPATCHED','phase':'N30_EXISTING_VIDEO_PREFIX_EXTRACTION','node_id':'14.1','agent':'/root/n22_cpu_executor','scope':ref(V/'root-scope-v1.md'),'source_base':manifest['source_commit'],'preceding_review':ref(H/'root-terminal-review-v1.json'),'cpu_seconds_limit':120,'wall_seconds_limit':120,'threads':2,'gpu_authorized':False,'tensor_payload_access_authorized':False,'video_image_decode_authorized':True,'existing_video_count':2,'frame_indices_each':[16,20,24,28,32,40],'max_exported_frames':12,'automatic_retry_authorized':False,'extra_simulator_steps':0,'registered_at':now}
 state.update(current_cpu_task=task,next_action='Extract fixed12 native existing-video frames around first N30 handoffs; inspect visible geometry before nominating QD/ED change. No new simulation or GPU; original Goal active.',updated_at=now)
 state['study']['status']='N30_FIXED_HANDOFF_VISUAL_DIAGNOSIS_TARGET_NOT_MET'
 cp.update(status=state['study']['status'],phase='DISPATCH_CPU',in_flight_executor=task,in_flight_executors=[task],inflight_executor=task,inflight_executors=[task],executor_task=task,next_action=state['next_action'],automatic_gpu_dispatch_authorized=False,automatic_gpu_dispatch_scope=None,updated_at=now,goal_achieved=False,target_achieved=False,target_met=False)
 tree['meta'].update(study_status=state['study']['status'],target_achieved=False,automatic_dispatch_authorized=False)
 a.node(tree,'14.1')['post_rejection_handoff_diagnostic_review']=ref(H/'root-terminal-review-v1.json')
 assert state['budget']==budget and state['worktree']==lex
 tmp=W/'research-state.yaml.n30-video-v1'
 with tmp.open('x') as f:yaml.safe_dump(state,f,sort_keys=False,allow_unicode=True);f.flush();os.fsync(f.fileno())
 os.replace(tmp,W/'research-state.yaml');r.durable_json(coord/'checkpoint.json',cp);a.save_tree(W,run,tree)
 note=f"\n### {now} — Handoff diagnosis accepted; fixed existing-video evidence selected\n\nLaunch2 exit0,68 containers24429984bytes each one load/read,4 contexts/32actualsteps; childCPU2.347659s/externalwall2.233845076s. Root reconciled output hashes, fixed record hashes, exactstep/event/command metadata and all process exits without tensor reread. BothStage1, guidance true->false. Task0 already withdrew during guided close prefix and then opened; task1 continued approaching after handoff and closed at29. Does not support a universal handoff interruption/true-grasp or causalStage claim. Two denied foreign dependency probes retained; launch1 pre-invocation30CPU error preserved.\n\nNew evidence choice follows this result: exactlyframes16,20,24,28,32,40 from each of the same2 existingvideos, CPU extraction only; overlays/pixels unchanged, no newcamera/simulator/GPU. No newalgorithm yet. Caps578/100 and protected reserves unchanged; original Goal NOT_MET. Review {H/'root-terminal-review-v1.json'}, scope {V/'root-scope-v1.md'}.\n"
 for p in [session/'REPORT.md',W/'docs/03_evidence/qd_ed_final/iteration-ledger.md']:
  with p.open('a') as f:f.write(note)
 r.durable_json(V/'root-registration-v1.json',{'closed_task':old,'task':task,'budget_changed':False})
print(json.dumps({'review':ref(H/'root-terminal-review-v1.json'),'scope':ref(V/'root-scope-v1.md'),'task':task['phase']}))
