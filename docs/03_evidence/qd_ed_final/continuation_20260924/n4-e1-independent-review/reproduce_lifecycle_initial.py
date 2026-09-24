"""Pure fake-process reproductions for initial lifecycle source, not live CLI."""
from pathlib import Path
import sys
import hashlib
import pytest

S = Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-stage-lifecycle-20260924')
for rel, sha in {
    'core/codex_stage.py': 'dd5a9389934a09f638e6ba159b2d74a958849844a34fd26cb62e07d36ca16805',
    'core/codex_stage_lifecycle.py': 'be02ab0ca6e84c7045f6730e8ca46d1ed8db10bb8c9a9ed417a8e6f81117f21f',
}.items():
    assert hashlib.sha256((S / rel).read_bytes()).hexdigest() == sha
sys.path[:0] = [str(S), str(S / 'tests')]
from test_codex_stage import make, identify, module
from core.codex_stage_lifecycle import StageLifecycle


@pytest.mark.parametrize('point', ['constructor', 'after_spawn', 'finish'])
def test_initial_observer_fault_changes_original_success(monkeypatch, tmp_path, point):
    rec, calls = make(monkeypatch, tmp_path)
    stopped = []
    monkeypatch.setattr(module, '_stop_owned_process', lambda process: stopped.append(process))
    class FaultyObserver:
        def __init__(self, *args):
            if point == 'constructor':
                raise RuntimeError('synthetic_observer_failure')
            self.data = {}
        def mark(self, name):
            if point == 'after_spawn' and name == 'spawn_returned_at':
                raise RuntimeError('synthetic_observer_failure')
        def start(self, file):
            pass
        def finish(self, process):
            if point == 'finish':
                raise RuntimeError('synthetic_observer_failure')
    monkeypatch.setattr(module, 'StageLifecycle', FaultyObserver)
    assert identify(rec) == (1, True)  # uninstrumented fake succeeds (2,False)
    assert rec.last_result['codex_failed_calls'] == 1
    if point == 'after_spawn':
        assert len(calls) == 1 and not hasattr(calls[0], 'prompt')
        assert stopped == []  # spawned child is neither communicated nor cleaned
    if point == 'finish':
        assert rec.last_result['codex_completed_turns'] == 1


def test_initial_finish_join_has_no_time_bound():
    calls = []
    class Thread:
        ident = 1
        def join(self, *args, **kwargs):
            calls.append((args, kwargs))
    observer = StageLifecycle(64)
    observer._thread = Thread()
    observer.finish(None)
    assert calls == [((), {})]  # no timeout; a stalled reader can block forever
