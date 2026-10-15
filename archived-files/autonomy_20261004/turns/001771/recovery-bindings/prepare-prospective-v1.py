"""Bounded disabled artifact composition; exact extracted CPU production consumers.
No native imports, substituted approvals, ledger mutation, or production dispatch.
"""
import ast, copy, datetime as dt, hashlib, json, os, subprocess, sys, time, types
from pathlib import Path
sys.dont_write_bytecode=True
START=time.monotonic(); O=Path(__file__).absolute().parent; T=O.parent.parent
I={}; OUT={}; CHECKS=[]; GAPS=[]
RID='n36_readiness_preparation_recovery_001771'
def rec(p):
 p=Path(p); b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def ref(v):return {k:v[k] for k in ('path','sha256')}
def read(v):
 p=Path(v['path'] if isinstance(v,dict) else v);r=rec(p)
 if isinstance(v,dict):assert all(r[k]==v[k] for k in ('bytes','sha256') if k in v),str(p)
 I[str(p)]=r;return json.loads(p.read_bytes())
A=read(O/'authority-v1.json'); ROOT=Path(A['worktree'])
os.environ.update(PYTHONDONTWRITEBYTECODE='1',GIT_OPTIONAL_LOCKS='0',GIT_NO_LAZY_FETCH='1',CUDA_VISIBLE_DEVICES='')
def guard():
 assert time.monotonic()-START<1000
 assert dt.datetime.now(dt.timezone.utc)<dt.datetime.fromisoformat(A['stop_authority']['deadline'].replace('Z','+00:00'))
 assert not any(os.path.lexists(p) for p in A['stop_authority']['paths'])
