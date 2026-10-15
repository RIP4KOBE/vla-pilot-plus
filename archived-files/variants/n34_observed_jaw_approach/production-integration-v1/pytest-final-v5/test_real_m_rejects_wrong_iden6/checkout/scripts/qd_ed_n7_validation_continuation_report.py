#!/usr/bin/env python3
"""Report all C1 cells and the typed recovery under the original 10/20 gate."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import qd_ed_final_runner as runner
import qd_ed_n7_validation_continuation as contract

ROOT=Path(__file__).resolve().parents[1]
ARMS=('C0','Q0','N7')


def report(plan_path):
    plan,_,_=runner.validate_plan(plan_path,root=ROOT)
    original=runner.read_json(contract.ORIGINAL)
    runner.require(runner.digest(contract.ORIGINAL)==contract.ORIGINAL_SHA,
                   'original C1 plan changed')
    events=runner.read_events(ROOT/'data/attempt-ledger.jsonl')
    attempts=[e for e in events if e.get('identity',{}).get('iteration')==contract.COHORT
              and e.get('event') in runner.TERMINAL]
    cells=[]
    for index,row in enumerate(original['episodes']):
        terminals=[e for e in attempts if e['episode_key']==row['episode_key']]
        accepted=[e for e in terminals if e['event']=='valid' and e.get('outcome_valid') is True]
        runner.require(len(accepted)<=1,'duplicate valid N7 C1 cell')
        if index==6:
            runner.require(all(e['attempt_id']==contract.OLD_ATTEMPT
                               for e in terminals if e.get('outcome_valid') is False),
                           'unapproved N7 C1 invalid attempt')
            if len(terminals)>1:
                retries=[e for e in terminals if e['attempt_id']!=contract.OLD_ATTEMPT]
                runner.require(len(terminals)==2 and len(retries)==1 and
                    retries[0].get('retry_of')==contract.OLD_ATTEMPT and
                    retries[0]['budget_bucket']=='recovery',
                    'N7 C1 typed recovery lineage differs')
        else:
            runner.require(len(terminals)<=1 and all(e.get('retry_of') is None for e in terminals),
                           'N7 C1 unapproved repeated original')
        chosen=accepted[0] if accepted else None
        checkpoint=None
        if chosen:
            p=Path(chosen['output_dir'])/'eds_eval/n7-validation-cell-audit.json'
            if p.is_file():
                checkpoint=runner.read_json(p)
                expected_plan=contract.ORIGINAL_SHA if index<6 else runner.digest(plan_path)
                expected_source=original['source_commit'] if index<6 else plan['source_commit']
                runner.require(checkpoint.get('accepted') is True
                    and checkpoint.get('attempt_id')==chosen['attempt_id']
                    and checkpoint.get('episode_key')==row['episode_key']
                    and checkpoint.get('profile')==row['profile']
                    and checkpoint.get('task_id')==row['task_id']
                    and checkpoint.get('seed_block')==row['seed_block']
                    and checkpoint.get('env_seed')==row['env_seed']
                    and checkpoint.get('init_row_sha256')==row['init_row_sha256']
                    and checkpoint.get('success')==chosen['success']
                    and checkpoint.get('plan_sha256')==expected_plan
                    and checkpoint.get('source_commit')==expected_source,
                    'N7 C1 cell native audit identity differs')
        cells.append({'task_id':row['task_id'],'seed_block':row['seed_block'],
            'env_seed':row['env_seed'],'init_row_sha256':row['init_row_sha256'],
            'profile':row['profile'],'episode_key':row['episode_key'],
            'status':'complete_audited' if checkpoint else 'incomplete_or_invalid',
            'success':chosen['success'] if checkpoint else None,
            'accepted_attempt_id':chosen['attempt_id'] if checkpoint else None,
            'guided_chunks':checkpoint['guided_chunks'] if checkpoint else None,
            'terminal_attempts':[{'attempt_id':e['attempt_id'],'event':e['event'],
                'outcome_valid':e.get('outcome_valid'),'retry_of':e.get('retry_of'),
                'budget_bucket':e.get('budget_bucket'),
                'gpu_process_wall_seconds':e.get('gpu_process_wall_seconds')}
                for e in terminals]})
    runner.require({e['episode_key'] for e in attempts}=={r['episode_key'] for r in original['episodes']
                   if any(e['episode_key']==r['episode_key'] for e in attempts)},
                   'N7 C1 out-of-plan attempt')
    complete=all(c['status']=='complete_audited' for c in cells)
    if complete:
        runner.require(len(attempts)==61 and sum(e['budget_bucket']=='validation' for e in attempts)==60
                       and sum(e['budget_bucket']=='recovery' for e in attempts)==1,
                       'N7 C1 complete cohort accounting differs')
    counts={arm:sum(c['success'] is True for c in cells if c['profile']==arm) if complete else None
            for arm in ARMS}
    blocks={block:{arm:sum(c['success'] is True for c in cells if c['seed_block']==block
                              and c['profile']==arm) if complete else None for arm in ARMS}
            for block in ('validation_c1_b1','validation_c1_b2')}
    matched=[]
    if complete:
        for block in blocks:
            for task in range(10):
                outcomes={c['profile']:c['success'] for c in cells if c['seed_block']==block
                          and c['task_id']==task}
                runner.require(set(outcomes)==set(ARMS),'N7 C1 matched triplet missing')
                matched.append({'seed_block':block,'task_id':task,'outcomes':outcomes,
                    'n7_gained_vs_c0':outcomes['N7'] and not outcomes['C0'],
                    'n7_lost_vs_c0':outcomes['C0'] and not outcomes['N7'],
                    'n7_gained_vs_q0':outcomes['N7'] and not outcomes['Q0'],
                    'n7_lost_vs_q0':outcomes['Q0'] and not outcomes['N7']})
    gate=complete and counts['N7']>=10 and counts['N7']>=counts['C0'] and counts['N7']>=counts['Q0']
    return {'schema':'qd-ed-n7-validation-c1-continuation-report-v1',
        'cohort_id':contract.COHORT,
        'original_plan':{'path':str(contract.ORIGINAL),'sha256':contract.ORIGINAL_SHA},
        'continuation_plan':{'path':str(plan_path.resolve()),'sha256':runner.digest(plan_path)},
        'typed_eligibility_audit_sha256':contract.ELIGIBILITY_SHA,
        'accepted_cells':sum(c['status']=='complete_audited' for c in cells),
        'expected_cells':60,'terminal_attempts':len(attempts),
        'invalid_old_attempt_id':contract.OLD_ATTEMPT,
        'success_counts':counts,'block_counts':blocks,'matched_triplets':matched,
        'candidate_numeric_gate':gate,
        'decision':'ELIGIBLE_FOR_SEPARATELY_FROZEN_FORMAL' if gate else
                   'REJECT_VALIDATION' if complete else 'INCOMPLETE_OR_INVALID',
        'formal_authorized':False,
        'gpu_process_wall_seconds':sum(e.get('gpu_process_wall_seconds',0.) for e in attempts),
        'generalization_claim':'seed_robustness_only','cells':cells}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    runner.require(not args.output.exists(),'N7 C1 report destination exists')
    result=report(args.plan)
    destination=runner.owned(args.output,runner.read_json(args.plan)['artifact_root'])
    runner.durable_json(destination,result)
    print(json.dumps({'decision':result['decision'],'accepted_cells':result['accepted_cells'],
        'success_counts':result['success_counts'],'report':str(destination)}))


if __name__=='__main__':
    main()
