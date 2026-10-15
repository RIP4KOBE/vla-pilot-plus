"""Stdlib-only delivery assembly; no imports of experiment modules or actual outputs."""
from pathlib import Path
import os,json,hashlib,subprocess,ast,time
K=Path(__file__).resolve().parent;I=K/'implementation';P=K.parent
os.sched_setaffinity(0,{0,1})
for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='2'
start=time.process_time()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def canonical(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def save(name,value):
 p=K/name
 with p.open('x') as f:f.write(json.dumps(value,indent=2,allow_nan=False)+'\n')
 return {'path':str(p),'sha256':sha(p)}
def ref(p):return {'path':str(p),'sha256':sha(p)}
base=json.loads((I/'docs/experiments/n30/r1/base-source-v1.json').read_text());original=json.loads((I/'docs/experiments/n30/r1/original-source-v1.json').read_text())
paths={x['path'] for x in base['files']}
for pattern in ('scripts/qd_ed_n30_r1_*.py','tests/test_n30_r1*.py','tests/n30_r1*.py','docs/experiments/n30/r1/*'):
 paths.update(str(p.relative_to(I)) for p in I.glob(pattern) if p.is_file())
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=I,text=True).strip()
assert not subprocess.check_output(['git','status','--porcelain'],cwd=I)
files=[]
for name in sorted(paths):
 data=(I/name).read_bytes();assert data==subprocess.check_output(['git','show',commit+':'+name],cwd=I)
 files.append({'path':name,'sha256':hashlib.sha256(data).hexdigest()})
source={'commit':commit,'files':files,'sha256':canonical(files)}
sourceref=save('source-manifest-execution-v1.json',source)
reverse=json.loads((I/'docs/experiments/n30/r1/reverse-source-v1.json').read_text());changed=[]
index={x['path']:x['sha256'] for x in files}
for f in base['files']:
 data=(I/f['path']).read_bytes()
 if index[f['path']]!=f['sha256']:
  changed.append(f['path']);e=reverse['files'][f['path']];assert e['new_sha256']==index[f['path']] and e['old_sha256']==f['sha256']
  lines=data.decode().splitlines(keepends=True)
  for h in reversed(e['hunks']):assert lines[h['start']:h['end']]==h['new'];lines[h['start']:h['end']]=h['old']
  assert hashlib.sha256(''.join(lines).encode()).hexdigest()==f['sha256']
assert set(changed)==set(reverse['files'])
sourcecheck={'schema':'n30-r1-static-source-check-v1','commit':commit,'base_commit':base['commit'],'files_verified':len(files),
 'base_files':len(base['files']),'unchanged_base_files':len(base['files'])-len(changed),'modified_base_files':changed,
 'added_files':sorted(paths-{x['path'] for x in base['files']}),'whole_file_reverse_verified':True,'git_blob_equality_verified':True,
 'runtime_or_history_outputs_read':False,'cuda_imported':False}
save('source-byte-check-v1.json',sourcecheck)
(K/'source-diff-v1.patch').write_bytes(subprocess.check_output(['git','diff',base['commit'],commit,'--'],cwd=I))
limits={'logical_cells':12,'inherited_cells':2,'new_dispatches':10,'combined_dispatches':13,'named_recoveries':1,
 'new_buckets':{'baseline':3,'development':6,'recovery':1},'combined_gpu_hours':6.,'old_gpu_seconds':1090.1433259700425,
 'episode_timeout_seconds':1800,'cleanup_seconds':40,'physical_gpu':7}
