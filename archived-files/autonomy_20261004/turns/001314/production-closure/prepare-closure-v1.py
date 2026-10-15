import os,sys,json,hashlib,datetime as dt,time,resource,subprocess,copy,traceback
from pathlib import Path
OUT=Path(__file__).resolve().parent
A=json.loads((OUT/'authority-v1.json').read_text()); ROOT=Path(A['worktree']); START=time.monotonic()
BASE=OUT.parents[1]; ART={}; CHECKS={}; ERRORS=[]
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2]);resource.setrlimit(resource.RLIMIT_CPU,(170,170))
STOP=[str(BASE.parent/'STOP'),'/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/STOP']
def guard():
 assert not any(os.path.lexists(p) for p in STOP),'STOP present'
 assert dt.datetime.now(dt.timezone.utc)<dt.datetime.fromisoformat(A['deadline'].replace('Z','+00:00'))
 assert time.monotonic()-START<175,'targeted check cap'
def audit(event,args):
 if event in ('socket.connect','socket.getaddrinfo'):raise PermissionError('network forbidden')
 if event=='open' and isinstance(args[0],(str,bytes)):
  p=os.fsdecode(args[0]);assert not any(x in p for x in ('/.codex/auth.json','/.git-credentials','credentials.json','2026-08-10-eds-qd-stage-guidance-transition-design.md'))
 if event=='exec' and getattr(args[0],'co_filename','')==str(ROOT/'main.py'):raise PermissionError('Main execution forbidden')
sys.addaudithook(audit)
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def ref(p):return {'path':str(p),'sha256':sha(p),'bytes':Path(p).stat().st_size}
def read(r):
 assert sha(r['path'])==r['sha256'];return json.loads(Path(r['path']).read_text())
def write(n,d):
 guard();p=OUT/n;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(d,f,indent=2,allow_nan=False);f.write('\n')
 ART[n]=ref(p);return {k:v for k,v in ART[n].items() if k!='bytes'}
def check(n,fn):
 guard();t=time.monotonic()
 try:r=fn();CHECKS[n]={'status':'PASS','seconds':time.monotonic()-t};print(n,'PASS',flush=True);return r
 except Exception as e:
  CHECKS[n]={'status':'FAIL','seconds':time.monotonic()-t,'error':str(e),'traceback':traceback.format_exc()};ERRORS.append(n);print(n,'FAIL',str(e),flush=True);return None
