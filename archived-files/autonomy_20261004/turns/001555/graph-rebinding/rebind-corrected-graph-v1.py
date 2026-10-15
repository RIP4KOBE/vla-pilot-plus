"""Disabled G5 artifacts only. Exact passive definitions, no execution authority."""
import ast, copy, datetime as dt, hashlib, json, math, os, re, resource
import signal, subprocess, sys, time, traceback, types
from pathlib import Path
from dataclasses import dataclass, asdict
from numbers import Integral, Real
from typing import Optional

OUT = Path(__file__).resolve().parent / 'prepared'
LEX = Path('/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001555/graph-rebinding')
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


SETUP_CODE = "    module('scripts');module('core')\n    w=extract('scripts/qd_ed_n23_worker.py',['require','sha','canonical_sha','read_ref'],module('scripts.qd_ed_n23_worker'))\n    stop=extract('scripts/qd_ed_n36_stop.py',['OWNER_STOP','DATA_STOP','STOP_PATHS','DEADLINE','binding','check'],module('scripts.qd_ed_n36_stop'))\n    stop.check()\n    route=extract('scripts/qd_ed_n36r2_admission.py',['SESSION','OWNER'],module('scripts.qd_ed_n36r2_admission'))\n    c=extract('scripts/qd_ed_n36_contract.py',['SEPARATE_HEALTH_COHORTS','COHORT','DRAFT_N36R4_COHORT','IDENTITIES','ARMS','DEADLINE','PROTOCOL_REVIEW_SHA','LIMITS','WORKER_CONTRACT','stop_path','validate_stop_binding','expected_rows','cohort','plan_rows','operational_binding'],module('scripts.qd_ed_n36_contract',{'w':w,'stop':stop}))\n    e=extract('scripts/qd_ed_n36_engineering.py',['BASE','SOURCE','PREPARATION','SPECIFICATION','IDENTITY','EPISODE_KEY','PURPOSE','PLAN_SCHEMA','AUDIT_SCHEMA','LIMITS','BINDINGS','RUNTIME_INPUTS','exact','reference','read','specification','row','disabled_scope','disabled_accounting','validate_disabled_scope','validate_disabled_accounting','validate_scope_reference','validate_accounting_reference','require_row','deployment','owner_root','validate_audit_view','validate_plan_shape','audit_mapping','require_dispatch_implementation'],module('scripts.qd_ed_n36_engineering',{'w':w,'c':c,'stop':stop,'OWNER':route.OWNER,'SESSION':route.SESSION}))\n    policy=extract('core/codex_stage_policy.py',['_DISABLED_FEATURES','_DEVELOPER_INSTRUCTIONS','_REMOVED_ENVIRONMENT','_MAX_EVENTS_BYTES','public_invocation_policy','policy_sha256'],module('core.codex_stage_policy'))\n    e1=extract('scripts/qd_ed_n4e1_plan.py',['CONDITION_ID','PROTOCOL','FROZEN_DOCS','STAGE_CONDITION','engineering_condition'],module('passive_e1'))\n    runner=extract('scripts/qd_ed_final_runner.py',['PYTHON','CODEX_CONFIG_KEYS','E2_STAGE_CONDITION','CODEX_STAGE_CONDITION','owned','hydra','is_n17_plan','is_n31_plan','is_n30_plan','is_n29_plan','n4e1_support','codex_policy_module','codex_public_config','codex_public_config_sha256','stage_overrides','stage_condition','build_command'],module('scripts.qd_ed_final_runner',{'require':w.require,'_N4E1_SUPPORT':e1}))\n    helper=extract('scripts/qd_ed_n32_bridge.py',['resolve_constructor','compose_launch'],module('scripts.qd_ed_n32_bridge',{'w':w,'dataclass':dataclass,'asdict':asdict,'Optional':Optional,'Integral':Integral,'Real':Real}))\n    n34=extract('scripts/qd_ed_n34_bridge.py',['MODE','runtime_sources','profiles'],module('scripts.qd_ed_n34_bridge',{'w':w,'runner':runner}))\n    constants=extract('core/qd_observed_jaw_approach.py',['SOURCE_FILES'],module('passive_n34_constants'))\n    n36constants=extract('core/qd_nonprogress_tangent.py',['MODE','SOURCE_FILES'],module('passive_n36_constants',{'N34_SOURCES':constants.SOURCE_FILES}))\n    extract('scripts/qd_ed_n36r4_admission.py',['PROTOCOL_SHA','ACCOUNTING_SHA'],module('scripts.qd_ed_n36r4_admission'))\n    b=extract('scripts/qd_ed_n36_bridge.py',['_ENGINEERING_ROUTES','_ENGINEERING_IDENTITIES','profiles','command','manifest','_verify_manifest_bound','engineering_command','engineering_manifest','verify_engineering_manifest'],module('scripts.qd_ed_n36_bridge',{'w':w,'c':c,'n34':n34,'runner':runner,'compose_launch':helper.compose_launch,'SOURCE_FILES':n36constants.SOURCE_FILES,'MODE':n36constants.MODE}))\n"
CPU_START=time.process_time()
ROOTS={}; CHANGES=[]; LEDGERS={}
UNRESOLVED=[
 {'gate':'G6_independent_B5','status':'ABSENT','reason':'This preparation is not independent B5. Review must bind the exact graph roots below.'},
 {'gate':'G7_dispatch_implementation','status':'VETO_UNCONDITIONAL','reason':'Unchanged candidate require_dispatch_implementation raises unconditionally; launch_guard invokes it first.'},
 {'gate':'G7_owner_adoption_and_releases','status':'UNRESOLVED','reason':'No source/accounting adoption, authority grant, root protocol acceptance or detached health/episode releases.'},
 {'gate':'G7_actual_readiness','status':'NOT_OBSERVED','reason':'No after-load native/build, controller instance, loaded postprocessor/decode path, fresh device/EGL/provider observations.'},
 {'gate':'scientific_execution','status':'NOT_AUTHORIZED','reason':'Original forty science rows and gates preserved; validation/formal/required ablations not executed.'}]
