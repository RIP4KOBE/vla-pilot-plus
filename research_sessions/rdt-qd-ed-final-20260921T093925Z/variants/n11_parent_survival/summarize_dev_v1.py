#!/usr/bin/env python3
"""Summarize the immutable 16-cell N11 Dev comparison from audited attempts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

SESSION = Path(__file__).resolve().parents[2]
ART = SESSION/'artifacts'
WORK = SESSION/'study_worktree'
RUN = ART/'continuation_20260928/n11-parent-survival-dev-v1'
HERE = Path(__file__).resolve().parent
COHORT = 'N11_EXACT_PARENT_SURVIVAL_DEV_20260928'
ARMS = ('C0','Q0','N7','N11')
TASKS = (0,3,6,9)


def data(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    old_plan = RUN/'plan.frozen.v1.json'
    new_plan = RUN/'plan.frozen.v2.json'
    plan1, plan2 = data(old_plan),data(new_plan)
    require(plan1['episodes'] == plan2['episodes'] and len(plan2['episodes']) == 16,
            'N11 paired matrix differs')
    status = data(RUN/'status.v2.json')
    require(status['status'] == 'completed_all_sixteen_audited'
            and status['completed_keys'] == [r['episode_key'] for r in plan2['episodes']],
            'N11 cohort incomplete')
    ledger = rows(WORK/'data/attempt-ledger.jsonl')
    cohort = [event for event in ledger if event.get('identity',{}).get('iteration') == COHORT]
    valid = {}
    per_task = {str(task):{} for task in TASKS}
    metrics = {}
    audits = {}
    for index,row in enumerate(plan2['episodes']):
        key = row['episode_key']
        events = [event for event in cohort if event.get('episode_key') == key]
        require([event['event'] for event in events] == ['reserved','dispatched','valid'],
                'N11 attempt not exactly once: '+key)
        event = events[-1]
        expected_plan = sha(old_plan) if index < 4 else sha(new_plan)
        require(event['plan_sha256'] == expected_plan and event['outcome_valid'] is True
                and event['physical_gpu'] == 3 and event['success'] in (True,False),
                'N11 result identity invalid: '+key)
        output = Path(event['output_dir'])
        require(output.is_dir(), 'N11 output absent: '+key)
        metric = rows(output/'eds_eval/eds_metrics.jsonl')
        audit_path = (HERE/'audit_correction_20260928/task0_reaudit.json'
                      if row['profile']=='N11' and row['task_id']==0 else
                      output/'eds_eval/decision-evidence-audit.json')
        audit = data(audit_path)
        require(audit['accepted'] is True and audit['evidence_complete'] is True
                and audit.get('errors',[]) == [], 'N11 native evidence invalid: '+key)
        if row['profile']=='N11':
            gate = audit['n11_parent_survival_audit']
            require(gate['checked_decisions'] == len(metric)
                    and gate['survivor_rounds_verified'] == 10*len(metric)
                    and all(value.get('qd_parent_survivor_count') == 4 and
                            value.get('qd_parent_survivor_counts_by_iter') == [4]*10
                            for value in metric), 'N11 parent survival incomplete: '+key)
        valid[key] = event
        metrics[key] = metric
        audits[key] = {'path':str(audit_path),'sha256':sha(audit_path)}
        per_task[str(row['task_id'])][row['profile']] = {
            'success':event['success'],
            'attempt_id':event['attempt_id'],
            'gpu_process_wall_seconds':event['gpu_process_wall_seconds'],
            'stage_query_events':event.get('stage_query_events'),
            'stage_failed_queries':event.get('stage_failed_queries'),
            'guided_decisions':len(metric),
            'audit':audits[key],
        }
    for task in TASKS:
        pair=per_task[str(task)]
        require(set(pair)==set(ARMS), 'N11 task arm missing')
        n7=metrics[f'n11_dev_t{task:02d}_n7_20260928']
        n11=metrics[f'n11_dev_t{task:02d}_n11_20260928']
        by_step={record['global_step']:record for record in n7}
        common=[record for record in n11 if record['global_step'] in by_step]
        pair['n7_n11_common_guided_steps']=len(common)
        pair['n7_n11_selected_action_different_steps']=sum(
            by_step[record['global_step']].get('qd_selected_action_fingerprint') !=
            record.get('qd_selected_action_fingerprint') for record in common)
    totals={arm:sum(int(per_task[str(task)][arm]['success']) for task in TASKS)
            for arm in ARMS}
    seconds=sum(event['gpu_process_wall_seconds'] for event in valid.values())
    state=yaml.safe_load((WORK/'research-state.yaml').read_text())
    report={
        'schema':'n11-four-arm-dev-comparison-v1',
        'cohort':COHORT,
        'original_plan':{'path':str(old_plan),'sha256':sha(old_plan)},
        'continuation_plan':{'path':str(new_plan),'sha256':sha(new_plan)},
        'original_failed_status':{'path':str(RUN/'status.json'),'sha256':sha(RUN/'status.json')},
        'completed_status':{'path':str(RUN/'status.v2.json'),'sha256':sha(RUN/'status.v2.json')},
        'audit_correction':{'path':str(HERE/'audit_correction_20260928/audit-correction-v1.md'),
                            'sha256':sha(HERE/'audit_correction_20260928/audit-correction-v1.md')},
        'all_sixteen_valid':True,
        'profile_successes':totals,
        'tasks':per_task,
        'cohort_gpu_process_wall_seconds':seconds,
        'cohort_gpu_hours':seconds/3600,
        'cumulative_budget':state['budget'],
        'n11_promotion_gate':{'required_successes':3,'strictly_more_than_n7':True,
                              'passed':totals['N11']>=3 and totals['N11']>totals['N7']
                              and totals['N11']>=totals['C0'] and totals['N11']>=totals['Q0']},
        'validation_authorized':False,
        'formal_authorized':False,
    }
    json_path=HERE/'dev-comparison-v1.json'
    require(not json_path.exists(), 'N11 summary already frozen')
    json_path.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    table='\n'.join(f'| {task} | '+ ' | '.join('1' if per_task[str(task)][arm]['success'] else '0'
                    for arm in ARMS) + ' |' for task in TASKS)
    lines=[
        '# N11 four-arm matched Dev result',
        '',
        'All 16 original exposed Dev identities were run once on GPU3 and audited. '
        'The first four use frozen plan v1; the other twelve use audit-correction continuation plan v2. '
        'The policy algorithm and Stage condition are unchanged between the plans. '
        'The original failed task0 N11 audit remains preserved; an independent corrected audit '
        'accepts the same SHA-verified native evidence.',
        '',
        '| Task | C0 | Q0 | N7 | N11 |',
        '| --- | ---: | ---: | ---: | ---: |',
        table,
        f'| **Total** | **{totals["C0"]}/4** | **{totals["Q0"]}/4** | '
        f'**{totals["N7"]}/4** | **{totals["N11"]}/4** |',
        '',
        'N11 gained task3 versus N7 but lost task6; both failed task0 and task9. '
        'Exact survivor selection changed actions, but the outcome gain did not generalize. '
        'N11 fails its preregistered >=3/4 gate and is not promoted to validation or formal acceptance.',
        '',
        f'GPU3 process wall time charged to this cohort: {seconds:.3f} s '
        f'({seconds/3600:.6f} GPU h), within the 6 h local cap. '
        f'Cumulative budget: {state["budget"]["dispatched"]}/393 attempts, '
        f'{state["budget"]["gpu_hours_consumed"]:.6f}/100 GPU h. '
        'Protected validation and formal reserves remain closed.',
        '',
        'The task3 success is a useful mechanism signal, not an accepted candidate: '
        'its three guided decisions contain 30 audited survivor rounds and 120 exact survivor slots, '
        'and all three selected actions differ from N7 at the same decision steps. '
        'Task6 shows the opposing failure case. Detailed per-attempt costs, selected-action '
        f'differences, audit hashes and provenance are in `{json_path.name}`.',
        '',
    ]
    markdown=HERE/'dev-comparison-v1.md'
    require(not markdown.exists(), 'N11 markdown summary already frozen')
    markdown.write_text('\n'.join(lines))
    print(json.dumps({'totals':totals,'cohort_gpu_hours':seconds/3600,
                      'cumulative_dispatched':state['budget']['dispatched'],
                      'cumulative_gpu_hours':state['budget']['gpu_hours_consumed'],
                      'json_sha256':sha(json_path),'markdown_sha256':sha(markdown)},sort_keys=True))


if __name__=='__main__':
    main()
