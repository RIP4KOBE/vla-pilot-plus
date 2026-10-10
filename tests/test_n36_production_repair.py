"""CPU-only PR-01/PR-04 regressions, with no project imports or subprocesses.

Execute complete, unmodified AST function bodies from production source. External
release/audit/device/accounting collaborators are synthetic: these tests prove
command agreement and handoff control flow, not runtime readiness or live audits.
All journals are in memory; only synthetic command/context receipts use temp files.
Run directly with Python -B (no pytest or runtime dependencies required).
"""
import ast
import copy
import datetime as dt
import hashlib
import json
from contextlib import nullcontext
from pathlib import Path
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace as NS
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def extract(filename, names, namespace):
    tree = ast.parse((ROOT / 'scripts' / filename).read_text())
    nodes = [node for node in tree.body
             if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names]
    assert {node.name for node in nodes} == set(names)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), filename, 'exec'), namespace)
    return NS(**{name: namespace[name] for name in names})


def constant(filename, name):
    tree = ast.parse((ROOT / 'scripts' / filename).read_text())
    return next(ast.literal_eval(node.value) for node in tree.body
                if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == name for target in node.targets))


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def reference(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def read_ref(ref):
    require(reference(ref['path']) == ref, 'synthetic reference hash differs')
    return json.loads(Path(ref['path']).read_text())


class Harness:
    def __init__(self, root, earliest='protocol', remaining=1850):
        self.root = root.resolve()
        self.output = self.root / 'artifacts/attempt'
        self.events = []
        self.created = []
        self.audit_calls = []
        self.admissions = []
        self.consume_at = None
        self.remaining_after = 1839.999
        self.stop_at = None
        self.deadline = dt.datetime.fromisoformat(
            constant('qd_ed_n36_contract.py', 'DEADLINE').replace('Z', '+00:00'))
        self.end = self.deadline if earliest == 'protocol' else self.deadline - dt.timedelta(hours=1)
        self.now = self.end - dt.timedelta(seconds=remaining)
        outer = self

        class Clock(dt.datetime):
            @classmethod
            def now(cls, tz=None):
                return outer.now

        self.row = {'episode_key': 'synthetic-primary', 'budget_bucket': 'baseline',
                    'replacement': None, 'init_row_sha256': 'i' * 64, 'profile': 'C0'}
        self.runtime = {'artifact_root': str(self.root / 'artifacts')}
        manifest = {'argv': ['/bound/python', 'main.py', '--synthetic'],
                    'output_dir': str(self.output), 'expected_runtime': None}
        self.manifest_ref = self.write(self.root / 'manifest.json', manifest)
        self.plan = {'worktree': str(self.root), 'artifact_root': self.runtime['artifact_root'],
                     'run_name': 'synthetic', 'stop_path': str(self.root / 'STOP'),
                     'source': {'commit': 'a' * 40}, 'runtime_inventory_sha256': 'b' * 64,
                     'runtime': self.write(self.root / 'runtime.json', self.runtime),
                     'runtime_closure': self.write(self.root / 'closure.json', {}),
                     'expected_manifests': {self.row['episode_key']: self.manifest_ref}}
        self.plan_ref = self.write(self.root / 'plan.json', self.plan)
        self.release_ref = self.write(self.root / 'release.json', {'synthetic_only': True})
        later = self.deadline + dt.timedelta(hours=1)
        self.authority = {
            'coordinator_ends_at': (self.end if earliest == 'coordinator' else later).isoformat(),
            'weekly_window': {'ends_at': (self.end if earliest == 'weekly' else later).isoformat()}}
        self.state = {'run_name': 'synthetic', 'artifacts': self.runtime['artifact_root']}
        self.outcome = {'outcome_valid': True, 'required_cost_telemetry_complete': True,
                        'success': True, 'guided_chunks': 0}
        self.w = NS(require=require, read_ref=read_ref, atomic_json=self.write)
        self.c = NS(DEADLINE=self.deadline.isoformat(), ref=reference,
                    operational_binding=lambda plan: {'synthetic_binding': True},
                    event_binding=lambda *args: self.audit_calls.append('event_binding'),
                    finite=lambda value, label: require(value >= 0, label))
        self.supervisor = ModuleType('scripts.qd_ed_n36_supervise')
        self.supervisor.c_identity = lambda row: {'episode_key': row['episode_key']}
        self.supervisor.reconcile = lambda *args, **kwargs: {'next_row': self.row}
        self.release = NS(validate_release=lambda *args: (self.plan, self.runtime, self.authority),
                          admission=self.admit)
        self.r = NS(locked=lambda *args, **kwargs: nullcontext(),
                    TERMINAL={'valid', 'aborted'}, event_groups=lambda events: {},
                    child_environment=lambda runtime: {}, verify_provider=lambda *a, **kw: None,
                    runtime_gpu=lambda *args: None, owned=lambda *args: None,
                    stage_condition=lambda runtime: 'synthetic', append_event_locked=self.append,
                    validate_result=lambda *args: dict(self.outcome), failed_outcome=self.forbidden)
        self.b = NS(runner=self.r, profiles=lambda root: {'profiles': {'C0': {}}})
        self.source = extract('qd_ed_n36_source.py', ['command'], {'Path': Path})
        self.source.active = lambda: None
        self.source.attest = lambda *args: None
        self.worker = extract('qd_ed_n36_worker.py', ['verify_terminal'], {
            'Path': Path, 'w': self.w, 'c': self.c, 'b': self.b,
            'release_api': lambda ref: self.release, 'source_execution': self.source,
            'verify_receipt': self.receipt, 'native_counts': self.native_counts})
        self.worker.context_for = lambda plan_ref, row, release_ref: {
            'plan': plan_ref, 'episode_key': row['episode_key'], 'release': release_ref}
        self.runner = extract('qd_ed_n36_runner.py', ['execute_one', 'worker_command'], {
            'Path': Path, 'dt': NS(datetime=Clock, timezone=dt.timezone),
            'time': NS(time=lambda: self.now.timestamp(), monotonic=lambda: 1.),
            'source_execution': self.source, 'release': self.release,
            'snapshot': lambda *args: (self.state, list(self.events), [], []),
            'r': self.r, 'w': self.w, 'c': self.c, 'b': self.b, 'worker': self.worker,
            'supervisor': self.supervisor, 'existing_handles': lambda *args: [],
            'check_probe': lambda *args: None, 'device_check': lambda: {'synthetic_only': True},
            'journal_prefix': lambda *args: {'synthetic_only': True},
            'subprocess': NS(Popen=self.popen, PIPE=-1, STDOUT=-2,
                             TimeoutExpired=subprocess.TimeoutExpired),
            'process_identity': lambda pid: {'pid': pid, 'boot_id': 'synthetic', 'proc_start_ticks': '1'},
            'wait_worker': self.wait_worker, 'cleanup_owned': self.forbidden})

    def forbidden(self, *args, **kwargs):
        raise AssertionError('no synthetic settlement, signaling or external execution allowed')

    def advance(self, stage):
        if self.consume_at == stage:
            self.now = self.end - dt.timedelta(seconds=self.remaining_after)
        if self.stop_at == stage:
            Path(self.plan['stop_path']).symlink_to(self.root / 'absent-stop-target')

    def write(self, path, value):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
        self.advance(path.name)
        return reference(path)

    def append(self, root, event):
        self.events.append(copy.deepcopy(event))
        self.advance(event['event'])

    def admit(self, *args, now, **kwargs):
        require((self.end - now).total_seconds() >= 1840, 'synthetic initial full allowance')
        self.admissions.append(now)
        return {'n36_reservation': {'synthetic_only': True}}

    def popen(self, command, **kwargs):
        self.created.append(list(command))
        stdin = NS(write=lambda data: None, flush=lambda: None, close=lambda: None)
        return NS(pid=12345, stdin=stdin, poll=lambda: 0)

    def receipt(self, *args):
        self.audit_calls.append('verify_receipt')
        return {'synthetic_only': True}

    def wait_worker(self, *args):
        self.write(self.output / 'eds_eval/n36-worker-receipt.json', {'synthetic_only': True})
        return 0

    def native_counts(self, *args, **kwargs):
        self.audit_calls.append('native_counts')

    def modules(self):
        scripts = ModuleType('scripts')
        scripts.qd_ed_n36_supervise = self.supervisor
        return patch.dict(sys.modules, {'scripts': scripts,
                                       'scripts.qd_ed_n36_supervise': self.supervisor})

    def run(self):
        with self.modules():
            return self.runner.execute_one(self.plan_ref, self.release_ref)

    def verify(self, terminal):
        with self.modules():
            return self.worker.verify_terminal(self.plan_ref, self.row, terminal, self.release_ref)


class ProductionRepairTests(unittest.TestCase):
    def harness(self, **kwargs):
        temp = tempfile.TemporaryDirectory(prefix='n36-production-repair-', dir=ROOT)
        self.addCleanup(temp.cleanup)
        return Harness(Path(temp.name), **kwargs)

    def test_actual_runner_command_receipt_passes_terminal_verifier(self):
        h = self.harness()
        result = h.run()
        self.assertEqual(result['status'], 'VALID')
        record = read_ref(reference(h.output / 'command.json'))
        expected = ['/bound/python', '-I', '-S', '-B', '-X', 'pycache_prefix=/dev/null',
                    str(h.root / 'scripts/qd_ed_n36_bootstrap.py'), 'scripts.qd_ed_n36_worker',
                    '--context', str(h.output / 'n36-worker-context.json'),
                    '--context-sha256', record['context']['sha256']]
        self.assertEqual(record['argv'], expected)
        self.assertEqual(h.created, [expected])
        self.assertEqual(h.audit_calls, ['event_binding', 'verify_receipt', 'native_counts'])
        self.assertEqual([e['event'] for e in h.events], ['reserved', 'dispatched', 'valid'])
        self.assertEqual(h.events[0]['reserved_gpu_seconds'], 1840)
        self.assertEqual(h.events[1]['timeout_seconds'], 1800)

    def test_every_command_token_mutation_is_rejected_before_audits(self):
        h = self.harness()
        terminal = h.run()['terminal']
        path = h.output / 'command.json'
        original = read_ref(reference(path))
        for index in range(len(original['argv'])):
            for operation in ('replace', 'delete'):
                with self.subTest(index=index, operation=operation):
                    changed = copy.deepcopy(original)
                    if operation == 'replace':
                        changed['argv'][index] += '-tampered'
                    else:
                        del changed['argv'][index]
                    h.write(path, changed)
                    h.audit_calls.clear()
                    with self.assertRaisesRegex(ValueError, 'worker command receipt differs'):
                        h.verify(terminal)
                    self.assertEqual(h.audit_calls, ['event_binding'])

    def test_command_envelope_and_legacy_launcher_mutations_are_rejected(self):
        h = self.harness()
        terminal = h.run()['terminal']
        path = h.output / 'command.json'
        original = read_ref(reference(path))
        for kind in ('legacy', 'extra_arg', 'reordered', 'main_argv', 'context', 'extra_key'):
            with self.subTest(kind=kind):
                changed = copy.deepcopy(original)
                if kind == 'legacy':
                    changed['argv'] = [original['argv'][0], '-m', *original['argv'][7:]]
                elif kind == 'extra_arg':
                    changed['argv'].append('--extra')
                elif kind == 'reordered':
                    changed['argv'][1:3] = reversed(changed['argv'][1:3])
                elif kind == 'main_argv':
                    changed['main_argv'].append('--extra')
                elif kind == 'context':
                    changed['context']['sha256'] = '0' * 64
                else:
                    changed['extra'] = True
                h.write(path, changed)
                with self.assertRaisesRegex(ValueError, 'worker command receipt differs'):
                    h.verify(terminal)

    def test_consumed_margin_at_each_late_boundary_prevents_worker_creation(self):
        for earliest in ('protocol', 'coordinator', 'weekly'):
            for stage in ('n36-worker-context.json', 'command.json', 'dispatched'):
                for remaining in (1839.999, 1., 0., -1.):
                    with self.subTest(earliest=earliest, stage=stage, remaining=remaining):
                        h = self.harness(earliest=earliest)
                        h.consume_at = stage
                        h.remaining_after = remaining
                        reason = 'before worker start' if stage == 'dispatched' else 'after reservation'
                        with self.assertRaisesRegex(ValueError, 'deadline ' + reason):
                            h.run()
                        self.assertEqual(len(h.admissions), 2)
                        self.assertEqual(h.created, [])
                        expected = ['reserved', 'dispatched'] if stage == 'dispatched' else ['reserved']
                        self.assertEqual([e['event'] for e in h.events], expected)
                        self.assertEqual(h.events[0]['reserved_gpu_seconds'], 1840)
                        self.assertFalse((h.output / 'process.json').exists())
                        self.assertFalse((h.output / 'attempt-result.json').exists())

    def test_exact_full_allowance_is_accepted_at_both_boundaries(self):
        for earliest in ('protocol', 'coordinator', 'weekly'):
            for stage in ('command.json', 'dispatched'):
                with self.subTest(earliest=earliest, stage=stage):
                    h = self.harness(earliest=earliest)
                    h.consume_at = stage
                    h.remaining_after = 1840
                    self.assertEqual(h.run()['status'], 'VALID')
                    self.assertEqual(len(h.created), 1)
                    self.assertEqual(h.events[1]['timeout_seconds'], 1800)

    def test_stop_at_late_boundaries_leaves_unsettled_without_signaling(self):
        for stage in ('reserved', 'dispatched'):
            with self.subTest(stage=stage):
                h = self.harness()
                h.stop_at = stage
                with self.assertRaisesRegex(ValueError, 'STOP'):
                    h.run()
                self.assertEqual(h.created, [])
                expected = ['reserved', 'dispatched'] if stage == 'dispatched' else ['reserved']
                self.assertEqual([e['event'] for e in h.events], expected)
                self.assertFalse((h.output / 'attempt-result.json').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
