#!/usr/bin/env python3
"""One conditional protected cohort; only aggregate disposition is printed."""
import argparse
import json
from pathlib import Path
import signal
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts import qd_ed_final_runner as r
from scripts import qd_ed_n24_validation_contract as c
from scripts import qd_ed_n24_validation_identity as identity
from scripts import qd_ed_n24_validation_recovery as recovery
from scripts import qd_ed_n24_validation_report as reporting
from scripts import qd_ed_n24_supervise as dev_supervisor
from scripts import qd_ed_n23_worker as w


def release_check(path,plan_path,plan):
    c.require(Path(path).resolve()==(c.RUN_DIR/'validation-execution-release-v1.json').resolve(),'N24 validation release path differs')
    c.require(w.read_ref(c.ref(path))=={'schema':'n24-validation-execution-release-v1','plan':c.ref(plan_path),
        'source_commit':plan['source_commit'],'cohort_id':c.COHORT,'seed_cohort':plan['n24_validation']['seed_cohort'],
        'episode_keys':[x['episode_key'] for x in plan['episodes']],'limits':c.LIMITS,
        'dev_review':plan['n24_validation']['dev_review'],'source_review':plan['n24_validation']['source_review'],
        'authority':plan['n24_validation']['authority'],'physical_gpu':7,'uuid':c.GPU7_UUID,
        'validation_authorized':True,'formal_authorized':False},'N24 exact protected release differs')
    with r.locked(ROOT/'data/qd-ed-runner.lock',nonblocking=True),r.locked(ROOT/'data/qd-ed-state.lock'):
        metadata=identity.metadata(ROOT,c.original_plan())
        c.require(identity.first_unused(*metadata[:4])==plan['n24_validation']['seed_cohort'],'N24 validation release freshness changed')
        events=r.read_events(ROOT/'data/attempt-ledger.jsonl');resources=r.read_events(ROOT/'data/gpu-healthcheck-ledger.jsonl')
        state=r.read_state(ROOT/'research-state.yaml');c.full_capacity(state,events,resources,vars(r))
        r.check_budget(state,events,plan['episodes'][0],resources,r.read_events(ROOT/'data/gpu-hour-reservation-ledger.jsonl'),physical_gpu=7)


def one_attempt(plan_path,plan,row,*,eligibility=None):
    seen={e['attempt_id'] for e in r.read_events(ROOT/'data/attempt-ledger.jsonl')}
    with c.supervised_scope(plan,ROOT,row['episode_key'],eligibility=eligibility):
        try:
            values=r.run_plan(plan_path,split='validation',iteration=c.COHORT,episode_keys=[row['episode_key']],root=ROOT)
            c.require(len(values)==1,'N24 validation one-cell result missing');return values[0]
        except r.GateError:
            finals=[e for e in r.read_events(ROOT/'data/attempt-ledger.jsonl') if e['attempt_id'] not in seen and e['event'] in r.TERMINAL
                and e.get('identity',{}).get('iteration')==c.COHORT and e.get('episode_key')==row['episode_key']]
            if len(finals)!=1:raise
            return finals[0]


def execute(plan_path,plan,profiles,runtime,output):
    output=r.owned(output,plan['artifact_root']);output.mkdir(parents=True,exist_ok=True)
    status=output/'aggregate-progress-v1.json';c.require(not status.exists(),'N24 validation cannot resume')
    completed=0;failed=True
    def progress(phase):
        r.durable_json(status,{'schema':'n24-validation-progress-v1','phase':phase,'accepted_cells':completed,
            'expected_cells':60,'protected_outcomes_disclosed':False})
    try:
        progress('started')
        for row in plan['episodes']:
            dev_supervisor.device_check();result=one_attempt(plan_path,plan,row)
            if result.get('outcome_valid') is not True:
                events=r.read_events(ROOT/'data/attempt-ledger.jsonl')
                record=recovery.create_eligibility(plan_path,plan,row,result,profiles['profiles'][row['profile']],runtime,events,ROOT,vars(r))
                path=c.RUN_DIR/'validation-eligibility-v1'/f"{result['attempt_id']}.json";w.atomic_json(path,record)
                dev_supervisor.device_check();result=one_attempt(plan_path,plan,row,eligibility=c.ref(path))
            final=c.accepted_cell(plan,row,r.read_events(ROOT/'data/attempt-ledger.jsonl'),ROOT,vars(r))
            c.require(final['attempt_id']==result['attempt_id'],'N24 validation accepted result is not first valid')
            completed+=1;progress('cell_audited')
        progress('completed');failed=False
    except BaseException:
        try:progress('invalid_or_interrupted')
        except OSError:pass
        raise
    finally:
        reporting.write_reports(plan,r.read_events(ROOT/'data/attempt-ledger.jsonl'),output,ROOT,vars(r),
            force_invalid=failed,controller_completed=completed)
    return w.read_ref(c.ref(output/'aggregate-disposition-v1.json'))


def launch(plan_path,release,output):
    plan,profiles,runtime=r.validate_plan(plan_path,root=ROOT)
    c.require(Path(output).resolve()==(c.RUN_DIR/'validation-execution').resolve(),'N24 protected output path differs')
    Path(output).mkdir(parents=True,exist_ok=True)
    with r.locked(Path(output)/'supervisor.lock',nonblocking=True):
        c.require(not (Path(output)/'aggregate-progress-v1.json').exists() and not (Path(output)/'aggregate-disposition-v1.json').exists(),
            'N24 validation no restart/result overwrite')
        release_check(release,plan_path,plan)
        return execute(plan_path,plan,profiles,runtime,output)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--release',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True);args=p.parse_args()
    try:aggregate=launch(args.plan,args.release,args.output_dir)
    except BaseException as exc:
        # Detailed protected evidence stays on disk; exception text never becomes a tuning summary.
        print(json.dumps({'schema':'n24-validation-launch-status-v1','aggregate_only':True,'status':'INVALID_OR_NOT_ADMITTED',
            'failure_class':type(exc).__name__,'formal_authorized':False}));raise SystemExit(1)
    print(json.dumps(aggregate))


if __name__=='__main__':
    signal.signal(signal.SIGTERM,lambda *_:(_ for _ in ()).throw(KeyboardInterrupt()))
    main()
