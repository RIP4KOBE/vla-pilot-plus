import os,sys,json,hashlib,datetime as dt,time,resource,subprocess,traceback,copy
from pathlib import Path
OUT=Path(__file__).resolve().parent;A=json.loads((OUT/'authority-v1.json').read_text());ROOT=Path(A['worktree']);BASE=OUT.parents[1];PRIOR=BASE/'001314/production-closure';START=time.monotonic()
sys.dont_write_bytecode=True;sys.path.insert(0,str(ROOT));os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2]);resource.setrlimit(resource.RLIMIT_CPU,(150,150))
ART={};CHECKS={};ERRORS=[]
def guard():
 assert not os.path.lexists(BASE.parent/'STOP') and not os.path.lexists(ROOT.parents[2]/'autonomy_20261004/STOP')
 assert dt.datetime.now(dt.timezone.utc)<dt.datetime.fromisoformat(A['deadline'].replace('Z','+00:00'))
 assert time.monotonic()-START<150

def audit(event,args):
 if event in ('socket.connect','socket.getaddrinfo'):raise PermissionError('network forbidden')
 if event=='open' and isinstance(args[0],(str,bytes)):
  name=os.fsdecode(args[0]);assert not any(x in name for x in ('/.codex/auth.json','/.git-credentials','credentials.json','2026-08-10-eds-qd-stage-guidance-transition-design.md','attempt-ledger.jsonl','gpu-healthcheck-ledger.jsonl'))
 if event=='exec' and getattr(args[0],'co_filename','')==str(ROOT/'main.py'):raise PermissionError('Main execution forbidden')
sys.addaudithook(audit)
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def ref(p):return {'path':str(p),'sha256':sha(p)}
def read(r):
 assert sha(r['path'])==r['sha256'];return json.loads(Path(r['path']).read_text())
def write(name,value):
 guard();p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
 ART[name]=ref(p);return ART[name]
def check(name,fn):
 guard();t=time.monotonic()
 try:
  result=fn();CHECKS[name]={'status':'PASS','seconds':time.monotonic()-t};print(name,'PASS',flush=True);return result
 except Exception as e:
  CHECKS[name]={'status':'FAIL','seconds':time.monotonic()-t,'error':str(e),'traceback':traceback.format_exc()};ERRORS.append(name);print(name,'FAIL',str(e),flush=True);return None

