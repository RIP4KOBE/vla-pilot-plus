import os, sys, json, hashlib, ast, math, signal, resource, datetime, subprocess, time
from pathlib import Path
OUT = Path(__file__).absolute().parent
ROOT = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r3_generated_import_001299/implementation_worktree')
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
os.environ.update(CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2', MKL_NUM_THREADS='2', PYTHONDONTWRITEBYTECODE='1')
os.sched_setaffinity(0, sorted(os.sched_getaffinity(0))[:2])
resource.setrlimit(resource.RLIMIT_CPU, (240, 240))
signal.alarm(360)
from scripts import qd_ed_n36_stop as stop
stop.check(need=360)
from scripts import qd_ed_n36_bridge as b, qd_ed_n36_contract as c, qd_ed_n36r3_admission as a, qd_ed_n23_worker as w
checks = []
reads = {}
def ref(path):
    path = Path(path)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
original_read = w.read_ref
def read(reference):
    value = original_read(reference)
    reads[reference['path']] = reference['sha256']
    return value
w.read_ref = read
def check(name, fn):
    stop.check()
    started = time.monotonic()
    try:
        result = fn()
        row = {'check': name, 'status': 'PASS', 'result': result}
    except Exception as e:
        row = {'check': name, 'status': 'FAIL', 'error': type(e).__name__ + ': ' + str(e)}
    row['seconds'] = round(time.monotonic() - started, 3)
    checks.append(row)
    print(json.dumps(row), flush=True)
def require(v, msg):
    if not v: raise ValueError(msg)
authority = json.loads((OUT/'authority-v1.json').read_text())
plan = read(authority['plan'])
bindings = read(authority['bindings'])
runtime = read(plan['runtime'])
closure = read(plan['runtime_closure'])
def exact():
    require(subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==authority['source']==plan['source']['commit'], 'HEAD/source mismatch')
    require(bindings == {'schema':'n36r3-refresh-bindings-draft-v1','plan':ref(Path(authority['plan']['path']).resolve()), **{k:plan[k] for k in a.BINDINGS},'expected_manifests':plan['expected_manifests'],'release_enabled':False,'worker_receipts_are_future':True,'target_met':False,'score':None}, 'binding envelope mismatch')
    return {'binding_fields': list(a.BINDINGS), 'source_files':len(plan['source']['files'])}
check('authority hashes, exact source HEAD and full disabled binding envelope', exact)
check('existing validate_draft (bounded direct contract references; no owner journals)', lambda: (c.validate_draft(plan), 'accepted')[1])
check('lexical owner versus isolated SOURCE routing', lambda: str(a.owner_root(plan)))
check('existing verify_sources including committed blobs and pinned dependency source', lambda: (b.verify_sources(plan),len(plan['source']['files']))[1])
def manifests():
    require(len(plan['episodes'])==len(plan['expected_manifests'])==40,'not forty')
    result=[]
    for row in plan['episodes']:
        r=plan['expected_manifests'][row['episode_key']]
        m=b._verify_manifest_bound(r,plan,runtime,row)
        require(Path(m['output_dir']).is_relative_to(Path(plan['artifact_root'])),'artifact escape')
        result.append({'episode_key':row['episode_key'], **r})
    return result
check('all 40 exact manifests recomposed through production API', manifests)
check('existing verify_runtime: pinned interpreter, 6767 modules, generated content, native aliases, required_after and installed metadata', lambda: (b.closure.verify_runtime(closure,plan['runtime']), {'modules':len(closure['modules']),'required_after':closure['required_after'],'generated_modules':closure['generated_modules'],'module_aliases':closure['module_aliases']})[1])
from scripts.qd_ed_n34_controller import verify_semantics
check('existing controller verify_semantics with all three deployed-source review bindings', lambda: {'status':verify_semantics(plan['controller_semantics'],plan['runtime'],closure)['status']})
def native():
    # Execute only the production manifest validator and its REQUIRED constant.
    # Avoid module-level torch import: no native library loading or device calls.
    tree=ast.parse((ROOT/'scripts/qd_ed_n36_build.py').read_text())
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='manifest' or isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='REQUIRED' for t in n.targets)]
    ns={'Path':Path,'w':w}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'scripts/qd_ed_n36_build.py','exec'),ns)
    value=ns['manifest'](plan['native_build'])
    return {'libraries':len(value['libraries']), 'torch_version':value['torch_version'],'cuda_version':value['cuda_version'],'mode':'pure production manifest function; no torch import'}
check('native inventory existing pure manifest validator',native)
def unchanged():
    refresh=read(ref(Path(authority['plan']['path']).parent/'report-v1.json'))
    prior=read(refresh['prior_plan'])
    changed=[k for k in set(prior)|set(plan) if prior.get(k)!=plan.get(k)]
    require(set(changed)=={'controller_semantics','artifact_root','expected_manifests'},'unexpected refresh delta')
    require(plan['episodes']==c.expected_rows(ROOT,cohort=c.DRAFT_N36R3_COHORT),'science rows differ')
    require(plan['deadline']=='2026-10-11T11:13:13Z','deadline')
    return {'changed_fields': sorted(changed),'rows':'ten dev tasks x C0/Q0/N34/N36','limits':plan['limits'],'worker_contract':plan['worker_contract']}
check('unchanged scientific identities, modes, gates and exact refresh delta',unchanged)
def released_rejection():
    from scripts.qd_ed_n36_release import validate_plan
    try: validate_plan(plan)
    except ValueError as e: return str(e)
    raise ValueError('draft accepted as release')
check('actual released-plan consumer rejects exact draft',released_rejection)
def pause():
    from scripts.qd_ed_n36_supervise import first_c0_boundary
    require(first_c0_boundary(plan['episodes'][0]),'first C0 boundary absent')
    require(not any(first_c0_boundary(r) for r in plan['episodes'][1:]),'extra boundary')
    return {'first_row':plan['episodes'][0]['episode_key'],'disposition':'mandatory PAUSED_FOR_ROOT_G3 after valid terminal; other terminal failure is INVALID_STOP; no override'}
check('first-C0 boundary predicate on exact matrix (no rollout)',pause)
def standing():
    s=read(authority['standing_authority'])
    require(s['approved'] is True and s['continuous_window']['end_utc']==c.DEADLINE,'standing window')
    return {'approved':True,'deadline':c.DEADLINE}
check('standing authorization hash and deadline only',standing)
stop.check()
payload={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'authority':ref(OUT/'authority-v1.json'),'plan':authority['plan'],'bindings':authority['bindings'],'source':authority['source'],'checks':checks,'read_bindings':reads,'cpu_affinity':sorted(os.sched_getaffinity(0)),'stop_paths':list(stop.STOP_PATHS),'deadline':c.DEADLINE,'score':None,'target_met':False,'release_enabled':False}
with (OUT/'checks-v1.json').open('x') as f: json.dump(payload,f,indent=2);f.write('\n')
