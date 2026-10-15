"""Focused pure-dictionary fix review; no actual data or dependency imports."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import sys

SOURCE = Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-decision-evidence-20260923/docs/03_evidence/qd_ed_final/continuation_20260923/full-dev-closed-loop-preparation/read_full_dev.py')
SOURCE_SHA = 'b19331ff6861210056858d56da6dcbd2d6a24f06fc91e24dcc1beb0d4df18b3e'
COMMIT = 'e1d2dbccb1bda39cccb680bd80bb7e590ff00319'
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == SOURCE_SHA
spec = importlib.util.spec_from_file_location('reviewed_full_dev_source_v2', SOURCE)
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)

decisions = [
    {'global_step': 0, 'last_executed_step': 7, 'executed_prefix_length': 8,
     'decision_id': 'd0', 'reset_sequence': 0, 'stage': 1, 'use_guidance': True},
    {'global_step': 8, 'last_executed_step': 8, 'executed_prefix_length': 1,
     'decision_id': 'd1', 'reset_sequence': 0, 'stage': 1, 'use_guidance': False},
]
steps = [{'global_step': i, 'reset_sequence': 0, 'terminated': False, 'truncated': False,
          'command': {'value': [0.] * 6 + ([1.] if i == 0 else [-1.])}} for i in range(9)]
common = {'episode_id': 0, 'task_id': 0, 'episode_seed': 100,
          'query_status': 'ok', 'trigger_reason': 'synthetic', 'gripper_value_used': 1.}
results, all_events = [], []

def check(name, event, expectation):
    original = copy.deepcopy(event)
    value = r.joined_stage([event], decisions, steps)
    assert event == original and value['events'] == [original]
    assert value['query_status_counts'] == {'ok': 1}
    assert value['trigger_counts'] == {'synthetic': 1}
    item = value['associations'][0]
    if expectation == 'unknown_location':
        assert item['location_status'] == 'Unknown_missing_or_invalid_step'
        assert item['current_decision_id'] is None and item['preceding_decision_id'] is None
        assert item['same_step_context_agrees'] is None and item['matches_first_sent'] is None
        assert item['state_comparison_status'].startswith('Unknown')
    else:
        assert item['location_status'] == 'recorded_nonnegative_integer'
        assert item['current_decision_id'] == 'd1' and item['preceding_decision_id'] == 'd0'
        assert item['matches_first_sent'] is True and item['matches_last_sent'] is False
        if expectation == 'unknown_state':
            assert item['same_step_context_agrees'] is None
            assert item['state_comparison_status'].startswith('Unknown')
        else:
            expected = expectation == 'known_match'
            assert item['same_step_context_agrees'] is expected
            assert item['state_comparison_status'] == expectation
    results.append({'case': name, 'passed': True, 'association': item})
    all_events.append(original)

for name, fields in [
    ('missing_global_step', {}), ('null_global_step', {'global_step': None}),
    ('negative_global_step', {'global_step': -1}), ('boolean_global_step', {'global_step': True}),
    ('float_global_step', {'global_step': 8.0}), ('string_global_step', {'global_step': '8'}),
]:
    check(name, {**common, 'stage_after': 1, 'guidance_after': False, **fields}, 'unknown_location')

for name, fields in [
    ('missing_both_after', {}), ('missing_stage_after', {'guidance_after': False}),
    ('missing_guidance_after', {'stage_after': 1}),
    ('null_stage_after', {'stage_after': None, 'guidance_after': False}),
    ('null_guidance_after', {'stage_after': 1, 'guidance_after': None}),
    ('boolean_stage_after', {'stage_after': True, 'guidance_after': False}),
    ('integer_guidance_after', {'stage_after': 1, 'guidance_after': 0}),
    ('negative_stage_after', {'stage_after': -1, 'guidance_after': False}),
    ('float_stage_after', {'stage_after': 1.0, 'guidance_after': False}),
    ('string_guidance_after', {'stage_after': 1, 'guidance_after': 'False'}),
]:
    check(name, {**common, 'global_step': 8, **fields}, 'unknown_state')

check('known_equal', {**common, 'global_step': 8, 'stage_after': 1, 'guidance_after': False}, 'known_match')
check('known_stage_mismatch', {**common, 'global_step': 8, 'stage_after': 2, 'guidance_after': False}, 'known_mismatch')
check('known_guidance_mismatch', {**common, 'global_step': 8, 'stage_after': 1, 'guidance_after': True}, 'known_mismatch')

absent = r.joined_stage(None, decisions, steps)
assert absent['status'] == 'not_recorded' and absent['events'] is None
assert absent['associations'] is None and absent['query_status_counts'] is None and absent['trigger_counts'] is None
results.append({'case': 'absent_stage', 'passed': True, 'value': absent})
empty = r.joined_stage([], decisions, steps)
assert empty['status'] == 'recorded' and empty['events'] == [] and empty['associations'] == []
assert empty['query_status_counts'] == {} and empty['trigger_counts'] == {}
results.append({'case': 'present_empty_stage', 'passed': True, 'value': empty})

before = copy.deepcopy(all_events)
mixed = r.joined_stage(all_events, decisions, steps)
assert mixed['events'] == before and all_events == before
assert len(mixed['associations']) == len(all_events) == 19
assert [x['event_index'] for x in mixed['associations']] == list(range(19))
assert mixed['query_status_counts'] == {'ok': 19} and mixed['trigger_counts'] == {'synthetic': 19}
assert [x['same_step_context_agrees'] for x in mixed['associations']] == [None] * 16 + [True, False, False]
results.append({'case': 'mixed_event_stream_all_preserved', 'passed': True, 'events': 19})
assert len(results) == 22
assert 'torch' not in sys.modules
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == SOURCE_SHA
out = {'schema': 'full-dev-chronology-fix-reproduction-v2', 'reviewed_commit': COMMIT,
       'reviewed_source_sha256': SOURCE_SHA,
       'reproduction_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
       'scope': '22 focused pure-dictionary checks; overlap with implementer tests, not extra independent performance evidence',
       'passed': 22, 'failed': 0, 'torch_imported': False, 'actual_bundle_loads': 0,
       'actual_read_authorized': False, 'results': results}
with Path(__file__).with_name('reproductions-v2.json').open('x') as f:
    json.dump(out, f, indent=2, allow_nan=False)
    f.write('\n')
print(json.dumps({k: out[k] for k in ('passed', 'failed', 'torch_imported', 'actual_bundle_loads')}))
