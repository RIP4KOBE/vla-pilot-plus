"""CPU-only proposal checks: no GPU, provider, simulator or process launch."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('observed_pairs', HERE/'observed-pairs.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
sys.path.insert(0, str(p.ROOT/'scripts'))
import qd_ed_final_runner as r


class Tests(unittest.TestCase):
    def dev_seeds(self):
        # Read only the dev block; no evaluation output or held-out row is used.
        return {'blocks': {'dev': json.loads((p.ROOT/'data/frozen-seed-plan.json').read_text())['blocks']['dev']}}

    def test_fixed_rows_pair_frozen_dev_identities_and_reject_drift(self):
        seeds = self.dev_seeds()
        rows = p.rows_from_dev(seeds)
        self.assertEqual([(row['task_id'], row['profile']) for row in rows], p.ORDER)
        self.assertEqual([row['env_seed'] for row in rows], [1969522881]*2+[970869399]*2)
        for left, right in ((rows[0], rows[1]), (rows[2], rows[3])):
            self.assertEqual({field: left[field] for field in p.FIELDS}, {field: right[field] for field in p.FIELDS})
        self.assertTrue(all(row['budget_bucket'] == 'development' and 'retry_of' not in row for row in rows))
        plan = {'episodes': rows, 'phase_authorization': {'dev': True, 'validation': False, 'formal': False},
            'boot_id': p.BOOT, 'observational_overrides': {'main.decision_evidence.enabled': True},
            'decision_evidence_gate': 'stop_remaining_on_incomplete_preserve_task_outcome'}
        p.validate_pair_contract(plan, seeds)
        plan['episodes'][1]['policy_seed'] += 1
        with self.assertRaisesRegex(ValueError, 'paired rows'):
            p.validate_pair_contract(plan, seeds)

    def test_named_profile_preserves_algorithms_and_original_runner_emits_flag(self):
        path = p.ROOT/'configs/qd_ed_final/baseline_profiles.json'
        baseline = json.loads(path.read_text())
        before = copy.deepcopy(baseline)
        observed = p.observed_profiles(baseline, hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(observed, json.loads((HERE/'observed-baseline-profiles.json').read_text()))
        self.assertEqual(baseline, before)
        for arm in ('C0', 'Q0'):
            old, new = baseline['profiles'][arm], observed['profiles'][arm]
            changed = {key for key in new if new[key] != old[key]}
            self.assertEqual(changed, {'static_override_values', 'hydra_overrides', 'historical_label'})
            self.assertEqual(new['restored_profile'], old['restored_profile'])
            self.assertEqual(new['resolved_eds_config'], old['resolved_eds_config'])
            self.assertEqual(new['static_override_values'], {**old['static_override_values'], 'main.decision_evidence.enabled': True})
        with tempfile.TemporaryDirectory() as folder:
            row = p.rows_from_dev(self.dev_seeds())[0]
            command, _ = r.build_command({'artifact_root': folder, 'worktree': str(p.ROOT)}, observed,
                {'tasks': {'0': {'cache_dir': folder}}, 'main_overrides': ['+main.require_task_cache_identity=true']}, row, 'CPU_PREVIEW')
            self.assertEqual(command.count(p.OVERRIDE), 1)

    def test_evidence_gate_occurs_after_original_return_and_does_not_rewrite_outcome(self):
        result = {'event': 'valid', 'outcome_valid': True, 'success': False, 'output_dir': '/cpu-only/attempt'}
        original = Mock(return_value=[result])
        api = SimpleNamespace(run_plan=original, durable_json=Mock(), require=r.require)
        audit = Mock(return_value={'accepted': False, 'errors': ['incomplete']})
        with p.audited_calls(api, audit):
            with self.assertRaisesRegex(r.GateError, 'remaining undispatched rows stopped'):
                api.run_plan('frozen-plan', episode_keys=[p.KEYS[0]])
        self.assertIs(api.run_plan, original)
        original.assert_called_once()
        self.assertEqual(result, {'event': 'valid', 'outcome_valid': True, 'success': False, 'output_dir': '/cpu-only/attempt'})
        self.assertEqual(api.durable_json.call_args.args[0], Path('/cpu-only/attempt/eds_eval/decision-evidence-audit.json'))
        observation = api.durable_json.call_args.args[1]['wrapper_observation']
        self.assertGreaterEqual(observation['audit_wall_seconds'], 0)
        self.assertGreater(observation['parent_ru_maxrss_before_kib'], 0)
        self.assertGreaterEqual(observation['parent_ru_maxrss_after_kib'], observation['parent_ru_maxrss_before_kib'])
        self.assertIn('not audit-exclusive', observation['memory_scope'])
        self.assertFalse(any('delta' in key for key in observation))
        audit.return_value = {'accepted': True}
        with p.audited_calls(api, audit):
            self.assertIs(api.run_plan('frozen-plan')[0], result)
        summary = p.queue_summary({'status': 'completed', 'completed_keys': [p.KEYS[0]],
            'results': [{**result, 'attempt_id': 'one', 'stage_transport': {'skills': 'not-for-summary'}}]},
            SimpleNamespace(read_json=Mock(return_value=api.durable_json.call_args.args[1])))
        self.assertEqual(summary['attempts'][0]['attempt_id'], 'one')
        self.assertNotIn('stage_transport', json.dumps(summary))
        self.assertNotIn('not-for-summary', json.dumps(summary))

    def test_batch_budget_preserves_full_four_timeouts_and_protected_hours(self):
        snap = {'dispatched': 12, 'by_bucket': {'development': 4, 'validation': 0, 'formal': 0},
                'gpu_hours_consumed': 22., 'gpu_hours_by_bucket': {'validation': 0., 'formal': 0.}}
        api = SimpleNamespace(budget_snapshot=lambda *_: snap, check_retry=Mock(),
            check_budget=Mock(return_value=1800), require=r.require, TERMINATION_GRACE_SECONDS=40)
        state = {'budget': {'max_episode_attempts': 240, 'max_gpu_hours': 48,
                           'reserved': {'development': 100}}}
        rows = p.rows_from_dev(self.dev_seeds())
        with self.assertRaisesRegex(r.GateError, 'protected GPU-hour'):
            p.batch_budget(api, state, [], [], rows, [])
        snap['gpu_hours_consumed'] = 21.
        p.batch_budget(api, state, [], [], rows, [])
        api.check_budget.return_value = 1799
        with self.assertRaisesRegex(r.GateError, 'full episode timeout'):
            p.batch_budget(api, state, [], [], rows, [])

    def journal_fixture(self, episode_seconds=3600):
        rows = p.rows_from_dev(self.dev_seeds())
        base = {'attempt_id': 'previous', 'budget_bucket': 'development',
                'identity': r.episode_identity({**rows[0], 'iteration': 'PREVIOUS'})}
        events = [{**base, 'event': 'reserved'}, {**base, 'event': 'dispatched'},
                  {**base, 'event': 'aborted', 'gpu_process_wall_seconds': episode_seconds}]
        resources = [{'resource_id': 'health', 'event': 'reserved'},
                     {'resource_id': 'health', 'event': 'dispatched'},
                     {'resource_id': 'health', 'event': 'completed', 'gpu_process_wall_seconds': 1800}]
        state = {'gpu_pool': [3], 'max_concurrent_gpu_workers': 1,
            'budget': {'max_episode_attempts': 240, 'max_gpu_hours': 48,
                'reserved': dict(r.BUCKETS), 'gpu_hour_reservations': {'validation': 14., 'formal': 10.},
                'dispatched': 239, 'aborted': 99, 'valid': 99, 'invalid': 99,
                'completed': 198, 'running': 1, 'gpu_hours_consumed': 47.},
            'runner': {'untouched_mutable_metadata': 'not used by budget checks'}}
        return state, events, resources, rows

    def test_actual_budget_uses_read_only_journal_view_including_resource_cost(self):
        state, events, resources, rows = self.journal_fixture()
        originals = copy.deepcopy((state, events, resources))
        with tempfile.TemporaryDirectory() as folder:
            paths = [Path(folder)/name for name in ('research-state.yaml', 'attempt-ledger.jsonl', 'gpu-healthcheck-ledger.jsonl')]
            for path, value in zip(paths, originals): path.write_text(json.dumps(value))
            before = [path.read_bytes() for path in paths]
            with patch.object(r, 'sync_state_from_journal', side_effect=AssertionError('must not persist')) as sync:
                view = p.journal_budget_view(r, state, events, resources)
                p.batch_budget(r, view, events, resources, rows, [])
                sync.assert_not_called()
            self.assertEqual([path.read_bytes() for path in paths], before)
        self.assertEqual((state, events, resources), originals)
        self.assertEqual(view['budget']['dispatched'], 1)
        self.assertEqual(view['budget']['gpu_hours_consumed'], 1.5)
        self.assertEqual(view['budget']['running'], 0)
        for name in ('max_episode_attempts', 'max_gpu_hours', 'reserved', 'gpu_hour_reservations'):
            self.assertEqual(view['budget'][name], state['budget'][name])
        self.assertEqual(view['runner'], state['runner'])
        self.assertEqual(r.check_budget(view, events, rows[0], resources, [], physical_gpu=3), 1800)

    def test_actual_journal_limits_still_reject_optimistic_stale_state(self):
        state, events, resources, rows = self.journal_fixture(21.5*3600)
        state['budget'].update(dispatched=0, gpu_hours_consumed=0.)
        original = copy.deepcopy(state)
        view = p.journal_budget_view(r, state, events, resources)
        self.assertEqual(view['budget']['gpu_hours_consumed'], 22.)
        with self.assertRaisesRegex(r.GateError, 'protected GPU-hour'):
            p.batch_budget(r, view, events, resources, rows, [])
        events[-1]['gpu_process_wall_seconds'] = 48*3600
        exhausted = p.journal_budget_view(r, state, events, resources)
        with self.assertRaisesRegex(r.GateError, 'GPU budget exhausted'):
            p.batch_budget(r, exhausted, events, resources, rows, [])
        self.assertEqual(state, original)


if __name__ == '__main__': unittest.main()
