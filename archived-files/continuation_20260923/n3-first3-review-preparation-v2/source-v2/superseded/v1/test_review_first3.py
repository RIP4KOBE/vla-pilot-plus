"""Explicit synthetic CPU tests; never historical or runtime episode evidence."""
import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

spec = importlib.util.spec_from_file_location('first3_review_test_target', Path(__file__).with_name('review_first3.py'))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


def samples(n=3, offset=0):
    result = torch.zeros(n, 64, 128, dtype=torch.bfloat16)
    result[:, 0, 0] = torch.arange(n) + offset
    return result


@pytest.mark.parametrize('raw,quality,witness,category', [
    ([0, 1, 2], [3, 4, 5], False, None),
    ([0, 1, 2], [2, 1, 0], True, 'strict_reversal'),
    ([0, 0, 2], [0, 1, 2], True, 'tie_split'),
    ([0, 1, 2], [0, 0, 2], True, 'tie_merge'),
    ([1, 1, 1], [1, 1, 1], False, None),
])
def test_native_comparators_not_scalar_difference(raw, quality, witness, category):
    result = m.compare_order(samples(), torch.tensor(raw, dtype=torch.bfloat16), torch.tensor(quality, dtype=torch.bfloat16))
    assert result['consumed_ordering_witness'] is witness
    assert sum(result['all_pair_transitions'].values()) == 3
    if category: assert result['distinct_native_order_changes'][category] > 0
    assert sorted(i for group in result['raw_rank_groups'] for i in group) == [0, 1, 2]


def test_duplicate_native_actions_never_supply_comparator_witness():
    sample = torch.zeros(2, 64, 128)
    result = m.compare_order(sample, torch.tensor([0., 1.]), torch.tensor([1., 0.]))
    assert not result['consumed_ordering_witness'] and result['duplicate_native_pairs'] == 1
    table = {}
    with pytest.raises(ValueError, match='conflicting native'):
        m.remember(table, sample, torch.tensor([0., 1.]), torch.tensor([1., 0.]))


@pytest.mark.parametrize('dtype', [torch.float32, torch.bfloat16])
def test_all_native_ties_preserved_in_final_pool(dtype):
    population = samples().to(dtype)
    raw = torch.tensor([-1., -1., -2.], dtype=dtype)
    quality = torch.tensor([2., 2., 1.], dtype=dtype)
    known = {}; m.remember(known, population, raw, quality)
    final = {'population': population, 'raw_provider_quality': raw.float(), 'selected_index': 0,
             'selected_latent': population[:1], 'selected_quality': 2., 'selected_raw_provider_quality': -1.}
    metric = {'qd_selected_raw_gap': 0., 'qd_selected_raw_reward': -1., 'qd_final_best_raw_reward': -1.}
    result = m.final_pool(final, known, metric)
    assert result['raw_max_indices'] == result['internal_max_indices'] == [0, 1]
    assert len(result['raw_max_native_ids']) == 2 and not result['strict_final_pool_witness']
    quality = torch.tensor([1., 0., 2.], dtype=dtype); known = {}; m.remember(known, population, raw, quality)
    final.update(selected_index=2, selected_latent=population[2:3], selected_raw_provider_quality=-2.)
    metric.update(qd_selected_raw_gap=-1., qd_selected_raw_reward=-2.)
    assert m.final_pool(final, known, metric)['strict_final_pool_witness']


