from pathlib import Path
import subprocess
import sys
import pytest
sys.path.insert(0, '/home/hynx/VLA-Pilot++/.worktree/exp/rdt-qd-ed-gpu6-20260922T063626Z/scripts')
import qd_ed_final_runner as r
import n1t_cohort_queue as module


def competing(path):
    script = 'import fcntl,sys\nf=open(sys.argv[1],"a+")\ntry: fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)\nexcept BlockingIOError: sys.exit(7)\n'
    return subprocess.run([sys.executable,'-c',script,str(path)],check=False).returncode


def test_outer_lease_excludes_competitors_between_nested_calls(tmp_path):
    path=tmp_path/'runner.lock';original=r.locked
    with module.held_runner_lease(r,path):
        assert competing(path)==7
        for _ in range(2):
            with r.locked(path,nonblocking=True):assert competing(path)==7
            assert competing(path)==7
    assert r.locked is original and competing(path)==0


def test_state_lock_and_symlink_aliases_remain_exclusive(tmp_path):
    path=tmp_path/'runner.lock';alias=tmp_path/'alias';alias.symlink_to(path)
    state=tmp_path/'state.lock'
    with module.held_runner_lease(r,path):
        with r.locked(alias,nonblocking=True):assert competing(path)==7
        with r.locked(state):
            assert competing(state)==7
            with pytest.raises(r.LockBusyError):
                with r.locked(state,nonblocking=True):pass
        assert competing(state)==0


def test_exception_restores_original_lock_and_releases_lease(tmp_path):
    path=tmp_path/'runner.lock';original=r.locked
    with pytest.raises(RuntimeError):
        with module.held_runner_lease(r,path):raise RuntimeError('test')
    assert r.locked is original and competing(path)==0


def test_busy_outer_lock_does_not_patch_lock_function(tmp_path):
    path=tmp_path/'runner.lock';original=r.locked
    with original(path):
        with pytest.raises(r.LockBusyError) as exc:
            with module.held_runner_lease(r,path):pass
        assert exc.value.lock_path==path.resolve()
        assert r.locked is original


def test_reentrant_lock_rejects_different_pid(tmp_path,monkeypatch):
    path=tmp_path/'runner.lock'
    with module.held_runner_lease(r,path):
        owner=module.os.getpid();monkeypatch.setattr(module.os,'getpid',lambda:owner+1)
        with pytest.raises(r.GateError,match='PID'):
            with r.locked(path):pass


def test_reentrant_lock_rejects_replaced_inode(tmp_path):
    path=tmp_path/'runner.lock'
    with module.held_runner_lease(r,path):
        replacement=tmp_path/'replacement';replacement.touch();replacement.replace(path)
        with pytest.raises(r.GateError,match='inode'):
            with r.locked(path):pass
