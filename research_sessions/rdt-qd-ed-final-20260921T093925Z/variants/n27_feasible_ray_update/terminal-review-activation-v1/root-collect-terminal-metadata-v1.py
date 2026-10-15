"""Root operational closure collector. No GPU, model, API or native payload reads."""
import hashlib, json, os, sys, time
from pathlib import Path
A=Path(__file__).resolve().parent
N=A.parent
W=N.parents[1]/'study_worktree'
H=N/'terminal-review-preparation-v1'
COMMIT='095cfeecd6af55477d2529441c307ab712e8a8da'
COHORT='N27_FEASIBLE_RAY_SCREEN_20261001'
CAP=16*1024*1024
def bounded(p):
    p=Path(p);assert p.is_file() and not p.is_symlink() and p.stat().st_size<=CAP
    with p.open('rb') as f:b=f.read(CAP+1)
    assert len(b)<=CAP
    return b
def sha(p):return hashlib.sha256(bounded(p)).hexdigest()
def ref(p):return {'path':str(Path(p).resolve()),'sha256':sha(p)}
def read(p):return json.loads(bounded(p))
def byref(r):
    assert set(r)=={'path','sha256'} and sha(r['path'])==r['sha256']
    return read(r['path'])
def save(name,value):
    p=A/name
    with p.open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    return ref(p)
def ident(p):return {k:p[k] for k in ('pid','proc_start_ticks','boot_id')}
def alive(p):
    if p['boot_id']!=Path('/proc/sys/kernel/random/boot_id').read_text().strip():return False
    q=Path('/proc')/str(p['pid'])/'stat'
    try:return q.read_text().rsplit(')',1)[1].split()[19]==p['proc_start_ticks']
    except FileNotFoundError:return False
def group_alive(p):
    if p['boot_id']!=Path('/proc/sys/kernel/random/boot_id').read_text().strip():return False
    for q in Path('/proc').iterdir():
        if not q.name.isdigit():continue
        try:fields=(q/'stat').read_text().rsplit(')',1)[1].split()
        except (FileNotFoundError,ProcessLookupError,PermissionError):continue
        if int(fields[2])==p['pid']:return True
    return False

