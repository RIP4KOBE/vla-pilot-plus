import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from qd_ed_gpu_faults import KernelXidMonitor, MonitorError, pci_device
import qd_ed_final_runner as runner


def row(cursor, message, *, boot='boot'):
    return {'__CURSOR': cursor, '_BOOT_ID': boot, 'MESSAGE': message,
            '__REALTIME_TIMESTAMP': '1790060046058719'}


def xid(code=31, bus='0000:c1:00', pid=123):
    return f'NVRM: Xid (PCI:{bus}): {code}, pid={pid}, name=python, MMU Fault'


def monitor(tmp_path, batches):
    calls = []
    batches = iter([[row('before', xid())], *batches])
    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout='\n'.join(json.dumps(r) for r in next(batches)))
    item = KernelXidMonitor({'physical_gpu': 6, 'pci_bus_id': '00000000:C1:00.0'}, tmp_path, run=run)
    item.pid = 123
    return item, calls


def test_old_xid_other_gpu_and_unrelated_journal_do_not_trigger(tmp_path):
    item, calls = monitor(tmp_path, [[row('next', xid(bus='0000:e1:00')),
                                    row('last', 'private unrelated kernel text')], []])
    item.check()
    item.check()
    saved = json.loads((tmp_path / 'gpu-kernel-xid.json').read_text())
    assert saved['records'] == [] and saved['after_cursor'] == 'last'
    assert calls[1][-2:] == ['--after-cursor', 'before']
    assert calls[2][-2:] == ['--after-cursor', 'last']
    assert 'private' not in (tmp_path / 'gpu-kernel-xid.json').read_text()


@pytest.mark.parametrize('code,pid,matched', [(31,123,True), (109,456,False)])
def test_new_fault_is_saved_before_failure_with_pid_attribution(tmp_path, code, pid, matched):
    item, _ = monitor(tmp_path, [[row('fault', xid(code=code, pid=pid))]])
    with pytest.raises(MonitorError, match=f'Xid {code}'):
        item.check()
    saved = json.loads((tmp_path / 'gpu-kernel-xid.json').read_text())
    assert saved['records'][0]['xid'] == code
    assert saved['records'][0]['owned_pid_match'] is matched


def test_boot_change_is_not_silent_success(tmp_path):
    item, _ = monitor(tmp_path, [[row('wrong', xid(), boot='changed')]])
    with pytest.raises(MonitorError, match='identity changed'):
        item.check()


@pytest.mark.parametrize('kind', ['exit', 'timeout', 'malformed', 'empty'])
def test_unreadable_baseline_prevents_monitor_creation(tmp_path, kind):
    def run(*args, **kwargs):
        if kind == 'timeout':
            raise subprocess.TimeoutExpired('journalctl', 5)
        return SimpleNamespace(returncode=1 if kind=='exit' else 0,
                               stdout='not json' if kind=='malformed' else '')
    with pytest.raises(MonitorError):
        KernelXidMonitor({'physical_gpu':6, 'pci_bus_id':'0000:c1:00.0'}, tmp_path, run=run)


def test_runner_checks_fault_on_healthy_exit_and_records_infrastructure(tmp_path):
    item, _ = monitor(tmp_path, [[row('fault', xid())]])
    process = SimpleNamespace(wait=lambda **kwargs: 0)
    with pytest.raises(runner.GateError, match='GPU6 kernel monitor') as caught:
        runner.wait_exclusively(process, 30, physical_gpu=6, fault_monitor=item)
    event, outcome = runner.failed_outcome(caught.value, tmp_path, {})
    assert event=='aborted' and outcome['retryable_infrastructure']
    assert not outcome['outcome_valid'] and not outcome['task_failure']


def test_runner_checks_fault_during_wait_before_next_poll(tmp_path):
    item, _ = monitor(tmp_path, [[row('fault', xid(109))]])
    def wait(**kwargs):
        raise subprocess.TimeoutExpired('owned', 5)
    with pytest.raises(runner.GateError, match='Xid 109'):
        runner.wait_exclusively(SimpleNamespace(wait=wait), 30, physical_gpu=6, fault_monitor=item)


@pytest.mark.parametrize('value', ['0000:c1:00', '0000:c1:00.0', '00000000:C1:00.0'])
def test_pci_identity_normalization(value):
    assert pci_device(value) == '0000:c1:00'