def save(n,v):
 guard();p=O/n;assert p.parent==O and not p.exists(),str(p)
 b=v if isinstance(v,bytes) else (json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
 p.write_bytes(b);OUT[n]=rec(p);return ref(OUT[n])
def check(n,b,**kw):
 assert b,n;CHECKS.append(dict(check=n,status='PASS',**kw))
def git(*args):return subprocess.check_output(['git','--no-optional-locks','--no-replace-objects','-C',str(ROOT),*args],text=True).strip()
def snapshot():return dict(commit=git('rev-parse','HEAD'),tree=git('rev-parse','HEAD^{tree}'),tracked_changes=git('status','--porcelain','--untracked-files=no'))
before=snapshot();check('frozen clean source',before['commit']==A['source'] and not before['tracked_changes']);guard()
summary=read(T/'001770/operational-summary-v1.json');review=read(A['scoped_source_review'])
check('scoped source review binding',summary['scoped_review']['sha256']==A['scoped_source_review']['sha256'])
for x in review['source']['files']:check('exact reviewed source file '+Path(x['path']).name,rec(x['path'])==x)
read(A['standing_authority']);terminal=read(A['terminal_reconciliation']);read(A['entry_inspection'])
repair=read(T/'001766/recovery-source-repair/report-v1.json')
prior=read(T/'001764/recovery-bindings/report-v1.json')
idx=read(T/'001748/disabled-graph-composition/final-composition-index-v1.json');g=read(idx['graph'])
spec=read(g['specification']);oldspec=copy.deepcopy(spec);pol=read(g['policy']);contract=read(g['recovery_prefix_contract'])
oldcontract=copy.deepcopy(contract);oldsource=read(g['source_record']);oldruntime=read(g['runtime'])
raw={}
for name,a in A['ledger_prefixes'].items():
 actual=rec(a['path']);check('unchanged full '+name,all(actual[k]==a[k] for k in actual));I[a['path']]=actual
 raw[name]=Path(a['path']).read_bytes();rows=[json.loads(x) for x in raw[name].splitlines()]
 check('unused successor '+name,all(RID not in (r.get('resource_id'),r.get('attempt_id'),r.get('episode_key')) for r in rows))
for name,a in contract['original_ledger_prefixes'].items():check('original accounting offset '+name,hashlib.sha256(raw[name][:a['bytes']]).hexdigest()==a['sha256'])
own=raw['readiness-preparation-ledger.jsonl']; offset=contract['original_ledger_prefixes']['gpu-healthcheck-ledger.jsonl']['bytes'];lines=own.splitlines(keepends=True)
check('all six raw rows exactly mirrored',len(lines)==6 and raw['gpu-healthcheck-ledger.jsonl'][offset:]==own)
preds=[]; ownpos=0;globalpos=offset
for j in range(2):
 chunk=b''.join(lines[j*3:j*3+3]);rows=[json.loads(x) for x in lines[j*3:j*3+3]];last=rows[-1]
 rr=save('retained-predecessor-%d.raw.jsonl'%(j+1),chunk);segments=[];cur=0
 for line,row in zip(lines[j*3:j*3+3],rows):
  segments.append(dict(bytes=len(line),event=row['event'],global_start_inclusive=globalpos+cur,global_end_exclusive=globalpos+cur+len(line),own_start_inclusive=ownpos+cur,own_end_exclusive=ownpos+cur+len(line),sha256=hashlib.sha256(line).hexdigest()));cur+=len(line)
 def seg(name,start):return dict(path=A['ledger_prefixes'][name]['path'],start_inclusive=start,end_exclusive=start+len(chunk),sha256=rr['sha256'])
 preds.append(dict(consumed=True,events=[r['event'] for r in rows],global_health_segment=seg('gpu-healthcheck-ledger.jsonl',globalpos),kind='readiness_preparation',own_journal=seg('readiness-preparation-ledger.jsonl',ownpos),provider_calls_retained=last['provider_calls'],raw_bytes=len(chunk),raw_sequence=rr,resource_id=last['resource_id'],retained_charge_gpu_hours=last['gpu_process_wall_seconds']/3600,retained_charge_gpu_seconds=last['gpu_process_wall_seconds'],row_segments=segments,rows=rows,telemetry_complete=last['telemetry_complete']))
 ownpos+=len(chunk);globalpos+=len(chunk)
check('latest abort matches terminal reconciliation',preds[-1]['rows'][-1]==terminal['terminal'])
charge=sum(p['retained_charge_gpu_hours'] for p in preds)
identity=save('recovery-identity.prospective-disabled-v1.json',dict(schema='n36-prospective-readiness-recovery-identity-v1',resource_id=RID,recovery_of=[p['resource_id'] for p in preds],retained_charge_gpu_hours=charge,source=A['source'],unconsumed_at_draft=True,automatic_retry=False,release_enabled=False,adopted=False))
contract.pop('predecessor');contract.update(schema='n36-failed-readiness-recovery-prefix-contract-v2',predecessors=preds,identity=identity,drafting_authority=ref(rec(O/'authority-v1.json')),accepted_review=None,root_terminal_reconciliation=ref(A['terminal_reconciliation']),root_observed_ledger_prefixes=terminal['ledger_prefixes'],own_journal_at_draft={k:A['ledger_prefixes']['readiness-preparation-ledger.jsonl'][k] for k in ('path','bytes','sha256')},status='DISABLED_PENDING_FRESH_ROOT_RECONCILIATION_AND_REVIEW')
contract['successor']['resource_id']=RID
contract['read_semantics']=[s for s in oldcontract['read_semantics'] if '5143-byte' not in s]
contract['read_semantics'].append('Retain ordered own [0,5143), [5143,10278) and global [114767,119910), [119910,125045), authenticating all six exact raw rows. accepted_review is deliberately null: turn001759 terminal is historical evidence, not the required fresh root recovery review reconciliation; production selection must reject until root supplies it.')
cr=save('recovery-prefix-contract.prospective-disabled-v2.json',contract)
for k in list(pol):
 if k.endswith('_path'):pol[k]=str(O/(k.removesuffix('_path').replace('_','-')+'.json'))
pol['previous_specification']=g['specification'];pol['resource_id']=RID
pr=save('preparation-policy.prospective-disabled-v1.json',pol)
spec['readiness_recovery']=identity;spec['recovery_prefix_contract']=cr;spec['runtime_binding']['preparation']=pr
spec['runtime_binding']['runtime_path']=str(O/'measured-runtime.json');spec['runtime_binding']['source_record_path']=str(O/'source-record.json')
sr=save('specification.prospective-disabled-v1.json',spec)
os.environ['QD_ED_N36_R1_SPECIFICATION']=json.dumps(sr)
selector=save('specification-selector-v1.json',{'environment':{'QD_ED_N36_R1_SPECIFICATION':json.dumps(sr)},'set_before_first_import':True,'release_enabled':False,'adopted':False})
# Extract unchanged definitions, retaining real hashing, file readers and assertions.
# This is a static CPU harness, not a full module import or whole-graph validation.
def extract(file,names=None,namespace=None,all_safe=False):
 p=ROOT/file;I[str(p)]=rec(p);tree=ast.parse(p.read_bytes());nodes=[]
 for n in tree.body:
  if names is not None:
   if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names:nodes.append(n)
   elif isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in names for t in n.targets):nodes.append(n)
  elif all_safe:
   if isinstance(n,(ast.FunctionDef,ast.ClassDef,ast.Assign)):nodes.append(n)
   elif isinstance(n,(ast.Import,ast.ImportFrom)) and not (isinstance(n,ast.ImportFrom) and n.module and n.module.startswith('scripts')):nodes.append(n)
 ns={} if namespace is None else namespace
 exec(compile(ast.Module(body=nodes,type_ignores=[]),str(p),'exec'),ns)
 return ns
