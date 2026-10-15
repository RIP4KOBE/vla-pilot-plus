#!/usr/bin/env python3
"""Run only the twelve previously frozen N11 Dev cells left after audit correction."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import signal

import audit_decision_evidence as audit
import qd_ed_available_gpu_queue as queue
import qd_ed_final_runner as runner
import qd_ed_n11_dev_contract as contract
import qd_ed_n11_dev_resume_prepare as prepare

ROOT = Path(__file__).resolve().parents[1]


def release_check(path, plan_path, plan):
    release = runner.read_json(path)
    runner.require(release == {
        'schema':'n11-dev-continuation-release-v2',
        'plan_path':str(Path(plan_path).resolve()),
        'plan_sha256':runner.digest(plan_path),
        'source_commit':plan['source_commit'],
        'cohort_id':contract.COHORT,
        'completed_episode_keys':prepare.PRIOR_KEYS,
        'remaining_episode_keys':prepare.REMAINING_KEYS,
        'physical_gpu':3,
        'validation_authorized':False,
        'formal_authorized':False,
    }, 'N11 continuation release differs from frozen Dev plan')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--release',type=Path,required=True)
    parser.add_argument('--status',type=Path,required=True)
    args = parser.parse_args()
    plan,_,_ = runner.validate_plan(args.plan,root=ROOT)
    runner.require(plan.get('n11_continuation',{}).get('schema') ==
                   'n11-audit-correction-continuation-v2'
                   and plan['n11_continuation']['completed_episode_keys'] == prepare.PRIOR_KEYS
                   and plan['n11_continuation']['remaining_episode_keys'] == prepare.REMAINING_KEYS,
                   'N11 continuation metadata differs')
    prepare.prior_evidence()
    release_check(args.release,args.plan,plan)
    status = runner.owned(args.status,plan['artifact_root'])
    runner.require(not status.exists(), 'N11 continuation status already exists')
    completed = list(prepare.PRIOR_KEYS)
    successes = {arm:0 for arm in contract.ARMS}
    runner.durable_json(status,{'status':'started','completed_keys':completed,
                               'successes':successes,'physical_gpu':3,
                               'audit_correction_sha256':prepare.CORRECTED_AUDIT_SHA})
    try:
        for row in plan['episodes'][4:]:
            runner.require(row['episode_key'] in prepare.REMAINING_KEYS,
                           'N11 continuation includes a prior identity')
            devices = queue.inventory()
            runner.require(3 in devices, 'GPU3 missing')
            queue.reservation_admission(devices[3])
            runner.gpu_admission(physical_gpu=3,expected_uuid=devices[3]['uuid'])
            with runner.n11_support().supervised_scope(plan,ROOT,row['episode_key']):
                summaries = runner.run_plan(args.plan,split='dev',iteration=contract.COHORT,
                                            episode_keys=[row['episode_key']],root=ROOT)
            runner.require(len(summaries)==1,'N11 continuation one-cell result missing')
            result = summaries[0]
            output = Path(result['output_dir'])
            links = contract.RUN_DIR/'attempts'
            links.mkdir(parents=True,exist_ok=True)
            link = links/result['attempt_id']
            runner.require(not link.exists() and not link.is_symlink(),
                           'N11 continuation attempt index collision')
            link.symlink_to(output,target_is_directory=True)
            runner.require(result['event']=='valid' and result['outcome_valid'] is True,
                           'N11 continuation Dev invalid; no automatic retry')
            native = audit.audit_episode(output/'eds_eval/decision_evidence/episode_000',
                                         output/'eds_eval/episode_compute.jsonl')
            runner.durable_json(output/'eds_eval/decision-evidence-audit.json',native)
            runner.require(native.get('accepted') is True and native.get('evidence_complete') is True,
                           'N11 continuation native evidence failed')
            if row['profile']=='N11':
                metric = runner.read_events(output/'eds_eval/eds_metrics.jsonl')
                runner.require(native.get('n11_parent_survival_audit',{}).get('checked_decisions')
                               == len(metric) and
                               native['n11_parent_survival_audit']['survivor_rounds_verified']
                               == 10*len(metric),
                               'N11 continuation exact parent survival not natively audited')
            successes[row['profile']] += int(result['success'] is True)
            completed.append(row['episode_key'])
            runner.durable_json(status,{'status':'cell_audited','completed_keys':completed,
                'successes':successes,'last_attempt':result['attempt_id'],'physical_gpu':3,
                'audit_correction_sha256':prepare.CORRECTED_AUDIT_SHA})
        runner.durable_json(status,{'status':'completed_all_sixteen_audited',
            'completed_keys':completed,'successes':successes,'physical_gpu':3,
            'audit_correction_sha256':prepare.CORRECTED_AUDIT_SHA})
    except BaseException as exc:
        runner.durable_json(status,{'status':'interrupted' if isinstance(exc,(KeyboardInterrupt,SystemExit)) else 'failed',
            'completed_keys':completed,'successes':successes,'reason':type(exc).__name__,
            'physical_gpu':3,'audit_correction_sha256':prepare.CORRECTED_AUDIT_SHA})
        raise


if __name__=='__main__':
    signal.signal(signal.SIGTERM,lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    main()
