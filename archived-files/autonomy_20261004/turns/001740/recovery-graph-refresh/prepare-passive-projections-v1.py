"""Standard-library-only incomplete artifact projections, not production acceptance."""
import ast, copy, datetime as dt, hashlib, json, os, subprocess, time
from pathlib import Path
O=Path(__file__).absolute().parent;T=O.parents[1]
A=json.loads((O/'authority-v1.json').read_text()); ROOT=Path(A['source']['worktree'])
START=time.monotonic();INPUTS={};OUTPUTS={};COMMANDS=[];CHECKS=[]
def guard():
 assert time.monotonic()-START<240
 assert dt.datetime.now(dt.timezone.utc)<dt.datetime.fromisoformat(A['deadline'].replace('Z','+00:00'))
 assert all(not os.path.lexists(p) for p in A['stop_authority']['paths'])
def rec(p):
 p=Path(p);assert 'poe' not in p.name.lower() and '2026-08-10' not in str(p)
 data=p.read_bytes();return dict(path=str(p),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
def ref(r):return {k:r[k] for k in ('path','sha256')}
def read(r):
 guard();a=rec(r['path']);assert all(a[k]==r[k] for k in ('sha256','bytes') if k in r);INPUTS[a['path']]=a;return json.loads(Path(a['path']).read_text())
def save(p,d,text=False):
 guard();p=Path(p);assert not os.path.lexists(p)
 assert any(p.resolve().is_relative_to(Path(r).resolve()) for r in A['allowed_output_roots'])
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('xb') as f:f.write(d.encode() if text else json.dumps(d,sort_keys=True,separators=(',',':'),allow_nan=False).encode())
 OUTPUTS[str(p)]=rec(p);return ref(OUTPUTS[str(p)])
def git(*args):
 guard();q=subprocess.run(['git','--no-replace-objects','-C',str(ROOT),*args],capture_output=True,text=True,check=True,timeout=30,env={**os.environ,'GIT_OPTIONAL_LOCKS':'0','GIT_NO_LAZY_FETCH':'1'})
 COMMANDS.append(dict(argv=q.args,stdout=q.stdout,stderr=q.stderr,returncode=q.returncode));return q.stdout.strip()
def note(name,detail):CHECKS.append(dict(check=name,status='PASS',detail=detail))
def source_check():
 assert git('rev-parse','HEAD')==A['source']['commit'] and git('rev-parse','HEAD^{tree}')==A['source']['tree']
 assert git('diff','--name-only')==git('diff','--cached','--name-only')==''
guard();source_check()
first=read(rec(O/'report-v1.json'));receipt=read(rec(O/'command-receipt-v1.json'));read(receipt['output']) if False else None
for k in ('review','source_placement','standing_authority'):read(A[k])
review=read(A['review']);spec=read(A['canonical_specification']);contract=read(A['canonical_contract']);slots=read(A['downstream_slots']);S=slots['slots']
assert all(not os.path.lexists(p) for p in list(S.values())+slots['full40_manifests'])
policy=read(spec['runtime_binding']['preparation']);identity=read(contract['identity'])
assert policy['resource_id']==A['fresh_resource_id']==contract['successor']['resource_id']==identity['resource_id']
assert contract['predecessor']['resource_id']==A['recovery_of']==identity['recovery_of']
assert contract['predecessor']['retained_charge_gpu_hours']==A['retained_charge_gpu_hours']
assert contract['predecessor']['rows'][-1]['telemetry_complete'] is False
# Real journal bytes and exact segment equality, no filtering or accounting rebasing.
for name,r in A['ledger_prefixes'].items():
 actual=rec(r['path']);assert all(actual[k]==r[k] for k in actual);INPUTS[actual['path']]=actual
for name,r in contract['original_ledger_prefixes'].items():
 with Path(r['path']).open('rb') as f:data=f.read(r['bytes'])
 assert len(data)==r['bytes'] and hashlib.sha256(data).hexdigest()==r['sha256']
assert spec['retained_ledger_prefixes']==contract['original_ledger_prefixes']
rawref=contract['predecessor']['raw_sequence'];actual=rec(rawref['path']);assert actual['sha256']==rawref['sha256'];INPUTS[actual['path']]=actual
raw=Path(rawref['path']).read_bytes();assert len(raw)==5143 and raw.endswith(b'\n')
for key in ('own_journal','global_health_segment'):
 segment=contract['predecessor'][key]
 with Path(segment['path']).open('rb') as f:f.seek(segment['start_inclusive']);data=f.read(segment['end_exclusive']-segment['start_inclusive'])
 assert data==raw
assert [json.loads(x) for x in raw.splitlines()]==contract['predecessor']['rows']
for r in contract['predecessor']['row_segments']:
 data=raw[r['own_start_inclusive']:r['own_end_exclusive']];assert len(data)==r['bytes'] and hashlib.sha256(data).hexdigest()==r['sha256']
note('retained historical prefix and charge','Exact original offsets, complete four journal hashes, 5143 raw bytes, all three row hashes and mirror equality; retained aborted predecessor incomplete telemetry and charge unchanged.')
r723=read(rec(T/'001723/readiness-recovery-graph/report-v1.json'));g723=read(r723['graph']);r707=read(rec(T/'001707/disabled-graph-refresh/report-v1.json'))
source=read(g723['source_record']);oldsource=copy.deepcopy(source)
changed=git('diff','--name-only',source['commit'],A['source']['commit'],'--').splitlines()
assert set(changed)=={'scripts/qd_ed_n36_engineering_r1.py','tests/test_n36_engineering_r1.py'}
reviewed={x['path']:x['after'] for x in review['source_files']}
for row in source['files']:
 if row['path'] in changed:
  a=rec(ROOT/row['path']);assert a['sha256']==reviewed[row['path']]['sha256'] and a['bytes']==reviewed[row['path']]['bytes'];INPUTS[a['path']]=a;row['sha256']=a['sha256']
source['commit']=A['source']['commit'];source['sha256']=hashlib.sha256(json.dumps(source['files'],sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
# Match the inspected canonical_sha API exactly, without importing production modules.
worker=(ROOT/'scripts/qd_ed_n23_worker.py').read_text();wn=next(n for n in ast.parse(worker).body if isinstance(n,ast.FunctionDef) and n.name=='canonical_sha')
assert "separators=(',', ':')" in ast.unparse(wn)
sr=save(S['source_record'],source)
note('source projection','1116-entry prior hash-bound inventory projected to final reviewed commit by exact two-file diff; Poe hash inherited without opening Poe; no full closure claim.')
text=(ROOT/'scripts/qd_ed_n36_engineering_r1.py').read_text();tree=ast.parse(text)
assign={t.id:n.value for n in tree.body if isinstance(n,ast.Assign) for t in n.targets if isinstance(t,ast.Name)}
assert ast.literal_eval(assign['SPECIFICATION'])==ref(A['canonical_specification'])
base=ast.literal_eval(assign['BASE']);allow=ast.literal_eval(assign['OPERATIONAL_FILES'].args[0]);changedall=git('diff','--name-only',base,source['commit'],'--').splitlines();assert set(changedall)<=allow
git('merge-base','--is-ancestor',base,source['commit'])
eq=save(S['scientific_equivalence'],dict(schema='n36-engineering-scientific-equivalence-v1',base_commit=base,source=source,changed_paths=sorted(changedall),scientific_changes=False))
note('scientific equivalence static prerequisites','Exact operational allowlist, ancestor and changed paths verified by Git; canonical evidence shape follows inspected source. Production scientific_equivalence was not executed.')
baseline=read(spec['canonical_runtime']);runtime=copy.deepcopy(baseline);runtime['preparation'].update(source=source['commit'],source_record=sr)
assert all(x is False for x in (runtime['preparation']['runtime_ready'],runtime['provider_ready'],runtime['cuda_egl_verified'],runtime['gpu_mapping']['cuda_egl_verified']))
assert policy['disabled_runtime_path']==S['disabled_runtime'] and spec['runtime_binding']['source_record_path']==S['source_record']
rr=save(S['disabled_runtime'],runtime)
oldclosure=read(g723['runtime_closure']);closure=copy.deepcopy(oldclosure);closure['runtime']=rr;cr=save(S['runtime_closure'],closure)
oldplan=read(g723['plan']);oldaudit=read(g723['audit']);native=read(oldplan['native_build']);nr=save(S['native_build'],native)
scope=read(oldplan['scope']);scope.update(specification=ref(A['canonical_specification']),scope=spec['scope']);assert scope['release_enabled'] is False;scr=save(S['scope'],scope)
acc=read(oldplan['accounting']);acc.update(specification=ref(A['canonical_specification']),accounting=spec['accounting_proposal'],retained_ledger_prefixes=spec['retained_ledger_prefixes'],retained_snapshot_reference=spec['retained_snapshot_reference']);assert acc['release_enabled'] is acc['root_adopted'] is False;acr=save(S['accounting'],acc)
dr=save(S['deployment'],read(oldplan['deployment']))
def proposal(d,prior):
 d=copy.deepcopy(d);assert d['status']=='PENDING_INDEPENDENT_AND_ROOT_REVIEW'
 d.update(runtime=rr,runtime_closure=cr,source_commit=source['commit'],at=dt.datetime.now(dt.timezone.utc).isoformat())
 d['reference_refresh_lineage']=dict(prior_evidence=prior,prior_status='PENDING_INDEPENDENT_AND_ROOT_REVIEW',semantic_findings_unchanged=True,new_root_approval=False,independent_certification=False,preparation_authority=ref(rec(O/'authority-v1.json')))
 return d
basis=r707['graph']['controller_semantics'];proof=proposal(read(basis),basis)
for name,r in proof['review_evidence'].items():proof['review_evidence'][name]=save(O/('controller-'+name+'.proposed-disabled-v1.json'),proposal(read(r),r))
assert proof['source']==closure['modules'][proof['module']]
pfr=save(S['controller_semantics'],proof)
fields=dict(source=source,scientific_source=source,runtime=rr,runtime_closure=cr,native_build=nr,controller_semantics=pfr,scope=scr,deployment=dr)
audit=copy.deepcopy(oldaudit);audit.update(fields,expected_manifests={},frozen=False,release_enabled=False);ar=save(S['audit_view'],audit)
plan=copy.deepcopy(oldplan);plan.update(fields,accounting=acr,scientific_equivalence=eq,audit_plan=ar,engineering_manifest=None,expected_manifests={},frozen=False,release_enabled=False,authority=None,b5_review=None);pr=save(S['engineering_plan'],plan)
assert all(v is False for v in plan['phase_authorization'].values()) and all(v is False for v in audit['phase_authorization'].values())
node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='validate_audit_view')
frozen=next(n for n in ast.walk(node) if isinstance(n,ast.Compare) and ast.unparse(n)=="plan['frozen'] is True")
blockers=[
 dict(id='FROZEN_AUDIT_CONFLICT',detail='All frozen flags must remain false/null, but unmodified validate_audit_view requires frozen is True. Both full40 and engineering production builders call it. No bypass or manifest stand-ins.',location='scripts/qd_ed_n36_engineering_r1.py:'+str(frozen.lineno)),
 dict(id='POE_FULL_SOURCE_VERIFICATION',detail='validate_runtime_binding invokes verify_source, which reads all source files including scripts/qd_ed_poe_launch.py. Poe must remain unopened; inventory is a projection only.',location='scripts/qd_ed_n34_source.py:367'),
 dict(id='MISSING_EXTERNAL_CONTROLLER_ACCEPTANCE',detail='Final-source/runtime/closure controller proposal is PENDING_INDEPENDENT_AND_ROOT_REVIEW. Production requires ROOT_REVIEWED and external binding evidence; no approval created.',location='scripts/qd_ed_n34_controller.py:45'),
 dict(id='GUARDED_IMPORT_STOP',detail='Initial production import was stopped by executor conservative no-model/native-import guard at audit_decision_evidence importing torch. No Torch/GPU execution occurred; this follow-up uses only standard library and does not claim production API validation.',evidence=ref(rec(O/'command-receipt-v1.json')))
]
for k in ('cohort','episodes','limits','worker_contract','deadline','protocol','protocol_review','accounting'):assert audit[k]==oldaudit[k]
assert len(audit['episodes'])==40 and [(x['task_id'],x['profile']) for x in audit['episodes']]==[(i,p) for i in range(10) for p in ('C0','Q0','N34','N36')]
assert audit['stop_authority']==plan['stop_authority']==A['stop_authority']
for path,r in INPUTS.items():assert rec(path)==r,path
assert all(not os.path.lexists(p) for p in list(S.values())+slots['full40_manifests'] if p not in OUTPUTS)
source_check();guard()
note('immutable inputs and scientific/resource projections','All direct input and ledger bytes preserved; all science rows/rules/limits, provider/GPU mapping, STOP/deadline, budgets/reserves retained. Approval/readiness/measurement/manifest reserved slots absent.')
graph=save(S['graph'],dict(schema='n36-readiness-recovery-prospective-graph-v1',status='BLOCKED_INCOMPLETE_DISABLED_GRAPH',specification=ref(A['canonical_specification']),policy=spec['runtime_binding']['preparation'],recovery_prefix_contract=ref(A['canonical_contract']),resource_id=A['fresh_resource_id'],recovery_of=A['recovery_of'],retained_charge_gpu_hours=A['retained_charge_gpu_hours'],source_record=sr,runtime=rr,runtime_closure=cr,native_build=nr,controller_semantics=pfr,scientific_equivalence=eq,audit=ar,plan=pr,full40_manifests=None,separate_engineering_manifest=None,graph_complete=False,graph_verified=False,release_enabled=False,frozen=False,runtime_ready=False,provider_ready=False,gpu_authorized=False,provider_measurement_authorized=False,authority=None,b5_review=None,root_acceptance=None,blockers=blockers))
ce=save(O/'passive-command-evidence-v1.json',dict(schema='n36-passive-cpu-evidence-v1',commands=COMMANDS,checks=CHECKS,production_api_calls=0,manifest_builder_invocations=0,model_native_provider_gpu_invocations=0,tests_run=[]))
im=save(O/'passive-inputs-manifest-v1.json',dict(files=list(INPUTS.values()),recursive_provenance_verified=False))
manifest=save(O/'generated-artifact-manifest-v2.json',dict(schema='n36-exact-generated-artifact-manifest-v1',files=[rec(Path(__file__))]+list(OUTPUTS.values()),scope='Exact passive output artifacts; final report/hash included in outputs-manifest-v2.json.'))
report=copy.deepcopy(first);report.update(at=dt.datetime.now(dt.timezone.utc).isoformat(),supersedes_without_overwrite=ref(rec(O/'report-v1.json')),graph=graph,blockers=blockers,generated_artifact_manifest=manifest,command_evidence=ce,input_manifest=im,elapsed_builder_seconds=time.monotonic()-START,checks=CHECKS,limitations=['Final-source inventory, runtime, closure, native inventory and controller bindings are explicit unaccepted projections. Full source/native/runtime verification not executed.','Scientific equivalence Git prerequisites and unchanged scientific/accounting projections verified, without production API validation.','40+1 manifest slots remain absent because frozen audit and Poe source verification conflict with task constraints.','No fresh external controller/B5/root adoption exists; conservative guarded import failure is preserved as initial report-v1.json.'])
reportref=save(O/'report-v2.json',report);save(O/'report-v2.sha256',reportref['sha256']+'  report-v2.json\n',text=True)
save(O/'outputs-manifest-v2.json',dict(schema='exact-passive-executor-output-manifest-v1',files=[rec(Path(__file__))]+list(OUTPUTS.values()),excludes=['outputs-manifest-v2.json (self reference)','passive-builder-stdout-v1.log (execution stream bound by passive-command-receipt-v1.json)']))
print(json.dumps(dict(status=report['status'],report=reportref,graph=graph,output_count=len(OUTPUTS),blockers=[x['id'] for x in blockers])),flush=True)
