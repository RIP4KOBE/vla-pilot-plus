import json, hashlib, time, resource
from pathlib import Path
from collections import Counter
resource.setrlimit(resource.RLIMIT_CPU,(60,60))
t0=time.monotonic(); c0=time.process_time()
p=Path(__file__).parent
scope=json.loads((p/'scope-v1.json').read_text()); rows=[]
for task in range(6):
 for profile in ['Q0','N31']:
  files=[i for i in scope['inputs'] if i['task_id']==task and i['profile']==profile]
  loaded={}
  for i in files:
   b=Path(i['path']).read_bytes(); assert len(b)==i['bytes'] and hashlib.sha256(b).hexdigest()==i['sha256']
   loaded[Path(i['path']).name]=b
  audit=json.loads(loaded['decision-evidence-audit.json']);assert audit['accepted']
  metrics=[json.loads(x) for x in loaded['eds_metrics.jsonl'].splitlines() if x.strip()]
  native=audit['n31_capture_dwell_audit'];assert len(metrics)==native['guided_decisions']
  row={'task_id':task,'profile':profile,'success':False,'guided_decisions':len(metrics),'native_counts':native}
  if profile=='N31':
   scalars=[m['capture_dwell_proposal'] for m in metrics]
   reasons=Counter(r for s in scalars for r in s['reasons'])
   assert sum(s['opportunities'] for s in scalars)==native['opportunities_verified']
   assert sum(s['changed'] for s in scalars)==native['changed_proposals_verified']
   assert sum(reasons.values())==native['opportunities_verified']
   row.update(reasons=dict(reasons),decisions_with_changes=sum(s['changed']>0 for s in scalars),changed_decisions=[{'global_step':m['global_step'],'changed':m['capture_dwell_proposal']['changed'],'reasons':m['capture_dwell_proposal']['reasons']} for m in metrics if m['capture_dwell_proposal']['changed']>0])
  rows.append(row)
assert time.monotonic()-t0<120
result={'schema':'n31-posthoc-json-summary-v1','scope_sha256':hashlib.sha256((p/'scope-v1.json').read_bytes()).hexdigest(),'source':scope['source'],'rows':rows,'cpu_seconds':time.process_time()-c0,'wall_seconds':time.monotonic()-t0,'physical_capture':'Unknown','actual_close_dwell_timing':'Unknown from aggregate receipt/scalars; requires bounded native event review','target_motion':'Unknown','is_new_evaluation':False}
(p/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
for r in rows:print(r['task_id'],r['profile'],r['guided_decisions'],r.get('reasons'),r['native_counts']['selected_proposal_content_decisions'])
print('CPU',result['cpu_seconds'],'wall',result['wall_seconds'])
