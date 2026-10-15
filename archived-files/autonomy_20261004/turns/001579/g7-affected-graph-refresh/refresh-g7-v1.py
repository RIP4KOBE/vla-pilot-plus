"""Disabled G5 artifacts only. Exact passive definitions, no execution authority."""
import ast, copy, datetime as dt, hashlib, json, math, os, re, resource
import signal, subprocess, sys, time, traceback, types
from pathlib import Path
from dataclasses import dataclass, asdict
from numbers import Integral, Real
from typing import Optional

OUT = Path(__file__).absolute().parent
LEX = Path('/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001579/g7-affected-graph-refresh')
TURNS = LEX.parents[1]
ROOT = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_adapter_001482/implementation_worktree')
HEAD = 'b8d6b98164f24a599a9aa1fa6ce862b12cb2fcf6'
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
        require(isinstance(argv,(list,tuple)) and Path(argv[0]).name=='git' and any(x in argv for x in ('rev-parse','diff','merge-base','show','log')), 'only passive git allowed')
    if event == 'open' and isinstance(args[0],(str,bytes)):
        p=Path(os.path.abspath(os.fsdecode(args[0]))); low=str(p).lower()
        require('2026-08-10' not in low and '/.codex/auth' not in low and 'credential' not in low and '/formal/' not in low and '/validation/' not in low, 'prohibited read: '+str(p))
        if isinstance(args[2],int) and args[2] & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):
            require(p.resolve().is_relative_to(OUT.resolve()), 'outside authorized output write: '+str(p))
        elif p.is_relative_to(ROOT): ACCESSED.add(str(p))
    if event in ('os.mkdir','os.remove','os.rmdir','os.rename'):
        for raw in args[:2] if event=='os.rename' else args[:1]:
            if isinstance(raw,(str,bytes)): require(Path(os.fsdecode(raw)).resolve().is_relative_to(OUT.resolve()),'outside output mutation')

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


