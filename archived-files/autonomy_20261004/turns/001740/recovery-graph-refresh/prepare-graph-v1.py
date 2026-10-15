"""Bounded CPU projections and precise blockers; never grants graph acceptance."""
import ast, copy, datetime as dt, hashlib, json, os, subprocess, sys, time, traceback
from pathlib import Path
sys.dont_write_bytecode = True
O = Path(__file__).absolute().parent
A = json.loads((O/'authority-v1.json').read_text())
ROOT = Path(A['source']['worktree']); T = O.parents[1]
START = time.monotonic(); INPUTS = {}; OUTPUTS = {}; CHECKS = []; COMMANDS = []; BLOCKERS = []
os.environ.update(GIT_OPTIONAL_LOCKS='0', GIT_NO_LAZY_FETCH='1', PYTHONDONTWRITEBYTECODE='1')
def guard():
    assert time.monotonic()-START < 1000, 'executor CPU bound'
    assert dt.datetime.now(dt.timezone.utc) < dt.datetime.fromisoformat(A['deadline'].replace('Z','+00:00')), 'deadline'
    assert all(not os.path.lexists(p) for p in A['stop_authority']['paths']), 'STOP present'
def record(p):
    p=Path(p)
    assert 'poe' not in p.name.lower() and '2026-08-10' not in str(p), 'prohibited input'
    data=p.read_bytes(); return dict(path=str(p),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
def ref(r): return {k:r[k] for k in ('path','sha256')}
def read(r):
    guard(); actual=record(r['path'])
    assert all(actual[k]==r[k] for k in ('sha256','bytes') if k in r), 'input hash: '+r['path']
    INPUTS[actual['path']]=actual
    return json.loads(Path(actual['path']).read_text())
def save(p,d,text=False):
    guard(); p=Path(p)
    assert any(p.resolve().is_relative_to(Path(r).resolve()) for r in A['allowed_output_roots']), 'output root'
    assert not os.path.lexists(p), 'existing output conflict: '+str(p)
    p.parent.mkdir(parents=True,exist_ok=True)
    data=d.encode() if text else json.dumps(d,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    with p.open('xb') as f: f.write(data)
    OUTPUTS[str(p)]=record(p);return ref(OUTPUTS[str(p)])
def git(*args):
    guard(); q=subprocess.run(['git','--no-replace-objects','-C',str(ROOT),*args],capture_output=True,text=True,check=True,timeout=60)
    COMMANDS.append(dict(argv=q.args,stdout=q.stdout,stderr=q.stderr,returncode=q.returncode));return q.stdout.strip()
def check(name,fn):
    guard(); t=time.monotonic(); result=fn()
    CHECKS.append(dict(check=name,status='PASS',detail=result,elapsed_seconds=time.monotonic()-t)); print(name,'PASS',flush=True)
def block(id,detail,locations):
    BLOCKERS.append(dict(id=id,blocking=True,detail=detail,locations=locations))
def source_check():
    assert git('rev-parse','HEAD')==A['source']['commit']
    assert git('rev-parse','HEAD^{tree}')==A['source']['tree']
    assert git('diff','--name-only')==git('diff','--cached','--name-only')==''
    return 'Reviewed HEAD/tree and clean tracked source; no untracked content inspected.'
# Runtime audit hook prevents accidental forbidden reads/imports and writes outside outputs.
def audit_hook(event,args):
    if event=='open' and isinstance(args[0],(str,bytes)):
        name=os.fsdecode(args[0]); low=name.lower()
        if 'poe' in Path(name).name.lower() or '2026-08-10' in name:
            raise PermissionError('prohibited file read: '+name)
        mode=args[1]; flags=args[2]
        writing=(isinstance(mode,str) and any(x in mode for x in 'wax+')) or (isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC))
        if writing and not any(Path(name).resolve().is_relative_to(Path(r).resolve()) for r in A['allowed_output_roots']):
            raise PermissionError('out-of-scope write: '+name)
    if event=='import' and args[0].split('.')[0] in ('torch','mujoco','robosuite','transformers','diffusers'):
        raise PermissionError('model/native import prohibited: '+args[0])
sys.addaudithook(audit_hook)
graphref=None
try:
    guard(); read(record(O/'authority-v1.json'))
    for k in ('standing_authority','review','source_placement'): read(A[k])
    summary=read(record(T/'001739/operational-summary-v1.json'))
    review=read(A['review']); assert review['verdict']=='PASS_SCOPED_SOURCE_REVIEW'
    contract=read(A['canonical_contract']); spec=read(A['canonical_specification']); slots=read(A['downstream_slots']); S=slots['slots']
    assert all(not os.path.lexists(p) for p in list(S.values())+slots['full40_manifests']), 'reserved outputs already exist'
    check('exact source before',source_check)
    for r in A['ledger_prefixes'].values():
        actual=record(r['path']);assert all(actual[k]==r[k] for k in actual); INPUTS[actual['path']]=actual
    r723=read(record(T/'001723/readiness-recovery-graph/report-v1.json')); g723=read(r723['graph'])
    r707=read(record(T/'001707/disabled-graph-refresh/report-v1.json'))
    for p in (T/'001707/disabled-graph-refresh/prepare-graph-v1.py',T/'001723/readiness-recovery-graph/prepare-recovery-v2.py'):
        INPUTS[str(p)]=record(p)
    sys.path.insert(0,str(ROOT));os.chdir(ROOT)
    from scripts import qd_ed_n36_engineering_r1 as e, qd_ed_n36_bridge as b, qd_ed_n36_readiness_prepare as prep, qd_ed_n36_stop as stop
    from scripts.qd_ed_n36_engineering_api import for_plan
    assert stop.binding()==A['stop_authority'];stop.check()
    check('real pinned specification and exact raw recovery-prefix admission',lambda: e.exact(e.specification(),spec,'canonical pinned specification'))
    policy=prep.policy(spec); assert policy==read(spec['runtime_binding']['preparation'])
    assert policy['resource_id']==A['fresh_resource_id']==contract['successor']['resource_id']
    assert contract['predecessor']['resource_id']==A['recovery_of']
    assert contract['predecessor']['retained_charge_gpu_hours']==A['retained_charge_gpu_hours']
    assert contract['predecessor']['telemetry_complete'] is False
    assert spec['retained_ledger_prefixes']==contract['original_ledger_prefixes']
    assert policy['disabled_runtime_path']==S['disabled_runtime'] and spec['runtime_binding']['source_record_path']==S['source_record']
    CHECKS.append(dict(check='original accounting offsets and charged predecessor',status='PASS',detail='Exact real contract admission retained original prefixes, mirrored raw predecessor and explicit unconsumed successor; no historical readiness accepted.'))
    oldsource=read(g723['source_record']); paths=b.source_paths(ROOT)
    assert set(paths)=={x['path'] for x in oldsource['files']}
    changed=set(git('diff','--name-only',oldsource['commit'],A['source']['commit'],'--').splitlines())
    assert changed=={'scripts/qd_ed_n36_engineering_r1.py','tests/test_n36_engineering_r1.py'}
    source=copy.deepcopy(oldsource);source['commit']=A['source']['commit']; reviewed={x['path']:x['after'] for x in review['source_files']}
    for row in source['files']:
        if row['path'] in changed:
            actual=record(ROOT/row['path']);assert actual['sha256']==reviewed[row['path']]['sha256'] and actual['bytes']==reviewed[row['path']]['bytes']
            INPUTS[actual['path']]=actual;row['sha256']=actual['sha256']
    source['sha256']=e.w.canonical_sha(source['files'])
    sr=save(S['source_record'],source)
    CHECKS.append(dict(check='final source inventory projection',status='PASS',detail='1116 inherited inventory entries; exact two-file Git diff and reviewed SHA256/bytes updated. Unchanged Poe hash inherited without opening Poe. This is not full source closure verification.'))
    block('B1_POE_SOURCE_CLOSURE','Full source_record/verify_source necessarily reads scripts/qd_ed_poe_launch.py; Poe must remain unopened. Final inventory is a hash-bound projection, not freshly verified complete source closure. validate_runtime_binding invokes verify_source before audit shape checks.', ['scripts/qd_ed_n34_source.py:339','scripts/qd_ed_n34_source.py:367','scripts/qd_ed_n36_engineering_r1.py:123'])
    baseline=read(spec['canonical_runtime']);runtime=copy.deepcopy(baseline);runtime['preparation'].update(source=source['commit'],source_record=sr)
    assert all(v is False for v in (runtime['preparation']['runtime_ready'],runtime['provider_ready'],runtime['cuda_egl_verified'],runtime['gpu_mapping']['cuda_egl_verified']))
    rr=save(S['disabled_runtime'],runtime)
    oldplan=read(g723['plan']);oldaudit=read(g723['audit']);oldclosure=read(g723['runtime_closure'])
    closure=copy.deepcopy(oldclosure);closure['runtime']=rr;cr=save(S['runtime_closure'],closure)
    native=read(oldplan['native_build']);nr=save(S['native_build'],native)
    scope=save(S['scope'],e.disabled_scope());accounting=save(S['accounting'],e.disabled_accounting());deployment=save(S['deployment'],read(oldplan['deployment']))
    basis=r707['graph']['controller_semantics'];proof=read(basis)
    def proposal(d,prior):
        d=copy.deepcopy(d);assert d['status']=='PENDING_INDEPENDENT_AND_ROOT_REVIEW'
        d.update(runtime=rr,runtime_closure=cr,source_commit=source['commit'],at=dt.datetime.now(dt.timezone.utc).isoformat())
        d['reference_refresh_lineage']=dict(prior_evidence=prior,prior_status='PENDING_INDEPENDENT_AND_ROOT_REVIEW',semantic_findings_unchanged=True,new_root_approval=False,independent_certification=False,preparation_authority=ref(record(O/'authority-v1.json')))
        return d
    proof=proposal(proof,basis)
    for name,r in proof['review_evidence'].items():
        proof['review_evidence'][name]=save(O/('controller-'+name+'.proposed-disabled-v1.json'),proposal(read(r),r))
    assert proof['source']==closure['modules'][proof['module']]
    proofref=save(S['controller_semantics'],proof)
    from scripts.qd_ed_n34_controller import verify_semantics
    try: verify_semantics(proofref,rr,closure)
    except ValueError as exc:
        assert str(exc)=='reviewed controller semantics required'
        CHECKS.append(dict(check='real controller acceptance gate',status='BLOCKED',message=str(exc)))
    else: raise AssertionError('pending controller proposal unexpectedly accepted')
    block('B2_CONTROLLER_REVIEW','Controller binding refreshed as PENDING_INDEPENDENT_AND_ROOT_REVIEW. Real verify_semantics rejects it: reviewed controller semantics required. No fresh external root binding attestation or independent B5 supplied.', ['scripts/qd_ed_n34_controller.py:42'])
    changedall=git('diff','--name-only',e.BASE,source['commit'],'--').splitlines()
    assert set(changedall)<=e.OPERATIONAL_FILES
    eq=save(S['scientific_equivalence'],dict(schema='n36-engineering-scientific-equivalence-v1',base_commit=e.BASE,source=source,changed_paths=sorted(changedall),scientific_changes=False))
    fields=dict(source=source,scientific_source=source,runtime=rr,runtime_closure=cr,native_build=nr,controller_semantics=proofref,scope=scope,deployment=deployment)
    audit=copy.deepcopy(oldaudit);audit.update(fields,expected_manifests={},frozen=False,release_enabled=False)
    ar=save(S['audit_view'],audit)
    plan=copy.deepcopy(oldplan);plan.update(fields,accounting=accounting,scientific_equivalence=eq,audit_plan=ar,engineering_manifest=None,expected_manifests={},frozen=False,release_enabled=False,authority=None,b5_review=None)
    assert all(v is False for v in plan['phase_authorization'].values()) and all(v is False for v in audit['phase_authorization'].values())
    pr=save(S['engineering_plan'],plan)
    check('real family route for canonical plan and audit',lambda: (e.exact(for_plan(plan).SPECIFICATION,e.SPECIFICATION,'plan route'),e.exact(for_plan(audit).SPECIFICATION,e.SPECIFICATION,'audit route')))
    check('real scientific source equivalence validator',lambda:e.scientific_equivalence(plan))
    check('loaded operational source bytes',lambda: sorted(b.attest_loaded(ROOT,source)))
    # Static inspection is used here because executing the gate reads forbidden Poe bytes first.
    tree=ast.parse((ROOT/'scripts/qd_ed_n36_engineering_r1.py').read_text())
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='validate_audit_view')
    required=next(n for n in ast.walk(node) if isinstance(n,ast.Compare) and ast.unparse(n)=="plan['frozen'] is True")
    block('B3_FROZEN_AUDIT','Task requires all frozen flags false/null. Unmodified validate_audit_view requires audit frozen is True. bridge.manifest -> command -> validate_audit_view and engineering_manifest -> audit_mapping -> validate_audit_view therefore cannot generate the requested 40+1 manifests under this authority. No alternate schema, validator bypass or synthetic manifests used.', ['scripts/qd_ed_n36_engineering_r1.py:'+str(required.lineno),'scripts/qd_ed_n36_bridge.py:49','scripts/qd_ed_n36_bridge.py:160'])
    CHECKS.append(dict(check='production manifest prerequisites',status='BLOCKED',method='exact reviewed AST and call-site inspection',manifest_builder_invocations=0))
    # Only projections, no native imports, model files, provider calls or recursive provenance checks.
    def preserve():
        expected=copy.deepcopy(baseline);expected['preparation'].update(source=source['commit'],source_record=sr);assert runtime==expected
        expected=copy.deepcopy(oldclosure);expected['runtime']=rr;assert closure==expected
        for k in ('cohort','episodes','limits','worker_contract','deadline','protocol','protocol_review','accounting'):assert audit[k]==oldaudit[k]
        assert audit['stop_authority']==plan['stop_authority']==A['stop_authority']
        assert len(audit['episodes'])==40
        assert [(x['task_id'],x['profile']) for x in audit['episodes']]==[(i,p) for i in range(10) for p in ('C0','Q0','N34','N36')]
        for path,r in INPUTS.items():assert record(path)==r, path
        assert all(not os.path.lexists(p) for p in list(S.values())+slots['full40_manifests'] if p not in OUTPUTS)
        return 'Exact baseline runtime projection retains provider/GPU mapping/rules. Original science, STOP/deadline, accounting prefixes/caps/reserves and all four complete journal hashes unchanged. Uncreated evidence/manifest/approval slots remain absent.'
    check('science budgets journals and unused reserved slots preserved',preserve)
    check('exact source after',source_check)
    graphref=save(S['graph'],dict(schema='n36-readiness-recovery-prospective-graph-v1',status='BLOCKED_INCOMPLETE_DISABLED_GRAPH',specification=ref(A['canonical_specification']),policy=spec['runtime_binding']['preparation'],recovery_prefix_contract=ref(A['canonical_contract']),resource_id=A['fresh_resource_id'],recovery_of=A['recovery_of'],retained_charge_gpu_hours=A['retained_charge_gpu_hours'],source_record=sr,runtime=rr,runtime_closure=cr,native_build=nr,controller_semantics=proofref,scientific_equivalence=eq,audit=ar,plan=pr,full40_manifests=None,separate_engineering_manifest=None,graph_complete=False,graph_verified=False,release_enabled=False,frozen=False,runtime_ready=False,provider_ready=False,gpu_authorized=False,provider_measurement_authorized=False,authority=None,b5_review=None,root_acceptance=None,blockers=BLOCKERS))
