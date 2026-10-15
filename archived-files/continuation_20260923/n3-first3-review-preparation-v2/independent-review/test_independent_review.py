"""Independent CPU synthetic review; no actual research input is opened."""
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
    assert result['consumed_ordering_witness'] and result['strict_final_pool_witness']
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
    assert not result['consumed_ordering_witness']
    assert not result['strict_final_pool_witness']
    assert all(not b['consumed_ordering_witness'] for b in result['canonical_batches'])


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
