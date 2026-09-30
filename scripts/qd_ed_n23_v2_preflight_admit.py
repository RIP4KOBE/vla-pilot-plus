#!/usr/bin/env python3
"""Closed one-attempt N23 v2 recovery admission. Never adopts an amendment."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from scripts import qd_ed_final_runner as runner
from scripts import qd_ed_n23_v2_contract as contract
from scripts import qd_ed_n23_worker as worker
from scripts import qd_ed_n23_v2_backend as backend


def diagnostic_row():
    return {'split': 'backend_diagnostic', 'iteration': contract.PREFLIGHT, 'profile': 'N23_backend',
            'task_id': -1, 'env_seed': -1, 'policy_seed': -1, 'init_index': -1,
            'episode_key': 'n23_backend_preflight_v2_once', 'budget_bucket': 'recovery', 'timeout_seconds': 120}


def admission(plan, state, events, resources, reservations, *, root=ROOT):
    contract.require_state(state, vars(runner))
    runner.require(plan['source'] == worker.source_record(root, contract.source_paths(vars(runner)))
        and plan['runtime'] == contract.ref(contract.GPU7_RUNTIME)
        and plan['predecessor_review'] == contract.predecessor_review(), 'N23 preflight source/runtime/prerequisite differs')
    contract.final_review(plan['source'], plan['runtime'])
    runtime = backend.validate_plan(plan)
    contract.validate_runtime(runtime, root, vars(runner))
    runner.require(Path(plan['artifact_root']).resolve() == Path(state['artifacts']).resolve()
        and Path(state.get('worktree', root)).resolve() == Path(root).resolve(), 'N23 private artifact/worktree differs')
    contract.cross_version_unused(events)
    runner.require(runner.check_budget(state, events, diagnostic_row(), resources, reservations, physical_gpu=7) == 120,
                   'N23 preflight requires full 120+40 reserve')
    contract.full_capacity(state, events, resources, vars(runner), preflight=True)
    return runtime


def gpu_gate(runtime, resources, *, root=ROOT):
    # Metadata enumeration and existing proof only; no provider verification,
    # model load, simulator reset or new CUDA/EGL probe is permitted here.
    if str(Path(root) / 'scripts') not in sys.path: sys.path.insert(0, str(Path(root) / 'scripts'))
    import qd_ed_available_gpu_queue as queue
    devices = queue.inventory()
    runner.require(7 in devices and devices[7]['uuid'] == contract.GPU7_UUID, 'N23 preflight GPU7 UUID differs')
    queue.reservation_admission(devices[7])
    runner.gpu_admission(physical_gpu=7, expected_uuid=contract.GPU7_UUID)
    mapping = queue.current_metadata(7, root=root)
    runner.require(queue.same_mapping(runtime['gpu_mapping'], mapping) and mapping.get('metadata_mapping_verified') is True,
                   'N23 preflight GPU/EGL metadata differs')
    proof = queue.find_probe(runtime, mapping, resources, root=root)
    runner.require(proof and proof.get('resource_id') == contract.GPU7_PROOF, 'N23 prior accounted probe missing')
    return {'physical_gpu': 7, 'uuid': contract.GPU7_UUID, 'reused_probe_resource_id': contract.GPU7_PROOF}


def run(plan_path, *, root=ROOT):
    root = Path(root).resolve(); plan_ref = contract.ref(plan_path); plan = worker.read_ref(plan_ref)
    with runner.locked(root / 'data/qd-ed-runner.lock', nonblocking=True):
        with runner.locked(root / 'data/qd-ed-state.lock'):
            events = runner.read_events(root / 'data/attempt-ledger.jsonl')
            resources = runner.read_events(root / 'data/gpu-healthcheck-ledger.jsonl')
            state = runner.read_state(root / 'research-state.yaml')
            runtime = admission(plan, state, events, resources,
                runner.read_events(root / 'data/gpu-hour-reservation-ledger.jsonl'), root=root)
            device = gpu_gate(runtime, resources, root=root)
            attempt_id = state['run_name'] + '__n23_backend_preflight_v2__' + uuid.uuid4().hex[:12]
            output = runner.owned(Path(plan['artifact_root']) / 'attempts' / attempt_id, plan['artifact_root'])
            runner.require(not output.exists(), 'N23 preflight output already exists')
            output.mkdir(parents=True)
            context = {'schema': 'n23-recovery-attempt-context-v2', 'attempt_id': attempt_id,
                'output_dir': str(output), 'budget_bucket': 'recovery', 'plan': plan_ref,
                'timeout_seconds': 120, 'cleanup_seconds': 40}
            release = {'schema': 'n23-backend-preflight-release-v2', 'plan': plan_ref,
                'source': plan['source'], 'runtime': plan['runtime'], 'limits': backend.LIMITS,
                'attempt_id': attempt_id, 'predecessor_review': plan['predecessor_review']}
            worker.atomic_json(output / 'attempt-context.json', context)
            worker.atomic_json(output / 'release.json', release)
            row = diagnostic_row()
            base = {'attempt_id': attempt_id, 'identity': runner.episode_identity(row),
                'episode_key': row['episode_key'], 'budget_bucket': 'recovery', 'output_dir': str(output),
                'plan_sha256': plan_ref['sha256'], 'source_commit': plan['source']['commit'],
                'runtime_manifest_sha256': plan['runtime']['sha256'], 'physical_gpu': 7,
                'n23_backend_preflight': True, 'task_outcome': False,
                'n23_final_review': contract.ref(contract.FINAL_REVIEW), 'retry_of': None}
            runner.append_event_locked(root, {**base, 'event': 'reserved', 'time_unix': time.time(), 'admission': device})
        command = backend.command(runner.PYTHON, plan_path, output / 'release.json', output / 'attempt-context.json', root=root)
        worker.atomic_json(output / 'command.json', {'argv': command})
        process = None; dispatched = False; started = time.monotonic(); finished = None
        outcome = {'event': 'aborted', 'outcome_valid': False, 'retryable_infrastructure': False}
        identity = None; failure = None
        try:
            gpu_gate(runtime, resources, root=root)
            # Atomic charge before Popen; failures to start remain charged.
            with runner.locked(root / 'data/qd-ed-state.lock'):
                state = runner.read_state(root / 'research-state.yaml'); contract.require_state(state, vars(runner))
                runner.require(runner.check_budget(state, runner.read_events(root / 'data/attempt-ledger.jsonl'), row,
                    runner.read_events(root / 'data/gpu-healthcheck-ledger.jsonl'),
                    runner.read_events(root / 'data/gpu-hour-reservation-ledger.jsonl'), physical_gpu=7) == 120,
                    'N23 preflight reserve changed before charge')
                runner.append_event_locked(root, {**base, 'event': 'dispatched', 'time_unix': time.time(), 'timeout_seconds': 120})
            dispatched = True; started = time.monotonic()
            with (output / 'runner.log').open('w') as log:
                process = subprocess.Popen(command, cwd=root, env=runner.child_environment(runtime),
                                           stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                identity = {'pid': process.pid,
                    'proc_start_ticks': Path(f'/proc/{process.pid}/stat').read_text().rsplit(')', 1)[1].split()[19],
                    'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
                worker.atomic_json(output / 'process.json', {**identity, 'attempt_id': attempt_id})
                code = runner.wait_exclusively(process, 120, physical_gpu=7); finished = time.monotonic()
            runner.require(code == 0, f'N23 backend worker exit {code}')
            report = output / 'n23-backend-preflight-report.json'
            proposal = {**base, 'event': 'valid', 'outcome_valid': True, 'process': identity,
                'gpu_process_wall_seconds': finished - started, 'backend_preflight_report': contract.ref(report)}
            backend.verify_preflight_proof(plan_path, report, proposal, plan['source'])
            outcome = {**proposal, 'backend_ready': True}
        except BaseException as exc:
            failure = exc
            outcome.update(reason=type(exc).__name__, detail=str(exc) if isinstance(exc, runner.GateError) else type(exc).__name__)
        finally:
            try:
                runner.terminate_owned(process)
            except BaseException as exc:
                failure = failure or exc
                outcome.update(event='aborted', outcome_valid=False, cleanup_error=type(exc).__name__)
                finished = None
            elapsed = (finished or time.monotonic()) - started if dispatched else 0.
            terminal = {**base, **outcome, 'process': identity, 'time_unix': time.time(),
                'gpu_process_wall_seconds': elapsed, 'n23_preflight_dispatched': dispatched,
                'gpu_time_measurement': 'exclusive GPU7 whole worker wall including arithmetic audit and abort cleanup'}
            runner.append_event(root, terminal); runner.durable_json(output / 'attempt-result.json', terminal)
        if failure: raise failure
        runner.require(terminal['event'] == 'valid' and terminal['outcome_valid'], 'N23 backend invalid; no retry')
        worker.atomic_json(output / 'backend-proof-reference.json', {
            'plan': plan_ref, 'report': terminal['backend_preflight_report'], 'attempt_id': attempt_id})
        return terminal


def reconcile(plan_path, attempt_id, *, root=ROOT):
    """Explicitly close a dead interrupted preflight, never retry or infer success."""
    root = Path(root).resolve(); plan = worker.read_ref(contract.ref(plan_path))
    with runner.locked(root / 'data/qd-ed-runner.lock', nonblocking=True):
        events = runner.read_events(root / 'data/attempt-ledger.jsonl')
        groups = runner.event_groups(events)
        runner.require(attempt_id in groups, 'unknown N23 preflight attempt')
        group = groups[attempt_id]; base = group[0]
        runner.require(base.get('n23_backend_preflight') is True
            and base.get('identity', {}).get('iteration') == contract.PREFLIGHT
            and base.get('plan_sha256') == worker.sha(plan_path), 'N23 interrupted preflight identity differs')
        if group[-1]['event'] in runner.TERMINAL:
            with runner.locked(root / 'data/qd-ed-state.lock'):
                runner.sync_state_from_journal(root, events)
            return group[-1]
        for proc in Path('/proc').iterdir():
            if not proc.name.isdigit(): continue
            try: args = (proc / 'cmdline').read_bytes().split(b'\0')
            except (FileNotFoundError, ProcessLookupError, PermissionError): continue
            runner.require(not (str(root / 'main.py').encode() in args
                and any(attempt_id.encode() in arg for arg in args)), 'N23 preflight child is still alive')
        runner.gpu_admission(physical_gpu=7, expected_uuid=contract.GPU7_UUID)
        output = runner.owned(base['output_dir'], plan['artifact_root'])
        dispatched = next((e for e in group if e['event'] == 'dispatched'), None)
        terminal = {**base, 'event': 'aborted', 'outcome_valid': False, 'retryable_infrastructure': False,
            'task_outcome': False, 'time_unix': time.time(), 'reason': 'dead interrupted backend preflight; no retry',
            'gpu_process_wall_seconds': max(0., time.time() - dispatched['time_unix']) if dispatched else 0.,
            'gpu_time_measurement': 'conservative charge through explicit dead-process reconciliation',
            'n23_preflight_dispatched': dispatched is not None}
        runner.append_event(root, terminal); runner.durable_json(output / 'attempt-result.json', terminal)
        return terminal


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--plan', type=Path, required=True)
    p.add_argument('--reconcile-attempt', help='Close only this provably dead interrupted preflight, never relaunch')
    args = p.parse_args()
    result = reconcile(args.plan, args.reconcile_attempt) if args.reconcile_attempt else run(args.plan)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    main()
