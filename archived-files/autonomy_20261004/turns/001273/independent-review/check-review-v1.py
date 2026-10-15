import os,sys,json,hashlib,pathlib,time,datetime,resource,subprocess,traceback
P=pathlib.Path
OUT=P(__file__).resolve().parent
A=json.loads((OUT/'authority-v1.json').read_text());ROOT=P(A['worktree']);PRE=OUT.parents[1]/'001268/source-runtime-preparation'
START=time.monotonic();resource.setrlimit(resource.RLIMIT_CPU,(105,105));os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2])
R={'checks':{},'bindings':[],'errors':[]}
def guard():
 assert not any(os.path.lexists(p) for p in A['STOP_paths']), 'STOP'
 assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat(A['deadline'].replace('Z','+00:00'))
 assert time.monotonic()-START<108

def audit(event,args):
 if event in ('socket.connect','socket.getaddrinfo'):raise RuntimeError('network prohibited')
 if event=='exec' and getattr(args[0],'co_filename','') in (str(ROOT/'main.py'),str(ROOT/'scripts/qd_ed_poe_launch.py')):raise RuntimeError('entrypoint prohibited')
 if event=='open' and isinstance(args[0],(str,bytes)):
  s=os.fsdecode(args[0]);assert not any(t in s for t in ('/auth.json','/.git-credentials','/credentials/','2026-08-10-eds-qd-stage-guidance-transition-design.md'))
sys.addaudithook(audit)
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for x in iter(lambda:f.read(4*1024*1024),b''):h.update(x)
 return h.hexdigest()
def read(p):return json.loads(P(p).read_text())
def ref(r):
 guard();p=P(r['path']);assert sha(p)==r['sha256'],str(p)
 if 'bytes'in r:assert p.stat().st_size==r['bytes']
 R['bindings'].append({'path':str(p),'sha256':r['sha256']});return read(p)
def check(n,fn):
 guard();t=time.monotonic();v=fn();R['checks'][n]={'status':'PASS','seconds':time.monotonic()-t,'detail':v};print(n,'PASS',flush=True);return v
