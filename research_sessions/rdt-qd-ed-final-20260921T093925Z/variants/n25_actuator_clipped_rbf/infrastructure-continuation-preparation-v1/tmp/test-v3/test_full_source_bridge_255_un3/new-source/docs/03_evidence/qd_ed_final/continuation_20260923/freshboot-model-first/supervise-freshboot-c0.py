#!/usr/bin/env python3
"""Single prospective C0 queue with boot and owned-PID Xid observation.

No independent child launcher, termination or ledger writer: errors propagate to
the original runner's existing except/finally and shared accounting. Imports of
the runner/queue are delayed until main so CPU tests need no GPU dependencies.
"""
import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading
import time

ROOT = Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z')
BOOT = '2a1fa95f-ab0d-488c-a298-fc488ddd2af7'
KEY = 'freshboot_c0_t00_20260923'
ITERATION = 'FRESHBOOT_C0_20260923'
GPU_UUID = 'GPU-62052fa1-37e0-79dc-21aa-5c0f25c0c315'
PCI = '0000:61:00'
JOURNAL_TIMEOUT = 5
DEPENDENCY_FREEZE = 'docs/03_evidence/qd_ed_final/continuation_20260923/freshboot-model-first/native-dependency-freeze.json'
XID = re.compile(r'^NVRM: Xid \(PCI:([0-9a-fA-F:.]+)\):\s*(\d+),.*?\bpid=(\d+),')


def normalize_boot(value): return str(value).replace('-', '').lower()


