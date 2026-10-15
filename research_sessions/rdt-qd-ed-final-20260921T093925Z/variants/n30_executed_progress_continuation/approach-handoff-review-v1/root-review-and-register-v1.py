"""Independent metadata delivery review and finite preparation registration; no payload reads."""
from pathlib import Path
import copy,datetime,hashlib,importlib.util,json,os,subprocess,sys,time,yaml
C=Path(__file__).resolve().parent;H=C/'decode-v1';P=C.parent;W=P.parents[1]/'study_worktree'
started=time.process_time();reads={}
def read(p):
 p=Path(p);assert p.suffix not in {'.pt','.mp4','.png','.jpg'},str(p)
 b=p.read_bytes();reads[str(p)]={'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)};return b
def ref(p):
 p=Path(p);b=read(p);return {'path':str(p),'sha256':hashlib.sha256(b).hexdigest()}
def check(q):
 b=read(q['path']);assert hashlib.sha256(b).hexdigest()==q['sha256'],q['path']
 if 'bytes' in q:assert len(b)==q['bytes'],q['path']
 return b
delivery=json.loads(read(C/'delivery-manifest-v1.json'))
assert reads[str(C/'delivery-manifest-v1.json')]['sha256']=='50ad75ff338977019802a16d2257e1975c4d6bb7d065513efd9662f86f95edae'
for q in delivery['files']:check(q)
inputs=json.loads(read(C/'input-source-manifest-v1.json'))
for q in inputs['reads']:check(q)
bindings=json.loads(read(C/'handoff-bindings.disabled.v1.json'))
assert not bindings['executable'] and not bindings['tensor_decode_authorized']
assert [e['cell']['task_id'] for e in bindings['episodes']]==[0,1]
files=[]
for e in bindings['episodes']:
 census=e['complete_decision_census']
 assert len(census)==90 and [r['step'] for r in census]==list(range(0,720,8))
 guided=[r['step'] for r in census if r['event_counts'].get('canonical_candidate_batch',0)]
 assert guided==e['metric_steps']
 first=next((a['step'],b['step']) for a,b in zip(census,census[1:]) if a['event_counts'].get('canonical_candidate_batch',0)>0 and b['event_counts'].get('canonical_candidate_batch',0)==0)
 assert first==(16,24)
 for pair in e['first_realized_eds_handoff']:
  d=pair['decision'];assert d['reset_sequence']==0
  assert [r['step'] for r in pair['ordered_actual_feedback']]==list(range(d['step'],d['step']+8))
 assert len(e['containers'])==34
 for q in e['containers']:
  stat=Path(q['path']).stat()
  assert stat.st_size==q['stat_bytes'] and q['existing_index_sha256']==q['existing_receipt_sha256']
  assert stat.st_ino==q['stat_identity']['inode'] and stat.st_mtime_ns==q['stat_identity']['mtime_ns']
  assert not q['payload_hash_measured']
  files.append(q)
assert len({q['path'] for q in files})==68 and sum(q['stat_bytes'] for q in files)==24429984
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=W,text=True).strip()=='6292fc8cffad2eec0f789e023d835ad3c1df146a'
resource=json.loads(read(C/'resource-summary-v1.json'))
assert resource['payload_opens']==resource['payload_decodes']==resource['payload_hash_measurements']==0
assert resource['accounted_budget_seconds_upper_charge']<300 and resource['external_read_bytes_including_repeats']<64*1024**2
review={'decision':'ACCEPT_METADATA_STATIC_REVIEW','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'delivery':ref(C/'delivery-manifest-v1.json'),'report':ref(C/'review-v1.md'),'proposal':ref(C/'minimum-evidence-proposal.disabled.v1.json'),'bindings':ref(C/'handoff-bindings.disabled.v1.json'),'verified_output_refs':len(delivery['files']),'verified_input_refs':len(inputs['reads']),'root_read_set':reads.copy(),'root_review_cpu_seconds':time.process_time()-started,'payload_stats':68,'payload_stat_bytes':24429984,'payload_reads_hashes_decodes':0,'findings':'Both full90-decision census and all metrics bind first realized EDS-to-nonEDS step16->24; no Stage cause, grasp or new algorithm claim. Select one tensor evidence route.','next':'Decoder preparation only; execution requires frozen source review.','goal_achieved':False}
with (C/'root-terminal-review-v1.json').open('x') as f:json.dump(review,f,indent=2);f.write('\n')
sys.path[:0]=[str(W),str(W/'scripts')]
from scripts import qd_ed_final_runner as r
spec=importlib.util.spec_from_file_location('arbor_state','/home/hynx/.codex/skills/arbor-agent-tools/scripts/arbor_state.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
now=datetime.datetime.now(datetime.timezone.utc).isoformat();run='rdt-qd-ed-final-20260921T093925Z';session=W/'.arbor/sessions'/run;coord=session/'.coordinator'
with r.locked(W/'data/qd-ed-state.lock'),a.state_lock(W,run):
 state=r.read_state(W/'research-state.yaml');cp=r.read_json(coord/'checkpoint.json');tree=a.load_tree(W,run)
 assert state['current_cpu_task']['phase']=='N30_APPROACH_HANDOFF_METADATA_REVIEW'
 assert state['active_controller'] is None and state['current_owned_workers']==[] and state['active_iteration'] is None
 budget=copy.deepcopy(state['budget']);lexical=state['worktree']
 snap=H/'registration-before-v1';snap.mkdir(exist_ok=False)
 for n,obj in [('state',state),('checkpoint',cp),('tree',tree)]:r.durable_json(snap/(n+'.json'),obj)
 prev=copy.deepcopy(state['current_cpu_task']);prev.update(status='COMPLETE_ACCEPTED_METADATA',closed_at=now,review=ref(C/'root-terminal-review-v1.json'),payload_open_hash_decode_count=0)
 state.setdefault('closed_cpu_tasks',{})[prev['phase']]=prev
 task={'status':'DISPATCHED','phase':'N30_HANDOFF_DECODER_PREPARATION','node_id':'14.1','agent':'/root/n22_cpu_executor','scope':ref(H/'root-preparation-scope-v1.md'),'bindings':ref(C/'handoff-bindings.disabled.v1.json'),'source_base':'6292fc8cffad2eec0f789e023d835ad3c1df146a','cpu_seconds_limit':300,'threads':2,'gpu_authorized':False,'tensor_payload_access_authorized':False,'video_image_decode_authorized':False,'registered_at':now}
 state.update(current_cpu_task=task,next_action='Prepare and review a bounded one-shot reader for fixed N30 step16->24 handoffs, then execute existing-data diagnosis within scope; no GPU or new algorithm yet. Continue active Goal.',updated_at=now)
 state['study']['status']='N30_HANDOFF_DECODER_PREPARATION_TARGET_NOT_MET'
 cp.update(status=state['study']['status'],phase='DISPATCH_CPU',in_flight_executor=task,in_flight_executors=[task],inflight_executor=task,inflight_executors=[task],executor_task=task,next_action=state['next_action'],automatic_gpu_dispatch_authorized=False,automatic_gpu_dispatch_scope=None,updated_at=now,goal_achieved=False,target_achieved=False,target_met=False)
 tree['meta'].update(study_status=state['study']['status'],target_achieved=False,automatic_dispatch_authorized=False)
 a.node(tree,'14.1')['post_rejection_handoff_metadata_review']=ref(C/'root-terminal-review-v1.json')
 assert state['budget']==budget and state['worktree']==lexical
 tmp=W/'research-state.yaml.n30-handoff-prep-tmp'
 with tmp.open('x') as f:yaml.safe_dump(state,f,sort_keys=False,allow_unicode=True);f.flush();os.fsync(f.fileno())
 os.replace(tmp,W/'research-state.yaml');r.durable_json(coord/'checkpoint.json',cp);a.save_tree(W,run,tree)
 note=f"\n### {now} — N30 handoff metadata accepted; bounded reader preparation\n\nBoth accepted N30 episodes first switch from realized EDS at16 to nonEDS at24, with complete recorded actual steps16..31. Root verified13 output refs,34 input refs,90-decision census/metrics each and68 container stats (24429984bytes), without payload reads. Missing Stage cause, grasp and target semantics remainUnknown; no new algorithm yet. One tensor route selected; preparation only, no execution release or GPU. Caps578/100 and protected reserves unchanged; original Goal NOT_MET. Review {C/'root-terminal-review-v1.json'}, scope {H/'root-preparation-scope-v1.md'}.\n"
 for p in [session/'REPORT.md',W/'docs/03_evidence/qd_ed_final/iteration-ledger.md']:
  with p.open('a') as f:f.write(note)
 r.durable_json(H/'root-registration-v1.json',{'at':now,'closed_cpu_task':prev,'task':task,'budget_changed':False,'goal_active':True})
print(json.dumps({'review':ref(C/'root-terminal-review-v1.json'),'scope':ref(H/'root-preparation-scope-v1.md'),'task':task}))