SETUP_CODE = "    module('scripts');module('core')\n    w=extract('scripts/qd_ed_n23_worker.py',['require','sha','canonical_sha','read_ref'],module('scripts.qd_ed_n23_worker'))\n    stop=extract('scripts/qd_ed_n36_stop.py',['OWNER_STOP','DATA_STOP','STOP_PATHS','DEADLINE','binding','check'],module('scripts.qd_ed_n36_stop'))\n    stop.check()\n    route=extract('scripts/qd_ed_n36r2_admission.py',['SESSION','OWNER'],module('scripts.qd_ed_n36r2_admission'))\n    c=extract('scripts/qd_ed_n36_contract.py',['SEPARATE_HEALTH_COHORTS','COHORT','DRAFT_N36R4_COHORT','IDENTITIES','ARMS','DEADLINE','PROTOCOL_REVIEW_SHA','LIMITS','WORKER_CONTRACT','stop_path','validate_stop_binding','expected_rows','cohort','plan_rows','operational_binding'],module('scripts.qd_ed_n36_contract',{'w':w,'stop':stop}))\n    e=extract('scripts/qd_ed_n36_engineering.py',['BASE','SOURCE','PREPARATION','SPECIFICATION','IDENTITY','EPISODE_KEY','PURPOSE','PLAN_SCHEMA','AUDIT_SCHEMA','LIMITS','BINDINGS','RUNTIME_INPUTS','exact','reference','read','specification','row','disabled_scope','disabled_accounting','validate_disabled_scope','validate_disabled_accounting','validate_scope_reference','validate_accounting_reference','require_row','deployment','owner_root','validate_audit_view','validate_plan_shape','audit_mapping','OPERATIONAL_FILES','scientific_equivalence','launch_guard'],module('scripts.qd_ed_n36_engineering',{'w':w,'c':c,'stop':stop,'OWNER':route.OWNER,'SESSION':route.SESSION}))\n    policy=extract('core/codex_stage_policy.py',['_DISABLED_FEATURES','_DEVELOPER_INSTRUCTIONS','_REMOVED_ENVIRONMENT','_MAX_EVENTS_BYTES','public_invocation_policy','policy_sha256'],module('core.codex_stage_policy'))\n    e1=extract('scripts/qd_ed_n4e1_plan.py',['CONDITION_ID','PROTOCOL','FROZEN_DOCS','STAGE_CONDITION','engineering_condition'],module('passive_e1'))\n    runner=extract('scripts/qd_ed_final_runner.py',['PYTHON','CODEX_CONFIG_KEYS','E2_STAGE_CONDITION','CODEX_STAGE_CONDITION','owned','hydra','is_n17_plan','is_n31_plan','is_n30_plan','is_n29_plan','n4e1_support','codex_policy_module','codex_public_config','codex_public_config_sha256','stage_overrides','stage_condition','build_command'],module('scripts.qd_ed_final_runner',{'require':w.require,'_N4E1_SUPPORT':e1}))\n    helper=extract('scripts/qd_ed_n32_bridge.py',['resolve_constructor','compose_launch'],module('scripts.qd_ed_n32_bridge',{'w':w,'dataclass':dataclass,'asdict':asdict,'Optional':Optional,'Integral':Integral,'Real':Real}))\n    n34=extract('scripts/qd_ed_n34_bridge.py',['MODE','runtime_sources','profiles'],module('scripts.qd_ed_n34_bridge',{'w':w,'runner':runner}))\n    constants=extract('core/qd_observed_jaw_approach.py',['SOURCE_FILES'],module('passive_n34_constants'))\n    n36constants=extract('core/qd_nonprogress_tangent.py',['MODE','SOURCE_FILES'],module('passive_n36_constants',{'N34_SOURCES':constants.SOURCE_FILES}))\n    extract('scripts/qd_ed_n36r4_admission.py',['PROTOCOL_SHA','ACCOUNTING_SHA'],module('scripts.qd_ed_n36r4_admission'))\n    b=extract('scripts/qd_ed_n36_bridge.py',['_ENGINEERING_ROUTES','_ENGINEERING_IDENTITIES','profiles','command','manifest','_verify_manifest_bound','engineering_command','engineering_manifest','verify_engineering_manifest'],module('scripts.qd_ed_n36_bridge',{'w':w,'c':c,'n34':n34,'runner':runner,'compose_launch':helper.compose_launch,'SOURCE_FILES':n36constants.SOURCE_FILES,'MODE':n36constants.MODE}))\n"

TASK_START=dt.datetime.fromisoformat('2026-10-10T18:55:13+00:00')
OLD='dcd890474b733743414d2a7711069bb0d2b0337e'
ROOTS={}; MATRIX=[]; CHANGES=[]; CPU_START=time.process_time()
def checked(name,ok,**detail):
    CHECKS[name]={'pass':bool(ok),**detail};require(ok,name)
def pair(r):return {k:r[k] for k in ('path','sha256')}
def preserve(old,new,allowed,label):
    changed=sorted(k for k in set(old)|set(new) if old.get(k)!=new.get(k))
    checked(label,set(old)==set(new) and set(changed)<=set(allowed),changed_keys=changed)
    return changed
def delta(old,new,where=''):
    if type(old)!=type(new):return [where]
    if isinstance(old,dict):return sum((delta(old.get(k),new.get(k),where+'/'+k) for k in sorted(set(old)|set(new))),[])
    if isinstance(old,list):
        if len(old)!=len(new):return [where]
        return sum((delta(a,b,where+'/'+str(i)) for i,(a,b) in enumerate(zip(old,new))),[])
    return [] if old==new else [where]
def normalized(value):
    if isinstance(value,dict):return {k:normalized(v) for k,v in value.items()}
    if isinstance(value,list):return [normalized(v) for v in value]
    if isinstance(value,str):return value.replace(HEAD,OLD)
    return value