def active_fixture():
    events = []; batch_values = []
    def event(kind, **values):
        row = {'sequence': len(events)+1, 'event': kind, 'values': values}
        events.append(row); return row
    for iteration in range(-1, 10):
        if iteration >= 0:
            old = batch_values[-1]
            event('archive_parent_allocation', iter_idx=iteration, parent_fingerprints=['fixture']*16,
                  parent_rewards=old['effective_quality'].float(), parent_costs=-old['effective_quality'].float(),
                  parent_raw_rewards=old['raw_provider_quality'].float())
            event('parent_allocation', iter_idx=iteration, source_population=old['candidates'].clone(),
                  source_quality=old['effective_quality'].float(), source_costs=-old['effective_quality'].float(),
                  parent_indices=torch.arange(16))
        candidate = samples(16, (iteration + 1)*16)
        raw = torch.arange(16, dtype=torch.bfloat16)
        quality = raw.flip(0)
        score = event('scoring_inputs', samples=candidate.clone(), scoring_scope={'role': 'canonical_initial' if iteration == -1 else 'canonical_offspring', 'iter_idx': iteration})
        event('scoring_aggregate', scoring_batch_id=score['sequence'], aggregate_before_reward_mode=raw.clone())
        event('effective_quality', scoring_batch_id=score['sequence'], raw_provider_quality=raw.clone(), quality=quality.clone())
        values = dict(iter_idx=iteration, candidates=candidate, raw_provider_quality=raw, effective_quality=quality, quality_mode='executed_feedback_v1')
        event('canonical_candidate_batch', **values); batch_values.append(values)
    event('final_selection', population=candidate, raw_provider_quality=raw.float(), selected_index=0,
          selected_latent=candidate[:1], selected_quality=15., selected_raw_provider_quality=0.)
    metric = {'global_step': 8, 'qd_selected_raw_gap': -15., 'qd_selected_raw_reward': 0., 'qd_final_best_raw_reward': 15.}
    return events, metric


def test_all_176_candidates_and_ten_actual_parent_rounds_are_preserved():
    rows, metric = active_fixture()
    result = m.analyze_active(rows, metric)
    assert result['canonical_evaluations'] == 176 and len(result['canonical_batches']) == 11
    assert len(result['parent_rounds']) == 10 and all(r['slots'] == 16 for r in result['parent_rounds'])
    assert result['consumed_ordering_witness'] and result['strict_final_pool_witness']
    assert not torch.cuda.is_initialized()


@pytest.mark.parametrize('corruption,match', [
    ('future_parent', 'earlier native'), ('raw', 'vector mismatch'), ('samples', 'scoring association'),
    ('iteration', 'iteration coverage'), ('selected', 'selected native'), ('gap', 'raw gap'),
])
def test_native_lineage_and_order_errors_reject(corruption, match):
    rows, metric = active_fixture()
    if corruption == 'future_parent':
        next(r for r in rows if r['event']=='parent_allocation')['values']['source_population'] = samples(16, 160)
    if corruption == 'raw':
        next(r for r in rows if r['event']=='canonical_candidate_batch')['values']['raw_provider_quality'] = torch.zeros(16, dtype=torch.bfloat16)
    if corruption == 'samples':
        next(r for r in rows if r['event']=='scoring_inputs')['values']['samples'] = samples(16, 160)
    if corruption == 'iteration':
        next(r for r in rows if r['event']=='canonical_candidate_batch')['values']['iter_idx'] = 2
    if corruption == 'selected': rows[-1]['values']['selected_latent'] = samples(1, 999)
    if corruption == 'gap': metric['qd_selected_raw_gap'] = 0.
    with pytest.raises(ValueError, match=match): m.analyze_active(rows, metric)


def test_inactive_or_unsupported_no_activity_even_when_outcome_successful():
    metric = {'global_step': 0, 'qd_quality_applicable': False, 'qd_feedback_active': False, 'qd_feedback_reason': 'unsupported'}
    accepted = [{'profile': p, 'attempt_id': p, 'terminal': {'success': True, 'gpu_process_wall_seconds': 1.}, 'verified': {}, 'metrics': [metric] if p=='N3' else []} for p in m.PROFILES]
    result = m.review(accepted, [{'event': 'decision_context', 'decision_id': 1, 'global_step': 0, 'values': {'stage': 1}}])
    assert not result['all_checks_pass'] and not result['checks']['substantive_feedback_search_activity']
    assert result['original_outcomes'][2]['success'] is True


