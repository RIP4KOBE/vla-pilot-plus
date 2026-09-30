#!/usr/bin/env python3
"""One protected N23 cohort; aggregate-only output, at most two typed recoveries."""
import argparse
from pathlib import Path
import signal
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
if str(ROOT/'scripts') not in sys.path:sys.path.insert(0,str(ROOT/'scripts'))
from scripts import qd_ed_final_runner as runner
from scripts import qd_ed_n23_validation_contract as c
from scripts import qd_ed_n23_validation_identity as identity
from scripts import qd_ed_n23_validation_recovery as recovery
from scripts import qd_ed_n23_validation_report as reporting
from scripts import qd_ed_n23_worker as worker
import qd_ed_available_gpu_queue as queue


def release_check(path,plan_path,plan):
    c.require(c.read_ref(c.ref(path))=={'schema':'n23-validation-execution-release-v1','plan':c.ref(plan_path),
        'source_commit':plan['source_commit'],'cohort_id':c.COHORT,'seed_cohort':plan['n23_validation']['seed_cohort'],
        'episode_keys':[v['episode_key'] for v in plan['episodes']],'limits':c.LIMITS,
        'dev_review':plan['n23_validation']['dev_review'],'source_review':plan['n23_validation']['source_review'],
        'backend_proof':plan['n23_validation']['backend_proof'],'physical_gpu':7,'uuid':c.GPU7_UUID,
        'validation_authorized':True,'formal_authorized':False},'validation exact root release differs')
    with runner.locked(ROOT/'data/qd-ed-runner.lock',nonblocking=True),runner.locked(ROOT/'data/qd-ed-state.lock'):
        snapshot=identity.metadata(ROOT,c.read(c.DEV_PLAN))
        c.require(identity.first_unused(*snapshot[:4])==plan['n23_validation']['seed_cohort'],'validation release freshness changed')
        events=runner.read_events(ROOT/'data/attempt-ledger.jsonl');resources=runner.read_events(ROOT/'data/gpu-healthcheck-ledger.jsonl')
        state=runner.read_state(ROOT/'research-state.yaml')
        c.full_capacity(state,events,resources,vars(runner))
        runner.check_budget(state,events,plan['episodes'][0],resources,
            runner.read_events(ROOT/'data/gpu-hour-reservation-ledger.jsonl'),physical_gpu=7)


def one_attempt(plan_path,plan,row,*,eligibility=None):
    seen={v['attempt_id'] for v in runner.read_events(ROOT/'data/attempt-ledger.jsonl')}
    with c.supervised_scope(plan,ROOT,row['episode_key'],eligibility=eligibility):
        try:
            values=runner.run_plan(plan_path,split='validation',iteration=c.COHORT,episode_keys=[row['episode_key']],root=ROOT)
            c.require(len(values)==1,'validation one-cell result missing');return values[0]
        except runner.GateError:
            events=runner.read_events(ROOT/'data/attempt-ledger.jsonl')
            finals=[v for v in events if v['attempt_id'] not in seen and v['event'] in runner.TERMINAL
                and v.get('identity',{}).get('iteration')==c.COHORT and v.get('episode_key')==row['episode_key']]
            if len(finals)!=1:raise
            return finals[0]


def execute(plan_path,plan,profiles,runtime,output):
    output=runner.owned(output,plan['artifact_root']);output.mkdir(parents=True,exist_ok=True)
    status=output/'aggregate-progress.json'
    c.require(not status.exists(),'validation cohort cannot resume or repeat')
    completed=0
    def progress(phase):
        runner.durable_json(status,{'schema':'n23-validation-progress-v1','phase':phase,'accepted_cells':completed,
            'expected_cells':60,'protected_outcomes_disclosed':False})
    progress('started')
    try:
        for row in plan['episodes']:
            devices=queue.inventory();c.require(7 in devices and devices[7]['uuid']==c.GPU7_UUID,'validation GPU7 differs')
            queue.reservation_admission(devices[7]);runner.gpu_admission(physical_gpu=7,expected_uuid=c.GPU7_UUID)
            result=one_attempt(plan_path,plan,row)
            if result.get('outcome_valid') is not True:
                events=runner.read_events(ROOT/'data/attempt-ledger.jsonl')
                value=recovery.create_eligibility(plan_path,plan,row,result,profiles['profiles'][row['profile']],runtime,events,ROOT,vars(runner))
                path=c.RUN_DIR/'validation-eligibility-v1'/f"{result['attempt_id']}.json"
                worker.atomic_json(path,value)
                result=one_attempt(plan_path,plan,row,eligibility=c.ref(path))
            events=runner.read_events(ROOT/'data/attempt-ledger.jsonl')
            accepted=c.accepted_cell(plan,row,events,ROOT,vars(runner))
            c.require(accepted['attempt_id']==result['attempt_id'],'validation accepted result is not first valid')
            completed+=1;progress('cell_audited')
        aggregate=reporting.write_reports(plan,runner.read_events(ROOT/'data/attempt-ledger.jsonl'),output,ROOT,vars(runner))
        progress('completed')
        return aggregate
    except BaseException:
        progress('invalid_or_interrupted')
        reporting.write_reports(plan,runner.read_events(ROOT/'data/attempt-ledger.jsonl'),output,ROOT,vars(runner),force_invalid=True)
        raise


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--release',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True)
    args=p.parse_args();plan,profiles,runtime=runner.validate_plan(args.plan,root=ROOT)
    release_check(args.release,args.plan,plan)
    import json
    print(json.dumps(execute(args.plan,plan,profiles,runtime,args.output_dir)))


if __name__=='__main__':
    signal.signal(signal.SIGTERM,lambda *_:(_ for _ in ()).throw(KeyboardInterrupt()))
    main()
