"""Independent v2 CPU synthetic review; no actual research input is opened."""
import copy
import importlib.util
from pathlib import Path

import pytest
import torch

PRODUCER = Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-executed-quality-20260923/docs/03_evidence/qd_ed_final/continuation_20260923/n3-first3-review-preparation')
spec = importlib.util.spec_from_file_location('n3_first3_author_synthetic_fixture', PRODUCER / 'test_review_first3.py')
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)
m = t.m


def move_to_end(rows, target):
    """Preserve internally valid sequential IDs and score references."""
    rows.remove(target)
    rows.append(target)
    scores = {r['sequence']: r for r in rows if r['event'] == 'scoring_inputs'}
    for sequence, row in enumerate(rows, 1):
        row['sequence'] = sequence
    for row in rows:
        if row['event'] in ('scoring_aggregate', 'effective_quality'):
            row['values']['scoring_batch_id'] = scores[row['values']['scoring_batch_id']]['sequence']


@pytest.mark.parametrize('case,message', [
    ('extra_archive_allocation', 'ten actual parent'),
    ('archive_allocation_after_final', 'parent/scoring causal'),
    ('effective_quality_after_final', 'canonical scoring/aggregate/effective causal'),
])
def test_original_three_reproductions_now_reject(case, message):
    rows, metric = t.active_fixture()
    if case == 'extra_archive_allocation':
        row = copy.deepcopy(next(r for r in rows if r['event'] == 'archive_parent_allocation'))
        row['sequence'] = len(rows) + 1
        rows.append(row)
    else:
        kind = 'archive_parent_allocation' if case == 'archive_allocation_after_final' else 'effective_quality'
        move_to_end(rows, next(r for r in rows if r['event'] == kind))
    with pytest.raises(ValueError, match=message):
        m.analyze_active(rows, metric)


def test_complete_unmodified_trace_still_accepted_without_mutation():
    rows, metric = t.active_fixture()
    before = [(r['sequence'], r['event']) for r in rows]
    result = m.analyze_active(rows, metric)
    assert len(result['canonical_batches']) == 11
    assert len(result['parent_rounds']) == 10
    assert result['canonical_evaluations'] == 176
    assert result['selected_final_ordering_witness'] and result['strict_final_pool_witness']
    assert before == [(r['sequence'], r['event']) for r in rows]
    assert not torch.cuda.is_initialized()


def test_equal_numbers_different_native_dtype_are_not_parent_lineage():
    rows, metric = t.active_fixture()
    parent = next(r for r in rows if r['event'] == 'parent_allocation')
    parent['values']['source_population'] = parent['values']['source_population'].float()
    with pytest.raises(ValueError, match='earlier native'):
        m.analyze_active(rows, metric)


def test_common_offset_across_full_search_does_not_establish_activity():
    rows, metric = t.active_fixture()
    for row in rows:
        values = row['values']
        if row['event'] == 'effective_quality':
            values['quality'] = values['raw_provider_quality'] + 2
        if row['event'] == 'canonical_candidate_batch':
            values['effective_quality'] = values['raw_provider_quality'] + 2
        if row['event'] == 'archive_parent_allocation':
            values['parent_rewards'] = values['parent_raw_rewards'] + 2
            values['parent_costs'] = -values['parent_rewards']
        if row['event'] == 'parent_allocation':
            values['source_quality'] = torch.arange(16, dtype=torch.float32) + 2
            values['source_costs'] = -values['source_quality']
    final = rows[-1]['values']
    final.update(selected_index=15, selected_latent=final['population'][15:16],
                 selected_quality=17.0, selected_raw_provider_quality=15.0)
    metric.update(qd_selected_raw_gap=0.0, qd_selected_raw_reward=15.0)
    result = m.analyze_active(rows, metric)
    assert not result['selected_final_ordering_witness']
    assert not result['strict_final_pool_witness']
    assert all(not b['descriptive_comparator_change'] for b in result['canonical_batches'])


