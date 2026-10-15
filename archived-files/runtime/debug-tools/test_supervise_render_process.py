"""CPU-only mocks of actual artifact supervisor helpers; never execute its dispatch body."""
import ast
import copy
from pathlib import Path
import os
import re
import signal
import subprocess
import time
from types import SimpleNamespace
import xml.etree.ElementTree as ET

import pytest

SCRIPT = Path(__file__).with_name('supervise-render-process.py')


class GateError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise GateError(message)


def helpers():
    tree = ast.parse(SCRIPT.read_text())
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    namespace = {'Path': Path, 'os': os, 'time': time, 'signal': signal, 'subprocess': subprocess,
        're': re, 'ET': ET, 'r': SimpleNamespace(require=require)}
    exec(compile(ast.Module(body=functions, type_ignores=[]), '<actual-supervisor-functions>', 'exec'), namespace)
    return namespace


def record(pid, ppid, role, *, ticks=None, pgid=100, state='S'):
    return dict(pid=pid, ppid=ppid, role=role, pgid=pgid, session_id=100,
        proc_start_ticks=str(ticks or pid), boot_id='abcd', state=state)


def family():
    parent = record(100, 50, 'model_parent')
    renderer = record(101, 100, 'renderer')
    auxiliary = record(102, 100, 'auxiliary_cpu')
    return {100: parent, 101: renderer, 102: auxiliary}


def cleanup_simulation(live, owned, *, kill_on=signal.SIGKILL):
    namespace = helpers()
    live, owned = copy.deepcopy(live), copy.deepcopy(owned)
    elapsed, signals = [0.0], []
    def killpg(pgid, signum):
        signals.append(('group', pgid, signum))
        if signum == kill_on:
            for pid in [pid for pid, item in live.items() if item['pgid'] == pgid]:
                del live[pid]
    def kill(pid, signum):
        signals.append(('pid', pid, signum))
        if signum == kill_on:
            live.pop(pid)
    result = namespace['cleanup_owned'](SimpleNamespace(poll=lambda: 0), owned,
        snapshot_fn=lambda: copy.deepcopy(live), clock=lambda: elapsed[0],
        sleep=lambda seconds: elapsed.__setitem__(0, elapsed[0] + seconds),
        killpg=killpg, kill=kill, timeout=18)
    return result, signals, live


def test_dead_leader_renderer_ignores_term_escalates_group_kill_including_cpu_tracker():
    owned = family()
    live = {pid: {**item, 'ppid': 1} for pid, item in owned.items() if pid != 100}
    result, signals, left = cleanup_simulation(live, owned)
    assert result['success'] and not left
    assert signals == [('group', 100, signal.SIGTERM), ('group', 100, signal.SIGKILL)]
    assert 9 <= result['elapsed_seconds'] < 18
    assert result['signals'][1]['pids'] == [101, 102]


def test_foreign_same_group_prevents_group_signal_and_is_not_killed():
    owned = family()
    live = {101: {**owned[101], 'ppid': 1}, 777: record(777, 1, 'foreign')}
    result, signals, left = cleanup_simulation(live, owned)
    assert not result['success'] and set(left) == {777}
    assert signals == [('pid', 101, signal.SIGTERM), ('pid', 101, signal.SIGKILL)]
    assert [item['pid'] for item in result['unverified_group_members']] == [777]


def test_reused_owned_pid_is_never_signalled_or_adopted():
    owned = family()
    live = {101: record(101, 1, 'foreign', ticks=999)}
    result, signals, left = cleanup_simulation(live, owned)
    assert not result['success'] and not signals and set(left) == {101}


def test_handshake_registers_renderer_but_auxiliary_and_unregistered_gpu_pids_are_rejected():
    ns, snapshot = helpers(), family()
    owned = {100: ns['identity'](snapshot[100])}
    handoff = {'schema': 'qd-ed-render-process-ownership-v1', 'resource_id': 'resource', 'contract_sha256': 'sha',
        'model_parent': ns['identity'](snapshot[100]), 'renderer': ns['identity'](snapshot[101])}
    ns['collect_owned'](owned, snapshot, handoff, resource_id='resource', contract_sha256='sha')
    assert {pid: item['role'] for pid, item in owned.items()} == {100: 'model_parent', 101: 'renderer', 102: 'auxiliary_cpu'}
    ns['validate_owned_liveness'](owned, snapshot)
    def xml(pids, uuid='GPU-frozen'):
        return '<nvidia_smi_log><gpu><uuid>' + uuid + '</uuid><processes>\n' + ''.join(
            f'<process_info><pid>{pid}</pid><type>G</type></process_info>' for pid in pids) + '</processes></gpu></nvidia_smi_log>'
    assert ns['validate_gpu_xml'](xml([100, 101]), 'GPU-frozen', owned, snapshot) == [100, 101]
    for pids in ([102], [777]):
        with pytest.raises(GateError, match='external or unverified'):
            ns['validate_gpu_xml'](xml(pids), 'GPU-frozen', owned, {**snapshot, 777: record(777, 1, 'foreign')})
    with pytest.raises(GateError, match='XML identity'):
        ns['validate_gpu_xml'](xml([], uuid='GPU-other'), 'GPU-frozen', owned, snapshot)
    bad = copy.deepcopy(handoff)
    bad['renderer']['ppid'] = 99
    with pytest.raises(GateError, match='invalid renderer'):
        ns['collect_owned'](owned, snapshot, bad, resource_id='resource', contract_sha256='sha')
    with pytest.raises(GateError, match='birth or group'):
        ns['validate_owned_liveness'](owned, {101: record(101, 1, 'renderer', ticks=999)})


