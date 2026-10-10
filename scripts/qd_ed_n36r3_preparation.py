"""Read-only N36R3 review package. Never creates adoption or dispatch authority."""
import argparse
import datetime as dt
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import subprocess
from scripts import qd_ed_n23_worker as w, qd_ed_n36_contract as c
from scripts import qd_ed_final_runner as r


def bound(path):
    path = Path(path).absolute()
    raw = path.read_bytes()
    return {'path': str(path), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def read(reference):
    raw = Path(reference['path']).read_bytes()
    w.require(hashlib.sha256(raw).hexdigest() == reference['sha256']
              and len(raw) == reference['bytes'], 'preparation input binding changed')
    return json.loads(raw)


def ledger_snapshot(owner, review):
    """Read current complete bytes once, bind them, and recheck before returning."""
    anchors, rows = {}, {}
    for name in ('attempt-ledger.jsonl', 'gpu-healthcheck-ledger.jsonl',
                 'gpu-hour-reservation-ledger.jsonl'):
        path = Path(owner) / 'data' / name
        w.require(path.is_file() and not path.is_symlink(), 'regular owning ledger required')
        raw = path.read_bytes()
        anchors[name] = {'path': str(path), 'bytes': len(raw),
                         'sha256': hashlib.sha256(raw).hexdigest()}
        rows[name] = [json.loads(line) for line in raw.splitlines() if line.strip()]
        key = {'attempt-ledger.jsonl': 'ledger_prefix',
               'gpu-healthcheck-ledger.jsonl': 'health_ledger_prefix'}.get(name)
        if key:
            old = review[key]
            w.require(Path(old['path']) == path and len(raw) >= old['bytes']
                      and hashlib.sha256(raw[:old['bytes']]).hexdigest() == old['sha256'],
                      'root-reviewed ledger prefix changed')
    for anchor in anchors.values():
        w.require(bound(anchor['path']) == anchor, 'ledger changed during read-only snapshot')
    events, health = rows['attempt-ledger.jsonl'], rows['gpu-healthcheck-ledger.jsonl']
    snap = r.budget_snapshot(events, health)
    w.require(snap['dispatched'] == snap['reserved_attempts'] == 505
              and snap['gpu_hours_consumed'] == 75.53031173955723,
              'current accounting differs; fresh root reconciliation required')
    w.require(all(g[-1]['event'] in r.TERMINAL for g in r.event_groups(events).values())
              and snap['running'] == snap['gpu_healthcheck_inflight'] == 0,
              'unsettled accounting requires root reconciliation')
    return {'ledger_prefixes': anchors, 'snapshot': snap,
            'reservation_events': rows['gpu-hour-reservation-ledger.jsonl'],
            'reservation_reconciliation_required': True}


def arithmetic(snap):
    """Exact decimal prospective deductions; these are not spendable balances."""
    d = Decimal
    w.require(snap['gpu_hours_consumed'] == 75.53031173955723, 'retained charge differs')
    retained = d(str(snap['gpu_hours_consumed']))
    margin = d('0.23357169027962')
    protected = sum(d(str(v)) for v in c.CAPS['protected_gpu_hours'].values())
    effective = min(d('224'), d('53.08404692669838') + d('168'))
    after = retained + margin + d('21')
    buckets = {}
    for key, cap in c.CAPS['buckets'].items():
        addition = {'baseline': 10, 'development': 30}.get(key, 0)
        before = snap['by_bucket'][key]
        w.require(before + addition <= cap, 'prospective bucket exceeded')
        buckets[key] = {'before': before, 'addition': addition, 'after': before + addition,
                        'cap': cap, 'remaining': cap - before - addition}
    w.require(effective - after - protected >= 0, 'prospective protected headroom exceeded')
    return {'retained_attempts': 505, 'prospective_attempts': 545,
            'attempt_cap': 1800, 'remaining_attempts': 1255, 'buckets': buckets,
            'protected_attempt_caps': {'validation': 180, 'formal': 40},
            'seconds': {'episode': 1800, 'cleanup': 40, 'per_episode': 1840,
                        'cells': 40, 'episodes_total': 73600, 'health_total': 1800,
                        'unused_contingency': 200, 'cohort_total': 75600},
            'health': {'max_invocations': 41, 'timeout_seconds': 20,
                       'cleanup_seconds': 40, 'per_invocation_reserved_seconds': 60,
                       'aggregate_seconds': 1800, 'all_maximum_invocations_seconds': 2460,
                       'maximum_full_reservations': 30,
                       'rule': 'Both invocation and cumulative bounds apply; 41 full reservations do not fit. No automatic retries.'},
            'hours': {k: str(v) for k, v in {
                'retained': retained, 'retained_admission_margin': margin,
                'conservative_before': retained + margin, 'finite_cohort': d(21),
                'conservative_after': after, 'absolute_cap': d(224),
                'effective_cap': effective, 'protected_validation': d(32),
                'protected_formal': d(12), 'absolute_after': d(224)-after,
                'effective_after': effective-after,
                'unprotected_effective_after': effective-after-protected}.items()},
            'current_headroom': None, 'automatic_recoveries': 0}


def prepare(authority_ref, output):
    c.stop.check()
    authority = read(authority_ref)
    root = Path(authority['worktree'])
    w.require(root.resolve() == c.ROOT.resolve() and authority['node_id'] == '15.6'
              and authority['release_enabled'] is False and authority['gpu_authorized'] is False
              and authority['deadline'] == c.DEADLINE, 'bounded executor authority')
    review, requirements = read(authority['review']), read(authority['requirements'])
    standing = read(authority['standing_authority'])
    w.require(requirements['root_review'] == authority['review']
              and review['repair_source'] == authority['source']
              and review['status'] == 'PASS_G2_CPU_PREPARATION_COMPOSITION_ONLY'
              and standing['approved'] is True
              and standing['continuous_window']['end_utc'] == c.DEADLINE,
              'accepted composition and standing window required')
    report = read(review['repair_report'])
    artifacts = report['artifacts']
    plan_ref = artifacts['draft/plan.draft.json']
    plan = read(plan_ref)
    c.validate_draft(plan)
    w.require(plan['source']['commit'] == authority['source'], 'accepted source differs')
    # Bind accepted composition directly. Do not regenerate historical provenance.
    for name in ('runtime.isolated.disabled-v1.json', 'runtime-closure.isolated.disabled-v1.json',
                 'controller-semantics.disabled-v1.json', 'required-after.production-v1.json'):
        read(artifacts[name])
    snapshot = ledger_snapshot(authority['owner'], review)
    head = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    w.require(not subprocess.check_output(['git', '-C', str(root), 'status', '--porcelain'], text=True),
              'commit preparation plumbing before binding')
    subprocess.run(['git', '-C', str(root), 'merge-base', '--is-ancestor', authority['source'], head], check=True)
    out = Path(output).absolute()
    allowed = Path(authority['output_directory']).absolute()
    w.require(out.is_relative_to(allowed) and out != allowed and not out.exists()
              and not out.is_symlink() and out.parent.resolve() == allowed.resolve(),
              'new package must be inside authorized output directory')
    common = {'status': 'DISABLED_PENDING_ROOT_REVIEW', 'release_enabled': False,
              'production_accepted': False, 'score': None, 'source_adopted': False,
              'automatic_recoveries': 0, 'deadline': c.DEADLINE}
    changed = subprocess.check_output(['git', '-C', str(root), 'diff', '--name-only',
                                       authority['source'], head], text=True).splitlines()
    source_files = []
    for name in changed:
        path = root / name
        source_files.append({'relative_path': name, **bound(path)})
    records = {
        'accounting': {**snapshot, 'arithmetic': arithmetic(snapshot['snapshot']),
                       'new_budget_authority': False, 'caps': c.CAPS},
        'adoption': {'owner': authority['owner'], 'source_before': authority['source'],
                     'source_after': head, 'changed_source_files': source_files,
                     'accepted_report': review['repair_report'], 'accepted_plan': plan_ref,
                     'accepted_composition': {k: artifacts[k] for k in (
                         'runtime.isolated.disabled-v1.json', 'runtime-closure.isolated.disabled-v1.json',
                         'controller-semantics.disabled-v1.json', 'required-after.production-v1.json')},
                     'fresh_source_runtime_controller_bindings_required': True,
                     'runtime_ready': False, 'owning_accounting_adopted': False},
        'release': {'authority': authority_ref, 'root_review': authority['review'],
                    'requirements': authority['requirements'], 'standing_authority': authority['standing_authority'],
                    'stop_authority': c.stop.binding(), 'limits': c.LIMITS,
                    'episodes': plan['episodes'], 'worker_contract': c.WORKER_CONTRACT,
                    'phase_authorization': {'dev': False, 'validation': False, 'formal': False},
                    'detached_root_approval': None, 'G3': 'OPEN_ACTUAL_PRODUCTION_REQUIRED',
                    'first_C0_boundary': 'Mandatory pause after terminal; no continuation override implemented.',
                    'required_before_dispatch': requirements['required_before_dispatch'],
                    'G3_acceptance': requirements['G3_acceptance']}}
    c.stop.check()
    out.mkdir()
    refs = {}
    for name, value in records.items():
        path = out / (name + '.disabled-v1.json')
        w.atomic_json(path, {**common, 'schema': 'n36r3-' + name + '-preparation-v1', **value})
        refs[name] = bound(path)
    manifest = {**common, 'schema': 'n36r3-review-package-v1', 'source_after': head,
                'created_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'bindings': refs}
    w.atomic_json(out / 'package.disabled-v1.json', manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--authority', required=True, type=Path)
    parser.add_argument('--authority-sha256', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    reference = bound(args.authority)
    w.require(reference['sha256'] == args.authority_sha256, 'external authority hash differs')
    print(json.dumps(prepare(reference, args.output), indent=2))


if __name__ == '__main__':
    main()
