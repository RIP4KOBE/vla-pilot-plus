import os,sys,json,hashlib,time,subprocess,copy,traceback
from pathlib import Path
os.environ['CUDA_VISIBLE_DEVICES']='';sys.dont_write_bytecode=True
O=Path(__file__).parent;A=json.loads((O/'authority-v1.json').read_text());S=Path(A['source']['worktree']);sys.path.insert(0,str(S))
checks=[]; hashes={}
def ref(r):
 p=Path(r['path']);assert '2026-08-10-eds-qd-stage-guidance-transition-design.md' not in str(p)
 b=p.read_bytes();v=dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest());assert v['sha256']==r['sha256'],str(p)
 if 'bytes' in r:assert v['bytes']==r['bytes']
 hashes[str(p)]=v;return json.loads(b)
def short(r):return {k:r[k] for k in ('path','sha256')}
def check(n,f,pending=None):
 t=time.monotonic()
 try:
  result=f();assert pending is None,'expected pending rejection absent';v=dict(check=n,status='PASS',result=result)
 except Exception as ex:v=dict(check=n,status='EXPECTED_PENDING' if pending==str(ex) else 'FAIL',message=str(ex),traceback=traceback.format_exc())
 v['elapsed_seconds']=time.monotonic()-t;checks.append(v);print(json.dumps(v),flush=True)
 (O/'checks-v1.json').write_text(json.dumps(dict(checks=checks,hashes=list(hashes.values())),indent=2)+'\n')
R=ref(A['graph_report']);M=ref(A['output_manifest']);G=R['graph'];D={}
def bindings():
 assert G==M['graph']
 for k,r in G.items():
  if k=='full40_manifests':
   D[k]={a:ref(b) for a,b in r.items()}
  else:D[k]=ref(r)
 for r in R['active_records'].values():ref(r)
 review=ref(R['review']);assert review['decision']=='PASS_SCOPED_CPU';assert review['source']['commit']==A['source']['commit']
 for r in review['source']['files']:
  local=S/Path(r['path']).relative_to(review['source']['worktree']); ref(dict(path=str(local),sha256=r['sha256'])) if local.suffix=='.json' else hash_file(local,r['sha256'])
 return {'graph_artifacts':len(G)-1+len(D['full40_manifests']),'prior_source_review':review['decision']}
def hash_file(p,expected):
 b=Path(p).read_bytes();h=hashlib.sha256(b).hexdigest();assert h==expected,str(p);hashes[str(p)]=dict(path=str(p),bytes=len(b),sha256=h)
check('Exact authority report/output hashes, graph artifacts and prior reviewed source file continuity',bindings)
from scripts import qd_ed_n36_engineering_r1 as e, qd_ed_n36_readiness_prepare as prep
P=D['engineering_plan'];T=D['runtime'];C=D['runtime_closure'];source=D['source_record'];audit=D['full40_audit']
def policy_binding():
 spec=e.specification();assert e.SPECIFICATION==short(R['active_records']['specification']);assert spec==ref(R['active_records']['specification']);p=prep.policy(spec)
 assert spec['runtime_binding']['accounting_contract']==short(R['active_records']['contract'])
 assert p==ref(R['active_records']['policy'])
 assert p['disabled_runtime_path']==G['runtime']['path'];assert spec['runtime_binding']['source_record_path']==G['source_record']['path']
 assert P['source']==P['scientific_source']==source;assert source['commit']==A['source']['commit']
 assert T['preparation']['source_record']==short(G['source_record'])
 base=e.read(spec['canonical_runtime']);expected=copy.deepcopy(base);expected['preparation'].update(source=source['commit'],source_record=short(G['source_record']));assert T==expected
 assert not T['provider_ready'] and not T['cuda_egl_verified'] and not T['gpu_mapping']['cuda_egl_verified'] and not T['preparation']['runtime_ready']
 assert D['accounting']==e.disabled_accounting();assert D['scope']==e.disabled_scope()
 return {'projection':'Only preparation.source and preparation.source_record differ from pinned baseline','all_readiness_flags':False}
check('New specification policy contract and exact disabled baseline projection',policy_binding)
check('Unmodified preparation.verify_graph on exact deployed graph',lambda:prep.verify_graph({'graph':{'plan':short(G['engineering_plan']),'runtime':short(G['runtime'])}},source,e.read(e.specification()['canonical_runtime'])),pending='reviewed controller semantics required')
def controller_bindings():
 proof=D['controller_semantics'];assert proof['runtime']==short(G['runtime']);assert proof['runtime_closure']==short(G['runtime_closure']);assert proof['source_commit']==source['commit'];assert proof['status']=='PENDING_INDEPENDENT_AND_ROOT_REVIEW'
 assert proof['source']==C['modules'][proof['module']];assert proof['module'] in C['required_after'];hash_file(proof['source']['path'],proof['source']['sha256'])
 assert proof['physical_gain_certified'] is False
 for name,r in proof['review_evidence'].items():
  d=ref(r);assert d['runtime']==proof['runtime'] and d['runtime_closure']==proof['runtime_closure'] and d['source_commit']==source['commit'];assert d['native_execution_observed'] is False and d['fixture_only'] is False
  for s in d['sources']:hash_file(s['path'],s['sha256'])
 return {'evidence':list(proof['review_evidence']),'native_execution_observed':False}
check('Controller proposals bind current runtime closure commit and exact installed source bytes',controller_bindings)
def all_manifest_bindings():
 assert len(audit['episodes'])==len(D['full40_manifests'])==40
 for row in audit['episodes']:
  key=row['episode_key'];assert audit['expected_manifests'][key]==short(G['full40_manifests'][key]);m=D['full40_manifests'][key]
  for k in ['source','scientific_source','runtime','runtime_closure','native_build','controller_semantics','scope','deployment']:assert m[k]==audit[k],(key,k)
 m=D['separate_engineering_manifest'];assert P['engineering_manifest']==short(G['separate_engineering_manifest']);assert P['expected_manifests']=={e.EPISODE_KEY:short(G['separate_engineering_manifest'])}
 for k in ['scientific_eligible','promotion_eligible','matched_improvement_eligible']:assert m[k] is False
 return {'audit_count':40,'engineering_separate':True,'scientific_eligible':False}
check('All40 direct manifest bindings and distinct engineering manifest',all_manifest_bindings)
check('Separate engineering manifest unmodified recomposition',lambda:e.b.verify_engineering_manifest(P['engineering_manifest'],P,T,e.row(),audit=audit))
check('Scientific source equivalence',lambda:e.scientific_equivalence(P))
def git_final():
 out={}
 for args in [('rev-parse','HEAD'),('rev-parse','HEAD^{tree}'),('diff','--name-only','HEAD')]:out[' '.join(args)]=subprocess.check_output(['git','--no-optional-locks','-C',str(S),*args],text=True).strip()
 assert out['rev-parse HEAD']==A['source']['commit'];assert out['rev-parse HEAD^{tree}']==A['source']['tree'];assert out['diff --name-only HEAD']=='';return out
check('Final unchanged deployed commit tree tracked files',git_final)
