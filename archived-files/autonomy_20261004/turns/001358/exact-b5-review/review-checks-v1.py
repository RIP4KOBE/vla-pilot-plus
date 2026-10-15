"""Independent leaf 15.6 bounded CPU checks; never invokes preparation or release."""
import os, sys, json, hashlib, datetime as dt, time, signal, resource, copy, ast, math
from pathlib import Path
OUT = Path(__file__).resolve().parent
ROOT = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r3_generated_import_001299/implementation_worktree')
BASE = OUT.parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
os.environ.update(CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2', MKL_NUM_THREADS='2', NUMEXPR_NUM_THREADS='2', PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(OUT))
os.sched_setaffinity(0, sorted(os.sched_getaffinity(0))[:2])
resource.setrlimit(resource.RLIMIT_CPU, (360, 360))
signal.alarm(480)
started = time.monotonic()
checks, reads = [], {}
def ref(path):
    path = Path(path)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
def read(reference):
    assert ref(reference['path'])['sha256'] == reference['sha256'], reference
    reads[reference['path']] = reference['sha256']
    return json.loads(Path(reference['path']).read_text())
def write(name, value):
    p = OUT/name
    with p.open('x') as f:
        json.dump(value, f, indent=2, allow_nan=False); f.write('\n')
    return ref(p)
def check(name, fn):
    tick = time.monotonic()
    try:
        result = fn()
        item = {'name':name, 'status':'PASS', 'result':result}
    except Exception as exc:
        item = {'name':name, 'status':'FAIL', 'error':type(exc).__name__+': '+str(exc)}
    item['seconds'] = time.monotonic()-tick
    checks.append(item)
    print(json.dumps(item), flush=True)
def rejected(fn):
    try: fn()
    except (ValueError, KeyError, TypeError) as exc: return str(exc)
    raise AssertionError('negative unexpectedly accepted')
from scripts import qd_ed_n36_stop as stop
stop.check(need=480)
from scripts import qd_ed_n36_bridge as b, qd_ed_n36_contract as c, qd_ed_n36r3_admission as a
from scripts import qd_ed_n23_worker as w, qd_ed_n36_release as release, qd_ed_n36_supervise as supervise
original_read = w.read_ref
def traced_read(r):
    result = original_read(r)
    reads[r['path']] = r['sha256']
    return result
w.read_ref = traced_read
authority_ref = ref(OUT/'authority-v1.json')
authority = read(authority_ref)
plan, bindings = read(authority['plan']), read(authority['bindings'])
runtime, closure = read(plan['runtime']), read(plan['runtime_closure'])
prior_report_ref = ref(BASE/'001348/exact-b5-review/report-v1.json')
prior_report = read(prior_report_ref)
prior_plan = read(prior_report['plan'])
def stop_and_authority():
    stop.check(need=480)
    standing = read(authority['standing_authority'])
    assert standing['continuous_window']['end_utc'] == plan['deadline'] == c.DEADLINE == '2026-10-11T11:13:13Z'
    assert authority['node_id']=='15.6' and authority['gpu_authorized'] is False and authority['source_edits_authorized'] is False
    return {'at':dt.datetime.now(dt.timezone.utc).isoformat(), 'stop_paths':list(stop.STOP_PATHS), 'entries':'absent including dangling symlinks', 'deadline':c.DEADLINE, 'cpu_affinity':sorted(os.sched_getaffinity(0))}
check('STOP/deadline/authority', stop_and_authority)
def envelope():
    c.validate_draft(plan)
    assert bindings == {'schema':'n36r3-refresh-bindings-draft-v1', 'plan':ref(Path(authority['plan']['path']).resolve()), **{k:plan[k] for k in a.BINDINGS}, 'expected_manifests':plan['expected_manifests'], 'release_enabled':False, 'worker_receipts_are_future':True, 'target_met':False, 'score':None}
    assert len(plan['episodes'])==len(plan['expected_manifests'])==40
    return {'BINDINGS':list(a.BINDINGS), 'release_rejection':rejected(lambda:release.validate_plan(plan))}
check('exact disabled envelope and draft consumer', envelope)
def source():
    b.verify_sources(plan)
    assert plan['source']['commit']==authority['source']=='21fc93e5667a83520401282d4ba8e945f954f99b'
    import subprocess
    delta=subprocess.check_output(['git','diff','--name-only',prior_plan['source']['commit'],authority['source']],cwd=ROOT,text=True).splitlines()
    assert delta==['scripts/qd_ed_n36_release.py','tests/test_n36r3_owner_alias.py'],delta
    old={v['path']:v['sha256'] for v in prior_plan['source']['files']};new={v['path']:v['sha256'] for v in plan['source']['files']}
    assert sorted(k for k in old.keys()|new.keys() if old.get(k)!=new.get(k))==delta
    return {'files':len(new),'previous_accepted_source':prior_plan['source']['commit'],'changed_or_added':delta}
check('committed source closure and sole accepted delta', source)
def runtime_check():
    b.closure.verify_runtime(closure,plan['runtime'])
    old=read(prior_plan['runtime_closure'])
    assert {k:v for k,v in old.items() if k not in ('runtime','modules')}=={k:v for k,v in closure.items() if k not in ('runtime','modules')}
    changed=sorted(k for k in old['modules'].keys()|closure['modules'].keys() if old['modules'].get(k)!=closure['modules'].get(k))
    assert changed==['scripts.qd_ed_n36_release'],changed
    previous_runtime=read(prior_plan['runtime'])
    changed_runtime=sorted(k for k in runtime.keys()|previous_runtime.keys() if runtime.get(k)!=previous_runtime.get(k))
    assert set(changed_runtime)<= {'files','preparation','preparation_history','cuda_egl_probe'},changed_runtime
    assert runtime['worktree']==str(ROOT) and runtime['frozen_stage_provider']['backend']=='codex_cli'
    assert runtime['stage_recovered_error_condition']==b.runner.E2_STAGE_CONDITION
    b.runner.stage_overrides(runtime)
    required=read(ref(BASE/'001355/binding-refresh/required-after.production-v1.json'))
    assert required=={'required_after':closure['required_after'],'runtime_closure':plan['runtime_closure'],'observed_loaded_after':False,'process_bound_lifecycle_evidence':False}
    assert closure['required_after']==['_remote_module_non_scriptable','robosuite.controllers.osc','transformers.models.t5.modeling_t5','transformers.models.siglip.modeling_siglip','_cyutility']
    return {'module_count':len(closure['modules']),'changed_modules':changed,'runtime_changed_top_level':changed_runtime,'required_after':required,'generated_modules':closure['generated_modules'],'module_aliases':closure['module_aliases'],'actual_loaded_worker_evidence':False}
check('runtime/generated/alias/required_after contracts',runtime_check)
def native():
    # Compile only the existing passive validator, excluding Torch import/attest.
    path=ROOT/'scripts/qd_ed_n36_build.py';tree=ast.parse(path.read_text())
    subset=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='manifest' or isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='REQUIRED' for t in n.targets)]
    ns={'Path':Path,'w':w};exec(compile(ast.Module(body=subset,type_ignores=[]),str(path),'exec'),ns)
    value=ns['manifest'](plan['native_build'])
    assert value==read(prior_plan['native_build'])
    return {'library_count':len(value['libraries']),'unchanged_from_accepted_B5':True,'no_library_load_or_probe':True}
