"""Independent bounded byte/AST/reported-test review; no new test or experiment."""
from pathlib import Path
import ast,hashlib,json,subprocess,datetime
H=Path(__file__).resolve().parent;I=H/'implementation';P=H.parent
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
ref=lambda p:{'path':str(Path(p).resolve()),'sha256':sha(p)}
base='4ce2b95757c1c0d662696ba19d6a9a14d2e59b49';head='7c0d80d734fa8300173e56d9a8de03415bc55fe2'
def git(*args):return subprocess.check_output(['git',*args],cwd=I)
assert git('rev-parse','HEAD').decode().strip()==head and git('rev-parse','HEAD^').decode().strip()==base
assert git('status','--porcelain')==b''
delivery=read(H/'delivery-manifest-v1.json')
assert sha(H/'delivery-manifest-v1.json')=='6d4d9d3f1a48b1bdf9bc417d45703b10214a9db3af1dca6b58c5b55d9b0e0cce'
for f in delivery['files']:assert sha(f['path'])==f['sha256'] and Path(f['path']).stat().st_size==f['bytes']
source=read(H/'source-manifest-v1.json')
changed=git('diff','--name-only',base,head).decode().splitlines()
assert changed==[v['path'] for v in source['files']]
for f in source['files']:
 assert hashlib.sha256(git('show',head+':'+f['path'])).hexdigest()==f['sha256']==sha(I/f['path'])
new=(I/'main.py').read_bytes();old=git('show',base+':main.py')
delta=b'        if continuation_enabled:\n            # Raw cached reset observation; policy preprocessing removes robot_state.\n            obs = self.adapter.get_obs()\n'
assert new.count(delta)==1 and new.replace(delta,b'',1)==old
pinned=read(I/'tests/n30_initial_observation_original.json')
def method(src,name):
 cls=next(x for x in ast.parse(src).body if isinstance(x,ast.ClassDef) and x.name=='Main')
 return next(x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name==name)
assert ast.dump(ast.parse(pinned['method_source']).body[0],include_attributes=False)==ast.dump(method(old,'_run_episode'),include_attributes=False)
assert pinned['base_commit']==base
prior=read(P/'source-manifest-execution-v1.json')
for f in prior['files']:
 if f['path']!='main.py':assert sha(I/f['path'])==f['sha256']
resource=read(H/'cpu-repair-run1-resource.json');log=(H/'cpu-repair-run1.log').read_text()
assert resource['pytest_exit']==0 and resource['guard_clean'] and not resource['denied']
assert resource['cuda_visible_devices']=='' and resource['cuda_initialized'] is False
assert resource['cpu_affinity']==[0,1] and resource['threads']==2 and resource['process_cpu_seconds']<600
assert '7 passed' in log
out={'schema':'n30-root-initial-observation-repair-review-v1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'disposition':'ACCEPT_CPU_REPAIR_ONLY','base_commit':base,'commit':head,'delivery':ref(H/'delivery-manifest-v1.json'),
 'source':ref(H/'source-manifest-v1.json'),'test_resource':ref(H/'cpu-repair-run1-resource.json'),'test_log':ref(H/'cpu-repair-run1.log'),
 'artifact_refs_verified':len(delivery['files']),'changed_files':changed,'existing_source_files_unchanged':438,
 'sole_production_delta':'N30-only passive cached raw observation initialization; exact three-line reversal matches original Main bytes',
 'old_complete_method_ast_independently_bound':True,'tests_reported_passed':7,'focused_cpu_seconds':resource['process_cpu_seconds'],
 'independent_review':'Root read complete regression, inspected actual Main/adapter provenance, rehashed Git blobs and pinned original full method; did not rerun tests already passing.',
 'cpu_regression_scope':'Synthetic external environment/model/Stage; actual complete Main loop and real policy/helper/DecisionEvidence. Not a production outcome.',
 'gpu_release':False,'algorithm_changed':False,'old_ledger_modified':False,'goal_status':'TARGET_NOT_MET'}
with (H/'root-cpu-repair-review-v1.json').open('x') as f:json.dump(out,f,indent=2);f.write('\n')
print(json.dumps({k:out[k] for k in ('disposition','commit','artifact_refs_verified','existing_source_files_unchanged','tests_reported_passed')}))