base=dict(Path=Path,json=json,hashlib=hashlib,os=os,subprocess=subprocess)
wn=extract('scripts/qd_ed_n23_worker.py',{'require','sha','canonical_sha','read_ref','_source_git','_source_entry'},base.copy());w=types.SimpleNamespace(**wn)
ns=extract('scripts/qd_ed_n36_engineering_r1.py',{'HISTORICAL_SPECIFICATION','SPECIFICATION','AMENDMENT','HEALTH_ID','EPISODE_KEY','JOURNALS','exact','reference','read','specification','_recovery_json','_recovery_rows','_recovery_read','_recovery_specification','_recovery_predecessors','_recovery_contract','_recovery_capture'},dict(base,w=w))
check('exact env selector evaluated by production assignment',ns['SPECIFICATION']==sr)
parsed,tail,current=ns['_recovery_capture'](contract,Path(A['ledger_prefixes']['attempt-ledger.jsonl']['path']).parent)
check('production raw capture retains both predecessors and empty successor',len(parsed['readiness-preparation-ledger.jsonl'])==6 and not tail and not current)
try:ns['specification']()
except Exception as ex:
 check('selected specification rejects missing fresh root reconciliation',str(ex)=='root recovery reconciliation schema')
 GAPS.append(dict(id='FRESH_ROOT_RECOVERY_RECONCILIATION_REQUIRED',consumer='scripts/qd_ed_n36_engineering_r1.py:_recovery_contract',error=str(ex),actual_schema=terminal['schema'],required_schema='n36-recovery-binding-review-terminal-reconciliation-v1',accepted_review=None,detail='Provided turn001759 terminal has no required review/live_handles/root_accepts_blocking_findings binding. No root acceptance fabricated; fresh contract is intentionally not yet consumable.'))
