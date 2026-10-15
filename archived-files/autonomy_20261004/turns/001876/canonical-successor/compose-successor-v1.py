import os,sys,json,hashlib,copy,datetime,subprocess
from pathlib import Path
O=Path(__file__).resolve().parent;T=O.parent.parent;ROOT=Path.cwd().resolve();RID='n36_readiness_preparation_recovery_001876';COMMIT='808e27f702564fe51db45016e139b68ecb476f8c'
sys.dont_write_bytecode=True
os.environ.update(PYTHONDONTWRITEBYTECODE='1',CUDA_VISIBLE_DEVICES='',GIT_OPTIONAL_LOCKS='0',GIT_NO_LAZY_FETCH='1')
H=lambda b:hashlib.sha256(b).hexdigest()
def ref(p):
 p=Path(p).resolve();return dict(path=str(p),sha256=H(p.read_bytes()))
def read(r):
 if isinstance(r,dict):
  p=Path(r['path']);b=p.read_bytes();assert H(b)==r['sha256']
 else:p=Path(r);b=p.read_bytes()
 return json.loads(b)
def save(n,d):
 p=O/n;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(d,f,sort_keys=True,separators=(',',':'),allow_nan=False)
 return ref(p)
def git(*a):return subprocess.check_output(['git','--no-optional-locks',*a],text=True).strip()
A=read(O/'authority-v1.json');assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat(A['stop_authority']['deadline'].replace('Z','+00:00'));assert all(not os.path.lexists(p) for p in A['stop_authority']['paths'])
proposal=read(A['prospective_plan']);diagnosis=read(proposal['diagnosis']);terminal=read(diagnosis['retained_measurement_reconciliation']);read(A['authority'])
assert git('rev-parse','HEAD')==COMMIT;initial=git('status','--porcelain','--untracked-files=no')
g=read(T/'001864/canonical-v2/graph.complete-disabled-v1.json');assert g['actual_source_worktree']==str(ROOT);n=copy.deepcopy(g);pairs=[]
def replace(v):
 for a,b in pairs:
  if v==a:return copy.deepcopy(b)
 if isinstance(v,dict):return {k:replace(x) for k,x in v.items()}
 if isinstance(v,list):return [replace(x) for x in v]
 return v
def bind(k,name,d=None):
 nr=save(name,replace(read(g[k])) if d is None else d);pairs.append((g[k],nr));n[k]=nr;return nr
# Preserve source bytes and inventories; only shallow graph dependencies are composed.
source=read(g['source_record']);assert source['commit']==COMMIT
bind('source_record','source-record.json',source)
bind('amendment','source-scope-amendment.disabled-v1.json')
bind('runtime','runtime.disabled-v1.json')
bind('runtime_closure','runtime-closure.disabled-v1.json')
controller=replace(read(g['controller_semantics']));controller.update(status='PENDING_OWNER_REVIEW',root_acceptance=None,historical_review_only=ref(g['controller_semantics']['path']),historical_review_evidence=controller['review_evidence'],review_evidence={k:None for k in controller['review_evidence']})
bind('controller_semantics','controller-semantics.pending-disabled-v1.json',controller)
c=read(g['recovery_prefix_contract']);ledgers={k:Path(v['path']).resolve().read_bytes() for k,v in c['root_observed_ledger_prefixes'].items()}
for k,b in ledgers.items():assert RID.encode() not in b
prefixes={k:dict(path=str(Path(c['root_observed_ledger_prefixes'][k]['path']).resolve()),sha256=H(b),bytes=len(b)) for k,b in ledgers.items()}
oldrid=terminal['terminal']['resource_id'];own=ledgers['readiness-preparation-ledger.jsonl'];health=ledgers['gpu-healthcheck-ledger.jsonl'];lines=[line for line in own.splitlines(keepends=True) if oldrid.encode() in line];raw=b''.join(lines);rows=[json.loads(x) for x in lines];assert [r['event'] for r in rows]==['reserved','dispatched','completed'];assert all(r['resource_id']==oldrid for r in rows)
assert rows[-1]==terminal['terminal'];ob=own.index(raw);gb=health.index(raw)
p=O/'retained-predecessor-5.raw.jsonl';p.write_bytes(raw)
last=rows[-1];pred=dict(consumed=True,events=[r['event'] for r in rows],kind=last['kind'],resource_id=oldrid,terminal_status='completed',telemetry_complete=True,provider_calls_retained=last['provider_calls'],retained_charge_gpu_seconds=last['gpu_process_wall_seconds'],retained_charge_gpu_hours=last['gpu_process_wall_seconds']/3600,raw_bytes=len(raw),raw_sequence=ref(p),rows=rows,row_segments=[])
for key,name,start in [('own_journal','readiness-preparation-ledger.jsonl',ob),('global_health_segment','gpu-healthcheck-ledger.jsonl',gb)]:pred[key]=dict(path=prefixes[name]['path'],start_inclusive=start,end_exclusive=start+len(raw),sha256=H(raw))
cursor=0
for line,row in zip(lines,rows):
 pred['row_segments'].append(dict(bytes=len(line),event=row['event'],global_start_inclusive=gb+cursor,global_end_exclusive=gb+cursor+len(line),own_start_inclusive=ob+cursor,own_end_exclusive=ob+cursor+len(line),sha256=H(line)));cursor+=len(line)
