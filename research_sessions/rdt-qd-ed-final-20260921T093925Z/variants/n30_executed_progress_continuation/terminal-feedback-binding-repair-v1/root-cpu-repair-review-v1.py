"""Independent source/metadata/resource review; no tensor deserialization or tests."""
from pathlib import Path
import ast,datetime,hashlib,io,json,subprocess,time
J=Path(__file__).resolve().parent;I=J/'implementation';K=J.parent/'repair-continuation-v1';W=J.parent.parents[1]/'study_worktree'
start=time.process_time();BASE='b2775fa2008a8a88e374c43a5753f8862485af1f';HEAD='debda23a0e8eda86a3bb4f398e9596edf05b37e5'
def sha(data):return hashlib.sha256(data).hexdigest()
def ref(p):return {'path':str(p),'sha256':sha(p.read_bytes())}
def read(p):return json.loads(p.read_text())
def checked(v):
 p=Path(v['path']);assert not p.is_symlink() and p.is_file() and sha(p.read_bytes())==v['sha256'];return read(p)
def git(*args):return subprocess.check_output(['git',*args],cwd=I)
assert git('rev-parse','HEAD').decode().strip()==HEAD and not git('status','--porcelain')
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=W,text=True).strip()==BASE
delivery=read(J/'delivery-manifest-v1.json');assert delivery['commit']==HEAD and len(delivery['files'])==21
assert ref(J/'delivery-manifest-v1.json')['sha256']=='44541427d00771e5422a169ec9d348095bd4927e4307e8444c2f61925a576965'
for v in delivery['files']:
 p=Path(v['path']);assert p.parent==J and not p.is_symlink() and p.stat().st_size==v['bytes'] and sha(p.read_bytes())==v['sha256']
source=read(J/'source-manifest-v1.json');base=read(K/'source-manifest-execution-v1.json')
assert source['commit']==HEAD and base['commit']==BASE and len(source['files'])==463 and len(base['files'])==457
def blobs(commit,files):
 paths=[v['path'] for v in files];assert len(paths)==len(set(paths)) and all(not Path(p).is_absolute() and '..' not in Path(p).parts for p in paths)
 data=subprocess.check_output(['git','cat-file','--batch'],cwd=I,input=''.join(commit+':'+p+'\n' for p in paths).encode());stream=io.BytesIO(data);out={}
 for v in files:
  header=stream.readline().split();assert len(header)==3 and header[1]==b'blob'
  content=stream.read(int(header[2]));assert stream.read(1)==b'\n' and sha(content)==v['sha256'],v['path'];out[v['path']]=content
 assert not stream.read();return out
old=blobs(BASE,base['files']);new=blobs(HEAD,source['files'])
for p,data in new.items():assert (I/p).read_bytes()==data,p
for p,data in old.items():assert (W/p).read_bytes()==data,p
changed=[p for p in old if new.get(p)!=old[p]];assert changed==['scripts/qd_ed_n30_native.py']
added=set(new)-set(old);assert len(added)==6
rev=read(J/'source-reverse-v1.json');path=rev['path'];lines=new[path].decode().splitlines(keepends=True)
for h in reversed(rev['hunks']):
 assert lines[h['start']:h['end']]==h['new'];lines[h['start']:h['end']]=h['old']
assert ''.join(lines).encode()==old[path] and rev['old_sha256']==sha(old[path]) and rev['new_sha256']==sha(new[path])
def functions(data):return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(data).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
f0=functions(old[path]);f1=functions(new[path]);assert set(f1)-set(f0)=={'terminal_bool'} and [p for p in f0 if f0[p]!=f1[p]]==['audit_events']
assert (I/'docs/experiments/n30/terminal-feedback-repair/original-native-v1.py').read_bytes()==old[path]
pre='1430c93';assert git('merge-base','--is-ancestor',pre,HEAD)==b''
for name in ('input-manifest.frozen.v2.json','replay_once_v1.py','cpu-repair-scope-v2.md','root-cpu-repair-release-v2.json'):
 rel='docs/experiments/n30/terminal-feedback-repair/'+name
 assert git('show',pre+':'+rel)==(J/name).read_bytes()
