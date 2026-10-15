#!/usr/bin/env python3
"""Exactly one finite continuation; any newly invalid outcome stops without retry."""
import argparse
from pathlib import Path
import signal
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts import qd_ed_final_runner as r,qd_ed_n23_worker as w,qd_ed_n27_supervise as old
from scripts import qd_ed_n27_cont_contract as c,qd_ed_n27_cont_report as report

def one_attempt(path,plan,row):
    seen={x['attempt_id'] for x in r.read_events(ROOT/'data/attempt-ledger.jsonl')}
    with c.supervised_scope(plan,ROOT,row['episode_key']):
        try:
            result=r.run_plan(path,split='dev',iteration=c.COHORT,episode_keys=[row['episode_key']],root=ROOT)
            w.require(len(result)==1,'one worker result required');return result[0]
        except r.GateError:
            finals=[x for x in r.read_events(ROOT/'data/attempt-ledger.jsonl') if x['attempt_id'] not in seen
                and x['event'] in r.TERMINAL and x.get('identity',{}).get('iteration')==c.COHORT and x['episode_key']==row['episode_key']]
            if len(finals)!=1:raise
            return finals[0]

def release_check(path,plan_path,plan):
    w.require(Path(path).resolve()==(c.RUN_DIR/'execution-release-v1.json').resolve(),'exact release path')
    expected={'schema':'n27-hydra-execution-release-v1','plan':c.ref(plan_path),'source_commit':plan['source_commit'],'cohort_id':c.COHORT,
        'authority':c.ref(c.AUTHORITY),'seal':c.ref(c.SEAL),'episode_keys':[x['episode_key'] for x in plan['episodes']],
        'limits':c.LIMITS,'one_launch':True,'physical_gpu':7,'validation_authorized':False,'formal_authorized':False}
    w.require(c.h.read(c.ref(path))==expected,'root executable release missing/different')

def execute(path,plan,status_path):
    w.require(Path(status_path).resolve()==(c.RUN_DIR/'execution/supervisor-status-v1.json').resolve(),'exact controller output root')
    Path(status_path).parent.mkdir(parents=True,exist_ok=True)
    completed=[];attempts=[];outcomes=[];wins={a:0 for a in c.ARMS};native={a:{} for a in c.ARMS}
    def write(phase,**extra):
        r.durable_json(status_path,{'schema':'n27-hydra-supervisor-status-v1','status':phase,'cohort_id':c.COHORT,
            'plan':c.ref(path),'source_commit':plan['source_commit'],'prefix_seal':c.ref(c.SEAL),'completed_keys':list(completed),
            'attempts':list(attempts),'outcomes':list(outcomes),'successes':dict(wins),'dev_gate_promoted':False,'protected_authorized':False,**extra})
    try:
        write('started')
        for row in plan['episodes']:
            old.device_check();final=one_attempt(path,plan,row)
            attempts.append({'attempt_id':final['attempt_id'],'episode_key':row['episode_key'],'profile':row['profile'],'terminal':final});write('attempt_journaled')
            w.require(final.get('outcome_valid') is True,'new invalidity closes continuation; no retry permitted')
            accepted=c.accepted_cell(plan,row,r.read_events(ROOT/'data/attempt-ledger.jsonl'),ROOT,vars(r));w.require(accepted==final,'journal/result differs')
            counts,_=c.native.from_output(row['profile'],final['output_dir'],c.read_worker_report(final['output_dir'],vars(r)),final.get('guided_chunks'))
            for k,v in counts.items():native[row['profile']][k]=native[row['profile']].get(k,0)+v
            outcomes.append({'episode_key':row['episode_key'],'attempt_id':final['attempt_id'],'success':final['success']})
            wins[row['profile']]+=int(final['success']);completed.append(row['episode_key']);write('cell_audited')
        promoted=wins['N27']>=2 and wins['N27']>=max(wins[a] for a in c.ARMS[:-1]) and wins['N27']>wins['N26']
        promoted=promoted and native['N27'].get('guided_decisions',0)>0 and native['N27'].get('parent_rounds_verified',0)>0
        write('completed_all_sixteen_audited',dev_gate_promoted=promoted)
    except BaseException as exc:
        try:write('interrupted' if isinstance(exc,(KeyboardInterrupt,SystemExit)) else 'failed',failure_class=type(exc).__name__,failure=str(exc))
        finally:raise
    finally:report.write_terminal(path,plan,status_path,ROOT,vars(r))

def launch(path,release,status):
    plan,_,_=r.validate_plan(path,root=ROOT);release_check(release,path,plan)
    w.require(Path(status).resolve()==(c.RUN_DIR/'execution/supervisor-status-v1.json').resolve(),'exact status path')
    (c.RUN_DIR/'execution').mkdir(parents=True,exist_ok=True)
    with r.locked(c.RUN_DIR/'execution/supervisor.lock',nonblocking=True):
        w.require(not Path(status).exists() and not (c.RUN_DIR/'result-v1.json').exists()
            and not (c.RUN_DIR/'execution/controller-process-v1.json').exists(),'no controller restart')
        with r.locked(ROOT/'data/qd-ed-runner.lock',nonblocking=True):
            events=r.read_events(ROOT/'data/attempt-ledger.jsonl');w.require(not c.local_events(events),'prior reservation consumes launch')
            c.full_capacity(r.read_state(ROOT/'research-state.yaml'),events,r.read_events(ROOT/'data/gpu-healthcheck-ledger.jsonl'),vars(r))
        w.atomic_json(c.RUN_DIR/'execution/controller-process-v1.json',{'schema':'n27-hydra-controller-process-v1','process':w.process_identity(),
            'plan':c.ref(path),'release':c.ref(release),'source_commit':plan['source_commit']})
        execute(path,plan,status)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('plan','release','status'):parser.add_argument('--'+key,type=Path,required=True)
    a=parser.parse_args();launch(a.plan,a.release,a.status)
if __name__=='__main__':
    signal.signal(signal.SIGTERM,lambda *_:(_ for _ in ()).throw(KeyboardInterrupt()))
    main()
