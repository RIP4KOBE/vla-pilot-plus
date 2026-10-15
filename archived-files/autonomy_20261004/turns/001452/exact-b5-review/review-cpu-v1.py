import os,sys,json,hashlib,datetime,resource,signal,ast,math,subprocess,copy,time
from pathlib import Path
sys.dont_write_bytecode=True
os.environ.update(CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',MKL_NUM_THREADS='2')
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2]);resource.setrlimit(resource.RLIMIT_CPU,(240,240));signal.alarm(300)
ROOT=Path.cwd();sys.path.insert(0,str(ROOT))
OUT=Path(__file__).absolute().parent;BASE=OUT.parents[1]
from scripts import qd_ed_n36_stop as stop,qd_ed_n36_bridge as b,qd_ed_n36_contract as c,qd_ed_n36r3_admission as a,qd_ed_n36r3_preparation as prep,qd_ed_n23_worker as w,qd_ed_n36_release as rel
stop.check(need=300)
checks=[];refs={}
def bound(p):
 p=Path(p);raw=p.read_bytes();return {'path':str(p),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
def read(ref):
 actual=bound(ref['path']);assert all(actual[k]==ref[k] for k in ('sha256',) + (('bytes',) if 'bytes' in ref else ())),str(ref)
 refs[str(ref['path'])]=actual;return json.loads(Path(ref['path']).read_bytes())
def get(p):return read(bound(p))
def ck(name,fn):
 t=time.monotonic()
 try:
  result=fn();checks.append({'check':name,'status':'PASS','seconds':round(time.monotonic()-t,3),'result':result});print(name,'PASS',flush=True);return result
 except Exception as e:
  checks.append({'check':name,'status':'FAIL','seconds':round(time.monotonic()-t,3),'error':type(e).__name__+': '+str(e)});print(name,'FAIL',str(e),flush=True)
def req(x,msg='comparison failed'):
 if not x:raise ValueError(msg)
auth=get(OUT/'authority-v1.json');plan=read(auth['plan']);bundle=read(auth['bindings']);runtime=read(plan['runtime']);closure=read(plan['runtime_closure'])
for k in ['standing_authority','terminal_reconciliation','controller_review']:read(auth[k])
ck('authority exact hashes, source HEAD, BINDINGS',lambda:(req(subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==auth['source']==plan['source']['commit']),req(all(bundle[k]==plan[k] for k in a.BINDINGS)),req(bundle['expected_manifests']==plan['expected_manifests']),req(read(bundle['plan'])==plan),list(a.BINDINGS))[-1])
ck('STOP and deadline',lambda:(stop.check(),stop.binding())[-1])
ck('draft and protocol consumers',lambda:c.validate_draft(plan))
ck('lexical owner and isolated SOURCE',lambda:str(a.owner_root(plan)))
ck('exact source closure',lambda:b.verify_sources(plan))
ck('passive runtime closure including generated rule and versions',lambda:(b.closure.verify_runtime(closure,plan['runtime']),{'modules':len(closure['modules']),'generated':list(closure.get('generated_modules',{}))})[-1])
def pure(file,names,ns):
 tree=ast.parse((ROOT/file).read_text());nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names or isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in names for t in n.targets)]
 exec(compile(ast.Module(body=nodes,type_ignores=[]),str(ROOT/file),'exec'),ns);return ns
ck('root controller exact consumer',lambda:pure('scripts/qd_ed_n34_controller.py',{'verify_semantics','FIELDS'},{'w':w,'math':math})['verify_semantics'](plan['controller_semantics'],plan['runtime'],closure)['status'])
ck('native build passive manifest API (AST without Torch import)',lambda:len(pure('scripts/qd_ed_n36_build.py',{'manifest','REQUIRED'},{'w':w,'Path':Path})['manifest'](plan['native_build'])['libraries']))
def manifests():
 for row in plan['episodes']:
  read(plan['expected_manifests'][row['episode_key']]);b._verify_manifest_bound(plan['expected_manifests'][row['episode_key']],plan,runtime,row)
 return {'count':len(plan['episodes']),'arms':{arm:sum(x['profile']==arm for x in plan['episodes']) for arm in c.ARMS}}
ck('all 40 regenerated in-memory exact expected manifests',manifests)
old=get(BASE/'001448/binding-refresh/draft/plan.draft.json')
ck('001448 to 001451 allowed delta only',lambda:(req({k:v for k,v in old.items() if k not in ('controller_semantics','artifact_root','expected_manifests')}=={k:v for k,v in plan.items() if k not in ('controller_semantics','artifact_root','expected_manifests')}),['controller_semantics','artifact_root','expected_manifests'])[-1])
prior=get(BASE/'001433/exact-b5-review/report-v1.json');continuity=get(BASE/'001437/terminal-reconciliation-v1.json');reconciled=get(BASE/'001447/terminal-reconciliation-v1.json');repair=get(BASE/'001445/accounting-health-repair/report-v1.json');snap=get(BASE/'001448/binding-refresh/accounting-snapshot.disabled-v1.json');health=get(BASE/'001448/binding-refresh/health-policy.disabled-v1.json');required=get(BASE/'001448/binding-refresh/required-after.production-v1.json')
ck('required_after exact prospective contract',lambda:(req(required['required_after']==closure['required_after']),req(required['runtime_closure']==plan['runtime_closure']),req(required['observed_loaded_after'] is False),required['required_after'])[-1])
ck('accounting arithmetic uses refreshed accepted reconciliation',lambda:(req(snap['snapshot']==reconciled['budget_snapshot']),req(prep.arithmetic(snap['snapshot'])==snap['arithmetic']),snap['arithmetic'])[-1])
def negative_charge():
 old=copy.deepcopy(snap['snapshot']);old['gpu_hours_consumed']=75.53031173955723
 try:prep.arithmetic(old)
 except ValueError as e:return 'expected rejection: '+str(e)
 raise ValueError('old retained charge accepted')
