"""CPU mocks only: no child process, GPU, provider or simulator is launched."""
import contextlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('freshboot_c0_supervisor', HERE / 'supervise-freshboot-c0.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)
sys.path.insert(0, str(s.ROOT / 'scripts'))
import qd_ed_final_runner as r


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def monitor(self, rows):
        run = Mock(return_value=SimpleNamespace(stdout='\n'.join(json.dumps(row) for row in rows)))
        m = s.Monitor(r, self.folder, self.folder, run=run, parent_pid=10, ticks_per_second=100)
        m.require_boot = Mock()
        m.proc_identity = Mock(return_value={'pid': 42, 'ppid': 10, 'pgid': 42,
            'session_id': 42, 'proc_start_ticks': 100, 'boot_id': s.BOOT})
        m.active = {**m.proc_identity(), 'cursor': 'baseline', 'output_dir': str(self.folder)}
        return m, run

    def row(self, message, cursor='next', monotonic=2_000_000, boot=s.BOOT):
        return {'_BOOT_ID': s.normalize_boot(boot), '__CURSOR': cursor, 'MESSAGE': message,
            '__MONOTONIC_TIMESTAMP': str(monotonic), '__REALTIME_TIMESTAMP': '123456789'}

    def test_only_exact_owned_pci_pid_lifetime_faults(self):
        rows = [self.row('NVRM: Xid (PCI:0000:41:00): 31, pid=42, irrelevant', 'other-gpu'),
            self.row('NVRM: Xid (PCI:0000:61:00): 31, pid=99, irrelevant', 'external-pid'),
            self.row('NVRM: Xid (PCI:0000:61:00): 31, pid=42, old lifetime', 'old', 1),
            self.row('unrelated kernel message with private material', 'irrelevant')]
        m, run = self.monitor(rows)
        m.poll(SimpleNamespace(pid=42, returncode=None))
        self.assertEqual(m.faults, [])
        self.assertEqual(run.call_args.kwargs['timeout'], 5)
        run.return_value.stdout = json.dumps(self.row('NVRM: Xid (PCI:0000:61:00): 31, pid=42, private name'))
        with self.assertRaisesRegex(r.GateError, 'GPU3 owned process Xid'):
            m.poll(SimpleNamespace(pid=42, returncode=None))
        evidence = (self.folder / 'freshboot-kernel-monitor.json').read_text()
        self.assertNotIn('private', evidence)
        self.assertEqual(json.loads(evidence)['faults'][0]['xid'], 31)

    def test_boot_or_pid_reuse_stops_before_query(self):
        m, run = self.monitor([])
        m.proc_identity.return_value['proc_start_ticks'] = 101
        with self.assertRaisesRegex(r.GateError, 'identity changed'):
            m.poll(SimpleNamespace(pid=42, returncode=None))
        run.assert_not_called()
        m, run = self.monitor([self.row('unrelated', boot='other-boot')])
        with self.assertRaisesRegex(r.GateError, 'journal boot differs'):
            m.poll(SimpleNamespace(pid=42, returncode=None))

    def test_query_failure_is_sanitized_infrastructure_gate(self):
        m, run = self.monitor([])
        run.side_effect = subprocess.TimeoutExpired(['journalctl', 'private'], 5, output='private output')
        with self.assertRaisesRegex(r.GateError, '^GPU3 owned-Xid journal query unavailable$'):
            m.poll(SimpleNamespace(pid=42, returncode=None))

    def test_original_wait_timeout_and_fast_exit_both_observed(self):
        timeout = subprocess.TimeoutExpired('owned episode', 5)
        process = SimpleNamespace(pid=42, wait=Mock(side_effect=[timeout, 0]))
        monitor = SimpleNamespace(poll=Mock())
        proxy = s.ObservedWait(process, monitor)
        with self.assertRaises(subprocess.TimeoutExpired) as caught:
            proxy.wait(timeout=5)
        self.assertIs(caught.exception, timeout)
        self.assertEqual(proxy.wait(timeout=2), 0)
        self.assertEqual(monitor.poll.call_count, 2)
        self.assertEqual(process.wait.call_args.kwargs, {'timeout': 2})

    def test_wrappers_restore_originals_even_on_error(self):
        api = SimpleNamespace(gpu_admission=Mock(return_value='admitted'), wait_exclusively=Mock(return_value=0), require=r.require)
        queue = SimpleNamespace(pending_gate=Mock(return_value='pending'))
        before = (api.gpu_admission, api.wait_exclusively, queue.pending_gate)
        monitor = SimpleNamespace(require_boot=Mock(), admission=Mock(), bind=Mock(), poll=Mock())
        prerequisite = Mock()
        with self.assertRaises(ValueError):
            with s.supervise_calls(api, queue, monitor, prerequisite):
                self.assertEqual(api.gpu_admission(physical_gpu=3), 'admitted')
                self.assertEqual(queue.pending_gate('root', {}), 'pending')
                raise ValueError('original error')
        self.assertEqual((api.gpu_admission, api.wait_exclusively, queue.pending_gate), before)
        self.assertEqual(prerequisite.call_count, 2)

    def test_original_runner_finally_accounts_one_abort_and_stops(self):
        row = {'episode_key': s.KEY, 'iteration': s.ITERATION, 'profile': 'C0', 'split': 'dev',
            'task_id': 0, 'env_seed': 1969522881, 'policy_seed': 1969522881,
            'init_index': 0, 'init_row_sha256': 'row', 'budget_bucket': 'development'}
        plan = {'episodes': [row], 'phase_authorization': {'dev': True}, 'run_name': 'cpu-test',
            'profiles_sha256': 'profiles', 'runtime_manifest_sha256': 'runtime',
            'runtime_inventory_sha256': 'inventory', 'source_commit': 'source'}
        process = SimpleNamespace(pid=42, wait=Mock(side_effect=subprocess.TimeoutExpired('owned episode', 5)))
        monitor = SimpleNamespace(require_boot=Mock(), admission=Mock(), bind=Mock(),
            poll=Mock(side_effect=r.GateError('GPU3 owned process Xid detected')))
        queue = SimpleNamespace(pending_gate=Mock())
        events, cleanup = [], Mock()
        output = self.folder / 'attempt'
        replacements = {'locked': lambda *a, **k: contextlib.nullcontext(),
            'validate_plan': lambda *a, **k: (plan, {'profiles': {'C0': {}}},
                {'environment': {}, 'gpu_mapping': {'uuid': s.GPU_UUID, 'egl_device_index': 0}}),
            'read_events': lambda *a: [], 'check_retry': lambda *a: None,
            'read_state': lambda *a: {}, 'runtime_gpu': lambda *a: 3,
            'check_budget': lambda *a, **k: 1800, 'gpu_admission': lambda **k: {},
            'build_command': lambda *a: (['never-launch'], output), 'digest': lambda *a: 'digest',
            'append_event': lambda root, event: events.append(event),
            'durable_json': lambda *a: None, 'child_environment': lambda *a: {},
            'verify_provider': lambda *a, **k: None, 'terminate_owned': cleanup,
            'episode_compute': Mock(side_effect=KeyError()), 'stage_query_summary': Mock(side_effect=KeyError())}
        with contextlib.ExitStack() as stack:
            for name, value in replacements.items(): stack.enter_context(patch.object(r, name, value))
            popen = stack.enter_context(patch.object(r.subprocess, 'Popen', return_value=process))
            # The fake child has no /proc entry; retain the recorded boot read.
            original_read = Path.read_text
            def read_text(path, *args, **kwargs):
                if str(path) == '/proc/42/stat': raise FileNotFoundError()
                return original_read(path, *args, **kwargs)
            stack.enter_context(patch.object(Path, 'read_text', autospec=True, side_effect=read_text))
            with s.supervise_calls(r, queue, monitor, lambda: None):
                with self.assertRaisesRegex(r.GateError, 'no automatic retry'):
                    r.run_plan(self.folder / 'plan.json', split='dev', iteration=s.ITERATION,
                               episode_keys=[s.KEY], root=self.folder)
        popen.assert_called_once()
        cleanup.assert_called_once_with(process)
        self.assertEqual([event['event'] for event in events], ['reserved', 'dispatched', 'aborted'], events[-1])
        self.assertTrue(events[-1]['retryable_infrastructure'])
        self.assertFalse(events[-1]['task_failure'])
        self.assertIn('gpu_process_wall_seconds', events[-1])


if __name__ == '__main__': unittest.main()
