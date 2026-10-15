#!/usr/bin/env python3
"""One successor launch, one named repeat; any new invalidity closes immediately."""
import argparse
from pathlib import Path
import signal
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts import qd_ed_final_runner as r,qd_ed_n23_worker as w,qd_ed_n25_supervise as old_supervisor
from scripts import qd_ed_n25_cont_contract as c,qd_ed_n25_cont_report as report


def one_attempt(path,plan,row):
    seen={x['attempt_id'] for x in r.read_events(ROOT/'data/attempt-ledger.jsonl')}
    with c.supervised_scope(plan,ROOT,row['episode_key']):
        try:
            values=r.run_plan(path,split='dev',iteration=c.COHORT,episode_keys=[row['episode_key']],root=ROOT)
            w.require(len(values)==1,'single successor worker result required');return values[0]
        except r.GateError:
            finals=[x for x in r.read_events(ROOT/'data/attempt-ledger.jsonl') if x['attempt_id'] not in seen
                and x['event'] in r.TERMINAL and x.get('identity',{}).get('iteration')==c.COHORT and x['episode_key']==row['episode_key']]
            if len(finals)!=1:raise
            return finals[0]


def release_check(path,plan_path,plan):
    w.require(Path(path).resolve()==(c.RUN_DIR/'execution-release-v1.json').resolve(),'successor release path')
    expected={'schema':'n25-continuation-execution-release-v1','plan':c.ref(plan_path),'source_commit':plan['source_commit'],
        'cohort_id':c.COHORT,'authority':c.ref(c.AUTHORITY),'seal':c.ref(c.SEAL),'episode_keys':[x['episode_key'] for x in plan['episodes']],
        'limits':c.LIMITS,'physical_gpu':7,'one_launch':True,'validation_authorized':False,'formal_authorized':False}
    w.require(w.read_ref(c.ref(path))==expected,'exact external successor release required')


def execute(path,plan,status_path):
    w.require(Path(status_path).resolve()==(c.RUN_DIR/'execution/supervisor-status-v1.json').resolve(),'split-root status differs')
    Path(status_path).parent.mkdir(parents=True,exist_ok=True)
    seal=c.history();completed=[];attempts=[];outcomes=[];wins={a:seal['counts'][a]['success'] for a in c.ARMS};native_totals={a:dict(seal['native'][a]) for a in c.ARMS}
    def write(phase,**kw):
        r.durable_json(status_path,{'schema':'n25-continuation-supervisor-status-v1','status':phase,'cohort_id':c.COHORT,
            'plan':c.ref(path),'source_commit':plan['source_commit'],'prefix_seal':c.ref(c.SEAL),'completed_keys':list(completed),
            'attempts':attempts,'outcomes':outcomes,'counts_success':wins,'dev_gate_promoted':False,'protected_authorized':False,**kw})
    try:
        write('started')
        for row in plan['episodes']:
            old_supervisor.device_check();final=one_attempt(path,plan,row)
            attempts.append(final);write('attempt_journaled')
            w.require(final.get('outcome_valid') is True,'any new invalidity closes; no further recovery')
            events=r.read_events(ROOT/'data/attempt-ledger.jsonl');accepted=c.accepted_cell({**plan,'_path':str(path)},row,events,ROOT,vars(r))
            w.require(accepted==final,'journal differs from result')
            counts,_=c.native.from_output(row['profile'],final['output_dir'],c.old.read_worker_report(final['output_dir'],vars(r)),final.get('guided_chunks'))
            for k,v in counts.items():native_totals[row['profile']][k]=native_totals[row['profile']].get(k,0)+v
            outcomes.append({'episode_key':row['episode_key'],'attempt_id':final['attempt_id'],'success':final['success']})
            wins[row['profile']]+=int(final['success'] is True);completed.append(row['episode_key']);write('cell_audited')
            n=18+len(completed)
            if n%4==0 and wins['N25']+10-n//4<5:write('rejected_numeric_futility');return
        promote=wins['N25']>=5 and wins['N25']>=max(wins[a] for a in c.ARMS[:-1]) and native_totals['N25'].get('guided_decisions',0)>0 and native_totals['N25'].get('parent_rounds_verified',0)>0
        write('completed_all_forty_audited',dev_gate_promoted=promote)
    except BaseException as exc:
        try:write('interrupted' if isinstance(exc,(KeyboardInterrupt,SystemExit)) else 'failed',failure_class=type(exc).__name__,failure=str(exc))
        finally:raise
    finally:report.write_terminal(path,plan,status_path,ROOT,vars(r))


def launch(path,release,status):
    plan,manifest,runtime=r.validate_plan(path,root=ROOT);release_check(release,path,plan)
    w.require(Path(status).resolve()==(c.RUN_DIR/'execution/supervisor-status-v1.json').resolve(),'exact status location')
    with r.locked(c.RUN_DIR/'execution/supervisor.lock',nonblocking=True):
        w.require(not Path(status).exists() and not (c.RUN_DIR/'result-v1.json').exists(),'single launch, never resume')
        with r.locked(ROOT/'data/qd-ed-runner.lock',nonblocking=True):
            c.history(cleanup=True);events=r.read_events(ROOT/'data/attempt-ledger.jsonl')
            w.require(not c.local_events(events),'reservation already consumed opportunity')
            c.full_capacity(r.read_state(ROOT/'research-state.yaml'),events,r.read_events(ROOT/'data/gpu-healthcheck-ledger.jsonl'),vars(r))
        w.atomic_json(c.RUN_DIR/'execution/controller-process-v1.json',{'schema':'n25-continuation-controller-process-v1',
            'process':w.process_identity(),'plan':c.ref(path),'release':c.ref(release),'source_commit':plan['source_commit']})
        execute(path,plan,status)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--release',type=Path,required=True);p.add_argument('--status',type=Path,required=True);a=p.parse_args();launch(a.plan,a.release,a.status)
if __name__=='__main__':
    signal.signal(signal.SIGTERM,lambda *_:(_ for _ in ()).throw(KeyboardInterrupt()))
    main()
