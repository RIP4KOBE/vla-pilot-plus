import os,sys,pathlib,json,hashlib,copy,datetime,subprocess,time,traceback
BASEOUT=pathlib.Path(__file__).parent; O=BASEOUT/"attempt-2"; T=BASEOUT.parent.parent; O.mkdir(exist_ok=False)
root=pathlib.Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_adapter_001482/implementation_worktree')
sys.path.insert(0,str(root));os.chdir(root)
from scripts import qd_ed_n36_engineering_r1 as e,qd_ed_n36_bridge as b,qd_ed_n23_worker as w,qd_ed_n36_stop as stop
inputs={};outputs={};checks=[];start=time.monotonic()
def rec(p):
 p=pathlib.Path(p);return {'path':str(p),'sha256':w.sha(p),'bytes':p.stat().st_size}
def load(p,expected=None):
 p=pathlib.Path(p);r=rec(p)
 if expected:assert r['sha256']==expected
 inputs[str(p)]=r;return json.loads(p.read_text())
def read(r):return load(r['path'],r['sha256'])
def save(name,d):
 p=O/name;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:f.write(json.dumps(d,sort_keys=True,separators=(',',':'),allow_nan=False))
 outputs[name]=rec(p);return {k:outputs[name][k] for k in ('path','sha256')}
def check(name,fn):
 stop.check();t=time.monotonic()
 try: fn();item={'check':name,'status':'PASS','elapsed_seconds':time.monotonic()-t}
 except Exception as ex:item={'check':name,'status':'FAIL','exception':type(ex).__name__,'message':str(ex),'traceback':traceback.format_exc(),'elapsed_seconds':time.monotonic()-t}
 checks.append(item);print(name,item['status'],item.get('message',''),flush=True);return item