class Monitor:
    def __init__(self, runner, root, folder, *, proc=Path('/proc'), run=subprocess.run,
                 parent_pid=None, ticks_per_second=None):
        self.r, self.root, self.folder = runner, Path(root), Path(folder)
        self.proc, self.run = Path(proc), run
        self.parent_pid = os.getpid() if parent_pid is None else parent_pid
        self.ticks_per_second = os.sysconf('SC_CLK_TCK') if ticks_per_second is None else ticks_per_second
        self.baseline = None
        self.active = None
        self.faults = []

    def require_boot(self):
        try:
            actual = self.proc.joinpath('sys/kernel/random/boot_id').read_text().strip()
        except OSError:
            raise self.r.GateError('GPU3 boot identity unavailable') from None
        self.r.require(actual == BOOT,
                       'GPU3 fresh-boot identity differs')

    def rows(self, extra):
        self.require_boot()
        try:
            result = self.run(['journalctl', '-k', '-b', '--no-pager', '-o', 'json', *extra],
                              capture_output=True, text=True, timeout=JOURNAL_TIMEOUT, check=True)
            rows = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
        except (OSError, subprocess.SubprocessError, ValueError):
            raise self.r.GateError('GPU3 owned-Xid journal query unavailable') from None
        self.r.require(all(normalize_boot(row.get('_BOOT_ID')) == normalize_boot(BOOT) for row in rows),
                       'GPU3 kernel journal boot differs')
        return rows

    def admission(self):
        rows = self.rows(['-n', '1'])
        self.r.require(len(rows) == 1 and rows[0].get('__CURSOR'), 'GPU3 kernel admission cursor missing')
        self.baseline = rows[0]['__CURSOR']
        self.r.durable_json(self.folder / 'kernel-admission.json',
            {'boot_id': BOOT, 'cursor': self.baseline, 'physical_gpu': 3, 'time_unix': time.time()})

    def proc_identity(self, pid):
        fields = self.proc.joinpath(str(pid), 'stat').read_text().rsplit(')', 1)[1].split()
        return {'pid': pid, 'ppid': int(fields[1]), 'pgid': int(fields[2]),
                'session_id': int(fields[3]), 'proc_start_ticks': int(fields[19]), 'boot_id': BOOT}

    def bind(self, process, physical_gpu):
        self.require_boot()
        self.r.require(physical_gpu == 3 and self.baseline is not None, 'GPU3 owned monitor admission missing')
        try:
            identity = self.proc_identity(process.pid)
        except (OSError, ValueError, IndexError):
            raise self.r.GateError('GPU3 owned child process identity unavailable') from None
        self.r.require(identity['ppid'] == self.parent_pid and identity['pgid'] == process.pid
            and identity['session_id'] == process.pid and identity['proc_start_ticks'] > 0,
            'GPU3 owned child ancestry/session differs')
        matches = []
        # The unchanged queue may need its existing accounted zero-step binding
        # probe. Observe that direct child too, without adding a model probe.
        for ledger, kind in [('attempt-ledger.jsonl', 'episode'), ('gpu-healthcheck-ledger.jsonl', 'binding_probe')]:
            for event in self.r.read_events(self.root / 'data' / ledger):
                if event.get('event') != 'dispatched' or event.get('physical_gpu') != 3:
                    continue
                if kind == 'episode' and event.get('episode_key') != KEY:
                    continue
                if kind == 'binding_probe' and event.get('kind') != 'cuda_egl_probe':
                    continue
                output = Path(event['output_dir'])
                process_path = output / 'process.json'
                if not process_path.exists():
                    continue
                saved = self.r.read_json(process_path)
                if saved.get('pid') == process.pid and str(saved.get('proc_start_ticks')) == str(identity['proc_start_ticks']):
                    self.r.require(saved.get('boot_id') == BOOT, 'GPU3 owned child saved boot differs')
                    matches.append((output, event, kind))
        self.r.require(len(matches) == 1, 'GPU3 owned child ledger/process linkage missing or ambiguous')
        output, event, kind = matches[0]
        self.active = {**identity, 'kind': kind, 'physical_gpu': 3, 'pci': PCI,
            'attempt_id': event.get('attempt_id'), 'resource_id': event.get('resource_id'),
            'output_dir': str(output), 'cursor': self.baseline}
        self.faults = []
        self.persist()

    def persist(self):
        self.r.durable_json(Path(self.active['output_dir']) / 'freshboot-kernel-monitor.json',
            {**self.active, 'faults': list(self.faults), 'updated_unix': time.time()})

    def poll(self, process):
        self.r.require(self.active is not None and self.active['pid'] == process.pid,
                       'GPU3 owned monitor process differs')
        self.require_boot()
        try:
            live = self.proc_identity(process.pid)
        except FileNotFoundError:
            self.r.require(process.returncode is not None, 'GPU3 owned child disappeared before wait completion')
        except (OSError, ValueError, IndexError):
            raise self.r.GateError('GPU3 owned child process identity unavailable') from None
        else:
            self.r.require(all(live[key] == self.active[key] for key in ('pid', 'ppid', 'pgid', 'session_id', 'proc_start_ticks')),
                           'GPU3 owned child identity changed')
        for row in self.rows(['--after-cursor', self.active['cursor']]):
            self.r.require(bool(row.get('__CURSOR')), 'GPU3 kernel row cursor missing')
            self.active['cursor'] = row['__CURSOR']
            match = XID.match(row.get('MESSAGE', ''))
            if match is None or match.group(1).lower() != PCI or int(match.group(3)) != process.pid:
                continue
            try:
                stamp = int(row['__MONOTONIC_TIMESTAMP'])
                realtime = int(row['__REALTIME_TIMESTAMP'])
            except (KeyError, ValueError, TypeError):
                raise self.r.GateError('GPU3 owned Xid timestamp unavailable') from None
            # Do not attribute an earlier lifetime of a reused numeric PID.
            if stamp * self.ticks_per_second < self.active['proc_start_ticks'] * 1_000_000:
                continue
            self.faults.append({'xid': int(match.group(2)), 'pid': process.pid, 'pci': PCI,
                'boot_id': BOOT, 'monotonic_us': stamp, 'realtime_us': realtime})
        self.persist()
        self.r.require(not self.faults, 'GPU3 owned process Xid detected; see sanitized kernel monitor evidence')


class ObservedWait:
    """Delegate original process behavior; check kernel after every wait outcome."""
    def __init__(self, process, monitor):
        self.process, self.monitor = process, monitor

    def __getattr__(self, name): return getattr(self.process, name)

    def wait(self, timeout=None):
        try:
            result = self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.monitor.poll(self.process)
            raise
        self.monitor.poll(self.process)
        return result


