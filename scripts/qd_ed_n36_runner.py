"""Root-invoked N36 production adapter. No authority creation or automatic recovery."""
import sys
if __name__ == '__main__' and '_n36_source_bootstrap' not in sys.modules:
    raise RuntimeError('Launch N36 runner through qd_ed_n36_bootstrap.py')
import argparse
import datetime as dt
import hashlib
import os
from pathlib import Path
import signal
import subprocess
import time

from scripts import qd_ed_final_runner as r, qd_ed_n23_worker as w
from scripts import qd_ed_n36_contract as c, qd_ed_n36_bridge as b
from scripts import qd_ed_n36_release as release, qd_ed_n36_supervise as supervisor
from scripts import qd_ed_n36_worker as worker
from scripts import qd_ed_n36_source as source_execution
from scripts.qd_ed_n36r2_admission import owner_root, child_environment


# Reuse process ownership, timeout, probe and device helpers unchanged.
from scripts.qd_ed_n32_runner import (process_identity, cleanup_owned, wait_worker,
                                      journal_prefix, device_check, check_probe)


def snapshot(root, authority):
    for name, anchor in authority['ledger_prefixes'].items():
        w.require(name in {'attempt-ledger.jsonl', 'gpu-healthcheck-ledger.jsonl', 'gpu-hour-reservation-ledger.jsonl'}, 'unexpected ledger anchor')
        release.prefix(root / 'data' / name, anchor)
    w.require({'attempt-ledger.jsonl', 'gpu-healthcheck-ledger.jsonl'} <= set(authority['ledger_prefixes']), 'historical charge anchors missing')
    events = r.read_events(root / 'data/attempt-ledger.jsonl')
    resources = r.read_events(root / 'data/gpu-healthcheck-ledger.jsonl')
    reservations = r.read_events(root / 'data/gpu-hour-reservation-ledger.jsonl')
    return r.read_state(root / 'research-state.yaml'), events, resources, reservations


def existing_handles(plan, events):
    """Read only N36 output identities; never signal or infer a new PID owner."""
    groups = r.event_groups(events)
    unsettled = []
    for row in plan['episodes']:
        output = Path(w.read_ref(plan['expected_manifests'][row['episode_key']])['output_dir'])
        if not output.exists() and not output.is_symlink():
            continue
        group = groups.get(row['episode_key'])
        if not group or group[-1]['event'] not in r.TERMINAL:
            unsettled.append({'episode_key': row['episode_key'], 'status': 'ORPHAN_OR_UNSETTLED'})
            continue
        try:
            record = r.read_json(output / 'process.json')
            expected = {k: record[k] for k in ('pid', 'boot_id', 'proc_start_ticks')}
            try:
                actual = process_identity(record['pid'])
            except FileNotFoundError:
                continue
            if actual == expected:
                unsettled.append({'episode_key': row['episode_key'], 'status': 'LIVE'})
        except (OSError, ValueError, KeyError, TypeError, r.GateError):
            unsettled.append({'episode_key': row['episode_key'], 'status': 'UNKNOWN'})
    return unsettled


