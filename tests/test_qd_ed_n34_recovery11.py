"""CPU-only identity/accounting regressions; no runtime or release generation."""
import copy
import datetime as dt
import unittest
from collections import Counter
from unittest.mock import patch

from scripts import qd_ed_n34_contract as c
from scripts import qd_ed_n34_release as release
from scripts import qd_ed_n34_report as report
from scripts import qd_ed_n34_supervise as supervisor


class Recovery11Tests(unittest.TestCase):
    def setUp(self):
        self.rows = c.expected_rows()
        self.plan = {'worktree': str(c.ROOT), 'episodes': self.rows}

    def events(self, rows=None, successes=None):
        events = []
        for row in self.rows if rows is None else rows:
            base = {'attempt_id': row['episode_key'], 'episode_key': row['episode_key'],
                    'identity': supervisor.c_identity(row), 'budget_bucket': row['budget_bucket'],
                    'replacement': copy.deepcopy(row['replacement'])}
            events.extend({**copy.deepcopy(base), 'event': kind} for kind in ('reserved', 'dispatched'))
            events.append({**base, 'event': 'valid', 'outcome_valid': True,
                           'required_cost_telemetry_complete': True,
                           'success': successes(row) if successes else True})
        return events

    def history(self):
        events = []
        for index, (episode, cohort, bucket) in enumerate(c.INVALID_HISTORY):
            for kind in ('reserved', 'dispatched', 'valid' if index % 2 else 'aborted'):
                events.append({'attempt_id': episode, 'episode_key': episode,
                               'identity': {'iteration': cohort}, 'budget_bucket': bucket,
                               'event': kind, 'outcome_valid': False, 'success': None,
                               'required_cost_telemetry_complete': False,
                               'gpu_process_wall_seconds': 10. + index,
                               'http_counters': 'Unknown'})
        return events

    def test_all30_fresh_task_major_keys_and_exact_buckets(self):
        self.assertEqual(c.COHORT, 'N34R11_OBSERVED_JAW_APPROACH_DEV_20261008')
        self.assertEqual([(r['task_id'], r['profile']) for r in self.rows],
                         [(task, arm) for task in range(10) for arm in ('C0', 'Q0', 'N34')])
        self.assertEqual(len({r['episode_key'] for r in self.rows}), 30)
        for row in self.rows:
            self.assertEqual(row['episode_key'], f'n34r11_dev_t{row["task_id"]:02d}_{row["profile"].lower()}_20261008')
            self.assertEqual(row['iteration'], c.COHORT)
            c.require_row(row)
        self.assertEqual(Counter(r['budget_bucket'] for r in self.rows),
                         {'recovery': 1, 'baseline': 9, 'development': 20})
        self.assertEqual([r['replacement'] for r in self.rows[1:]], [None] * 29)

    def test_exact_turn715_replacement(self):
        self.assertEqual(c.REPLACEMENT, {
            'old_episode_key': 'n34r10_dev_t00_c0_20261008',
            'new_episode_key': 'n34r11_dev_t00_c0_20261008', 'budget_bucket': 'recovery',
            'terminal_closure': {
                'path': '/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/000715/terminal-closure-v1.json',
                'sha256': '7ef0fb93d65b4c14fabdc2786f6711c5f0a2821efe140d70638cecd1b1f7ab2f'},
            'automatic': False})
        plan = {**self.plan, 'schema': 'n34-released-plan-v1'}
        c.require_recovery_row(plan, self.rows[0])
        for row in self.rows[1:]:
            with self.assertRaises(ValueError):
                c.require_recovery_row(plan, row)

    def test_stale_rows_and_terminal_references_rejected(self):
        stale = copy.deepcopy(self.rows[0])
        stale['iteration'] = c.OLD_COHORT
        stale['episode_key'] = c.OLD_EPISODE
        mutations = [stale]
        for key, value in [('path', c.REPLACEMENT['terminal_closure']['path'].replace('000715', '000704')),
                           ('sha256', 'c27a1d6c0a041f3bdd3218525907d6c2b523e84e80076b8b37521113fc62a2f1')]:
            row = copy.deepcopy(self.rows[0])
            row['replacement']['terminal_closure'][key] = value
            mutations.append(row)
        for row in mutations:
            with self.subTest(row=row), self.assertRaises(ValueError):
                c.require_row(row)
            with self.assertRaises(ValueError):
                supervisor.reconcile({**self.plan, 'episodes': [row] + self.rows[1:]}, [], lambda *_: None)

    def test_replacement_and_bucket_cannot_move_or_disappear(self):
        for index, key, value in [(0, 'budget_bucket', 'baseline'), (0, 'replacement', None),
                                   (1, 'budget_bucket', 'recovery'), (1, 'replacement', c.REPLACEMENT),
                                   (3, 'budget_bucket', 'development')]:
            row = {**self.rows[index], key: value}
            with self.subTest(index=index, key=key), self.assertRaises(ValueError):
                c.require_row(row)
        for field, value in [('old_episode_key', 'n34r9_dev_t00_c0_20261008'),
                             ('new_episode_key', c.OLD_EPISODE), ('automatic', True)]:
            row = copy.deepcopy(self.rows[0])
            row['replacement'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                c.require_row(row)

    def test_stale_terminal_cannot_bind_to_fresh_attempt(self):
        for mutation in ('identity', 'attempt_id', 'episode_key', 'replacement', 'budget_bucket', 'retry_of', 'recovery_of'):
            events = self.events(self.rows[:1])
            final = events[-1]
            if mutation == 'identity':
                final['identity']['iteration'] = c.OLD_COHORT
            elif mutation == 'replacement':
                final['replacement']['terminal_closure']['sha256'] = '0' * 64
            elif mutation == 'budget_bucket':
                final[mutation] = 'baseline'
            else:
                final[mutation] = c.OLD_EPISODE
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                supervisor.reconcile(self.plan, events, lambda *_: None)

    def test_all_eleven_invalids_preserved_without_carrying_controls(self):
        history = self.history()
        original = copy.deepcopy(history)
        self.assertEqual(len(c.INVALID_HISTORY), 11)
        self.assertEqual([x[0] for x in c.INVALID_HISTORY], ['n34_dev_t00_c0_20261008'] +
                         [f'n34r{i}_dev_t00_c0_20261008' for i in range(1, 11)])
        c.require_replacement_history(history)
        result = supervisor.reconcile(self.plan, history, lambda *_: self.fail('historical control reused'))
        self.assertEqual(result['outcomes'], [])
        self.assertEqual(result['next_row'], self.rows[0])
        summary = report.summary(result, history)
        self.assertEqual(summary['matrix'][0]['C0'], 'Unknown')
        self.assertFalse(summary['prospective_dev_necessary_gate_met'])
        self.assertEqual(summary['charges_and_health_events_preserved'], original)
        self.assertEqual(history, original)
        snap = release.r.budget_snapshot(history, [])
        self.assertEqual(snap['dispatched'], 11)
        self.assertEqual(snap['by_bucket']['baseline'], 1)
        self.assertEqual(snap['by_bucket']['recovery'], 10)
        self.assertAlmostEqual(snap['gpu_hours_consumed'], sum(10. + i for i in range(11)) / 3600.)

    def test_each_historical_charge_required_and_invalid(self):
        for index in range(11):
            events = self.history()
            del events[index * 3:index * 3 + 3]
            with self.subTest(missing=index), self.assertRaises(ValueError):
                c.require_replacement_history(events)
        for field, value in [('outcome_valid', True), ('success', False),
                             ('required_cost_telemetry_complete', True), ('budget_bucket', 'baseline'),
                             ('gpu_process_wall_seconds', None), ('gpu_process_wall_seconds', float('nan'))]:
            events = self.history()
            events[-1][field] = value
            with self.subTest(field=field, value=value), self.assertRaises((ValueError, TypeError)):
                c.require_replacement_history(events)
        events = self.history()
        events[-1]['gpu_process_wall_seconds'] = None
        with self.assertRaises(release.r.GateError):
            release.r.budget_snapshot(events, [])

    def test_invalid_current_control_stops_with_charge_and_no_retry(self):
        events = self.events(self.rows[:1])
        events[-1].update(outcome_valid=False, success=None, required_cost_telemetry_complete=False)
        result = supervisor.reconcile(self.plan, events, lambda *_: self.fail('invalid control verified'))
        self.assertEqual(result['status'], 'INVALID_STOP')
        self.assertIsNone(result['next_row'])
        self.assertEqual(result['charged_events'], events)
        self.assertEqual(result['outcomes'], [])
        self.assertEqual(c.LIMITS['automatic_recoveries'], 0)

    def test_futility_only_after_complete_valid_triple(self):
        for count, status in [(16, 'READY_FOR_ROOT_RELEASE'), (17, 'READY_FOR_ROOT_RELEASE'),
                              (18, 'NUMERIC_FUTILITY')]:
            result = supervisor.reconcile(self.plan, self.events(self.rows[:count], lambda _: False), lambda *_: None)
            self.assertEqual(result['status'], status)
        events = self.events(self.rows[:18], lambda _: False)
        events[-1]['outcome_valid'] = False
        self.assertEqual(supervisor.reconcile(self.plan, events, lambda *_: None)['status'], 'INVALID_STOP')
        with self.assertRaises(ValueError):
            supervisor.reconcile(self.plan, self.events(self.rows[:19], lambda _: False), lambda *_: None)

    def test_promotion_still_requires_all30_five_and_both_controls(self):
        for totals, passed in [({'C0': 5, 'Q0': 5, 'N34': 5}, True),
                                ({'C0': 6, 'Q0': 5, 'N34': 5}, False),
                                ({'C0': 5, 'Q0': 6, 'N34': 5}, False),
                                ({'C0': 4, 'Q0': 4, 'N34': 4}, False)]:
            outcomes = [{**row, 'success': row['task_id'] < totals[row['profile']]} for row in self.rows]
            result = report.summary({'status': 'COMPLETE', 'outcomes': outcomes}, [])
            self.assertEqual(result['prospective_dev_necessary_gate_met'], passed)
            for name in ('validation_authorized', 'formal_authorized', 'release_enabled'):
                self.assertFalse(result[name])
            self.assertFalse(report.summary({'status': 'COMPLETE', 'outcomes': outcomes[:-1]}, [])['prospective_dev_necessary_gate_met'])
            self.assertFalse(report.summary({'status': 'INVALID_STOP', 'outcomes': outcomes}, [])['prospective_dev_necessary_gate_met'])

    def test_admission_counts_fresh_preparation_locally_and_all_history_globally(self):
        events = self.history()
        resources = [
            {'resource_id': 'old-preparation', 'kind': 'n34r10_resource_preparation_v1'},
            {'resource_id': 'fresh-preparation', 'kind': 'n34r11_resource_preparation_v1'},
            {'resource_id': 'fresh-cohort', 'cohort': c.COHORT},
            {'resource_id': 'old-cohort', 'cohort': c.OLD_COHORT}]
        authority = {'prospective_recovery': c.REPLACEMENT, 'caps': c.CAPS,
                     'amendment': 'synthetic', 'weekly_window': {'ends_at': c.DEADLINE},
                     'starts_at': '2026-10-08T00:00:00Z', 'coordinator_ends_at': c.DEADLINE}
        state = {'n34_budget_authority': 'synthetic-authority',
                 'budget': {'max_episode_attempts': 1800, 'max_gpu_hours': 224.,
                            'reserved': c.CAPS['buckets'], 'gpu_hour_reservations': c.CAPS['protected_gpu_hours'],
                            'amendment': 'synthetic'},
                 'resource_isolation': {'status': 'ACTIVE', 'validation_status': 'PASS', 'private_budget': True}}
        total = {'gpu_hours_consumed': 64., 'gpu_hours_by_bucket': {k: 0. for k in c.CAPS['buckets']},
                 'by_bucket': {k: 0 for k in c.CAPS['buckets']}, 'dispatched': 453}
        local = {**total, 'gpu_hours_consumed': 0.1, 'dispatched': 0}
        with patch.object(release.r, 'budget_snapshot', side_effect=[total, local]) as snapshot, \
             patch.object(release.r, 'authorized_gpu', return_value=7), \
             patch.object(release.r, 'check_budget_limits', return_value=1800), \
             patch('scripts.qd_ed_n31_contract.effective_hours', return_value=224.), \
             patch.object(c, 'pre_dispatch') as guard:
            result = release.admission({**self.plan, 'authority': 'synthetic-authority', 'stop_path': 'unused'},
                                       authority, state, events, resources, [], self.rows[0],
                                       now=dt.datetime(2026, 10, 9, tzinfo=dt.timezone.utc), gpu_idle=True)
        self.assertIs(result, total)
        self.assertEqual(snapshot.call_args_list[0].args, (events, resources))
        self.assertEqual(snapshot.call_args_list[1].args, ([], resources[1:3]))
        allowance = guard.call_args.args[1]
        self.assertEqual(allowance['cohort_seconds_remaining'], 17640.)
        self.assertEqual(allowance['global_attempts_remaining'], 1347)

    def test_stale_plan_rejected_before_release_or_runtime_access(self):
        stale_rows = copy.deepcopy(self.rows)
        for row in stale_rows:
            row['iteration'] = c.OLD_COHORT
            row['episode_key'] = row['episode_key'].replace('n34r11', 'n34r10')
        stale_plan = {**self.plan, 'episodes': stale_rows, 'schema': 'n34-released-plan-v1',
                      'frozen': True, 'release_enabled': True}
        with self.assertRaises(ValueError):
            release.validate_plan(stale_plan)
        with self.assertRaises(ValueError):
            c.require_release(stale_plan)


if __name__ == '__main__':
    unittest.main()
