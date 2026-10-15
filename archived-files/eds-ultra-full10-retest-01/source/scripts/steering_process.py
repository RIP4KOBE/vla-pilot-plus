"""Owned worker cancellation for the launcher; no scientific runtime imports.

SIGINT/SIGTERM are handled. SIGKILL, host death, and descendants that escaped by
reparenting before discovery require an external supervisor and cannot be made
recoverable by a Python finally block. Partial results are never resumed here.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from datetime import datetime, timezone

import psutil


class LauncherInterrupted(BaseException):
    def __init__(self, signum):
        self.signum = signum
        super().__init__(f'Launcher received {signal.Signals(signum).name}')


def durable_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f'.interrupted-{os.getpid()}.tmp')
    with temporary.open('w') as file:
        json.dump(value, file, sort_keys=True, indent=2, allow_nan=False)
        file.write('\n'); file.flush(); os.fsync(file.fileno())
    os.replace(temporary, path)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class OwnedWorker:
    def __init__(self, *, grace_seconds=5.):
        self.proc = None
        self.root = None
        self.spawning = False
        self.signum = None
        self.grace_seconds = grace_seconds

    def interrupt(self, signum, frame):
        self.signum = self.signum or signum
        # Do not lose a child in the Popen-return/assignment window. This also
        # avoids inheriting a blocked signal mask in the worker.
        if not self.spawning:
            raise LauncherInterrupted(self.signum)

    def spawn(self, *args, **kwargs):
        if self.proc is not None:
            raise RuntimeError('One scientific worker per launcher; retries are forbidden')
        self.spawning = True
        try:
            self.proc = subprocess.Popen(*args, **kwargs, start_new_session=True)
            try:
                self.root = psutil.Process(self.proc.pid)
                self.root.create_time()  # Cache identity; psutil checks PID reuse on signals.
            except psutil.NoSuchProcess:
                self.root = None
        finally:
            self.spawning = False
        if self.signum is not None:
            raise LauncherInterrupted(self.signum)
        return self.proc

    def stop(self):
        known, errors = {}, []
        def remember(process):
            try:
                identity = (process.pid, process.create_time())
                if identity not in known:
                    known[identity] = process
                    process.suspend()
            except psutil.NoSuchProcess:
                pass
            except psutil.Error as exc:
                errors.append(dict(pid=process.pid, operation='suspend', error=type(exc).__name__))
        if self.root is not None:
            remember(self.root)
            # Stop newly discovered children before rescanning; descendants may
            # have their own sessions/process groups (e.g. a provider subprocess).
            for _ in range(16):
                before = len(known)
                for parent in list(known.values()):
                    try:
                        for child in parent.children(recursive=True): remember(child)
                    except psutil.NoSuchProcess:
                        pass
                    except psutil.Error as exc:
                        errors.append(dict(pid=parent.pid, operation='discover', error=type(exc).__name__))
                if len(known) == before: break
        processes = list(reversed(list(known.values())))
        for process in processes:
            try:
                process.terminate()
            except psutil.NoSuchProcess:
                pass
            except psutil.Error as exc:
                errors.append(dict(pid=process.pid, operation='terminate', error=type(exc).__name__))
            finally:
                try: process.resume()  # Deliver a pending SIGTERM to a stopped process.
                except psutil.NoSuchProcess: pass
                except psutil.Error as exc:
                    errors.append(dict(pid=process.pid, operation='resume', error=type(exc).__name__))
        _, alive = psutil.wait_procs(processes, timeout=self.grace_seconds)
        for process in alive:
            try: process.kill()
            except psutil.NoSuchProcess: pass
            except psutil.Error as exc:
                errors.append(dict(pid=process.pid, operation='kill', error=type(exc).__name__))
        psutil.wait_procs(alive, timeout=self.grace_seconds)
        if self.proc is not None:
            try: self.proc.wait(timeout=self.grace_seconds)
            except subprocess.TimeoutExpired:
                errors.append(dict(pid=self.proc.pid, operation='reap', error='TimeoutExpired'))
        survivors = []
        for identity, process in known.items():
            try:
                if process.is_running() and process.status() != psutil.STATUS_ZOMBIE:
                    survivors.append(dict(pid=identity[0], create_time=identity[1]))
            except psutil.NoSuchProcess: pass
            except psutil.Error as exc:
                errors.append(dict(pid=identity[0], operation='verify_exit', error=type(exc).__name__))
        return dict(scope='Captured owned descendant process identities only',
                    discovered_pids=sorted(p.pid for p in processes), survivors=survivors,
                    errors=errors, cleanup_complete=not survivors and not errors,
                    limits=['SIGKILL/host death cannot be handled.',
                            'Already-reparented escaped descendants require an external supervisor.'])


@contextmanager
def worker_lifecycle(folder, *, grace_seconds=5.):
    """Caller must have atomically claimed this new run directory before entry."""
    folder = Path(folder)
    owner = OwnedWorker(grace_seconds=grace_seconds)
    handled = (signal.SIGINT, signal.SIGTERM)
    old = {s: signal.getsignal(s) for s in handled}
    for signum in handled: signal.signal(signum, owner.interrupt)
    try:
        yield owner
    except BaseException as exc:
        # Finish owned cleanup/status writing even if the terminal sends a
        # second cancellation signal. Never signal unrelated sessions or GPUs.
        for signum in handled: signal.signal(signum, signal.SIG_IGN)
        cleanup = owner.stop()
        try: status = json.loads((folder/'status.json').read_text())
        except (OSError, ValueError): status = {'launcher_pid': os.getpid(), 'run_dir': str(folder)}
        interrupted = isinstance(exc, (LauncherInterrupted, KeyboardInterrupt))
        terminal = 'interrupted' if interrupted else ('preflight_failed' if status.get('state') == 'preflight_failed' else 'launcher_failed')
        status.update(state=terminal,
            completed_at=datetime.now(timezone.utc).isoformat(),
            exit_code=owner.proc.returncode if owner.proc is not None else None,
            launcher_signal=getattr(exc, 'signum', signal.SIGINT if isinstance(exc, KeyboardInterrupt) else None),
            error_type=type(exc).__name__, worker_cleanup=cleanup,
            partial_evidence_preserved=True, automatic_retry=False)
        durable_json(folder/'status.json', status)
        raise
    finally:
        for signum, handler in old.items(): signal.signal(signum, handler)
