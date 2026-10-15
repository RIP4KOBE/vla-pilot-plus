from pathlib import Path
import os,json,hashlib,subprocess,difflib,time,ast
J=Path(__file__).resolve().parent;I=J/'implementation';os.sched_setaffinity(0,{0,1});start=time.process_time()
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='2'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return {'path':str(p),'sha256':sha(p)}
def canonical(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def save(name,value):
 p=J/name
 with p.open('x') as f:f.write(json.dumps(value,indent=2,allow_nan=False)+'\n')
 return ref(p)
base_path=J.parent/'repair-continuation-v1/source-manifest-execution-v1.json';assert sha(base_path)=='5ecec50164559cd96f86140c481d78d41120be9a1a3da3802fc7774d7912c01f';base=json.loads(base_path.read_text())
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=I,text=True).strip();assert not subprocess.check_output(['git','status','--porcelain'],cwd=I)
paths={x['path'] for x in base['files']}|{'tests/test_n30_terminal_feedback_repair.py'}
paths.update(str(p.relative_to(I)) for p in (I/'docs/experiments/n30/terminal-feedback-repair').iterdir() if p.is_file())
files=[]
for p in sorted(paths):
 data=(I/p).read_bytes();assert data==subprocess.check_output(['git','show',commit+':'+p],cwd=I)
 files.append({'path':p,'sha256':hashlib.sha256(data).hexdigest()})
source={'commit':commit,'files':files,'sha256':canonical(files)};save('source-manifest-v1.json',source)
changed=[x['path'] for x in base['files'] if sha(I/x['path'])!=x['sha256']];assert changed==['scripts/qd_ed_n30_native.py']
name=changed[0];old=subprocess.check_output(['git','show',base['commit']+':'+name],cwd=I);new=(I/name).read_bytes()
a=old.decode().splitlines(keepends=True);z=new.decode().splitlines(keepends=True)
hunks=[{'start':j,'end':jj,'old':a[i:ii],'new':z[j:jj]} for tag,i,ii,j,jj in difflib.SequenceMatcher(None,a,z,autojunk=False).get_opcodes() if tag!='equal']
restored=z.copy()
for h in reversed(hunks):assert restored[h['start']:h['end']]==h['new'];restored[h['start']:h['end']]=h['old']
assert ''.join(restored).encode()==old
save('source-reverse-v1.json',{'base_commit':base['commit'],'commit':commit,'path':name,'old_sha256':hashlib.sha256(old).hexdigest(),'new_sha256':sha(I/name),'hunks':hunks})
(K:=J/'source-diff-v1.patch').write_bytes(subprocess.check_output(['git','diff',base['commit'],commit,'--'],cwd=I))
oldtree=ast.parse(old);newtree=ast.parse(new);oldf={n.name:ast.dump(n,include_attributes=False) for n in oldtree.body if isinstance(n,ast.FunctionDef)};newf={n.name:ast.dump(n,include_attributes=False) for n in newtree.body if isinstance(n,ast.FunctionDef)}
assert set(newf)-set(oldf)=={'terminal_bool'} and [k for k in oldf if oldf[k]!=newf[k]]==['audit_events']
save('source-byte-review-v1.json',{'base_source':ref(base_path),'commit':commit,'total_source_files':len(files),'base_files':len(base['files']),
 'unchanged_base_files':len(base['files'])-1,'only_modified_base_file':name,'exact_reverse_verified':True,'all_git_blobs_verified':True,
 'new_function':'terminal_bool','modified_function':'audit_events','other_native_functions_ast_unchanged':len(oldf)-1,
 'new_files':sorted(paths-{x['path'] for x in base['files']})})
replay=json.loads((J/'real-replay-v1.json').read_text());rr=json.loads((J/'real-replay-resource-v1.json').read_text());tr=json.loads((J/'cpu-run1-resource.json').read_text());inputs=json.loads((J/'input-manifest.frozen.v2.json').read_text())
assert replay['old_replays']==replay['repaired_replays']==1 and replay['bundle_reads']==2250 and replay['bundle_bytes']==297071656 and replay['repaired_error'] is None
assert replay['repaired_source_sha256']==sha(I/name)
assert all(rr['read_counts'][x['path']]==1 for x in inputs['bundles'])
assert len(rr['denied'])==6 and not rr['guard_clean'] and tr['guard_clean'] and tr['pytest_exit']==0
save('resource-summary-v1.json',{'schema':'n30-terminal-feedback-cpu-resources-v1','inventory_cpu_seconds':inputs['inventory_cpu_seconds'],
 'real_replay_cpu_seconds':rr['cpu_seconds'],'synthetic_test_cpu_seconds':tr['process_cpu_seconds'],
 'cumulative_cpu_seconds':inputs['inventory_cpu_seconds']+rr['cpu_seconds']+tr['process_cpu_seconds'],'limit_cpu_seconds':900,
 'real_bundle_loads':2250,'real_bundle_bytes':297071656,'old_replays':1,'repaired_replays':1,'synthetic_tests_passed':21,'failed_test_invocations':0,
 'synthetic_guard_clean':True,'real_replay_guard_clean':False,'blocked_import_probes':rr['denied'],
 'blocked_probe_access_succeeded':False,'cuda_initialized_in_both_processes':False,'affinity':[0,1],'threads':2,
 'real_replay_peak_rss_kib':rr['peak_rss_kib'],'synthetic_peak_rss_kib':tr['peak_rss_kib'],'rlimit_as_bytes':rr['rlimit_as_bytes'],
 'immutable_original_receipt':True,'scientific_acceptance':False})
save('packaging-resource-v1.json',{'mode':'stdlib/Git byte verification; no experiment imports','cpu_seconds':time.process_time()-start,'affinity':[0,1]})
for p in ('source-manifest-v1.json','source-reverse-v1.json','resource-summary-v1.json'):print(p,sha(J/p))