def checked(name,ok,**detail):
    CHECKS[name]={'pass':bool(ok),**detail};require(ok,name)
def pair(r): return {k:r[k] for k in ('path','sha256')}
def ledgers(label):
    rows={}
    for name,r in AUTH['ledger_prefixes'].items():
        actual=track(r['path']); checked(label+'_'+name,actual==r)
        rows[name]=actual
    LEDGERS[label]=rows

def unchanged(old,new,allowed,label):
    changed=sorted(k for k in set(old)|set(new) if old.get(k)!=new.get(k))
    checked(label,set(old)==set(new) and set(changed)<=set(allowed),changed_keys=changed,allowed_keys=allowed)
    return changed

def main():
    global AUTH, INDEX, STAGE, G5
    boundary(); track(__file__); track('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001552/graph-rebinding/rebind-graph-attempt-4-v1.py')
    AUTH=load(LEX/'authority-v1.json')
    checked('initial_stop_deadline',True,paths=[str(TURNS.parent/'STOP'),str(ROOT.parents[2]/'autonomy_20261004/STOP')],at=dt.datetime.now(dt.timezone.utc).isoformat())
    read(AUTH['standing_authority']);cr=read(AUTH['controller_review']);g5review=read(AUTH['accepted_g5_review']);g6review=read(AUTH['g6_reconciliation'])
    G5=read(g5review['report']);g6=read(g6review['report'])
    checked('accepted_statuses',g5review['status']=='PASS_G5_DISABLED_ARTIFACTS_ONLY' and cr['status']=='PASS_SOURCE_SEMANTICS_ONLY' and not g6['effective_check_failures'])
    for r in g6['outputs'].values() if isinstance(g6['outputs'],dict) else g6['outputs']:
        if isinstance(r,dict) and 'path' in r: read(r)
    oldplan=read(G5['outputs']['engineering-plan.disabled-v1.json']); oldaudit=read(G5['outputs']['audit-view.disabled-v1.json'])
    checked('old_plan_audit_ref',oldplan['audit_plan']==pair(G5['outputs']['audit-view.disabled-v1.json']))
    runtime=read(oldplan['runtime']); closure=read(oldplan['runtime_closure']); read(oldplan['native_build'])
    repair=read(AUTH['schema_repair_review']); prior=read(AUTH['prior_rebinding_report'])
    checked('corrected_proof_authority_binding',repair['corrected_proof']==AUTH['corrected_controller_proof'] and repair['corrected_proof']['sha256']=='294095fb64a1e3045de560ffc598f306aecc92f4e2577f363399d3277dae41b5')
    proof=read(AUTH['corrected_controller_proof']); proofref=pair(AUTH['corrected_controller_proof'])
    source=oldplan['source']; INDEX={x['path']:x['sha256'] for x in source['files']}
    checked('candidate_head_initial',git('rev-parse','HEAD')==HEAD==AUTH['source']==cr['source']==source['commit'])
    checked('candidate_tracked_tree_initial',not git('diff','--name-only',HEAD,'--'))
    ledgers('initial')
    track(TURNS/'001543/g5-disabled-preparation/prepare-g5-v1.py')
    track(TURNS/'001548/g6-verification/verify-g6-v1.py')
    exec(compile('\n'.join(line[4:] if line.startswith('    ') else line for line in SETUP_CODE.splitlines()),'<G5 passive setup>','exec'),globals())
    controller=extract('scripts/qd_ed_n34_controller.py',['FIELDS','verify_semantics'],module('passive_controller',{'w':w}))
    stop.check()
    controller.verify_semantics(proofref,oldplan['runtime'],closure)
    checked('exact_candidate_controller_verify_semantics',True,physical_instance_observed=False,proof=proofref)
    checked('controller_closure_binding',proof['runtime_closure']==oldplan['runtime_closure'] and proof['source_commit']==HEAD and proof['release_enabled'] is False)
    for r in proof['review_evidence'].values(): read(r)
    tree=ast.parse((ROOT/'scripts/qd_ed_n36_engineering.py').read_text())
    guard=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='launch_guard')
    checked('launch_guard_veto_first',ast.unparse(guard.body[0])=='require_dispatch_implementation()')
    try:e.require_dispatch_implementation()
    except RuntimeError as exc:checked('unconditional_source_dispatch_veto',True,message=str(exc))
    else:raise ValueError('dispatch veto absent')
    checked('dedicated_execution_output_absent_initial',not Path(oldplan['artifact_root']).exists())
    plan=copy.deepcopy(oldplan);audit=copy.deepcopy(oldaudit)
    plan['controller_semantics']=proofref;audit['controller_semantics']=proofref
    STAGE='transitive_rebinding'
    for row in audit['episodes']:
        boundary();key=row['episode_key'];oldref=oldaudit['expected_manifests'][key];old=read(oldref)
        value=copy.deepcopy(old);value['controller_semantics']=proofref
        unchanged(old,value,['controller_semantics'],'manifest_preserved_'+key)
        newref=write('audit-manifests/'+key+'.json',value)
        audit['expected_manifests'][key]=newref
        CHANGES.append({'kind':'audit_manifest','old':track(oldref['path']),'new':OUTPUTS['audit-manifests/'+key+'.json'],'changed_keys':['controller_semantics']})
    e.validate_audit_view(audit)
    unchanged(oldaudit,audit,['controller_semantics','expected_manifests'],'audit_preserved')
    plan['audit_plan']=write('audit-view.disabled-v1.json',audit)
    olddiagnostic=read(oldplan['engineering_manifest']);diagnostic=copy.deepcopy(olddiagnostic)
    diagnostic['controller_semantics']=proofref;diagnostic['audit_plan']=plan['audit_plan']
    diagnostic['audit_manifest']=audit['expected_manifests'][diagnostic['audit_row']['episode_key']]
    unchanged(olddiagnostic,diagnostic,['controller_semantics','audit_plan','audit_manifest'],'diagnostic_preserved')
    plan['engineering_manifest']=write('diagnostic-manifest.disabled-v1.json',diagnostic)
    plan['expected_manifests']={e.EPISODE_KEY:plan['engineering_manifest']}
    unchanged(oldplan,plan,['controller_semantics','audit_plan','engineering_manifest','expected_manifests'],'plan_preserved')
    e.validate_plan_shape(plan);e.audit_mapping(plan,audit,e.row())
    planref=write('engineering-plan.disabled-v1.json',plan)
    STAGE='exact_candidate_passive_verification'
    for row in audit['episodes']:
        boundary();b._verify_manifest_bound(audit['expected_manifests'][row['episode_key']],audit,runtime,row)
        checked('exact_manifest_'+row['episode_key'],True)
    b.verify_engineering_manifest(plan['engineering_manifest'],plan,runtime,e.row(),audit=audit)
    checked('exact_engineering_manifest',True)
    checked('disabled_authority_preserved',plan['b5_review'] is None and plan['authority'] is None and plan['release_enabled'] is False and audit['release_enabled'] is False and not any(plan['phase_authorization'].values()) and not any(audit['phase_authorization'].values()))
    original=read(audit['original_plan'])
    science=['cohort','episodes','limits','worker_contract','deadline','protocol','protocol_review','accounting']
    checked('original_40_rows_and_science_gates',len(audit['episodes'])==40 and all(audit[k]==original[k] for k in science),fields=science)
    # Verify every active top-level file-reference edge, without recursively rebuilding accepted provenance.
    active=[('plan',plan),('audit',audit),('diagnostic',diagnostic)]+[(r['episode_key'],read(audit['expected_manifests'][r['episode_key']])) for r in audit['episodes']]
    edges=[]
    def scan(obj,where):
        if isinstance(obj,dict):
            if set(obj)=={'path','sha256'} and Path(obj['path']).is_absolute():
                actual=track(obj['path']);require(actual['sha256']==obj['sha256'],'edge hash mismatch '+where)
                require(obj!=oldplan['controller_semantics'],'stale controller edge '+where)
                edges.append({'location':where,'reference':actual});return
            for k,v in obj.items():
                if k not in ('source','scientific_source'):scan(v,where+'/'+k)
        elif isinstance(obj,list):
            for i,v in enumerate(obj):scan(v,where+'/'+str(i))
    for label,obj in active:scan(obj,label)
    checked('all_active_graph_reference_edges_hash_verified',True,count=len(edges),accepted_source_inventory_recursion=False)
    checked('all_active_controller_edges_refreshed',all(obj['controller_semantics']==proofref for _,obj in active),count=len(active))
    graph={'schema':'n36-disabled-refreshed-graph-v1','source':HEAD,'plan':planref,'audit':plan['audit_plan'],'diagnostic_manifest':plan['engineering_manifest'],'audit_manifests':audit['expected_manifests'],'controller_semantics':proofref,'retained_bindings':{k:plan[k] for k in ['source','scientific_source','runtime','runtime_closure','native_build','scientific_equivalence','scope','accounting','deployment']},'controller_root_review':AUTH['controller_review'],'controller_schema_repair_review':AUTH['schema_repair_review'],'accepted_g5_review':AUTH['accepted_g5_review'],'accepted_g6_reconciliation':AUTH['g6_reconciliation'],'b5_review':None,'release_enabled':False,'authority':None,'source_adopted':False}
    graphref=write('graph-root.disabled-v1.json',graph)
    ROOTS.update(plan=track(planref['path']),audit=track(plan['audit_plan']['path']),diagnostic_manifest=track(plan['engineering_manifest']['path']),graph=track(graphref['path']),controller_semantics=track(proofref['path']))
    write('graph-edges-v1.json',{'edges':edges,'scope':'All active plan/audit/manifest references; preserved original_plan is a historical anchor, not an active controller reference. Accepted source/native/runtime provenance not rebuilt.'})
    write('rebindings-v1.json',{'controller':{'old':oldplan['controller_semantics'],'new':proofref},'audit_manifests':CHANGES,'other_roots':[{'old':G5['outputs'][n],'new':OUTPUTS[n]} for n in ['audit-view.disabled-v1.json','diagnostic-manifest.disabled-v1.json','engineering-plan.disabled-v1.json']]})
    for k in ['runtime','runtime_closure','native_build']:
        checked(k+'_bytes_preserved',track(plan[k]['path'])['sha256']==oldplan[k]['sha256'] and plan[k]==oldplan[k])
    ledgers('final');stop.check()
    checked('final_stop_deadline',True)
    checked('candidate_head_final',git('rev-parse','HEAD')==HEAD)
    checked('candidate_tracked_tree_final',not git('diff','--name-only',HEAD,'--'))
    checked('dedicated_execution_output_absent_final',not Path(plan['artifact_root']).exists())
    STAGE='DISABLED_GRAPH_REBOUND_PENDING_INDEPENDENT_B5'