c['predecessors'].append(pred)
identity=read(g['readiness_recovery']);identity.update(resource_id=RID,recovery_of=[p['resource_id'] for p in c['predecessors']],retained_charge_gpu_hours=sum(p['retained_charge_gpu_hours'] for p in c['predecessors']),unconsumed_at_draft=True,adopted=False,release_enabled=False)
bind('readiness_recovery','recovery-identity.disabled-v1.json',identity)
c.update(identity=n['readiness_recovery'],drafting_authority=ref(O/'authority-v1.json'),root_observed_ledger_prefixes=prefixes,own_journal_at_draft=prefixes['readiness-preparation-ledger.jsonl'],accepted_review=None,root_terminal_reconciliation=None,status='DISABLED_PENDING_OWNER_RECONCILIATION_FIVE_PREDECESSORS');c['successor']['resource_id']=RID
bind('recovery_prefix_contract','recovery-prefix-contract.disabled-v1.json',c)
p=read(g['policy'])
for k in p:
 if k.endswith('_path'):p[k]=str(O/('pending-'+k.removesuffix('_path')+'.json'))
p.update(resource_id=RID,disabled_runtime_path=n['runtime']['path']);bind('policy','preparation-policy.disabled-v1.json',p)
spec=replace(read(g['specification']));spec['runtime_binding'].update(source_record_path=n['source_record']['path'],runtime_path=str(O/'pending-measured-runtime.json'));bind('specification','specification.disabled-v1.json',spec)
plan=read(g['plan'])
for k in ['scope','accounting']:
 nr=save(k+'.disabled-v1.json',replace(read(plan[k])));pairs.append((plan[k],nr))
audit=replace(read(g['audit']));index=[];science=[]
science_keys=['argv','resolved_config','composed_config_sha256','row','audit_row','scientific_source','source','output_dir']
for i,row in enumerate(audit['episodes']):
 oldref=audit['expected_manifests'][row['episode_key']];old=read(oldref);new=replace(old);nr=save('audit-manifests/%02d.json'%i,new);pairs.append((oldref,nr));audit['expected_manifests'][row['episode_key']]=nr
 payload={k:old[k] for k in science_keys if k in old};assert payload=={k:new[k] for k in payload};science.append(dict(index=i,payload_sha256=H(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()),unchanged=True));index.append(dict(row=row,original=ref(oldref['path']),new=nr))
bind('audit','all40-audit.disabled-v1.json',audit)
old=read(g['separate_engineering_manifest']);new=replace(old);payload={k:old[k] for k in science_keys if k in old};assert payload=={k:new[k] for k in payload};science.append(dict(index=40,payload_sha256=H(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()),unchanged=True));bind('separate_engineering_manifest','engineering-manifest.disabled-v1.json',new)
bind('plan','engineering-plan.disabled-v1.json')
n['full40_manifests']=save('full40-manifest-index-v1.json',dict(manifests=index))
# Canonicalize direct external graph references without recursively changing historical records.
for k,v in n.items():
 if isinstance(v,dict) and 'path' in v and 'sha256' in v:n[k]={**v,'path':str(Path(v['path']).resolve())}
n.update(resource_id=RID,status='DISABLED_COMPOSED_PENDING_STRICT_ADMISSION_AND_OWNER_REVIEWS',review_status='RECOVERY_AND_CONTROLLER_BINDINGS_PENDING',graph_verified=False,release_enabled=False,historical_graph_only=ref(T/'001864/canonical-v2/graph.complete-disabled-v1.json'),recovery_identity_status='ABSENT_FROM_FOUR_COMPLETE_LEDGERS_AT_COMPOSITION_NOT_RESERVED')
n['historical_accounting_only']=dict(recovery_of=identity['recovery_of'],retained_charge_gpu_seconds=sum(x['retained_charge_gpu_seconds'] for x in c['predecessors']),retained_charge_gpu_hours=[x['retained_charge_gpu_hours'] for x in c['predecessors']])
gr=save('graph.complete-disabled-v1.json',n)
release_inputs=dict(graph=dict(plan=n['plan'],runtime=n['runtime']),specification=n['specification'],source_record=n['source_record'],baseline=spec['canonical_runtime'])
ri=save('release-inputs.disabled-v1.json',dict(**release_inputs,approved=False,release_enabled=False,resource_id=RID,proof_path=p['proof_path'],acceptance_path=p['acceptance_path'],runtime_output_path=spec['runtime_binding']['runtime_path'],accounting_authority=None,root_review=None))
prov=save('provenance-reconciliation-v1.json',dict(authority=ref(O/'authority-v1.json'),prospective_plan=ref(A['prospective_plan']['path']),path_failure=ref(proposal['diagnosis']['path']),predecessor_completed=ref(diagnosis['retained_measurement_reconciliation']['path']),historical_release=ref(diagnosis['release']['path']),historical_readiness_reusable=False,new_charge=0,retained_preparation_seconds=n['historical_accounting_only']['retained_charge_gpu_seconds'],retained_provider_calls=sum(x['provider_calls_retained'] for x in c['predecessors']),ledger_prefixes=prefixes,owner_worktree=str(Path(prefixes['attempt-ledger.jsonl']['path']).parent.parent),owner_reconciliation_pending=True,source_unchanged=True))
assert git('rev-parse','HEAD')==COMMIT and git('status','--porcelain','--untracked-files=no')==initial
for k,b in ledgers.items():assert Path(prefixes[k]['path']).read_bytes()==b
save('scientific-payload-integrity-v1.json',dict(status='PASS',count=len(science),payloads=science,fields_checked=science_keys,source_before_after=COMMIT,tracked_status_unchanged=True,ledger_bytes_unchanged=True,old_artifacts_overwritten=False))
print(json.dumps(dict(graph=gr,release_inputs=ri,provenance=prov,scientific_payload_count=len(science))))
