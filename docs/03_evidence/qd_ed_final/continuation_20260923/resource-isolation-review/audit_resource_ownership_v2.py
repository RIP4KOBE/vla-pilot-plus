#!/usr/bin/env python3
"""Read-only ownership audit; retain resource fields, never outcome/metric fields.

This is a snapshot report, not a ledger migration or budget authority.
No imports from the runner, no locks, and no shared-file writes.
"""
import ast
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path

W = Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z')
X = Path('/home/hynx/VLA-Pilot++/.worktree/exp/rdt-qd-ed-gpu6-20260922T063626Z')
ROOTS = {
    'W': Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z'),
    'X': Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-gpu6-20260922T063626Z'),
}
NAMES = ('attempt-ledger.jsonl', 'gpu-healthcheck-ledger.jsonl', 'gpu-hour-reservation-ledger.jsonl')
FIELDS = {'attempt_id', 'resource_id', 'event', 'output_dir', 'budget_bucket',
          'gpu_process_wall_seconds', 'physical_gpu', 'source_commit', 'plan_sha256',
          'runtime_manifest_sha256', 'time_unix', 'evidence_path', 'source_script_sha256'}
STABLE = FIELDS - {'event', 'gpu_process_wall_seconds', 'time_unix', 'evidence_path'}
TERMINAL = {'valid', 'aborted', 'completed'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def owner(path):
    if not isinstance(path, str) or not Path(path).is_absolute() or '..' in Path(path).parts:
        return 'Unknown'
    matches = [key for key, root in ROOTS.items() if Path(path).is_relative_to(root)]
    return matches[0] if len(matches) == 1 else 'Unknown'


def scalar(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: scalar(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [scalar(val) for val in value]
    return value


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    dest = Path(__file__).parent
    require(not (dest / 'snapshot-v2.json').exists(), 'snapshot output already exists')
    started = datetime.now(timezone.utc).isoformat()
    captured = {}
    for name in NAMES:
        path = W / 'data' / name
        before = path.stat()
        raw = path.read_bytes()
        after = path.stat()
        require((before.st_ino, before.st_size, before.st_mtime_ns) ==
                (after.st_ino, after.st_size, after.st_mtime_ns), 'ledger changed during byte read')
        require(not raw or raw.endswith(b'\n'), 'partial final JSONL line')
        captured[name] = (raw, after)
    # Require one stable sequential capture; stop rather than infer a live tail.
    require(all((W / 'data' / name).read_bytes() == raw for name, (raw, _) in captured.items()),
            'ledger append occurred during snapshot')

    result = {'schema': 'resource-ownership-read-only-review-v1', 'captured_utc': started,
              'scope': 'resource fields only; no task outcome, metric, native bundle, proof image or state read',
              'ownership_roots': {k: str(v) for k, v in ROOTS.items()}, 'ledgers': {}, 'groups': [],
              'issues': [], 'current_inflight': [], 'scientific_fields_retained': False}
    projections = {}
    for name, (raw, stat) in captured.items():
        group_rows = defaultdict(list)
        line_records = []
        offset = 0
        for line_number, line in enumerate(raw.splitlines(keepends=True), 1):
            # JSON is parsed only to select the explicitly permitted fields.
            resource = {k: v for k, v in json.loads(line, parse_float=Decimal).items() if k in FIELDS}
            identifier = resource.get('attempt_id', resource.get('resource_id'))
            require(identifier is not None, 'unrecognized reservation row requires separate review')
            assignment = owner(resource.get('output_dir'))
            ref = {'line': line_number, 'byte_offset': offset, 'byte_length': len(line),
                   'raw_line_sha256': sha(line), 'resource_group_id': identifier,
                   'owner': assignment}
            line_records.append(ref)
            group_rows[identifier].append((resource, ref))
            offset += len(line)
        projections[name] = [row for rows in group_rows.values() for row, _ in rows]
        partition_bytes = {key: b''.join(line for line, ref in zip(raw.splitlines(keepends=True), line_records)
                                       if ref['owner'] == key) for key in ('W', 'X', 'Unknown')}
        info = {'path': str(W / 'data' / name), 'snapshot_sha256': sha(raw),
                'bytes': len(raw), 'event_count': len(line_records), 'group_count': len(group_rows),
                'inode': stat.st_ino, 'mtime_ns': stat.st_mtime_ns,
                'x_symlink': str(X / 'data' / name),
                'x_resolves_same_file': (X / 'data' / name).resolve() == (W / 'data' / name).resolve(),
                'partition_raw_sha256': {key: sha(value) for key, value in partition_bytes.items()},
                'partition_bytes': {key: len(value) for key, value in partition_bytes.items()},
                'line_references': line_records}
        result['ledgers'][name] = info
        require(sum(info['partition_bytes'].values()) == len(raw), 'byte conservation failed')
        for identifier, rows in group_rows.items():
            owners = {ref['owner'] for _, ref in rows}
            issues = []
            if len(owners) != 1 or 'Unknown' in owners:
                issues.append('unknown_or_conflicting_output_root')
            for key in STABLE:
                present = {json.dumps(scalar(row[key]), sort_keys=True) for row, _ in rows if key in row}
                if len(present) > 1:
                    issues.append('resource_identity_drift:' + key)
            assignment = next(iter(owners)) if len(owners) == 1 else 'Unknown'
            events = [row['event'] for row, _ in rows]
            expected = (['reserved'], ['reserved', 'dispatched'], ['reserved', 'aborted'],
                        ['reserved', 'dispatched', 'valid'], ['reserved', 'dispatched', 'aborted'],
                        ['reserved', 'dispatched', 'completed'])
            require(events in expected, 'illegal resource event ordering')
            last = rows[-1][0]
            terminal = last['event'] in TERMINAL
            seconds = last.get('gpu_process_wall_seconds') if terminal else None
            require(not terminal or (isinstance(seconds, (int, Decimal)) and Decimal(seconds).is_finite()
                                     and seconds >= 0), 'missing/invalid terminal duration')
            item = {'ledger': name, 'resource_group_id': identifier, 'owner': assignment,
                    'event_count': len(rows), 'first_line': rows[0][1]['line'], 'last_line': rows[-1][1]['line'],
                    'dispatched': 'dispatched' in events, 'terminal': terminal,
                    'gpu_process_wall_seconds': seconds, 'output_dir': last.get('output_dir'),
                    'budget_bucket': last.get('budget_bucket'), 'physical_gpu': last.get('physical_gpu'),
                    'source_commit': last.get('source_commit'), 'plan_sha256': last.get('plan_sha256'),
                    'runtime_manifest_sha256': last.get('runtime_manifest_sha256'),
                    'issues': issues}
            result['groups'].append(item)
            if issues:
                result['issues'].append({'id': identifier, 'issues': issues})
            if not terminal:
                result['current_inflight'].append({'id': identifier, 'owner': assignment,
                    'ledger': name, 'phase': last['event'], 'observed_cost': 'Unknown_until_terminal'})

    def totals(groups):
        attempts = [g for g in groups if g['ledger'] == NAMES[0]]
        health = [g for g in groups if g['ledger'] == NAMES[1]]
        duration = lambda rows: sum((Decimal(g['gpu_process_wall_seconds']) for g in rows if g['terminal']), Decimal(0))
        attempt_seconds, health_seconds = duration(attempts), duration(health)
        buckets = sorted({g['budget_bucket'] for g in attempts})
        return {'attempt_groups': len(attempts), 'attempt_events': sum(g['event_count'] for g in attempts),
                'dispatched_attempts': sum(g['dispatched'] for g in attempts),
                'terminal_attempts': sum(g['terminal'] for g in attempts),
                'unsettled_attempts': sum(not g['terminal'] for g in attempts),
                'attempts_by_bucket': {b: sum(g['dispatched'] and g['budget_bucket'] == b for g in attempts) for b in buckets},
                'attempt_seconds_by_bucket': {b: duration([g for g in attempts if g['budget_bucket'] == b]) for b in buckets},
                'attempt_seconds': attempt_seconds, 'health_groups': len(health),
                'health_events': sum(g['event_count'] for g in health),
                'terminal_health_groups': sum(g['terminal'] for g in health), 'health_seconds': health_seconds,
                'combined_settled_seconds': attempt_seconds + health_seconds,
                'combined_settled_hours': (attempt_seconds + health_seconds) / Decimal(3600)}
    result['totals'] = {key: totals([g for g in result['groups'] if g['owner'] == key])
                        for key in ('W', 'X', 'Unknown')}
    result['totals']['shared'] = totals(result['groups'])
    keys = ('attempt_groups', 'attempt_events', 'dispatched_attempts', 'terminal_attempts',
            'unsettled_attempts', 'attempt_seconds', 'health_groups', 'health_events',
            'terminal_health_groups', 'health_seconds', 'combined_settled_seconds')
    result['conservation'] = {key: sum(result['totals'][k][key] for k in ('W','X','Unknown')) ==
                             result['totals']['shared'][key] for key in keys}
    require(all(result['conservation'].values()), 'resource conservation failed')
    # Replay only two source functions using resource-only inputs, not the runner module.
    source = W / 'scripts/qd_ed_final_runner.py'
    module = ast.parse(source.read_text())
    selected = [node for node in module.body if isinstance(node, ast.FunctionDef)
                and node.name in {'event_groups', 'budget_snapshot'}]
    namespace = {'require': require, 'math': math, 'TERMINAL': {'valid', 'aborted'},
                 'BUCKETS': dict.fromkeys(('baseline','development','validation','formal','recovery'))}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(source), 'exec'), namespace)
    floats = lambda rows: [{k: float(v) if isinstance(v, Decimal) else v for k,v in row.items()} for row in rows]
    replay = namespace['budget_snapshot'](floats(projections[NAMES[0]]), floats(projections[NAMES[1]]))
    result['source_resource_replay'] = {'source': str(source), 'sha256': sha(source.read_bytes()),
        'note': 'Only resource outputs retained. Outcome fields absent from replay input; outcome counters intentionally not reported.',
        **{k: replay[k] for k in ('dispatched','reserved_attempts','running','gpu_hours_consumed','by_bucket',
                                  'gpu_hours_by_bucket','gpu_healthcheck_hours','gpu_healthcheck_inflight')}}
    require(abs(replay['gpu_hours_consumed'] - float(result['totals']['shared']['combined_settled_hours'])) < 1e-10,
            'resource replay differs')
    result['x_groups_with_w_run_id_prefix'] = {name: sum(g['owner']=='X' and
        g['resource_group_id'].startswith('rdt-qd-ed-final-20260921T093925Z__') and g['ledger']==name
        for g in result['groups']) for name in NAMES[:2]}
    with (dest / 'snapshot-v2.json').open('x') as stream:
        json.dump(scalar(result), stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')
    print(json.dumps(scalar({key: result[key] for key in ('captured_utc','totals','conservation','current_inflight','issues')}), indent=2))


if __name__ == '__main__':
    main()