else:raise AssertionError('Unreviewed selection unexpectedly passed')
# Exact production source closure functions, with native imports excluded.
cl=extract('scripts/qd_ed_n34_source.py',namespace={'w':w},all_safe=True)
paths={r['path'] for r in oldsource['files']}
newsource=cl['source_record'](ROOT,paths,commit=A['source'])
source_ref=save('source-record.json',newsource)
check('1116 production source files verified against Git objects',len(newsource['files'])==1116)
changed=[r['path'] for r in newsource['files'] if r not in oldsource['files']]
check('source inventory changes exactly scoped repair',set(changed)=={'scripts/qd_ed_n36_engineering_r1.py','tests/test_n36_engineering_r1.py'})
runtime=read(spec['canonical_runtime']);runtime['preparation']['source']=A['source'];runtime['preparation']['source_record']=source_ref
runtime_ref=save('disabled-runtime.json',runtime)
check('runtime flags remain disabled',runtime['preparation']['runtime_ready'] is False and runtime['provider_ready'] is False and runtime['cuda_egl_verified'] is False)
cs=read(T/'001763/operational-summary-v1.json');cov=read(cs['review']);candidate=read(cs['prospective_candidate_closure']);baseclosure=read(cov['base_closure'])
check('closure retains all 6767 base entries',len(baseclosure['modules'])==6767 and all(candidate['modules'].get(k)==v for k,v in baseclosure['modules'].items()))
added=set(candidate['modules'])-set(baseclosure['modules']);check('145 exact OpenGL additions',len(added)==145 and all(k.startswith('OpenGL.') for k in added))
check('prior candidate runtime binding',candidate['runtime']==g['runtime'])
closure=copy.deepcopy(candidate);closure['runtime']=runtime_ref
closure_ref=save('runtime-closure.prospective-disabled-v1.json',closure)
cl['verify_runtime'](closure,runtime_ref)
check('production static runtime closure verifies all 6912 origins and interpreter',len(closure['modules'])==6912)
controller=read(g['controller_semantics'])
for k in ['root_binding_attestation','review_scope','scope','reference_refresh_lineage','historical_review_provenance']:controller.pop(k,None)
controller.update(runtime=runtime_ref,runtime_closure=closure_ref,source_commit=A['source'],status='PENDING_INDEPENDENT_AND_ROOT_REVIEW',review_evidence={},historical_review=g['controller_semantics'],release_enabled=False,review_scope='Candidate static rebinding only. Historical review does not approve this changed runtime/source/closure.')
controller_ref=save('controller-semantics.prospective-disabled-v1.json',controller)
cn=extract('scripts/qd_ed_n34_controller.py',{'verify_semantics'},dict(w=w))
try:cn['verify_semantics'](controller_ref,runtime_ref,closure)
except ValueError as ex:
 check('production controller consumer rejects unreviewed binding',str(ex)=='reviewed controller semantics required')
 GAPS.append(dict(id='FRESH_CONTROLLER_BINDING_REVIEW_REQUIRED',consumer='scripts/qd_ed_n34_controller.py:verify_semantics',error=str(ex),historical_review=g['controller_semantics'],detail='New runtime/closure/source require fresh review; historical ROOT_REVIEWED status and review_evidence were not transferred.'))
else:raise AssertionError('Unreviewed controller unexpectedly accepted')
# Do not manufacture audit/manifest downstream attestations through a failed upstream gate.
source_text=(ROOT/'scripts/qd_ed_n36_engineering_r1.py').read_text()
GAPS.append(dict(id='DEPLOYED_SOURCE_ROUTE_UNRESOLVED',consumer='scripts/qd_ed_n36_readiness_prepare.py:verify_graph',required_source_route='SESSION/variants/n36_engineering_adapter_001482/implementation_worktree',reviewed_source_worktree=str(ROOT),detail='Production verify_graph requires plan.worktree == module root == e.SOURCE. Reviewed repair is in n36_engineering_r1_001617; no deployment or source edit was authorized. Root must resolve deployment of pinned reviewed source before whole-graph validation.'))
retained=save('historical-evidence-v1.json',dict(schema='n36-historical-evidence-only-v1',prior_graph=idx['graph'],prior_acceptance=ref(rec(T/'001755/root-b5-scoped-acceptance-v1.json')),terminal_reconciliation=ref(A['terminal_reconciliation']),source_review=ref(A['scoped_source_review']),opengl_review=ref(cs['review']),prior_preparation=ref(rec(T/'001764/recovery-bindings/report-v1.json')),scope='Historical provenance only; no approval of changed candidates.'))
account=save('accounting-prefix.prospective-v1.json',dict(original_ledger_prefixes=contract['original_ledger_prefixes'],full_ledger_prefixes=A['ledger_prefixes'],retained_snapshot_reference=spec['retained_snapshot_reference'],retained_charge_gpu_hours=charge,retained_charge_gpu_seconds=sum(p['retained_charge_gpu_seconds'] for p in preds),full_ledgers_required=True,unknown_telemetry_preserved=True,rebased=False,budget_recomputed=False,reservation_created=False,release_enabled=False))
affected=[]
for k in ['audit','full40_manifests','separate_engineering_manifest','native_build','scientific_equivalence','plan']:
 affected.append(dict(node=k,historical=g[k],status='PENDING_UPSTREAM_RECONCILIATION_CONTROLLER_REVIEW_AND_DEPLOYMENT',new_artifact=None))