def main():
 guard()
 from scripts import qd_ed_n36_bridge as b,qd_ed_n36_contract as c,qd_ed_n36_prepare as prep,qd_ed_n34_source as s,qd_ed_n36_source as policy,qd_ed_final_runner as runner
 head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
 source=check('production_source_record',lambda:s.source_record(ROOT,b.source_paths(ROOT)));assert source is not None
 sr=write('source.complete-v1.json',source)
 runtime=json.loads((PRIOR/'runtime.isolated.disabled-v1.json').read_text());closure=json.loads((PRIOR/'runtime-closure.isolated.disabled-v1.json').read_text())
 previous_path=BASE/'001295/plan.frozen.n36r2-v1.json';previous=json.loads(previous_path.read_text())
 materialized={str(ROOT/r['path']):r for r in json.loads((OUT/'isolated-materialization-v1.json').read_text())['records']}
 index={str(ROOT/r['path']):r['sha256'] for r in source['files']}
 changes=[]
 cfgold=Path(runtime['environment']['LIBERO_CONFIG_PATH'])/'config.yaml'
 cfgref=write('libero-config/config.yaml',json.loads(cfgold.read_text()));runtime['environment']['LIBERO_CONFIG_PATH']=str(OUT/'libero-config')
 for i,row in enumerate(runtime['files']):
  before=copy.deepcopy(row)
  if row['path'] in materialized and 'link_target' in row:
   row.pop('link_target');row['resolved_path']=str(Path(row['path']).resolve())
  if row['path'] in index:row['sha256']=index[row['path']];row['size_bytes']=Path(row['path']).stat().st_size
  if row['path']==str(cfgold):
   runtime['files'][i]={**cfgref,'resolved_path':cfgref['path'],'size_bytes':Path(cfgref['path']).stat().st_size};row=runtime['files'][i]
  if before!=row:changes.append({'before':before,'after':row})
 runtime['preparation']={'source':head,'source_record':sr,'status':'DISABLED_CPU_CLOSURE','runtime_ready':False,'release_enabled':False,'historical_runtime':previous['runtime'],'historical_readiness_is_not_current':True}
 rr=write('runtime.isolated.disabled-v1.json',runtime);closure['runtime']=rr
 for row in closure['modules'].values():
  if row['path'] in index:row['sha256']=index[row['path']]
 cr=write('runtime-closure.isolated.disabled-v1.json',closure)
 write('runtime-rebinding-provenance-v1.json',{'prior_runtime':ref(PRIOR/'runtime.isolated.disabled-v1.json'),'changes':changes,'inventory_entries_removed':False,'isolated_regular_symlink_target_copies':12})
 check('production_runtime_closure',lambda:s.verify_runtime(closure,rr))
 check('production_runtime_files',lambda:runner.verify_files(runtime['files'],allowed_roots=(ROOT,runtime['artifact_root'])))
 check('production_generated_Torch_rule',lambda:s._generated_runtime(closure))
 check('production_frozen_os_path_CPU_identity',lambda:policy.live_alias(closure,None))
 for alias,name in policy.IMPORTLIB_FROZEN_PAIRS:check('production_alias_'+alias,lambda alias=alias,name=name:policy.importlib_alias_claim(closure,None,alias,name))
 assert closure['required_after']==read(previous['runtime_closure'])['required_after']
 write('required-after.production-v1.json',{'required_after':closure['required_after'],'runtime_closure':cr,'observed_loaded_after':False,'process_bound_lifecycle_evidence':False})
 rows=c.expected_rows(ROOT,cohort=c.DRAFT_N36R3_COHORT)
 science=lambda rs:[{k:v for k,v in r.items() if k not in ('iteration','episode_key')} for r in rs]
 assert science(rows)==science(previous['episodes']);assert not {r['episode_key'] for r in rows}&{r['episode_key'] for r in previous['episodes']}
 allocation=write('allocation.disabled-v1.json',{'schema':'n36r3-allocation-draft-v1','cohort':c.DRAFT_N36R3_COHORT,'episodes':rows,'automatic_recoveries':0,'allocation_is_not_authority':True,'release_enabled':False})
 terminal_ref=ref(BASE/'001316/terminal-reconciliation-v1.json');terminal=read(terminal_ref)
 accounting=write('accounting.disabled-v1.json',{'schema':'n36r3-accounting-draft-v1','cohort':c.DRAFT_N36R3_COHORT,'inherited_accounting':previous['accounting'],'terminal_reconciliation':terminal_ref,'retained_ledger_prefix':terminal['ledger_prefix'],'retained_health_ledger_prefix':terminal['health_ledger_prefix'],'allocation':allocation,'all_prior_charges_retained':True,'N36R2_status':'INVALID','N36R2_charges_retained':True,'protected_gpu_hours':c.CAPS['protected_gpu_hours'],'automatic_recoveries':0,'new_budget_authority':False,'current_headroom':None,'release_enabled':False})
 protocol=write('protocol.disabled-v1.json',{'schema':'n36r3-operational-protocol-draft-v1','cohort':c.DRAFT_N36R3_COHORT,'previous_plan':ref(previous_path),'inherited_protocol':previous['protocol'],'inherited_protocol_review':previous['protocol_review'],'accounting':accounting,'allocation':allocation,'episodes':rows,'automatic_recoveries':0,'scientific_changes':False,'release_enabled':False})
 historical=read(previous['controller_semantics'])
 controller=write('controller-semantics.disabled-v1.json',{'schema':'n36r3-controller-semantics-draft-v1','status':'DISABLED_PENDING_ROOT_REVIEW','release_enabled':False,'runtime':rr,'inherited_review':previous['controller_semantics'],'module':historical['module'],'source':historical['source'],'instance':historical['instance'],'semantics':historical['semantics']})
 plan=check('production_prepare_disabled_N36R3',lambda:prep.prepare(OUT/'draft',rr,runtime_closure_ref=cr,controller_semantics_ref=controller,native_build_ref=previous['native_build'],root=ROOT,recovery_protocol_ref=protocol))
 if plan is not None:
  ART['draft/plan.draft.json']=ref(OUT/'draft/plan.draft.json')
  check('production_validate_disabled_N36R3_draft',lambda:c.validate_draft(plan))
  check('all40_manifests',lambda:[b._verify_manifest_bound(plan['expected_manifests'][r['episode_key']],plan,runtime,r) for r in rows])
  ART.update({'draft/expected/'+Path(v['path']).name:v for v in plan['expected_manifests'].values()})
 return {'source_before':A['source'],'source_after':head,'source_files':len(source['files']),'runtime_files':len(runtime['files']),'runtime_modules':len(closure['modules']),'required_after_count':len(closure['required_after']),'draft_prepared':plan is not None,'scientific_membership_seeds_limits_preserved':True}
try:summary=main()
except BaseException as e:
 summary={};ERRORS.append('harness');CHECKS['harness']={'status':'FAIL','error':str(e),'traceback':traceback.format_exc()};print(traceback.format_exc(),flush=True)
with (OUT/'validation-results-v1.json').open('x') as f:json.dump({'summary':summary,'checks':CHECKS,'failing_checks':ERRORS,'artifacts':ART,'seconds':time.monotonic()-START},f,indent=2)
print('FINISHED',time.monotonic()-START,ERRORS,flush=True)
