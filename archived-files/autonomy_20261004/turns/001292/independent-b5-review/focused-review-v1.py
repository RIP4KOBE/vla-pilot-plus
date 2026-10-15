import os,sys,json,hashlib,time,datetime as dt,resource,traceback
from pathlib import Path
OUT=Path(__file__).parent; start=time.monotonic(); evidence={}; checks={}; rows=[]
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2]);resource.setrlimit(resource.RLIMIT_CPU,(110,110))
A=json.loads((OUT/'authority-v1.json').read_text());sys.path.insert(0,A['worktree'])
def guard():
 assert not any(os.path.lexists(p) for p in A['STOP_paths']), 'STOP present'
 assert dt.datetime.now(dt.timezone.utc)<dt.datetime.fromisoformat(A['deadline'].replace('Z','+00:00'))
 assert time.monotonic()-start<110

def read(r,parse=True):
 p=Path(r['path']);assert p.stat().st_size<25000000, 'no large artifact hashing'
 b=p.read_bytes();h=hashlib.sha256(b).hexdigest();assert h==r['sha256'],str(p)
 if 'bytes' in r:assert len(b)==r['bytes'],str(p)
 evidence[str(p)]={'path':str(p),'sha256':h,'bytes':len(b)}
 return json.loads(b) if parse else b

def eq(a,b):return json.dumps(a,sort_keys=True,allow_nan=False)==json.dumps(b,sort_keys=True,allow_nan=False)
def omit(d,keys):return {k:v for k,v in d.items() if k not in keys}
def strict_normalize(a,b,path=''):
 # Permit tuple -> list only; never coerce scalar types or numeric values.
 if isinstance(a,tuple):
  assert isinstance(b,list) and len(a)==len(b),path
  found=[path]
  for i,(x,y) in enumerate(zip(a,b)):found+=strict_normalize(x,y,path+'/'+str(i))
  return found
 assert type(a)==type(b),(path,type(a).__name__,type(b).__name__)
 if isinstance(a,dict):
  assert a.keys()==b.keys(),path
  return [p for k in a for p in strict_normalize(a[k],b[k],path+'/'+k)]
 if isinstance(a,list):
  assert len(a)==len(b),path
  return [p for i,(x,y) in enumerate(zip(a,b)) for p in strict_normalize(x,y,path+'/'+str(i))]
 assert a==b,path
 return []