def execute_one(plan_ref, release_ref, *, _engineering=False):
    """One primary, or a read-only stop. Engineering is explicitly selected by its adapter.

    Legacy launch/main never selects this private route, and every route runs
    its own complete release validator before any operational work.
    """
    engineering = _engineering
    if engineering:
        from scripts import qd_ed_n36_engineering as api
        api.require_dispatch_implementation()
        lifecycle = api
        get_owner, environment = api.owner_root, api.child_environment
        binding, guard = api.operational_binding, api.launch_guard
    else:
        api, lifecycle = release, supervisor
        get_owner, environment = owner_root, child_environment
        binding, guard = c.operational_binding, c.launch_guard
    source_execution.active()
    plan, runtime, authority = api.validate_release(plan_ref, release_ref)
    source_root = Path(plan['worktree']).resolve()
    root = get_owner(plan)
    # The verified detached release binds this parent invocation to its plan.
    # Use the live parent identity, not a future episode child's identity.
    source_execution.attest(source_root, plan['source'], w.read_ref(plan['runtime_closure']),
        binding=worker.runtime_receipt_binding(release_ref, plan, w.process_identity(), 'runtime_before'))
    with r.locked(root / 'data/qd-ed-runner.lock', nonblocking=True):
        with r.locked(root / 'data/qd-ed-state.lock'):
            plan, runtime, authority = api.validate_release(plan_ref, release_ref)
            state, events, resources, reservations = snapshot(root, authority)
            w.require(state['run_name'] == plan['run_name'] and Path(state['artifacts']).resolve() == Path(runtime['artifact_root']).resolve(), 'owning run identity')
            def verify_existing(row, final):
                release.prefix(root / 'data/attempt-ledger.jsonl', final['ledger_prefix'])
                recorded = w.read_ref(c.ref(Path(final['output_dir']) / 'attempt-result.json'))
                w.require(recorded == final, 'terminal artifact/journal differs')
                return worker.verify_terminal(plan_ref, row, final, release_ref)
            if engineering:
                api.live_journals(plan, authority, events, resources, reservations)
            reconciled = lifecycle.reconcile(plan, events, verify_existing, live_handles=existing_handles(plan, events))
            if reconciled['next_row'] is None:
                return reconciled
            row = reconciled['next_row']
            # Reject every foreign or unknown unsettled handle, including reservations.
            w.require(all(g[-1]['event'] in r.TERMINAL for g in r.event_groups(events).values()), 'unsettled/live ledger')
            # STOP/time/accounting checked before even probing the device.
            api.admission(plan, authority, state, events, resources, reservations, row,
                              now=dt.datetime.now(dt.timezone.utc), gpu_idle=True, release_refs=(plan_ref, release_ref))
            if engineering:
                api.validate_readiness(plan_ref, w.read_ref(release_ref), resources=resources)
            elif c.cohort(plan) in c.SEPARATE_HEALTH_COHORTS:
                from scripts.qd_ed_n36r3_admission import validate_readiness
                validate_readiness(plan_ref, w.read_ref(release_ref), resources=resources)
            else:
                check_probe(runtime, resources, source_root)
            admission = device_check()
            env = environment(plan, runtime)
            r.verify_provider(runtime, env, root=source_root)
            r.runtime_gpu(runtime, state)
            plan, runtime, authority = api.validate_release(plan_ref, release_ref)
            state, current, resources, reservations = snapshot(root, authority)
            w.require(current == events, 'ledger changed under locks')
            admission = device_check()
            accounting = api.admission(plan, authority, state, current, resources, reservations, row,
                              now=dt.datetime.now(dt.timezone.utc), gpu_idle=True, release_refs=(plan_ref, release_ref))
            manifest = w.read_ref(plan['expected_manifests'][row['episode_key']])
            output = Path(manifest['output_dir'])
            r.owned(output, plan['artifact_root'])
            w.require(not output.exists() and not output.is_symlink(), 'output exists: no replay')
            # A deterministic key is unique across the entire journal, not just N36.
            w.require(not any(e['attempt_id'] == row['episode_key'] or e.get('episode_key') == row['episode_key'] for e in events), 'global attempt replay')
            output.mkdir(parents=True)
            context_path = output / 'n36-worker-context.json'
            w.atomic_json(context_path, worker.context_for(plan_ref, row, release_ref))
            context_ref = c.ref(context_path)
            command = worker_command(manifest['argv'][0], source_root, context_path, context_ref['sha256'])
            base = {**binding(plan), 'attempt_id': row['episode_key'], 'episode_key': row['episode_key'], 'identity': supervisor.c_identity(row),
                    'budget_bucket': row['budget_bucket'], 'replacement': row['replacement'], 'plan_sha256': plan_ref['sha256'], 'release': release_ref,
                    'source_commit': plan['source']['commit'], 'runtime_manifest_sha256': plan['runtime']['sha256'],
                    'runtime_inventory_sha256': plan['runtime_inventory_sha256'], 'init_row_sha256': row['init_row_sha256'],
                    'output_dir': str(output), 'physical_gpu': 7, 'retry_of': None, 'recovery_of': None,
                    'ledger_prefix': journal_prefix(root / 'data/attempt-ledger.jsonl'), 'context': context_ref,
                    'reserved_gpu_seconds':1840, 'accounting_admission':accounting['n36_reservation'], 'stage_backend': 'codex_cli', 'stage_model': 'gpt-6-astra', 'stage_condition': r.stage_condition(runtime)}
            r.append_event_locked(root, {**base, 'event': 'reserved', 'time_unix': time.time(), 'admission': admission})
            w.atomic_json(output / 'command.json', {'argv': command, 'main_argv': manifest['argv'], 'context': context_ref})
            # Recheck STOP after durable reservation. Rejection leaves an unsettled
            # primary for root review, never a retryable/zero-charge synthetic outcome.
            guard(plan, authority)
            r.append_event_locked(root, {**base, 'event': 'dispatched', 'time_unix': time.time(), 'timeout_seconds': 1800})
        started = time.monotonic()
        process = None
        process_finished = None
        identity = None
        outcome = None
        start_admitted = False
        try:
            with (output / 'runner.log').open('w') as log:
                guard(plan, authority)
                start_admitted = True
                process = subprocess.Popen(command, cwd=source_root, env=env, stdin=subprocess.PIPE, stdout=log,
                                           stderr=subprocess.STDOUT, start_new_session=True)
                identity = process_identity(process.pid)
                record = {**identity, 'attempt_id': row['episode_key'], 'context': context_ref, 'release': release_ref}
                w.atomic_json(output / 'process.json', record)
                process.stdin.write(b'G'); process.stdin.flush(); process.stdin.close()
                code = wait_worker(process, started, identity)
                process_finished = time.monotonic()
                w.require(code == 0, 'worker exit not zero')
            outcome = r.validate_result(output, row, b.profiles(source_root)['profiles'][row['profile']], runtime)
            outcome['n36_worker_receipt'] = c.ref(output / 'eds_eval/n36-worker-receipt.json')
            terminal = {**base, **outcome, 'event': 'valid', 'time_unix': time.time(),
                        'gpu_process_wall_seconds': (process_finished or time.monotonic()) - started}
            worker.verify_terminal(plan_ref, row, terminal, release_ref)
        except BaseException as exc:
            # A rejected final handoff remains unsettled for root reconciliation;
            # it is not a completed, zero-worker-cost synthetic attempt.
            if not start_admitted:
                raise
            if isinstance(exc, subprocess.TimeoutExpired) and exc.cmd == 'owned episode' and process is not None:
                w.require(identity is not None, 'missing owned child identity; leave unsettled')
                cleanup_owned(process, identity)
                process_finished = time.monotonic()
            # An unknown/live process stays dispatched and blocks every new launch.
            # Root reconciles its eventual cost; STOP/interrupt never kills it.
            if process is not None and process.poll() is None:
                raise
            _, outcome = r.failed_outcome(exc, output, row, launch_failed=process is None, runtime=runtime)
            outcome.update(outcome_valid=False, success=None, task_failure=False, retryable_infrastructure=False,
                           classification='INVALID', required_cost_telemetry_complete=False)
            terminal = {**base, **outcome, 'event': 'aborted', 'time_unix': time.time(),
                        'gpu_process_wall_seconds': (process_finished or time.monotonic()) - started}
        terminal['gpu_time_measurement'] = 'exclusive GPU7 process wall-time upper bound including audits and cleanup'
        with r.locked(root / 'data/qd-ed-state.lock'):
            r.append_event_locked(root, terminal)
            w.atomic_json(output / 'attempt-result.json', terminal)
        # Terminal is durably charged once before pausing. Invalidity keeps the
        # existing stop semantics; no later row or automatic recovery is allowed.
        status = 'INVALID_STOP' if terminal['outcome_valid'] is not True else (
            'PAUSED_FOR_ROOT_G3' if engineering or supervisor.first_c0_boundary(row) else 'VALID')
        return {'status': status, 'terminal': terminal, **(
            {'purpose': api.PURPOSE, 'scope_exhausted': True, 'continuation_authorized': False,
             'scientific_eligible': False, 'next_row': None, 'outcomes': []} if engineering else {})}


def worker_command(python, root, context_path, digest):
    return source_execution.command(python, root, 'scripts.qd_ed_n36_worker',
        '--context', str(context_path), '--context-sha256', digest)


def launch(plan_ref, release_ref):
    while True:
        result = execute_one(plan_ref, release_ref)
        if result['status'] != 'VALID':
            return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('plan', 'plan-sha256', 'release', 'release-sha256'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    for name in ('plan', 'release'):
        if not Path(getattr(args, name)).is_absolute():
            parser.error('--' + name + ' must be an absolute path')
    # Frozen references bind lexical paths, including symlinked parent directories.
    result = launch({'path': args.plan, 'sha256': args.plan_sha256},
                    {'path': args.release, 'sha256': args.release_sha256})
    print(result['status'])


if __name__ == '__main__':
    main()