def test_renderer_xid_is_retained_after_exit_but_foreign_gpu_or_reused_birth_not_attributed():
    ns, owned = helpers(), family()
    def row(pid, code=31, *, pci='0000:61:00', monotonic=2_000_000):
        return {'_BOOT_ID': 'ab-cd', '__CURSOR': f'{pid}-{code}', '__MONOTONIC_TIMESTAMP': str(monotonic),
            '__REALTIME_TIMESTAMP': '1790000000000000', 'MESSAGE': f'NVRM: Xid (PCI:{pci}): {code}, pid={pid}, name=python'}
    ns['collect_owned'](owned, {})  # Exited PIDs remain in the immutable history.
    faults = ns['owned_xids']([row(101), row(101, 109), row(100), row(777), row(101, pci='0000:a1:00')],
        owned, 'abcd', '00000000:61:00.0', clock_ticks=100)
    assert [(item['pid'], item['xid']) for item in faults] == [(101, 31), (101, 109), (100, 31)]
    ns['collect_owned'](owned, {101: record(101, 1, 'foreign', ticks=300)})
    assert ns['owned_xids']([row(101, monotonic=4_000_000)], owned, 'abcd', '0000:61:00', clock_ticks=100) == []


def test_proc_identity_parser_handles_command_parentheses_without_reading_environment(tmp_path):
    ns = helpers()
    folder = tmp_path / '321'
    folder.mkdir()
    fields = ['S', '100', '100', '100'] + ['0'] * 16
    fields[19] = '987654'
    (folder / 'stat').write_text('321 (name with ) paren) ' + ' '.join(fields))
    actual = ns['proc_table']('ab-cd', proc_root=tmp_path)[321]
    assert actual == {'pid': 321, 'ppid': 100, 'pgid': 100, 'session_id': 100,
        'proc_start_ticks': '987654', 'boot_id': 'abcd', 'state': 'S'}


@pytest.mark.parametrize('registered_before', [True, False])
def test_renderer_exit_or_durable_registration_during_gpu_query_is_not_foreign(registered_before):
    ns, initial = helpers(), family()
    owned = {100: ns['identity'](initial[100])}
    if registered_before:
        owned[101] = ns['identity'](initial[101])
    handoff = {'schema': 'qd-ed-render-process-ownership-v1', 'resource_id': 'resource', 'contract_sha256': 'sha',
        'model_parent': ns['identity'](initial[100]), 'renderer': ns['identity'](initial[101])}
    xml = '<nvidia_smi_log><gpu><uuid>GPU-frozen</uuid><processes><process_info><pid>101</pid><type>G</type></process_info></processes></gpu></nvidia_smi_log>'
    ns['proc_table'] = lambda boot: copy.deepcopy(initial)
    query_finished = []
    def run(command, **kwargs):
        assert command == ['nvidia-smi', '-q', '-x', '-i', '3']
        query_finished.append(True)
        return SimpleNamespace(returncode=0, stdout=xml)
    def refresh():
        assert query_finished
        after = {100: initial[100]}
        ns['collect_owned'](owned, after, handoff, resource_id='resource', contract_sha256='sha')
        return after
    assert ns['gpu_processes']('GPU-frozen', owned, 'abcd', run=run, refresh=refresh) == [101]
    # The pre-query identity cannot authorize a different process reusing its numeric PID.
    with pytest.raises(GateError, match='external or unverified'):
        ns['validate_gpu_xml'](xml, 'GPU-frozen', owned, {101: record(101, 1, 'foreign', ticks=999)}, before_snapshot=initial)


def test_cleanup_still_runs_when_final_ownership_record_fails_and_original_reason_is_preserved(tmp_path):
    tree = ast.parse(SCRIPT.read_text())
    dispatch_with = next(node for node in tree.body if isinstance(node, ast.With))
    dispatch_try = next(node for node in dispatch_with.body if isinstance(node, ast.Try))
    calls, saved = [], []
    def broken_refresh():
        raise GateError('synthetic ownership metadata failure')
    def cleanup(*args, **kwargs):
        calls.append('cleanup')
        return {'success': True, 'remaining_owned_pids': []}
    ns = {'time': SimpleNamespace(monotonic=lambda: 10, time=lambda: 1000), 'process': SimpleNamespace(poll=lambda: 0),
        'owned': family(), 'monitor_errors': [], 'refresh_owned': broken_refresh, 'cleanup_owned': cleanup,
        'read_faults': lambda *_: calls.append('kernel'), 'gpu_processes': lambda *_a, **_kw: [],
        'runtime': {'gpu_mapping': {'uuid': 'GPU-frozen'}}, 'boot': 'abcd', 'faults': [],
        'terminal': 'aborted', 'result': {'reason': 'original failure'}, 'base': {'resource_id': 'resource'},
        'started': 0, 'dispatched': True, 'output': tmp_path, 'ROOT': tmp_path, 'FOLDER': tmp_path,
        'resource_id': 'resource', 'json': __import__('json'),
        'r': SimpleNamespace(require=require, durable_json=lambda path, value: saved.append(copy.deepcopy(value)),
            append_healthcheck_event=lambda root, value: saved.append(copy.deepcopy(value))),
        'proc_table': lambda *_: {}, 'print': lambda *_a, **_kw: None}
    exec(compile(ast.Module(body=dispatch_try.finalbody, type_ignores=[]), '<actual-supervisor-finally>', 'exec'), ns)
    assert calls == ['cleanup', 'kernel']
    assert ns['result']['reason'] == 'original failure'
    assert ns['result']['gpu_process_wall_seconds'] == 10
    assert ns['result']['event'] == 'aborted' and len(ns['result']['final_monitor_errors']) == 2
