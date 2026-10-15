"""Metadata-only protected-cohort readiness snapshot; never an execution release."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1] / 'study_worktree'


def require(value, message):
    if not value:
        raise ValueError(message)


def pair(row, key='env_seed'):
    values = row.get('task_id'), row.get(key)
    require(all(type(x) is int for x in values), 'missing/noninteger task/seed identity')
    return values


def analyze(seeds, exposed_pairs, reserved_pairs):
    blocks = seeds['blocks']
    expected = set(range(10))
    formal = {pair(x) for x in blocks['formal']}
    dev = {pair(x) for x in blocks['dev']}
    used = set(exposed_pairs) | set(reserved_pairs) | formal | dev
    seen, result = set(), {}
    for cohort in range(1, 5):
        names = [f'validation_c{cohort}_b{i}' for i in (1, 2)]
        rows = []
        for name in names:
            block = blocks[name]
            require(len(block) == 10 and {x['task_id'] for x in block} == expected,
                    'validation block task mapping differs')
            require(all(type(x['policy_seed']) is int for x in block), 'policy seed missing')
            rows.extend(block)
        identities = {pair(x) for x in rows}
        require(len(identities) == 20 and not seen.intersection(identities),
                'preregistered validation seeds duplicate within/across cohorts')
        seen.update(identities)
        layouts = {t: {(x['init_index'], x['init_row_sha256'], x['init_file_sha256'], x['bddl_sha256'])
                       for x in rows if x['task_id'] == t} for t in range(10)}
        result[f'c{cohort}'] = {
            'blocks': names, 'task_seed_cells': len(identities),
            'overlap_with_exposure_registry': len(identities.intersection(exposed_pairs)),
            'overlap_with_reserved_or_dispatched_identities': len(identities.intersection(reserved_pairs)),
            'overlap_with_dev_or_formal': len(identities.intersection(dev | formal)),
            'unused_in_this_snapshot': not bool(identities.intersection(used)),
            'same_init_identity_across_two_seeds_for_every_task': all(len(v) == 1 for v in layouts.values()),
        }
    first = next((k for k, v in result.items() if v['unused_in_this_snapshot']), None)
    return {'cohorts': result, 'first_unused_in_this_snapshot': first,
            'release_authorized': False,
            'caveat': 'Identity-only snapshot of this study and its frozen historical inventory. Must recheck under owning locks after candidate promotion and before a separately frozen phase release. Shared init identities support seed robustness, not new-layout generalization. No validation outcomes were used.'}


def main():
    paths = [ROOT/'data'/x for x in ('frozen-seed-plan.json', 'historical-exposure-inventory.jsonl',
                                   'exposure-registry.jsonl', 'attempt-ledger.jsonl')]
    snapshots = {p: p.read_bytes() for p in paths}
    require(all(p.read_bytes() == blob for p, blob in snapshots.items()), 'metadata changed during snapshot')
    seeds = json.loads(snapshots[paths[0]])
    exposed = set()
    for p in paths[1:3]:
        for line in snapshots[p].splitlines():
            row = json.loads(line)
            # No outcome fields are inspected or retained.
            exposed.add(pair(row, 'episode_seed'))
    reserved = set()
    for line in snapshots[paths[3]].splitlines():
        row = json.loads(line)
        if row['event'] in ('reserved', 'dispatched'):
            identity = row.get('identity', {})
            require(identity.get('split') in ('dev', 'validation', 'formal'), 'unknown ledger identity scope')
            reserved.add(pair(identity))
    report = analyze(seeds, exposed, reserved)
    report.update(schema='protected-exposure-readiness-snapshot-v1',
                  recorded_at=datetime.now(timezone.utc).isoformat(),
                  input_snapshots=[{'path': str(p), 'bytes': len(blob), 'sha256': hashlib.sha256(blob).hexdigest()}
                                   for p, blob in snapshots.items()],
                  reader_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    target = HERE / 'exposure-snapshot-result-v1.json'
    with target.open('x') as f:
        f.write(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'path': str(target), **{k: report[k] for k in ('cohorts','first_unused_in_this_snapshot','release_authorized')}}))


if __name__ == '__main__':
    main()
