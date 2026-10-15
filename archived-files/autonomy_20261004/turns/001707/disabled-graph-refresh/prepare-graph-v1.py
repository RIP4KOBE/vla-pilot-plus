"""Bounded artifact-only driver using accepted production graph builders. No measurement."""
import os,sys,json,hashlib,copy,datetime,time,traceback,subprocess
from pathlib import Path
O=Path(__file__).absolute().parent
A=json.loads((O/'authority-v1.json').read_text()); ROOT=Path(A['source']['worktree'])
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT));os.chdir(ROOT)
from scripts import qd_ed_n36_engineering_r1 as e, qd_ed_n36_bridge as b, qd_ed_n23_worker as w, qd_ed_n36_stop as stop
from scripts import qd_ed_n36_readiness_prepare as preparation
start=time.monotonic(); inputs={};outputs={};checks=[];commands=[]
def guard():
 stop.check()
 assert time.monotonic()-start<850,'CPU executor bound'
 assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat(A['deadline'].replace('Z','+00:00'))
def record(p):
 p=Path(p);data=p.read_bytes();return dict(path=str(p),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
def ref(p):return {k:v for k,v in record(p).items() if k!='bytes'}
def read(r):
 guard();v=record(r['path']);assert v['sha256']==r['sha256'] and ('bytes' not in r or v['bytes']==r['bytes']), 'input mismatch: '+r['path'];inputs[v['path']]=v;return json.loads(Path(v['path']).read_text())
def save_path(p,d,fixed=False):
 guard();p=Path(p);data=json.dumps(d,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
 if os.path.lexists(p):
  raise AssertionError('existing output conflict: '+str(p))
 else:
  p.parent.mkdir(parents=True,exist_ok=True)
  with p.open('xb') as f:f.write(data)
 outputs[str(p)]=record(p);return ref(p)
def save(n,d):return save_path(O/n,d)
def check(label,fn):
 guard();t=time.monotonic()
 try:fn();v=dict(check=label,status='PASS')
 except Exception as ex:v=dict(check=label,status='FAIL',message=str(ex),traceback=traceback.format_exc())
 v['elapsed_seconds']=time.monotonic()-t;checks.append(v);print(label,v['status'],v.get('message',''),flush=True);
 if v['status']=='FAIL' and label!='complete disabled preparation graph': raise RuntimeError(label+': '+v['message'])
 return v
try:
 guard()
 read(record(O/'authority-v1.json'))
 for key in ('standing_authority','review','source_placement'):read(A[key])
 review=read(A['review']);assert review['bounded_next_step']==A['scope']
 detached=Path(A['review']['path']).with_suffix('.sha256');assert detached.read_text().split()[0]==A['review']['sha256'];inputs[str(detached)]=record(detached)
 for r in review['active_records'].values():read(r)
 for r in A['ledger_prefixes'].values():assert record(r['path'])=={k:r[k] for k in ('path','bytes','sha256')};inputs[r['path']]=record(r['path'])
 for args,expected in [(['rev-parse','HEAD'],A['source']['commit']),(['rev-parse','HEAD^{tree}'],A['source']['tree']),(['diff','--name-only'],''),(['diff','--cached','--name-only'],'')]:
  q=subprocess.run(['git','-C',str(ROOT),*args],capture_output=True,text=True,check=True);assert q.stdout.strip()==expected;commands.append(dict(argv=q.args,stdout=q.stdout,returncode=q.returncode))
 spec=e.specification();assert spec==read(review['active_records']['specification']);p=preparation.policy(spec)
 assert spec['runtime_binding']['source_record_path']==A['scope']['fresh_source_record_path']
 assert p['disabled_runtime_path']==A['scope']['fresh_disabled_runtime_path']
 prospective={k:v for k,v in p.items() if k.endswith('_path')};prospective.update({k:spec['runtime_binding'][k] for k in ('runtime_path','source_record_path')})
 assert all(not os.path.lexists(v) for v in prospective.values()),'prospective path already present'
 def direct_refs(obj):
  if isinstance(obj,dict):
   if 'path' in obj and 'sha256' in obj and Path(obj['path']).is_absolute():
    v=record(obj['path']);assert v['sha256']==obj['sha256'] and ('bytes' not in obj or v['bytes']==obj['bytes']), 'direct input mismatch: '+obj['path'];inputs[v['path']]=v
   else:
    for x in obj.values():direct_refs(x)
  elif isinstance(obj,list):
   for x in obj:direct_refs(x)
 direct_refs(spec);direct_refs(p)
 prior_dir=O.parents[1]/'001691/refreshed-disabled-graph'
 prior_report=read(record(prior_dir/'refresh-result-v1.json'))
 oldplan=read(prior_report['graph']['plan']);oldaudit=read(oldplan['audit_plan'])
 for key in ('runtime','runtime_closure','native_build','controller_semantics','scope','accounting','deployment','scientific_equivalence'):read(oldplan[key])
 for key in ('protocol','protocol_review','accounting','original_plan'):read(oldaudit[key])
 for key in ('runtime_inventory','seed_plan'):
  direct_refs(dict(path=oldplan[key+'_path'],sha256=oldplan[key+'_sha256']))
 read(read(A['source_placement'])['complete_committed_inventory']) if False else direct_refs(read(A['source_placement'])['complete_committed_inventory'])
 source=b.closure.source_record(ROOT,b.source_paths(ROOT));assert source['commit']==A['source']['commit']
 source_ref=save_path(spec['runtime_binding']['source_record_path'],source,True)
 save('source-inventory.disabled-v1.json',source)
 baseline=read(spec['canonical_runtime']);runtime=copy.deepcopy(baseline)
 runtime['preparation'].update(source=source['commit'],source_record=source_ref)
 assert not runtime['preparation']['runtime_ready'] and not runtime['provider_ready'] and not runtime['cuda_egl_verified'] and not runtime['gpu_mapping']['cuda_egl_verified']
 rtref=save_path(p['disabled_runtime_path'],runtime,True)
 closure=read(oldplan['runtime_closure']);oldclosure=copy.deepcopy(closure);closure['runtime']=rtref
 clref=save('runtime-closure.disabled-v1.json',closure)
 native=read(oldplan['native_build']);nr=save('native-build.disabled-v1.json',native)
 def proposal(d,prior):
  d=copy.deepcopy(d);assert d['status']=='PENDING_INDEPENDENT_AND_ROOT_REVIEW'
  d.update(runtime=rtref,runtime_closure=clref,source_commit=source['commit'],at=datetime.datetime.now(datetime.timezone.utc).isoformat())
  for key in ('source','sources'):
   if key in d:direct_refs(d[key])
  d['reference_refresh_lineage']=dict(prior_evidence=prior,prior_status='PENDING_INDEPENDENT_AND_ROOT_REVIEW',semantic_findings_unchanged=True,new_root_approval=False,independent_certification=False,preparation_authority=ref(O/'authority-v1.json'))
  return d
 proposal_basis=record(O.parents[1]/'001682/disabled-graph-preparation/controller-semantics.proposed-disabled-v1.json')
 proof=proposal(read(proposal_basis),proposal_basis)
 for name,r in proof['review_evidence'].items():proof['review_evidence'][name]=save('controller-evidence/'+name+'.proposed-disabled-v1.json',proposal(read(r),r))
 proofref=save('controller-semantics.proposed-disabled-v1.json',proof)
 scope=save('scope.disabled-v1.json',e.disabled_scope());accounting=save('accounting.disabled-v1.json',e.disabled_accounting())
 deployment=save('deployment.disabled-v1.json',read(oldplan['deployment']))
 argv=['git','-C',str(ROOT),'diff','--name-only',e.BASE,source['commit'],'--']
 proc=subprocess.run(argv,capture_output=True,text=True,check=True);commands.append(dict(argv=argv,stdout=proc.stdout,stderr=proc.stderr,returncode=proc.returncode))
 equivalence=save('scientific-equivalence.disabled-v1.json',dict(schema='n36-engineering-scientific-equivalence-v1',base_commit=e.BASE,source=source,changed_paths=sorted(proc.stdout.splitlines()),scientific_changes=False))
 fields=dict(source=source,scientific_source=source,runtime=rtref,runtime_closure=clref,native_build=nr,controller_semantics=proofref,scope=scope,deployment=deployment)
 audit=copy.deepcopy(oldaudit);audit.update(fields,expected_manifests={})
 # Production helpers compose all manifests. No reference-only substitutes.
 for row in audit['episodes']:
  guard();key=row['episode_key'];m=b.manifest(audit,runtime,row)
  audit['expected_manifests'][key]=save('audit-manifests/'+key+'.disabled.json',m)
  print('generated',key,flush=True)
 auditref=save('audit-view.disabled-v1.json',audit)
 plan=copy.deepcopy(oldplan);plan.update(fields,accounting=accounting,scientific_equivalence=equivalence,audit_plan=auditref,expected_manifests={})
 mr=save('engineering-manifest.disabled-v1.json',b.engineering_manifest(plan,runtime,e.row(),audit=audit))
 plan.update(engineering_manifest=mr,expected_manifests={e.EPISODE_KEY:mr})
 assert plan['authority'] is None and plan['b5_review'] is None and not plan['frozen'] and not plan['release_enabled']
 pr=save('engineering-plan.draft-disabled-v1.json',plan)
 save('bindings.disabled-v1.json',dict(schema='n36-disabled-graph-bindings-v1',plan=pr,bindings=e.review_bindings(plan),source_record=source_ref,release_enabled=False,gpu_authorized=False,root_review='PENDING',independent_b5='PENDING'))
 check('exact deployed source closure',lambda:b.verify_sources(plan))
 check('loaded source bytes',lambda:b.attest_loaded(ROOT,source))
 check('runtime source closure',lambda:b.closure.verify_runtime(closure,rtref))
 check('disabled plan shape',lambda:e.validate_plan_shape(plan))
 check('all40 audit shape',lambda:e.validate_audit_view(audit))
 check('distinct engineering audit mapping',lambda:e.audit_mapping(plan,audit,e.row()))
 check('scientific source equivalence',lambda:e.scientific_equivalence(plan))
 from scripts.qd_ed_n36_build import manifest as native_manifest
 check('native inventory passive hash validation',lambda:native_manifest(nr))
 def all41():
  for row in audit['episodes']:
   guard();b._verify_manifest_bound(audit['expected_manifests'][row['episode_key']],audit,runtime,row)
  b.verify_engineering_manifest(mr,plan,runtime,e.row(),audit=audit)
 check('all41 production manifest recompositions',all41)
 def preserve():
  projection=copy.deepcopy(baseline);projection['preparation'].update(source=source['commit'],source_record=source_ref);assert runtime==projection
  for k in ('cohort','episodes','limits','worker_contract','deadline','protocol','protocol_review','accounting'):assert audit[k]==oldaudit[k]
  assert native==read(oldplan['native_build'])
  assert all(record(path)==r for path,r in inputs.items())
  assert all(not os.path.lexists(v) for k,v in prospective.items() if k not in ('disabled_runtime_path','source_record_path'))
  assert all(v is False for v in plan['phase_authorization'].values())
 check('immutable inputs science costs and ledgers preserved',preserve)
 # Read-only complete bootstrap gate intentionally retains required external controller review.
 check('complete disabled preparation graph',lambda:preparation.verify_graph({'graph':{'plan':pr,'runtime':rtref}},source,baseline))
except Exception as ex:
 checks.append(dict(check='generation',status='FAIL',message=str(ex),traceback=traceback.format_exc()));print(traceback.format_exc(),flush=True)
finally:
 save('generation-results-v1.json',dict(schema='n36-disabled-graph-generation-results-v1',inputs=list(inputs.values()),outputs=list(outputs.values()),checks=checks,commands=commands,elapsed_seconds=time.monotonic()-start,release_enabled=False,gpu_authorized=False,measurement_invocations=0))