except Exception as exc:
    BLOCKERS.append(dict(id='UNEXPECTED_GENERATION_BLOCK',blocking=True,detail=str(exc),traceback=traceback.format_exc()));print(traceback.format_exc(),flush=True)
finally:
    # No failure is converted into permission or an acceptance artifact.
    checkref=save(O/'command-evidence-v1.json',dict(schema='n36-focused-cpu-command-evidence-v1',invocation=[sys.executable,'-B',str(Path(__file__).absolute())],commands=COMMANDS,checks=CHECKS,manifest_builder_invocations=0,model_native_provider_gpu_invocations=0,tests_run=[],recursive_provenance_rebuilt=False))
    inref=save(O/'inputs-manifest-v1.json',dict(files=list(INPUTS.values()),recursive_provenance_verified=False))
    artifacts=save(O/'generated-artifact-manifest-v1.json',dict(schema='n36-exact-generated-artifact-manifest-v1',files=[record(Path(__file__).absolute())]+list(OUTPUTS.values()),scope='Builder, exact graph artifacts, command evidence and input manifest. Report and detached digest are final envelopes listed separately in outputs-manifest-v1.json.',graph_complete=False))
    requirements=[
      'Owning root must resolve frozen=false versus the unchanged audit frozen=true contract before any production all40/engineering composition; executor has no authority to change either.',
      'Complete source verification requires a root-authorized resolution of the unopened Poe constraint; inherited source inventory projection is not complete fresh attestation.',
      'Fresh independent engineering B5 and root controller/source/protocol/scope/accounting adoption must bind final source, exact canonical graph, resource n36_readiness_preparation_recovery_001723, original offsets and retained charged aborted predecessor 001651.',
      'Recompose all 40 and separate engineering manifests and pass all unmodified graph/native/runtime/controller validations; no acceptance inferred from projections or prior review.',
      'Exact released-graph/production integration checks, operation-lock/capture consistency, fresh full budget/margin/protected reserves and idle-resource/one-use admission require separate authority.',
      'Separate finite preparation release, fresh measured proof and external acceptance; then distinct health/episode releases. Historical readiness cannot be reused.'
    ]
    report=dict(schema='n36-readiness-recovery-graph-refresh-report-v1',node_id='15.6',status='BLOCKED_INCOMPLETE_DISABLED_GRAPH',at=dt.datetime.now(dt.timezone.utc).isoformat(),authority=ref(record(O/'authority-v1.json')),source=A['source'],graph=graphref,generated_artifact_manifest=artifacts,command_evidence=checkref,input_manifest=inref,blockers=BLOCKERS,resource_id=A['fresh_resource_id'],recovery_of=A['recovery_of'],retained_charge_gpu_hours=A['retained_charge_gpu_hours'],independent_b5_and_root_adoption_requirements=requirements,elapsed_builder_seconds=time.monotonic()-START,maximum_executor_seconds=1200,source_edits=False,source_adopted=False,active_specification_adopted=False,owning_state_mutation=False,ledger_writes=False,graph_complete=False,graph_verified=False,release_enabled=False,frozen=False,runtime_ready=False,provider_ready=False,production_readiness=False,gpu_authorized=False,provider_measurement_authorized=False,health_authorized=False,episode_authorized=False,scientific_success=False,authority_created=None,b5_review=None,release=None,root_acceptance=None,generated_audit_manifest_count=0,generated_engineering_manifest_count=0,poe_files_opened=False,prohibited_design_or_protected_results_read=False,stop_authority=A['stop_authority'],limitations=['Final inventory is prior bound inventory plus reviewed two-file projection; full source verifier intentionally not run.','Runtime/closure/native inventory are disabled reference projections, not fresh measured readiness or native payload attestation.','40+1 manifests absent because immutable production prerequisites conflict with explicit task constraints; no placeholders in reserved slots.','Controller proposal is pending; real controller validator rejects it. No source repair or authority adoption performed.'])
    rr=save(O/'report-v1.json',report)
    save(O/'report-v1.sha256',rr['sha256']+'  report-v1.json\n',text=True)
    save(O/'outputs-manifest-v1.json',dict(schema='exact-executor-output-manifest-v1',files=[record(Path(__file__).absolute())]+list(OUTPUTS.values()),excludes=['outputs-manifest-v1.json (self reference)','builder-stdout-v1.log (execution stream, recorded by command-receipt-v1.json)']))
    print(json.dumps(dict(status=report['status'],report=rr,blockers=[x['id'] for x in BLOCKERS],outputs=len(OUTPUTS))),flush=True)