def git(*args):return subprocess.check_output(['git','-C',str(ROOT),*args],text=True).strip()
def main():
 guard();assert git('rev-parse','HEAD')==A['source'];assert not git('status','--porcelain=v1')
 sys.path.insert(0,str(ROOT))
 from scripts import qd_ed_n36_bridge as b,qd_ed_n36_contract as c,qd_ed_n34_source as s,qd_ed_n36_source as policy,qd_ed_final_runner as runner
 old=json.loads((BASE/'001295/plan.frozen.n36r2-v1.json').read_text());runtime=read(old['runtime']);closure=read(old['runtime_closure']);oldroot=runtime['worktree']
 paths=sorted(b.source_paths(ROOT))
 source=check('production_source_record',lambda:s.source_record(ROOT,paths))
 # Exact Git inventory is retained separately when the actual checkout cannot pass.
 groups={}; files=[]; missing=[]; mismatched=[]
 for name in paths:
  sub=next((x for x in s.PINNED_SUBMODULES if name.startswith(x+'/')),None);groups.setdefault(sub,[]).append(name)
 for sub,names in groups.items():
  pin,db=s.submodule_pin(ROOT,sub,A['source']) if sub else (A['source'],None)
  tree=s._source_tree(ROOT,pin,db);blobs={n:tree[n[len(sub)+1:] if sub else n][2] for n in names};data=s._source_blobs(ROOT,blobs.values(),db)
  for name,blob in blobs.items():
   digest=hashlib.sha256(data[blob]).hexdigest();files.append({'path':name,'sha256':digest});p=ROOT/name
   if not p.is_file():missing.append(name)
   elif sha(p)!=digest:mismatched.append(name)
 files.sort(key=lambda x:x['path']);expected={'commit':A['source'],'files':files,'sha256':b.w.canonical_sha(files)}
 sr=write('source.git-expected-v1.json',expected)
 if source is not None:sr=write('source.complete-v1.json',source)
 write('source-materialization-v1.json',{'complete':not missing and not mismatched,'missing':missing,'mismatched':mismatched,'count':len(files),'expected_source':sr,'actual_source_validator_passed':source is not None})
 def relocate(x):
  if isinstance(x,str):return x.replace(oldroot,str(ROOT))
  if isinstance(x,list):return [relocate(v) for v in x]
  if isinstance(x,dict):return {k:relocate(v) for k,v in x.items()}
  return x
 runtime=relocate(runtime);closure=relocate(closure)
 index={str(ROOT/x['path']):x['sha256'] for x in files}
 for row in runtime['files']:
  if row['path'] in index:row['sha256']=index[row['path']]
  if Path(row['path']).exists():row['size_bytes']=Path(row['path']).stat().st_size
 # Bind a fresh local config without modifying the checkout or old runtime.
 cfgpath=Path(runtime['environment']['LIBERO_CONFIG_PATH'])/'config.yaml';cfg=relocate(json.loads(cfgpath.read_text()))
 cfgref=write('libero-config/config.yaml',cfg);runtime['environment']['LIBERO_CONFIG_PATH']=str(OUT/'libero-config')
 for i,row in enumerate(runtime['files']):
  if row['path']==str(cfgpath):runtime['files'][i]={**cfgref,'resolved_path':cfgref['path'],'size_bytes':Path(cfgref['path']).stat().st_size}
 runtime['preparation']={'source':A['source'],'source_record':sr,'status':'DISABLED_PARTIAL_CPU_CLOSURE','runtime_ready':False,'release_enabled':False,'historical_runtime':old['runtime'],'historical_readiness_is_not_current':True}
 rr=write('runtime.isolated.disabled-v1.json',runtime);closure['runtime']=rr
 for name,row in closure['modules'].items():
  if row['path'] in index:row['sha256']=index[row['path']]
 cr=write('runtime-closure.isolated.disabled-v1.json',closure)
 required=closure['required_after'];assert required==read(old['runtime_closure'])['required_after']
 write('required-after.production-v1.json',{'source':A['source'],'runtime_closure':cr,'complete_inherited_production_set':True,'required_after':required,'records':{n:closure['modules'].get(n) or closure.get('generated_modules',{}).get(n) or closure.get('module_aliases',{}).get(n) for n in required},'observed_loaded_after':False,'scope':'Complete frozen production requirement, not live lifecycle coverage'})
 check('production_runtime_closure',lambda:s.verify_runtime(closure,rr))
 check('production_generated_Torch_rule',lambda:s._generated_runtime(closure))
 alias=check('production_frozen_os_path_CPU_identity',lambda:policy.live_alias(closure,None))
 # No synthetic worker/process receipt: only prospective claim validation.
 pairs={}
 for a,n in policy.IMPORTLIB_FROZEN_PAIRS:
  pairs[a]=check('production_frozen_alias_inventory_'+a,lambda a=a,n=n:policy.importlib_alias_claim(closure,None,a,n))
 write('generated-and-frozen-alias-preparation-v1.json',{'generated_modules':closure['generated_modules'],'os_path_CPU_inventory_check':alias,'importlib_prospective_inventory_checks':pairs,'worker_receipt':False,'process_bound_lifecycle_evidence':False,'generated_module_executed':False})
 missing_runtime=[row for row in runtime['files'] if not Path(row['path']).exists()]
 missing_modules={n:r for n,r in closure['modules'].items() if not Path(r['path']).exists()}
 write('runtime-materialization-v1.json',{'missing_files':missing_runtime,'missing_modules':missing_modules,'source_files_not_modified_or_materialized':True,'no_inventory_entries_removed':True})
 check('production_runtime_files',lambda:runner.verify_files(runtime['files'],allowed_roots=(ROOT,runtime['artifact_root'])))
 cohort='N36R3_NONPROGRESS_TANGENT_DEV_001314'
 rows=[{**r,'iteration':cohort,'episode_key':r['episode_key'].replace('n36r2_','n36r3_').replace('_001250','_001314')} for r in old['episodes']]
 assert len(rows)==40 and not {r['episode_key'] for r in rows}&{r['episode_key'] for r in old['episodes']}
 science=[{k:v for k,v in r.items() if k not in ('iteration','episode_key')} for r in rows]
 assert science==[{k:v for k,v in r.items() if k not in ('iteration','episode_key')} for r in old['episodes']]
 plan={'schema':'n36-release-draft-v1','frozen':False,'release_enabled':False,'source':expected,'scientific_source':expected,'worktree':str(ROOT),'artifact_root':str(OUT/'prospective-artifacts-n36r3-001314'),'runtime':rr,'runtime_closure':cr,'native_build':old['native_build'],'controller_semantics':None,'cohort':cohort,'episodes':rows,'limits':old['limits'],'worker_contract':old['worker_contract'],'deadline':A['deadline'],'stop_path':old['stop_path'],'stop_authority':old['stop_authority'],'root_review':None,'protocol':None,'protocol_review':None,'accounting':None,'authority':None,'execution_release':None,'b5_review':None,'phase_authorization':{'dev':False,'validation':False,'formal':False},'expected_manifests':{},'http_counters':'Unknown','source_binding_status':'PARTIAL_NOT_ADMITTED','production_accepted':False}
 pr=write('plan.prospective-disabled.partial-v1.json',plan)
 check('production_N36R3_expected_rows',lambda:c.expected_rows(ROOT,cohort=cohort))
 check('production_validate_disabled_N36R3_draft',lambda:c.validate_draft(plan))
 check('production_N36R3_manifest',lambda:b.manifest(plan,runtime,rows[0]))
 write('scientific-membership-and-disabled-binding-v1.json',{'plan':pr,'exact_task_seed_profile_membership_preserved':True,'count':40,'all_output_identities_fresh':True,'output_root_absent':not Path(plan['artifact_root']).exists(),'thresholds_limits_worker_contract_unchanged':True,'old_plan':ref(BASE/'001295/plan.frozen.n36r2-v1.json'),'old_N36R2_status':'INVALID; all charges retained; no accounting writes','new_accounting_or_release_authority':False})
 assert git('rev-parse','HEAD')==A['source'] and not git('status','--porcelain=v1')
 return {'source_files':len(files),'missing_source_files':len(missing),'runtime_files':len(runtime['files']),'missing_runtime_files':len(missing_runtime),'runtime_modules':len(closure['modules']),'missing_runtime_modules':len(missing_modules),'required_after_count':len(required)}
