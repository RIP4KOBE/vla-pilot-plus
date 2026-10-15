"""Artifact-only recovery drafts. No pin replacement, validation bypass or execution."""
import os, sys, json, hashlib, copy, datetime as dt, time, subprocess, difflib, ast
from pathlib import Path
sys.dont_write_bytecode=True
O=Path(__file__).absolute().parent
A=json.loads((O/'authority-v1.json').read_text()); ROOT=Path(A['source']['worktree'])
START=time.monotonic(); INPUTS={}; OUTPUTS={}; CHECKS=[]; COMMANDS=[]
def guard():
    for name in A['stop_authority']['paths']:
        try: os.lstat(name)
        except FileNotFoundError: pass
        else: raise RuntimeError('STOP present: '+name)
    assert dt.datetime.now(dt.timezone.utc)<dt.datetime.fromisoformat(A['deadline'].replace('Z','+00:00'))
    assert time.monotonic()-START<1000

def record(path):
    path=Path(path); data=path.read_bytes()
    return dict(path=str(path),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
def ref(record): return {k:record[k] for k in ('path','sha256')}
def read(r):
    guard(); p=Path(r['path']); assert not p.is_symlink()
    v=record(p); assert v['sha256']==r['sha256'] and ('bytes' not in r or v['bytes']==r['bytes']),str(p)
    INPUTS[str(p)]=v; return json.loads(p.read_text())
def save(name,value,text=False):
    guard(); p=O/name; assert p.parent==O
    data=value.encode() if text else json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    if os.path.lexists(p):
        assert p.name in ('recovery-identity.prospective-disabled-v1.json','preparation-policy.prospective-disabled-v1.json','engineering-r1-spec.prospective-disabled-v1.json','specification.diff','preparation-policy.diff') and p.read_bytes()==data, 'output conflict: '+str(p)
    else:
        with p.open('xb') as f:f.write(data)
    OUTPUTS[name]=record(p);return ref(OUTPUTS[name])
def check(name,fn):
    guard(); result=fn(); CHECKS.append(dict(check=name,status='PASS',detail=result)); print(name,'PASS',flush=True)
def git(*args):
    q=subprocess.run(['git','--no-replace-objects','-C',str(ROOT),*args],capture_output=True,text=True,check=True,env={**os.environ,'GIT_OPTIONAL_LOCKS':'0','GIT_NO_LAZY_FETCH':'1'})
    COMMANDS.append(dict(argv=q.args,returncode=q.returncode,stdout=q.stdout,stderr=q.stderr));return q.stdout.strip()
def source_check():
    assert git('rev-parse','HEAD')==A['source']['commit']
    assert git('rev-parse','HEAD^{tree}')==A['source']['tree']
    assert git('diff','--name-only')==git('diff','--cached','--name-only')==''
    return 'Exact HEAD/tree; no tracked changes; untracked contents not inspected.'
guard();read(record(O/'authority-v1.json'))
for key in ('standing_authority','review','source_placement'):read(A[key])
check('source before',source_check)
R=O.parents[1]/'001707/disabled-graph-refresh'
prior=read(record(R/'report-v1.json'))
assert (R/'report-v1.sha256').read_text().split()[0]==INPUTS[str(R/'report-v1.json')]['sha256']
INPUTS[str(R/'report-v1.sha256')]=record(R/'report-v1.sha256')
INPUTS[str(R/'prepare-graph-v1.py')]=record(R/'prepare-graph-v1.py')
# Inspect only directly needed current source, no recursive provenance reconstruction.
for name in ('scripts/qd_ed_n36_engineering_r1.py','scripts/qd_ed_n36_engineering_api.py','scripts/qd_ed_n36_readiness_prepare.py','scripts/qd_ed_n36_bridge.py','scripts/qd_ed_n36_stop.py'):
    INPUTS[str(ROOT/name)]=record(ROOT/name)
sys.path.insert(0,str(ROOT));os.chdir(ROOT)
from scripts import qd_ed_n36_engineering_r1 as e, qd_ed_n36_bridge as b, qd_ed_n36_readiness_prepare as prep, qd_ed_n36_stop as stop
assert stop.binding()==A['stop_authority'];stop.check()
spec=read(e.SPECIFICATION); policy=read(spec['runtime_binding']['preparation'])
assert policy['resource_id']==A['recovery_of']
assert e.SPECIFICATION==ref(prior['active_records']['specification'])
assert not ast.parse((ROOT/'scripts/qd_ed_n36_engineering_r1.py').read_text()).body is None
# Both the current resource and its charge remain explicit, immutable historical facts.
identity=dict(schema='n36-readiness-recovery-identity-v1',resource_id=A['fresh_resource_id'],recovery_of=A['recovery_of'],retained_charge_gpu_hours=A['retained_charge_gpu_hours'],retained_terminal_status='ABORTED_CHARGED_IMPORT_FAILURE',prior_identity_replay_authorized=False,prior_identity_replayed=False,authority=ref(record(O/'authority-v1.json')),source=A['source'],stop_authority=A['stop_authority'],deadline=A['deadline'],release_enabled=False,frozen=False,gpu_authorized=False,provider_measurement_authorized=False,runtime_ready=False,source_adopted=False,root_adopted=False,independently_reviewed=False)
identity_ref=save('recovery-identity.prospective-disabled-v1.json',identity)
newpolicy=copy.deepcopy(policy)
newpolicy['resource_id']=A['fresh_resource_id']
pathnames={'disabled_runtime_path':'runtime.prospective-disabled-v1.json','release_path':'release.pending-v1.json','proof_path':'proof.pending-v1.json','gpu_path':'gpu-evidence.pending-v1.json','provider_path':'provider-evidence.pending-v1.json','accounting_path':'accounting-evidence.pending-v1.json','acceptance_path':'acceptance.pending-v1.json'}
for key,name in pathnames.items():newpolicy[key]=str(O/name)
policy_ref=save('preparation-policy.prospective-disabled-v1.json',newpolicy)
newspec=copy.deepcopy(spec);newspec['runtime_binding'].update(preparation=policy_ref,runtime_path=str(O/'runtime.measured.pending-v1.json'),source_record_path=str(O/'source-record.prospective-disabled-v1.json'))
# Recovery metadata is outside the closed preparation policy; runtime audit schema unchanged.
newspec['readiness_recovery']=identity_ref
spec_ref=save('engineering-r1-spec.prospective-disabled-v1.json',newspec)
for name,old,new in [('specification',spec,newspec),('preparation-policy',policy,newpolicy)]:
    save(name+'.diff', ''.join(difflib.unified_diff(json.dumps(old,indent=2,sort_keys=True).splitlines(True),json.dumps(new,indent=2,sort_keys=True).splitlines(True),fromfile='immutable-active/'+name,tofile='prospective-only/'+name)),text=True)
paths=b.source_paths(ROOT)
# Full inventory builder is prohibited here because its exact set includes Poe.
assert [p for p in paths if 'poe' in p.lower()]==['scripts/qd_ed_poe_launch.py']
oldsource=read(prior['graph']['source_record'])
assert set(paths)=={x['path'] for x in oldsource['files']}
changed=set(git('diff','--name-only',oldsource['commit'],A['source']['commit'],'--').splitlines())
assert changed=={'scripts/qd_ed_n36_readiness_prepare.py','tests/test_n36_readiness_prepare.py'}
review=read(A['review']); reviewfiles={x['path']:x for x in review['source']['files']}
source=copy.deepcopy(oldsource);source['commit']=A['source']['commit']
for row in source['files']:
    if row['path'] in changed:
        r=record(ROOT/row['path']);assert r['sha256']==reviewfiles[row['path']]['after_sha256']
        assert r['bytes']==reviewfiles[row['path']]['after_bytes']
        INPUTS[r['path']]=r;row['sha256']=r['sha256']
source['sha256']=e.w.canonical_sha(source['files'])
CHECKS.append(dict(check='source inventory prospective projection',status='PASS',detail='Prior directly bound source record plus exact two-file Git diff and reviewed working hashes. Poe entry inherited unchanged; Poe file unopened. Full source_record/verify_source not executed.'))
CHECKS.append(dict(check='initial full inventory access guard',status='EXPECTED_BLOCK',detail='v1 stopped before source_record: inventory includes scripts/qd_ed_poe_launch.py. No Poe content read; five identical prospective draft files reused after byte equality checks.'))
sourceref=save('source-record.prospective-disabled-v1.json',source)
baseline=read(spec['canonical_runtime']);runtime=copy.deepcopy(baseline)
runtime['preparation'].update(source=source['commit'],source_record=sourceref)
assert all(x is False for x in (runtime['preparation']['runtime_ready'],runtime['provider_ready'],runtime['cuda_egl_verified'],runtime['gpu_mapping']['cuda_egl_verified']))
runtimeref=save('runtime.prospective-disabled-v1.json',runtime)
oldplan=read(prior['graph']['engineering_plan']); oldaudit=read(prior['graph']['full40_audit'])
oldclosure=read(prior['graph']['runtime_closure']);closure=copy.deepcopy(oldclosure);closure['runtime']=runtimeref
closureref=save('runtime-closure.prospective-disabled-v1.json',closure)
nativeref=save('native-inventory.prospective-disabled-v1.json',read(prior['graph']['native_build']))
scope=save('scope.prospective-disabled-v1.json',dict(schema='n36-engineering-scope-v1',specification=spec_ref,scope=newspec['scope'],release_enabled=False))
accounting=save('accounting.prospective-disabled-v1.json',dict(schema='n36-engineering-accounting-v1',specification=spec_ref,accounting=newspec['accounting_proposal'],retained_ledger_prefixes=newspec['retained_ledger_prefixes'],retained_snapshot_reference=newspec['retained_snapshot_reference'],release_enabled=False,root_adopted=False))
# Keep the lexical execution deployment unchanged: no execution outputs are created.
deployment=save('deployment.prospective-disabled-v1.json',read(prior['graph']['deployment']))
fields=dict(source=source,scientific_source=source,runtime=runtimeref,runtime_closure=closureref,native_build=nativeref,scope=scope,deployment=deployment,controller_semantics=None)
audit=copy.deepcopy(oldaudit);audit.update(fields,expected_manifests={},frozen=False)
audref=save('audit-view.incomplete-prospective-disabled-v1.json',audit)
plan=copy.deepcopy(oldplan);plan.update(fields,accounting=accounting,audit_plan=audref,expected_manifests={},engineering_manifest=None,scientific_equivalence=None,frozen=False,authority=None,b5_review=None,release_enabled=False)
planref=save('engineering-plan.incomplete-prospective-disabled-v1.json',plan)
assert all(v is False for v in plan['phase_authorization'].values())
# Call the real validator only far enough to expose the first pin failure. No bypass.
try:e.validate_runtime_binding(plan)
except ValueError as exc:
    assert str(exc)=='R1 canonical runtime reference path',str(exc)
    CHECKS.append(dict(check='current production runtime binding rejects prospective path',status='EXPECTED_BLOCK',message=str(exc)))
else:raise AssertionError('source-pinned validator unexpectedly admitted draft')
try:
    from scripts.qd_ed_n36_engineering_api import for_plan
    for_plan(audit)
except ValueError as exc:
    assert str(exc)=='unknown engineering identity/specification',str(exc)
    CHECKS.append(dict(check='current production route rejects prospective specification',status='EXPECTED_BLOCK',message=str(exc)))
else:raise AssertionError('source-pinned routing unexpectedly admitted draft')

def preserve():
    expected=copy.deepcopy(spec);expected['runtime_binding'].update(preparation=policy_ref,runtime_path=newspec['runtime_binding']['runtime_path'],source_record_path=newspec['runtime_binding']['source_record_path']);expected['readiness_recovery']=identity_ref
    assert newspec==expected
    expectedpolicy=copy.deepcopy(policy);expectedpolicy['resource_id']=A['fresh_resource_id'];expectedpolicy.update({k:str(O/v) for k,v in pathnames.items()});assert newpolicy==expectedpolicy
    expectedruntime=copy.deepcopy(baseline);expectedruntime['preparation'].update(source=source['commit'],source_record=sourceref);assert runtime==expectedruntime
    expectedclosure=copy.deepcopy(oldclosure);expectedclosure['runtime']=runtimeref;assert closure==expectedclosure
    for key in ('cohort','episodes','limits','worker_contract','deadline','protocol','protocol_review','accounting'):assert audit[key]==oldaudit[key]
    for key in ('scope','accounting_proposal','retained_snapshot','retained_ledger_prefixes','binding_requirements','canonical_runtime'):assert newspec[key]==spec[key]
    for key in ('measurement_contract','mutable_runtime_fields','source_base','source_change_allowlist','accounting_contract','repair_authority','amendment'):assert newspec['runtime_binding'][key]==spec['runtime_binding'][key]
    for p,r in INPUTS.items():assert record(p)==r,p
    for key in pathnames:
        if key!='disabled_runtime_path':assert not os.path.lexists(newpolicy[key])
    assert not os.path.lexists(newspec['runtime_binding']['runtime_path'])
    return 'Only readiness identity, fresh prospective path/hash bindings, source commit/inventory and recovery metadata changed. Scientific/accounting thresholds, reserves, provider/GPU mapping/runtime audit rules and STOP/deadline preserved exactly. Evidence/release slots absent.'
check('exact prospective projections and immutable input preservation',preserve)
# Verify current ledger bindings as bytes only; no parsing or accounting mutations.
for name,r in A['ledger_prefixes'].items():
    actual=record(r['path']);assert all(actual[k]==r[k] for k in ('path','bytes','sha256'));INPUTS[r['path']]=actual
CHECKS.append(dict(check='authority ledger bytes retained',status='PASS',detail='Exact direct current ledger hashes; no records parsed or written. Historical specification prefixes remain unchanged.'))
check('source after',source_check)
remaining=[
 'Independent review of these exact prospective drafts and the consumed-identity/retained-charge binding; no review is claimed here.',
 'Separately authorized source amendment: replace only scripts/qd_ed_n36_engineering_r1.py SPECIFICATION path/hash with the reviewed prospective specification reference; preserve AMENDMENT and all audit/admission checks. Commit/review/place that source, then regenerate its source record and downstream hashes. No pin replacement was performed.',
 'Resolve the explicit frozen=false task constraint with owning authority before production audit composition: validate_audit_view requires frozen=true. This executor kept frozen=false and did not weaken that validator.',
 'Regenerate full40 and separate engineering manifests with current builders after the reviewed pin amendment and authorized audit freeze; create and verify scientific equivalence against the final source.',
 'Fresh detached owning-root controller binding attestation and accepted controller evidence for final source/runtime/closure; complete unmodified preparation.verify_graph must pass.',
 'Exact fresh preparation accounting authority/root review and dedicated owner preparation adoption must bind n36_readiness_preparation_recovery_001723, recovery_of n36_readiness_preparation_001651, its retained 0.045194898711310494 GPUh, current ledger suffix and unchanged caps/reserves; never replay or subtract the failed charge.',
 'Separate finite preparation release and exact read-only predispatch admission with both STOP paths, deadline, GPU7 isolation and unchanged official current-login codex_cli gpt-6-astra provider route.',
 'Only after separate authorization: metered live CUDA/EGL/provider preparation, terminal mirrored accounting, external proof acceptance and ready-graph refresh.',
 'Independent final B5, production protocol/source/accounting adoption, and distinct health/episode releases remain required.'
]
oldline=next(l for l in (ROOT/'scripts/qd_ed_n36_engineering_r1.py').read_text().splitlines() if l.startswith('SPECIFICATION = '))
newline='SPECIFICATION = '+repr(spec_ref)
save('minimal-follow-on-source-pin.diff','--- a/scripts/qd_ed_n36_engineering_r1.py\n+++ b/scripts/qd_ed_n36_engineering_r1.py\n@@ -37 +37 @@\n-'+oldline+'\n+'+newline+'\n',text=True)
save('remaining-gates-v1.json',dict(schema='n36-readiness-recovery-remaining-gates-v1',gates=remaining,applied=False,source_edits_authorized=False))
graph=save('graph.incomplete-prospective-disabled-v1.json',dict(schema='n36-readiness-recovery-prospective-graph-v1',status='BLOCKED_SOURCE_PIN_AND_UNFROZEN_AUDIT',identity=identity_ref,specification=spec_ref,policy=policy_ref,source_record=sourceref,runtime=runtimeref,runtime_closure=closureref,plan=planref,audit=audref,full40_manifests=None,separate_engineering_manifest=None,controller_evidence=None,scientific_equivalence=None,graph_complete=False,graph_verified=False,frozen=False,release_enabled=False,runtime_ready=False,gpu_authorized=False,provider_measurement_authorized=False,authority=None,b5_review=None,root_acceptance=None))
# Record input preservation again after all generation; every output is confined here.
check('final immutable direct-input preservation',preserve);guard()
save('commands-checks-v1.json',dict(schema='n36-recovery-focused-checks-v1',commands=COMMANDS,checks=CHECKS,stop_paths=[dict(path=p,present=False) for p in A['stop_authority']['paths']],checked_at=dt.datetime.now(dt.timezone.utc).isoformat(),deadline=A['deadline'],tests_run=[],production_manifest_builder_invocations=0,model_native_provider_gpu_invocations=0,reason='Source pin blocks production graph before manifest composition; no audit/schema bypass.'))
save('inputs-manifest-v1.json',dict(schema='direct-input-bindings-v1',files=list(INPUTS.values()),recursive_provenance_verified=False))
report=dict(schema='n36-readiness-recovery-artifact-report-v1',node_id='15.6',status='PROSPECTIVE_DRAFTS_COMPLETE_GRAPH_BLOCKED',at=dt.datetime.now(dt.timezone.utc).isoformat(),authority=ref(record(O/'authority-v1.json')),review=A['review'],source_placement=A['source_placement'],source=A['source'],resource_id=A['fresh_resource_id'],recovery_of=A['recovery_of'],retained_charge_gpu_hours=A['retained_charge_gpu_hours'],replayed=False,graph=graph,prospective_specification=spec_ref,prospective_policy=policy_ref,checks=CHECKS,remaining_exact_gates=remaining,source_edits=False,active_specification_replaced=False,source_adopted=False,root_adopted=False,independently_reviewed=False,production_readiness=False,runtime_ready=False,provider_ready=False,frozen=False,release_enabled=False,gpu_authorized=False,provider_measurement_authorized=False,episode_authorized=False,health_authorized=False,owning_state_mutation=False,graph_complete=False,graph_verified=False,b5_review=None,release=None,root_acceptance=None,stop_authority=A['stop_authority'],elapsed_seconds=time.monotonic()-START,limitations=['Graph drafts are intentionally incomplete: all40/engineering manifests, controller evidence and scientific equivalence are null or empty, and frozen is false. They fail current production validators.','The existing audit injection only supplies an audit object; it does not inject the specification or bypass pinned family routing.','Recovery metadata is a draft binding, not an accounting authority. Historical snapshot and budgets were not recalculated; later admission must account for the retained failed charge and all current suffix charges.','Only direct inputs and source inventory projection verified; full inventory verification not executed because Poe files must remain unopened. No recursive provenance, model/native payload verification, provider preflight, live readiness, independent review, cloud, credentials, agents, leases, state/checkpoint/tree/ledger/lock writes or source edits. Poe and prohibited untracked design/protected results unopened.'],manifest='outputs-manifest-v1.json')
rr=save('report-v1.json',report);save('report-v1.sha256',rr['sha256']+'  report-v1.json\n',text=True)
save('outputs-manifest-v1.json',dict(schema='generated-files-manifest-v1',files=[record(Path(__file__)),record(O/'prepare-recovery-v1.py'),record(O/'prepare-recovery-v1.log')]+list(OUTPUTS.values()),excludes=['outputs-manifest-v1.json (self-reference)','prepare-recovery-v2.log (execution stream; detached separately)'],release_enabled=False))
print(json.dumps(dict(status=report['status'],report=rr,generated_files=len(OUTPUTS)+1,elapsed_seconds=time.monotonic()-START)),flush=True)