graph=save('affected-graph.prospective-disabled-v1.json',dict(schema='n36-readiness-recovery-prospective-graph-v1',status='BLOCKED_DISABLED_PARTIAL_GRAPH',resource_id=RID,recovery_of=[p['resource_id'] for p in preds],specification=sr,selector=selector,policy=pr,recovery_prefix_contract=cr,source_record=source_ref,runtime=runtime_ref,runtime_closure=closure_ref,controller_semantics=controller_ref,accounting_prefix=account,historical_evidence=retained,affected_downstream=affected,graph_complete=False,graph_verified=False,release_enabled=False,gpu_authorized=False,provider_measurement_authorized=False,provider_ready=False,runtime_ready=False,root_acceptance=None,root_controller_acceptance=None,b5_review=None,authority=None,frozen=False,adopted=False))
check('source unchanged after composition',snapshot()==before)
for p,v in I.items():assert rec(p)==v,p
check('all direct inputs and full ledgers unchanged',True)
check('no native runtime imported',not any(x.split('.')[0] in {'torch','numpy','OpenGL','mujoco','robosuite','libero'} for x in sys.modules))
validation=save('focused-static-validation-v1.json',dict(schema='n36-focused-static-composition-validation-v1',method='Unchanged AST-extracted production definitions, real read/hash/Git operations; no mock references/assertions, native imports or full production module loading. No broad tests repeated.',checks=CHECKS,blockers=GAPS,full_graph_validated=False))
manifest=save('artifact-manifest-v1.json',dict(files=list(OUT.values())+[rec(__file__)],excludes=['artifact-manifest-v1.json','report-v1.json','report-v1.sha256','executor transport logs']))
report=dict(schema='n36-prospective-recovery-bindings-report-v1',at=dt.datetime.now(dt.timezone.utc).isoformat(),status='BLOCKED_DISABLED_CANDIDATES_PREPARED',authority=ref(rec(O/'authority-v1.json')),node_id='15.6',resource_id=RID,source=dict(worktree=str(ROOT),**before),specification=sr,recovery_prefix_contract=cr,preparation_policy=pr,source_record=source_ref,runtime=runtime_ref,runtime_closure=closure_ref,graph=graph,artifact_manifest=manifest,focused_validation=validation,retained_lifecycles=[{k:p[k] for k in ['resource_id','retained_charge_gpu_hours','retained_charge_gpu_seconds','provider_calls_retained','telemetry_complete']} for p in preds],retained_charge_gpu_hours=charge,original_global_health_offset=offset,full_ledger_hashes_unchanged=True,runtime_reuse=dict(retained=6767,added=145,all_6912_origins_hash_verified=True,only_runtime_reference_rebound=True),blockers=GAPS,next_action='Owning root to review exact disabled candidates and supply a fresh recovery-binding-review terminal reconciliation plus scoped controller binding review; resolve deployment of reviewed a5b32cdef source to required production route. Then compose affected downstream audit/all41/native/equivalence/plan graph and run focused static consumers before any separately authorized measurement. Do not replay either consumed identity.',gaps=['No complete graph, fresh binding acceptance, source deployment, release/adoption or measured readiness.','Runtime static hashes do not establish native runtime coverage or successful provider execution.','Original scientific validation/formal/required ablation evidence remains incomplete.'],release_enabled=False,measurement_enabled=False,adopted=False,full_graph_validated=False,independent_approval_claimed=False,source_edits=False,owning_state_mutation=False,ledger_writes=False,old_artifact_writes=False,gpu_dispatches=0,provider_calls=0,native_imports=0,stage_access=False,protected_results_access=False,scientific_changes=False,limits_changed=False,recursive_provenance_rebuilt=False,elapsed_seconds=time.monotonic()-START,deadline=A['stop_authority']['deadline'],direct_inputs=list(I.values()))
r=save('report-v1.json',report);save('report-v1.sha256',(r['sha256']+'  report-v1.json\n').encode());print(json.dumps(dict(status=report['status'],report=r,checks=len(CHECKS),blockers=[b['id'] for b in GAPS])))
