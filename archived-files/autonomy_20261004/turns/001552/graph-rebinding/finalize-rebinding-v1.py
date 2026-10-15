import datetime as dt, hashlib, json, os, time
from pathlib import Path
OUT=Path(__file__).resolve().parent
START=dt.datetime.fromisoformat('2026-10-10T17:49:44+00:00')
def digest(p):
 p=Path(p);b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def read(p):return json.loads(Path(p).read_text())
def put(p,v):
 p=OUT/p
 with p.open('x') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n')
 return digest(p)
def boundary():
 now=dt.datetime.now(dt.timezone.utc)
 assert now<dt.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
 assert (now-START).total_seconds()<1200
 for p in ['/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/STOP','/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/STOP']:
  try:os.lstat(p)
  except FileNotFoundError:pass
  else:raise ValueError('STOP '+p)
boundary()
r=read(OUT/'attempt-4/report-v1.json');b5=read(OUT/'attempt-4/independent-b5-inputs-v1.json')
verified=[]
for name,ref in r['outputs'].items():
 actual=digest(ref['path']);assert actual==ref,(name,actual,ref);verified.append(actual)
for k,ref in r['roots'].items():assert digest(ref['path'])==ref,k
assert len(r['checks'])==110
assert [k for k,v in r['checks'].items() if not v['pass']]==['exact_candidate_controller_verify_semantics']
# Preserve this executor's early root-level failed artifacts byte-for-byte under explicit attempt names.
retained=[]
for name in ['report-v1.json','independent-b5-inputs-v1.json']:
 old=OUT/name;before=digest(old);new=OUT/name.replace('-v1.json','-attempt-1-v1.json')
 assert not new.exists();old.rename(new);after=digest(new);assert before['sha256']==after['sha256']
 retained.append({'original_location':before['path'],'retained':after})
for n in [2,3]:retained.append({'retained':digest(OUT/f'attempt-{n}/report-v1.json')})
for n in [1,2,3,4]:
 p=OUT/('rebind-graph-v1.py' if n==1 else f'rebind-graph-attempt-{n}-v1.py')
 r['inputs'].append(digest(p))
r['inputs'].append(digest(__file__))
finalcheck=put('artifact-final-check-v1.json',{'schema':'n36-graph-rebinding-final-check-v1','at':dt.datetime.now(dt.timezone.utc).isoformat(),'all_output_hashes_verified':True,'verified_outputs':verified,'roots':r['roots'],'check_count':110,'passed_checks':109,'failed_checks':1,'failed_check':'exact_candidate_controller_verify_semantics','graph_rebinding_complete':True,'controller_verifier_compatible':False,'candidate_controller_proof_unmodified':True,'b5_review':None,'release_enabled':False,'retained_attempts':retained})
b5.update(preparation_report=digest(OUT/'attempt-4/report-v1.json'),final_artifact_check=finalcheck,retained_attempts=retained,status='GRAPH_REBOUND_CONTROLLER_REFERENCE_SCHEMA_BLOCKED',required_next_action='Owner must resolve accepted controller proof reference-schema incompatibility and issue a new reviewed proof; rebind affected graph and obtain independent B5. This executor does not alter accepted proof or grant authority.')
b5ref=put('independent-b5-inputs-v1.json',b5)
r.update(status='DISABLED_GRAPH_REBOUND_CONTROLLER_REFERENCE_SCHEMA_BLOCKED',graph_rebinding_complete=True,controller_verifier_compatible=False,artifact_generation_report=digest(OUT/'attempt-4/report-v1.json'),retained_attempts=retained,finalized_at=dt.datetime.now(dt.timezone.utc).isoformat())
r['outputs']['artifact-final-check-v1.json']=finalcheck
r['outputs']['independent-b5-inputs-v1.json']=b5ref
r['budget']['total_preparation_wall_seconds']=(dt.datetime.now(dt.timezone.utc)-START).total_seconds()
r['next_step']=b5['required_next_action']
r['checks']['final_output_hashes']={'pass':True,'count':len(verified)}
r['checks']['final_stop_deadline_and_preparation_budget']={'pass':True}
boundary()
report=put('report-v1.json',r)
print(json.dumps({'report':report,'independent_b5_inputs':b5ref,'status':r['status'],'total_wall_seconds':r['budget']['total_preparation_wall_seconds']}))
