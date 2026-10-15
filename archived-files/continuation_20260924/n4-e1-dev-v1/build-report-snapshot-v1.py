#!/usr/bin/env python3
"""Freeze a metadata-only, exact-cohort E1 report input snapshot."""
import argparse
import collections
import datetime
import hashlib
import json
import pathlib
import sys

W = pathlib.Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z')
B = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(W / 'scripts'))
import qd_ed_final_runner as r
import qd_ed_n4e1_plan as n


def ref(path):
    path = pathlib.Path(path).resolve()
    return {'path': str(path), 'sha256': r.digest(path)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=pathlib.Path, required=True)
    parser.add_argument('--plan-revision', type=pathlib.Path, action='append', default=[])
    args = parser.parse_args()
    output = args.output_dir.resolve()
    assert output.is_relative_to(pathlib.Path(r.read_json(B / 'plan.frozen.json')['artifact_root']) / 'continuation_20260923')
    output.mkdir(parents=True, exist_ok=False)

    def write(name, value):
        with (output / name).open('x') as stream:
            json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write('\n')

    base_path = B / 'plan.frozen.json'
    base = r.read_json(base_path)
    source = {item['path']: item['sha256'] for item in base['code_files']}
    for name in ('scripts/qd_ed_n4e1_report.py', 'scripts/qd_ed_n4e1_plan.py'):
        assert r.digest(W / name) == source[name], name
    with r.locked(W / 'data/qd-ed-state.lock'):
        raw = (W / 'data/attempt-ledger.jsonl').read_bytes()
        health_raw = (W / 'data/gpu-healthcheck-ledger.jsonl').read_bytes()
    assert raw.endswith(b'\n') and health_raw.endswith(b'\n')
    events = [entry for line in raw.splitlines() if (entry := json.loads(line)).get('identity', {}).get('iteration') == n.COHORT]
    groups = collections.OrderedDict()
    for entry in events:
        groups.setdefault(entry['attempt_id'], []).append(entry)
    assert groups and all(group[-1]['event'] in r.TERMINAL for group in groups.values()), 'snapshot needs terminal cohort attempts'
    excerpt = {
        'schema': 'qd-ed-n4e1-journal-excerpt-v1',
        'cohort_id': n.COHORT,
        'extraction': 'all_events_all_n4e1_attempts_through_snapshot',
        'snapshot_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'source_journal': {'path': str(W / 'data/attempt-ledger.jsonl'), 'sha256': hashlib.sha256(raw).hexdigest()},
        'source_journal_bytes': len(raw),
        'events': events,
        'terminal_attempt_ids': list(groups),
        'inflight_attempt_ids': [],
    }
    write('journal-excerpt.json', excerpt)
    plans = [ref(base_path)] + [ref(path) for path in args.plan_revision]
    assert len({item['sha256'] for item in plans}) == len(plans)
    attempts = []
    for group in groups.values():
        terminal = group[-1]
        path = r.owned(terminal['output_dir'], base['artifact_root']) / 'attempt-result.json'
        assert r.read_json(path) == terminal
        assert terminal['plan_sha256'] in {item['sha256'] for item in plans}
        spec = {'terminal': ref(path)}
        if terminal['event'] == 'valid' and terminal.get('outcome_valid') is True:
            audit = path.parent / 'eds_eval/decision-evidence-audit.json'
            if audit.exists():
                data = r.read_json(audit)
                spec['audit'] = ref(audit)
                if data.get('accepted') is True and data.get('evidence_complete') is True:
                    spec['compute'] = ref(path.parent / 'eds_eval/episode_compute.jsonl')
                    spec['metrics'] = ref(path.parent / 'eds_eval/eds_metrics.jsonl')
        attempts.append(spec)
    health = []
    for declared in base['n4e1_cohort']['health_resources']:
        records = [entry for line in health_raw.splitlines() if (entry := json.loads(line)).get('resource_id') == declared['resource_id']]
        assert records and records[-1]['event'] in {'completed', 'aborted'}
        terminal = records[-1]
        path = r.owned(pathlib.Path(terminal['output_dir']) / 'healthcheck-result.json', base['artifact_root'])
        assert r.read_json(path) == terminal
        health.append({**declared, 'terminal': ref(path)})
    script = W / 'scripts/qd_ed_n4e1_report.py'
    auth = {
        'schema': 'qd-ed-n4e1-report-authorization-v1',
        'status': 'authorized',
        'script': ref(script),
        'protocol_sha256': base['n4e1_cohort']['protocol']['sha256'],
        'base_plan_sha256': r.digest(base_path),
        'journal_excerpt_sha256': r.digest(output / 'journal-excerpt.json'),
        'scope': 'Exact E1 cohort terminal metadata and named accepted audit/compute/metrics only; no raw native reread or GPU/model/provider work.',
        'snapshot_builder': ref(__file__),
    }
    write('authorization.json', auth)
    manifest = {
        'schema': 'qd-ed-n4e1-report-input-v1',
        'script_sha256': r.digest(script),
        'protocol_sha256': base['n4e1_cohort']['protocol']['sha256'],
        'authorization': ref(output / 'authorization.json'),
        'base_plan': ref(base_path),
        'plan_revisions': plans[1:],
        'journal_excerpt': ref(output / 'journal-excerpt.json'),
        'attempts': attempts,
        'health_resources': health,
        'input_scope_complete': True,
    }
    write('manifest.json', manifest)
    print(json.dumps({'manifest': ref(output / 'manifest.json'), 'terminal_count': len(attempts), 'GPU_dispatches': 0}))


if __name__ == '__main__':
    main()