def admission_fixture(tmp_path, monkeypatch):
    def write(path, value, lines=False):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(('\n'.join(json.dumps(v) for v in value)+'\n') if lines else json.dumps(value))
        return {'path': str(path), 'sha256': m.sha(path)}
    source = tmp_path/'source'; (source/'scripts').mkdir(parents=True)
    for name in ('qd_ed_n3_report.py', 'qd_ed_n3_plan.py', 'audit_decision_evidence.py'):
        (source/'scripts'/name).write_text('# synthetic source fixture\n')
    files = {f'scripts/{name}': m.sha(source/'scripts'/name) for name in ('qd_ed_n3_report.py','qd_ed_n3_plan.py','audit_decision_evidence.py')}
    base = {'worktree': str(source), 'source_commit': 'f'*40, 'code_files': [{'path': k, 'sha256': v} for k,v in files.items()]}
    plan = write(tmp_path/'plan.json', base)
    cell_specs = []; cell_reports = []
    for profile in m.PROFILES:
        output = tmp_path/profile; episode = output/'eds_eval/decision_evidence/episode_000'
        terminal = {'attempt_id': profile, 'event': 'valid', 'outcome_valid': True, 'output_dir': str(output)}
        audit = {'accepted': True, 'evidence_complete': True, 'errors': [], 'episode_dir': str(episode),
                 'n3_feedback_audit': {'schema': 'n3-native-feedback-audit-v1'}}
        refs = {'terminal': write(output/'attempt-result.json', terminal), 'audit': write(output/'eds_eval/decision-evidence-audit.json', audit),
                'compute': write(output/'eds_eval/episode_compute.jsonl', [{'decision_evidence': {'bundles': 1}}], True),
                'metrics': write(output/'eds_eval/eds_metrics.jsonl', [], True)}
        cell_specs.append({'profile': profile, 'attempt_id': profile, 'references': refs})
        cell_reports.append({'identity': {'task_id': 0, 'profile': profile}, 'status': 'complete_valid', 'valid_attempt_id': profile,
                             'attempts': [{'status': 'complete_valid', 'references': refs}], 'metrics': {}})
    report_input = {'base_plan': plan}
    input_ref = write(tmp_path/'report-input.json', report_input)
    matrix = {'schema': 'qd-ed-n3-matrix-report-v1', 'cohort_id': 'N3_EXECUTED_FEEDBACK_DEV_20260923',
              'input_manifest_sha256': input_ref['sha256'], 'input_manifest': report_input,
              'first_three': {'all_complete_valid': True}, 'cells': cell_reports}
    matrix_ref = write(tmp_path/'report.json', matrix)
    episode.mkdir(parents=True)
    (episode/'bundle_000001.pt').write_bytes(b'explicit synthetic integrity fixture; never decoded')
    status = write(episode/'status.json', {'complete': True, 'failed': False, 'pending_action': False, 'episode': 0, 'bundles': 1})
    index = write(episode/'events.jsonl', [{'bundle': 'bundle_000001.pt', 'sha256': m.sha(episode/'bundle_000001.pt')}], True)
    manifest = {'schema': 'n3-first3-review-inputs-v1', 'matrix_report': matrix_ref, 'matrix_report_input': input_ref,
                'cells': cell_specs, 'source_root': str(source), 'source_commit': 'f'*40,
                'n3_episode': {'episode_dir': str(episode), 'status': status, 'index': index}}
    auth = {'schema': 'n3-first3-read-authorization-v1', 'status': 'authorized', 'reviewed_matrix_report': matrix_ref,
            'n3_audit_snapshot': {'audit': cell_specs[2]['references']['audit'], 'status': status, 'index': index,
                'auditor_sha256': files['scripts/audit_decision_evidence.py'], 'binding': 'root_verified_unchanged_after_complete_frozen_audit'}}
    freeze = {'reviewed_source_sha256': {k: v for k,v in files.items() if k not in m.METADATA_GATE_FILES}}
    auth['reviewed_metadata_gate_sources'] = {k: files[k] for k in m.METADATA_GATE_FILES}
    monkeypatch.setenv('CUDA_VISIBLE_DEVICES','')
    monkeypatch.setattr(m.subprocess,'check_output',lambda cmd, **kw: ('f'*40+'\n') if 'rev-parse' in cmd else (source/cmd[-1].split(':',1)[1]).read_bytes())
    decoder_calls = []
    auditor = SimpleNamespace(load_events=lambda *args: decoder_calls.append(args))
    reporter = SimpleNamespace(plan_contract=lambda value: [], BINDING=(), load_attempt=lambda *args: {'status':'complete_valid','metrics':{}})
    monkeypatch.setattr(m,'load_module',lambda name,path: auditor if 'auditor' in name else reporter)
    return manifest, auth, freeze, decoder_calls


