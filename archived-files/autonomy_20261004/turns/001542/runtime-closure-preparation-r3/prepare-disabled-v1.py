"""CPU artifact-only G3-G4 preparation consuming accepted G2; no implementation edits, imports or dispatch."""
import ast, copy, datetime as dt, hashlib, json, os, resource, signal, subprocess, sys, time, traceback, types
from pathlib import Path
sys.dont_write_bytecode = True
OUT = Path(__file__).resolve().parent
LEX = Path('/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001542/runtime-closure-preparation-r3')
TURNS = LEX.parents[1]
ROOT = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_adapter_001482/implementation_worktree')
HEAD = 'dcd890474b733743414d2a7711069bb0d2b0337e'
START = time.monotonic()
INPUTS, OUTPUTS, CHECKS, ERRORS = {}, {}, {}, []
HASH_CACHE = {}
STAGE = 'initial'
os.environ.update(CUDA_VISIBLE_DEVICES='', GIT_OPTIONAL_LOCKS='0', GIT_NO_LAZY_FETCH='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', PYTHONDONTWRITEBYTECODE='1')
os.sched_setaffinity(0, sorted(os.sched_getaffinity(0))[:2])
resource.setrlimit(resource.RLIMIT_CPU, (550, 550))
signal.alarm(650)
def require(ok, message):
    if not ok: raise ValueError(message)
def boundary():
    require(not (TURNS.parent/'STOP').exists(), 'STOP present: no new work')
    require(dt.datetime.now(dt.timezone.utc) < dt.datetime.fromisoformat('2026-10-11T11:13:13+00:00'), 'deadline reached: no new work')
def fence(event, args):
    if event in ('socket.connect', 'socket.getaddrinfo'): raise PermissionError('network forbidden')
    if event == 'import':
        require(args[0].split('.')[0] not in {'torch','numpy','scipy','pandas','sklearn','mujoco','robosuite','libero','transformers','diffusers','cv2','hydra','omegaconf'}, 'native/model/config import forbidden: '+args[0])
    if event == 'subprocess.Popen':
        argv = args[1]
        require(isinstance(argv,(tuple,list)) and Path(argv[0]).name=='git' and any(x in argv for x in ('rev-parse','diff','ls-tree','cat-file','merge-base')), 'only passive Git allowed')
    if event == 'open' and isinstance(args[0],(str,bytes)):
        p = Path(os.path.abspath(os.fsdecode(args[0]))); low = str(p).lower()
        require(not any(x in low for x in ('2026-08-10-eds-qd-stage-guidance-transition-design.md','/.codex/auth','/poe','poe_','/formal/')) and ('/validation/' not in low or str(p).startswith('/home/hynx/miniconda3/envs/vla-pilot/lib/python3.12/site-packages/wandb/vendor/graphql-core-1.1/wandb_graphql/validation/')) and ('credential' not in low or str(p) == '/home/hynx/miniconda3/envs/vla-pilot/lib/python3.12/site-packages/huggingface_hub/utils/_git_credential.py'), 'prohibited read: '+str(p))
        if isinstance(args[2],int) and args[2] & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):
            require(p==Path('/dev/null') or p.resolve().is_relative_to(OUT), 'outside output write: '+str(p))
    if event in ('os.rename','os.remove','os.rmdir','os.mkdir'):
        for raw in args[:2] if event=='os.rename' else args[:1]:
            if isinstance(raw,(str,bytes)): require(Path(os.fsdecode(raw)).resolve().is_relative_to(OUT), 'outside mutation')
sys.addaudithook(fence)
def sha(p):
    boundary()
    p=Path(p); st=p.stat(); key=(str(p.resolve()),st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns)
    if key not in HASH_CACHE:
        h=hashlib.sha256()
        with p.open('rb') as f:
            for chunk in iter(lambda:f.read(8*1024*1024),b''): h.update(chunk)
        after=p.stat(); require((after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns)==key[1:], 'file changed while hashing '+str(p))
        HASH_CACHE[key]=h.hexdigest()
    if not p.resolve().is_relative_to(OUT.resolve()): INPUTS[str(p)]={'path':str(p),'bytes':st.st_size,'sha256':HASH_CACHE[key]}
    return HASH_CACHE[key]
def ref(p):
    p=Path(p); return {'path':str(p),'sha256':sha(p)}
def track(p):
    p=Path(p); r={**ref(p),'bytes':p.stat().st_size}; INPUTS[str(p)]=r; return r
def load(p):
    track(p); return json.loads(Path(p).read_text())
def read(r):
    require(sha(r['path'])==r['sha256'] and ('bytes' not in r or Path(r['path']).stat().st_size==r['bytes']),'reference mismatch '+r['path']); return load(r['path'])