def main():
    launch=read(N/'root-controller-launch-v1.json')
    assert not alive(launch['process']), 'controller still alive'
    review=read(H/'root-cpu-review-v1.json');assert review['decision']=='ACCEPT_BOUNDED_METADATA_READER'
    delivery=byref(review['delivery'])
    for x in delivery['files']:assert sha(x['path'])==x['sha256']
    sys.path[:0]=[str(W),str(W/'scripts'),str(H)]
    from scripts import qd_ed_final_runner as r, qd_ed_n27_contract as c
    from bounded_json_v1 import canonical
    records={}
    def include(path,role):
        p=Path(path).resolve();assert p.suffix=='.json' and 'decision_evidence' not in p.parts
        exists=p.is_file();b=bounded(p) if exists else b''
        item={'role':role,'path':str(p),'present':exists,'sha256':hashlib.sha256(b).hexdigest() if exists else None,'bytes':len(b)}
        assert str(p) not in records
        records[str(p)]=item
        assert len(records)<=120 and sum(x['bytes'] for x in records.values())<=128*1024*1024
        return {k:item[k] for k in ('path','sha256')}
    def add(q,role):
        v=include(q['path'],role);assert v==q;return v
    def project(path,events,role):
        return {'schema':f'n27-current-terminal-{role}-projection-v1','cohort_id':COHORT,'events':events,
          'event_count':len(events),'all_matching_events':True,'source_ledger':ref(path),
          'collector':ref(__file__),'collected_at':time.time()}
    with r.locked(N/'execution/supervisor.lock',nonblocking=True),r.locked(W/'data/qd-ed-runner.lock',nonblocking=True),r.locked(W/'data/qd-ed-state.lock',nonblocking=True):
        assert not alive(launch['process'])
        plan_path=N/'plan.frozen.v1.gpu7.json'
        plan,profiles,runtime=r.validate_plan(plan_path,root=W)
        assert plan['source_commit']==COMMIT and len(plan['code_files'])==345
        jpath=W/'data/attempt-ledger.jsonl';hpath=W/'data/gpu-healthcheck-ledger.jsonl'
        all_events=r.read_events(jpath);all_resources=r.read_events(hpath)
        own=[e for e in all_events if e.get('identity',{}).get('iteration')==COHORT]
        assert len({e['attempt_id'] for e in own})==4
        assert all(e.get('retry_of') is None for e in own)
        sr=byref(plan['n27_cohort']['final_review']);proof=byref(sr['backend_proof']);pp=byref(proof['plan'])
        health=[e for e in all_resources if e.get('resource_id')==pp['resource_id'] or e.get('kind')=='n27_tensor_arithmetic_v1']
        source=read(N/'source-manifest.v1.json')
        assert source['files']==plan['code_files'] and source['commit']==COMMIT
        snapshot=N/'execution/terminal-ledger-v1.json';assert read(snapshot)==own
        refs={'plan':include(plan_path,'plan'),'source':include(N/'source-manifest.v1.json','source'),
          'result':include(N/'result-v1.json','result'),'status':include(N/'execution/supervisor-status-v1.json','status'),
          'proof':add(sr['backend_proof'],'proof'),'bridge':add(sr['source_bridge'],'bridge'),
          'source_review':add(plan['n27_cohort']['final_review'],'source_review'),
          'authority':add(plan['n27_cohort']['authority'],'authority'),'release':include(N/'execution-release-v1.json','release')}
        for key in ('plan','report','process','terminal'):refs['proof_'+key]=add(proof[key],'proof_'+key)
        hashes={v['path']:v['sha256'] for v in source['files']}
        controller={'schema':'n27-root-controller-process-v1','source_commit':COMMIT,'plan':refs['plan'],
          'release':refs['release'],'physical_gpu':7,'one_launch':True,'wrapper':ref(N/'root-controller-launch-v1.json'),
          'entrypoint':{'path':str(W/'scripts/qd_ed_n27_supervise.py'),'sha256':hashes['scripts/qd_ed_n27_supervise.py']},
          'process':ident(launch['process'])}
        refs['controller']=add(save('controller-process-v1.json',controller),'controller')
        journal=project(jpath,own,'journal');journal.update(snapshot=ref(snapshot),snapshot_events_sha256=canonical(own))
        refs['journal']=add(save('current-journal-projection-v1.json',journal),'journal')
        refs['resources']=add(save('current-resource-projection-v1.json',project(hpath,health,'resource')),'resources')
        templates=[{'episode_key':row['episode_key'],'argv':r.build_command(plan,profiles,runtime,row,'__N27_REVIEW_ATTEMPT__')[0]} for row in plan['episodes']]
        pre={'schema':'n27-terminal-prerequisite-attestation-v1','bindings':{k:refs[k] for k in ('plan','source','proof','bridge','source_review','authority','release')},
          'runtime':sr['runtime'],'source_commit':COMMIT,'source_files_verified':345,'operations':['validate_plan','build_command'],
          'all_prerequisites_passed':True,'historical_proof_lineage_verified':True,'model_api_sim_calls':0,
          'collector':ref(__file__),'command_templates':templates,'hydra_composition_passed':False,
          'known_startup_fault':'N27 missing Hydra diversity_update_mode schema key; prerequisite here means frozen plan integrity, not executable success'}
        refs['precheck']=add(save('prerequisite-attestation-v1.json',pre),'precheck')
        groups={}
        for e in own:groups.setdefault(e['attempt_id'],[]).append(e)
        processes={'controller':ident(controller['process']),'proof':ident(byref(proof['process']))};bindings=[]
        names={'terminal':'attempt-result.json','context':'n23-worker-context.json','process':'process.json','receipt':'eds_eval/in-worker-audit-receipt.json','audit':'eds_eval/decision-evidence-audit.json'}
        for aid,events in groups.items():
            folder=Path(events[0]['output_dir']).resolve();assert folder==Path(plan['artifact_root'])/'attempts'/aid
            fields={role:include(folder/name,role) for role,name in names.items()}
            process=byref(fields['process']) if fields['process']['sha256'] else None
            processes[aid]=ident(process) if process else None
            bindings.append({'attempt_id':aid,'refs':fields})
        checks={}
        for key,pid in processes.items():
            checks[key]={'identity':pid,'same_identity_alive':alive(pid) if pid else None,'group_alive':group_alive(pid) if pid else None}
            if pid:assert checks[key]['same_identity_alive'] is False and checks[key]['group_alive'] is False
        assert [e for e in r.read_events(jpath) if e.get('identity',{}).get('iteration')==COHORT]==own
        assert [e for e in r.read_events(hpath) if e.get('resource_id')==pp['resource_id'] or e.get('kind')=='n27_tensor_arithmetic_v1']==health
        cleanup={'schema':'n27-root-cleanup-attestation-v1','plan':refs['plan'],'source':refs['source'],'controller':refs['controller'],
          'journal':refs['journal'],'resources':refs['resources'],'process_identities':processes,'checks':checks,
          'collector':ref(__file__),'collected_at':time.time(),'locks_held':True,'current_matching_subsets_equal':True}
        refs['cleanup']=add(save('cleanup-attestation-v1.json',cleanup),'cleanup')
        snap=r.budget_snapshot(all_events,all_resources)
        save('budget-at-closure-v1.json',snap)
        output=save('metadata-input-draft-v1.json',{'schema':'n27-terminal-metadata-input-v1','root_authorized':False,'executable':False,
          'refs':refs,'attempts':bindings,'files':list(records.values())})
        print(json.dumps({'draft':output,'files':len(records),'bytes':sum(x['bytes'] for x in records.values()),'attempts':len(bindings),'known_processes_clean':len(checks),'gpu_api_sim_calls':0}))
if __name__=='__main__':main()