ck('stale accounting charge rejected',negative_charge)
def current_ledgers():
 # Hash only; no protected episode result inspection, no state/ledger writes.
 for name,ref in snap['ledger_prefixes'].items():
  req(all(bound(ref['path'])[k]==ref[k] for k in ('path','bytes','sha256')),name)
  req(all(ref[k]==reconciled['ledger_prefixes'][name][k] for k in ('path','bytes','sha256')))
 historical=w.read_ref(plan['accounting'])
 for key in ('retained_ledger_prefix','retained_health_ledger_prefix'):
  anchor=historical[key];rel.prefix(anchor['path'],anchor)
 # Only finite current health accounting journal, never probe output.
 events=[json.loads(line) for line in Path(snap['ledger_prefixes']['gpu-healthcheck-ledger.jsonl']['path']).read_text().splitlines() if line.strip()]
 req(not any(e['resource_id']==a.PREPARATION_ID for e in events),'new preparation identity already charged')
 return {'exact_current_journal_hashes':snap['ledger_prefixes'],'fresh_identity_uncharged':a.PREPARATION_ID,'historical_prefixes_retained':True}
ck('current accounting hashes and retained prefixes, no adoption',current_ledgers)
ck('distinct finite health policy',lambda:(req(a.PREPARATION_ID=='n36_healthcheck_n36r3_preparation_001445'),req(health['healthchecks']==a.HEALTH),req(health['release_enabled'] is False and health['runtime_ready'] is False and health['replay_allowed'] is False),a.HEALTH)[-1])
ck('accepted scientific identities and gates unchanged',lambda:(req(all(plan[k]==prior[k] for k in ('protocol','protocol_review','accounting','resource_routing'))),req(old['episodes']==plan['episodes']),req(c.LIMITS==plan['limits']),req(c.WORKER_CONTRACT==plan['worker_contract']),True)[-1])
def release_reject():
 try:rel.validate_plan(plan)
 except ValueError as e:return 'expected rejection: '+str(e)
 raise ValueError('disabled draft accepted as released')
ck('production disabled-plan guard',release_reject)
ck('retained lexical reference repair',lambda:(req("launch({'path': args.plan, 'sha256': args.plan_sha256}" in (ROOT/'scripts/qd_ed_n36_runner.py').read_text()),req("{'path': args.release, 'sha256': args.release_sha256}" in (ROOT/'scripts/qd_ed_n36_runner.py').read_text()),'CLI preserves exact absolute lexical plan/release paths')[-1])
from scripts import qd_ed_n36_supervise as supervisor
ck('mandatory first C0 boundary',lambda:(req(supervisor.first_c0_boundary(plan['episodes'][0])),req(not any(supervisor.first_c0_boundary(x) for x in plan['episodes'][1:])),req("'status': 'PAUSED_FOR_ROOT_G3', 'next_row': None" in (ROOT/'scripts/qd_ed_n36_supervise.py').read_text()),'first C0 terminal pauses; no continuation override; invalid terminal stops')[-1])
# Evidence of continuity is consumed once, never recursively audited.
for f in ['001358/manifest-refresh/report-v1.json','001358/manifest-refresh/refresh-v1.py','001451/manifest-refresh/refresh-v1.py','001448/binding-refresh/production-parent-attestation-feasibility-v1.json','001445/accounting-health-repair/repair-v1.patch']:
 p=BASE/f;refs[str(p)]=bound(p)
source_delta=subprocess.check_output(['git','diff',prior['source']['commit'],auth['source'],'--','scripts/qd_ed_n36r3_admission.py','scripts/qd_ed_n36r3_preparation.py','scripts/qd_ed_n36_runner.py'],text=True)
print('SOURCE_DELTA\n'+source_delta,flush=True)
ck('final STOP and exact authority inputs stable',lambda:(stop.check(),req(read(auth['plan'])==plan),req(read(auth['bindings'])==bundle),True)[-1])
result={'checks':checks,'input_refs':list(refs.values()),'source_delta':source_delta,'cpu_affinity':sorted(os.sched_getaffinity(0)),'command':'OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 CUDA_VISIBLE_DEVICES= /home/hynx/miniconda3/envs/vla-pilot/bin/python -B '+str(Path(__file__).absolute()),'at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
with (OUT/'checks-v1.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print('FAILED',sum(x['status']=='FAIL' for x in checks),flush=True)