@contextmanager
def supervise_calls(r, q, monitor, prerequisite):
    admission, wait, pending = r.gpu_admission, r.wait_exclusively, q.pending_gate
    def guarded_pending(*args, **kwargs):
        monitor.require_boot()
        prerequisite()
        return pending(*args, **kwargs)
    def guarded_admission(*args, **kwargs):
        monitor.require_boot()
        prerequisite()
        r.require(kwargs.get('physical_gpu') == 3, 'GPU3-only admission required')
        result = admission(*args, **kwargs)
        monitor.admission()
        return result
    def guarded_wait(process, timeout, *, physical_gpu=7):
        monitor.bind(process, physical_gpu)
        return wait(ObservedWait(process, monitor), timeout, physical_gpu=physical_gpu)
    r.gpu_admission, r.wait_exclusively, q.pending_gate = guarded_admission, guarded_wait, guarded_pending
    try:
        yield
    finally:
        r.gpu_admission, r.wait_exclusively, q.pending_gate = admission, wait, pending


@contextmanager
def shared_runner_lease(r, q, root, status_path, plan_path, monitor, prerequisite,
                        *, sleep=time.sleep, poll_seconds=30):
    """Hold the real shared flock across the queue's idle window and one C0.

    Only this process/thread's nested use of this exact inode is reentrant.
    All other locks and callers retain the original runner implementation.
    """
    r.require(type(poll_seconds) is int and 1 <= poll_seconds <= 30,
              'shared runner poll interval must be 1..30 seconds')
    root, status_path = Path(root), Path(status_path)
    lock_path = (root / 'data/qd-ed-runner.lock').resolve()
    original_locked = r.locked
    owner_pid, owner_thread = os.getpid(), threading.get_ident()
    acquired = yielded = patched = False
    status = {'schema': 'qd-ed-available-gpu-queue-v1', 'pid': owner_pid,
              'base_plan_path': str(Path(plan_path).resolve()), 'episode_keys': [KEY],
              'completed_keys': [], 'results': [], 'selected_physical_gpu': None,
              'boot_id': BOOT, 'runner_lock_path': str(lock_path)}

    def save(phase, **values):
        status.update(status=phase, updated_unix=time.time(), **values)
        r.durable_json(status_path, status)

    try:
        with lock_path.open('a+') as stream:
            try:
                while True:
                    monitor.require_boot()
                    prerequisite()
                    try:
                        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        save('waiting_shared_runner')
                        sleep(poll_seconds)
                        continue
                    acquired = True
                    break

                def verify_lease():
                    r.require(os.getpid() == owner_pid and threading.get_ident() == owner_thread,
                              'shared runner lease owner differs')
                    held, current = os.fstat(stream.fileno()), lock_path.stat()
                    r.require((held.st_dev, held.st_ino) == (current.st_dev, current.st_ino),
                              'shared runner lock inode changed')
                    # Same open-file description: no unlock/relock gap. If an
                    # unexpected unlock occurred, this still cannot bypass a
                    # competing holder of the original lock.
                    try:
                        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        raise r.GateError('shared runner lease no longer held') from None

                @contextmanager
                def nested_locked(path, *, nonblocking=False):
                    if (Path(path).resolve() == lock_path and os.getpid() == owner_pid
                            and threading.get_ident() == owner_thread):
                        verify_lease()
                        yield
                        verify_lease()
                    else:
                        with original_locked(path, nonblocking=nonblocking):
                            yield

                verify_lease()
                monitor.require_boot()
                prerequisite()
                # Acquiring a released lock does not authorize reconciliation
                # of an orphan reservation. Reject it before any state write.
                with original_locked(root / 'data/qd-ed-state.lock'):
                    events, _ = q.no_unfinished(root)
                    r.sync_state_from_journal(root, events)
                held = os.fstat(stream.fileno())
                save('shared_runner_acquired', runner_lock_device=held.st_dev,
                     runner_lock_inode=held.st_ino, owner_thread_id=owner_thread)
                r.locked = nested_locked
                patched = True
                yielded = True
                yield
            finally:
                if patched:
                    r.locked = original_locked
                if acquired:
                    fcntl.flock(stream, fcntl.LOCK_UN)
    except BaseException as exc:
        # Once the queue is entered its existing error/finally owns status,
        # termination and accounting. Here only pre-queue failures are saved.
        if not yielded:
            save('interrupted' if isinstance(exc, (KeyboardInterrupt, SystemExit)) else 'failed',
                 reason=str(exc) if isinstance(exc, r.GateError) else type(exc).__name__)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--status-path', type=Path, required=True)
    args = parser.parse_args(argv)
    sys.path.insert(0, str(ROOT / 'scripts'))
    import qd_ed_final_runner as r
    import qd_ed_available_gpu_queue as q
    plan = r.read_json(args.plan)
    r.require(plan.get('frozen') is True and plan.get('boot_id') == BOOT, 'frozen fresh-boot plan required')
    r.require(plan['phase_authorization'] == {'dev': True, 'validation': False, 'formal': False}
        and len(plan['episodes']) == 1, 'single dev episode authorization required')
    row = plan['episodes'][0]
    expected = {'episode_key': KEY, 'iteration': ITERATION, 'profile': 'C0', 'split': 'dev',
        'seed_block': 'dev', 'task_id': 0, 'env_seed': 1969522881, 'policy_seed': 1969522881,
        'init_index': 0, 'timeout_seconds': 1800, 'budget_bucket': 'development'}
    r.require(all(row.get(key) == value for key, value in expected.items()) and not row.get('retry_of'), 'prospective C0 identity differs')
    own = str(Path(__file__).resolve().relative_to(ROOT))
    r.require(any(record['path'] == own and record['sha256'] == r.digest(__file__) for record in plan['code_files']), 'supervisor source is not frozen')
    runtime = r.read_json(plan['runtime_manifest_path'])
    r.require(runtime['gpu_mapping']['physical_gpu'] == 3 and runtime['gpu_mapping']['uuid'] == GPU_UUID
        and runtime['gpu_mapping']['egl_device_index'] == 0, 'GPU3 runtime mapping differs')
    status = r.owned(args.status_path, plan['artifact_root'])
    status.parent.mkdir(parents=True, exist_ok=True)
    reference = plan['engineering_prerequisite']
    def prerequisite():
        dependency_path = ROOT / DEPENDENCY_FREEZE
        r.require(any(record['path'] == DEPENDENCY_FREEZE and record['sha256'] == r.digest(dependency_path)
            for record in plan['code_files']), 'GPU3 native dependency snapshot is not frozen')
        r.verify_files(r.read_json(dependency_path)['files'])
        for label in ('result', 'contract'):
            path = r.owned(reference[label + '_path'], plan['artifact_root'])
            r.require(r.digest(path) == reference[label + '_sha256'], 'GPU3 prerequisite fingerprint changed')
        proof = r.read_json(reference['result_path'])
        contract = r.read_json(reference['contract_path'])
        r.require(proof['event'] == 'completed' and not proof.get('faults') and
            proof['resource_id'] == contract['resource_id'] == reference['resource_id'] and
            proof['contract_sha256'] == reference['contract_sha256'] and
            proof['boot_id'] == contract['boot_id'] == reference['boot_id'] == BOOT,
            'GPU3 fresh-boot prerequisite completion differs')
    monitor = Monitor(r, ROOT, status.parent)
    monitor.require_boot()
    prerequisite()
    def interrupted(*_):
        raise KeyboardInterrupt()
    previous_sigterm = signal.signal(signal.SIGTERM, interrupted)
    try:
        with shared_runner_lease(r, q, ROOT, status, args.plan, monitor, prerequisite):
            with supervise_calls(r, q, monitor, prerequisite):
                return q.run_queue(args.plan, [KEY], poll_seconds=30, idle_seconds=120,
                                   status_path=status, root=ROOT)
    finally:
        signal.signal(signal.SIGTERM, previous_sigterm)


if __name__ == '__main__':
    main()