check('native passive inventory validator',native)
def controller():
    from scripts.qd_ed_n34_controller import verify_semantics
    proof=verify_semantics(plan['controller_semantics'],plan['runtime'],closure)
    assert proof['source_commit']==authority['source'] and proof['runtime_closure']==plan['runtime_closure']
    old=read(prior_plan['controller_semantics'])
    assert all(proof[k]==old[k] for k in ('module','class','source','instance','semantics','physical_gain_certified'))
    return {'proof':plan['controller_semantics'],'evidence':proof['review_evidence'],'actual_instance_evidence':False}
check('accepted 001357 controller proof exact consumer',controller)
def manifests():
    result=[]
    expected={f'n36r3_dev_t{t:02d}_{arm.lower()}_001314' for t in range(10) for arm in ('C0','Q0','N34','N36')}
    assert set(plan['expected_manifests'])==expected
    for row in plan['episodes']:
        reference=plan['expected_manifests'][row['episode_key']]
        m=b._verify_manifest_bound(reference,plan,runtime,row)
        assert m['row']==row and m['controller_semantics']==plan['controller_semantics'] and m['resource_routing']==plan['resource_routing']
        assert Path(m['output_dir']).is_relative_to(plan['artifact_root'])
        result.append({'episode_key':row['episode_key'],**reference,'recomputed_equal':True})
    return result
check('40 exact prospective manifest recompositions',manifests)
def science():
    preparation=read(ref(BASE/'001358/manifest-refresh/report-v1.json'))
    old=read(preparation['prior_plan'])
    changed=sorted(k for k in old.keys()|plan.keys() if old.get(k)!=plan.get(k))
    assert changed==['artifact_root','controller_semantics','expected_manifests']
    stable=('episodes','protocol','protocol_review','accounting','limits','worker_contract','deadline','cohort','phase_authorization','http_counters','resource_routing')
    assert all(plan[k]==prior_plan[k] for k in stable)
    return {'refresh_delta':changed,'equal_to_001348_accepted_fields':list(stable),'scientific_gates':read(plan['protocol_review'])['scientific_decisions']}
