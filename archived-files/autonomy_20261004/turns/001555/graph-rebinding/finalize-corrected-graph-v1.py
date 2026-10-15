import datetime as dt, hashlib, json, os
from pathlib import Path
OUT=Path(__file__).resolve().parent
START=dt.datetime.fromisoformat('2026-10-10T17:57:41+00:00')
def digest(p):
 p=Path(p); b=p.read_bytes(); return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def read(p): return json.loads(Path(p).read_text())
def put(name,v):
 p=OUT/name
 with p.open('x') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n')
 return digest(p)
def boundary():
 now=dt.datetime.now(dt.timezone.utc)
 assert now<dt.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
 assert (now-START).total_seconds()<1200
 for p in [OUT.parents[2]/'STOP',Path('/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/STOP')]:
  try:os.lstat(p)
  except FileNotFoundError:pass
  else:raise ValueError('STOP '+str(p))
boundary()
r=read(OUT/'prepared/report-v1.json'); b=read(OUT/'prepared/independent-b5-inputs-v1.json'); a=read(OUT/'authority-v1.json')
assert r['status']=='PREPARATION_COMPLETE_PENDING_INDEPENDENT_B5' and not r['blockers']
assert all(c['pass'] for c in r['checks'].values())
verified=[]
for ref in r['outputs'].values():
 actual=digest(ref['path']); assert actual==ref;verified.append(actual)
for ref in r['roots'].values():assert digest(ref['path'])==ref
# Recheck every recorded preparation input for concurrent changes, including old artifacts.
for ref in r['inputs']:
 assert digest(ref['path'])==ref
assert r['roots']['controller_semantics']['sha256']==a['corrected_controller_proof']['sha256']=='294095fb64a1e3045de560ffc598f306aecc92f4e2577f363399d3277dae41b5'
assert r['checks']['all_active_controller_edges_refreshed']['count']==43
assert r['checks']['all_active_graph_reference_edges_hash_verified']['count']==470
assert sum(k.startswith('exact_manifest_') for k in r['checks'])==40
assert r['checks']['exact_engineering_manifest']['pass']
for obj in (r,b):assert obj['b5_review'] is None and obj['release_enabled'] is False and obj['source_adopted'] is False
boundary()
finalcheck=put('artifact-final-check-v1.json',{'schema':'n36-graph-rebinding-final-check-v1','at':dt.datetime.now(dt.timezone.utc).isoformat(),'all_output_hashes_verified':True,'verified_outputs':verified,'all_recorded_input_hashes_rechecked':True,'input_count':len(r['inputs']),'roots':r['roots'],'preparation_check_count':len(r['checks']),'passed_checks':len(r['checks']),'failed_checks':0,'controller_verifier_compatible':True,'b5_review':None,'release_enabled':False,'G7_dispatch':'VETO_UNCONDITIONAL','independent_B5_performed':False})
b.update(preparation_report=digest(OUT/'prepared/report-v1.json'),final_artifact_check=finalcheck,status='PREPARATION_COMPLETE_PENDING_INDEPENDENT_B5',required_next_action='Independent B5 on exact refreshed plan and graph roots. G7 unconditional dispatch veto, adoption, detached releases and actual readiness remain unresolved. No authority granted.')
bref=put('independent-b5-inputs-v1.json',b)
r.update(graph_rebinding_complete=True,controller_verifier_compatible=True,artifact_generation_report=digest(OUT/'prepared/report-v1.json'),finalized_at=dt.datetime.now(dt.timezone.utc).isoformat())
r['inputs'].append(digest(__file__))
r['outputs']['artifact-final-check-v1.json']=finalcheck
r['outputs']['independent-b5-inputs-v1.json']=bref
r['checks']['final_output_hashes']={'pass':True,'count':len(verified)}
r['checks']['final_recorded_input_hashes']={'pass':True,'count':len(r['inputs'])-1}
r['checks']['final_stop_deadline_and_preparation_budget']={'pass':True}
r['budget']['total_preparation_wall_seconds']=(dt.datetime.now(dt.timezone.utc)-START).total_seconds()
r['next_step']=b['required_next_action']
boundary()
rref=put('report-v1.json',r)
assert digest(bref['path'])==bref and digest(rref['path'])==rref
print(json.dumps({'report':rref,'independent_b5_inputs':bref,'status':r['status'],'checks':len(r['checks']),'budget':r['budget']}))
