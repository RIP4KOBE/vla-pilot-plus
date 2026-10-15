#!/usr/bin/env python3
"""Audit and dispatch the exact 54 pending N7 C1 cells, one at a time."""
from __future__ import annotations

import argparse
from pathlib import Path
import signal

import qd_ed_final_runner as runner
import qd_ed_n7_validation_continuation as contract
import qd_ed_n7_validation_supervise as original_supervisor

ROOT = Path(__file__).resolve().parents[1]


def release_check(path, plan_path, plan):
    expected={'schema':'qd-ed-n7-validation-continuation-execution-release-v1',
        'plan_path':str(plan_path.resolve()),'plan_sha256':runner.digest(plan_path),
        'source_commit':plan['source_commit'],'cohort_id':contract.COHORT,
        'episode_keys':[r['episode_key'] for r in plan['episodes']],
        'recovery_of':contract.OLD_ATTEMPT,'physical_gpu':3,'formal_authorized':False}
    runner.require(runner.read_json(path)==expected,
                   'N7 C1 continuation exact execution release differs')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--release',type=Path,required=True)
    parser.add_argument('--status',type=Path,required=True)
    args=parser.parse_args()
    runner.require(Path(runner.read_state(ROOT/'research-state.yaml')['worktree']).resolve()==ROOT,
                   'N7 C1 continuation must run in owning study')
    plan,_,_=runner.validate_plan(args.plan,root=ROOT)
    runner.require(len(plan['episodes'])==54 and plan['episodes'][0]['retry_of']==contract.OLD_ATTEMPT,
                   'N7 C1 pending matrix differs')
    release_check(args.release,args.plan,plan)
    events=runner.read_events(ROOT/'data/attempt-ledger.jsonl')
    original=runner.read_json(contract.ORIGINAL)
    contract.old_accepted(events,original,runner.__dict__)
    contract.eligibility(events,original,runner.__dict__)
    status=runner.owned(args.status,plan['artifact_root'])
    runner.require(not status.exists(),'N7 C1 continuation status already exists')
    completed=[]
    runner.durable_json(status,{'status':'started','prior_accepted_count':6,
                               'completed_count':0,'selected_physical_gpu':3})
    try:
        for row in plan['episodes']:
            original_supervisor.wait_gpu3(status,completed)
            runner.durable_json(status,{'status':'dispatching','prior_accepted_count':6,
                'completed_count':len(completed),'current_key':row['episode_key'],
                'selected_physical_gpu':3})
            with runner.n7_validation_continuation_support().supervised_scope(plan,ROOT,row['episode_key']):
                summaries=runner.run_plan(args.plan,split='validation',
                    iteration=contract.COHORT,episode_keys=[row['episode_key']],root=ROOT)
            runner.require(len(summaries)==1 and summaries[0]['event']=='valid'
                           and summaries[0]['outcome_valid'] is True,
                           'N7 C1 continuation cell failed; preserve terminal and stop')
            original_supervisor.audit_result(summaries[0],row,status,completed)
            completed.append(row['episode_key'])
        runner.durable_json(status,{'status':'completed_all_54_audited',
            'prior_accepted_count':6,'completed_count':54,'total_accepted_count':60,
            'selected_physical_gpu':3})
    except BaseException as exc:
        runner.durable_json(status,{'status':'interrupted' if isinstance(exc,(KeyboardInterrupt,SystemExit)) else 'failed',
            'prior_accepted_count':6,'completed_count':len(completed),
            'reason':str(exc) if isinstance(exc,runner.GateError) else type(exc).__name__,
            'selected_physical_gpu':3})
        raise


if __name__=='__main__':
    signal.signal(signal.SIGTERM,lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    main()
