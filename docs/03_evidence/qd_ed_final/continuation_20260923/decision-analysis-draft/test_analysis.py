"""Explicitly synthetic CPU diagnostics plus the existing collector's CPU test fixture.

These are numerical/audit tests, never experimental episodes or evidence of a hypothesis.
"""
import copy
import importlib.util
import json
import os
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = next(p for p in HERE.parents if (p / 'scripts/audit_decision_evidence.py').is_file())


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


a = module('offline_selected_analysis', HERE / 'analyze_episode.py')
fixture = module('existing_cpu_audit_fixture', ROOT / 'tests/test_decision_evidence_audit.py')
torch = a.cpu_torch()


def observations(xs):
    return [{'eef': [x, 0., 0.], 'eef_ulp_m': 1e-9,
             'action': [0., 0., 0., 0., 0., 0., -1. if i < 7 else 1.],
             'gripper_qpos': [i * .01, -i * .01]} for i, x in enumerate(xs)]


def calculate(predicted, actual=None, target=(1., 0., 0.)):
    if actual is None:
        actual = predicted
    return a.numerical_diagnostics([[0., 0., 0.]] + [[x, 0., 0.] for x in predicted],
        [0., 0., 0.], list(target) if target is not None else None,
        observations(actual), [1e-9] * (len(predicted) + 1))


def test_straight_exact_tracking_and_command_sign_change():
    value = calculate([i / 10 for i in range(1, 9)])
    assert value['actual_frozen_target_progress_m'] == pytest.approx(.8)
    assert value['eef_projection_rmse_m'] == 0
    assert value['projected_motion_tracking_gain'] == pytest.approx(1)
    assert value['step7_to8']['actual_distance_increase_m'] == pytest.approx(-.1)
    assert value['step7_to8']['gripper_commands'] == [-1., 1.]
    assert value['step7_to8']['gripper_command_switched']
    assert value['step7_to8']['gripper_qpos_change_l2'] == pytest.approx(2**.5 * .01)
    assert not value['projection_optimism_witness']


def test_tail_reversal_is_measured_from_real_step7_and8():
    value = calculate([.1, .2, .3, .4, .5, .6, .7, -.1])
    tail = value['step7_to8']
    assert tail['actual_progress_through_step7_m'] == pytest.approx(.7)
    assert tail['actual_progress_through_step8_m'] == pytest.approx(-.1)
    assert tail['actual_distance_increase_m'] == pytest.approx(.8)
    assert tail['both_regress_robust'] and tail['positive_progress_reversed']


def test_projection_optimism_has_zero_tracking_gain_for_no_actual_motion():
    value = calculate([i / 10 for i in range(1, 9)], [0.] * 8)
    assert value['projection_optimism_witness']
    assert value['progress_optimism_m'] == pytest.approx(.8)
    assert value['projected_motion_tracking_gain'] == 0
    assert value['endpoint_projection_error_m'] == pytest.approx(.8)


def test_unknown_target_keeps_tracking_and_gripper_but_no_distance_claim():
    value = calculate([i / 10 for i in range(1, 9)], target=None)
    assert value['actual_frozen_target_distance_m'] is None
    assert value['projection_optimism_witness'] is None
    assert value['eef_projection_rmse_m'] == 0
    assert value['step7_to8']['both_regress_robust'] is None
    assert value['step7_to8']['gripper_command_switched']


def test_short_prefix_never_invents_tail_and_sub_precision_is_not_a_witness():
    assert calculate([.1])['step7_to8'] is None
    value = calculate([1e-10] * 8, [0.] * 8)
    assert not value['projection_optimism_witness']
    assert value['projected_motion_tracking_gain'] is None
    with pytest.raises(ValueError, match='nonempty'):
        a.numerical_diagnostics([[0., 0., 0.]], [0., 0., 0.], None, [], [1e-9])


def test_bfloat16_precision_is_not_falsely_promoted_to_float64():
    bf = a.ulp_norm(torch.tensor([1., 0., 0.], dtype=torch.bfloat16))
    native = a.ulp_norm(torch.tensor([1., 0., 0.], dtype=torch.float64))
    assert bf >= .0078125
    assert native <= 1e-9


def test_target_requires_reviewed_nonzero_index_and_exact_scoring_keypoints():
    code = 'a' * 64
    context = {'providers': [{'code_sha256': code}],
               'keypoints': torch.tensor([[50., 50., 50.], [1., 2., 3.]], dtype=torch.float64)}
    projected = {'keypoints': context['keypoints'].to(torch.bfloat16)}
    mapping = {code: {'keypoint_index': 1, 'target_expression': 'keypoints[1]'}}
    assert a.resolve_target(context, projected, {})[0] is None
    assert a.resolve_target(context, projected, mapping)[0] == [1., 2., 3.]
    assert a.resolve_target(context, {'keypoints': projected['keypoints'].flip(0)}, mapping)[0] is None
    context['providers'] *= 2
    assert a.resolve_target(context, projected, mapping)[2] == 'target_unknown_no_unique_provider'


