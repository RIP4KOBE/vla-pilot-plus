import os,sys,json,hashlib,datetime as dt,time,resource,subprocess,copy,traceback
from pathlib import Path
OUT=Path(__file__).parent;A=json.loads((OUT/'authority-v1.json').read_text());ROOT=Path(A['worktree']);START=time.monotonic();ART={};CHECK={}
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2]);resource.setrlimit(resource.RLIMIT_CPU,(115,115))
def guard():
 assert not any(os.path.lexists(p) for p in A['STOP_paths']),'STOP alias present'
 assert dt.datetime.now(dt.timezone.utc)<dt.datetime.fromisoformat(A['deadline'].replace('Z','+00:00'))
 assert time.monotonic()-START<115
 assert os.environ['CUDA_VISIBLE_DEVICES']==''
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return {'path':str(p),'sha256':sha(p)}
def read(r):
 assert sha(r['path'])==r['sha256'],r['path'];return json.loads(Path(r['path']).read_text())
def write(n,d):
 guard();p=OUT/n;p.parent.mkdir(parents=True,exist_ok=True);assert not p.exists(),p;p.write_text(json.dumps(d,indent=2,allow_nan=False)+'\n');ART[n]=ref(p);return ART[n]
def git(*args):return subprocess.check_output(['git','-C',str(ROOT),*args],text=True).strip()
def normal(x,m):
 if isinstance(x,str):return x.replace(m['output_dir'],'<output>').replace(m['source']['commit'],'<source>')
 if isinstance(x,(list,tuple)):return [normal(v,m) for v in x]
 if isinstance(x,dict):return {k:normal(v,m) for k,v in x.items()}
 return x
