#!/usr/bin/env python3
"""One non-resumable N30 cohort; original single-worker runner owns every charge."""
import argparse
from pathlib import Path
import signal
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts import qd_ed_final_runner as r
from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n30_contract as c
from scripts import qd_ed_n30_native as native
from scripts import qd_ed_n30_report as report


def release_check(path,plan_path,plan):
    w.require(Path(path).resolve()==(c.RUN_DIR/'execution-release-v1.json').resolve(),'N30 release path differs')
    w.require(w.read_ref(c.ref(path))=={'schema':'n30-dev-execution-release-v1','plan':c.ref(plan_path),
        'source_commit':plan['source_commit'],'cohort_id':c.COHORT,'episode_keys':[x['episode_key'] for x in plan['episodes']],
        'authority':plan['n30_cohort']['authority'],'physical_gpu':7,'limits':c.LIMITS,
        'validation_authorized':False,'formal_authorized':False},'N30 external release differs')


def one_attempt(plan_path,plan,row):
    before=r.read_events(ROOT/'data/attempt-ledger.jsonl');seen={e['attempt_id'] for e in before}
    with c.supervised_scope(plan,ROOT,row['episode_key']):
        try:
            result=r.run_plan(plan_path,split='dev',iteration=c.COHORT,episode_keys=[row['episode_key']],root=ROOT)
            w.require(len(result)==1,'N30 one-worker result missing');return result[0]
        except r.GateError:
            finals=[e for e in r.read_events(ROOT/'data/attempt-ledger.jsonl') if e['attempt_id'] not in seen
                and e['event'] in r.TERMINAL and e.get('identity',{}).get('iteration')==c.COHORT and e.get('episode_key')==row['episode_key']]
            if len(finals)!=1:raise
            return finals[0]


def device_check():
    # Only the root-released CLI reaches this; CPU tests replace it without CUDA imports.
    from scripts import qd_ed_available_gpu_queue as queue
    devices=queue.inventory();w.require(7 in devices and devices[7]['uuid']==c.GPU7_UUID,'N30 GPU7 identity differs')
    queue.reservation_admission(devices[7]);r.gpu_admission(physical_gpu=7,expected_uuid=c.GPU7_UUID)


def execute(plan_path,plan,manifest,runtime,status_path):
    attempts=[];outcomes=[];completed=[];successes={a:0 for a in c.ARMS};native_totals={a:{} for a in c.ARMS};auxiliary={a:{} for a in c.ARMS}
    def write(phase,**extra):
        r.durable_json(status_path,{'schema':'n30-dev-supervisor-status-v1','status':phase,'cohort_id':c.COHORT,
            'source_commit':plan['source_commit'],'plan':c.ref(plan_path),'completed_keys':list(completed),
            'attempts':attempts,'outcomes':outcomes,'successes':successes,'native':native_totals,'auxiliary':auxiliary,
            'dev_gate_promoted':False,'protected_authorized':False,**report.summary(outcomes,attempts),**extra})
    def record(final,row):
        attempts.append({'attempt_id':final['attempt_id'],'episode_key':row['episode_key'],'profile':row['profile'],'terminal':final})
        write('attempt_journaled')
    write('started')
    try:
        for row in plan['episodes']:
            device_check();result=one_attempt(plan_path,plan,row);record(result,row)
            w.require(result.get('outcome_valid') is True,'N30 primary invalid; no retry; costs retained')
            events=r.read_events(ROOT/'data/attempt-ledger.jsonl')
            final=c.accepted_cell(plan,row,events,ROOT,vars(r))
            w.require(final['attempt_id']==result['attempt_id'],'N30 first-valid selection differs')
            counts,aux=native.from_output(row['profile'],final['output_dir'],c.read_worker_report(final['output_dir'],vars(r)),final.get('guided_chunks'))
            for k,v in counts.items():native_totals[row['profile']][k]=native_totals[row['profile']].get(k,0)+v
            for k,v in aux.items():auxiliary[row['profile']][k]=auxiliary[row['profile']].get(k,0)+v
            outcomes.append({'episode_key':row['episode_key'],'task_id':row['task_id'],'profile':row['profile'],
                'success':final['success'],'attempt_id':final['attempt_id'],'recovered':bool(final.get('retry_of'))})
            successes[row['profile']]+=int(final['success'] is True);completed.append(row['episode_key']);write('cell_audited')
            if report.futile(outcomes):
                write('rejected_numeric_futility');return
        promoted=(successes['N30']>=3 and successes['N30']>=max(successes[a] for a in ('C0','Q0'))
            and native_totals['N30'].get('guided_decisions',0)>0 and native_totals['N30'].get('parent_rounds_verified',0)>0 and native_totals['N30'].get('active_insertions_verified',0)>0)
        write('completed_all_twelve_audited',dev_gate_promoted=promoted)
    except c.ResourceBudgetIncomplete as exc:
        write('resource_budget_incomplete',failure_class=type(exc).__name__,failure=str(exc));return
    except BaseException as exc:
        write('interrupted' if isinstance(exc,(KeyboardInterrupt,SystemExit)) else 'failed',failure_class=type(exc).__name__,failure=str(exc));raise
    finally:
        # CPU receipt consumption, never a second CUDA audit; includes journaled failures not returned by run_plan.
        report.write_terminal(plan_path,plan,status_path,ROOT,vars(r))


def launch(plan_path,release,status_path):
    plan,manifest,runtime=r.validate_plan(plan_path,root=ROOT);release_check(release,plan_path,plan)
    w.require(Path(status_path).resolve()==(c.RUN_DIR/'execution/supervisor-status-v1.json').resolve(),'N30 exact status path differs')
    (c.RUN_DIR/'execution').mkdir(parents=True,exist_ok=True)
    with r.locked(c.RUN_DIR/'execution/supervisor.lock',nonblocking=True):
        w.require(not Path(status_path).exists() and not (c.RUN_DIR/'result-v1.json').exists(),'N30 no automatic controller resume')
        with r.locked(ROOT/'data/qd-ed-runner.lock',nonblocking=True):
            events=r.read_events(ROOT/'data/attempt-ledger.jsonl')
            w.require(not any(e.get('identity',{}).get('iteration') in {c.COHORT} for e in events),'N30 prior reservation forbids restart')
            c.full_capacity(r.read_state(ROOT/'research-state.yaml'),events,r.read_events(ROOT/'data/gpu-healthcheck-ledger.jsonl'),vars(r))
        execute(plan_path,plan,manifest,runtime,status_path)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--release',type=Path,required=True);p.add_argument('--status',type=Path,required=True);args=p.parse_args()
    launch(args.plan,args.release,args.status)


if __name__=='__main__':
    signal.signal(signal.SIGTERM,lambda *_:(_ for _ in ()).throw(KeyboardInterrupt()))
    main()