def test_target_map_source_hash_and_review_are_required(tmp_path):
    source = tmp_path / 'synthetic_provider_source.py'
    source.write_text('def synthetic_provider(keypoints, trajectory):\n    return keypoints[1]\n')
    entry = {'provider_code_sha256': 'a' * 64, 'keypoint_index': 1,
             'source_path': str(source), 'source_sha256': a.digest(source),
             'target_expression': 'keypoints[1]', 'reviewed_against_frozen_provider_source': True,
             'target_selection': 'fixed_keypoint_index'}
    path = tmp_path / 'synthetic-target-map.json'
    path.write_text(json.dumps({'schema': 'qd-ed-provider-target-map-v1', 'entries': [entry]}))
    mapping, hashes = a.load_target_map(path)
    assert mapping['a' * 64]['keypoint_index'] == 1 and len(hashes) == 2
    source.write_text(source.read_text() + '# changed\n')
    with pytest.raises(ValueError, match='SHA mismatch'):
        a.load_target_map(path)


def test_existing_collector_cpu_fixture_passes_actual_auditor_without_invented_steps(tmp_path):
    rec, compute = fixture.episode(tmp_path, auxiliary=True)
    result = a.analyze_episode(rec.root, compute, ROOT, input_kind='synthetic_unit_fixture')
    assert result['input_kind'] == 'synthetic_unit_fixture'
    assert result['audit']['accepted']
    assert result['cuda_initialized_after'] is False
    decision = result['decisions'][0]
    assert decision['executed_prefix_length'] == 1
    assert decision['diagnostics']['step7_to8'] is None
    assert decision['frozen_target'] is None
    assert decision['selected_projected_xyz'][8][0] == 1.125
    assert len(decision['selected_projection_associations']) == 2  # Auxiliary excluded.
    assert all(x['scope']['role'].startswith('canonical_') for x in decision['selected_projection_associations'])
    assert decision['unknown_reasons'] == ['target_unknown_no_reviewed_provider_mapping',
                                         'step7_to8_unknown_for_short_actual_prefix']
    assert result['original_execution_outcome'] == 'completed'
    json.dumps(result, allow_nan=False)


def test_same_fingerprint_different_canonical_projection_is_unknown(tmp_path):
    rec, compute = fixture.episode(tmp_path)
    events = fixture.audit.load_events(rec.root, json.loads((rec.root / 'status.json').read_text()))
    rows = copy.deepcopy(events)
    scores = [r for r in rows if r['event'] == 'scoring_inputs']
    scores[1]['values']['projected_xyz'][1, 8, 0] += 1
    selected, missing, associations = a.selected_projection(rows, {r['sequence']: r for r in rows})
    assert selected is None and associations == []
    assert missing == 'selected_fingerprint_has_ambiguous_projection_or_origin'


def test_approach_interpretation_and_command_identity_control_eligibility(tmp_path):
    rec, compute = fixture.episode(tmp_path)
    events = fixture.audit.load_events(rec.root, json.loads((rec.root / 'status.json').read_text()))
    context = next(r['values'] for r in events if r['event'] == 'decision_context')
    code = context['providers'][0]['code_sha256']
    # An intentionally synthetic semantic annotation for eligibility plumbing only.
    mapping = {code: {'keypoint_index': 0, 'distance_progress_interpretation': 'descriptive_only'}}
    result = a.analyze_events(events, input_kind='synthetic_unit_fixture', target_map=mapping)
    assert result['decisions'][0]['frozen_target'] == [0., 0., 0.]
    assert not result['decisions'][0]['hypothesis_eligible']
    mapping[code]['distance_progress_interpretation'] = 'approach_proxy'
    result = a.analyze_events(events, input_kind='synthetic_unit_fixture', target_map=mapping)
    assert result['decisions'][0]['hypothesis_eligible']
    sent = next(r['values'] for r in events if r['event'] == 'executed_action')
    sent['action_numpy'][0] = 1.
    result = a.analyze_events(events, input_kind='synthetic_unit_fixture', target_map=mapping)
    assert not result['decisions'][0]['hypothesis_eligible']
    assert 'actual_translation_changed_after_decode' in result['decisions'][0]['hypothesis_ineligible_reasons']


def test_tampered_bundle_is_refused_by_existing_auditor(tmp_path):
    rec, compute = fixture.episode(tmp_path)
    bundle = next(rec.root.glob('bundle_*.pt'))
    bundle.write_bytes(bundle.read_bytes() + b'tampered')
    with pytest.raises(ValueError, match='existing episode audit refused'):
        a.analyze_episode(rec.root, compute, ROOT, input_kind='synthetic_unit_fixture')


def test_cpu_guard_requires_explicit_mask_and_never_initializes_cuda(monkeypatch):
    assert not torch.cuda.is_initialized()
    monkeypatch.delenv('CUDA_VISIBLE_DEVICES')
    with pytest.raises(ValueError, match='empty CUDA_VISIBLE_DEVICES'):
        a.cpu_torch()
    assert not torch.cuda.is_initialized()