check('scientific identities/gates and bounded refresh delta',science)
def owner_alias():
    owner=a.owner_root(plan)
    alias=Path(release.N36R3_OWNER_ALIAS)
    assert alias.resolve(strict=True)==owner and alias.is_dir() and alias.samefile(owner)
    # Synthetic scalar state only, passed to the actual read-only gate.
    cap=copy.deepcopy(c.CAPS); authority_stub={'caps':cap,'amendment':{'synthetic':True}}
    state={'worktree':str(alias),'canonical_worktree':str(owner),'n36_budget_authority':plan['authority'],'gpu_pool':[7],'max_concurrent_gpu_workers':1,
      'budget':{'max_episode_attempts':cap['attempts'],'max_gpu_hours':cap['gpu_hours'],'reserved':cap['buckets'],'gpu_hour_reservations':cap['protected_gpu_hours'],'amendment':authority_stub['amendment']},
      'resource_isolation':{'status':'ACTIVE','validation_status':'PASS','private_budget':True}}
    before=copy.deepcopy(state);release.validate_state(plan,authority_stub,state);assert state==before
    state['worktree']=str(owner);release.validate_state(plan,authority_stub,state)
    negatives={}
    for key,value in [('canonical_worktree',str(ROOT)),('worktree',str(ROOT)),('worktree',str(owner)+'/.')]:
        bad=copy.deepcopy(state);bad[key]=value
        negatives[key+'='+value]=rejected(lambda:release.validate_state(plan,authority_stub,bad))
    return {'owner':str(owner),'source':str(a.SOURCE),'historical_alias':str(alias),'live_alias_identity_matches':True,'synthetic_gate_only':True,'negative_cases':negatives,'owning_state_not_read':True}
check('owner/source routing and owner-alias delta gate',owner_alias)
def pause():
    assert [i for i,row in enumerate(plan['episodes']) if supervise.first_c0_boundary(row)]==[0]
    row=plan['episodes'][0]
    # In-memory synthetic lifecycle proves only the pure pause predicate.
    common={'attempt_id':row['episode_key'],'episode_key':row['episode_key'],'identity':supervise.c_identity(row),'budget_bucket':row['budget_bucket'],'replacement':None}
    events=[{**common,'event':kind} for kind in ('reserved','dispatched','valid')]
    events[-1].update(outcome_valid=True,required_cost_telemetry_complete=True,success=False)
    result=supervise.reconcile(plan,events,lambda *_:None)
    assert result['status']=='PAUSED_FOR_ROOT_G3' and result['next_row'] is None
    invalid=copy.deepcopy(events);invalid[-1]['outcome_valid']=False
    assert supervise.reconcile(plan,invalid,lambda *_:None)['status']=='INVALID_STOP'
    return {'first_row':row['episode_key'],'valid_terminal_status':result['status'],'next_row':None,'invalid_terminal_status':'INVALID_STOP','synthetic_only_not_G3':True}
check('first-C0 mandatory G3 pause',pause)
def continuity():
    refs={k:v for k,v in prior_report['preserved_reviews'].items() if k.startswith(('001334','001340'))}
    refs.update({'001348_B5':prior_report_ref,'001354_alias_acceptance':ref(BASE/'001354/operational-summary.json'),'001357_controller':plan['controller_semantics']})
    for r in refs.values():read(r)
    return refs
check('accepted review continuity (direct artifacts only)',continuity)
b5_ref=None
if all(x['status']=='PASS' for x in checks):
    value={'schema':'n36r3-independent-b5-review-v1','decision':'PASS_PREPARATION_REQUIRES_ROOT_RELEASE',**{k:plan[k] for k in a.BINDINGS},'worker_receipts_are_future':True,'release_enabled':False}
    b5_ref=write('b5-review-v1.json',value)
    def b5_consumer():
        p=copy.deepcopy(plan);p['b5_review']=b5_ref;a.independent_review(p)
        negatives={}
        for k in a.BINDINGS:
            bad=copy.deepcopy(p);bad[k]={'deliberately_invalid':True}
            negatives[k]=rejected(lambda:a.independent_review(bad))
        wrong=copy.deepcopy(plan);wrong['b5_review']=ref(Path(authority['bindings']['path']).resolve())
        return {'accepted':b5_ref,'rejected_changed_bindings':negatives,'envelope_rejected':rejected(lambda:a.independent_review(wrong))}
    check('exact independent B5 consumer and ten binding negatives',b5_consumer)
stop.check()
assert ref(authority['plan']['path'])==authority['plan'] and ref(authority['bindings']['path'])==authority['bindings']
result={'schema':'n36r3-independent-b5-cpu-checks-v1','at':dt.datetime.now(dt.timezone.utc).isoformat(),'elapsed_seconds':time.monotonic()-started,'checks':checks,'all_pass':all(x['status']=='PASS' for x in checks),'b5_review':b5_ref,'read_references':reads,'stop_final':'both absent; deadline open','score':None,'target_met':False,'release_enabled':False}
write('checks-v1.json',result)
print(json.dumps({'all_pass':result['all_pass'],'elapsed_seconds':result['elapsed_seconds'],'b5_review':b5_ref}),flush=True)
