"""Ephemeral CPU graph. Nothing here is an operational approval or inventory.

Every trust root is relocated into a TemporaryDirectory with fixture identities.
Source and runtime files are inert fixture bytes; Hydra/constructor source is
copied for real composition. Git/source, schema, closure, native/controller,
accounting, readiness and receipt validators are not replaced. Process import
observations and child/device/provider observations are simulated explicitly.
Public released lifecycle functions are executed directly. Only process/device/
provider observations and content-keyed fixture composition are simulated.
"""
import copy
import datetime as dt
import importlib.metadata
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import yaml
from scripts import qd_ed_n23_worker as w, qd_ed_final_runner as r
from scripts import qd_ed_n36_engineering as e, qd_ed_n36_contract as c
from scripts import qd_ed_n36_bridge as b, qd_ed_n36_runner as runner
from scripts import qd_ed_n36_healthcheck as health, qd_ed_n36_worker as worker
from scripts import qd_ed_n36_release as full, qd_ed_n34_controller as controller

REAL_ROOT = b.ROOT
NOW = dt.datetime(2026, 10, 10, 16, tzinfo=dt.timezone.utc)


def put(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False))
    return c.ref(path)


def lines(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(v, sort_keys=True) + '\n' for v in values))


def inert(path, text='# CPU fixture only; never imported or executed\n'):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return c.ref(path)


def git(root, *args):
    # Local object operations only; no user config, hooks, network or credentials.
    return subprocess.check_output(['git', '-c', 'core.hooksPath=/dev/null', '-C', str(root), *args],
        env={'PATH': os.defpath, 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null',
             'GIT_AUTHOR_NAME': 'CPU fixture', 'GIT_AUTHOR_EMAIL': 'fixture@invalid',
             'GIT_COMMITTER_NAME': 'CPU fixture', 'GIT_COMMITTER_EMAIL': 'fixture@invalid'},
        stderr=subprocess.DEVNULL, text=True).strip()


