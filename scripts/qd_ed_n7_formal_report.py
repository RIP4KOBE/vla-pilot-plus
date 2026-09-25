#!/usr/bin/env python3
"""Audit the exact historical fixed-set 40-cell N7 engineering acceptance."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import qd_ed_final_runner as runner
import qd_ed_n7_formal_plan as contract

ROOT=Path(__file__).resolve().parents[1]


def report(plan_path):
    plan,_,_=runner.validate_plan(plan_path,root=ROOT)
    events=runner.read_events(ROOT/'data/attempt-ledger.jsonl')
    terminals=[e for e in events if e.get('identity',{}).get('iteration')==contract.COHORT
               and e.get('event') in runner.TERMINAL]
    cells=[]
    for row in plan['episodes']:
        attempts=[e for e in terminals if e['episode_key']==row['episode_key']]
        runner.require(len(attempts)<=1,'N7 formal original repeated')
        accepted=attempts[0] if attempts and attempts[0]['event']=='valid' and attempts[0].get('outcome_valid') is True else None
        checkpoint=None
        if accepted:
            p=Path(accepted['output_dir'])/'eds_eval/n7-formal-cell-audit.json'
            if p.is_file():
                checkpoint=runner.read_json(p)
                runner.require(checkpoint.get('schema')=='qd-ed-n7-formal-cell-audit-v1'
                    and checkpoint.get('accepted') is True
                    and checkpoint.get('attempt_id')==accepted['attempt_id']
                    and checkpoint.get('episode_key')==row['episode_key']
                    and checkpoint.get('task_id')==row['task_id']
                    and checkpoint.get('profile')==row['profile']
                    and checkpoint.get('env_seed')==row['env_seed']
                    and checkpoint.get('init_row_sha256')==row['init_row_sha256']
                    and checkpoint.get('success')==accepted['success']
                    and checkpoint.get('source_commit')==plan['source_commit']
                    and checkpoint.get('plan_sha256')==runner.digest(plan_path),
                    'N7 formal accepted cell native audit differs')
        cells.append({'task_id':row['task_id'],'env_seed':row['env_seed'],
            'init_row_sha256':row['init_row_sha256'],'profile':row['profile'],
            'episode_key':row['episode_key'],
            'status':'complete_audited' if checkpoint else 'incomplete_or_invalid',
            'success':accepted['success'] if checkpoint else None,
            'accepted_attempt_id':accepted['attempt_id'] if checkpoint else None,
            'guided_chunks':checkpoint['guided_chunks'] if checkpoint else None,
            'qd_activity_observed':checkpoint['qd_activity_observed'] if checkpoint else None,
            'native_descriptor_assignments':checkpoint['native_descriptor_assignments'] if checkpoint else None,
            'terminal_attempts':[{'attempt_id':e['attempt_id'],'event':e['event'],
                'outcome_valid':e.get('outcome_valid'),
                'gpu_process_wall_seconds':e.get('gpu_process_wall_seconds')}
                for e in attempts]})
    runner.require({e['episode_key'] for e in terminals}<={r['episode_key'] for r in plan['episodes']},
                   'out-of-plan N7 formal terminal')
    complete=all(c['status']=='complete_audited' for c in cells)
    if complete:
        runner.require(len(terminals)==40 and all(e['budget_bucket']=='formal' for e in terminals),
                       'N7 formal complete cohort accounting differs')
    counts={arm:sum(c['success'] is True for c in cells if c['profile']==arm) if complete else None
            for arm in contract.ARMS}
    n7=[c for c in cells if c['profile']=='N7']
    activity={'active_episodes':sum(c['qd_activity_observed'] is True for c in n7) if complete else None,
        'guided_chunks':sum(c['guided_chunks'] for c in n7) if complete else None,
        'native_descriptor_assignments':sum(c['native_descriptor_assignments'] or 0 for c in n7) if complete else None}
    # Quantitative witness for substantive deployed QD, fixed before formal outcomes.
    active=complete and activity['active_episodes']>=5 and activity['guided_chunks']>=10
    active=active and activity['native_descriptor_assignments']==activity['guided_chunks']*11
    matched=[]
    if complete:
        for task in contract.TASKS:
            outcomes={c['profile']:c['success'] for c in cells if c['task_id']==task}
            runner.require(set(outcomes)==set(contract.ARMS),'N7 formal matched task missing')
            matched.append({'task_id':task,'outcomes':outcomes,
                'n7_gained_vs_c0':outcomes['N7'] and not outcomes['C0'],
                'n7_lost_vs_c0':outcomes['C0'] and not outcomes['N7'],
                'n7_gained_vs_q0':outcomes['N7'] and not outcomes['Q0'],
                'n7_lost_vs_q0':outcomes['Q0'] and not outcomes['N7'],
                'n7_gained_vs_n6':outcomes['N7'] and not outcomes['N6'],
                'n7_lost_vs_n6':outcomes['N6'] and not outcomes['N7']})
    gate=complete and active and counts['N7']>=5 and counts['N7']>=counts['C0'] and counts['N7']>=counts['Q0']
    return {'schema':'qd-ed-n7-formal-fixed-report-v1','cohort_id':contract.COHORT,
        'historical_fixed_set':True,'independent_generalization_claim':False,
        'plan':{'path':str(plan_path.resolve()),'sha256':runner.digest(plan_path)},
        'validation_report':plan['n7_formal']['validation_report'],
        'accepted_cells':sum(c['status']=='complete_audited' for c in cells),
        'expected_cells':40,'attempts':len(terminals),'success_counts':counts,
        'n7_qd_activity':activity,'n7_qd_substantively_active':active,
        'matched_tasks':matched,'formal_gate':gate,
        'decision':'TARGET_MET_ON_HISTORICAL_FIXED_SET' if gate else
                   'TARGET_NOT_MET_ON_HISTORICAL_FIXED_SET' if complete else 'INCOMPLETE_OR_INVALID',
        'gpu_process_wall_seconds':sum(e.get('gpu_process_wall_seconds',0.) for e in terminals),
        'cells':cells}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    runner.require(not args.output.exists(),'N7 formal report destination exists')
    result=report(args.plan)
    destination=runner.owned(args.output,runner.read_json(args.plan)['artifact_root'])
    runner.durable_json(destination,result)
    print(json.dumps({'decision':result['decision'],'accepted_cells':result['accepted_cells'],
        'success_counts':result['success_counts'],'report':str(destination)}))


if __name__=='__main__':
    main()
