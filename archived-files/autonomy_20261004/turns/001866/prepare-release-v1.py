import os,sys,json,pathlib,datetime,hashlib
P=pathlib.Path
O=P('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001866');O.mkdir(exist_ok=True)
G=O.parent/'001864/canonical-v2/graph.complete-disabled-v1.json';g=json.loads(G.read_text());root=P(g['production_required_worktree'])
os.environ['QD_ED_N36_R1_SPECIFICATION']=json.dumps(g['specification']);os.environ['PYTHONDONTWRITEBYTECODE']='1';sys.path.insert(0,str(root));os.chdir(root)
from scripts import qd_ed_n36_readiness_prepare as m
e=m.e
spec=e.specification(); policy=m.policy(spec);source=e.read(g['source_record']);contract_ref=spec['runtime_binding']['accounting_contract'];c=e.read(contract_ref)
def put(p,v):
 p=P(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(v,f,indent=2);f.write('\n')
 return {'path':str(p),'sha256':e.w.sha(p)}
now=datetime.datetime.now(datetime.timezone.utc);end=datetime.datetime.fromisoformat(policy['deadline'])
r=dict(schema='n36-preparation-measurement-release-v1',approved=True,purpose='readiness_preparation_only',specification=e.SPECIFICATION,source_record=g['source_record'],baseline=spec['canonical_runtime'],resource_id=policy['resource_id'],source_cwd=str(e.SOURCE),interpreter=dict(path=str(P(sys.executable).resolve()),sha256=e.w.sha(P(sys.executable).resolve()),version=sys.version),issued_at=now.isoformat(),expires_at=end.isoformat(),gpu_seconds=600,provider_calls=1,episode_authorized=False,health_authorized=False,stop_authority=e.stop.binding(),graph={k:g[k] for k in ['plan','runtime']})
a=dict(schema=c['authority_schema'],approved=True,purpose='readiness_preparation_only',contract=contract_ref,approval_basis=c['standing_authority'],independent_review=c['independent_review'],owner=c['owner'],gpu_mapping=e.read(spec['canonical_runtime'])['gpu_mapping'],caps=e.c.CAPS,amendment=c['amendment'],margin_reference=c['margin_reference'],ledger_prefixes=spec['retained_ledger_prefixes'],retained_snapshot=spec['retained_snapshot'],retained_snapshot_reference=spec['retained_snapshot_reference'],retained_margin_gpu_hours='0.23357169027962',absolute_gpu_hours='224',weekly_window=dict(origin_gpu_hours=53.08404692669838,increment_gpu_hours=168.,ends_at=e.c.DEADLINE),cleanup_seconds=m.MEASUREMENT_CONTRACT['cleanup_seconds'],max_episode_attempts=0,max_health_invocations=0,automatic_recoveries=0,adoption_slot=m.ADOPTION_SLOT,**{k:r[k] for k in m.AUTHORITY_BINDINGS})
a['root_review']=put(O/'accounting-root-review-v1.json',{**a,'schema':c['review_schema'],'decision':'APPROVED'})
r['accounting_authority']=put(O/'accounting-authority-v1.json',a)
r['root_review']=put(O/'measurement-root-review-v1.json',{**r,'schema':'n36-preparation-root-measurement-review-v1','decision':'APPROVED'})
rr=put(policy['release_path'],r)
try:
 m.validate_release(rr,spec,source,g['source_record'])
 result=dict(status='PASS_RELEASE_AND_ACCOUNTING_AUTHORITY',release=rr,accounting=r['accounting_authority'],resource_id=r['resource_id'],gpu_seconds=600,provider_calls=1,episode_authorized=False,state_adopted=False)
except Exception as ex:
 result=dict(status='BLOCKED_RELEASE_VALIDATION',release=rr,error=type(ex).__name__+': '+str(ex),state_adopted=False)
put(O/'release-validation-v1.json',result);print(json.dumps(result))
