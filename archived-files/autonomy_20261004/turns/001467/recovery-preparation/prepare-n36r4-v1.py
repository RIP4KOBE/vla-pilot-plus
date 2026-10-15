"""Bounded artifact-only N36R4 preparation. Never authorizes or executes a cell."""
import os,sys,json,hashlib,copy,datetime as dt,time,resource,signal,subprocess,ast,types,traceback
from decimal import Decimal as D
from pathlib import Path
OUT=Path(__file__).absolute().parent
BASE=OUT.parents[2]
A=json.loads((OUT/'authority-v1.json').read_text());ROOT=Path(A['worktree'])
sys.dont_write_bytecode=True;sys.path.insert(0,str(ROOT))
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2]);resource.setrlimit(resource.RLIMIT_CPU,(600,600));signal.alarm(700)
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='2'
os.environ.update(CUDA_VISIBLE_DEVICES='',GIT_OPTIONAL_LOCKS='0',GIT_NO_LAZY_FETCH='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
START=time.monotonic();INPUTS={};ART={};CHECKS={};ERRORS=[]
def fence(event,args):
 if event in ('socket.connect','socket.getaddrinfo'):raise PermissionError('network forbidden')
 if event=='subprocess.Popen':
  argv=args[1]
  assert isinstance(argv,(list,tuple)) and Path(argv[0]).name=='git','only passive Git allowed'
  assert any(x in argv for x in ('rev-parse','status','diff','ls-tree','cat-file','config'))
 if event=='open' and isinstance(args[0],(str,bytes)):
  name=os.path.abspath(os.fsdecode(args[0]));low=name.lower()
  assert not any(x in low for x in ('/.codex/auth.json','/.git-credentials','credentials.json','2026-08-10-eds-qd-stage-guidance-transition-design.md'))
  flags=args[2]
  if isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):assert name=='/dev/null' or Path(name).resolve().is_relative_to(OUT.resolve()),'outside output write'
 if event in ('os.rename','os.remove','os.rmdir','os.mkdir'):
  for name in args[:2] if event=='os.rename' else args[:1]:
   if isinstance(name,(str,bytes)):assert Path(os.fsdecode(name)).resolve().is_relative_to(OUT.resolve())
sys.addaudithook(fence)
from scripts import qd_ed_n36_stop as stop
stop.check(need=700)
def guard():
 stop.check();assert time.monotonic()-START<700
 launch=json.loads((OUT/'executor-process-v1.json').read_text());assert time.time()-launch['started_unix']<900

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for raw in iter(lambda:f.read(8*1024*1024),b''):h.update(raw)
 return h.hexdigest()
def ref(p):
 p=Path(p);return {'path':str(p),'sha256':sha(p)}
def load(p):
 p=Path(p);r=ref(p);INPUTS[str(p)]=r;return json.loads(p.read_text())
def read(r):
 assert sha(r['path'])==r['sha256'];return load(r['path'])
def write(name,v):
 guard();p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n')
 ART[name]=ref(p);return ART[name]
def git(*args):
 p=subprocess.run(['git','-C',str(ROOT),*args],capture_output=True,text=True);assert p.returncode==0,p.stderr;return p.stdout.strip()
def check(name,fn):
 guard();t=time.monotonic();v=fn();CHECKS[name]={'status':'PASS','seconds':time.monotonic()-t};print(name,'PASS',flush=True);return v
def require(x,m):
 if not x:raise ValueError(m)