def record_change(kind,oldref,newref,old,new):
    MATRIX.append({'kind':kind,'disposition':'regenerated','old':oldref,'new':newref,'changed_fields':delta(old,new),'rationale':'Exact G7 source identity or transitive referenced content/hash changed.'})
def main():
    global AUTH,INDEX,STAGE
    boundary();checked('initial_STOP_deadline',True,at=dt.datetime.now(dt.timezone.utc).isoformat())
    AUTH=load(LEX/'authority-v1.json');track(__file__)
    standing=read(AUTH['standing_authority']);accepted=read(AUTH['accepted_source_review']);review=read(AUTH['independent_source_review']);prior=read(AUTH['prior_graph_report'])
    checked('authority_review_bindings',accepted['report']==AUTH['independent_source_review'] and accepted['source']==review['source']==AUTH['source']==HEAD and accepted['status']=='PASS_BOUNDED_SOURCE_REVIEW' and review['source_approved'] is True and not review['source_review_blockers'])
    checked('candidate_exact_clean',git('rev-parse','HEAD')==HEAD and not git('diff','--name-only',HEAD,'--'))
    oldplan=read(prior['roots']['plan']);oldaudit=read(prior['roots']['audit']);oldgraph=read(prior['roots']['graph'])
    checked('prior_source_exact',oldplan['source']['commit']==OLD and oldplan['source']==oldplan['scientific_source'])
    changed=git('diff','--name-only',OLD,HEAD,'--').splitlines()
    source=copy.deepcopy(oldplan['source']);oldindex={r['path']:r['sha256'] for r in source['files']}
    checked('inventory_delta_covered',set(changed)<=set(oldindex),paths=changed)
    descriptions={
      'scripts/qd_ed_n36_engineering.py':'Conditional released-plan guard replaces unconditional veto; prospective health/episode release timestamps and settled health requirements.',
      'scripts/qd_ed_n36_healthcheck.py':'Conditional engineering lifecycle; persist uncapped measured overrun as aborted, never readiness.',
      'scripts/qd_ed_n36_runner.py':'Conditional engineering lifecycle; overrun rejection before valid terminal, retain full charge.',
      'scripts/qd_ed_n36_worker.py':'Require loaded and compiled canonical engineering/release/accounting/STOP identities in both phases.',
      'tests/n36_engineering_cpu_fixture.py':'Disposable CPU lifecycle fixture, immutable release references and composition caching; no science rows.',
      'tests/test_n36_engineering.py':'Tests current conditional released schema instead of obsolete veto.',
      'tests/test_n36_engineering_integration.py':'Lifecycle, timestamp, overrun and deep receipt negatives; fixture isolation and worker __main__ positive.'}
    checked('bounded_all_intervening_paths',set(changed)==set(descriptions))
    for row in source['files']:
        path=ROOT/row['path'];actual=sha(path)
        if row['path'] in changed:
            committed=subprocess.check_output(['git','--no-replace-objects','-C',str(ROOT),'show',HEAD+':'+row['path']])
            checked('committed_'+row['path'],hashlib.sha256(committed).hexdigest()==actual)
            CHANGES.append({'path':row['path'],'old_sha256':row['sha256'],'new_sha256':actual,'assessment':descriptions[row['path']]})
            row['sha256']=actual
        else:require(actual==row['sha256'],'unchanged source drift '+row['path'])
    source['commit']=HEAD
    source['sha256']=hashlib.sha256(json.dumps(source['files'],sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    INDEX={r['path']:r['sha256'] for r in source['files']}
    checked('all_1110_inventory_bytes_checked',len(source['files'])==1110)
    for r in review['source_files'].values():readbytes=track(r['path']);require(readbytes==r,'review source differs')
    for r in review['unaffected_reviewed_source_files'].values():
        actual=track(r['path']);require(actual==r,'retained review source differs')
    source_ref=write('source-inventory-v1.json',source);ROOTS['source_inventory']=track(source_ref['path']);ROOTS['scientific_source_inventory']=ROOTS['source_inventory']
    MATRIX.append({'kind':'source_and_scientific_source','disposition':'regenerated','old_commit':OLD,'new':ROOTS['source_inventory'],'changed_files':CHANGES,'unchanged_file_count':1103,'rationale':'Same accepted inventory membership, seven reviewed G7 changes; all 1110 on-disk digests checked; dependency inventories reused, not reconstructed.'})
    write('all-intervening-g7-changes-v1.json',{'old_commit':OLD,'source':HEAD,'changes':CHANGES,'commit_history':git('log','--format=%H %s',OLD+'..'+HEAD),'source_review':AUTH['independent_source_review'],'release_enabled':False,'b5_review':None})
    exec(compile('\n'.join(line[4:] if line.startswith('    ') else line for line in SETUP_CODE.splitlines()),'<exact source passive setup>','exec'),globals())
    stop.check();checked('exact_canonical_STOP_deadline',True)
    controller=extract('scripts/qd_ed_n34_controller.py',['FIELDS','verify_semantics'],module('passive_controller',{'w':w}))
    runtime=read(oldplan['runtime']);closure=read(oldplan['runtime_closure']);native=read(oldplan['native_build']);controllerproof=read(oldplan['controller_semantics'])
    controller.verify_semantics(oldplan['controller_semantics'],oldplan['runtime'],closure)
    checked('exact_controller_verifier_compatible',True,historical_source_commit=controllerproof['source_commit'],current_source=HEAD,physical_instance_observed=False)
    rationales={
      'runtime':'Task/init/bddl inputs, stage/provider policy, interpreter/dependency selection and output mapping unchanged. G7 changes admission/accounting/receipt checks only. Record hash retained; no new readiness or provider observation claimed.',
      'runtime_closure':'Interpreter, package modules, aliases, generated-module rules and required-after set unchanged; new receipt obligations bind project modules via refreshed source inventories, not external package closure. Exact runtime reference retained.',
      'native_build':'No native code/library/dependency or build-selection change in full G7 diff. Existing expected-build record reused by hash; no native binary execution/rehash or current hardware observation.',
      'controller_semantics':'Controller, wrappers/gripper forwarding, science algorithms/config and controller verifier unchanged. Exact verify_semantics passes against same runtime/closure. source_commit remains historical review provenance dcd890; not a claim of new root review. Accepted source review permits scoped reuse; no physical-gain/instance claim.',
      'scope':'Disabled one-C0 engineering identity and eligibility exclusions unchanged; exact disabled-scope validator retained.',
      'accounting':'Disabled finite accounting specification/retained history unchanged. G7 enforces full measured overrun charge, does not change reservation limits, scope or ledger baselines; no accounting adoption.',
      'deployment':'Same lexical owner/source/output roots and canonical STOP paths; no source adoption or routing change.'}
    for kind,why in rationales.items():
        value=read(oldplan[kind]);MATRIX.append({'kind':kind,'disposition':'reused_byte_identical','reference':track(oldplan[kind]['path']),'compatibility_rationale':why,'source_change_range':[OLD,HEAD]})
    for r in controllerproof['review_evidence'].values():read(r)
    plan=copy.deepcopy(oldplan);audit=copy.deepcopy(oldaudit)
    for obj in [plan,audit]:obj['source']=copy.deepcopy(source);obj['scientific_source']=copy.deepcopy(source)
    oldeq=read(oldplan['scientific_equivalence'])
    basechanged=sorted(git('diff','--name-only',e.BASE,HEAD,'--').splitlines())
    checked('all_changes_since_scientific_base_operational',set(basechanged)<=e.OPERATIONAL_FILES,base=e.BASE,paths=basechanged)
    equivalence={'schema':'n36-engineering-scientific-equivalence-v1','base_commit':e.BASE,'source':source,'changed_paths':basechanged,'scientific_changes':False}
    plan['scientific_equivalence']=write('scientific-equivalence-v1.json',equivalence)
    e.scientific_equivalence(plan);checked('exact_scientific_equivalence_validator',True)
    ROOTS['scientific_equivalence']=track(plan['scientific_equivalence']['path']);record_change('scientific_equivalence',oldplan['scientific_equivalence'],plan['scientific_equivalence'],oldeq,equivalence)
    STAGE='manifest_recomposition'
    for row in audit['episodes']:
        boundary();key=row['episode_key'];oldref=oldaudit['expected_manifests'][key];old=read(oldref)
        value=b.manifest(audit,runtime,row)
        fields=preserve(old,value,['source','scientific_source','argv','resolved_config','expected_runtime','composed_config_sha256'],'manifest_allowed_'+key)
        checked('scientific_config_preserved_'+key,normalized(value['resolved_config'])==old['resolved_config'] and normalized(value['argv'])==old['argv'])
        if value['expected_runtime']:
            checked('algorithm_source_hashes_preserved_'+key,value['expected_runtime']['source_hashes']==old['expected_runtime']['source_hashes'] and normalized(value['expected_runtime']['binding'])==old['expected_runtime']['binding'])
        newref=write('audit-manifests/'+key+'.json',value);audit['expected_manifests'][key]=newref
        record_change('audit_manifest:'+key,oldref,newref,old,value)
    e.validate_audit_view(audit);checked('exact_audit_view_validator',True)
    preserve(oldaudit,audit,['source','scientific_source','expected_manifests'],'audit_allowed')
    plan['audit_plan']=write('audit-view.disabled-v1.json',audit);record_change('audit_view',oldplan['audit_plan'],plan['audit_plan'],oldaudit,audit)
    diagnostic=b.engineering_manifest(plan,runtime,e.row(),audit=audit);olddiagnostic=read(oldplan['engineering_manifest'])
    preserve(olddiagnostic,diagnostic,['source','scientific_source','audit_plan','audit_manifest'],'engineering_manifest_allowed')
    plan['engineering_manifest']=write('engineering-manifest.disabled-v1.json',diagnostic)
    record_change('engineering_manifest',oldplan['engineering_manifest'],plan['engineering_manifest'],olddiagnostic,diagnostic)
    plan['expected_manifests']={e.EPISODE_KEY:plan['engineering_manifest']}
    preserve(oldplan,plan,['source','scientific_source','scientific_equivalence','audit_plan','engineering_manifest','expected_manifests'],'plan_allowed')
    e.validate_plan_shape(plan);e.audit_mapping(plan,audit,e.row());e.scientific_equivalence(plan)
    planref=write('engineering-plan.disabled-v1.json',plan);record_change('disabled_plan',pair(prior['roots']['plan']),planref,oldplan,plan)
    STAGE='exact_passive_validators'
    for row in audit['episodes']:
        boundary();b._verify_manifest_bound(audit['expected_manifests'][row['episode_key']],audit,runtime,row)
        checked('exact_manifest_'+row['episode_key'],True)
    b.verify_engineering_manifest(plan['engineering_manifest'],plan,runtime,e.row(),audit=audit);checked('exact_engineering_manifest',True)
    try:e.launch_guard(plan,None)
    except ValueError as exc:checked('conditional_guard_rejects_disabled_plan',str(exc)=='distinct released engineering plan required',reason=str(exc))
    else:raise ValueError('disabled plan accepted by conditional guard')
    checked('no_obsolete_unconditional_veto',not hasattr(e,'require_dispatch_implementation'))
    checked('science_rows_gates_preserved',len(audit['episodes'])==40 and all(audit[k]==oldaudit[k] for k in ['episodes','cohort','limits','worker_contract','deadline','protocol','protocol_review','accounting']))
    checked('no_authority_or_B5',plan['release_enabled'] is False and plan['b5_review'] is None and plan['authority'] is None and audit['release_enabled'] is False and audit['dispatch_authority'] is False)
    checked('execution_output_absent',not Path(plan['artifact_root']).exists())
    active=[('plan',plan),('audit',audit),('engineering_manifest',diagnostic)]+[(r['episode_key'],read(audit['expected_manifests'][r['episode_key']])) for r in audit['episodes']]
    edges=[]
    def scan(obj,where):
        if isinstance(obj,dict):
            if set(obj)=={'path','sha256'} and Path(obj['path']).is_absolute():
                actual=track(obj['path']);require(actual['sha256']==obj['sha256'],'edge hash mismatch '+where);edges.append({'location':where,'reference':actual});return
            for k,v in obj.items():
                if k not in ('source','scientific_source'):scan(v,where+'/'+k)
        elif isinstance(obj,list):
            for i,v in enumerate(obj):scan(v,where+'/'+str(i))
    for name,obj in active:
        checked('source_inventory_binding_'+name,obj['source']==obj['scientific_source']==source)
        scan(obj,name)
    checked('active_reference_hashes',True,count=len(edges))
    write('graph-edges-v1.json',{'edges':edges,'scope':'Active plan/audit/41 manifests only; historical original_plan and retained external evidence remain anchors; no recursive provenance reconstruction.'})
    history={k:review[k] for k in ['retained_prior_tests','historical_failed_and_interrupted_tests_preserved','retained_final_implementation_test_evidence','history_interpretation','tests']}
    # Bind historical records without rerunning tests or recursively opening their provenance.
    for r in history['historical_failed_and_interrupted_tests_preserved']:require(track(r['path'])==r,'history drift')
    for k in ['retained_prior_tests','retained_final_implementation_test_evidence','tests']:
        for test in history[k]:
            if 'evidence' in test:require(track(test['evidence']['path'])==test['evidence'],'test history drift')
    write('retained-test-history-v1.json',history)
    matrixref=write('changed-reused-evidence-matrix-v1.json',{'source_range':[OLD,HEAD],'entries':MATRIX,'all40_recomposed':True,'prior_B5_transfers':False,'release_enabled':False,'b5_review':None})
    graph={'schema':'n36-g7-disabled-refreshed-graph-v1','source':HEAD,'plan':planref,'audit':plan['audit_plan'],'engineering_manifest':plan['engineering_manifest'],'audit_manifests':audit['expected_manifests'],'source_inventory':source_ref,'scientific_source_inventory':source_ref,'scientific_equivalence':plan['scientific_equivalence'],'retained_bindings':{k:plan[k] for k in rationales},'prior_graph':pair(prior['roots']['graph']),'accepted_source_review':pair(AUTH['accepted_source_review']),'independent_source_review':pair(AUTH['independent_source_review']),'evidence_matrix':matrixref,'b5_review':None,'release_enabled':False,'authority':None,'source_adopted':False,'accounting_adopted':False}
    graphref=write('graph-root.disabled-v1.json',graph)
    ROOTS.update(plan=track(planref['path']),audit=track(plan['audit_plan']['path']),engineering_manifest=track(plan['engineering_manifest']['path']),graph=track(graphref['path']),controller_semantics=track(plan['controller_semantics']['path']),evidence_matrix=track(matrixref['path']))
    write('refreshed-root-references-v1.json',{'roots':ROOTS,'b5_review':None,'release_enabled':False,'authority':None,'source_adopted':False})
    write('passive-validator-definitions-v1.json',{'definitions':EXTRACTED,'ast_rewritten':False,'no_production_imports':True,'no_acceptance_predicates_patched':True,'hydra_configuration_only':True})
    checked('candidate_exact_clean_final',git('rev-parse','HEAD')==HEAD and not git('diff','--name-only',HEAD,'--'))
    for r in list(INPUTS.values()):require(sha(r['path'])==r['sha256'],'input drift '+r['path'])
    for r in OUTPUTS.values():require(sha(r['path'])==r['sha256'],'output drift '+r['path'])
    stop.check();boundary();checked('final_STOP_deadline',True,at=dt.datetime.now(dt.timezone.utc).isoformat())
    STAGE='complete'

try:main()
except BaseException as exc:
    ERRORS.append({'stage':STAGE,'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()});print(traceback.format_exc(),flush=True)
finally:
    status='PREPARATION_COMPLETE_PENDING_INDEPENDENT_B5' if not ERRORS else 'BLOCKED_PARTIAL_OUTPUTS_PRESERVED'
    unresolved=['Fresh independent B5 must bind current source, accepted source review, affected proof and refreshed roots; prior B5 does not transfer.','Coordinator-only source/accounting adoption, authority/protocol acceptance, actual readiness and prospective detached health/episode releases remain absent.','No scientific evaluation or success claim.']
    b5={'schema':'n36-g7-independent-b5-inputs-v1','source':HEAD,'prior_source':OLD,'status':status,'roots':ROOTS,'authority_record':track(LEX/'authority-v1.json'),'accepted_source_review':AUTH['accepted_source_review'] if 'AUTH' in globals() else None,'independent_source_review':AUTH['independent_source_review'] if 'AUTH' in globals() else None,'prior_graph_report':AUTH['prior_graph_report'] if 'AUTH' in globals() else None,'preparation_outputs':dict(OUTPUTS),'blockers':ERRORS,'remaining_obligations':unresolved,'b5_review':None,'independent_B5_performed':False,'release_enabled':False,'authority':None,'source_adopted':False,'prior_B5_approves_current_source':False}
    b5ref=write('independent-b5-inputs-v1.json',b5)
    report={'schema':'n36-g7-affected-graph-refresh-report-v1','node_id':'15.6','at':dt.datetime.now(dt.timezone.utc).isoformat(),'source':HEAD,'prior_source':OLD,'status':status,'stage':STAGE,'inputs':list(INPUTS.values()),'outputs':dict(OUTPUTS),'roots':ROOTS,'checks':CHECKS,'blockers':ERRORS,'remaining_obligations':unresolved,'changed_source_files':CHANGES,'evidence_matrix':ROOTS.get('evidence_matrix'),'b5_review':None,'independent_B5_performed':False,'release_enabled':False,'dispatch_enabled':False,'authority':None,'authority_granted':False,'source_adopted':False,'accounting_adopted':False,'source_edited':False,'owner_state_tree_ledger_written':False,'native_model_provider_execution':False,'gpu_dispatch':False,'CUDA_VISIBLE_DEVICES':os.environ['CUDA_VISIBLE_DEVICES'],'protected_results_accessed':False,'credentials_accessed':False,'delegation':False,'scientific_success':False,'target_met':False,'score':None,'tests_rerun':0,'verification_scope':'Exact-source unmodified AST-extracted passive validators; scientific-equivalence and disabled plan/audit guards; all40+engineering Hydra recomposition/recomparison; active direct reference hashes. No full release/runtime/native execution or recursive provenance reconstruction.','G7_lifecycle':'Conditional detached-release lifecycle implemented; disabled plan rejected by released schema guard. No obsolete unconditional veto assumed.','budget':{'started_at':TASK_START.isoformat(),'finished_at':dt.datetime.now(dt.timezone.utc).isoformat(),'elapsed_seconds':(dt.datetime.now(dt.timezone.utc)-TASK_START).total_seconds(),'cpu_seconds':time.process_time()-CPU_START,'timeout_seconds':1200,'deadline':'2026-10-11T11:13:13Z'},'next_step':unresolved[0]}
    reportref=write('report-v1.json',report)
    seal=write('artifact-hash-seal-v1.json',{'schema':'n36-g7-artifact-hash-seal-v1','report':track(reportref['path']),'independent_b5_inputs':track(b5ref['path']),'roots':ROOTS,'release_enabled':False,'b5_review':None})
    print(json.dumps({'status':status,'report':reportref,'seal':seal,'checks':len(CHECKS),'blockers':ERRORS}),flush=True)
    if ERRORS:sys.exit(1)
