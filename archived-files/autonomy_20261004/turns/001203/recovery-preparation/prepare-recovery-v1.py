import ast,copy,datetime as dt,hashlib,json,os,pathlib,resource,subprocess,time
OUT=pathlib.Path(__file__).resolve().parent; T=OUT.parents[1]; START=time.monotonic()
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def ref(p):return {'path':str(p),'sha256':sha(p),'bytes':pathlib.Path(p).stat().st_size}
def write(n,v):
 p=OUT/n;p.write_text(json.dumps(v,indent=2)+'\n');return ref(p)
def read(r):
 assert sha(r['path'])==r['sha256'],r['path'];return json.loads(pathlib.Path(r['path']).read_text())
a=json.loads((OUT/'authority-v1.json').read_text());root=pathlib.Path(a['implementation_worktree']);stop=root.parents[2]/'autonomy_20261004/STOP'
def guard():
 assert not os.path.lexists(stop),'STOP'
 assert dt.datetime.now(dt.timezone.utc)<dt.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
 assert time.monotonic()-START<1700
 return {'at':dt.datetime.now(dt.timezone.utc).isoformat(),'stop_absent':True}
g0=guard();diagnosis=read(a['diagnosis']);p=read(a['prior_plan']);old=read(p['native_build']);assert read(diagnosis['native_manifest'])==old
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip();assert head==a['source']
ledger0=ref(a['ledger']['path']);assert ledger0['sha256']==a['ledger']['sha256'] and ledger0['bytes']==a['ledger']['bytes']
protected=[a['prior_plan'],a['diagnosis'],p['native_build'],ref(T/'001199/execution-release-v2.json'),ref(T/'001185/runtime-preparation/report-v1.json')]
# Only native binaries and narrow contract sources are rehashed; no model or task data reads.
checks=[]
for r in old['libraries']:
 guard();q=pathlib.Path(r['path']);assert q.is_absolute() and str(q.resolve())==str(q) and not q.is_symlink();v=ref(q);assert v['sha256']==r['sha256'];checks.append(v)
source_checks=[]
for name in ['scripts/qd_ed_n36_build.py','scripts/qd_ed_n36_contract.py','scripts/qd_ed_n36_release.py','scripts/qd_ed_n36_runner.py','scripts/qd_ed_n36_bridge.py']:
 q=root/name;expected=next(x['sha256'] for x in p['source']['files'] if x['path']==name);assert sha(q)==expected;source_checks.append(ref(q))
write('input-verification-v1.json',{'authority':ref(OUT/'authority-v1.json'),'bound_inputs':protected,'source_head':head,'narrow_sources':source_checks,'ledger_before':ledger0,'native_binaries':checks,'native_bytes_hashed':sum(x['bytes'] for x in checks),'guard_start':g0})
probe='''import ast,json,os,pathlib,sys\nsys.path.append('/home/hynx/miniconda3/envs/vla-pilot/lib/python3.12/site-packages')\nimport torch\nassert os.environ['CUDA_VISIBLE_DEVICES']=='7'\nassert not torch.cuda.is_initialized()\nactual={'torch_version':str(torch.__version__),'cuda_version':torch.version.cuda,'torch_build':torch.__config__.show()}\nassert not torch.cuda.is_initialized()\nold=json.loads(pathlib.Path(sys.argv[1]).read_text())\nresult={'actual':actual,'visibility':os.environ['CUDA_VISIBLE_DEVICES'],'cuda_initialized_before':False,'cuda_initialized_after':torch.cuda.is_initialized(),'old_matches':{k:old[k]==v for k,v in actual.items()},'torch_file':torch.__file__}\nif len(sys.argv)>3:\n new=json.loads(pathlib.Path(sys.argv[2]).read_text())\n tree=ast.parse(pathlib.Path(sys.argv[3]).read_text());fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='attest');expr=fn.body[1].value.args[0]\n predicate=compile(ast.Expression(expr),sys.argv[3],'eval')\n result['existing_exact_metadata_predicate']=ast.unparse(expr)\n result['old_predicate']=eval(predicate,{'expected':old,'torch':torch})\n result['new_predicate']=eval(predicate,{'expected':new,'torch':torch})\n result['new_matches']={k:new[k]==v for k,v in actual.items()}\n assert result['old_predicate'] is False and result['new_predicate'] is True\nassert not torch.cuda.is_initialized()\nprint(json.dumps(result))\n'''
(OUT/'metadata-probe-v1.py').write_text(probe)
env={'PATH':'/usr/bin:/bin','HOME':str(OUT),'CUDA_VISIBLE_DEVICES':'7','OMP_NUM_THREADS':'2','MKL_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2','PYTHONDONTWRITEBYTECODE':'1','TMPDIR':str(OUT)}
py='/home/hynx/miniconda3/envs/vla-pilot/bin/python3.12';commands=[]
def run(label,args):
 guard();cmd=[py,'-I','-S','-B',str(OUT/'metadata-probe-v1.py'),*args];t=time.monotonic();u=resource.getrusage(resource.RUSAGE_CHILDREN);r=subprocess.run(cmd,env=env,cwd=root,capture_output=True,text=True,timeout=90);v=resource.getrusage(resource.RUSAGE_CHILDREN)
 (OUT/(label+'.stderr.txt')).write_text(r.stderr)
 commands.append({'command':cmd,'environment':env,'cwd':str(root),'exit_code':r.returncode,'wall_seconds':time.monotonic()-t,'child_cpu_seconds':v.ru_utime+v.ru_stime-u.ru_utime-u.ru_stime,'peak_child_rss_kib':v.ru_maxrss})
 assert r.returncode==0,r.stderr;d=json.loads(r.stdout);write(label+'.json',d);return d
