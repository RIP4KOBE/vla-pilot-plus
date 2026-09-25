#!/usr/bin/env python3
"""Freeze N7 validation's previously unseen task/seed identities before release."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKTREE = ROOT / 'study_worktree'
ART = ROOT / 'artifacts'
OUT = ART / 'continuation_20260925/n7-validation-c1-v1/prelaunch-exposure-v1.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if OUT.exists():
        raise SystemExit(f'Immutable preflight exists: {OUT}')
    seed_path = WORKTREE / 'data/frozen-seed-plan.json'
    historical_path = WORKTREE / 'data/exposure-registry.jsonl'
    attempt_path = WORKTREE / 'data/attempt-ledger.jsonl'
    seeds = json.loads(seed_path.read_text())['blocks']
    hist = [json.loads(line) for line in historical_path.open() if line.strip()]
    attempts = [json.loads(line) for line in attempt_path.open() if line.strip()]
    exposed = {(row['task_id'], row['episode_seed']) for row in hist}
    exposed.update((x['identity']['task_id'], x['identity']['env_seed'])
                   for x in attempts if x.get('event') == 'dispatched' and isinstance(x.get('identity'), dict))
    formal = {(row['task_id'], row['env_seed']) for row in seeds['formal']}
    blocks = ('validation_c1_b1', 'validation_c1_b2')
    cells = []
    for block in blocks:
        rows = seeds[block]
        assert sorted(row['task_id'] for row in rows) == list(range(10))
        for row in rows:
            key = (row['task_id'], row['env_seed'])
            assert key not in exposed and key not in formal
            cells.append({'seed_block': block, 'task_id': row['task_id'],
                          'env_seed': row['env_seed'], 'policy_seed': row['policy_seed'],
                          'init_index': row['init_index'],
                          'init_row_sha256': row['init_row_sha256']})
    assert len({(x['task_id'], x['env_seed']) for x in cells}) == 20
    same_layout = all(seeds[blocks[0]][i]['init_row_sha256'] == seeds[blocks[1]][i]['init_row_sha256']
                      for i in range(10))
    payload = {'schema': 'n7-validation-prelaunch-exposure-v1',
               'seed_plan_sha256': sha(seed_path),
               'historical_registry_sha256_at_freeze': sha(historical_path),
               'attempt_ledger_sha256_at_freeze': sha(attempt_path),
               'historical_registry_rows': len(hist), 'attempt_events_at_freeze': len(attempts),
               'blocks': list(blocks), 'candidate_cells': 20,
               'task_seed_overlaps_with_prior_or_formal': 0,
               'same_init_row_across_two_seeds_per_task': same_layout,
               'generalization_claim': 'seed_robustness_only' if same_layout else 'seed_and_init_layout',
               'cells': cells}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + '\n')
    print(json.dumps({'path': str(OUT), 'sha256': sha(OUT), 'cells': len(cells),
                      'same_init_row_across_blocks': same_layout}))


if __name__ == '__main__':
    main()
