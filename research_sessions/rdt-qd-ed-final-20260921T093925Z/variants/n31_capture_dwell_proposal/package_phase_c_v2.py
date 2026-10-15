"""Static-only CPU packaging: frozen function ASTs, metadata and Git source bytes; never launch."""
from pathlib import Path
from types import SimpleNamespace
import ast,copy,hashlib,json,re,subprocess,time,resource
P=Path(__file__).resolve().parent;I=P/'implementation';R=I.parents[2]
start=time.process_time();wall=time.monotonic();reads=[]
def raw(p):
 p=Path(p);b=p.read_bytes();reads.append({'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()});return b
def read(p):return json.loads(raw(p))
def ref(p):p=Path(p);return {'path':str(p.resolve()),'sha256':hashlib.sha256(raw(p)).hexdigest()}
def dump(name,value):
 if (P/name).exists():
  assert json.loads((P/name).read_text())==value,name;return
 with (P/name).open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
def require(x,msg):
 if not x:raise ValueError(msg)
def load_functions(relative,names,ns):
 p=I/relative;t=ast.parse(raw(p));nodes=[n for n in t.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names]
 assert {n.name for n in nodes}==set(names)
 exec(compile(ast.Module(nodes,type_ignores=[]),str(p),'exec'),ns)
def constants(relative,names):
 tree=ast.parse(raw(I/relative));out={}
 for n in tree.body:
  if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id in names:
   try:out[n.targets[0].id]=ast.literal_eval(n.value)
   except ValueError:
    assert n.targets[0].id=='WORKER_CONTRACT'
    out[n.targets[0].id]=eval(compile(ast.Expression(n.value),relative,'eval'),{'__builtins__':{},'list':list,'ARMS':out['ARMS']})
 assert set(out)==set(names);return out
# Assemble real complete closure without imports or suppressed filesystem errors.
bs={'Path':Path,'json':json,'DOC':'docs/experiments/n31'}
load_functions('scripts/qd_ed_n31_bridge.py',['source_paths'],bs);paths=bs['source_paths'](I)
required=constants('scripts/qd_ed_final_runner.py',['REQUIRED_CODE'])['REQUIRED_CODE']
for folder in ('core','utils','vlm_query'):
 required.update(str(f.relative_to(I)) for f in (I/folder).rglob('*') if f.is_file() and f.suffix in {'.py','.txt'})
required |= constants('scripts/qd_ed_n23_worker.py',['REQUIRED_SOURCE'])['REQUIRED_SOURCE']
assert required<=paths,sorted(required-paths)
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=I,text=True).strip()
assert not subprocess.check_output(['git','status','--porcelain'],cwd=I,text=True)
files=[]
for name in sorted(paths):
 b=raw(I/name);assert subprocess.check_output(['git','show',commit+':'+name],cwd=I)==b
 files.append({'path':name,'sha256':hashlib.sha256(b).hexdigest()})
source={'commit':commit,'files':files,'sha256':hashlib.sha256(json.dumps(files,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()}
# Worker source_record hashes files, see exact consistency check below.
worker=ast.parse(raw(I/'scripts/qd_ed_n23_worker.py'))
sourcefun=next(n for n in worker.body if isinstance(n,ast.FunctionDef) and n.name=='source_record')
print('source_record return:',ast.unparse(sourcefun.body[-1]))
dump('source-manifest-execution-v1.json',source)
old=read(I/'docs/experiments/n31/base-source-v1.json');reverse=read(I/'docs/experiments/n31/reverse-source-v1.json')
current={x['path']:x['sha256'] for x in files};base={x['path']:x['sha256'] for x in old['files']}
for name,hash0 in base.items():
 b=raw(I/name)
 if name in reverse['files']:
  rec=reverse['files'][name];assert rec['new_sha256']==current[name] and rec['old_sha256']==hash0
  lines=b.decode().splitlines(keepends=True)
  for h in reversed(rec['hunks']):assert lines[h['start']:h['end']]==h['new'];lines[h['start']:h['end']]=h['old']
  b=''.join(lines).encode()
 assert hashlib.sha256(b).hexdigest()==hash0
new=sorted(set(current)-set(base));changed=sorted(k for k in base if base[k]!=current[k])
assert set(subprocess.check_output(['git','diff','--name-only',old['commit'],commit],cwd=I,text=True).splitlines())<=set(current)
dump('source-closure-phase-c-v1.json',{'schema':'n31-cpu-source-closure-v1','commit':commit,'base':old['commit'],'files':len(files),'required_code_complete':True,'required_source_files':len(required),'unchanged_old':len(base)-len(changed),'changed_existing':changed,'new':new,'reverse':ref(I/'docs/experiments/n31/reverse-source-v1.json'),'phase_a_helper':ref(I/'core/qd_capture_dwell_proposal.py'),'base_audit':'All current files equal committed Git blobs; all old files equal base or reverse byte-exactly. No history payload/proof execution.'})
assert (P/'phase-c-source.diff').read_bytes()==subprocess.check_output(['git','diff','ae5ecf82ccbfd8f904a655ea78f75d433e8a5c77',commit],cwd=I)
assert (P/'full-n31-source.diff').read_bytes()==subprocess.check_output(['git','diff',old['commit'],commit],cwd=I)
# Execute only existing pure builder function AST with explicit metadata/ref bindings.
refs=read(I/'docs/experiments/n31/historical-input-bindings-v1.json');oldplan=read(I/'docs/experiments/n31/base-plan-metadata-v1.json')
protocol=ref(P/'prospective-dev-science-protocol-v1.md');tasks=read(I/'configs/qd_ed_final/n31_dev_task_identities.json')['tasks']
cc=constants('scripts/qd_ed_n31_contract.py',['COHORT','LIMITS','WORKER_CONTRACT','ARMS'])
rows=[{**task,'iteration':cc['COHORT'],'profile':arm,'timeout_seconds':1800,'episode_key':f'n31_dev_t{task["task_id"]:02d}_{arm.lower()}_20261004','budget_bucket':'baseline' if arm=='C0' else 'development'} for task in tasks for arm in cc['ARMS']]
obs=R/'variants/n23_actuator_clipped_quality/timeout-observability-addendum-v2.md'
obsref={'path':str(obs),'sha256':'fa0723919c67d0417b101be2a36d9832cfaaf15e4b1c4e0cdfbf61caa43e34c6'}
def metadata_ref(path):
 if Path(path)==obs:return obsref
 if Path(path)==Path(refs['source_plan']['path']):return refs['source_plan']
 return ref(path)
c=SimpleNamespace(**cc,RUN_DIR=P,SOURCE_PLAN=Path(refs['source_plan']['path']),PROTOCOL=P/'prospective-dev-science-protocol-v1.md',OBSERVABILITY=obs,BUDGET_REUSE=P/'budget-adoption-v1/authority.json',ref=metadata_ref,original_plan=lambda:copy.deepcopy(oldplan),runtime_ref=lambda:refs['runtime'],expected_rows=lambda:copy.deepcopy(rows))
ns={'Path':Path,'copy':copy,'c':c,'ROOT':I}
load_functions('scripts/qd_ed_n31_prepare.py',['build_plan'],ns)
plan=ns['build_plan'](source=source,root=I);assert plan['frozen'] is False and len(plan['episodes'])==30
# Explicit unresolved refs ensure this preview cannot be released.
assert all(plan['n31_cohort'][k] is None for k in ('authority','final_review','predecessor','budget_reuse'))
dump('plan.preview.disabled.v1.json',plan)
# Commands use the exact build_command AST and hash-bound public runtime metadata;
# this is offline composition, not real admission or CLI/provider invocation.
runtime_bytes=raw(refs['runtime']['path']);assert hashlib.sha256(runtime_bytes).hexdigest()==refs['runtime']['sha256'];runtime=json.loads(runtime_bytes)
manifest=read(I/'configs/qd_ed_final/n4_observed_baseline_profiles.json');candidate=read(I/'configs/qd_ed_final/candidate_n31.json')
w=SimpleNamespace(require=require,sha=lambda p:ref(p)['sha256'])
rns={'Path':Path,'json':json,'re':re,'require':require,'PYTHON':Path('/home/hynx/miniconda3/envs/vla-pilot/bin/python')}
rns.update(constants('scripts/qd_ed_final_runner.py',['CODEX_CONFIG_KEYS','E2_STAGE_CONDITION','CODEX_STAGE_CONDITION']))
public={'Path':Path,'hashlib':hashlib,'json':json};public.update(constants('core/codex_stage_policy.py',['_DISABLED_FEATURES','_DEVELOPER_INSTRUCTIONS','_REMOVED_ENVIRONMENT','_MAX_EVENTS_BYTES']))
load_functions('core/codex_stage_policy.py',['public_invocation_policy','policy_sha256'],public)
rns['codex_public_config_sha256']=lambda frozen:public['policy_sha256'](public['public_invocation_policy'](**{k:frozen[k] for k in rns['CODEX_CONFIG_KEYS'] if k!='backend'}))
rns['n4e1_support']=lambda:SimpleNamespace(engineering_condition=lambda:runtime['stage_engineering_condition'])
rns['is_n17_plan']=lambda p:False # Exact new plan has n31 marker and no old markers; real predicate route tested in run8.
load_functions('scripts/qd_ed_final_runner.py',['owned','hydra','stage_overrides','stage_condition','build_command'],rns)
cns={'Path':Path,'copy':copy,'w':w};load_functions('scripts/qd_ed_n31_contract.py',['expand_candidate'],cns)
manifest['profiles']['N31']=cns['expand_candidate'](candidate,manifest['profiles']['Q0'],{'ROOT':I,'read_json':read,'hydra':rns['hydra']})
commands=[]
for row in rows:
 aid='DISABLED_PREVIEW__'+row['episode_key'];argv,output=rns['build_command'](plan,manifest,runtime,row,aid)
 commands.append({'episode_key':row['episode_key'],'profile':row['profile'],'task_id':row['task_id'],'argv':argv,'output':str(output)})
dump('commands.preview.disabled.v1.json',{'schema':'n31-offline-command-preview-v1','executable':False,'root':str(I),'source_commit':commit,'runtime':refs['runtime'],'commands':commands,'limitations':'Pure existing function AST composition only. Future owning W paths/source/admission/account/GPU/resource checks remain mandatory; no real commands executed. E1 condition supplied by hash-bound runtime; exact full contract/Hydra checked with controlled fixtures in run8.'})
# Templates are envelopes, deliberately not valid adopted records.
blank={'path':None,'sha256':None}
dump('source-bridge.disabled.v1.json',{'schema':'n31-source-equivalence-bridge-template-v1','executable':False,'source':source,'runtime':refs['runtime'],'requires':'root bridge.build(source,runtime,owning_W) after exact adoption; no historical replay'})
review={'schema':'n31-source-runtime-review-v1','disposition':None,'source':source,'runtime':refs['runtime'],'protocol':protocol,'source_plan':refs['source_plan'],'source_bridge':blank,'predecessor':refs['closed_review'],'new_tensor_preflight':False,'budget_reuse':blank,'no_gpu_release':True}
dump('final-review.disabled.v1.json',{'executable':False,'record_template':review})
authority={'schema':'n31-dev-authority-v1','cohort_id':cc['COHORT'],'source':source,'runtime':refs['runtime'],'protocol':protocol,'final_review':blank,'budget_reuse':blank,'limits':cc['LIMITS'],'local_gpu_hours':5.0,'recorded_at':None,'authority_interpretation':None,'predecessor':refs['closed_review'],'validation_authorized':False,'formal_authorized':False}
dump('adoption-authority.disabled.v1.json',{'executable':False,'record_template':authority})
budget={'schema':'n31-approved-budget-authority-v1','approved':False,'cohort_id':cc['COHORT'],'approval_basis':None,'caps':None,'amendment':{'approval':blank,'proposal':blank,'previous_authority':blank,'history_boundary':{'dispatched':403,'gpu_hours_consumed':53.80872756284531}},'weekly_window':None,'validation_authorized':False,'formal_authorized':False}
dump('budget-authority.disabled.v1.json',{'executable':False,'record_template':budget,'unapproved_alternatives':[{'attempts':598,'gpu_hours':100.,'buckets':dict(zip(['baseline','development','validation','formal','recovery'],[84,274,180,40,20])),'protected_gpu_hours':{'validation':32.,'formal':12.},'weekly_window':None},{'attempts':1800,'gpu_hours':224.,'buckets':dict(zip(['baseline','development','validation','formal','recovery'],[400,1120,180,40,60])),'protected_gpu_hours':{'validation':32.,'formal':12.},'weekly_window':{'origin_gpu_hours':53.08404692669838,'increment_gpu_hours':168.,'ends_at':'2026-10-10T17:42:00Z'}}]})
release={'schema':'n31-dev-execution-release-v1','plan':blank,'source_commit':commit,'cohort_id':cc['COHORT'],'episode_keys':[r['episode_key'] for r in rows],'authority':blank,'physical_gpu':7,'limits':cc['LIMITS'],'validation_authorized':False,'formal_authorized':False}
dump('execution-release.disabled.v1.json',{'executable':False,'record_template':release})
dump('packaging-resource-phase-c-v1.json',{'schema':'n31-static-packaging-resource-v1','cpu_seconds':time.process_time()-start,'child_cpu_seconds':resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime+resource.getrusage(resource.RUSAGE_CHILDREN).ru_stime,'wall_seconds':time.monotonic()-wall,'source_and_metadata_reads':reads,'production_imports':0,'historical_payload_reads':0,'provider_model_gpu_env_calls':0})
print('commit',commit,'files',len(files),'changed',len(changed),'new',len(new))