actual=run('metadata-capture-v1',[p['native_build']['path']]);new=copy.deepcopy(old);new.update(actual['actual']);assert [k for k in old if old[k]!=new[k]]==['torch_build'];nr=write('native-build-n36r1.draft-v1.json',new)
verification=run('metadata-comparison-v1',[p['native_build']['path'],nr['path'],str(root/'scripts/qd_ed_n36_build.py')]);write('cpu-commands-v1.json',commands)
# Intentionally a proposal schema, not a runner-valid plan. Existing code cannot admit fresh identities.
cohort='N36R1_NONPROGRESS_TANGENT_DEV_001203';rows=[];bindings=[]
for i,original in enumerate(p['episodes']):
 row=copy.deepcopy(original);row['iteration']=cohort;row['episode_key']=f'n36r1_dev_t{row["task_id"]:02d}_{row["profile"].lower()}_001203';rows.append(row)
 bindings.append({'ordinal':i+1,'original_episode_key':original['episode_key'],'prospective_attempt_id':row['episode_key'],'prospective_row':row,'inherited_manifest':p['expected_manifests'][original['episode_key']],'prospective_output_dir':str(OUT/'prospective-artifacts/attempts'/row['episode_key']),'allocation_status':'PROPOSED_NOT_RESERVED','relation':'fresh matched cell; original invalid attempt retained' if i==0 else 'fresh matched unexecuted cell'})
assert len(set(r['episode_key'] for r in rows))==40
# Hash ledger bytes without opening protected scientific records; only exact invalid-ID lines inspected.
ledgerbytes=pathlib.Path(a['ledger']['path']).read_bytes();old_id=b'n36_dev_t00_c0_001147';selected=[]
for line in ledgerbytes.splitlines():
 if old_id in line:
  event=json.loads(line)
  if event.get('attempt_id')==old_id.decode():selected.append({'event':event.get('event'),'attempt_id':event.get('attempt_id'),'line_sha256':hashlib.sha256(line).hexdigest(),'gpu_seconds':event.get('gpu_seconds'),'gpu_hours':event.get('gpu_hours'),'status':event.get('status')})
assert all(r['episode_key'].encode() not in ledgerbytes for r in rows)
ar=write('attempt-allocation.draft-v1.json',{'schema':'n36r1-prospective-allocation-v1','release_enabled':False,'recovery_id':'N36R1_001203','cohort':cohort,'attempts':bindings,'proposed_count':40,'proposed_by_bucket':{'baseline':10,'development':30,'recovery':0},'allocation_is_not_authority':True,'automatic_recoveries':0,'replay':False,'abandoned_original_ids_are_not_deleted':True,'original_invalid_attempt':{'attempt_id':old_id.decode(),'gpu_seconds':86.40354533703066,'charge_preserved':True,'ledger_line_evidence':selected},'fresh_ids_absent_from_ledger':True})
inherited={k:p[k] for k in ['source','scientific_source','runtime','runtime_closure','controller_semantics','protocol','protocol_review','worker_contract','limits','deadline','stop_path','runtime_inventory_path','runtime_inventory_sha256','seed_plan_path','seed_plan_sha256','input_contract_label']}
pr=write('plan.n36r1.proposal-v1.json',{'schema':'n36r1-engineering-recovery-proposal-v1','frozen':False,'release_enabled':False,'runtime_ready':False,'approved':False,'executable':False,'worktree':p['worktree'],'source':p['source'],'scientific_source':p['scientific_source'],'native_build':nr,'recovery_id':'N36R1_001203','cohort':cohort,'episodes':rows,'allocation':ar,'original_plan':a['prior_plan'],'inherited_bindings':inherited,'inherited_bindings_are_not_new_readiness_or_authority':True,'authority':None,'execution_release':None,'root_review':None,'phase_authorization':{'dev':False,'validation':False,'formal':False},'expected_manifests':{},'manifest_preparation_status':'BLOCKED by immutable identity/protocol contract; old manifests retained as inherited inputs, not relabeled as newly valid','budget_adopted':False,'reserve_consumed':False})
blockers=[{'id':'IMMUTABLE_IDENTITY_CONTRACT','evidence':source_checks[1:3],'detail':'qd_ed_n36_contract.py COHORT line 11 and expected_rows lines 46-54 hard-code original iteration and episode keys; require_row line 58 and validate_draft lines 87-96 reject N36R1. qd_ed_n36_release.py validate_plan lines 14-22 requires exact expected_rows; lines 55-60 bind fixed protocol/review hashes and protocol episode equality; lines 65-72 bind original cohort authority. Fresh identifiers cannot pass unchanged source even with a new native manifest.','needed':'Separately authorized minimal identity/protocol/accounting binding implementation and review, or root decision to stop. No source change made. Do not monkeypatch constants, weaken equality, replay the invalid key, or sign this proposal.'}]
write('release-blockers-v1.json',blockers)
ledger1=ref(a['ledger']['path']);assert ledger1==ledger0
for r in protected:assert sha(r['path'])==r['sha256']
write('preservation-v1.json',{'ledger_before':ledger0,'ledger_after':ledger1,'byte_identical':True,'original_records_unchanged':protected,'source_head':head,'narrow_sources_unchanged':all(sha(x['path'])==x['sha256'] for x in source_checks),'study_dispatches':503,'study_gpu_hours':75.26779409697457,'study_totals_basis':'user supplied; not independently recomputed from protected records','invalid_attempt_gpu_seconds_preserved':86.40354533703066,'new_dispatches':0,'new_gpu_seconds':0,'new_reservations':0,'guard_end':guard()})
print(json.dumps({'native_manifest':nr,'plan_proposal':pr,'allocation':ar,'metadata_checks':verification['new_matches'],'blocker':blockers[0]['id'],'wall_seconds':time.monotonic()-START}))
