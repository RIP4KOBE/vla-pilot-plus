"""Root review of frozen CPU result and closure; no tensor replay."""
from pathlib import Path
import json,hashlib,time,collections,datetime,math
B=Path(__file__).resolve().parent;D=B.parent;T=time.process_time();reads=[]
def read(p,sha=None):
 p=Path(p);assert p.suffix in {'.json','.jsonl','.py','.md','.log'};b=p.read_bytes();h=hashlib.sha256(b).hexdigest()
 if sha:assert h==sha,(str(p),h)
 reads.append({'path':str(p),'sha256':h,'bytes':len(b)});return b
def j(p,sha=None):return json.loads(read(p,sha))
def ref(p):return {'path':str(p),'sha256':hashlib.sha256(read(p)).hexdigest()}
m=j(B/'execution-output-manifest-v1.json','c789da3a23b9bccc51af2a364e688e8a367f51ac522a8d3e23be35e6a7b9642d')
for f in m['files']:assert len(read(f['path'],f['sha256']))==f['bytes']
result=j(B/'result-v1.json');resource=j(B/'resource-v1.json');closure=j(B/'closure-v1.json');release=j(B/'root-execution-release-v1.json')
read(release['reader']['path'],release['reader']['sha256'])
bindings=j(release['input_bindings']['path'],release['input_bindings']['sha256'])
assert closure['exit_code']==0 and closure['execution_count']==1 and resource['error'] is None
assert resource['complete'] and result['complete'] and [e['task_id'] for e in result['episodes']]==[0,1]
assert resource['cpu_seconds']<120 and closure['tool_reported_outer_wall_seconds']<120 and resource['cuda_initialized'] is False
assert resource['affinity']==[0,1] and resource['threads']==2 and resource['peak_rss_kib']*1024<16*1024**3
assert resource['zip_uncompressed_bytes']<128*1024**2 and resource['decoded_cpu_storage_bytes']<128*1024**2
assert not Path('/proc/'+str(resource['pid'])).exists(),'reported original CPU pid still exists: inspect before closure'
payloads={c['path']:c for e in bindings['episodes'] for c in e['containers']}
actual=[x for x in resource['reads'] if x['kind']=='payload'];assert len(actual)==len(payloads)==34
assert len({x['path'] for x in actual})==34 and sum(x['bytes'] for x in actual)==24273690
for x in actual:
 c=payloads[x['path']];assert x['bytes']==c['stat_bytes'] and x['sha256']==c['existing_index_sha256']
 assert x['load_invocations']==x['filesystem_opens']==resource['payload_open_counts'][x['path']]==1 and x['decode_succeeded'] is True
progress=[json.loads(x) for x in read(B/'progress-v1.jsonl').splitlines()];assert progress==actual
denied=resource['denied_probes'];assert len(denied)==2 and resource['guard_clean'] is False
foreign='/home/hynx/VLA-Pilot++/.worktrees/feat/rdt-libero-gt-rollout-reintegration/third_party/lerobot/src'
assert {d['path'] for d in denied}=={foreign} and {d['event'] for d in denied}=={'open','os.listdir'}
assert foreign not in resource['dependency_opens'] and foreign not in resource['dependency_scans']
summaries=[]
for e in result['episodes']:
 assert all(e[k] is True for k in ['insertion_content_verified','canonical_initial_row15_verified','other15_and_fresh_tail_verified'])
 assert e['canonical_rows']==176 and e['native_dtype']=='torch.bfloat16'
 assert [r['iteration'] for r in e['parent_rounds']]==list(range(10))
 for r in e['parent_rounds']:
  ms=r['source_occurrence_matches'];assert [x['slot'] for x in ms]==list(range(16))
  assert all(len(x['matching_occurrences'])==1 for x in ms)
  assert dict(collections.Counter(x['ancestry']['class'] for x in ms))==r['content_match_class_counts']
  assert sum('warm' in x['ancestry']['possibilities'] for x in ms)==r['warm_possible_slots']
 f=e['final'];assert f['selected_ancestry']=={'class':'unique_content_supported_nonwarm','possibilities':['nonwarm']}
 assert f['committed8_bound_to_selected'] and not f['selected_direct_inserted_content'] and f['archive_unmatched_rows']==0 and f['archive_direct_inserted_content_rows']==0
 assert len(f['selected_content_matching_occurrences'])==1
 fs=e['feedback'];assert [r['step'] for r in fs]==list(range(8,16))
 for r in fs:
  assert r['command_gripper']==-1. and not r['terminal_or_truncated']
  assert math.isclose(e['start_distance_to_fixed_step8_target_m']-r['eef_distance_to_fixed_step8_target_m'],r['approach_from_step8_start_m'],abs_tol=1e-14)
 direct=[r['direct_inserted_content_slots'] for r in e['parent_rounds']]
 warm=[r['warm_possible_slots'] for r in e['parent_rounds']]
 expected=[1,1]+[0]*8 if e['task_id']==0 else [0]*10
 assert direct==warm==expected
 summaries.append({'task_id':e['task_id'],'direct_parent_slots_by_round':direct,'warm_content_supported_slots_by_round':warm,'final':f,'start_distance_m':e['start_distance_to_fixed_step8_target_m'],'end_distance_m':fs[-1]['eef_distance_to_fixed_step8_target_m'],'approach_m':fs[-1]['approach_from_step8_start_m'],'all8_gripper_commands':-1.0})