def main():
 guard();assert git('rev-parse','HEAD')==A['base_source'];assert not git('status','--porcelain','--untracked-files=no')
 sys.path.insert(0,str(ROOT))
 from scripts import qd_ed_n36_bridge as b,qd_ed_n36_contract as c,qd_ed_n34_source as s,qd_ed_n34_controller as controller
 from scripts import qd_ed_n23_worker as w
 prep=read(A['preparation_report']);review=read(A['review_report']);oldref=ref(Path(A['preparation_report']['path']).parent/'plan.unbound-disabled-v1.json');old=read(oldref)
 source=s.source_record(ROOT,b.source_paths(ROOT));assert source['commit']==A['base_source'];sr=write('source.complete-v1.json',source);write('scientific_source.complete-v1.json',source)
 before={v['path']:v['sha256'] for v in old['source']['files']};after={v['path']:v['sha256'] for v in source['files']};changed=git('diff','--name-only',old['source']['commit'],'HEAD').splitlines();assert len(changed)==10
 assert {k for k in before.keys()|after.keys() if before.get(k)!=after.get(k)}==set(changed)
 write('source_files_sha256-v1.json',after)
 write('source-change-bindings-v1.json',{'base_commit':old['source']['commit'],'commit':source['commit'],'changes':[{'path':k,'before':before.get(k),'after':after[k]} for k in changed],'unchanged_files':len(set(before)-set(changed)),'scientific_bytes_unchanged_outside_exact_engineering_delta':True,'schema_note':'Production requires source == scientific_source; both full records refresh. All non-delta source bytes remain exact.'})
 # Execute frozen bootstrap bytes with the exact isolated startup flags, then observe only safe source policy and finder resolution.
 harness="""import sys
__file__=sys.argv[1]
sys.argv=[__file__,'scripts.qd_ed_n36_source']
exec(compile(open(__file__,'rb').read(),__file__,'exec'))
import json
from pathlib import Path
from importlib.machinery import PathFinder
from scripts import qd_ed_n36_source as policy
state=policy.active()
rows=[]
for name in ['lerobot','lerobot.processor','models.rdt_runner','configs.state_vec','libero','libero.libero','libero.libero.envs.env_wrapper','robosuite.controllers.osc']:
 search=sys.path
 for i in range(1,len(name.split('.'))+1):
  full='.'.join(name.split('.')[:i]);spec=PathFinder.find_spec(full,search);assert spec is not None,full;search=spec.submodule_search_locations
 rows.append({'module':name,'origin':spec.origin,'sha256':policy.sha(spec.origin) if spec.origin else None,'module_executed':False})
rejected=[]
for search in [sys.path+[''],sys.path+['/home/hynx/VLA-Pilot++']]:
 try:policy.validate_search_path(state.root,search,sys.prefix)
 except ValueError as e:rejected.append(str(e))
 else:raise AssertionError('foreign search accepted')
print(json.dumps({'schema':'n36r2-isolated-import-search-evidence-v1','search_path':sys.path,'search_prefix':sys.prefix,'interpreter':policy.interpreter_identity(),'bootstrap_sha256':state.bootstrap_digest,'source_only_active':True,'resolved_only':rows,'negative_rejections':rejected,'actual_worker_receipt':False,'scope':'Frozen bootstrap executed by CPU harness; no worker/Main/simulator imports or execution; finder resolution only.'}))
"""
 hp=OUT/'import-search-harness-v1.py';hp.write_text(harness);ART[hp.name]=ref(hp)
 py=read(old['runtime_closure'])['interpreter']['path'];cmd=[py,'-I','-S','-B','-X','pycache_prefix=/dev/null','-c',harness,str(ROOT/'scripts/qd_ed_n36_bootstrap.py')]
 cp=subprocess.run(cmd,text=True,capture_output=True,timeout=15);assert cp.returncode==0,cp.stderr
 evidence=json.loads(cp.stdout);evidence['harness']=ref(hp);evidence['source_commit']=source['commit'];evidence['inherited_PYTHONPATH_ignored']=True
 ir=write('import-search.isolated-v1.json',evidence)
 runtime=read(old['runtime']);oldruntime=copy.deepcopy(runtime)
 for row in runtime['files']:
  if row['path'].startswith(str(ROOT)+'/') and row['path'][len(str(ROOT))+1:] in changed:
   row['sha256']=sha(row['path']);row['size_bytes']=Path(row['path']).stat().st_size
 existing={v['path'] for v in runtime['files']}
 for name in changed:
  if name.startswith('scripts/') and str(ROOT/name) not in existing:
   p=ROOT/name;runtime['files'].append({'path':str(p),'resolved_path':str(p),'sha256':sha(p),'size_bytes':p.stat().st_size})
 runtime['preparation']={**runtime['preparation'],'source':source['commit'],'source_record':sr,'runtime_ready':False,'release_enabled':False,'status':'FINAL_SOURCE_CPU_BINDING_REVIEW_REQUIRED','import_search_evidence':ir}
 rr=write('runtime.isolated.draft-v1.json',runtime)
 closure=read(old['runtime_closure']);oldclosure=copy.deepcopy(closure);closure['runtime']=rr
 for name in changed:
  if name.startswith('scripts/'):closure['modules'][name[:-3].replace('/','.')]=ref(ROOT/name)
 # Retain unchanged historical runtime/native/checkpoint inventories without re-running broad probes.
 cr=write('runtime-closure.isolated.draft-v1.json',closure)
 proof=read(old['controller_semantics']);priorproof=copy.deepcopy(proof);proof['runtime']=rr;proof['runtime_closure']=cr;proof['rebound_from']=old['controller_semantics']
 proof['scope']='Inherited controller semantics only; final-source bindings await external review. No current device/provider/worker evidence or new approval.'
 for name,r in list(proof['review_evidence'].items()):
  e=read(r)
  for f in e['sources']:assert sha(f['path'])==f['sha256']
  e.update(runtime=rr,runtime_closure=cr,source_commit=source['commit'],rebound_from=r,binding_review=proof['scope'])
  proof['review_evidence'][name]=write('controller-'+name+'.isolated-v1.json',e)
 pr=write('controller-semantics.isolated.draft-v1.json',proof);controller.verify_semantics(pr,rr,closure)
 assert proof['instance']==priorproof['instance'] and proof['semantics']==priorproof['semantics']
 native=read(old['native_build']);assert runtime['tasks']==oldruntime['tasks'];assert runtime['main_overrides']==oldruntime['main_overrides'];assert runtime['frozen_stage_provider']==oldruntime['frozen_stage_provider']
 write('reused-evidence-v1.json',{'native_build':old['native_build'],'native_record_hash_verified':True,'native_libraries_rehashed':False,'checkpoint_and_task_records_unchanged':True,'prior_runtime':old['runtime'],'prior_closure':old['runtime_closure'],'unchanged_runtime_modules':len(oldclosure['modules']),'new_source_modules':9,'current_device_provider_readiness':False,'scope':'Reuse accepted unchanged native/checkpoint evidence. No historical worker receipt/search-path evidence reused as new-source evidence.'})
 plan=copy.deepcopy(old);plan.update(source=source,scientific_source=source,runtime=rr,runtime_closure=cr,controller_semantics=pr,source_binding_status='FINAL_SOURCE_REFRESHED_DISABLED_EXTERNAL_REVIEW_REQUIRED')
 # Preserve original output identities, protocol/accounting/routing and all forty rows.
 read(plan['protocol']);read(plan['accounting']);read(plan['protocol_review'])
 joins=[];comparisons=[]
 for row in plan['episodes']:
  guard();key=row['episode_key'];previous=read(old['expected_manifests'][key]);m=b.manifest(plan,runtime,row)
  assert m['row']==previous['row'] and m['output_dir']==previous['output_dir'];assert normal(m['argv'],m)==normal(previous['argv'],previous)
  beforeconfig,_=b.compose_launch(previous['argv'],ROOT);afterconfig,_=b.compose_launch(m['argv'],ROOT)
  assert w.canonical_sha(beforeconfig)==previous['composed_config_sha256'];assert w.canonical_sha(afterconfig)==m['composed_config_sha256']
  assert normal(beforeconfig,previous)==normal(afterconfig,m);assert normal(previous['resolved_config'],previous)==normal(m['resolved_config'],m)
  mr=write('expected/'+key+'.json',m);plan['expected_manifests'][key]=mr
  joins.append({'episode_key':key,'row':row,'manifest':mr,'source_files_sha256':source['sha256'],'scientific_source_sha256':source['sha256'],'runtime':rr,'runtime_closure':cr,'controller_semantics':pr,'protocol':plan['protocol'],'accounting':plan['accounting'],'composed_config_sha256':m['composed_config_sha256'],'resolved_config_sha256':w.canonical_sha(m['resolved_config']),'argv_sha256':w.canonical_sha(m['argv']),'output_dir':m['output_dir']})
  comparisons.append({'episode_key':key,'prior_manifest':old['expected_manifests'][key],'manifest':mr,'prior_composed_config_sha256':previous['composed_config_sha256'],'composed_config_sha256':m['composed_config_sha256'],'normalized_full_config_sha256':w.canonical_sha(normal(afterconfig,m)),'full_scientific_config_equal':True,'row_exact':True,'output_identity_exact':True})
 assert plan['episodes']==old['episodes'] and plan['resource_routing']==old['resource_routing'];assert not plan['release_enabled'] and plan['b5_review'] is None
 for k in ['authority','root_review','execution_release']:assert plan[k] is None
 assert not any(plan['phase_authorization'].values());assert not plan['frozen'];assert plan['source']==plan['scientific_source']
 # Avoid recursive old-provenance reconstruction: protocol/accounting bytes are unchanged accepted inputs.
 c.validate_stop_binding(plan);assert c.plan_rows(plan)==plan['episodes'];assert c.operational_binding(plan)==c.operational_binding(old)
 planref=write('plan.complete-disabled-v1.json',plan)
 for row in plan['episodes']:
  key=row['episode_key'];m=read(plan['expected_manifests'][key]);ctx={'schema':'n36-worker-context-v1','plan':planref,'release':None,'expected_manifest':plan['expected_manifests'][key],'episode_key':key,'attempt_id':key,'main_argv':m['argv'][1:],'worker_contract':c.WORKER_CONTRACT}
  ctxref=write('contexts/'+key+'.disabled.json',ctx);next(x for x in joins if x['episode_key']==key)['context']=ctxref
 write('all40-joins-v1.json',{'count':40,'rows':joins,'release_enabled':False})
 write('full-scientific-config-comparison-v1.json',{'count':40,'rows':comparisons,'normalization_only':['exact source commit in command/config; original output identities unchanged'],'status':'PASS','release_enabled':False})
 from scripts import qd_ed_n36_release as release
 try:release.validate_plan(plan)
 except (ValueError,KeyError) as e:rejection={'exception':type(e).__name__,'reason':str(e)}
 else:raise AssertionError('disabled plan admitted')
 CHECK.update(all40_manifests_regenerated=True,all40_full_scientific_configs_equal=True,all40_contexts_disabled=True,source_inventory_verified_against_frozen_git=True,source_change_count=10,import_search_policy_active=True,controller_semantics_unchanged=True,protocol_accounting_routing_unchanged=True,disabled_rejection=rejection)
 assert git('rev-parse','HEAD')==A['base_source'] and not git('status','--porcelain','--untracked-files=no')
 assert subprocess.check_output(['git','-C',A['owner'],'rev-parse','HEAD'],text=True).strip()==review['owner_source']
 acceptance=read(A['root_acceptance'])
 for name,r in acceptance['ledger_prefixes'].items():assert Path(r['path']).stat().st_size==r['bytes'] and sha(r['path'])==r['sha256']
 CHECK['all_past_ledger_bytes_retained']=True
 write('dependency-graph-v1.json',{'source':sr,'scientific_source':ref(OUT/'scientific_source.complete-v1.json'),'source_files_sha256':ref(OUT/'source_files_sha256-v1.json'),'import_search':ir,'runtime':rr,'runtime_closure':cr,'controller_semantics':pr,'native_build':plan['native_build'],'protocol':plan['protocol'],'accounting':plan['accounting'],'resource_routing':plan['resource_routing'],'plan':planref,'all40_joins':ART['all40-joins-v1.json'],'full_config_comparison':ART['full-scientific-config-comparison-v1.json'],'direction':'source/import-search -> runtime -> closure -> controller -> manifests -> disabled plan -> disabled contexts','release_enabled':False})
 return review
