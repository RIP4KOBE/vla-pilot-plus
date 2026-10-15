import os,sys,json,hashlib,datetime as dt,time,resource,copy,subprocess,traceback,shutil,importlib
from pathlib import Path
OUT=Path(__file__).resolve().parent
ROOT=Path.cwd().resolve()
AUTH=json.loads((OUT/'authority-v1.json').read_text())
OLD=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001250/recovery-preparation')
START=time.monotonic();CHECKS={};ART={}
resource.setrlimit(resource.RLIMIT_CPU,(350,350));os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2])
def guard():
 assert not any(os.path.lexists(p) for p in AUTH['STOP_paths']), 'canonical STOP present'
 assert dt.datetime.now(dt.timezone.utc)<dt.datetime.fromisoformat(AUTH['deadline'].replace('Z','+00:00'))
 assert time.monotonic()-START<340 and os.environ['CUDA_VISIBLE_DEVICES']==''
def audit(event,args):
 if event=='open' and isinstance(args[0],(str,bytes)):
  p=os.fsdecode(args[0]).lower()
  assert not any(t in p for t in ('/.codex/auth.json','/.git-credentials','/credentials.json','/credentials/','/superpowers','2026-08-10-eds-qd-stage-guidance-transition-design')), 'prohibited open'
 if event in ('socket.connect','socket.getaddrinfo'):raise PermissionError('network forbidden')
 if event=='exec' and getattr(args[0],'co_filename','').endswith(('qd_ed_poe_launch.py','/main.py')):raise PermissionError('launcher/Main execution forbidden')
sys.addaudithook(audit)
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def ref(p):return {'path':str(Path(p).resolve()),'sha256':sha(p)}
def read(r):
 assert sha(r['path'])==r['sha256'];return json.loads(Path(r['path']).read_text())
def write(name,v):
 p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True);assert not p.exists(),str(p)
 p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n');ART[name]=ref(p);return ART[name]
def check(name,fn):
 guard();t=time.monotonic()
 try:
  v=fn();CHECKS[name]={'status':'PASS','seconds':time.monotonic()-t};print(name,'PASS',flush=True);return v
 except BaseException as e:
  CHECKS[name]={'status':'FAIL','seconds':time.monotonic()-t,'error':repr(e)};raise

