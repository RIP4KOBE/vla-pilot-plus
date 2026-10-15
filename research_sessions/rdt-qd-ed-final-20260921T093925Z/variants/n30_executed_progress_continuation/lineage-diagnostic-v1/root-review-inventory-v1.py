"""Independent root metadata review; no tensor reads/imports."""
from pathlib import Path
import json,hashlib,time,os,collections,datetime
os.sched_setaffinity(0,{0,1})
T=time.process_time();D=Path(__file__).resolve().parent;READS=[];CACHE={}
def read(p,expected=None):
 p=Path(p);assert p.suffix in {'.json','.jsonl','.md','.py','.csv','.log'}
 if str(p) not in CACHE:
  b=p.read_bytes();assert len(b)<32*1024**2
  CACHE[str(p)]=b;READS.append({'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
 b=CACHE[str(p)]
 if expected:assert hashlib.sha256(b).hexdigest()==expected,(str(p),'hash')
 return b
def j(p,sha=None):return json.loads(read(p,sha))
def ref(p):return {'path':str(p),'sha256':hashlib.sha256(read(p)).hexdigest()}
delivery=j(D/'delivery-manifest-v1.json','c3b008aae2bf66dac545740d09aa8d4071571971d0ece83496cc0087f0c43340')
for f in delivery['files']:
 assert Path(f['path']).parent==D
 b=read(f['path'],f['sha256']);assert len(b)==f['bytes']
bindings=j(D/'input-bindings.disabled.v1.json')
assert bindings['executable'] is False and bindings['payload_read_authorized'] is False
assert bindings['limits']==dict(episodes=2,decisions=2,containers=34,container_bytes=24273690,loads_per_container=1)
L=D.parent/'feedback-repair-continuation-v1'
terminal=j(L/'root-terminal-review-v1.json','0a840aebc3e63fd3f9940b0bd51b042fb471385e6522a74493c916b7b8c39f91')
assert terminal['decision']=='REJECT_NUMERIC_DEV_FUTILITY'
source=j(bindings['source']['path'],bindings['source']['sha256'])
plan=j(bindings['plan']['path'],bindings['plan']['sha256'])
result=j(bindings['result']['path'],bindings['result']['sha256'])
summary=[]
for e in bindings['episodes']:
 cell=e['cell'];out=Path(cell['attempt_result']['path']).parent
 ar=j(cell['attempt_result']['path'],cell['attempt_result']['sha256'])
 wr=j(cell['worker_receipt']['path'],cell['worker_receipt']['sha256'])
 ctx=j(cell['worker_context']['path'],cell['worker_context']['sha256'])
 assert wr['accepted'] is True and wr['profile']==ctx['profile']=='N30'
 assert wr['source']==ctx['source']==source and wr['plan']==ctx['plan']==bindings['plan']
 assert ar['identity']['task_id']==cell['task_id'] and ar['identity']['profile']=='N30'
 metricref=wr['n30_metrics']
 metrics=[json.loads(x) for x in read(out/'eds_eval/eds_metrics.jsonl',metricref['sha256']).splitlines() if x]
 active=[m for m in metrics if m.get('executed_progress_continuation',{}).get('active') is True]
 assert active and min(m['global_step'] for m in active)==e['global_step']==8
 ix=[json.loads(x) for x in read(e['index_ref']['path'],e['index_ref']['sha256']).splitlines() if x]
 wanted={x['bundle']:x for x in ix if any(v['decision_id']==e['decision_id'] and v['event'] in e['requested_event_kinds'] for v in x['events'])}
 assert set(wanted)=={Path(x['path']).name for x in e['containers']}
 for c in e['containers']:
  p=Path(c['path']);assert not p.is_symlink() and not p.parent.is_symlink()
  st=p.stat();assert st.st_size==c['stat_bytes']
  assert (st.st_dev,st.st_ino,st.st_mtime_ns)==tuple(c['stat_identity'][k] for k in ['device','inode','mtime_ns'])
  x=wanted[p.name];assert x['sha256']==c['existing_index_sha256']==c['existing_receipt_sha256']
  assert x['events']==c['events']
  req=[v for v in x['events'] if v['decision_id']==e['decision_id'] and v['event'] in e['requested_event_kinds']]
  assert req==c['requested_events']
  assert dict(collections.Counter(v['event'] for v in x['events'] if v not in req))==c['co_resident_event_counts']
 summary.append({'task_id':cell['task_id'],'attempt_id':cell['attempt_id'],'decision_id':e['decision_id'],'first_active_step':8,'active_decisions':len(active),'containers':len(e['containers']),'bytes':sum(c['stat_bytes'] for c in e['containers'])})
assert [e['task_id'] for e in summary]==[0,1]
resource=j(D/'resource-v1.json')
assert resource['payload_opens']==resource['payload_hash_measurements']==resource['payload_decodes']==0
assert resource['conservative_combined_bytes']<128*1024**2
review={'schema':'n30-lineage-root-phase-a-review-v1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'decision':'ACCEPT_METADATA_INVENTORY','delivery':ref(D/'delivery-manifest-v1.json'),'bindings':ref(D/'input-bindings.disabled.v1.json'),'disabled_protocol':ref(D/'decode-protocol.disabled.v1.md'),'report':ref(D/'report-v1.md'),'episodes':summary,'independent_checks':['28 delivered refs hashes','two accepted source/plan/attempt identities','full metrics earliest-active rule','exact index requested/co-resident selection','selected34 payload paths STAT_ONLY'],'inherited':['original worker numerical/native source attestation','executor instrumented no-payload-read/resource claims; static reader reviewed'],'limitations':['archive origin occurrence missing; duplicated content remains ambiguous','direct ancestry is not total influence; QD/ED coupling possible','two first-active decisions only, not all18 active insertions','no counterfactual physical effect or efficacy inferred'],'root_tensor_open_hash_decode_count':0,'root_cpu_seconds':time.process_time()-T,'root_read_bytes':sum(x['bytes'] for x in READS),'reads':READS,'gpu_authorized':False,'payload_decode_authorized':False,'target_met':False}
with (D/'root-inventory-review-v1.json').open('x') as f:json.dump(review,f,indent=2);f.write('\n')
print(json.dumps({k:v for k,v in review.items() if k not in ['reads']}))

