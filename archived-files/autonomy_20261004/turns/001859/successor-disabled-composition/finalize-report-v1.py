import json,hashlib,copy,os,subprocess,datetime as dt
from pathlib import Path
O=Path(__file__).resolve().parent;OLD=O.parent.parent/'001841/composition-v6'
def ref(p):return dict(path=str(p),sha256=hashlib.sha256(Path(p).read_bytes()).hexdigest())
def read(v):
 if isinstance(v,dict):assert ref(v['path'])=={k:v[k] for k in ('path','sha256')};v=v['path']
 return json.loads(Path(v).read_text())
def save(n,d):
 p=O/n
 with p.open('x') as f:json.dump(d,f,indent=2,sort_keys=True);f.write('\n')
 return ref(p)
a=read(O/'authority-v1.json');assert all(not os.path.lexists(p) for p in a['stop_authority']['paths']);assert dt.datetime.now(dt.timezone.utc)<dt.datetime.fromisoformat(a['stop_authority']['deadline'].replace('Z','+00:00'))
r=read(O/'report-v1.json');g=read(r['candidate_graph']);old=read(OLD/'graph.complete-disabled-v1.json');p=read(g['plan']);op=read(old['plan']);audit=read(g['audit']);oa=read(old['audit']);s=read(g['specification']);oldspec=read(old['specification'])
checks=[]
for v in r['outputs'].values():read(v)
checks.append(dict(check='all recorded output artifact hashes resolve',status='PASS'))
pairs=[(old[k],g[k]) for k in ('source_record','runtime','runtime_closure','controller_semantics','amendment','readiness_recovery','recovery_prefix_contract','policy','specification')]+[(op[k],p[k]) for k in ('scope','accounting')]
for key,v in oa['expected_manifests'].items():pairs.append((v,audit['expected_manifests'][key]))
pairs.append((old['audit'],g['audit']))
def replace(v):
 for a,b in pairs:
  if v==a:return copy.deepcopy(b)
 if isinstance(v,dict):return {k:replace(x) for k,x in v.items()}
 if isinstance(v,list):return [replace(x) for x in v]
 return v
assert len(audit['episodes'])==len(audit['expected_manifests'])==40
for row in audit['episodes']:
 key=row['episode_key'];assert read(audit['expected_manifests'][key])==replace(read(oa['expected_manifests'][key]))
assert read(g['separate_engineering_manifest'])==replace(read(old['separate_engineering_manifest']))
assert audit==replace(oa)
checks.append(dict(check='all 40 audit manifests plus engineering manifest exact dependency rebinding; all scientific commands/config hashes unchanged',status='PASS',production_recomposition='Blocked at null owner reconciliation; structural equality is not full production admission'))
projected=copy.deepcopy(s)
for k in ('readiness_recovery','recovery_prefix_contract'):projected[k]=oldspec[k]
for k in ('preparation','amendment','source_record_path','runtime_path'):projected['runtime_binding'][k]=oldspec['runtime_binding'][k]
assert projected==oldspec
checks.append(dict(check='entire scientific/accounting specification unchanged outside declared operational references',status='PASS'))
contract=read(g['recovery_prefix_contract']);ctrl=read(g['controller_semantics']);assert contract['root_terminal_reconciliation'] is contract['accepted_review'] is ctrl['root_acceptance'] is None
assert all(v is None for v in ctrl['review_evidence'].values())
assert p['authority'] is p['b5_review'] is None and p['release_enabled'] is p['frozen'] is False
policy=read(g['policy']);pending={k:v for k,v in policy.items() if k.endswith('_path') and k!='disabled_runtime_path'};pending['runtime_path']=s['runtime_binding']['runtime_path']
assert all(Path(v).is_relative_to(O) and not os.path.lexists(v) for v in pending.values())
checks.append(dict(check='changed approval gates null and all future preparation release/proof/output paths fresh and absent',status='PASS'))
command=['env','PYTHONDONTWRITEBYTECODE=1','CUDA_VISIBLE_DEVICES=','OMP_NUM_THREADS=1','/home/hynx/miniconda3/envs/vla-pilot/bin/python','-B',str(O/'verify-candidate-v3.py')]
run=subprocess.run(command,cwd=a['worktree'],capture_output=True,text=True,timeout=45)
assert run.returncode==0,run.stderr
result=json.loads(run.stdout);receipt=save('bounded-verifier-receipt-v1.json',dict(argv=command,cwd=a['worktree'],returncode=run.returncode,result=result,stderr=run.stderr))
for name,v in a['ledger_prefixes'].items():
 data=Path(v['path']).read_bytes();assert len(data)==v['bytes'] and hashlib.sha256(data).hexdigest()==v['sha256']
checks.append(dict(check='final complete ledger hashes equal authority',status='PASS'))
checks_ref=save('composition-integrity-checks-v1.json',dict(checks=checks,production_verifier_receipt=receipt,fourth_predecessor={k:contract['predecessors'][3][k] for k in ('resource_id','terminal_status','telemetry_complete','provider_calls_retained','retained_charge_gpu_seconds','retained_charge_gpu_hours','raw_bytes','own_journal','global_health_segment')}))
commands=read(r['next_commands']);commands['commands'][0].update(argv=command,expected='PASS policy/capture/budget; EXPECTED_BLOCK null reconciliation',tested_receipt=receipt)
commands['supersedes']=r['next_commands'];commands['correction']='Standalone verifier v1/v2 blocked library import-time /dev/null/tempdir discovery. v3 prebinds tempdir inside output directory, allows /dev/null, prohibits filesystem writes, and passes. No production validators changed.'
command_ref=save('next-commands-v2.json',commands)
r.update(previous_report=ref(O/'report-v1.json'),next_commands=command_ref,composition_integrity=checks_ref,production_verifier_receipt=receipt,completion_at=dt.datetime.now(dt.timezone.utc).isoformat())
r['checks']+=checks
r['outputs'].update({p.name:ref(p) for p in (O/'compose-successor-v1.py',O/'verify-candidate-v3.py',O/'finalize-report-v1.py',O/'bounded-verifier-receipt-v1.json',O/'composition-integrity-checks-v1.json',O/'next-commands-v2.json')})
r['correction']='Use next-commands-v2.json and verify-candidate-v3.py. The original report and all earlier artifacts remain immutable.'
r['unresolved_owner_gates'].append(dict(id='all41_production_manifest_admission',status='PENDING',requirement='Manifest dependency equality passed. Exact production recomposition remains gated by owner terminal reconciliation; do not claim all41 production validation.'))
final=save('report-final-v2.json',r)
print(json.dumps(dict(final_report=final,candidate_graph=r['candidate_graph'],checks=checks,fourth_predecessor_seconds=contract['predecessors'][3]['retained_charge_gpu_seconds'])))