@pytest.mark.parametrize('corruption,match', [
    ('authorization','authorized'), ('source','source review'), ('metadata_missing','source closure'),
    ('metadata_mismatch','source review'), ('representative','representative'),
    ('audit','SHA mismatch'), ('index','SHA mismatch'), ('bundle','bundle hash'), ('binding','snapshot binding'),
])
def test_admission_rejection_precedes_any_bundle_decode(tmp_path, monkeypatch, corruption, match):
    manifest, auth, freeze, calls = admission_fixture(tmp_path, monkeypatch)
    if corruption == 'authorization': auth['status'] = 'pending'
    if corruption == 'source': freeze['reviewed_source_sha256']['scripts/audit_decision_evidence.py'] = '0'*64
    if corruption == 'metadata_missing': auth['reviewed_metadata_gate_sources'].pop('scripts/qd_ed_n3_plan.py')
    if corruption == 'metadata_mismatch': auth['reviewed_metadata_gate_sources']['scripts/qd_ed_n3_plan.py'] = '0'*64
    if corruption == 'representative': manifest['cells'][1]['attempt_id'] = 'unapproved'
    if corruption == 'audit': Path(manifest['cells'][2]['references']['audit']['path']).write_text('{}')
    if corruption == 'index': Path(manifest['n3_episode']['index']['path']).write_text('')
    if corruption == 'bundle': (Path(manifest['n3_episode']['episode_dir'])/'bundle_000001.pt').write_bytes(b'changed')
    if corruption == 'binding': auth['n3_audit_snapshot']['binding'] = 'self_asserted'
    with pytest.raises(ValueError, match=match): m.admit(manifest, auth, freeze, {})
    assert calls == []


def test_valid_admission_only_hashes_and_never_decodes(tmp_path, monkeypatch):
    manifest, auth, freeze, calls = admission_fixture(tmp_path, monkeypatch)
    accepted, _, _, _ = m.admit(manifest, auth, freeze, {})
    assert len(accepted) == 3 and calls == [] and not torch.cuda.is_initialized()


@pytest.mark.parametrize('kind,operation,match', [
    ('archive_parent_allocation', 'duplicate', 'ten actual parent'),
    ('parent_allocation', 'duplicate', 'ten actual parent'),
    ('scoring_inputs', 'duplicate', 'canonical scoring coverage'),
    ('archive_parent_allocation', 'move_last', 'parent/scoring causal'),
    ('effective_quality', 'move_last', 'canonical scoring/aggregate/effective causal'),
    ('final_selection', 'move_first', 'final selection causal'),
])
def test_duplicate_or_future_consumption_events_reject(kind, operation, match):
    rows, metric = active_fixture()
    target = next(row for row in rows if row['event'] == kind)
    if operation == 'duplicate':
        rows.append(copy.deepcopy(target))
    else:
        rows.remove(target)
        if operation == 'move_last': rows.append(target)
        else: rows.insert(0, target)
        remap = {row['sequence']: i for i, row in enumerate(rows, 1)}
        for i, row in enumerate(rows, 1):
            row['sequence'] = i
            values = row['values']
            if 'scoring_batch_id' in values: values['scoring_batch_id'] = remap[values['scoring_batch_id']]
    with pytest.raises(ValueError, match=match): m.analyze_active(rows, metric)
