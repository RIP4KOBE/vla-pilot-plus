"""Disabled G5 artifacts only. Exact passive definitions, no execution authority."""
import ast, copy, datetime as dt, hashlib, json, math, os, re, resource
import signal, subprocess, sys, time, traceback, types
from pathlib import Path
from dataclasses import dataclass, asdict
from numbers import Integral, Real
from typing import Optional

OUT = Path(__file__).resolve().parent
LEX = Path('/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001543/g5-disabled-preparation')
TURNS = LEX.parents[1]
ROOT = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_adapter_001482/implementation_worktree')
HEAD = 'dcd890474b733743414d2a7711069bb0d2b0337e'
START = time.monotonic()
INPUTS, OUTPUTS, CHECKS, EXTRACTED, ERRORS = {}, {}, {}, [], []
ACCESSED, IMPORT_BLOCKS = set(), []
STAGE = 'initial'
sys.dont_write_bytecode = True
os.environ.update(PYTHONDONTWRITEBYTECODE='1', CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2', MKL_NUM_THREADS='2', GIT_OPTIONAL_LOCKS='0', GIT_NO_LAZY_FETCH='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
os.sched_setaffinity(0, sorted(os.sched_getaffinity(0))[:2])
resource.setrlimit(resource.RLIMIT_CPU, (1000, 1000))
signal.alarm(1050)

def require(ok, message):
    if not ok: raise ValueError(message)

def boundary():
    for p in [TURNS.parent/'STOP', ROOT.parents[2]/'autonomy_20261004/STOP']:
        try: p.lstat()
        except FileNotFoundError: pass
        else: raise ValueError('STOP present: '+str(p))
    require(dt.datetime.now(dt.timezone.utc) < dt.datetime.fromisoformat('2026-10-11T11:13:13+00:00'), 'deadline reached')
    require(time.monotonic()-START < 1050, 'local time budget exhausted')

def fence(event, args):
    if event in ('socket.connect', 'socket.getaddrinfo'): raise PermissionError('network forbidden')
    if event == 'import':
        name, filename = args[:2]
        if name.split('.')[0] in {'torch','numpy','scipy','pandas','sklearn','mujoco','robosuite','libero','transformers','diffusers','cv2'}:
            IMPORT_BLOCKS.append({'module':name,'reason':'model/native import forbidden'})
            raise ImportError('model/native import forbidden: '+name)
        if filename and str(filename).endswith(('.so','.pyd')) and 'site-packages' in str(filename):
            IMPORT_BLOCKS.append({'module':name,'path':filename,'reason':'third-party native extension forbidden'})
            raise ImportError('third-party native extension forbidden: '+name)
    if event == 'subprocess.Popen':
        argv=args[1]
        require(isinstance(argv,(list,tuple)) and Path(argv[0]).name=='git' and any(x in argv for x in ('rev-parse','diff')), 'only passive git allowed')
    if event == 'open' and isinstance(args[0],(str,bytes)):
        p=Path(os.path.abspath(os.fsdecode(args[0]))); low=str(p).lower()
        require('2026-08-10' not in low and '/.codex/auth' not in low and 'credential' not in low and '/formal/' not in low and '/validation/' not in low, 'prohibited read: '+str(p))
        if isinstance(args[2],int) and args[2] & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):
            require(p.resolve().is_relative_to(OUT), 'outside authorized output write: '+str(p))
        elif p.is_relative_to(ROOT): ACCESSED.add(str(p))
    if event in ('os.mkdir','os.remove','os.rmdir','os.rename'):
        for raw in args[:2] if event=='os.rename' else args[:1]:
            if isinstance(raw,(str,bytes)): require(Path(os.fsdecode(raw)).resolve().is_relative_to(OUT),'outside output mutation')

sys.addaudithook(fence)

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda:f.read(8*1024*1024),b''): h.update(chunk)
    return h.hexdigest()