review={'schema':'n30-lineage-root-terminal-review-v1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'decision':'ACCEPT_BOUNDED_DESCRIPTIVE_DIAGNOSTIC','result':ref(B/'result-v1.json'),'resource':ref(B/'resource-v1.json'),'closure':ref(B/'closure-v1.json'),'delivery':ref(B/'execution-output-manifest-v1.json'),'release':ref(B/'root-execution-release-v1.json'),'summary':ref(B/'summary-v1.md'),'root_review_correction':ref(B/'root-decoder-review-addendum-v1.json'),
 'episodes':summaries,'payload_files_read_once':34,'payload_bytes':24273690,'cpu_seconds':resource['cpu_seconds'],
 'guard_clean':False,'denied_foreign_dependency_probes':2,'reported_cpu_process_exited':True,
 'root_independent_checks':['8 output hashes/source/release binding','34 exact hash/byte/load records reconciled to frozen inventory and progress journal','20round per-slot classifications/counts and16scalar feedback rows internally reconcile','resource bound and originalpidabsence','blocked foreign probes retained; no successful access recorded'],
 'inherited_numerical_evidence':'Standalone frozen CPU decoder instrumented native-content/lineage/decode/actual-feedback checks; root did not deserialize tensors again.',
 'prior_root_metadata_review_failure':{'script':'root-review-result-v1.py','error':'KeyError: loads; actual frozen resource field is load_invocations with separate decode_succeeded','payload_reads':0,'cpu_seconds':'unmeasured; immediate schema failure'},'root_tensor_read_decode_count':0,'root_review_cpu_seconds':time.process_time()-T,'reads':reads,
 'interpretation':'At these2first-active decisions, neither final selected action is uniquely traced through the inserted row as direct/single-parent ancestor. Task0 inserted row was allocated in first2rounds; task1 no actual parent allocation. Actual chosen prefixes still approach fixed snapshots. This does not justify forced retention or identify the eventual failure cause.',
 'limitations':['Only2of18active insertions','original archive insertion occurrence absent','QD/ED population coupling may affect nonwarm descendants','unexecuted physical outcomes unknown','fixed snapshot distance/gripper command is not grasp or task success','old eligibility/native validity inherited; no score/model/physics replay'],
 'next_direction':'Locate where approach-to-execution progress subsequently fails using bounded already-exposed evidence; no automatic rescue candidate. Originalgoal active, protected phases closed, caps578/100 unchanged.',
 'new_algorithm_authorized':False,'new_gpu_authorized':False,'target_met':False}
with (B/'root-terminal-review-v1.json').open('x') as f:json.dump(review,f,indent=2);f.write('\n')
print(json.dumps({k:v for k,v in review.items() if k not in ['reads','episodes']}))