replay=read(J/'real-replay-v1.json');inventory=checked(replay['input_manifest']);rr=read(J/'real-replay-resource-v1.json');tests=read(J/'cpu-run1-resource.json')
assert replay['old_source_sha256']==sha(old[path]) and replay['repaired_source_sha256']==sha(new[path])
assert replay['old_error']=={'type':'ValueError','message':'N30 native: terminal feedback binding'} and replay['repaired_error'] is None
assert replay['old_replays']==replay['repaired_replays']==1 and replay['bundle_reads']==2250 and replay['bundle_bytes']==297071656
assert inventory['bundle_count']==2250 and sum(v['bytes'] for v in inventory['bundles'])==297071656
assert all(rr['read_counts'].get(v['path'])==1 for v in inventory['bundles'])
assert tests['pytest_exit']==0 and tests['guard_clean'] and tests['denied']==[] and '21 passed' in (J/'cpu-run1.log').read_text()
assert all(v['cuda_initialized'] is False and v.get('affinity',v.get('cpu_affinity'))==[0,1] and v['threads']==2 for v in (rr,tests))
assert rr['guard_clean'] is False and len(rr['denied'])==6
assert {v['event'] for v in rr['denied']}=={'open','os.listdir','os.scandir'}
assert not any(v['path'] in rr['read_counts'] for v in rr['denied'])
assert len([v for v in rr['denied'] if v['path'].startswith(str(J)+'/')])==4
assert sum(v['path'].endswith('/third_party/lerobot/src') for v in rr['denied'])==2
totals=read(J/'resource-summary-v1.json');packaging=read(J/'packaging-resource-v1.json')
measured=inventory['inventory_cpu_seconds']+rr['cpu_seconds']+tests['process_cpu_seconds']
assert abs(measured-totals['cumulative_cpu_seconds'])<1e-9 and measured+packaging['cpu_seconds']<900
closure=read(K/'root-terminal-review-v1.json');invalid=closure['invalid_attempt'];receipt=checked(invalid['receipt']);attempt=checked(invalid['attempt_result'])
assert receipt['accepted'] is False and attempt['outcome_valid'] is False
assert checked(inventory['metadata']['receipt'])==receipt and replay['original_receipt_stays_invalid'] and not replay['scientific_acceptance'] and not replay['generic_native_replay']
triple=read(J/'first-triple-v1.json');assert [triple[x]['sequence'] for x in ('pre_reset_outcome','n30_actual_ack','step_returned')]==[3113,3114,3115]
assert all(v['global_step']==0 and v['flags']['terminated']['value'] is False for v in triple.values())
assert triple['n30_actual_ack']['flags']['terminated']=={'type':'torch.Tensor','dtype':'torch.bool','shape':[],'device':'cpu','value':False}
assert all(triple[x]['flags']['terminated']['type']=='builtins.bool' for x in ('pre_reset_outcome','step_returned'))
review={'schema':'n30-terminal-feedback-root-cpu-repair-review-v1','reviewed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'disposition':'ACCEPT_CPU_REPAIR_ONLY','source_commit':HEAD,'base_commit':BASE,'source':ref(J/'source-manifest-v1.json'),
 'source_files_rehashed':463,'base_git_blobs_rehashed':457,'unchanged_base_files':456,'modified_base_files':changed,'new_files':sorted(added),
 'reverse_proof':ref(J/'source-reverse-v1.json'),'whole_file_reverse_independently_verified':True,'other_native_functions_ast_unchanged':len(f0)-1,
 'scope':ref(J/'cpu-repair-scope-v2.md'),'release':ref(J/'root-cpu-repair-release-v2.json'),'delivery':ref(J/'delivery-manifest-v1.json'),
 'report':ref(J/'cpu-repair-report-v1.md'),'real_replay':ref(J/'real-replay-v1.json'),'real_resources':ref(J/'real-replay-resource-v1.json'),
 'test_resources':ref(J/'cpu-run1-resource.json'),'first_triple':ref(J/'first-triple-v1.json'),'closed_gpu_execution':ref(K/'root-terminal-review-v1.json'),
 'tests_passed':21,'diagnostic_and_tests_cpu_seconds':measured,'source_packaging_cpu_seconds':packaging['cpu_seconds'],
 'root_metadata_review_cpu_seconds':time.process_time()-start,'real_replay_counts':replay['repaired_counts'],
 'real_guard_clean':False,'blocked_dependency_probe_count':6,'blocked_probes':rr['denied'],
 'guard_interpretation':'Six dependency-discovery accesses were denied before content access; retained as denied, not falsely guard-clean. No CUDA initialization or extra replay. This does not falsify the bounded permitted input diagnosis.',
 'root_tensor_replay':False,'root_test_rerun':False,'original_receipt_stays_invalid':True,
 'interpretation':'Strict Python-bool/zero-dimensional CPU-bool equivalence fixes auditor representation error, while mismatched values and unsupported representations still fail. All online algorithm/decision bytes unchanged; offline N30-only audit establishes repair, not scientific acceptance.',
 'source_adopted_to_owning_worktree':False,'gpu_release':False,'new_retry_authorized':False,'validation_authorized':False,'formal_authorized':False,'goal_status':'TARGET_NOT_MET'}
with (J/'root-cpu-repair-review-v1.json').open('x') as f:json.dump(review,f,indent=2);f.write('\n')
print(json.dumps({k:review[k] for k in ('disposition','source_commit','source_files_rehashed','tests_passed','diagnostic_and_tests_cpu_seconds','real_guard_clean','blocked_dependency_probe_count','root_metadata_review_cpu_seconds')}))