def write(name,value):
    p=OUT/name; p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x') as f: json.dump(value,f,sort_keys=True,separators=(',',':'),allow_nan=False)
    OUTPUTS[name]={**ref(p),'bytes':p.stat().st_size}; return ref(p)
def report(status):
    value={'schema':'n36-g3-g4-disabled-preparation-report-v1','at':dt.datetime.now(dt.timezone.utc).isoformat(),'node_id':'15.6','status':status,'stage':STAGE,'source':HEAD,'candidate_worktree':str(ROOT),'owner_scientific_source':'1065f38122379a515b60a9a424f574330405b66f','owner_adopted_source':'bee9f6a4703e9d5d802d6b8c7950b69beefac4c0','inputs':list(INPUTS.values()),'outputs':OUTPUTS,'checks':CHECKS,'errors':ERRORS,'elapsed_seconds':time.monotonic()-START,'source_edited':False,'source_adopted':False,'dispatch_enabled':False,'release_enabled':False,'goal_complete':False,'scientific_promotion_eligible':False,'after_load_receipts_created':False,'fresh_device_provider_readiness':False,'tests_run':0,'verification_method':'Unmodified passive helper definitions extracted from hash-bound candidate AST; standard library only; no production module import. No live native/model/provider execution.','commands':['PYTHONDONTWRITEBYTECODE=1 /home/hynx/miniconda3/envs/vla-pilot/bin/python -B '+str(OUT/'prepare-disabled-v1.py')],'reproduction_note':'Script creates immutable outputs and refuses overwrite. To reproduce, copy script and authority/root-review/gap references to a new authorized artifact directory and update OUT/LEX routes under separate authorization, or passively inspect retained hashes.','unresolved_gaps':['G5 full disabled 40-row audit and 40+1 manifests','G6 native/controller graph verification and independent B5','G7 separately reviewed implementation and prospective owner adoption; unconditional dispatch veto remains','Actual after-load receipts and fresh provider/device readiness remain absent'],'next_bounded_step':'Return to parent for review. G5/G6/G7 unresolved; no G5 expansion authorized in this task.'}
    p=OUT/'report-v1.json'; tmp=OUT/'report-v1.tmp.json'; tmp.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n'); tmp.replace(p)
def git(*args):
    return subprocess.check_output(['git','--no-replace-objects','-C',str(ROOT),*args],text=True).strip()
def extract(path,names,ns):
    track(path); require(sha(path)==ACCEPTED_INDEX[str(path.relative_to(ROOT))], 'passive helper differs from accepted G2'); tree=ast.parse(path.read_text()); nodes=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names]
    require({n.name for n in nodes}==set(names),'helper missing '+str(names)); exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),ns); return ns
def constant(path,name):
    track(path); tree=ast.parse(path.read_text()); node=next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in n.targets))
    if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='frozenset': return frozenset(ast.literal_eval(node.args[0]))
    return ast.literal_eval(node)
def check(name,func):
    t=time.monotonic(); result=func(); CHECKS[name]={'status':'PASS','seconds':time.monotonic()-t}; print(name,'PASS',flush=True); return result