def track(p):
    p=Path(p); ref={'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size}
    INPUTS[str(p)]=ref
    return ref

def ref(p):
    d=track(p); return {k:d[k] for k in ('path','sha256')}

def load(p):
    track(p); return json.loads(Path(p).read_text())

def read(r):
    require(sha(r['path'])==r['sha256'], 'hash mismatch '+r['path'])
    require('bytes' not in r or Path(r['path']).stat().st_size==r['bytes'], 'size mismatch')
    return load(r['path'])

def write(name, value):
    boundary(); p=OUT/name; p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x') as f: json.dump(value,f,sort_keys=True,separators=(',',':'),allow_nan=False)
    result={'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size}
    OUTPUTS[name]=result
    return {k:result[k] for k in ('path','sha256')}

def git(*args):
    return subprocess.check_output(['git','--no-replace-objects','-C',str(ROOT),*args],text=True).strip()

def module(name, globals=None):
    m=types.ModuleType(name); m.__dict__.update({'Path':Path,'json':json,'hashlib':hashlib,'copy':copy,'ast':ast,'os':os,'sys':sys,'re':re,'math':math,'dt':dt,'subprocess':subprocess,'ROOT':ROOT,**(globals or {})})
    sys.modules[name]=m
    if '.' in name:
        parent,leaf=name.rsplit('.',1); setattr(sys.modules[parent],leaf,m)
    return m

def extract(relative, names, m):
    p=ROOT/relative; binding=track(p)
    require(INDEX[relative]==binding['sha256'],'helper differs from accepted G2 '+relative)
    text=p.read_text(); tree=ast.parse(text); chosen=[]; assignments={}
    for n in tree.body:
        if isinstance(n,ast.Assign):
            for t in n.targets:
                if isinstance(t,ast.Name): assignments[t.id]=n
    done=set()
    def constant(name):
        if name in done: return
        node=assignments[name]
        for d in ast.walk(node.value):
            if isinstance(d,ast.Name) and isinstance(d.ctx,ast.Load) and d.id in assignments and d.id not in m.__dict__: constant(d.id)
        exec(compile(ast.Module(body=[node],type_ignores=[]),str(p),'exec'),m.__dict__)
        done.add(name); chosen.append(node)
    for name in names:
        if name in assignments: constant(name)
        else:
            n=next(n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name==name)
            exec(compile(ast.Module(body=[n],type_ignores=[]),str(p),'exec'),m.__dict__);chosen.append(n)
    m.__file__=str(p)
    EXTRACTED.append({'source':binding,'definitions':[{'name':getattr(n,'name',None) or ast.unparse(n.targets[0]),'line':n.lineno,'end_line':n.end_lineno,'definition_sha256':hashlib.sha256(ast.get_source_segment(text,n).encode()).hexdigest()} for n in chosen], 'ast_rewritten':False})
    return m

def ledger_agreement(authority, spec, review):
    result={}
    for name,r in authority['ledger_prefixes'].items():
        p=Path(r['path'])
        with p.open('rb') as f: actual=hashlib.sha256(f.read(r['bytes'])).hexdigest()
        require(actual==r['sha256'], 'retained ledger prefix changed '+name)
        for source in (spec['retained_ledger_prefixes'],review['retained_ledger_prefixes']):
            require(all(source[name][k]==r[k] for k in ('path','bytes','sha256')), 'retained prefix anchors disagree')
        result[name]={'reference':r,'prefix_agrees':True,'current_bytes':p.stat().st_size,'suffix_bytes':p.stat().st_size-r['bytes']}
    return result

def main():
    global STAGE, INDEX
    boundary();track(Path(__file__))
    authority=load(LEX/'authority-v1.json');review=read(authority['root_review']);gap=read(authority['gap_assessment'])
    accepted=read(review['report']);source=read(authority['accepted_g2_source']);equiv=read(authority['accepted_scientific_equivalence'])
    require(review['status']=='PASS_G3_G4_CPU_ONLY' and accepted['status']=='PASS','accepted G3/G4 missing')
    require(source['commit']==HEAD==authority['source']==accepted['source'] and equiv['source']==source,'accepted source binding')
    INDEX={x['path']:x['sha256'] for x in source['files']}
    require(git('rev-parse','HEAD')==HEAD and not git('diff','--name-only',HEAD,'--'),'immutable candidate changed')
    CHECKS['accepted_G2_G3_G4_consumed_directly']={'status':'PASS','source_files':len(source['files']),'recursive_provenance_rebuild':False}
    runtime_ref={k:accepted['outputs']['runtime.isolated.disabled-v1.json'][k] for k in ('path','sha256')}
    closure_ref={k:accepted['outputs']['runtime-closure.isolated.disabled-v1.json'][k] for k in ('path','sha256')}
    runtime=read(runtime_ref);closure=read(closure_ref)
    require(closure['runtime']==runtime_ref and runtime['worktree']==str(ROOT),'accepted runtime graph differs')
    require(runtime['provider_ready'] is False and runtime['cuda_egl_verified'] is False,'actual readiness cannot be claimed')
    module('scripts');module('core')
    w=extract('scripts/qd_ed_n23_worker.py',['require','sha','canonical_sha','read_ref'],module('scripts.qd_ed_n23_worker'))
    stop=extract('scripts/qd_ed_n36_stop.py',['OWNER_STOP','DATA_STOP','STOP_PATHS','DEADLINE','binding','check'],module('scripts.qd_ed_n36_stop'))
    stop.check()
    route=extract('scripts/qd_ed_n36r2_admission.py',['SESSION','OWNER'],module('scripts.qd_ed_n36r2_admission'))
    c=extract('scripts/qd_ed_n36_contract.py',['COHORT','DRAFT_N36R4_COHORT','SEPARATE_HEALTH_COHORTS','IDENTITIES','ARMS','DEADLINE','PROTOCOL_REVIEW_SHA','LIMITS','WORKER_CONTRACT','stop_path','validate_stop_binding','expected_rows','cohort','plan_rows','operational_binding'],module('scripts.qd_ed_n36_contract',{'w':w,'stop':stop}))
    e=extract('scripts/qd_ed_n36_engineering.py',['BASE','SOURCE','PREPARATION','SPECIFICATION','IDENTITY','EPISODE_KEY','PURPOSE','PLAN_SCHEMA','AUDIT_SCHEMA','LIMITS','BINDINGS','RUNTIME_INPUTS','exact','reference','read','specification','row','disabled_scope','disabled_accounting','validate_disabled_scope','validate_disabled_accounting','validate_scope_reference','validate_accounting_reference','require_row','deployment','owner_root','validate_audit_view','validate_plan_shape','audit_mapping','require_dispatch_implementation'],module('scripts.qd_ed_n36_engineering',{'w':w,'c':c,'stop':stop,'OWNER':route.OWNER,'SESSION':route.SESSION}))
    try: e.require_dispatch_implementation()
    except RuntimeError as exc: CHECKS['unconditional_dispatch_veto']={'status':'PASS','message':str(exc)}
    else: raise ValueError('dispatch veto absent')
    spec=read(e.SPECIFICATION);original_ref={k:spec['full_audit_view']['immutable_original_plan'][k] for k in ('path','sha256')};original=read(original_ref)
    CHECKS['retained_ledger_prefix_agreement']=ledger_agreement(authority,spec,review)
    retained_plan=load(ROOT/'data/qd-ed-final-plan.json'); inputs={k:retained_plan[k] for k in e.RUNTIME_INPUTS};rebindings=[]
    for stem in ('runtime_inventory','seed_plan'):
        p=ROOT/'data'/Path(inputs[stem+'_path']).name
        require(sha(p)==inputs[stem+'_sha256'],'exact original input hash missing')
        rebindings.append({'field':stem+'_path','original':inputs[stem+'_path'],'candidate':str(p),'sha256':inputs[stem+'_sha256']})
        inputs[stem+'_path']=str(p);track(p)
    write('original-input-bindings-v1.json',{'retained_plan':ref(ROOT/'data/qd-ed-final-plan.json'),'original_full_plan':original_ref,'bindings':inputs,'byte_identical_path_rebindings':rebindings})
    scope_ref=write('scope.disabled-v1.json',e.disabled_scope()); accounting_ref=write('accounting.disabled-v1.json',e.disabled_accounting())
    output=route.SESSION/'engineering-executions'/e.EPISODE_KEY
    require(not output.exists() and not output.is_symlink(),'dedicated execution output already exists')
    deployment_ref=write('deployment.disabled-v1.json',{'schema':'n36-engineering-deployment-v1','source_cwd':str(ROOT),'owner_root':str(route.OWNER),'output_root':str(output),'stop_authority':stop.binding()})
    native_ref=original['native_build']; native=read(native_ref)
    prior_controller=read(original['controller_semantics']);controller=copy.deepcopy(prior_controller)
    for key,oldref in prior_controller['review_evidence'].items():
        evidence=read(oldref);evidence.update(runtime=runtime_ref,runtime_closure=closure_ref,source_commit=HEAD,rebound_from=oldref,status='DISABLED_PENDING_ROOT_REVIEW',release_enabled=False,native_execution_observed=False,binding_review='G5 prospective hash rebinding only; inherited findings not independently reviewed against this graph. G6 pending.')
        controller['review_evidence'][key]=write('controller-evidence/'+key+'.disabled-v1.json',evidence)
    require(prior_controller['source']==closure['modules'][prior_controller['module']], 'controller source differs: requires new review, not silent rebinding')
    controller.update(runtime=runtime_ref,runtime_closure=closure_ref,source_commit=HEAD,status='DISABLED_PENDING_ROOT_REVIEW',release_enabled=False,inherited_review=original['controller_semantics'],scope='G5 disabled graph rebinding only. G6 verification and independent root review absent.')
    controller_ref=write('controller-semantics.disabled-v1.json',controller)
    common={'source':source,'scientific_source':source,'runtime':runtime_ref,'runtime_closure':closure_ref,'native_build':native_ref,'controller_semantics':controller_ref,'worktree':str(ROOT),'stop_path':c.stop_path(ROOT),'stop_authority':stop.binding(),**inputs}
    audit={k:copy.deepcopy(original[k]) for k in ('cohort','episodes','limits','worker_contract','deadline','protocol','protocol_review','accounting')}
    for k in ('protocol','protocol_review','accounting'):read(audit[k])
    audit.update(common,schema=e.AUDIT_SCHEMA,original_plan=original_ref,dispatch_authority=False,frozen=True,release_enabled=False,artifact_root=str(output/'audit-only'),phase_authorization={'dev':False,'validation':False,'formal':False},expected_manifests={},deployment=deployment_ref,scope=scope_ref,attempt_identity='episode_key')
    e.validate_audit_view(audit,require_manifests=False)
    write('audit-view.partial.disabled-v1.json',audit)
    CHECKS['original_40_rows_scientific_gates_and_routes']={'status':'PASS','rows':len(audit['episodes']),'original_fields_equal':['cohort','episodes','limits','worker_contract','deadline','protocol','protocol_review','accounting'],'manifests_required_for_complete':40}
    STAGE='manifest_helper_composition'
    policy=extract('core/codex_stage_policy.py',['_DISABLED_FEATURES','_DEVELOPER_INSTRUCTIONS','_REMOVED_ENVIRONMENT','_MAX_EVENTS_BYTES','public_invocation_policy','policy_sha256'],module('core.codex_stage_policy'))
    e1=extract('scripts/qd_ed_n4e1_plan.py',['CONDITION_ID','PROTOCOL','FROZEN_DOCS','STAGE_CONDITION','engineering_condition'],module('passive_e1'))
    runner=extract('scripts/qd_ed_final_runner.py',['PYTHON','CODEX_CONFIG_KEYS','E2_STAGE_CONDITION','CODEX_STAGE_CONDITION','owned','hydra','is_n17_plan','is_n31_plan','is_n30_plan','is_n29_plan','n4e1_support','codex_policy_module','codex_public_config','codex_public_config_sha256','stage_overrides','stage_condition','build_command'],module('scripts.qd_ed_final_runner',{'require':w.require,'_N4E1_SUPPORT':e1}))
    helper=extract('scripts/qd_ed_n32_bridge.py',['resolve_constructor','compose_launch'],module('scripts.qd_ed_n32_bridge',{'w':w,'dataclass':dataclass,'asdict':asdict,'Optional':Optional,'Integral':Integral,'Real':Real}))
    n34=extract('scripts/qd_ed_n34_bridge.py',['MODE','runtime_sources','profiles'],module('scripts.qd_ed_n34_bridge',{'w':w,'runner':runner}))
    constants=extract('core/qd_observed_jaw_approach.py',['SOURCE_FILES'],module('passive_n34_constants'))
    n36constants=extract('core/qd_nonprogress_tangent.py',['MODE','SOURCE_FILES'],module('passive_n36_constants',{'N34_SOURCES':constants.SOURCE_FILES}))
    extract('scripts/qd_ed_n36r4_admission.py',['PROTOCOL_SHA','ACCOUNTING_SHA'],module('scripts.qd_ed_n36r4_admission'))
    b=extract('scripts/qd_ed_n36_bridge.py',['_ENGINEERING_ROUTES','_ENGINEERING_IDENTITIES','profiles','command','manifest','_verify_manifest_bound','engineering_command','engineering_manifest','verify_engineering_manifest'],module('scripts.qd_ed_n36_bridge',{'w':w,'c':c,'n34':n34,'runner':runner,'compose_launch':helper.compose_launch,'SOURCE_FILES':n36constants.SOURCE_FILES,'MODE':n36constants.MODE}))
    runner.stage_overrides(runtime)
    for row in audit['episodes']:
        boundary()
        value=b.manifest(audit,runtime,row)
        audit['expected_manifests'][row['episode_key']]=write('audit-manifests/'+row['episode_key']+'.json',value)
    e.validate_audit_view(audit)
    audit_ref=write('audit-view.disabled-v1.json',audit)
    plan={**common,'schema':e.PLAN_SCHEMA,'frozen':False,'release_enabled':False,'cohort':e.IDENTITY,'purpose':e.PURPOSE,'episodes':[e.row()],'limits':e.LIMITS,'worker_contract':c.WORKER_CONTRACT,'deadline':c.DEADLINE,'attempt_identity':'episode_key','artifact_root':str(output),'scope':scope_ref,'accounting':accounting_ref,'deployment':deployment_ref,'audit_plan':audit_ref,'scientific_equivalence':{k:authority['accepted_scientific_equivalence'][k] for k in ('path','sha256')},'phase_authorization':{'engineering':False,'dev':False,'validation':False,'formal':False},'authority':None,'b5_review':None,'engineering_manifest':None,'expected_manifests':{}}
    value=b.engineering_manifest(plan,runtime,e.row(),audit=audit)
    plan['engineering_manifest']=write('diagnostic-manifest.disabled-v1.json',value)
    plan['expected_manifests']={e.EPISODE_KEY:plan['engineering_manifest']}
    e.validate_plan_shape(plan);e.audit_mapping(plan,audit,e.row())
    write('engineering-plan.disabled-v1.json',plan)
    STAGE='exact_manifest_recomparison'
    for row in audit['episodes']:
        boundary();b._verify_manifest_bound(audit['expected_manifests'][row['episode_key']],audit,runtime,row)
    b.verify_engineering_manifest(plan['engineering_manifest'],plan,runtime,e.row(),audit=audit)
    CHECKS['exact_candidate_manifest_recomparison']={'status':'PASS','audit_manifests':40,'diagnostic_manifests':1,'scientific_config_equivalence':'candidate engineering_manifest exact comparison','full_release_verifier_run':False}
    CHECKS['disabled_plan_shape_and_exact_mapping']={'status':'PASS','authority':None,'b5_review':None,'scope_exhaustion_not_executed':True}
    CHECKS['retained_ledger_prefix_agreement_final']=ledger_agreement(authority,spec,review)
    require(git('rev-parse','HEAD')==HEAD and not git('diff','--name-only',HEAD,'--'),'candidate mutated')
    require(not output.exists(),'execution directory was created')
    STAGE='G5_disabled_graph_complete'

def finish(status):
    for p in sorted(ACCESSED):
        if Path(p).is_file():track(p)
    write('passive-extraction-provenance-v1.json',{'definitions':EXTRACTED,'verification_semantics_edited':False,'production_modules_imported':False,'optional_import_rejections':IMPORT_BLOCKS})
    # Hash configuration-composition libraries actually loaded; do not execute them again.
    config_modules=[]
    for name,m in list(sys.modules.items()):
        if name.split('.')[0] in {'hydra','omegaconf','antlr4','yaml','packaging'}:
            p=getattr(m,'__file__',None)
            if p and Path(p).is_file():config_modules.append({'module':name,'source':track(p)})
    write('configuration-composition-modules-v1.json',{'modules':config_modules,'third_party_native_extensions_loaded':False})
    write('failed-attempts-v1.json',{'failures':ERRORS,'inspection_failures':[{'stage':'initial accepted report inspection','detail':'An initial summary command serialized the large accepted report; tool output was truncated. Corrected to key/count summaries; no artifact or scientific inference used truncated inventory.'}],'optional_import_rejections':IMPORT_BLOCKS})
    count=sum(k.startswith('audit-manifests/') for k in OUTPUTS)
    now=dt.datetime.now(dt.timezone.utc);remaining=(dt.datetime.fromisoformat('2026-10-11T11:13:13+00:00')-now).total_seconds()
    result={'schema':'n36-g5-disabled-preparation-report-v1','at':now.isoformat(),'node_id':'15.6','status':status,'stage':STAGE,'source':HEAD,'source_adopted':False,'source_edited':False,'goal_complete':False,'score':None,'inputs':list(INPUTS.values()),'outputs':OUTPUTS,'checks':CHECKS,'errors':ERRORS,'counts':{'original_rows':40,'audit_manifests':count,'diagnostic_manifests':int('diagnostic-manifest.disabled-v1.json' in OUTPUTS)},'release_enabled':False,'dispatch_enabled':False,'accounting_adopted':False,'owner_state_or_ledger_written':False,'execution_output_created':False,'scientific_eligible':False,'full_cohort_execution_authorized':False,'native_gpu_model_provider_execution':False,'actual_after_load_readiness':False,'fresh_device_provider_readiness':False,'tests_run':0,'unresolved':['G6: native-build binary graph verification, refreshed controller root review, and independent B5 absent. Disabled controller rebinding inherits findings only.','G7: unconditional source dispatch veto, owner source/accounting adoption, detached health/episode releases, actual after-load/device/provider readiness unresolved.'],'clock':{'deadline':'2026-10-11T11:13:13Z','remaining_seconds':remaining,'full_cohort_required_seconds':75600,'full_cohort_fits':remaining>=75600,'diagnostic_required_seconds':2100,'clock_fit_is_not_release':True},'cpu_affinity':sorted(os.sched_getaffinity(0)),'elapsed_seconds':time.monotonic()-START,'verification_scope':'Disabled artifact shapes, exact retained identities/gates, and exact candidate manifest regeneration only; no full verify_audit_closure readiness claim. Definitions extracted by standard-library AST without rewriting; config composition uses original Hydra/OmegaConf helper with non-standard native imports blocked.','next_step':'Parent review of this disabled report only. No owner adoption or execution authority.'}
    p=OUT/'report-v1.json'
    with p.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({'status':status,'stage':STAGE,'counts':result['counts'],'errors':ERRORS,'report':str(p)}),flush=True)

if __name__=='__main__':
    try:
        main();finish('PASS')
    except Exception as exc:
        ERRORS.append({'stage':STAGE,'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()})
        finish('BLOCKED')