def main():
 guard();sys.path.insert(0,str(ROOT))
 from scripts import qd_ed_n36_bridge as b,qd_ed_n36_contract as c,qd_ed_n34_source as s,qd_ed_n36_prepare as prep,qd_ed_final_runner as runner
 from scripts import qd_ed_n34_controller as controller,qd_ed_n36_release as release
 old=read(ref(OLD/'draft/plan.partial.draft-v1.json'));runtime=read(old['runtime']);owner=runtime['worktree']
 def relocate(x):
  if isinstance(x,str):return x.replace(owner,str(ROOT))
  if isinstance(x,list):return [relocate(v) for v in x]
  if isinstance(x,dict):return {k:relocate(v) for k,v in x.items()}
  return x
 source=check('production_source_record',lambda:s.source_record(ROOT,b.source_paths(ROOT)))
 assert source['commit']==AUTH['base_source'];sr=write('source.complete-v1.json',source)
 assert 'scripts/qd_ed_poe_launch.py' in {x['path'] for x in source['files']}
 material=[]
 # No source tree symlinks. Only individually inventoried, missing non-source assets.
 for row in runtime['files']:
  if not row['path'].startswith(owner+'/'):continue
  guard();p=Path(relocate(row['path']));original=Path(row['path']);kind='existing'
  if not os.path.lexists(p):
   assert str(p.relative_to(ROOT)) not in b.source_paths(ROOT),'missing source must use Git materialization'
   p.parent.mkdir(parents=True,exist_ok=True)
   if 'link_target' in row:
    assert not Path(row['link_target']).is_absolute();p.symlink_to(row['link_target']);kind='preserved_relative_non_source_symlink'
   else:
    assert sha(original)==row['sha256'];shutil.copyfile(original,p);kind='copied_non_source_bytes'
  material.append({'original':row,'relocated':relocate(row),'action':kind})
 check('relocated_asset_bytes',lambda:runner.verify_files([x['relocated'] for x in material],allowed_roots=(ROOT,)))
 write('relocated-assets-v1.json',{'files':material,'count':len(material),'whole_source_tree_linked':False})
 runtime=relocate(runtime)
 # Rebind LIBERO configuration rather than retaining an owner-source search path.
 cfgpath=Path(runtime['environment']['LIBERO_CONFIG_PATH'])/'config.yaml'
 cfg=json.loads(cfgpath.read_text());oldcfg=ref(cfgpath)
 cfg['benchmark_root']=str(ROOT/'third_party/libero_pro/libero/libero');cfg['assets']=str(ROOT/'third_party/libero_pro/libero/libero/assets')
 cfgref=write('libero-config/config.yaml',cfg)
 runtime['environment']['LIBERO_CONFIG_PATH']=str(OUT/'libero-config')
 matches=[i for i,x in enumerate(runtime['files']) if x['path']==str(cfgpath)];assert len(matches)==1
 runtime['files'][matches[0]]={'path':cfgref['path'],'resolved_path':cfgref['path'],'sha256':cfgref['sha256'],'size_bytes':Path(cfgref['path']).stat().st_size}
 runtime['preparation_history']=runtime.get('preparation_history',[])+[runtime['preparation']]
 runtime['preparation']={'source':source['commit'],'source_record':sr,'release_enabled':False,'runtime_ready':False,'status':'CPU_ISOLATED_PROSPECTIVE_BINDING','historical_runtime':old['runtime'],'historical_device_provider_receipts_are_not_current_readiness':True,'no_provider_or_device_probe':True,'libero_config_rebound_from':oldcfg}
 rr=write('runtime.isolated.draft-v1.json',runtime)
 closure=read(old['runtime_closure']);original_modules=copy.deepcopy(closure['modules']);closure['runtime']=rr
 assert closure['modules']==original_modules
 cr=write('runtime-closure.isolated.draft-v1.json',closure)
 check('production_runtime_closure',lambda:s.verify_runtime(closure,rr))
 check('production_runtime_files',lambda:runner.verify_files(runtime['files'],allowed_roots=(ROOT,runtime['artifact_root'])))
 proof=read(old['controller_semantics']);proof['runtime']=rr;proof['rebound_from']=old['controller_semantics']
 proof['scope']='Inherited ROOT_REVIEWED source findings only; every referenced source byte reverified. New isolated composition awaits independent root review. No live instance, physical gain or production approval.'
 for name,r in list(proof['review_evidence'].items()):
  e=relocate(read(r));e.update(runtime=rr,source_commit=source['commit'],rebound_from=r,binding_review=proof['scope'])
  for f in e['sources']:assert sha(f['path'])==f['sha256']
  proof['review_evidence'][name]=write('controller-'+name+'.isolated-v1.json',e)
 proofref=write('controller-semantics.isolated.draft-v1.json',proof)
 check('production_controller_semantics',lambda:controller.verify_semantics(proofref,rr,closure))
 plan=check('production_prepare_all40',lambda:prep.prepare(OUT/'prepared',rr,runtime_closure_ref=cr,controller_semantics_ref=proofref,native_build_ref=old['native_build'],root=ROOT,recovery_protocol_ref=old['protocol']))
 # Input validator metadata remains identical except checkout location; no authority.
 for k in ['run_name','input_contract_label','runtime_inventory_path','runtime_inventory_sha256','seed_plan_path','seed_plan_sha256']:plan[k]=relocate(old[k])
 planref=write('plan.complete-disabled-v1.json',plan)
 check('production_verify_sources',lambda:b.verify_sources(plan))
 check('production_validate_draft',lambda:c.validate_draft(plan))
 check('production_runtime_inputs_all40_with_checkpoint_bytes',lambda:runner.validate_runtime_inputs(plan,runtime,b.profiles(ROOT),ROOT,{'artifacts':runtime['artifact_root']}))
 fingerprints={str(Path(x['path']).resolve()) for x in runtime['files']}
 for task in runtime['tasks'].values():
  actual={str(p.resolve()) for p in Path(task['cache_dir']).rglob('*') if p.is_file()};assert actual and actual<=fingerprints
 def norm(x):
  x=json.loads(json.dumps(x))
  for key in ['n34_runtime_binding','n36_runtime_binding']:
   if x.get(key):x[key]['source_commit']='<source>';x[key]['run_id']='<episode>'
  if x.get('mechanism_pretest'):x['mechanism_pretest']['run_id']='<episode>';x['mechanism_pretest']['output_dir']='<output>/mechanism'
  return x
 joins=[]
 def verify_all():
  for row in plan['episodes']:
   guard();m=b.verify_manifest(plan['expected_manifests'][row['episode_key']],plan,runtime,row)
   prior=read(old['expected_manifests'][row['episode_key']]);assert prior['row']==row and norm(prior['resolved_config'])==norm(m['resolved_config'])
   config,resolved=b.compose_launch(m['argv'],ROOT);assert runner.canonical_sha(config)==m['composed_config_sha256'] if hasattr(runner,'canonical_sha') else b.w.canonical_sha(config)==m['composed_config_sha256']
   assert not Path(m['output_dir']).exists();assert row['split']=='dev'
   context={'schema':'n36-worker-context-v1','plan':planref,'release':None,'expected_manifest':plan['expected_manifests'][row['episode_key']],'episode_key':row['episode_key'],'attempt_id':row['episode_key'],'main_argv':m['argv'][1:],'worker_contract':c.WORKER_CONTRACT}
   ctx=write('contexts/'+row['episode_key']+'.disabled.json',context)
   joins.append({'row':row,'manifest':plan['expected_manifests'][row['episode_key']],'context':ctx,'argv_sha256':b.w.canonical_sha(m['argv']),'composed_config_sha256':m['composed_config_sha256'],'resolved_config_sha256':b.w.canonical_sha(m['resolved_config']),'output_dir':m['output_dir'],'output_absent':True,'science_matches_prior':True,'source_runtime_controller_joins':True})
 check('production_verify_manifest_all40',verify_all)
 write('all40-joins-v1.json',{'count':len(joins),'rows':joins,'contexts_are_disabled_prospective_only':True,'worker_context_validation_requires_separate_release':True})
 try:release.validate_plan(plan)
 except ValueError as e:
  assert 'N36R2 draft only' in str(e);write('b5-hard-rejection-v1.json',{'expected_rejection':str(e),'release_enabled':False})
 else:raise AssertionError('B5 unexpectedly admitted')
 # Resolve all dependency source modules without executing simulator/model modules.
 from importlib.machinery import PathFinder
 search=[str(ROOT)]+runtime['environment']['PYTHONPATH'].split(os.pathsep)+[p for p in sys.path if p and p!=str(ROOT)]
 resolutions=[]
 for name in ['lerobot','lerobot.processor','models.rdt_runner','configs.state_vec','libero','libero.libero','libero.libero.envs.env_wrapper','robosuite.controllers.osc']:
  path=search;spec=None
  for i in range(1,len(name.split('.'))+1):
   full='.'.join(name.split('.')[:i]);spec=PathFinder.find_spec(full,path);assert spec is not None,full;path=spec.submodule_search_locations
  if spec.origin:
   p=Path(spec.origin).resolve();record={'path':str(p),'sha256':sha(p)}
   if name.startswith(('lerobot','libero','models','configs')):assert p.is_relative_to(ROOT)
  else:record={'namespace_locations':list(spec.submodule_search_locations)}
  resolutions.append({'module':name,'resolved_origin':record,'module_executed':False})
 sys.path[:0]=runtime['environment']['PYTHONPATH'].split(os.pathsep)
 loaded={}
 for name in ['lerobot','libero']:
  mod=importlib.import_module(name);loaded[name]={'path':str(Path(mod.__file__).resolve()),'sha256':sha(mod.__file__)};assert Path(mod.__file__).resolve().is_relative_to(ROOT)
 check('production_loaded_source_origins',lambda:s.attest_loaded(ROOT,source))
 write('import-origins-v1.json',{'search_path':search,'resolved_only':resolutions,'actual_cpu_imports':loaded,'source_attestor_passed':True,'all_worker_imports_observed':False})
 write('composition-result-v1.json',{'source':sr,'plan':planref,'runtime':rr,'runtime_closure':cr,'controller_semantics':proofref,'native_build':old['native_build'],'all40_complete':True,'release_enabled':False,'production_accepted':False})

if __name__=='__main__':
 try:main();status='CPU_PREPARATION_COMPLETE_REVIEW_REQUIRED';error=None
 except BaseException as e:status='BLOCKED_PARTIAL';error={'error':repr(e),'traceback':traceback.format_exc()};print(error['traceback'],flush=True)
 report={'schema':'n36r2-source-runtime-cpu-report-v1','node_id':'15.6','status':status,'at':dt.datetime.now(dt.timezone.utc).isoformat(),'source_commit':AUTH['base_source'],'owner_commit':'ca4e6a96d049c7ebb1f302d755883388ddbfdbd8','score':None,'production_accepted':False,'release_enabled':False,'source_adopted':False,'checks':CHECKS,'artifacts':ART.copy(),'error':error,'elapsed_seconds':time.monotonic()-START,'cpu_seconds':resource.getrusage(resource.RUSAGE_SELF).ru_utime+resource.getrusage(resource.RUSAGE_SELF).ru_stime,'full_before_after_worker_receipts':False,'immutable_live_runtime_observations':False,'B5':'HARD_REJECTED','owner_state_or_ledgers_written':False}
 write('preparation-attempt-v1.json',report)
 sys.exit(0 if error is None else 1)