def main():
    global STAGE, ACCEPTED_INDEX
    track(Path(__file__))
    boundary()
    authority=load(LEX/'authority-v1.json'); review=read(authority['root_review']); prior=read(authority['prior_scope']); track(authority['prior_script']['path']); gap=read(prior['gap_assessment'])
    source=read(authority['accepted_source']); equiv=read(authority['accepted_scientific_equivalence'])
    require(review['status']=='PASS_G2_SOURCE_CLOSURE_ONLY' and review['source']==authority['accepted_source'] and review['scientific_equivalence']==authority['accepted_scientific_equivalence'],'G2 acceptance binding differs')
    require(source['commit']==HEAD and equiv['source']==source and equiv['scientific_changes'] is False and len(source['files'])==1110,'accepted G2 inventory differs')
    ACCEPTED_INDEX={x['path']:x['sha256'] for x in source['files']}
    sr=ref(authority['accepted_source']['path']); eqref=ref(authority['accepted_scientific_equivalence']['path'])
    CHECKS['G2_consumed_not_rebuilt']={'status':'PASS','source_files':1110,'accepted_dependency_entries':review['verified_materialized_entries'],'accepted_exact_symlinks':review['verified_exact_internal_symlinks']}
    write('accepted-g2-binding-v1.json',{'review':authority['root_review'],'source':sr,'scientific_equivalence':eqref,'accepted_counts':CHECKS['G2_consumed_not_rebuilt'],'accounting_retained':gap['accounting'],'ledger_prefixes':authority['ledger_prefixes'],'scientific_gates_unchanged':True})
    require(authority['source']==HEAD and authority['source_edits_authorized'] is False and authority['gpu_authorized'] is False,'authority differs')
    require(git('rev-parse','HEAD')==HEAD,'candidate HEAD differs')
    require(not git('diff','--name-only',HEAD,'--'),'tracked candidate dirty')
    olddir=TURNS/'001467/recovery-preparation'
    retained={Path(r['path']).name:r for r in gap['inputs'] if str(olddir) in r['path']}
    oldruntime=read(retained['runtime.isolated.disabled-v1.json']); oldclosure=read(retained['runtime-closure.isolated.disabled-v1.json'])
    wn={'Path':Path,'hashlib':hashlib,'json':json,'subprocess':subprocess,'os':os,'require':require}
    extract(ROOT/'scripts/qd_ed_n23_worker.py',{'_source_git','_source_entry','canonical_sha'},wn)
    wn.update(sha=sha,read_ref=read); w=types.SimpleNamespace(**wn)
    sp=ROOT/'scripts/qd_ed_n34_source.py'; track(sp); require(sha(sp)==next(x['sha256'] for x in source['files'] if x['path']==str(sp.relative_to(ROOT))), 'closure helper differs from accepted source')
    sn={'__file__':str(sp),'__name__':'passive_source','w':w}
    tree=ast.parse(sp.read_text()); nodes=[n for n in tree.body if not(isinstance(n,ast.ImportFrom) and n.module=='scripts')]
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(sp),'exec'),sn); s=types.SimpleNamespace(**sn)
    en={}
    extract(ROOT/'scripts/qd_ed_n36_engineering.py',{'require_dispatch_implementation'},en)
    try: en['require_dispatch_implementation']()
    except RuntimeError as exc: CHECKS['dispatch_veto']={'status':'PASS','message':str(exc)}
    else: raise ValueError('unconditional veto absent')
    STAGE='G3'
    oldroot=oldruntime['worktree']; runtime=copy.deepcopy(oldruntime); index={str(ROOT/x['path']):x['sha256'] for x in source['files']}
    cache_map={v['cache_dir']:str(OUT/'task-caches'/('task_'+k)) for k,v in oldruntime['tasks'].items()}
    route_map={oldroot:str(ROOT),**cache_map}
    def route(x):
        if isinstance(x,str):
            for before,after in route_map.items(): x=x.replace(before,after)
            return x
        if isinstance(x,list): return [route(v) for v in x]
        if isinstance(x,dict): return {k:route(v) for k,v in x.items()}
        return x
    # Copy only complete, inventoried task-cache bytes. Never consult source_cache provenance paths.
    task_checks=[]
    oldindex={x['path']:x for x in oldruntime['files']}
    for key,task in oldruntime['tasks'].items():
        files=sorted(p for p in Path(task['cache_dir']).rglob('*') if p.is_file())
        require(files,'empty task cache')
        for p in files:
            require(str(p) in oldindex,'task cache unbound '+str(p)); r=oldindex[str(p)]
            require(sha(p)==r['sha256'] and p.stat().st_size==r['size_bytes'],'task cache bytes changed '+str(p))
            q=Path(route(str(p))); q.parent.mkdir(parents=True,exist_ok=True)
            with q.open('xb') as f: f.write(p.read_bytes())
            require(sha(q)==r['sha256'],'cache copy mismatch')
        meta=load(Path(task['cache_dir'])/'metadata.json'); identity=meta['qd_ed_task_identity']
        require(all(identity[k]==task[k] for k in identity),'cache task identity differs')
        for name,digest in task['canonical_reward_sha256'].items(): require(sha(Path(route(task['cache_dir']))/name)==digest,'canonical reward differs')
        task_checks.append({'task_id':int(key),'cache_dir':route(task['cache_dir']),'file_count':len(files),'identity':identity,'byte_identical':True})
    runtime=route(runtime); updates=[]
    for before,row in zip(oldruntime['files'],runtime['files']):
        p=Path(row['path']); require(p.is_file(),'runtime file missing '+str(p))
        digest=sha(p); expected=index.get(str(p),before['sha256'])
        require(digest==expected,'runtime bytes contract mismatch '+str(p)+' expected='+expected+' actual='+digest)
        row.update(sha256=digest,size_bytes=p.stat().st_size,resolved_path=str(p.resolve()))
        if before!=row: updates.append({'before':before,'after':copy.deepcopy(row)})
    for k in ('cuda_egl_verified','metadata_mapping_verified','provider_ready'): runtime[k]=False
    runtime['cuda_egl_probe']=None; runtime['provider_evidence']=None
    for k in ('cuda_egl_verified','metadata_mapping_verified','drm_pci_verified'): runtime['gpu_mapping'][k]=False
    runtime['preparation']={'source':HEAD,'source_record':sr,'cohort':'N36_ENGINEERING_C0_TASK0_001479','status':'DISABLED_CPU_PREPARATION','runtime_ready':False,'release_enabled':False,'historical_runtime':retained['runtime.isolated.disabled-v1.json'],'historical_readiness_is_not_current':True}
    require(runtime['worktree']==str(ROOT),'runtime route differs')
    require(runtime['frozen_stage_provider']==oldruntime['frozen_stage_provider'],'provider configuration changed')
    require(oldroot not in json.dumps({k:v for k,v in runtime.items() if k!='preparation'}),'old source route retained')
    rn={'Path':Path,'os':os,'require':require,'digest':sha}
    extract(ROOT/'scripts/qd_ed_final_runner.py',{'verify_files'},rn)
    check('G3_all_runtime_paths_bytes_sizes',lambda:rn['verify_files'](runtime['files'],allowed_roots=(str(ROOT),runtime['artifact_root'])))
    rr=write('runtime.isolated.disabled-v1.json',runtime)
    write('task-cache-rebinding-v1.json',{'runtime':rr,'retained_runtime':retained['runtime.isolated.disabled-v1.json'],'source':sr,'tasks':task_checks,'content_changes':False})
    write('runtime-rebinding-provenance-v1.json',{'retained_runtime':retained['runtime.isolated.disabled-v1.json'],'runtime':rr,'source':sr,'route_map':route_map,'updates':updates,'removed_entries':[],'provider_configuration_unchanged':True,'historical_readiness_is_not_current':True,'historical_readiness':{k:oldruntime.get(k) for k in ('gpu_mapping','cuda_egl_probe','provider_ready','provider_evidence','provider_frozen_at')},'all_files_hashed':len(runtime['files'])})
    CHECKS['G3_task_cache_identity_and_canonical_rewards']={'status':'PASS','tasks':len(task_checks),'copied_files':sum(x['file_count'] for x in task_checks)}
    report('PARTIAL_G3_VERIFIED')
    STAGE='G4'; closure=copy.deepcopy(oldclosure); module_updates=[]
    for name,rec in closure['modules'].items():
        before=copy.deepcopy(rec); rec['path']=route(rec['path'])
        if rec['path'] in index: rec['sha256']=index[rec['path']]
        if before!=rec: module_updates.append({'module':name,'before':before,'after':copy.deepcopy(rec)})
    closure['runtime']=rr
    for key in ('generated_modules','module_aliases','required_after','interpreter','distribution_versions','versions'):
        require(closure[key]==oldclosure[key],'retained closure rule changed '+key)
    check('G4_production_verify_runtime_closure',lambda:s.verify_runtime(closure,rr))
    cr=write('runtime-closure.isolated.disabled-v1.json',closure)
    dino=[x for x in runtime['files'] if '/facebookresearch_dinov2_main/' in x['path']]
    require(dino and dino==[x for x in oldruntime['files'] if '/facebookresearch_dinov2_main/' in x['path']],'DINO passive inventory changed')
    dino_modules={k:v for k,v in closure['modules'].items() if 'dinov2' in k or '/facebookresearch_dinov2_main/' in v['path']}
    write('dino-lazy-passive-inventory-v1.json',{'runtime':rr,'runtime_closure':cr,'files':dino,'prospective_modules':dino_modules,'all_hashes_checked':True,'model_constructed':False,'lazy_import_execution_covered':False,'boundary':'Passive inventory is not evidence of model-construction or lazy-import execution; live source origins and required-after receipts remain future.'})
    write('generated-module-required-after-v1.json',{'runtime_closure':cr,'generated_modules':closure['generated_modules'],'module_aliases':closure['module_aliases'],'required_after':closure['required_after'],'exact_retained_rules_preserved':True,'generator_template_and_prospective_content_verified':True,'interpreter_and_distributions_verified':True,'ordinary_module_count':len(closure['modules']),'module_updates':module_updates,'actual_after_load_observed':False,'receipts':[]})
    CHECKS['G4_preserved_generated_alias_required_after_inventory']={'status':'PASS','ordinary_modules':len(closure['modules']),'generated_rules':len(closure['generated_modules']),'required_after':len(closure['required_after']),'dino_files':len(dino),'dino_prospective_modules':len(dino_modules)}
    require(git('rev-parse','HEAD')==HEAD and not git('diff','--name-only',HEAD,'--'),'candidate changed during preparation')
    require(not any(n.split('.')[0] in {'torch','numpy','mujoco','robosuite','transformers','libero'} for n in sys.modules),'prohibited import occurred')
    CHECKS['immutable_candidate_and_no_native_model_imports']={'status':'PASS'}
    STAGE='G3_G4_complete'; boundary(); report('PASS')
try:
    main()
except BaseException as exc:
    ERRORS.append({'stage':STAGE,'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()}); report('BLOCKED_EXACT_CONTRACT_MISMATCH' if isinstance(exc,(ValueError,FileNotFoundError)) else 'BLOCKED_PREPARATION_ERROR'); print(traceback.format_exc(),flush=True); sys.exit(1)
