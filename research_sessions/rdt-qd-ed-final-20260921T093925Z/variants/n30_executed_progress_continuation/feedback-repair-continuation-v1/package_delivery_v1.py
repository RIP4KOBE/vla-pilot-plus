"""Source-only closure packaging; no production imports or real experiment reads."""
import hashlib,json,subprocess,time,resource,os
from pathlib import Path
L=Path(__file__).resolve().parent;I=L/'implementation';D=I/'docs/experiments/n30/r2'
os.sched_setaffinity(0,{0,1});start=time.process_time();wall=time.monotonic()
sha=lambda data:hashlib.sha256(data).hexdigest()
canonical=lambda obj:sha(json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode())
def put(path,obj):
 with path.open('x') as f:f.write(json.dumps(obj,indent=2)+'\n')
def ref(path):return {'path':str(path),'sha256':sha(path.read_bytes())}
base=json.loads((D/'base-source-v1.json').read_text());paths={v['path'] for v in base['files']}
for pattern in ('scripts/qd_ed_n30_r2_*.py','tests/test_n30_r2*.py','tests/n30_r2*.py','docs/experiments/n30/r2/*'):
 paths.update(str(p.relative_to(I)) for p in I.glob(pattern) if p.is_file())
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=I,text=True).strip()
assert not subprocess.check_output(['git','status','--porcelain'],cwd=I)
files=[]
for p in sorted(paths):
 data=(I/p).read_bytes();assert data==subprocess.check_output(['git','show',head+':'+p],cwd=I)
 files.append({'path':p,'sha256':sha(data)})
source={'commit':head,'files':files,'sha256':canonical(files)};put(L/'source-manifest-execution-v1.json',source)
patch=json.loads((D/'reverse-source-v1.json').read_text());unchanged=[]
for v in base['files']:
 data=(I/v['path']).read_bytes()
 if v['path'] in patch['files']:
  x=patch['files'][v['path']];assert sha(data)==x['new_sha256'];lines=data.decode().splitlines(keepends=True)
  for h in reversed(x['hunks']):assert lines[h['start']:h['end']]==h['new'];lines[h['start']:h['end']]=h['old']
  data=''.join(lines).encode()
 else:unchanged.append(v['path'])
 assert sha(data)==v['sha256']
 assert data==subprocess.check_output(['git','show',base['commit']+':'+v['path']],cwd=I)
changes=subprocess.check_output(['git','diff','--name-status',base['commit'],head],cwd=I,text=True)
with (L/'source-diff-v1.patch').open('xb') as f:f.write(subprocess.check_output(['git','diff',base['commit'],head],cwd=I))
put(L/'source-byte-check-v1.json',{'schema':'n30-r2-source-byte-check-v1','source':ref(L/'source-manifest-execution-v1.json'),
 'base_commit':base['commit'],'current_commit':head,'base_files':len(base['files']),'current_files':len(files),'unchanged_base_files':len(unchanged),
 'modified_base_files':sorted(patch['files']),'new_files':sorted(paths-{x['path'] for x in base['files']}),'whole_file_reversal':True,
 'current_and_base_git_bytes_verified':True,'clean':True,'changes':changes.splitlines(),'reverse':ref(D/'reverse-source-v1.json')})
cohort='N30_TERMINAL_BOOLEAN_REPAIR_DEV_20261003'
limits={'logical_cells':12,'inherited_cells':2,'new_dispatches':10,'combined_dispatches':14,'named_recoveries':1,
 'new_buckets':{'baseline':3,'development':6,'recovery':1},'combined_gpu_hours':6.,'old_gpu_seconds':1445.4208934970666,
 'episode_timeout_seconds':1800,'cleanup_seconds':40,'physical_gpu':7}
caps={'attempts':578,'gpu_hours':100.,'buckets':{'baseline':76,'development':262,'validation':180,'formal':40,'recovery':20},'protected_gpu_hours':{'validation':32.,'formal':12.}}
common={'source':None,'runtime':None,'protocol':ref(L/'cpu-integration-scope-v1.md')}
drafts={
 'bridge':{'schema':'n30-r2-source-history-bridge-v1','source':None,'repair_base_source':None,'original_source':None,'r1_source':None,'runtime':None,
  'metadata_refs':None,'imports':None,'old_gpu_seconds':limits['old_gpu_seconds'],'original_disposition':'INVALID_OR_INTERRUPTED','r1_disposition':'INVALID_OR_INTERRUPTED',
  'invalid_attempts':['rdt-qd-ed-final-20260921T093925Z__n30_dev_t00_n30_20261003__5bf10b19849f','rdt-qd-ed-final-20260921T093925Z__n30_r1_dev_t00_n30_20261003__2138c682c5a7'],
  'r1_review':None,'repair_review':None,'historical_trust':None,'new_standalone_proof':False,'gpu_release':False},
 'final-review':{'schema':'n30-r2-source-runtime-review-v1','disposition':None,**common,'source_bridge':None,'new_tensor_preflight':False,'no_gpu_release':True},
 'authority':{'schema':'n30-r2-authority-v1','cohort_id':cohort,**common,'final_review':None,'source_bridge':None,'limits':limits,'caps':caps,
  'validation_authorized':False,'formal_authorized':False,'recorded_at':None,'authority_interpretation':None},
 'plan':{'schema':'qd-ed-final-plan-v1','frozen':False,'source_commit':head,'code_files':files,'episodes':None,'n30_r2_cohort':{'schema':'n30-r2-cohort-v1','cohort_id':cohort,'limits':limits,'executable':False,'authority':None},'phase_authorization':{'dev':False,'validation':False,'formal':False}},
 'release':{'schema':'n30-r2-execution-release-v1','plan':None,'source_commit':head,'cohort_id':cohort,'episode_keys':None,'authority':None,'physical_gpu':7,'limits':limits,'validation_authorized':False,'formal_authorized':False}}
folder=L/'disabled-templates';folder.mkdir(exist_ok=True)
for name,payload in drafts.items():
 put(folder/(name+'.disabled.v1.json'),{'schema':'n30-r2-disabled-template-v1','executable':False,'gpu_release':False,'validation_authorized':False,'formal_authorized':False,
  'purpose':name,'payload_template':payload,'unresolved':'Root must derive exact live payload through documented API after review/adoption. This envelope is rejected by production validators.'})
put(L/'packaging-resource-v1.json',{'schema':'n30-r2-source-packaging-resource-v1','process_cpu_seconds':time.process_time()-start,'wall_seconds':time.monotonic()-wall,
 'cpu_affinity':sorted(os.sched_getaffinity(0)),'production_imports':0,'historical_tensor_reads':0,'source_files':len(files),'git_source_blobs':len(files)+len(base['files']),
 'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss})
print(json.dumps({'commit':head,'source':ref(L/'source-manifest-execution-v1.json'),'files':len(files),'base_unchanged':len(unchanged),'new':len(paths)-len(base['files'])}))