error=None
try:
 guard();inputs={k:read(v) for k,v in A['inputs'].items()};pkg=inputs['b5_input_package'];report=inputs['candidate_report']
 read(pkg['verifier'],False)
 for r in report['outputs'].values():read(r,False)
 supp={k:read(v) for k,v in pkg['supporting_evidence'].items()}
 read(inputs['completion']['preserved_initial_attempt']);read(report['preparation_script'],False)
 accepted=supp['accepted_package'];old=lambda n:read(accepted['artifacts'][n]);plan0=old('plan.complete-disabled-v1.json');plan=read(pkg['candidate_plan'])
 assert pkg['review_inputs']=={k:plan[k] for k in pkg['review_inputs']}
 assert plan['source']==plan['scientific_source']==plan0['source'] and plan['source']['commit']==A['base_source']
 from scripts import qd_ed_n36_bridge as b,qd_ed_n36_contract as c,qd_ed_n34_source as s,qd_ed_n34_controller as ctrl,qd_ed_n36_release as release,qd_ed_n36r2_admission as adm,qd_ed_n23_worker as w
 s.verify_source(A['worktree'],plan['source'],commit=A['base_source'])
 assert b.source_paths(A['worktree']) <= {v['path'] for v in plan['source']['files']}
 checks['source']={'status':'PASS','commit':A['base_source'],'files':len(plan['source']['files']),'frozen_git_and_working_bytes':True}
 runtime=read(plan['runtime']);runtime0=old('runtime.isolated.draft-v1.json');closure=read(plan['runtime_closure']);closure0=old('runtime-closure.isolated.draft-v1.json')
 assert eq(omit(runtime,['preparation']),omit(runtime0,['preparation'])) and supp['runtime_ready']==runtime0
 assert eq(omit(closure,['runtime']),omit(closure0,['runtime'])) and closure['runtime']==plan['runtime']
 # Full runtime/native/model hashing is deliberately reserved for production. Check exact immutable inventory inheritance here.
 assert len(closure['modules'])==6767
 proof=read(plan['controller_semantics']);proof0=old('controller-semantics.isolated.draft-v1.json')
 assert eq(omit(proof,['runtime','runtime_closure','review_evidence']),omit(proof0,['runtime','runtime_closure','review_evidence']))
 for name,r in proof['review_evidence'].items():
  new=read(r);prior=read(proof0['review_evidence'][name]);assert eq(omit(new,['runtime','runtime_closure']),omit(prior,['runtime','runtime_closure']))
  assert new['runtime']==plan['runtime'] and new['runtime_closure']==plan['runtime_closure']
 ctrl.verify_semantics(plan['controller_semantics'],plan['runtime'],closure)
 assert proof['runtime_closure']==plan['runtime_closure'] and plan['native_build']==plan0['native_build'];read(plan['native_build'])
 ready=supp['readiness_review'];adopt=supp['source_accounting_adoption'];authority=read(plan['authority']);prep=runtime['preparation']
 assert ready['status']=='PASS_READINESS_ONLY_NOT_RELEASE' and ready['source']==adopt['source_after']==A['base_source']
 assert ready['runtime']['sha256']==ready['disabled_runtime']['sha256']==pkg['supporting_evidence']['runtime_ready']['sha256']
 assert ready['changed_fields']==[] and ready['accounting_authority']==adopt['authority']
 assert prep['readiness_review']==pkg['supporting_evidence']['readiness_review'] and prep['source_accounting_adoption']==pkg['supporting_evidence']['source_accounting_adoption']
 assert prep['runtime_ready'] is True and prep['release_enabled'] is False and prep['no_provider_or_device_probe'] is True
 assert runtime['provider_ready'] and runtime['cuda_egl_verified'] and runtime['gpu_mapping']['uuid']==c.GPU_UUID and b.runner.runtime_gpu(runtime)==7 and runtime['gpu_mapping']['egl_device_index']==4
 b.runner.stage_overrides(runtime)
 checks['runtime_closure_controller_readiness']={'status':'PASS','runtime_files':len(runtime['files']),'closure_modules':len(closure['modules']),'runtime_payload_unchanged_except_preparation':True,'closure_payload_unchanged_except_runtime_ref':True,'controller_semantics_unchanged':True,'full_byte_checks_deferred_to_production':True,'new_device_or_provider_probe':False}
 c.validate_stop_binding(plan);assert plan['episodes']==c.plan_rows(plan)==plan0['episodes']
 assert plan['resource_routing']==plan0['resource_routing'];adm.owner_root(plan)
 assert not plan['frozen'] and not plan['release_enabled'] and plan['b5_review'] is None and not any(plan['phase_authorization'].values())
 assert 'root_review' not in plan and 'execution_release' not in plan
 assert eq(omit(plan,['runtime','runtime_closure','controller_semantics','expected_manifests','authority','source_binding_status','root_review','execution_release']),omit(plan0,['runtime','runtime_closure','controller_semantics','expected_manifests','authority','source_binding_status','root_review','execution_release']))
 assert plan['protocol']==plan0['protocol'] and plan['accounting']==plan0['accounting'] and plan['protocol_review']==plan0['protocol_review']
 protocol=read(plan['protocol']);ledger=read(plan['accounting']);calc=read(ledger['calculation']);snap=read(calc['ledger_snapshot'])
 assert protocol['episodes']==plan['episodes'] and protocol['accounting']==plan['accounting'] and protocol['resource_routing']==plan['resource_routing'] and protocol['scientific_changes'] is False
 assert authority['protocol']==plan['protocol'] and authority['accounting']==authority['amendment']==plan['accounting'] and authority['ledger_prefixes']==ledger['ledger_prefixes']==adopt['ledger_prefixes']==ready['ledger_prefixes']
 release.validate_caps(authority['caps']);adm.validate_calculation(ledger)
 assert authority['limits']==plan['limits']==c.LIMITS and authority['automatic_recoveries']==0 and authority['validation_authorized'] is False and authority['formal_authorized'] is False
 assert snap['snapshot']==adopt['retained_snapshot']
 ids={row['episode_key'] for row in plan['episodes']};assert len(ids)==40
 for name,r in ledger['ledger_prefixes'].items():
  raw=read(r,False)
  assert not any(k.encode() in raw for k in ids), 'cohort ID already present in ledger'
  assert Path(r['path']).resolve()==Path(A['owner'])/'data'/name
 checks['protocol_accounting_fresh_ids']={'status':'PASS','retained_attempts':adopt['retained_snapshot']['dispatched'],'retained_gpu_hours':adopt['retained_snapshot']['gpu_hours_consumed'],'arithmetic':calc['arithmetic'],'attempts':calc['attempts'],'preserved_attempts':ledger['preserved_attempts'],'ledger_bytes_exact':True,'fresh_ids_absent_from_all_three_journals':True,'historical_protocol_review_reused_without_recursive_rebuild':True}
 joins=supp['all40_joins'];assert joins['plan']==pkg['candidate_plan'] and joins['count']==40 and {x['episode_key'] for x in joins['rows']}==ids
 indexed={x['episode_key']:x for x in joins['rows']}
 for row in plan['episodes']:
  guard();key=row['episode_key'];m=read(plan['expected_manifests'][key]);prior=read(plan0['expected_manifests'][key]);j=indexed[key]
  assert eq(omit(m,['runtime','runtime_closure','controller_semantics']),omit(prior,['runtime','runtime_closure','controller_semantics']))
  for field in ['source','scientific_source','native_build','runtime','runtime_closure','controller_semantics']:assert m[field]==plan[field]
  composed=b.manifest(plan,runtime,row);paths=strict_normalize(composed,m)
  config,resolved=b.compose_launch(m['argv'],A['worktree']);config0,resolved0=b.compose_launch(prior['argv'],A['worktree'])
  assert eq(config,config0) and w.canonical_sha(config)==m['composed_config_sha256']==prior['composed_config_sha256']
  resolved_paths=strict_normalize(resolved,m['resolved_config']);assert eq(resolved,resolved0)
  assert not os.path.lexists(m['output_dir'])
  ctx=read(j['context']);ctx0=old('contexts/'+key+'.disabled.json')
  assert ctx['plan']==pkg['candidate_plan'] and ctx['expected_manifest']==plan['expected_manifests'][key]==j['manifest']
  assert ctx['release'] is None and ctx['episode_key']==ctx['attempt_id']==key and ctx['main_argv']==m['argv']
  assert eq(omit(ctx,['plan','expected_manifest']),omit(ctx0,['plan','expected_manifest']))
  for f in ['runtime','runtime_closure','controller_semantics']:assert j[f]==plan[f]
  rows.append({'episode_key':key,'status':'PASS','full_config_sha256':w.canonical_sha(config),'manifest':plan['expected_manifests'][key],'context':j['context'],'tuple_to_list_paths':paths,'resolved_tuple_to_list_paths':resolved_paths,'scalar_types_and_values_exact':True,'output_absent':True})
 checks['all40']={'status':'PASS','count':len(rows),'rows':rows,'independent_full_config_recomposition':True}
 try:release.validate_plan(plan)
 except ValueError as e:assert str(e)=='released plan contract';checks['nonreleased_rejection']={'status':'PASS','reason':str(e)}
 else:raise AssertionError('nonreleased candidate accepted')
 guard();checks['input_hashes']={'status':'PASS','count':len(evidence)}
except BaseException as e:error={'type':type(e).__name__,'message':str(e),'traceback':traceback.format_exc()}
result={'status':'PASS' if error is None else 'BLOCKED','checks':checks,'blocker':error,'evidence':list(evidence.values()),'wall_seconds':time.monotonic()-start,'cpu_seconds':resource.getrusage(resource.RUSAGE_SELF).ru_utime+resource.getrusage(resource.RUSAGE_SELF).ru_stime,'threads':2,'score':None,'target_met':False,'release_enabled':False}
(OUT/'focused-check-results-v1.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
print(json.dumps({'status':result['status'],'blocker':error,'wall_seconds':result['wall_seconds'],'cpu_seconds':result['cpu_seconds'],'completed_checks':list(checks),'completed_cells':len(rows)}))