try:
 review=main();status='FINAL_SOURCE_REFRESH_COMPLETE_EXTERNAL_REVIEW_REQUIRED';error=None
except BaseException as e:
 status='BLOCKED';error={'type':type(e).__name__,'message':str(e),'traceback':traceback.format_exc()};print(error['traceback']);review=read(A['review_report'])
report={'schema':'n36r2-final-source-refresh-report-v1','node_id':'15.6','status':status,'at':dt.datetime.now(dt.timezone.utc).isoformat(),'source_commit':A['base_source'],'owner_source':review['owner_source'],'authority':ref(OUT/'authority-v1.json'),'accepted_review':A['review_report'],'preparation_report':A['preparation_report'],'score':None,'target_met':False,'release_enabled':False,'production_accepted':False,'source_adopted':False,'gpu_authorized':False,'root_token_minted':False,'independent_review_token_minted':False,'retained_attempts':504,'retained_gpu_hours':75.49265038509455,'preserved_invalid_charges':review['findings'][1]['details']['retained_invalid_charges'],'checks':CHECK,'artifacts':ART.copy(),'blocker':error,'cpu_checks':{'wall_seconds':time.monotonic()-START,'cpu_seconds':resource.getrusage(resource.RUSAGE_SELF).ru_utime+resource.getrusage(resource.RUSAGE_SELF).ru_stime,'threads':2,'cap_seconds':120,'broad_tests_repeated':False},'STOP_paths':{p:os.path.lexists(p) for p in A['STOP_paths']},'deadline':A['deadline'],'worker_receipts_are_future':True,'future_worker_receipts_required_before_dispatch':False,'future_worker_receipts_fabricated':False,'remaining_gates':['External final-source review of this exact package; executor grants no approval.']+review['remaining_release_prerequisites'],'limits':['No source edits, GPU/Main/simulator/healthcheck/provider/network/package/credential operations, child agents or owner/state/ledger writes.','No protected result inspection, old-provenance recursion or broad B2/B4 repeats. Native/checkpoint evidence retained within prior accepted scope.','CPU bootstrap evidence is import-search evidence only, never an actual-worker receipt. Current provider/device readiness remains external.']}
md='# Node15.6 final-source binding refresh\n\n'+status+'\n\nFrozen isolated source: `'+A['base_source']+'`. Owner source: `'+review['owner_source']+'`.\n\nScore: null. Target met: false. Release enabled: false. Retained costs: 504 attempts / 75.49265038509455 GPU hours.\n\n'+('All 40 original identities and full scientific configurations preserved. Source inventory, runtime, closure, controller references, manifests, joins, disabled plan and contexts refreshed. Protocol/accounting/routing unchanged. Exact hashes are in dependency-graph-v1.json and report-v1.json.\n\n' if not error else 'Concrete blocker: '+str(error)+'\n\n')+'Actual worker before/after receipts remain future and are not predispatch prerequisites. No review/release token or source adoption was created. External final-source review, coordinator adoption and readiness/release gates remain in order.\n'
(OUT/'report-v1.md').write_text(md);report['markdown']=ref(OUT/'report-v1.md');(OUT/'report-v1.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'status':status,'wall_seconds':time.monotonic()-START,'blocker':error}));sys.exit(0 if error is None else 1)
