#!/usr/bin/env python3
"""Prospective CPU preparation and explicit four-row observed-pair entrypoint.

Prepare never freezes, runs a model/provider, or mutates state/ledger. Run is
root-only after integration/review/freeze; it delegates every launch to the
original queue/runner. The adjacent independent support copy is fingerprinted.
"""
import argparse
import copy
from contextlib import contextmanager
import importlib.util
import json
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[5]
AUTHORITATIVE_ROOT = Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z')
REL = 'docs/03_evidence/qd_ed_final/continuation_20260923/observed-pairs-draft'
SUPPORT = REL + '/supervisor-support.py'
DEPENDENCIES = 'docs/03_evidence/qd_ed_final/continuation_20260923/freshboot-model-first/native-dependency-freeze.json'
PROTOCOL = REL + '/prospective-protocol.md'
ITERATION = 'OBSERVED_PAIRS_DEV_20260923'
ORDER = [(0, 'C0'), (0, 'Q0'), (5, 'C0'), (5, 'Q0')]
KEYS = [f'observed_pairs_t{task:02d}_{profile.lower()}_20260923' for task, profile in ORDER]
FIELDS = ('env_seed', 'policy_seed', 'init_index', 'init_row_sha256', 'init_file_sha256', 'bddl_sha256')
OVERRIDE = 'main.decision_evidence.enabled=true'
PROFILE_PATH = REL + '/observed-baseline-profiles.json'
BOOT = '2a1fa95f-ab0d-488c-a298-fc488ddd2af7'


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def rows_from_dev(seeds):
    rows = []
    for (task, profile), key in zip(ORDER, KEYS):
        choices = [item for item in seeds['blocks']['dev'] if item['task_id'] == task]
        require(len(choices) == 1, 'missing or ambiguous dev task')
        source = choices[0]
        require(source['init_index'] == 0, 'init0 required')
        rows.append({**{name: source[name] for name in FIELDS}, 'task_id': task,
            'profile': profile, 'episode_key': key, 'iteration': ITERATION,
            'split': 'dev', 'seed_block': 'dev', 'budget_bucket': 'development',
            'timeout_seconds': 1800})
    return rows


def validate_pair_contract(plan, seeds):
    require(plan['episodes'] == rows_from_dev(seeds), 'fixed paired rows/order differ')
    require(plan['phase_authorization'] == {'dev': True, 'validation': False, 'formal': False},
            'only dev authorization permitted')
    require(plan['boot_id'] == BOOT, 'freshboot condition differs')
    require(plan.get('observational_overrides') == {OVERRIDE.split('=')[0]: True},
            'sole observation override differs')
    require(not plan.get('candidate_profiles'), 'candidate mechanisms are not authorized')
    require(plan.get('decision_evidence_gate') == 'stop_remaining_on_incomplete_preserve_task_outcome',
            'evidence stop rule differs')


def observed_profiles(baseline, baseline_sha256):
    result = copy.deepcopy(baseline)
    result['observation_condition'] = {'name': 'decision_observed_v1',
        'baseline_path': 'configs/qd_ed_final/baseline_profiles.json',
        'baseline_sha256': baseline_sha256, 'enabled_override': OVERRIDE}
    for name in ('C0', 'Q0'):
        profile = result['profiles'][name]
        require(OVERRIDE.split('=')[0] not in profile['static_override_values'], 'baseline observer collision')
        profile['static_override_values'][OVERRIDE.split('=')[0]] = True
        profile['hydra_overrides'].append(OVERRIDE)
        profile['historical_label'] += '__decision_observed_v1'
    return result


@contextmanager
def audited_calls(r, audit):
    """Audit after original terminal accounting; never rewrite that outcome."""
    original = r.run_plan
    def run(*args, **kwargs):
        results = original(*args, **kwargs)
        for result in results:
            output = Path(result['output_dir'])
            peak_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            started = time.monotonic()
            try:
                report = audit(output/'eds_eval/decision_evidence/episode_000', output/'eds_eval/episode_compute.jsonl')
            except Exception as exc:
                report = {'schema': 'qd-ed-decision-evidence-wrapper-error-v1', 'accepted': False,
                          'errors': ['audit_exception:' + type(exc).__name__]}
            elapsed = time.monotonic() - started
            report['wrapper_observation'] = {
                'audit_wall_seconds': elapsed,
                'parent_ru_maxrss_before_kib': peak_before,
                'parent_ru_maxrss_after_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                'memory_scope': 'Linux parent-process cumulative peak including imports/queue and previous audits; not audit-exclusive memory; peak difference is not memory usage',
            }
            r.durable_json(output/'eds_eval/decision-evidence-audit.json', report)
            r.require(report.get('accepted') is True, 'decision evidence incomplete; remaining undispatched rows stopped')
        return results
    r.run_plan = run
    try:
        yield
    finally:
        r.run_plan = original


