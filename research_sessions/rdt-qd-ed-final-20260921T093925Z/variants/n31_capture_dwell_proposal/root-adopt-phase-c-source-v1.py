from pathlib import Path
import json,hashlib,subprocess,datetime,fcntl,os,yaml
P=Path(__file__).resolve().parent;I=P/'implementation';W=P.parents[1]/'study_worktree'
def ref(p):
 p=Path(p);b=p.read_bytes();return {'path':str(p),'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}
def git(*args):return subprocess.check_output(['git',*args],cwd=W)
D=json.loads((P/'delivery-manifest-phase-c-v1.json').read_text());S=json.loads((P/'source-manifest-execution-v1.json').read_text())
for x in D['files']:assert ref(x['path'])==x,x['path']
B=json.loads((P/'root-phase-c-source-bytes-review-v1.json').read_text());T=json.loads((P/'root-phase-c-test-resource-review-v1.json').read_text())
assert D['commit']==S['commit']==B['source_commit']==T['source_commit']=='7428ce8a51f76c5f641537be9a7614631d82b0d9'
assert S['files']==B['complete_source_files'] and T['final_distinct_passing_cases']==D['test_passes']==121
assert D['final_guard_clean'] is True and D['gpu_authorized'] is False and D['budget_adopted'] is False
fds=[]
try:
 for path in ('data/qd-ed-runner.lock','data/qd-ed-state.lock'):
  fd=open(W/path,'a+');fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);fds.append(fd)
 state=yaml.safe_load((W/'research-state.yaml').read_text())
 assert state['resource_isolation']['status']=='ACTIVE' and state['resource_isolation']['validation_status']=='PASS'
 assert state['current_owned_workers']==[] and state['active_plan'] is None and state['active_controller'] is None
 assert state['budget']['dispatched']==403 and state['budget']['gpu_hours_consumed']==53.80872756284531 and state['budget']['running']==0
 assert git('rev-parse','HEAD').decode().strip()==B['base_commit']
 assert git('diff','--cached','--name-only')==b''
 dirty=git('diff','--name-only','HEAD').decode().splitlines()
 assert set(dirty).isdisjoint({v['path'] for v in S['files']})
 before={p:ref(W/p)['sha256'] for p in dirty}
 result=git('merge','--ff-only','--no-edit',S['commit']).decode()
 assert git('rev-parse','HEAD').decode().strip()==S['commit']
 assert git('diff','--name-only','HEAD').decode().splitlines()==dirty
 assert before=={p:ref(W/p)['sha256'] for p in dirty}
 for row in S['files']:assert ref(W/row['path'])['sha256']==row['sha256'],row['path']
 out={'schema':'n31-root-source-adoption-v1','recorded_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_commit':S['commit'],'previous_commit':B['base_commit'],'worktree':str(W),'lexical_worktree_retained':state['worktree'],'delivery':ref(P/'delivery-manifest-phase-c-v1.json'),'source':ref(P/'source-manifest-execution-v1.json'),'source_review':ref(P/'root-phase-c-source-bytes-review-v1.json'),'test_review':ref(P/'root-phase-c-test-resource-review-v1.json'),'delivery_entries_verified':len(D['files']),'source_files_rehashed_in_owning_worktree':len(S['files']),'operational_file_hashes_before_and_after':before,'all_operational_files_preserved':True,'budget_changed':False,'gpu_authorized':False,'target_achieved':False,'merge_output':result}
 path=P/'root-source-adoption-v1.json'
 with path.open('x') as f:json.dump(out,f,indent=2);f.write('\n')
 print(json.dumps({'adoption':ref(path),'commit':S['commit'],'source_files':len(S['files']),'operational_files_preserved':len(before)}))
finally:
 for fd in reversed(fds):fd.close()