def main():
 global PLAN,ARITH
 assert git('rev-parse','HEAD')==A['source'] and not git('status','--porcelain','--untracked-files=no')
 read(A['accepted_repair']);standing=read(A['user_authority']);assert standing['approved']
 oldreport=load(BASE/'turns/001451/manifest-refresh/report-v1.json');old=read(oldreport['plan'])
 accounting=load(BASE/'turns/001455/accounting-v1.json');terminal=load(BASE/'turns/001460/terminal-reconciliation-v1.json')
 assert terminal['snapshot']['dispatched']==506 and terminal['snapshot']['gpu_hours_consumed']==75.60616276674473
 assert not terminal['native_G3_accepted'] and terminal['no_later_cell_authorized']
 # Hash owner journals without parsing protected outcome rows. Accepted terminal supplies aggregate accounting.
 for r in terminal['ledger_prefixes'].values():
  assert Path(r['path']).stat().st_size==r['bytes'] and sha(r['path'])==r['sha256'];INPUTS[r['path']]=ref(r['path'])
 from scripts import qd_ed_n36_bridge as b,qd_ed_n36_contract as c,qd_ed_n34_source as s,qd_ed_n36r3_admission as admission
 source=check('exact_committed_source_inventory',lambda:s.source_record(ROOT,b.source_paths(ROOT)))
 assert source['commit']==A['source'];sr=write('source.complete-v1.json',source)
 changed=git('diff','--name-only',old['source']['commit'],A['source']).splitlines()
 write('source-delta-v1.json',{'parent_source':old['source']['commit'],'source':A['source'],'changed_paths':changed,'accepted_review':A['accepted_repair'],'inventory':sr,'source_edited':False})
 runtime=read(old['runtime']);prior_runtime=copy.deepcopy(runtime);closure=read(old['runtime_closure']);prior_closure=copy.deepcopy(closure)
 index={str(ROOT/x['path']):x['sha256'] for x in source['files']};deltas=[]
 for row in runtime['files']:
  if row['path'] in index:
   before=copy.deepcopy(row);row['sha256']=index[row['path']];row['size_bytes']=Path(row['path']).stat().st_size
   if row!=before:deltas.append({'before':before,'after':copy.deepcopy(row)})
 # Historical readiness is not current readiness, including nested GPU metadata.
 history={k:copy.deepcopy(runtime.get(k)) for k in ('cuda_egl_verified','metadata_mapping_verified','provider_ready','cuda_egl_probe','gpu_mapping','preparation','preparation_history')}
 for k in ('cuda_egl_verified','metadata_mapping_verified','provider_ready'):runtime[k]=False
 runtime['cuda_egl_probe']=None
 for k in ('cuda_egl_verified','metadata_mapping_verified'):runtime['gpu_mapping'][k]=False
 runtime.pop('preparation_history',None)
 runtime['preparation']={'source':A['source'],'source_record':sr,'cohort':'N36R4_NONPROGRESS_TANGENT_DEV_001467','status':'DISABLED_CPU_DRAFT','runtime_ready':False,'release_enabled':False,'historical_runtime':old['runtime'],'historical_readiness_is_not_current':True}
 rr=write('runtime.isolated.disabled-v1.json',runtime)
 modules=[]
 for name,row in closure['modules'].items():
  if row.get('path') in index and row['sha256']!=index[row['path']]:
   modules.append({'module':name,'before':copy.deepcopy(row),'after_sha256':index[row['path']]});row['sha256']=index[row['path']]
 closure['runtime']=rr;cr=write('runtime-closure.isolated.disabled-v1.json',closure)
 write('runtime-rebinding-provenance-v1.json',{'prior_runtime':old['runtime'],'prior_closure':old['runtime_closure'],'source_updates':deltas,'module_updates':modules,'historical_readiness_not_transferred':history,'removed_inventory_entries':[]})
 check('passive_runtime_closure_bytes',lambda:s.verify_runtime(closure,rr))
 assert closure['required_after']==prior_closure['required_after']
 write('required-after.production-v1.json',{'runtime_closure':cr,'required_after':closure['required_after'],'actual_worker_observed':False,'native_G3_accepted':False})
 dino=[r for r in runtime['files'] if '/facebookresearch_dinov2_main/' in r['path']]
 assert dino and dino==[r for r in prior_runtime['files'] if '/facebookresearch_dinov2_main/' in r['path']]
 for r in dino:assert sha(r['path'])==r['sha256']
 write('dino-passive-inventory-v1.json',{'runtime':rr,'accepted_repair':A['accepted_repair'],'files':dino,'all_hashes_checked':True,'model_constructed':False,'lazy_import_execution_covered':False,'boundary':'Passive bytes/path coverage only; cannot prove model-construction lazy import execution or loaded origins without exercising those paths. No weights/model load, GPU, or downloads performed.'})
 native=read(old['native_build'])
 # Pure native manifest function; no Torch import or shared library loading.
 tree=ast.parse((ROOT/'scripts/qd_ed_n36_build.py').read_text());subset=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='manifest' or isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='REQUIRED' for x in n.targets)]
 ns={'w':types.SimpleNamespace(read_ref=read,require=require,sha=sha),'Path':Path};exec(compile(ast.Module(body=subset,type_ignores=[]),'passive-native-manifest','exec'),ns)
 check('passive_native_inventory',lambda:ns['manifest'](old['native_build']))
 nr=write('native-build.disabled-v1.json',native)
 controller=read(old['controller_semantics']);controller.pop('reviewed_draft',None)
 controller.update(runtime=rr,runtime_closure=cr,source_commit=A['source'],status='DISABLED_PENDING_ROOT_REVIEW',inherited_review=old['controller_semantics'],release_enabled=False,scope='Inherited unchanged controller findings rebound to N36R4 source/runtime; root review and actual first-C0 instance/native evidence required.')
 for k,r in list(controller['review_evidence'].items()):
  ev=read(r)
  for v in ev['sources']:assert sha(v['path'])==v['sha256']
  ev.update(runtime=rr,runtime_closure=cr,source_commit=A['source'],rebound_from=r,status='DISABLED_PENDING_ROOT_REVIEW',release_enabled=False,binding_review='CPU prospective binding only; root review required.')
  controller['review_evidence'][k]=write('controller-evidence/'+k+'.disabled-v1.json',ev)
 ctr=write('controller-semantics.disabled-v1.json',controller)
 plan=copy.deepcopy(old);PLAN=plan
 plan.update(cohort='N36R4_NONPROGRESS_TANGENT_DEV_001467',source=source,scientific_source=source,runtime=rr,runtime_closure=cr,native_build=nr,controller_semantics=ctr,artifact_root=str(OUT/'prospective-artifacts-001467'),expected_manifests={},protocol=None,accounting=None)
 for row in plan['episodes']:
  row['iteration']=plan['cohort'];row['episode_key']=f'n36r4_dev_t{row["task_id"]:02d}_{row["profile"].lower()}_001467'
 check('owner_lexical_routing',lambda:admission.owner_root(plan))
 check('canonical_STOP_deadline_binding',lambda:c.validate_stop_binding(plan))
 assert all({k:v for k,v in x.items() if k not in ('iteration','episode_key')}=={k:v for k,v in y.items() if k not in ('iteration','episode_key')} for x,y in zip(old['episodes'],plan['episodes']))
 assert plan['limits']==c.LIMITS and plan['worker_contract']==c.WORKER_CONTRACT
 snap=terminal['snapshot'];caps=accounting['caps'];margin=D(accounting['arithmetic']['hours']['retained_admission_margin']);effective=D(accounting['arithmetic']['hours']['effective_cap']);retained=D(str(snap['gpu_hours_consumed']))
 protected={k:max(D(0),D(str(v))-D(str(snap['gpu_hours_by_bucket'][k]))) for k,v in caps['protected_gpu_hours'].items()}
 now=dt.datetime.now(dt.timezone.utc);end=dt.datetime.fromisoformat(A['deadline'].replace('Z','+00:00'));wall=D(str((end-now).total_seconds()))
 buckets={}
 for k,cap in caps['buckets'].items():
  addition={'baseline':10,'development':30}.get(k,0);before=snap['by_bucket'][k];buckets[k]={'before':before,'addition':addition,'after':before+addition,'cap':cap,'remaining_after':cap-before-addition}
 ARITH={'schema':'n36r4-prospective-finite-accounting-v1','cohort':plan['cohort'],'standing_authority':A['user_authority'],'draft_only':True,'root_adopted':False,'release_enabled':False,'retained_snapshot':snap,'retained_ledger_prefixes':terminal['ledger_prefixes'],'retained_accounting':ref(BASE/'turns/001455/accounting-v1.json'),'terminal_reconciliation':ref(BASE/'turns/001460/terminal-reconciliation-v1.json'),'caps':caps,'buckets':buckets,'retained_attempts':506,'new_primary_attempts':40,'prospective_attempts':546,'remaining_attempts_after':1254,'automatic_recoveries':0,'allocation_rationale':'New independent recovery cohort allocates ten C0 baseline and thirty development cells. Operational recovery does not relabel these as retry-bucket attempts. Recovery bucket retains 27/60; 33 remain, none allocated or borrowed. No prior control pooling or invalid-success substitution.','protected_remaining_attempts':{'validation':120,'formal':40},'protected_remaining_gpu_hours':{k:str(v) for k,v in protected.items()},'hours':{'retained':str(retained),'retained_admission_margin':str(margin),'conservative_before':str(retained+margin),'finite_cohort':'21','conservative_after':str(retained+margin+D(21)),'absolute_cap':'224','effective_cap':str(effective),'absolute_remaining_after':str(D(224)-retained-margin-D(21)),'effective_remaining_after':str(effective-retained-margin-D(21)),'unprotected_effective_remaining_after':str(effective-retained-margin-D(21)-sum(protected.values()))},'seconds':{'cells':40,'episode':1800,'cleanup':40,'per_cell':1840,'episodes_total':73600,'health_total':1800,'contingency':200,'cohort_total':75600},'health':{'preparation_id':'n36_healthcheck_n36r4_preparation_001467','max_invocations':41,'timeout_seconds':20,'cleanup_seconds':40,'per_invocation_reserved_seconds':60,'aggregate_seconds':1800,'all_full_reservations_seconds':2460,'maximum_full_reservations':30,'rule':'Both aggregate and invocation limits bind. Forty-one maximum reservations do not fit; admit each only with remaining full reservation. Zero automatic retries.'},'window':{'calculated_at':now.isoformat(),'deadline':A['deadline'],'remaining_wall_seconds':str(wall),'cohort_upper_bound_seconds':75600,'slack_seconds':str(wall-D(75600)),'full_cohort_fits_at_preparation':wall>=D(75600),'latest_full_cohort_start':(end-dt.timedelta(seconds=75600)).isoformat(),'root_must_recompute_at_adoption':True,'per_cell_full_timeout_and_cleanup_headroom_required':True,'N31_original_deadline_unchanged':True},'history_policy':'All failures, unknown telemetry, health charges, reserves, and admission margin retained; no ledger rewriting or historical provenance regeneration.'}
 assert all(v['remaining_after']>=0 for v in buckets.values()) and D(ARITH['hours']['unprotected_effective_remaining_after'])>0
 ar=write('accounting.disabled-v1.json',ARITH);plan['accounting']=ar
 allocation=write('allocation.disabled-v1.json',{'cohort':plan['cohort'],'episodes':plan['episodes'],'limits':plan['limits'],'accounting':ar,'release_enabled':False})
 protocol=write('protocol.disabled-v1.json',{'schema':'n36r4-prospective-protocol-draft-v1','cohort':plan['cohort'],'previous_plan':oldreport['plan'],'terminal_reconciliation':ref(BASE/'turns/001460/terminal-reconciliation-v1.json'),'accepted_repair':A['accepted_repair'],'allocation':allocation,'accounting':ar,'scientific_protocol_review':old['protocol_review'],'seed_policy':'Preserve prospective fixed dev seeds and init rows from N31 dev identities; identical across four arms within each task. Distinct episode/cohort identities; no pooling previous controls.','task_order':'task 0..9, within each task C0,Q0,N34,N36','first_C0_G3_pause':True,'later_cells_require_root_G3_acceptance':True,'N36R3_terminal_INVALID_never_replay':True,'methods_controls_thresholds_unchanged':True,'ordinary_native_source_audits_required':True,'fresh_health_required':True,'release_enabled':False,'root_adopted':False})
 plan['protocol']=protocol
 write('health-policy.disabled-v1.json',{'cohort':plan['cohort'],**ARITH['health'],'episode_health_ids':['n36_healthcheck_'+r['episode_key'] for r in plan['episodes']],'output_root':str(OUT/'prospective-health-001467'),'runtime':rr,'readiness':None,'prior_readiness_transfer_allowed':False,'release_enabled':False})
 # Production rejection is an intended blocker; never monkeypatch contract identities.
 try:c.validate_draft(plan)
 except ValueError as e:
  assert str(e)=='unsupported N36 cohort';CHECKS['production_N36R4_contract']={'status':'EXPECTED_BLOCK','error':str(e)}
 else:raise AssertionError('unexpected N36R4 production support')
 # Draft command compositions only: preserve every scientific argument; replace exact identities/output/source bindings.
 # These are explicitly NOT production external manifests and cannot substitute for bridge.manifest validation.
 prospective={}
 for oldrow,row in zip(old['episodes'],plan['episodes']):
  m=read(old['expected_manifests'][oldrow['episode_key']]);oldout=m['output_dir'];newout=str(Path(plan['artifact_root'])/'attempts'/row['episode_key'])
  argv=[v.replace(oldout,newout).replace(oldrow['episode_key'],row['episode_key']).replace(old['source']['commit'],A['source']) for v in m['argv']]
  # All prospective output destinations belong to this output, including the legacy report destination.
  argv=[('main.eds_eval.report_dir='+str(OUT/'prospective-reports-001467')) if v.startswith('main.eds_eval.report_dir=') else v for v in argv]
  config,resolved=b.compose_launch(argv,ROOT)
  expected=copy.deepcopy(m['expected_runtime'])
  if expected is not None:
   expected['binding']={'task_id':row['task_id'],'source_commit':A['source'],'run_id':row['episode_key']}
   expected['config_sha256']=hashlib.sha256(json.dumps(resolved,sort_keys=True,allow_nan=False).encode()).hexdigest()
   expected['source_hashes']={name:index[str(ROOT/name)] for name in expected['source_hashes']}
  manifest={**{k:plan[k] for k in ('resource_routing','cohort','protocol','protocol_review','accounting','source','scientific_source','native_build','runtime','runtime_closure','controller_semantics')},'schema':'n36r4-external-runtime-PROSPECTIVE-UNVALIDATED-v1','row':row,'argv':argv,'output_dir':newout,'composed_config_sha256':b.runner.canonical_sha(config) if hasattr(b.runner,'canonical_sha') else hashlib.sha256(json.dumps(config,sort_keys=True,allow_nan=False).encode()).hexdigest(),'resolved_config':resolved,'expected_runtime':expected,'release_enabled':False,'production_manifest_validation':'BLOCKED_UNSUPPORTED_COHORT','parent_manifest':old['expected_manifests'][oldrow['episode_key']]}
  # Exact identity substitution accounts for the only allowed resolved-config differences.
  def transform(x):
   if isinstance(x,str):return x.replace(oldout,newout).replace(oldrow['episode_key'],row['episode_key']).replace(old['source']['commit'],A['source'])
   if isinstance(x,dict):return {k:transform(v) for k,v in x.items()}
   if isinstance(x,list):return [transform(v) for v in x]
   return x
  assert resolved==transform(m['resolved_config']), 'scientific resolved configuration changed'
  assert config['backend']['libero']['max_episode_steps']==720 and config['policy']['rdt']['control_frequency']==20 and config['policy']['rdt']['action_chunk_horizon']==8
  prospective[row['episode_key']]=write('prospective-manifests/'+row['episode_key']+'.json',manifest)
 plan['prospective_manifests']=prospective
 plan['preparation_status']='BLOCKED_SOURCE_CONTRACT_NO_N36R4_SUPPORT'
 pr=write('plan.draft.json',plan)
 write('bindings.disabled-v1.json',{'plan':pr,**{k:plan[k] for k in admission.BINDINGS},'prospective_manifests':prospective,'production_expected_manifests':{},'release_enabled':False,'root_adopted':False,'worker_receipts_are_future':True})
 CHECKS['40_draft_compositions_scientific_equality']={'status':'PASS','count':40,'production_manifest_validation':False}
 CHECKS['fresh_identity_seed_order_limits']={'status':'PASS','count':40,'old_controls_pooled':False}
 assert 'torch' not in sys.modules, 'unexpected Torch import'
 CHECKS['no_model_or_torch_import']={'status':'PASS'}
 write('consistency-v1.json',{'source':A['source'],'cohort':plan['cohort'],'source_files':len(source['files']),'runtime_files':len(runtime['files']),'runtime_modules':len(closure['modules']),'DINO_files':len(dino),'runtime_source_updates':deltas,'closure_module_updates':modules,'native_libraries':len(native['libraries']),'expected_production_manifests':0,'prospective_composed_drafts':40,'owner_routing':plan['resource_routing'],'source_dependent_references_replaced':['source','scientific_source','runtime','runtime_closure','controller_semantics and direct evidence','protocol','accounting','episode and output identities','prospective manifest expected source hashes'],'immutable_references_preserved':['scientific protocol review','native inventory bytes','runtime dependency/model file inventories','DINO admission manifest file set','controller source findings','accepted root repair and terminal accounting anchors'],'release_enabled':False})