class Graph:
    def __init__(self, root, patch):
        self.root, self.patch = root, patch
        self.session = root / 'CPU_FIXTURE_NOT_AUTHORITY'
        self.source = self.session / 'variants/fixture/implementation_worktree'
        self.owner = self.session / 'owner'
        self.output = self.session / 'engineering-executions/n36_engineering_cpu_fixture'
        self.docs = root / 'fixture-documents'
        self.launches = []
        self.clock = NOW.timestamp()
        self.monotonic = 100.
        for path in (self.source, self.owner / 'data', self.docs):
            path.mkdir(parents=True)
        for name, value in {'SOURCE': self.source, 'OWNER': self.owner, 'SESSION': self.session,
            'IDENTITY': 'N36_ENGINEERING_CPU_FIXTURE_NOT_AUTHORITY',
            'EPISODE_KEY': self.output.name, 'HEALTH_ID': 'n36_healthcheck_engineering_cpu_fixture',
            'HEALTH_KIND': 'n36_engineering_cpu_fixture_resource'}.items():
            patch.setattr(e, name, value)
        patch.setattr(b, 'ROOT', self.source)
        paths = (str(self.owner / 'STOP'), str(self.session / 'autonomy_20261004/STOP'))
        patch.setattr(c.stop, 'STOP_PATHS', paths)
        self._source_tree()
        self._composition_cache()
        self._journals()
        self._runtime()
        self._documents()
        self._observations()
        self.reset()

    def doc(self, name, value):
        return put(self.docs / (name + '.json'), value)

    def _composition_cache(self):
        """Memoize only deterministic fixture composition by complete inputs.

        Every distinct argv/config/constructor byte sequence executes the real
        composer. Every release still runs all source/runtime/native/manifest
        validators. No acceptance result, hash check or release is cached.
        """
        compose = b.compose_launch
        cache = {}
        def composed(argv, root):
            assert Path(root) == self.source
            inputs = tuple((str(p.relative_to(self.source)), w.sha(p))
                           for folder in ('configs', 'core')
                           for p in sorted((self.source / folder).rglob('*'))
                           if p.is_file() and p.suffix in ('.py', '.yaml', '.yml', '.json'))
            key = (tuple(argv), inputs)
            if key not in cache:
                cache[key] = compose(argv, root)
            return copy.deepcopy(cache[key])
        self.patch.setattr(b, 'compose_launch', composed)

    def _source_tree(self):
        # No production inventory is built. Only this disposable source tree is
        # committed. Real composition inputs are copied; other code is inert.
        for folder in ('configs', 'core'):
            for path in (REAL_ROOT / folder).rglob('*'):
                if path.is_file() and path.suffix in ('.py', '.yaml', '.yml', '.json'):
                    dest = self.source / path.relative_to(REAL_ROOT)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(path, dest)
        required = set(r.REQUIRED_CODE) | set(b.RUNTIME_SOURCES)
        required |= {'scripts/qd_ed_n36_' + name + '.py' for name in
                     ('worker', 'bridge', 'contract', 'native', 'build', 'lifecycle', 'arithmetic',
                      'reference', 'source', 'bootstrap', 'engineering', 'release', 'accounting', 'stop')}
        required |= {'scripts/' + name + '.py' for name in
                     ('qd_ed_n23_worker', 'audit_decision_evidence', 'qd_ed_n31_native',
                      'qd_ed_n34_controller', 'qd_ed_n34_source', 'qd_ed_n34_worker', 'qd_ed_n34_native')}
        for name in required:
            if not (self.source / name).exists():
                inert(self.source / name)
        shutil.copyfile(REAL_ROOT / 'scripts/qd_ed_gpu_probe.py', self.source / 'scripts/qd_ed_gpu_probe.py')
        for name in ('third_party/rdt/scripts/maniskill_model.py',
                     'third_party/rdt/models/rdt_runner.py', 'third_party/rdt/models/multimodal_encoder/siglip_encoder.py',
                     'third_party/rdt/models/multimodal_encoder/t5_encoder.py', 'third_party/rdt/configs/state_vec.py',
                     'third_party/lerobot/src/lerobot/__init__.py',
                     'third_party/libero_pro/libero/libero/__init__.py'):
            inert(self.source / name)
        task_path = self.source / 'configs/qd_ed_final/n31_dev_task_identities.json'
        task_doc = json.loads(task_path.read_text())
        for task in task_doc['tasks']:
            task['init_file_sha256'] = w.canonical_sha({'fixture_init': task['task_id']})
            task['bddl_sha256'] = w.canonical_sha({'fixture_bddl': task['task_id']})
            task['init_row_sha256'] = w.canonical_sha({'fixture_row': task['task_id']})
        put(task_path, task_doc)
        git(self.source, 'init', '-q')
        for sub in b.closure.PINNED_SUBMODULES:
            path = self.source / sub
            database = self.source / '.git/modules' / sub
            database.parent.mkdir(parents=True, exist_ok=True)
            git(path, 'init', '-q', '--separate-git-dir=' + str(database))
            git(path, 'add', '.')
            git(path, 'commit', '-qm', 'inert CPU fixture dependency')
        git(self.source, 'add', '.')
        git(self.source, 'commit', '-qm', 'inert CPU fixture source')
        self.source_record = b.closure.source_record(self.source, b.source_paths(self.source))
        self.patch.setattr(e, 'BASE', self.source_record['commit'])
        # Only parent imported-module observations are simulated. The real
        # attest_loaded validator checks these against the real fixture files.
        observed = {'scripts.fixture_parent': SimpleNamespace(__file__=str(self.source / 'scripts/qd_ed_n36_runner.py'))}
        # Use an inventoried path without creating a post-commit source file.
        observed['scripts.fixture_parent'].__file__ = str(self.source / 'scripts/qd_ed_final_runner.py')
        self.patch.setattr(b.closure, 'sys', SimpleNamespace(**{**vars(sys), 'modules': observed}))

    def _journals(self):
        self.baseline = {name: [] for name in e.JOURNALS}
        # Synthetic 506-attempt history, exact whole-snapshot total. It is NOT
        # a copy of study journals or evidence of the actual retained history.
        for index in range(506):
            base = {'attempt_id': f'CPU_FIXTURE_HISTORY_{index}', 'episode_key': f'CPU_FIXTURE_HISTORY_{index}',
                    'identity': {'iteration': 'CPU_FIXTURE_HISTORY'}, 'budget_bucket': 'development'}
            self.baseline[e.JOURNALS[0]] += [{**base, 'event': kind,
                **({'gpu_process_wall_seconds': 75. * 3600 if index == 0 else (75.60616276674473 - 75.) * 3600 if index == 1 else 0.,
                    'outcome_valid': False} if kind == 'aborted' else {})}
                for kind in ('reserved', 'dispatched', 'aborted')]
        self.baseline[e.JOURNALS[2]] = [{'event': 'gpu_hour_reservations_changed',
            'gpu_hour_reservations': c.CAPS['protected_gpu_hours'], 'rationale': 'CPU fixture only', 'time_unix': 1}]
        self.prefixes = {}
        for name, values in self.baseline.items():
            path = self.owner / 'data' / name
            lines(path, values)
            self.prefixes[name] = {'path': str(path), **runner.journal_prefix(path)}
        self.retained = r.budget_snapshot(self.baseline[e.JOURNALS[0]], [])
        assert self.retained['gpu_hours_consumed'] == 75.60616276674473
        self.margin = self.doc('fixture-margin', {'ledger_prefixes': self.prefixes,
            'cost_reconciliation': {'retained_admission_margin_gpu_hours': .23357169027962}})
        self.patch.setattr(c, 'ACCOUNTING_SHA', self.margin['sha256'])

    def _runtime(self):
        self.mapping = {'physical_gpu': 7, 'uuid': c.GPU_UUID, 'egl_device_index': 4,
                        'metadata_mapping_verified': True, 'pci_bus_id': '0000:01:00.0'}
        artifact = self.session
        provider = {'backend': 'codex_cli', 'model': 'gpt-6-astra', 'auth_mode': 'chatgpt',
            'reasoning_effort': 'low', 'timeout_seconds': 180, 'cli_path': str(self.root / 'never-executed-cli'),
            'cli_version': '0.155.1', 'cli_sha256': '0' * 64,
            'disabled_skill_paths': [str(self.root / 'inactive-fixture-skills')], 'allow_recovered_error_events': True}
        provider['public_config_sha256'] = r.codex_public_config_sha256(provider)
        runtime = {'schema': 'qd-ed-runtime-setup-v1', 'worktree': str(self.source), 'artifact_root': str(artifact),
            'gpu_mapping': self.mapping, 'files': [], 'tasks': {}, 'cuda_egl_verified': True,
            'provider_ready': True, 'frozen_stage_provider': provider,
            'stage_engineering_condition': r.n4e1_support().engineering_condition(),
            'stage_recovered_error_condition': r.E2_STAGE_CONDITION,
            'main_overrides': ['+main.require_task_cache_identity=true'],
            'environment': {'LIBERO_CONFIG_PATH': str(artifact / 'fixture-libero'), 'TORCH_HOME': str(artifact / 'fixture-torch')}}
        for task in c.expected_rows(self.source, cohort=c.DRAFT_N36R4_COHORT)[::4]:
            tid = task['task_id']
            init = put(artifact / f'inputs/{tid}-init.json', {'fixture_init': tid})
            bddl = put(artifact / f'inputs/{tid}-bddl.json', {'fixture_bddl': tid})
            cache = artifact / f'cache/{tid}'
            inert(cache / 'fixture.txt', 'inert cache\n')
            runtime['tasks'][str(tid)] = {'task_id': tid, 'init_index': 0, 'init_path': init['path'],
                                         'bddl_path': bddl['path'], 'cache_dir': str(cache)}
            runtime['files'] += [self.file_row(Path(ref['path'])) for ref in (init, bddl)]
            runtime['files'].append(self.file_row(cache / 'fixture.txt'))
        for name in ('hubconf.py', 'dinov2/__init__.py'):
            path = Path(runtime['environment']['TORCH_HOME']) / 'hub/facebookresearch_dinov2_main' / name
            inert(path)
            runtime['files'].append(self.file_row(path))
        self.runtime = runtime
        self.runtime_ref = self.doc('fixture-runtime', runtime)
        module = inert(self.root / 'inert-runtime/osc.py')
        modules = {'robosuite.controllers.osc': module}
        for name in ('encodings', 'encodings.aliases', 'encodings.utf_8'):
            modules[name] = inert(self.root / ('inert-runtime/' + name + '.py'))
        for name in ('os.path', 'posixpath', 'importlib._bootstrap', '_frozen_importlib',
                     'importlib._bootstrap_external', '_frozen_importlib_external'):
            modules[name] = c.ref(Path(sys.modules[name].__file__).resolve())
        versions = {name: importlib.metadata.version(name) for name in ('torch', 'numpy', 'robosuite', 'mujoco', 'transformers')}
        self.closure = {'schema': 'n34-runtime-source-closure-v1', 'runtime': self.runtime_ref,
            'modules': modules, 'required_after': list(modules),
            'interpreter': {'path': str(Path(sys.executable).resolve()), 'sha256': w.sha(Path(sys.executable).resolve()), 'version': sys.version},
            'versions': {name: 'CPU fixture' for name in ('python', 'torch', 'libero', 'robosuite', 'mujoco')},
            'distribution_versions': versions}
        self.closure_ref = self.doc('fixture-closure', self.closure)
        proof = {'schema': 'n34-deployed-controller-semantics-v1', 'runtime': self.runtime_ref,
            'status': 'ROOT_REVIEWED', 'physical_gain_certified': False,
            'module': 'robosuite.controllers.osc', 'class': 'OperationalSpaceController', 'source': module,
            'instance': {'control_delta': True, 'control_ori': True, 'control_dim': 6, 'impedance_mode': 'fixed',
                'policy_freq': 20, 'interpolator_pos': None, 'interpolator_ori': None, 'uncouple_pos_ori': True,
                'input_min': [-1]*6, 'input_max': [1]*6, 'output_min': [-.1]*6, 'output_max': [.1]*6},
            'semantics': {'translation': 'scaled_world_delta', 'rotation': 'scaled_axis_angle_delta',
                'zero_rotation': 'zero_increment_not_absolute_pose', 'gripper': 'minus_open_plus_close',
                'projector_0_01': 'convention_not_measured_gain'},
            'review_evidence': {name: self.doc('fixture-controller-' + name,
                {'kind': 'deployed_source_review', 'runtime': self.runtime_ref, 'fixture_only': False,
                 'notice': 'APPROVAL SHAPE ONLY: ephemeral CPU fixture, no operational authority'})
                for name in ('set_goal', 'scale_action', 'wrapper_and_gripper')}}
        self.controller_ref = self.doc('fixture-controller', proof)
        from test_n36_build import synthetic_build
        self.native_ref = synthetic_build(self.root / 'inert-native')
        tasks = c.expected_rows(self.source, cohort=c.DRAFT_N36R4_COHORT)[::4]
        inventory = {'schema': 'qd-ed-runtime-inventory-v1', 'checkpoint': [self.file_row(Path(inert(artifact / 'fixture-checkpoint')['path']))], 'hf_encoders': [],
            'dinov2': {'weights': self.file_row(Path(inert(artifact / 'fixture-weights')['path']))},
            'libero_tasks': [{'task_id': t['task_id'], 'used_init_index': 0, 'used_init_row_sha256': t['init_row_sha256']} for t in tasks]}
        inv = put(self.source / 'fixture-inventory.json', inventory)
        seeds = put(self.source / 'fixture-seeds.json', {'schema': 'qd-ed-frozen-seed-plan-v1',
            'run_name': 'CPU_FIXTURE_NOT_AUTHORITY', 'blocks': {'dev': tasks}})
        self.inputs = {'run_name': 'CPU_FIXTURE_NOT_AUTHORITY', 'runtime_inventory_path': inv['path'],
            'runtime_inventory_sha256': inv['sha256'], 'seed_plan_path': seeds['path'],
            'seed_plan_sha256': seeds['sha256'], 'input_contract_label': 'input_repaired'}

    @staticmethod
    def file_row(path):
        return {'path': str(path), 'resolved_path': str(path), 'sha256': w.sha(path), 'size_bytes': path.stat().st_size}

    def _documents(self):
        rows = c.expected_rows(self.source, cohort=c.DRAFT_N36R4_COHORT)
        selected = {**rows[0], 'iteration': e.IDENTITY, 'episode_key': e.EPISODE_KEY}
        review = self.doc('fixture-protocol-review', {'notice': 'CPU fixture only'})
        self.patch.setattr(c, 'PROTOCOL_REVIEW_SHA', review['sha256'])
        original = {'cohort': c.DRAFT_N36R4_COHORT, 'episodes': rows, 'limits': c.LIMITS,
            'worker_contract': c.WORKER_CONTRACT, 'deadline': c.DEADLINE,
            'protocol': self.doc('fixture-protocol', {'notice': 'CPU fixture only'}),
            'protocol_review': review, 'accounting': self.margin}
        original_ref = self.doc('fixture-original', original)
        spec = {'scope': {'episode': selected, 'notice': 'CPU fixture only'},
            'accounting_proposal': {'notice': 'CPU fixture only'}, 'retained_ledger_prefixes': self.prefixes,
            'retained_snapshot_reference': self.doc('fixture-retained', {'retained_snapshot': self.retained}),
            'full_audit_view': {'immutable_original_plan': original_ref}}
        self.patch.setattr(e, 'SPECIFICATION', self.doc('fixture-specification', spec))
        scope = self.doc('fixture-scope', e.disabled_scope())
        account = self.doc('fixture-accounting', e.disabled_accounting())
        route = self.doc('fixture-deployment', {'schema': 'n36-engineering-deployment-v1',
            'source_cwd': str(self.source), 'owner_root': str(self.owner), 'output_root': str(self.output),
            'stop_authority': c.stop.binding()})
        common = {'source': self.source_record, 'scientific_source': self.source_record,
            'runtime': self.runtime_ref, 'runtime_closure': self.closure_ref, 'native_build': self.native_ref,
            'controller_semantics': self.controller_ref, 'worktree': str(self.source),
            'stop_authority': c.stop.binding(), 'stop_path': c.stop_path(self.source), **self.inputs}
        audit = {**original, **common, 'schema': e.AUDIT_SCHEMA, 'original_plan': original_ref,
            'dispatch_authority': False, 'frozen': True, 'release_enabled': False,
            'artifact_root': str(self.output / 'audit-only'), 'phase_authorization': {'dev': False, 'validation': False, 'formal': False},
            'expected_manifests': {}, 'deployment': route, 'scope': scope, 'attempt_identity': 'episode_key'}
        for i, row in enumerate(rows):
            audit['expected_manifests'][row['episode_key']] = self.doc(f'fixture-audit-manifest-{i}', b.manifest(audit, self.runtime, row))
        audit_ref = self.doc('fixture-audit', audit)
        empty = self.doc('fixture-placeholder', {'notice': 'unbound CPU fixture'})
        plan = {**common, 'schema': e.PLAN_SCHEMA, 'frozen': False, 'release_enabled': False,
            'cohort': e.IDENTITY, 'purpose': e.PURPOSE, 'episodes': [selected], 'limits': e.LIMITS,
            'worker_contract': c.WORKER_CONTRACT, 'deadline': c.DEADLINE, 'attempt_identity': 'episode_key',
            'artifact_root': str(self.output), 'scope': scope, 'accounting': account, 'deployment': route,
            'audit_plan': audit_ref, 'scientific_equivalence': self.doc('fixture-equivalence', {
                'schema': 'n36-engineering-scientific-equivalence-v1', 'base_commit': e.BASE,
                'source': self.source_record, 'changed_paths': [], 'scientific_changes': False}),
            'phase_authorization': {'engineering': False, 'dev': False, 'validation': False, 'formal': False},
            'authority': empty, 'b5_review': empty, 'engineering_manifest': empty, 'expected_manifests': {}}
        plan['engineering_manifest'] = self.doc('fixture-engineering-manifest', b.engineering_manifest(plan, self.runtime, selected))
        plan['expected_manifests'] = {e.EPISODE_KEY: plan['engineering_manifest']}
        bindings = e.review_bindings(plan)
        plan['b5_review'] = self.doc('fixture-b5-shape', {'schema': 'n36-engineering-independent-b5-review-v1',
            'decision': 'PASS_PREPARATION_REQUIRES_ROOT_RELEASE', **bindings, 'worker_receipts_are_future': True, 'release_enabled': False})
        protocol = self.doc('fixture-protocol-acceptance-shape', {'schema': 'n36-engineering-root-protocol-acceptance-v1',
            'approved': True, **bindings, 'b5_review': plan['b5_review'], 'limits': e.LIMITS})
        adoption = self.doc('fixture-source-adoption-shape', {'schema': 'n36-engineering-source-adoption-v1',
            'approved': True, **bindings, 'b5_review': plan['b5_review'], 'protocol_acceptance': protocol,
            'owner_root': str(self.owner), 'source_cwd': str(self.source)})
        amendment = self.doc('fixture-accounting-adoption-shape', {'schema': 'n36-engineering-owning-accounting-v1',
            'approved': True, **bindings, 'source_adoption': adoption, 'caps': c.CAPS, 'limits': e.LIMITS,
            'ledger_prefixes': self.prefixes, 'snapshot': self.retained, 'arithmetic': spec['accounting_proposal'],
            'margin_reference': self.margin, 'automatic_recoveries': 0})
        authority = {'schema': 'n36-engineering-budget-authority-v1', 'approved': True, 'cohort': e.IDENTITY,
            'purpose': e.PURPOSE, **bindings, 'b5_review': plan['b5_review'], 'caps': c.CAPS, 'limits': e.LIMITS,
            'automatic_recoveries': 0, 'validation_authorized': False, 'formal_authorized': False,
            'coordinator_ends_at': c.DEADLINE, 'starts_at': '2026-10-10T00:00:00Z',
            'weekly_window': {'origin_gpu_hours': 53.08404692669838, 'increment_gpu_hours': 168., 'ends_at': c.DEADLINE},
            'approval_basis': empty, 'protocol_acceptance': protocol, 'source_adoption': adoption,
            'amendment': amendment, 'ledger_prefixes': self.prefixes, 'margin_reference': self.margin}
        plan['authority'] = self.doc('fixture-authority-shape', authority)
        plan.update(frozen=True, release_enabled=True)
        plan['phase_authorization']['engineering'] = True
        self.plan, self.authority, self.audit = plan, authority, audit
        self.plan_ref = self.doc('fixture-plan-shape', plan)
        self.health_ref = self.release('health')
        self.state = {'canonical_worktree': str(self.owner), 'worktree': str(self.owner),
            'run_name': plan['run_name'], 'artifacts': self.runtime['artifact_root'],
            'n36_engineering_budget_authority': plan['authority'], 'gpu_pool': [7], 'max_concurrent_gpu_workers': 1,
            'resource_isolation': {'status': 'ACTIVE', 'validation_status': 'PASS', 'private_budget': True},
            'budget': {**self.retained, 'max_episode_attempts': c.CAPS['attempts'], 'max_gpu_hours': c.CAPS['gpu_hours'],
                'reserved': c.CAPS['buckets'], 'gpu_hour_reservations': c.CAPS['protected_gpu_hours'], 'amendment': amendment}}

    def release(self, kind, readiness=None, issued_at=None):
        if issued_at is None:
            issued_at = dt.datetime.fromtimestamp(self.clock, dt.timezone.utc).isoformat()
        value = {'schema': f'n36-engineering-{kind}-release-v1', 'approved': True,
            'plan': self.plan_ref, 'authority': self.plan['authority'], 'b5_review': self.plan['b5_review'],
            **e.review_bindings(self.plan), 'limits': e.LIMITS, 'purpose': e.PURPOSE, 'issued_at': issued_at}
        if kind == 'episode':
            value['readiness'] = readiness
        # A later fixture release must not rewrite evidence used by restart
        # tests. Content-addressed names keep every detached binding immutable.
        tag = w.canonical_sha(value)
        review = self.doc('fixture-root-' + kind + '-review-shape-' + tag,
            {**value, 'schema': f'n36-engineering-root-{kind}-review-v1', 'decision': 'APPROVED'})
        return self.doc('fixture-' + kind + '-release-shape-' + tag, {**value, 'root_review': review})

    def reset(self):
        shutil.rmtree(self.output, ignore_errors=True)
        for name, values in self.baseline.items():
            lines(self.owner / 'data' / name, values)
        (self.owner / 'research-state.yaml').write_text(yaml.safe_dump(self.state))
        self.launches.clear()
        self.clock, self.monotonic = NOW.timestamp(), 100.
        for path in c.stop.STOP_PATHS:
            Path(path).unlink(missing_ok=True)

    def _observations(self):
        graph = self
        class Clock(dt.datetime):
            @classmethod
            def now(cls, tz=None):
                return cls.fromtimestamp(graph.clock, tz=tz)
        self.patch.setattr(e, 'dt', SimpleNamespace(datetime=Clock, timezone=dt.timezone))
        self.patch.setattr(runner, 'dt', SimpleNamespace(datetime=Clock, timezone=dt.timezone))
        self.patch.setattr(c.stop, 'dt', SimpleNamespace(datetime=Clock, timezone=dt.timezone))
        # source-only bootstrap observations belong to the simulated parent.
        # Actual source closure and child receipt validators remain intact.
        self.patch.setattr(runner.source_execution, 'active', lambda: SimpleNamespace(fixture_only=True))
        self.patch.setattr(runner.source_execution, 'attest', lambda *a, **kw: {'fixture_only': True})
        self.patch.setattr(runner, 'device_check', lambda: {'physical_gpu': 7, 'fixture_only': True})
        self.patch.setattr(r, 'verify_provider', lambda *a, **kw: {'fixture_only': True})
        # Avoid reading or inheriting any process credential environment.
        self.patch.setattr(e, 'child_environment', lambda *a: {'CPU_FIXTURE_ONLY': '1'})
        self.patch.setattr(runner, 'process_identity', lambda pid: {'pid': pid, 'boot_id': 'CPU_FIXTURE', 'proc_start_ticks': '1'})
        self.patch.setattr(health, 'time', SimpleNamespace(time=lambda: graph.clock, monotonic=lambda: graph.monotonic))
        self.patch.setattr(runner, 'time', SimpleNamespace(time=lambda: graph.clock, monotonic=lambda: graph.monotonic))
        class Child:
            pid = 424242
            returncode = None
            def __init__(self, command, **kwargs):
                self.command, self.stdin = command, io.BytesIO()
                graph.launches.append(command)
            def poll(self):
                return self.returncode
        # Restrict Popen substitution to module-local subprocess views.
        self.patch.setattr(health, 'subprocess', SimpleNamespace(**{**vars(subprocess), 'Popen': Child}))
        self.patch.setattr(runner, 'subprocess', SimpleNamespace(**{**vars(subprocess), 'Popen': Child}))
        self.patch.setattr(health, 'wait_probe', self.probe_child)
        self.patch.setattr(e, 'time', SimpleNamespace(time=lambda: graph.clock))
        self.guard = e.launch_guard
        self.reserve = e.reserve_health_handoff
        self.api = e
        self.health_run = health.run_healthcheck
        self.episode_run = runner.execute_one

    def orchestration(self, patch):
        # Restore direct public entrypoints between disposable scenarios.
        self.api.reserve_health_handoff = self.reserve
        self.api.launch_guard = self.guard
        failed_outcome = r.failed_outcome
        def observed_failure(exc, *args, **kwargs):
            self.last_failure = (type(exc).__name__, str(exc))
            return failed_outcome(exc, *args, **kwargs)
        patch.setattr(r, 'failed_outcome', observed_failure)

    def probe_child(self, process, started, identity, timeout):
        assert timeout == 20
        output = Path(process.command[process.command.index('--output') + 1])
        (output / 'probe-frame.png').write_bytes(b'CPU_SIMULATED_FRAME_NOT_GPU_EVIDENCE')
        self.clock += 1
        self.monotonic += 1
        evidence = {'schema': 'qd-ed-gpu-context-probe-v2', 'resource_id': e.HEALTH_ID,
            'time_unix': self.clock, 'physical_gpu': 7, 'torch_logical_device': 0,
            'cuda_visible_devices': '7', 'cuda_device_order': 'PCI_BUS_ID', 'egl_cuda_ordinal_namespace': 'process_visible',
            'torch_uuid': c.GPU_UUID, 'nvidia_physical_gpu': 7, 'nvidia_uuid': c.GPU_UUID,
            'nvidia_pci_bus_id': self.mapping['pci_bus_id'], 'torch_visible_device_count': 1, 'cuda_kernel_result': 2.,
            'display_egl_device_index': 4, 'display_cuda_ordinal': 0,
            'cuda_associated_egl_devices': [{'egl_device_index': 4, 'cuda_ordinal': 0}],
            'gl_vendor': 'NVIDIA CPU SIMULATION', 'gl_renderer': 'CPU fixture', 'gl_version': 'CPU fixture',
            'frame_shape': [64, 64, 3], 'frame_dtype': 'uint8', 'frame_nonzero_values': 1, 'frame_std': 1.,
            'simulation_steps': 0, 'frame_png_sha256': w.sha(output / 'probe-frame.png'),
            'fixture_only': True}
        put(output / 'probe-evidence.json', evidence)
        process.returncode = 0
        return 0

    def health(self):
        return self.health_run(self.plan_ref, self.health_ref, e.HEALTH_ID, timeout_seconds=20)

    def readiness(self):
        return {'health_release': self.health_ref,
                'terminal': c.ref(self.output / 'healthchecks' / e.HEALTH_ID / 'healthcheck-result.json')}

    def accepted_episode(self):
        """Real health/release validation with simulated device/import evidence.

        No episode child, native execution, or production approval is involved.
        """
        result = self.health()
        assert result['status'] == 'VALID', result
        reference = self.release('episode', self.readiness())
        assert e.validate_release(self.plan_ref, reference)[0] == self.plan
        return reference

    def saved_cpu_state(self):
        """Restore disposable health evidence between fresh negative episodes."""
        saved = {path: path.read_bytes() for parent in (self.output, self.owner)
                 for path in parent.rglob('*') if path.is_file()}
        clock, monotonic = self.clock, self.monotonic
        def restore():
            self.reset()
            for path, data in saved.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            self.clock, self.monotonic = clock, monotonic
        return restore

    def worker_child(self, process, started, identity, *, fault=None):
        """Execute the real worker body with CPU-only observation providers.

        The older receipt fixture supplies inert Main outputs and observation
        templates, then is removed. Only run_worker writes the new start,
        immutable observations, audit report and final receipt. No native
        arithmetic, CUDA, model, provider or controller is executed.
        """
        from contextlib import contextmanager
        import pytest
        context_path = Path(process.command[process.command.index('--context') + 1])
        context_ref = c.ref(context_path)
        output = context_path.parent
        parent_files = {p for p in output.rglob('*') if p.is_file()}
        clock, monotonic = self.clock, self.monotonic
        self.episode_child(process, started, identity)
        receipt = r.read_json(output / 'eds_eval/n36-worker-receipt.json')
        report = w.read_ref(receipt['audit_report'])
        generated = {p: p.read_bytes() for p in output.rglob('*') if p.is_file() and p not in parent_files}
        worker_names = {'n36-worker-start.json', 'n36-worker-receipt.json',
                        'n36-runtime-before.json', 'n36-runtime-after.json', 'decision-evidence-audit.json'}
        for path in generated:
            path.unlink()
        self.clock, self.monotonic = clock, monotonic
        process.returncode = None
        self.worker_calls = []
        def main(path):
            self.worker_calls.append('main')
            assert path == str(self.source / 'main.py')
            for dest, data in generated.items():
                if dest.name not in worker_names:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(data)
            if fault == 'main_failure':
                raise RuntimeError('CPU simulated Main failure')
        @contextmanager
        def observe(proof):
            self.worker_calls.append('controller_observation')
            yield receipt['controller_instances']
        def execution(root, source, runtime, *, binding):
            phase = binding['phase'].removeprefix('runtime_')
            self.worker_calls.append('execution_' + phase)
            return copy.deepcopy(receipt['execution_' + phase])
        def runtime_observation(closure, runtime_ref, *, binding, after=False):
            phase = 'after' if after else 'before'
            self.worker_calls.append('runtime_' + phase)
            return copy.deepcopy(receipt['runtime_' + phase])
        def generic_audit(*args, **kwargs):
            self.worker_calls.append('generic_audit')
            return {**copy.deepcopy(report), 'n23_arithmetic_backend': kwargs['arithmetic_backend'].report()}
        def native_audit(*args, **kwargs):
            self.worker_calls.append('native_audit_simulated')
            if fault == 'audit_failure':
                raise ValueError('CPU simulated native audit failure')
            return copy.deepcopy(args[2])
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(w, 'process_identity', lambda: identity)
            patch.setattr(worker.source_execution, 'bind_dino', lambda ref: None)
            patch.setattr(worker.source_execution, 'run_main', main)
            patch.setattr(worker.source_execution, 'attest', execution)
            patch.setattr(worker.closure, 'attest_runtime_receipt', runtime_observation)
            patch.setattr(worker.native_build, 'attest', lambda ref, after=False:
                          copy.deepcopy(receipt['native_build_after' if after else 'native_build_before']))
            patch.setattr(worker, 'attest_worker_loaded', lambda *a: copy.deepcopy(receipt['loaded_before']))
            patch.setattr(worker.controller, 'observe_instances', observe)
            patch.setattr(w, 'cuda_binding', lambda runtime: {'fixture_only': True})
            patch.setattr(worker, 'assigned_cuda_identity', lambda binding: copy.deepcopy(receipt['worker_cuda']))
            patch.setattr(worker.generic, 'audit_episode', generic_audit)
            patch.setattr(worker, 'audit_native', native_audit)
            code = worker.run_worker(context_ref)
        actual = r.read_json(output / 'eds_eval/n36-worker-receipt.json')
        self.worker_error = actual.get('error')
        assert actual['process'] == identity and actual['process_unchanged'] is True
        assert actual['accepted'] is (fault is None), self.worker_error
        self.clock += 1
        self.monotonic += 1
        process.returncode = code
        return code

    def episode_child(self, process, started, identity):
        """Simulated child artifacts; every consuming validator stays real."""
        from hydra import compose, initialize_config_dir
        from omegaconf import OmegaConf
        import cv2
        import numpy as np
        from scripts import qd_ed_n31_native as control
        from scripts import qd_ed_n36_dino as dino
        sx = runner.source_execution
        context_path = Path(process.command[process.command.index('--context') + 1])
        context_ref = c.ref(context_path)
        context = w.read_ref(context_ref)
        manifest = w.read_ref(context['expected_manifest'])
        output, row = Path(manifest['output_dir']), e.row()
        with initialize_config_dir(config_dir=str(self.source / 'configs'), version_base=None):
            config = OmegaConf.to_container(compose(config_name='config', overrides=manifest['argv'][2:]), resolve=False)
        (output / '.hydra').mkdir()
        (output / '.hydra/config.yaml').write_text(yaml.safe_dump(config))
        (output / 'results.txt').write_text('Success count: 0/1\nSuccess rate: 0.0%\n')
        video = output / 'episode_1/episode_1_fail.mp4'
        video.parent.mkdir()
        cv2.setNumThreads(2)
        writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*'mp4v'), 1., (16, 16))
        assert writer.isOpened()
        writer.write(np.zeros((16, 16, 3), dtype=np.uint8))
        writer.release()
        ev = output / 'eds_eval'
        ev.mkdir(exist_ok=True)
        for name, records in {'episode_metadata': [{'episode_id': 0, 'episode_seed': row['env_seed'], 'task_id': 0}],
                              'eds_metrics': [], 'stage_events': [], 'safety_events': []}.items():
            lines(ev / (name + '.jsonl'), records)
        transport = {**self.runtime['frozen_stage_provider'], 'application_max_attempts': 1,
            'internal_http_retry_observation_available': False, 'internal_retry_policy': 'cli_managed_unknown',
            'recovered_error_policy': 'pre_final_only_v1'}
        compute = {'schema': 'qd-ed-episode-compute-v2', 'episode_id': 0, 'task_id': 0,
            'episode_seed': row['env_seed'], 'policy_counters_available': True,
            'provider_counters_available': True, 'perception_counters_available': True,
            **{name: None if name in r.CODEX_UNKNOWN_HTTP_FIELDS else 0 for name in r.COMPUTE_FIELDS},
            'model_forward_batch_sizes': [], 'stage_transport': transport, 'outcome': 'completed',
            'provider_http_counters_available': False, 'provider_logical_counters_available': True,
            'provider_token_usage_complete': True}
        for prefix in ('stage_codex_', 'provider_'):
            compute.update({prefix + name: 0 for name in r.CODEX_COUNT_SUFFIXES})
            compute.update({prefix + 'reasoning_output_tokens': None, prefix + 'call_latency_s': 0.})
        lines(ev / 'episode_compute.jsonl', [compute])
        put(ev / 'decision_evidence/episode_000/status.json', {'notice': 'CPU simulated child evidence'})
        lines(ev / 'decision_evidence/episode_000/events.jsonl', [])
        backend = {'kind': 'cpu', 'logical_device': 'cpu'}
        report = {'accepted': True, 'evidence_complete': True, 'observed_counts': {},
            'n23_arithmetic_backend': backend, 'n36_control_absence': {'profile': 'C0', 'events': 0, 'metrics': 0},
            'n34_control_absence': {'profile': 'C0', 'events': 0, 'metrics': 0},
            'n36_control_arithmetic': {'kind': 'native_recomputation', 'device': 'cuda:0', 'gpu_attested': True},
            control.GATE: {'schema': 'n31-independent-capture-dwell-v1', 'profile': 'C0',
                'guided_decisions': 0, 'canonical_batches_verified': 0, 'canonical_candidates_verified': 0,
                'compute_expected': {'guided_chunks': 0}}, 'fixture_only': True}
        report_ref = put(ev / 'decision-evidence-audit.json', report)
        counts, auxiliary = worker.native_counts('C0', output, report, None)
        source_index = {v['path']: v['sha256'] for v in self.source_record['files']}
        names = {'scripts.qd_ed_n36_' + name for name in
                 ('worker', 'bridge', 'contract', 'native', 'build', 'lifecycle', 'arithmetic', 'reference',
                  'source', 'engineering', 'release', 'accounting', 'stop')}
        names |= {'scripts.' + name for name in ('qd_ed_n23_worker', 'audit_decision_evidence',
                 'qd_ed_n31_native', 'qd_ed_n34_controller', 'qd_ed_n34_source', 'qd_ed_n34_worker', 'qd_ed_n34_native')}
        names |= {name.removesuffix('.py').replace('/', '.') for name in b.RUNTIME_SOURCES if name != 'main.py'}
        names |= {'scripts.maniskill_model', 'core.env_adapters.libero_adapter', 'models.rdt_runner',
                  'models.multimodal_encoder.siglip_encoder', 'models.multimodal_encoder.t5_encoder', 'configs.state_vec'}
        loaded = {}
        for name in names:
            path = name.replace('.', '/') + '.py'
            if path not in source_index:
                path = 'third_party/rdt/' + path
            loaded[name] = {'path': path, 'sha256': source_index[path]}
        loaded['scripts.qd_ed_n36_worker'].update(module_name='scripts.qd_ed_n36_worker',
            spec_name='scripts.qd_ed_n36_worker', origin=str(self.source / 'scripts/qd_ed_n36_worker.py'))
        native = w.read_ref(self.native_ref)
        native_receipt = {'schema': 'n36-loaded-native-build-v1', 'manifest': self.native_ref, 'libraries': native['libraries']}
        receipt = {'schema': 'n36-worker-receipt-v2', **e.operational_binding(self.plan),
            'process': identity, 'process_unchanged': True, 'accepted': True, 'main_exit_code': 0,
            'context': context_ref, 'plan': self.plan_ref, 'expected_manifest': context['expected_manifest'],
            'source': self.source_record, 'scientific_source': self.source_record, 'row': row,
            'attempt_id': e.EPISODE_KEY, 'evidence': worker.evidence(output), 'audit_backend': backend,
            'worker_cuda': {'physical_gpu': 7, 'uuid': c.GPU_UUID, 'logical_device': 'cuda:0',
                'physical_uuid': worker.canonical_cuda_uuid(c.GPU_UUID), 'actual_uuid': c.GPU_UUID,
                'actual_uuid_type': 'builtins.str', 'actual_uuid_bytes_hex': None},
            'audit_report': report_ref, 'native_counts': counts, 'auxiliary': auxiliary,
            'controller_instances': [{k: w.read_ref(self.controller_ref)[k] for k in ('source', 'module', 'class', 'instance')}],
            'worker_wall_seconds': 1., 'audit_seconds': .1, 'fixture_only': True}
        put(ev / 'n36-worker-start.json', {'context': context_ref, 'process': identity})
        for phase in ('before', 'after'):
            binding = worker.runtime_receipt_binding(context_ref, self.plan, identity, 'runtime_' + phase)
            runtime_receipt = {'schema': 'n34-runtime-receipt-v2', 'binding': binding,
                               'modules': self.closure['modules'], 'generated_modules': {}}
            compiled = [{'module': name, 'path': str(self.source / record['path']), 'sha256': record['sha256']}
                        for name, record in loaded.items()]
            compiled += [{'module': name, **record} for name, record in self.closure['modules'].items()]
            compiled.append({'module': 'main', 'path': str(self.source / 'main.py'), 'sha256': source_index['main.py']})
            ds = dino.DinoSources(self.runtime_ref)
            dino_rows = [{'module': name, 'path': path, 'sha256': ds.files[path]['sha256']} for name, path in ds.names.items()]
            compiled += dino_rows
            execution = {'schema': 'n36-source-execution-v2', 'binding': binding,
                'interpreter': self.closure['interpreter'], 'search_prefix': str(Path(sys.executable).resolve().parent.parent),
                'search_path': [str(self.source)], 'compiled': compiled,
                'startup_source_only': [{'module': name, **self.closure['modules'][name]} for name in
                                        ('encodings', 'encodings.aliases', 'encodings.utf_8')],
                'frozen_modules': sorted(['posixpath', '_frozen_importlib', '_frozen_importlib_external']),
                'bootstrap': {'path': str(self.source / 'scripts/qd_ed_n36_bootstrap.py'),
                              'sha256': source_index['scripts/qd_ed_n36_bootstrap.py']},
                'frozen_aliases': {'os.path': sx.alias_claim(self.closure, binding)},
                'frozen_importlib_aliases': {alias: sx.importlib_alias_claim(self.closure, binding, alias, canonical)
                                            for alias, canonical in sx.IMPORTLIB_FROZEN_PAIRS},
                'dino_sources': {'runtime_manifest': self.runtime_ref, 'root': ds.root, 'compiled': dino_rows}}
            observation = {'runtime_' + phase: runtime_receipt, 'execution_' + phase: execution,
                           'loaded_' + phase: loaded, 'native_build_' + phase: native_receipt}
            receipt.update(observation)
            receipt['observation_' + phase] = put(ev / ('n36-runtime-' + phase + '.json'), observation)
        put(ev / 'n36-worker-receipt.json', receipt)
        self.clock += 1
        self.monotonic += 1
        process.returncode = 0
        return 0