try:summary=main()
except BaseException as e:summary={};ERRORS.append('harness');CHECKS['harness']={'status':'FAIL','error':str(e),'traceback':traceback.format_exc()};print(traceback.format_exc(),flush=True)
report={'schema':'n36r3-production-closure-report-v1','node_id':'15.6','source':A['source'],'owner_source':'30c6321715df86c5bab623db607bab2811aed56d','status':'BLOCKED_PARTIAL_G2','G2':'OPEN: preparation validators did not certify complete closure','score':None,'production_accepted':False,'release_enabled':False,'source_adopted':False,'dispatch':False,'authority':ref(OUT/'authority-v1.json'),'summary':summary,'checks':CHECKS,'failing_checks':ERRORS,'artifacts':ART,'targeted_checks_wall_seconds':time.monotonic()-START,'threads':2,'broad_tests_repeated':False,'source_edits':[],'owner_state_budget_ledger_lease_lock_writes':False,'gpu_simulator_Main_provider_network_package_operations':False,'STOP_checks':{p:os.path.lexists(p) for p in STOP},'deadline':A['deadline'],'remaining_G3':['Immutable production observations independently anchored to actual worker PID/start ticks/boot identity and actual context/runtime hashes','Actual worker loaded_before/after identity equality, execution monotonicity and generated before/after identity equality','Main lifecycle execution and complete required_after coverage; CPU preparation is not lifecycle evidence'],'remaining_G4':['Root exact-source/composition review and adoption; owner remains at prior source','Fresh N36R3 finite protocol/allocation/accounting and resource/readiness bindings retaining all old INVALID charges and protected reserves','External root release and phase admission; scientific audits and success gates remain unchanged and unproved'],'bounded_repairs_needed':['Materialize the missing pinned dependency source files listed in source-materialization-v1.json from their already-local Git objects; do not change their content or pins. Populate missing frozen runtime assets from inventoried bytes. This executor did not write source files.','Add an explicitly disabled finite N36R3 draft cohort/identity preparation path in scripts/qd_ed_n36_contract.py and scripts/qd_ed_n36_prepare.py, with corresponding structural draft protocol/accounting validation. Preserve release/admission hard rejection until separately root-authorized bindings exist. Do not alias N36R2 or reset charges.','Re-run bounded exact-source/source-runtime validators and prepare controller/manifests only after materialization and draft tooling are repaired. Any tooling source commit changes the exact-source target and needs renewed root source review.']}
with (OUT/'report-v1.json').open('x') as f:json.dump(report,f,indent=2);f.write('\n')
md='G2 remains OPEN / BLOCKED_PARTIAL for source `'+A['source']+'`.\n\nFresh exact Git source inventory, isolated disabled runtime/closure candidate, complete inherited production required_after inventory, generated Torch provenance and frozen alias checks, and a fresh-identity disabled partial binding are retained with hashes in report-v1.json. These candidates are not certified complete.\n\nFailures: '+', '.join(ERRORS)+'. Counts: '+json.dumps(summary)+'.\n\nMissing dependency files require exact pinned materialization. Production tooling rejects N36R3 as unsupported; bounded disabled draft cohort/protocol/accounting support is needed without weakening admission. No source files were edited. Full failure commands and evidence are in the JSON report and preparation log.\n\nG3 actual process-bound worker before/after, Main lifecycle and required-after observations remain absent. G4 root adoption, fresh accounting retaining old INVALID charges, readiness/release and scientific evidence remain outstanding. Score=null; production_accepted=false; release_enabled=false; no dispatch.\n'
with (OUT/'report-v1.md').open('x') as f:f.write(md)
print(json.dumps({'status':report['status'],'summary':summary,'seconds':report['targeted_checks_wall_seconds']}),flush=True)
