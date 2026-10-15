#!/usr/bin/env python3
"""Read-only N19 Dev accounting and gate summary from frozen identities."""
from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1] / 'study_worktree'
PLAN = HERE / 'plan.frozen.v1.gpu7.json'
COHORT = 'N19_CORRECTED_LIFT_DEV_20260929'
STATUS = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/continuation_20260929/n19-corrected-lift-dev-v1/supervisor-status-gpu7-v1.json')


def jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def summarize():
    plan = json.loads(PLAN.read_text())
    expected = plan['episodes']
    assert len(expected) == 9 and [x['episode_key'] for x in expected] == [
        f'n19_dev_t{task:02d}_{arm.lower()}_20260929'
        for task in (0, 6, 9) for arm in ('C0', 'Q0', 'N19')]
    events = [x for x in jsonl(ROOT / 'data/attempt-ledger.jsonl')
              if x.get('identity', {}).get('iteration') == COHORT]
    groups = defaultdict(list)
    for event in events:
        groups[event['episode_key']].append(event)
    assert set(groups) <= {x['episode_key'] for x in expected}
    cells = []
    for row in expected:
        stream = groups.get(row['episode_key'], [])
        if not stream:
            cells.append({'task_id': row['task_id'], 'profile': row['profile'],
                          'episode_key': row['episode_key'], 'status': 'not_dispatched'})
            continue
        assert len({x['attempt_id'] for x in stream}) == 1, 'duplicate N19 episode identity'
        assert [x['event'] for x in stream[:2]] == ['reserved', 'dispatched'], 'N19 dispatch sequence differs'
        last = stream[-1]
        cell = {'task_id': row['task_id'], 'profile': row['profile'],
                'episode_key': row['episode_key'], 'attempt_id': last['attempt_id'],
                'status': last['event'], 'physical_gpu': last.get('physical_gpu'),
                'gpu_process_wall_seconds': last.get('gpu_process_wall_seconds')}
        if last['event'] in {'valid', 'aborted'}:
            cell.update(outcome_valid=last.get('outcome_valid'),
                        success=last.get('success'),
                        compute_outcome=last.get('compute_outcome'))
            audit_path = Path(last['output_dir']) / 'eds_eval/decision-evidence-audit.json'
            if audit_path.exists():
                audit = json.loads(audit_path.read_text())
                cell['native_accepted'] = audit.get('accepted') is True and audit.get('evidence_complete') is True
                if row['profile'] == 'N19':
                    cell['lift_native'] = audit.get('n18_lift_quality_audit')
            else:
                cell['native_accepted'] = False
        cells.append(cell)
    terminal = [x for x in cells if x['status'] in {'valid', 'aborted'}]
    complete = len(terminal) == len(expected)
    all_valid = complete and all(x['status'] == 'valid'
                                 and x.get('outcome_valid') is True
                                 and x.get('native_accepted') is True for x in terminal)
    successes = {arm: sum(x.get('success') is True for x in terminal if x['profile'] == arm)
                 for arm in ('C0', 'Q0', 'N19')}
    candidate_success_tasks = sorted(x['task_id'] for x in terminal
                                     if x['profile'] == 'N19' and x.get('success') is True)
    native = [x['lift_native'] for x in terminal if x['profile'] == 'N19'
              and isinstance(x.get('lift_native'), dict)]
    positive = sum(x.get('positive_bonus_candidates', 0) for x in native)
    promoted = bool(all_valid and 0 in candidate_success_tasks and successes['N19'] >= 2
                    and successes['N19'] > max(successes['C0'], successes['Q0'])
                    and positive > 0 and len(native) == 3)
    status = json.loads(STATUS.read_text()) if STATUS.exists() else None
    if status and status.get('status') == 'completed_all_nine_audited':
        assert complete and all_valid and promoted == status['dev_gate_promoted'], 'supervisor/report gate differs'
    return {'schema': 'n19-dev-readonly-summary-v1',
            'cohort': COHORT, 'plan_sha256': __import__('hashlib').sha256(PLAN.read_bytes()).hexdigest(),
            'completed_cells': len(terminal), 'all_nine_native_valid': all_valid,
            'successes': successes, 'candidate_success_tasks': candidate_success_tasks,
            'positive_bonus_candidates': positive, 'dev_gate_promoted': promoted,
            'supervisor_status': status.get('status') if status else None,
            'cells': cells}


if __name__ == '__main__':
    print(json.dumps(summarize(), indent=2, sort_keys=True))