try:
 stop.check()
 a=load(BASEOUT/'authority-v1.json');review=read(a['source_review']);impact=load(T/'001617/recovery-implementation/binding-impact-v1.json','451914f21dba6d39d47ac86a2653d139f84ea97d8a2ebe7cdb80ef1eedf84a2a');amend=read(a['amendment']);read(a['standing_authority']);spec=read(impact['operational_specification']);parent=read(impact['parent_plan']);load(BASEOUT/'source-placement-v1.json')
 # Only immediate current graph: no walking historical review chains.
 old={k:read(v['prior']) for k,v in impact['affected_bindings'].items() if 'path' in v['prior']}
 for ref in impact['affected_audit_manifest_bindings'].values():read(ref)
 for ref in impact['unchanged_parent_audit_science'].values():read(ref)
 read(impact['preserve']['native_build']);runtime=read(amend['runtime']);read(amend['parent_terminal']);read(amend['retained_snapshot'])
 for r in a['ledger_prefixes'].values():
  rr=rec(r['path']);assert rr==r;inputs[r['path']]=rr
 for key in ('runtime_inventory','seed_plan'):
  p=impact['preserve']['seed_and_runtime_inventory_inputs'][key+'_path'];load(p,impact['preserve']['seed_and_runtime_inventory_inputs'][key+'_sha256'])
 assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==review['source_commit']
 source=b.closure.source_record(root,b.source_paths(root));assert source['commit']==review['source_commit']
 save('source-inventory.disabled-v1.json',source)
 scope=save('scope.disabled-v1.json',e.disabled_scope());account=save('accounting.disabled-v1.json',e.disabled_accounting())
 route=copy.deepcopy(old['deployment']);route['output_root']=impact['new_output_root'];dep=save('deployment.disabled-v1.json',route)
 closure=copy.deepcopy(old['runtime_closure']);closure['runtime']=amend['runtime']
 changes=[];oldindex={r['path']:r['sha256'] for r in parent['source']['files']};newindex={r['path']:r['sha256'] for r in source['files']}
 for name,record in closure['modules'].items():
  path=pathlib.Path(record['path'])
  if path.is_relative_to(root):
   relative=str(path.relative_to(root));digest=w.sha(path)
   if digest!=record['sha256']:
    assert relative in e.OPERATIONAL_FILES and oldindex[relative]==record['sha256'] and newindex[relative]==digest
    changes.append({'module':name,'before':copy.deepcopy(record),'after':{'path':str(path),'sha256':digest}});record['sha256']=digest
 assert len(changes)==4
 for key in closure:
  if key not in ('modules','runtime'):assert closure[key]==old['runtime_closure'][key]
 for name,record in closure['modules'].items():
  if name not in {v['module'] for v in changes}:assert record==old['runtime_closure']['modules'][name]
 clref=save('runtime-closure.disabled-v1.json',closure)
 save('runtime-closure-diff.disabled-v1.json',{'runtime_reference_before':old['runtime_closure']['runtime'],'runtime_reference_after':amend['runtime'],'changed_modules':changes,'all_other_entries_unchanged':True,'release_enabled':False})
 # A changed binding is a proposal, never a newly ROOT_REVIEWED assertion.
 def proposal(prior,ref):
  p=copy.deepcopy(prior)
  p['historical_review_provenance']={k:p.pop(k) for k in ('root_binding_attestation','root_review_evidence','binding_review','reference_refresh_lineage') if k in p}
  p.update(status='PENDING_INDEPENDENT_AND_ROOT_REVIEW',at=datetime.datetime.now(datetime.timezone.utc).isoformat(),runtime=amend['runtime'],runtime_closure=clref,source_commit=source['commit'],release_enabled=False,b5_review=None)
  p['reference_refresh_lineage']={'prior_evidence':ref,'prior_status':prior['status'],'semantic_findings_unchanged':True,'new_root_approval':False,'independent_certification':False,'preparation_authority':{'path':str(BASEOUT/'authority-v1.json'),'sha256':w.sha(BASEOUT/'authority-v1.json')}}
  p['review_scope']='Disabled reference refresh proposal only; prior semantic findings retained; independent and root acceptance pending.'
  return p
 proof=proposal(old['controller_semantics'],impact['affected_bindings']['controller_semantics']['prior'])
 for name,ref in old['controller_semantics']['review_evidence'].items():
  prior=read(ref)
  for sr in prior['sources']: assert w.sha(sr['path'])==sr['sha256'];inputs[sr['path']]=rec(sr['path'])
  pp=proposal(prior,ref);proof['review_evidence'][name]=save('controller-evidence/'+name+'.proposed-disabled-v1.json',pp)
 proof['scope']='Disabled binding proposal. No new root source-semantics approval, deployment, physical gain, release or scientific promotion certification.'
 proofref=save('controller-semantics.proposed-disabled-v1.json',proof)
 changed=subprocess.check_output(['git','diff','--name-only',e.BASE,source['commit'],'--'],text=True).splitlines()
 assert set(changed)<=e.OPERATIONAL_FILES
 eq=save('scientific-equivalence.disabled-v1.json',{'schema':'n36-engineering-scientific-equivalence-v1','base_commit':e.BASE,'source':source,'changed_paths':sorted(changed),'scientific_changes':False})
 audit=copy.deepcopy(old['audit_plan']);audit.update(source=source,scientific_source=source,runtime=amend['runtime'],runtime_closure=clref,controller_semantics=proofref,scope=scope,deployment=dep,artifact_root=route['output_root']+'/audit-only',expected_manifests={})
 for k in ('episodes','cohort','limits','worker_contract','protocol','protocol_review','accounting','original_plan'):assert audit[k]==old['audit_plan'][k]
 e.validate_audit_view(audit,require_manifests=False)
 for n,row in enumerate(audit['episodes']):
  stop.check();m=b.manifest(audit,runtime,row);audit['expected_manifests'][row['episode_key']]=save('audit-manifests/'+row['episode_key']+'.disabled.json',m)
  if n%10==9:print('Generated audit manifests',n+1,flush=True)
 auditref=save('audit-view.disabled-v1.json',audit)
 plan=copy.deepcopy(parent);plan.update(cohort=e.IDENTITY,episodes=[e.row()],frozen=False,release_enabled=False,limits=e.LIMITS,phase_authorization={'engineering':False,'dev':False,'validation':False,'formal':False},source=source,scientific_source=source,runtime=amend['runtime'],runtime_closure=clref,controller_semantics=proofref,scope=scope,accounting=account,deployment=dep,artifact_root=route['output_root'],audit_plan=auditref,scientific_equivalence=eq,authority=None,b5_review=None,engineering_manifest=None,expected_manifests={})
 m=b.engineering_manifest(plan,runtime,e.row());mr=save('engineering-manifest.disabled-v1.json',m);plan['engineering_manifest']=mr;plan['expected_manifests']={e.EPISODE_KEY:mr}
 planref=save('engineering-plan.draft-disabled-v1.json',plan)
 save('bindings.disabled-v1.json',{'schema':'n36-engineering-r1-binding-refresh-draft-v1','bindings':e.review_bindings(plan),'plan':planref,'deployment':dep,'scope':scope,'accounting':account,'release_enabled':False,'gpu_authorized':False,'independent_b5':'PENDING','root_review':'PENDING','controller_review':'PENDING','frozen_plan':'PENDING','inherited_parent_authority':False})
 check('R1 disabled scope',lambda:e.validate_scope_reference(scope))
 check('R1 disabled accounting',lambda:e.validate_accounting_reference(account))
 check('R1 lexical deployment',lambda:e.deployment(plan))
 check('R1 draft plan shape',lambda:e.validate_plan_shape(plan))
 check('R1 all40 audit shape and original scientific rows',lambda:e.validate_audit_view(audit))
 check('R1 exact audit mapping',lambda:e.audit_mapping(plan,audit,e.row()))
 check('R1 scientific equivalence',lambda:e.scientific_equivalence(plan))
 check('R1 terminal parent prefixes and retained accounting',e.terminal_parent_prefix)
 # Actual full closure verifies source/runtime then fails closed on pending root controller review.
 check('Full actual CPU audit closure',lambda:e.full.verify_audit_closure(audit))
 # Verify remaining independent pieces not reached after the expected controller gate.
 from scripts.qd_ed_n36_build import manifest as native_manifest
 # Native bytes were already validated in attempt 1 and are unchanged.
 def audit_manifests():
  for row in audit['episodes']:stop.check();b._verify_manifest_bound(audit['expected_manifests'][row['episode_key']],audit,runtime,row)
 check('All40 generated audit manifest recompositions',audit_manifests)
 check('Engineering R1 manifest and exact C0 configuration',lambda:b.verify_engineering_manifest(mr,plan,runtime,e.row(),audit=audit))
 def dino_check():
  from scripts.qd_ed_n36_dino import DinoSources
  d=DinoSources(amend['runtime'])
  for name,path in d.names.items():d.check_file(name,path)
 check('Canonical DINO runtime reference and source bytes',dino_check)
 def runtime_files():
  r=e.r;r.verify_files(runtime['files'],allowed_roots=(plan['worktree'],runtime['worktree'],runtime['artifact_root']))
  fingerprints={str(pathlib.Path(x['path']).resolve()) for x in runtime['files']}
  for task in runtime['tasks'].values():
   actual={str(p.resolve()) for p in pathlib.Path(task['cache_dir']).rglob('*') if p.is_file()}
   w.require(actual and actual<=fingerprints,'task cache inventory incomplete')
 check('Runtime file and task cache validators',runtime_files)
 check('Frozen runtime checkpoint task seed validators',lambda:e.r.validate_runtime_inputs(audit,runtime,b.profiles(plan['worktree']),root,{'artifacts':runtime['artifact_root']}))
 from scripts.qd_ed_n34_controller import verify_semantics
 check('Pending controller attestation gate',lambda:verify_semantics(proofref,amend['runtime'],closure))
except Exception as ex:
 checks.append({'check':'graph_generation','status':'FAIL','exception':type(ex).__name__,'message':str(ex),'traceback':traceback.format_exc()});print(traceback.format_exc(),flush=True)
finally:
 save('generation-results-v1.json',{'schema':'n36-engineering-r1-disabled-generation-results-v1','checks':checks,'inputs':list(inputs.values()),'outputs':outputs.copy(),'elapsed_seconds':time.monotonic()-start,'release_enabled':False,'gpu_authorized':False})