def finish():
    # Register passive source/config files actually accessed, never import production modules.
    for p in sorted(ACCESSED):
        if Path(p).is_file():track(p)
    write('passive-verifier-definitions-v1.json',{'definitions':EXTRACTED,'ast_rewritten':False,'constructor_composition_note':'Exact candidate resolve_constructor internally slices its constructor AST for config serialization; passive verifier definitions are not rewritten.','production_modules_imported':False,'optional_import_rejections':IMPORT_BLOCKS})
    config=[]
    for name,m in list(sys.modules.items()):
        if name.split('.')[0] in {'hydra','omegaconf','antlr4','yaml','packaging'}:
            p=getattr(m,'__file__',None)
            if p and Path(p).is_file():config.append({'module':name,'source':track(p)})
    write('configuration-composition-modules-v1.json',{'modules':config,'third_party_native_extensions_loaded':False})
    write('independent-b5-inputs-v1.json',{'schema':'n36-independent-b5-inputs-v1','purpose':'Inputs for a subsequent independent review; no B5 performed here','source':HEAD,'roots':ROOTS,'accepted_records':{k:AUTH[k] for k in ['controller_review','accepted_g5_review','g6_reconciliation','schema_repair_review','corrected_controller_proof','prior_rebinding_report']},'b5_review':None,'release_enabled':False,'authority':None,'source_adopted':False,'preparation_outputs':dict(OUTPUTS),'unresolved':UNRESOLVED,'blockers':ERRORS})
    status='PREPARATION_COMPLETE_PENDING_INDEPENDENT_B5' if not ERRORS else 'BLOCKED_PARTIAL_ARTIFACTS'
    result={'schema':'n36-disabled-graph-rebinding-report-v1','at':dt.datetime.now(dt.timezone.utc).isoformat(),'node_id':'15.6','status':status,'stage':STAGE,'source':HEAD,'inputs':list(INPUTS.values()),'outputs':dict(OUTPUTS),'roots':ROOTS,'checks':CHECKS,'blockers':ERRORS,'unresolved':UNRESOLVED,'b5_review':None,'independent_B5_performed':False,'release_enabled':False,'dispatch_enabled':False,'authority':None,'authority_granted':False,'source_adopted':False,'accounting_adopted':False,'source_edited':False,'owner_state_checkpoint_tree_ledger_written':False,'native_model_provider_execution':False,'gpu_dispatch':False,'protected_results_accessed':False,'scientific_success':False,'goal_complete':False,'score':None,'retained_accounting':G5.get('retained_accounting') if 'G5' in globals() else None,'ledger_checks':LEDGERS,'budget':{'deadline':'2026-10-11T11:13:13Z','task_started_at':'2026-10-10T17:57:41Z','preparation_max_seconds':1200,'helper_elapsed_seconds':time.monotonic()-START,'helper_cpu_seconds':time.process_time()-CPU_START,'cpu_limit_seconds':1000,'helper_wall_limit_seconds':1050},'verification_scope':'Exact candidate passive plan/audit/controller definitions and 41 manifest recomparisons. Pure-Python Hydra/OmegaConf config composition only; no production imports, full release verifier, native binary rehash, broad tests, independent B5 or scientific evaluation. Accepted G2/G3/G4/native provenance retained.','tests_run':0,'next_step':'Independent B5 review of exact refreshed plan and graph roots; all G7 gates and unconditional dispatch veto remain.'}
    write('report-v1.json',result)
    print(json.dumps({'status':status,'roots':ROOTS,'check_count':len(CHECKS),'blockers':ERRORS,'report':OUTPUTS['report-v1.json']}),flush=True)
try:main()
except Exception as exc:
    ERRORS.append({'stage':STAGE,'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()})
finally:finish()