PLAN=None;ARITH=None
try:main()
except BaseException as e:
 ERRORS.append({'type':type(e).__name__,'message':str(e),'traceback':traceback.format_exc()});print(traceback.format_exc(),flush=True)
finally:
 signal.alarm(0)
 try:
  assert all(sha(p)==r['sha256'] for p,r in INPUTS.items())
  assert git('rev-parse','HEAD')==A['source'] and not git('status','--porcelain','--untracked-files=no')
  CHECKS['inputs_ledgers_source_unchanged']={'status':'PASS','input_count':len(INPUTS)}
 except BaseException as e:ERRORS.append({'type':type(e).__name__,'message':str(e)})
 write('checks-results-v1.json',{'checks':CHECKS,'errors':ERRORS,'seconds':time.monotonic()-START,'cpu_threads':2})
 write('input-bindings-v1.json',{'inputs':list(INPUTS.values()),'tooling_ancestry':[ref(BASE/'turns/001448/binding-refresh/refresh-bindings-v1.py'),ref(BASE/'turns/001451/manifest-refresh/refresh-v1.py')],'adaptation':'New artifact-only tool; no stale script execution, production monkeypatching, source editing, or recursive historical reconstruction.'})
 print(json.dumps({'errors':ERRORS,'artifacts':len(ART),'checks':CHECKS},indent=2))
