#!/usr/bin/env python3
"""Append omitted current-study Dev exposure identities from the attempt journal."""
import datetime
import json
import os
from pathlib import Path
import sys

W = Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z')
A = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z')
OUT = A / 'continuation_20260924/n4-e1-dev-v1/dev-exposure-reconcile-v1'
sys.path.insert(0, str(W / 'scripts'))
import qd_ed_final_runner as r

seed_path = W / 'data/frozen-seed-plan.json'
ledger_path = W / 'data/attempt-ledger.jsonl'
registry_path = W / 'data/exposure-registry.jsonl'
seed_plan = r.read_json(seed_path)
assert len(seed_plan['blocks']['dev']) == 10
with r.locked(W / 'data/qd-ed-state.lock'):
    events = r.read_events(ledger_path)
    before = r.read_events(registry_path)
    assert len(before) == 55
    existing = {(x['task_id'], x['episode_seed'], x['init_identity']['row_sha256'])
                for x in before if x.get('schema') == 'qd-ed-final-study-exposure-v1'}
    assert existing == {(0, 1969522881, '48b759458f7f8b6c4ee24238038db71ab908360b36e58729d053daf269d544ae')}
    new = []
    covered = []
    for seed in seed_plan['blocks']['dev']:
        task = seed['task_id']
        matches = [event for event in events if event['event'] == 'dispatched'
                   and event['identity']['split'] == 'dev' and event['identity']['task_id'] == task]
        assert matches
        for event in matches:
            identity = event['identity']
            assert identity['env_seed'] == seed['env_seed']
            assert identity['policy_seed'] == seed['policy_seed']
            assert identity['init_index'] == seed['init_index']
            assert event['init_row_sha256'] == seed['init_row_sha256']
        key = (task, seed['env_seed'], seed['init_row_sha256'])
        covered.append({'task_id': task, 'env_seed': seed['env_seed'],
                        'init_row_sha256': seed['init_row_sha256'],
                        'dispatched_attempts': len(matches)})
        if key in existing:
            continue
        new.append({
            'schema': 'qd-ed-final-study-exposure-v1',
            'run_name': seed_plan['run_name'], 'suite': 'libero_object_swap',
            'study_role': 'dev_exposed', 'new_run_exposure': True,
            'counterfactual_or_new_holdout': False,
            'exposure_kind': 'conservative_dispatched_dev_cell_including_invalid_and_infrastructure_aborts',
            'task_id': task, 'task_name': seed['task_name'],
            'episode_seed': seed['env_seed'], 'policy_seed': seed['policy_seed'],
            'init_identity': {'index': seed['init_index'], 'file_sha256': seed['init_file_sha256'],
                              'row_sha256': seed['init_row_sha256']},
            'attempt_ids': [event['attempt_id'] for event in matches],
            'evidence_path': str(ledger_path), 'seed_plan_path': str(seed_path),
            'limitation': 'Exposure means dispatched at least once; task outcome and independent layout generalization are not inferred.',
            'time': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        })
    assert len(new) == 9 and sorted(x['task_id'] for x in new) == list(range(1, 10))
    assert not OUT.exists()
    OUT.mkdir(parents=True)
    with registry_path.open('a') as stream:
        for row in new:
            stream.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + '\n')
        stream.flush(); os.fsync(stream.fileno())
    after = r.read_events(registry_path)
    assert len(after) == 64
    assert sum(x.get('schema') == 'qd-ed-final-study-exposure-v1' for x in after) == 10
    result = {'schema': 'qd-ed-dev-exposure-reconcile-v1',
              'decision': 'ALL_TEN_FROZEN_DEV_TASK_SEED_INIT_IDENTITIES_EXPOSED',
              'existing_study_records': 1, 'new_records_appended': 9,
              'covered': covered,
              'attempt_ledger': {'path': str(ledger_path), 'sha256': r.digest(ledger_path)},
              'seed_plan': {'path': str(seed_path), 'sha256': r.digest(seed_path)},
              'registry_after': {'path': str(registry_path), 'sha256': r.digest(registry_path)},
              'protected_validation_formal_exposure': 'not_claimed_or_inferred'}
    with (OUT / 'reconciliation.json').open('x') as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write('\n')
print(json.dumps({'decision': result['decision'], 'new_records': len(new),
                  'registry_sha256': r.digest(registry_path)}))