def queue_summary(status, r):
    attempts = []
    for result in status.get('results', []):
        path = Path(result['output_dir'])/'eds_eval/decision-evidence-audit.json'
        audit = r.read_json(path)
        attempts.append({**{key: result.get(key) for key in
            ('attempt_id', 'event', 'outcome_valid', 'success', 'failure_class')},
            'evidence_audit': {key: audit.get(key) for key in
                ('accepted', 'evidence_complete', 'errors', 'wrapper_observation')}})
    return {'status': status['status'], 'completed_keys': status.get('completed_keys', []), 'attempts': attempts}


def load_support(root):
    spec = importlib.util.spec_from_file_location('observed_pair_support', root / SUPPORT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prerequisite(r, plan, root):
    r.require(Path('/proc/sys/kernel/random/boot_id').read_text().strip() == BOOT, 'GPU3 boot changed')
    records = {item['path']: item['sha256'] for item in plan['code_files']}
    for relative in (SUPPORT, DEPENDENCIES, REL + '/observed-pairs.py', PROTOCOL):
        r.require(records.get(relative) == r.digest(root / relative), 'GPU3 support/protocol freeze differs')
    r.verify_files(r.read_json(root / DEPENDENCIES)['files'])
    baseline = root/'configs/qd_ed_final/baseline_profiles.json'
    r.require(Path(plan['profiles_path']).resolve() == (root/PROFILE_PATH).resolve() and
        r.read_json(plan['profiles_path']) == observed_profiles(r.read_json(baseline), r.digest(baseline)),
        'observed profiles differ beyond the declared common instrumentation')
    refs = plan['observed_pair_prerequisites']
    loaded = {}
    for name, ref in refs.items():
        path = r.owned(ref['path'], plan['artifact_root'])
        r.require(r.digest(path) == ref['sha256'], 'GPU3 prerequisite changed: ' + name)
        loaded[name] = r.read_json(path)
    health, contract = loaded['health_result'], loaded['health_contract']
    r.require(health['event'] == 'completed' and not health.get('faults') and
        health['boot_id'] == contract['boot_id'] == BOOT and contract['physical_gpu'] == 3 and
        health['resource_id'] == contract['resource_id'] and
        health['contract_sha256'] == refs['health_contract']['sha256'], 'GPU3 health prerequisite differs')
    result, process, kernel = loaded['common_result'], loaded['common_process'], loaded['common_kernel']
    r.require(result['event'] == 'valid' and result.get('outcome_valid') is True and
        result['episode_key'] == 'freshboot_c0_t00_20260923' and result['physical_gpu'] == 3,
        'GPU3 production common-condition prerequisite incomplete')
    r.require(process['attempt_id'] == kernel['attempt_id'] == result['attempt_id'] and
        process['pid'] == kernel['pid'] and str(process['proc_start_ticks']) == str(kernel['proc_start_ticks']) and
        process['boot_id'] == kernel['boot_id'] == BOOT and kernel['physical_gpu'] == 3 and
        kernel['kind'] == 'episode' and kernel['faults'] == [], 'GPU3 common-condition process evidence differs')


def journal_budget_view(r, state, events, resources):
    """Read-only prepare view from the terminal journal held by the runner lock.

    Refresh only sync_state_from_journal's dynamic budget fields. Authorization,
    maxima, reserves and the caller's original state are never changed.
    """
    view = copy.deepcopy(state)
    snapshot = r.budget_snapshot(events, resources)
    for key in ('dispatched', 'aborted', 'valid', 'invalid', 'completed', 'running', 'gpu_hours_consumed'):
        view['budget'][key] = snapshot[key]
    return view


def batch_budget(r, state, events, resources, rows, reservations):
    snap = r.budget_snapshot(events, resources)
    budget = state['budget']
    r.require(budget.get('gpu_hour_reservations', {'validation': 14., 'formal': 10.}) ==
              {'validation': 14., 'formal': 10.}, 'protected 24h policy changed')
    for row in rows:
        r.check_retry(events, row)
        r.require(r.check_budget(state, events, row, resources, reservations, physical_gpu=3) == 1800,
                  'full episode timeout unavailable')
    protected_slots = sum(max(0, limit-snap['by_bucket'][name])
                          for name, limit in [('validation', 60), ('formal', 40)])
    protected_hours = sum(max(0., limit-snap['gpu_hours_by_bucket'][name])
                          for name, limit in [('validation', 14.), ('formal', 10.)])
    r.require(snap['dispatched'] + len(rows) + protected_slots <= budget['max_episode_attempts'] and
        snap['by_bucket']['development'] + len(rows) <= min(100, budget['reserved']['development']),
        'four rows exceed protected attempt budget')
    r.require(snap['gpu_hours_consumed'] + protected_hours +
        len(rows)*(1800+r.TERMINATION_GRACE_SECONDS)/3600 <= budget['max_gpu_hours'],
        'four rows exceed protected GPU-hour budget')


def prepare(args, r, q, root):
    plan = copy.deepcopy(r.read_json(args.base_plan))
    r.require(Path(plan['worktree']).resolve() == root, 'integrate into authoritative worktree first')
    output = r.owned(args.output, Path(plan['artifact_root']) / 'continuation_20260923')
    r.require(not output.exists(), 'refusing to overwrite plan')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    r.require(head == args.source_head, 'HEAD differs')
    for label in ('profiles', 'seed_plan', 'runtime_inventory', 'runtime_manifest'):
        r.require(r.digest(plan[label+'_path']) == plan[label+'_sha256'], 'input identity changed: '+label)
    seeds = r.read_json(plan['seed_plan_path'])
    base_common = r.read_json(args.common_result)
    r.require(base_common['plan_sha256'] == r.digest(args.base_plan) and
        base_common['source_commit'] == plan['source_commit'], 'common result must link explicit executed base plan')
    prior = plan['engineering_prerequisite']
    source_refs = {'health_result': Path(prior['result_path']), 'health_contract': Path(prior['contract_path']),
        'common_result': args.common_result, 'common_process': args.common_result.parent/'process.json',
        'common_kernel': args.common_result.parent/'freshboot-kernel-monitor.json'}
    plan['observed_pair_prerequisites'] = {name: {'path': str(path.resolve()), 'sha256': r.digest(path)}
                                         for name, path in source_refs.items()}
    for name in ('candidate_profiles', 'recovery_note', 'recovery_protocol', 'recovery_provenance',
                 'ordering_amendment', 'preflight_index', 'preflight_index_sha256', 'frozen_at',
                 'diagnostic_only', 'native_probe_contract', 'queue_contract', 'hardware_selection'):
        plan.pop(name, None)
    plan.update(frozen=False, source_commit=head, boot_id=BOOT, episodes=rows_from_dev(seeds),
        phase_authorization={'dev': True, 'validation': False, 'formal': False},
        observational_overrides={OVERRIDE.split('=')[0]: True},
        diagnostic_scope='Prospective observed C0/Q0 pairs on Dev tasks0/5; no candidate or promotion score',
        decision_evidence_gate='stop_remaining_on_incomplete_preserve_task_outcome',
        resource_amendment=PROTOCOL)
    observed = root/PROFILE_PATH
    r.require(r.read_json(observed) == observed_profiles(r.read_json(plan['profiles_path']), plan['profiles_sha256']),
              'observed profile must be the exact declared copy of base profile')
    plan.update(profiles_path=str(observed), profiles_sha256=r.digest(observed))
    paths = {item['path'] for item in plan['code_files']} | r.REQUIRED_CODE | {
        SUPPORT, DEPENDENCIES, PROTOCOL, PROFILE_PATH, REL+'/observed-pairs.py',
        'scripts/qd_ed_available_gpu_queue.py', 'scripts/qd_ed_gpu_probe.py', 'scripts/qd_ed_runtime_setup.py',
        'core/decision_evidence.py', 'scripts/audit_decision_evidence.py'}
    plan['scientific_config_files'] = sorted(set(plan['scientific_config_files']) | {PROTOCOL, PROFILE_PATH})
    paths |= set(plan['scientific_config_files'])
    for relative in sorted(paths):
        path = r.owned(root/relative, root)
        committed = subprocess.check_output(['git', 'show', head+':'+relative], cwd=root)
        r.require(path.read_bytes() == committed, 'uncommitted source: '+relative)
    plan['code_files'] = [{'path': name, 'sha256': r.digest(root/name)} for name in sorted(paths)]
    plan['preparation_provenance'] = {'base_plan_path': str(args.base_plan.resolve()),
        'base_plan_sha256': r.digest(args.base_plan), 'builder_sha256': r.digest(__file__)}
    validate_pair_contract(plan, seeds)
    prerequisite(r, plan, root)
    # No model bytes/provider/GPU work here. Terminal journals and budget are
    # read under the real lock; this builder never synchronizes/writes state.
    with r.locked(root/'data/qd-ed-runner.lock', nonblocking=True):
        events, resources = q.no_unfinished(root)
        state = r.read_state(root/'research-state.yaml')
        r.require(q.candidate_indices(state) == [3] and r.authorized_gpu(state) == 3,
                  'GPU3-only authorization required')
        r.require(not any(event.get('episode_key') in KEYS for event in events), 'new key already used')
        budget_state = journal_budget_view(r, state, events, resources)
        batch_budget(r, budget_state, events, resources, plan['episodes'],
                     r.read_events(root/'data/gpu-hour-reservation-ledger.jsonl'))
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('x') as stream:
            json.dump(plan, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write('\n')
        r.validate_plan(output, root=root, require_frozen=False)
    return {'draft': str(output), 'frozen': False, 'episode_keys': KEYS, 'GPU_dispatches': 0}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prep = commands.add_parser('prepare')
    prep.add_argument('--base-plan', type=Path, required=True)
    prep.add_argument('--common-result', type=Path, required=True)
    prep.add_argument('--source-head', required=True)
    prep.add_argument('--output', type=Path, required=True)
    for name in ('preview', 'run'):
        sub = commands.add_parser(name)
        sub.add_argument('--plan', type=Path, required=True)
        if name == 'run': sub.add_argument('--status-path', type=Path, required=True)
    args = parser.parse_args(argv)
    sys.path.insert(0, str(ROOT/'scripts'))
    import qd_ed_final_runner as r
    import qd_ed_available_gpu_queue as q
    r.require(ROOT == AUTHORITATIVE_ROOT, 'preparation worktree cannot dispatch or prepare authoritative plans; integrate first')
    if args.command == 'prepare':
        result = prepare(args, r, q, ROOT)
    elif args.command == 'preview':
        plan, manifest, runtime = r.validate_plan(args.plan, root=ROOT, require_frozen=False)
        validate_pair_contract(plan, r.read_json(plan['seed_plan_path']))
        result = [r.build_command(plan, manifest, runtime, row, 'PREVIEW__'+row['episode_key'])[0]
                  for row in plan['episodes']]
    else:
        plan = r.read_json(args.plan)
        r.require(plan.get('frozen') is True and Path(plan['worktree']).resolve() == ROOT,
                  'frozen authoritative plan required')
        r.verify_files(plan['code_files'], root=ROOT)
        validate_pair_contract(plan, r.read_json(plan['seed_plan_path']))
        support = load_support(ROOT)
        import audit_decision_evidence
        status = r.owned(args.status_path, plan['artifact_root'])
        status.parent.mkdir(parents=True, exist_ok=True)
        monitor = support.Monitor(r, ROOT, status.parent, episode_keys=KEYS)
        check = lambda: prerequisite(r, plan, ROOT)
        previous = signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
        entered_queue = False
        try:
            with support.shared_runner_lease(r, q, ROOT, status, args.plan, monitor, check, episode_keys=KEYS):
                events, resources = q.no_unfinished(ROOT)
                batch_budget(r, r.read_state(ROOT/'research-state.yaml'), events, resources, plan['episodes'],
                    r.read_events(ROOT/'data/gpu-hour-reservation-ledger.jsonl'))
                with support.supervise_calls(r, q, monitor, check), audited_calls(r, audit_decision_evidence.audit_episode):
                    entered_queue = True
                    result = q.run_queue(args.plan, KEYS, poll_seconds=30, idle_seconds=120,
                                         status_path=status, root=ROOT)
                    result = queue_summary(result, r)
        except BaseException as exc:
            if not entered_queue:
                r.durable_json(status, {'status': 'interrupted' if isinstance(exc, (KeyboardInterrupt, SystemExit)) else 'failed',
                    'episode_keys': KEYS, 'selected_physical_gpu': None,
                    'reason': str(exc) if isinstance(exc, r.GateError) else type(exc).__name__})
            raise
        finally:
            signal.signal(signal.SIGTERM, previous)
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    main()