def test_duplicate_native_maxima_keep_all_occurrences_without_strict_witness():
    population = t.samples(3)
    population[1] = population[0]
    raw = torch.tensor([2, 2, 1], dtype=torch.bfloat16)
    internal = torch.tensor([3, 3, 0], dtype=torch.bfloat16)
    known = {}
    m.remember(known, population, raw, internal)
    final = dict(population=population, raw_provider_quality=raw.float(), selected_index=1,
                 selected_latent=population[1:2], selected_quality=3.0,
                 selected_raw_provider_quality=2.0)
    metric = dict(qd_selected_raw_gap=0.0, qd_selected_raw_reward=2.0, qd_final_best_raw_reward=2.0)
    result = m.final_pool(final, known, metric)
    assert result['raw_max_indices'] == result['internal_max_indices'] == [0, 1]
    assert len(result['raw_max_native_ids']) == len(result['internal_max_native_ids']) == 1
    assert not result['strict_final_pool_witness']


def review_single_active(rows, metric):
    """Exercise review->analyze_active->final_pool without replacing any function."""
    metric.update(qd_quality_applicable=True, qd_feedback_active=True,
                  qd_feedback_context={}, qd_feedback_previous={}, qd_feedback_selected={},
                  qd_feedback_reason='synthetic', qd_archive_active_for_chunk=True,
                  qd_evaluation_count=176)
    for row in rows:
        row.update(decision_id=1, global_step=8)
    events = [dict(event='decision_context', decision_id=1, sequence=0,
                   global_step=8, values={'stage': 1})] + rows
    events.append(dict(event='execution_feedback_selection', decision_id=1,
                       sequence=len(events), global_step=8,
                       values=dict(active=True, context={}, previous={}, selected={})))
    accepted = [dict(profile=p, attempt_id=p,
                     terminal=dict(success=False, gpu_process_wall_seconds=1.0),
                     verified={}, metrics=[metric] if p == 'N3' else []) for p in m.PROFILES]
    return m.review(accepted, events)


def test_cross_cell_canonical_changes_with_singleton_final_do_not_pass():
    rows, metric = t.active_fixture()
    final = rows[-1]['values']
    final['population'] = final['population'][:1]
    final['raw_provider_quality'] = final['raw_provider_quality'][:1]
    metric.update(qd_selected_raw_gap=0.0, qd_final_best_raw_reward=0.0)
    result = review_single_active(rows, metric)
    analysis = result['n3_all_guided_decisions'][0]['analysis']
    assert analysis['canonical_comparator_changes_descriptive_only']
    assert analysis['final_pool']['selected_comparisons'] == []
    assert not result['checks']['substantive_feedback_search_activity']
    assert not result['all_checks_pass']


def test_final_lower_pair_reversal_without_selected_boundary_change_does_not_pass():
    rows, metric = t.active_fixture()
    source = [r for r in rows if r['event'] == 'scoring_inputs'][-1]
    raw = torch.tensor([3, 2, 1] + [-1]*13, dtype=torch.bfloat16)
    quality = torch.tensor([3, 1, 2] + [-1]*13, dtype=torch.bfloat16)
    for row in rows:
        value = row['values']
        if row['event'] == 'scoring_aggregate' and value['scoring_batch_id'] == source['sequence']:
            value['aggregate_before_reward_mode'] = raw
        if row['event'] == 'effective_quality' and value['scoring_batch_id'] == source['sequence']:
            value.update(raw_provider_quality=raw, quality=quality)
        if row['event'] == 'canonical_candidate_batch' and value['iter_idx'] == 9:
            value.update(raw_provider_quality=raw, effective_quality=quality)
    final = rows[-1]['values']
    final.update(population=final['population'][:3], raw_provider_quality=raw[:3].float(),
                 selected_quality=3.0, selected_raw_provider_quality=3.0)
    metric.update(qd_selected_raw_gap=0.0, qd_selected_raw_reward=3.0, qd_final_best_raw_reward=3.0)
    result = review_single_active(rows, metric)
    analysis = result['n3_all_guided_decisions'][0]['analysis']
    assert analysis['canonical_comparator_changes_descriptive_only']
    assert analysis['final_pool']['all_pool_comparisons_descriptive']['descriptive_comparator_change']
    assert not analysis['selected_final_ordering_witness']
    assert not result['checks']['substantive_feedback_search_activity']


def test_selected_native_entry_must_actually_be_internal_maximum():
    rows, metric = t.active_fixture()
    final = rows[-1]['values']
    final.update(selected_index=15, selected_latent=final['population'][15:16],
                 selected_quality=0.0, selected_raw_provider_quality=15.0)
    metric.update(qd_selected_raw_gap=0.0, qd_selected_raw_reward=15.0)
    with pytest.raises(ValueError, match='recorded final selection quality mismatch'):
        m.analyze_active(rows, metric)