caps={'attempts':578,'gpu_hours':100.,'buckets':{'baseline':76,'development':262,'validation':180,'formal':40,'recovery':20},'protected_gpu_hours':{'validation':32.,'formal':12.}}
cohort='N30_INITIAL_OBSERVATION_REPAIR_DEV_20261003';protocol=ref(K/'cpu-integration-scope-v1.md')
def draft(name,payload,missing):return save(name,{'schema':'n30-r1-disabled-artifact-template-v1','executable':False,'gpu_release':False,'unresolved':missing,'payload':payload})
draft('source-history-bridge.disabled.v1.json',{'schema':'n30-r1-source-history-bridge-v1','source':source,'repair_base_source':base,'original_source':original,'runtime':None,
 'metadata_refs':None,'imports':None,'old_gpu_seconds':limits['old_gpu_seconds'],'original_disposition':'INVALID_OR_INTERRUPTED',
 'historical_trust':None,'new_standalone_proof':False,'gpu_release':False},['root runs bridge.build under adopted source; no history values fabricated'])
draft('final-source-runtime-review.disabled.v1.json',{'schema':'n30-r1-source-runtime-review-v1','disposition':'accepted','source':source,'runtime':None,
 'protocol':protocol,'source_bridge':None,'new_tensor_preflight':False,'no_gpu_release':True},['runtime','source_bridge','independent root source/runtime acceptance'])
draft('authority.disabled.v1.json',{'schema':'n30-r1-authority-v1','cohort_id':cohort,'source':source,'runtime':None,'protocol':protocol,'final_review':None,
 'source_bridge':None,'limits':limits,'caps':caps,'validation_authorized':False,'formal_authorized':False,'recorded_at':None,'authority_interpretation':None},
 ['runtime','final_review','source_bridge','recorded_at','authority_interpretation','locked state.n30_r1_authority adoption'])
draft('plan.disabled.v1.json',{'schema':'use original frozen plan schema','frozen':False,'source_commit':commit,'code_files':files,
 'episodes':None,'n30_r1_cohort':{'cohort_id':cohort,'authority':None},'phase_authorization':{'dev':True,'validation':False,'formal':False}},['prepare.build_plan(enabled=False), then root reviewed prepare.freeze; original inputs stay exact'])
keys=[f'n30_r1_dev_t{t:02d}_{a.lower()}_20261003' for t,a in [(0,'N30')]+[(t,a) for t in range(1,4) for a in ('C0','Q0','N30')]]
draft('execution-release.disabled.v1.json',{'schema':'n30-r1-execution-release-v1','plan':None,'source_commit':commit,'cohort_id':cohort,
 'episode_keys':keys,'authority':None,'physical_gpu':7,'limits':limits,'validation_authorized':False,'formal_authorized':False},['plan','authority','root fresh source/runtime/resource/provider/20GiB destination disk review'])
resources=[json.loads((K/f'cpu-run{i}-resource.json').read_text()) for i in range(1,4)]
assert all(x['guard_clean'] and x['pytest_exit']==0 and x['cuda_initialized'] is False for x in resources)
save('cpu-resource-summary-v1.json',{'schema':'n30-r1-cpu-resource-summary-v1','runs':[ref(K/f'cpu-run{i}-resource.json') for i in range(1,4)],
 'process_cpu_seconds':sum(x['process_cpu_seconds'] for x in resources),'wall_seconds':sum(x['wall_seconds'] for x in resources),
 'test_limit_cpu_seconds':1200,'distinct_passed':51,'failed_invocations':0,'guard_denied':0,'cuda_initialized':False,
 'cpu_affinity':[0,1],'threads':2,'brief_authoring_and_git_not_test_execution':True,
 'authoring_scope_deviation':'One empty /tmp/n30_unused was accidentally created, then moved intact to K/empty-authoring-transient-v1.txt; no payload or source content was written/read there.'})
save('packaging-resource-v1.json',{'process_cpu_seconds':time.process_time()-start,'cpu_affinity':sorted(os.sched_getaffinity(0)),
 'mode':'stdlib hashing/Git byte verification only','production_imports':False})
print(json.dumps({'commit':commit,'source':sourceref,'files':len(files),'base_unchanged':len(base['files'])-len(changed),'cpu_seconds':sum(x['process_cpu_seconds'] for x in resources)}))