def git(*args,cwd=ROOT):return subprocess.check_output(['git','--no-optional-locks',*args],cwd=cwd,env={**os.environ,'GIT_NO_LAZY_FETCH':'1'}).decode().strip()
def main():
 guard();report=read(PRE/'report-v1.json');R['preparation_report_sha256']=sha(PRE/'report-v1.json')
 ref(A['root_acceptance']);ref(A['standing_authority']);index=ref(report['evidence_index'])
 check('evidence_index_bytes',lambda:[ref(x) if x['path'].endswith('.json') else (R['bindings'].append(x), (_ for _ in ()).throw(AssertionError(x['path'])) if sha(x['path'])!=x['sha256'] else None) for x in index['files']] and len(index['files']))
 R['identity']={'isolated':git('rev-parse','HEAD'),'owner':git('rev-parse','HEAD',cwd=A['owner']),'status':git('status','--porcelain=v1'),'branch':git('branch','--show-current'),'owner_to_isolated_paths':git('diff','--name-only',report['source_identity']['owner_commit'],A['base_source']).splitlines()}
 assert R['identity']['isolated']==A['base_source'] and R['identity']['owner']==report['source_identity']['owner_commit'] and not R['identity']['status']
 sys.path.insert(0,str(ROOT))
 from scripts import qd_ed_n36_bridge as b,qd_ed_n34_source as s,qd_ed_n36_contract as c,qd_ed_final_runner as runner,qd_ed_n36_release as release,qd_ed_n34_controller as controller
 plan=read(PRE/'plan.complete-disabled-v1.json');source=read(PRE/'source.complete-v1.json');runtime=ref(plan['runtime']);closure=ref(plan['runtime_closure']);old=ref(report['preservation']['old_partial_plan_verified_unchanged'])
 def source_check():
  b.verify_sources(plan);assert source==plan['source']==plan['scientific_source'];assert set(b.source_paths(ROOT))=={x['path'] for x in source['files']};return {'count':len(source['files']),'canonical_sha256':source['sha256'],'launcher':next(x for x in source['files'] if x['path']=='scripts/qd_ed_poe_launch.py')}
 check('complete_source_git_bytes_and_exact_inventory',source_check)
 oldclosure=ref(old['runtime_closure']);assert {k:v for k,v in closure.items() if k!='runtime'}=={k:v for k,v in oldclosure.items() if k!='runtime'}
 check('runtime_closure_current_bytes_and_rules',lambda: (s.verify_runtime(closure,plan['runtime']),{'module_count':len(closure['modules']),'only_runtime_ref_changed':True})[1])
 check('runtime_files_current_bytes',lambda:(runner.verify_files(runtime['files'],allowed_roots=(ROOT,runtime['artifact_root'])),len(runtime['files']))[1])
 def assets():
  d=read(PRE/'relocated-assets-v1.json');counts={}
  for x in d['files']:
   guard();a,z=x['original'],x['relocated'];assert a['sha256']==z['sha256'];assert P(z['path']).resolve().is_relative_to(ROOT);assert sha(z['path'])==z['sha256'];counts[x['action']]=counts.get(x['action'],0)+1
  assert len(d['files'])==3000;return counts
 check('relocated_assets_independent',assets)
 def semantics():
  proof=controller.verify_semantics(plan['controller_semantics'],plan['runtime'],closure)
  for e in proof['review_evidence'].values():
   for f in ref(e)['sources']:assert sha(f['path'])==f['sha256']
  return {'source_only':True,'physical_gain_certified':proof['physical_gain_certified']}
 check('controller_bound_source_bytes',semantics)
 check('draft_contract',lambda:(c.validate_draft(plan),True)[1])
 def inputs():
  # Check task/seed/config bindings without repeating multi-GB checkpoint reads.
  runner.validate_runtime_inputs(plan,runtime,b.profiles(ROOT),ROOT,{'artifacts':runtime['artifact_root']},require_frozen=False)
  return {'all_rows':40,'checkpoint_bytes_rehashed':False,'prior_checkpoint_validation_reviewed':True}
 check('runtime_input_task_seed_joins',inputs)
 joins=read(PRE/'all40-joins-v1.json');science=read(PRE/'full-scientific-config-comparison-v1.json')
 def norm(x,m):
  if isinstance(x,str):return x.replace(m['output_dir'],'<prospective-output>').replace(m['source']['commit'],'<source-commit>')
  if isinstance(x,list):return [norm(v,m) for v in x]
  if isinstance(x,dict):return {k:norm(v,m) for k,v in x.items()}
  return x
 def all40():
  rows=plan['episodes'];assert len(rows)==len(joins['rows'])==len(science['rows'])==40;assert rows==old['episodes'];assert set(plan['expected_manifests'])=={r['episode_key'] for r in rows}
  done=[]
  for row,j,sc in zip(rows,joins['rows'],science['rows']):
   guard();key=row['episode_key'];m=ref(plan['expected_manifests'][key]);prior=ref(old['expected_manifests'][key]);assert m==json.loads(json.dumps(b.manifest(plan,runtime,row)))
   assert j['row']==row and j['manifest']==plan['expected_manifests'][key];ctx=ref(j['context']);assert ctx['release'] is None and ctx['expected_manifest']==j['manifest'] and ctx['episode_key']==ctx['attempt_id']==key and ctx['main_argv']==m['argv'][1:] and ctx['worker_contract']==c.WORKER_CONTRACT
   assert ctx['plan']['sha256']==sha(PRE/'plan.complete-disabled-v1.json');assert P(ctx['plan']['path']).resolve()==(PRE/'plan.complete-disabled-v1.json').resolve()
   assert j['argv_sha256']==b.w.canonical_sha(m['argv']) and j['composed_config_sha256']==m['composed_config_sha256'] and j['resolved_config_sha256']==b.w.canonical_sha(m['resolved_config'])
   assert not os.path.lexists(m['output_dir']) and m['output_dir']==j['output_dir'];assert prior['row']==row and norm(prior['argv'],prior)==norm(m['argv'],m)
   before,_=b.compose_launch(prior['argv'],ROOT);after,_=b.compose_launch(m['argv'],ROOT)
   assert b.w.canonical_sha(before)==prior['composed_config_sha256'] and b.w.canonical_sha(after)==m['composed_config_sha256'];assert norm(before,prior)==norm(after,m)
   assert sc['episode_key']==key and sc['normalized_composed_config_sha256']==b.w.canonical_sha(norm(after,m));done.append({'episode_key':key,'manifest_sha256':j['manifest']['sha256'],'output_absent':True})
  return done
 check('all40_production_manifest_and_full_science_joins',all40)
 def origins():
  from importlib.machinery import PathFinder
  d=read(PRE/'import-origins-v1.json')
  for x in d['resolved_only']:
   search=d['search_path'];name=x['module']
   for i in range(1,len(name.split('.'))+1):
    spec=PathFinder.find_spec('.'.join(name.split('.')[:i]),search);assert spec;search=spec.submodule_search_locations
   e=x['resolved_origin']
   if 'path'in e:assert str(P(spec.origin).resolve())==e['path'] and sha(e['path'])==e['sha256']
   else:assert list(spec.submodule_search_locations)==e['namespace_locations']
  return {'passive_resolutions':len(d['resolved_only']),'historical_actual_cpu_imports':list(d['actual_cpu_imports']),'worker_import_evidence':False,'adjacent_checkout_search_paths':[p for p in d['search_path'] if '/.worktrees/' in p]}
 check('passive_import_resolution_provenance',origins)
 def blocked():
  try:release.validate_plan(plan)
  except ValueError as e:assert str(e)=='N36R2 draft only; release disabled';return str(e)
  raise AssertionError('B5 admitted')
 check('B5_hard_rejection',blocked)
 assert not plan['release_enabled'] and not plan['frozen'] and plan['root_review'] is None and plan['authority'] is None and plan['execution_release'] is None
 assert all(v is False for v in plan['phase_authorization'].values())
 R['final_status']=git('status','--porcelain=v1');assert R['final_status']==''
 guard()
try:main()
except BaseException as e:R['errors'].append({'error':repr(e),'traceback':traceback.format_exc()});print(traceback.format_exc())
R['elapsed_seconds']=time.monotonic()-START;R['cpu_seconds']=resource.getrusage(resource.RUSAGE_SELF).ru_utime+resource.getrusage(resource.RUSAGE_SELF).ru_stime;R['stop_paths']={p:os.path.lexists(p) for p in A['STOP_paths']};R['at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
with (OUT/'check-results-v1.json').open('x') as f:json.dump(R,f,indent=2);f.write('\n')
print(json.dumps({'errors':R['errors'],'elapsed_seconds':R['elapsed_seconds'],'cpu_seconds':R['cpu_seconds']}))
