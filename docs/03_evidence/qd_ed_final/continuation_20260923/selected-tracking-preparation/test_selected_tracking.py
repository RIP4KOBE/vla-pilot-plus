"""Handmade diagnostic fixtures only; no fixture is runtime scientific evidence."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import io
import json
import os

os.environ['CUDA_VISIBLE_DEVICES'] = ''
import pytest
import torch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('selected_tracking_under_test', HERE/'read_selected_tracking.py')
r = importlib.util.module_from_spec(spec); spec.loader.exec_module(r)
assert not torch.cuda.is_initialized()


def fixture_rows(start=0, m=8, *, terminal=False, guided=True, residual=(.008, -.016, .024), dtype=torch.bfloat16):
    """A fake log assembled from known arrays, never a simulated execution."""
    rows = []
    def add(kind, values, step=None, reset=0):
        row = {'sequence': len(rows)+1, 'event': kind, 'episode': 0,
               'decision_id': f'd{start}', 'global_step': start if step is None else step,
               'reset_sequence': reset, 'values': values}
        rows.append(row); return row
    provider = {'ordinal': 0, 'original_code_sha256': 'a'*64, 'source_text_sha256': 'b'*64,
                'source_path': '/synthetic/source.py'}
    add('decision_context', {'stage': 1, 'use_guidance': guided, 'providers': [provider], 'keypoints': 'DO_NOT_READ'})
    sample = torch.zeros((1, 64, 128), dtype=dtype); sample[0, :8, 39] = 2.0
    fp = r.fingerprint(sample[0]); origin = torch.tensor([.10001, .2, .3], dtype=torch.float64)
    x = origin.to(dtype).repeat(9, 1); x[:, 0] += torch.arange(9, dtype=dtype)*.01
    origin_event = add('projection_origin', {'source_eef_position': origin, 'cast_eef_start': x[0].clone()})
    if guided:
        add('scoring_inputs', {'samples': sample.clone(), 'projected_xyz': x.unsqueeze(0).clone(),
            'projection_origin_sequences': [origin_event['sequence']], 'scoring_scope': {'role': 'canonical_initial'},
            'keypoints': 'DO_NOT_READ', 'provider_input_xyz': 'DO_NOT_READ'})
        add('final_selection', {'selected_latent': sample.clone(), 'selected_canonical_fingerprint': fp,
                               'population': 'DO_NOT_READ', 'selected_quality': 'DO_NOT_READ'})
    decoded = sample[:, :8, [39, 40, 41, 42, 43, 44, 10]].float(); decoded[:, :, -1] = 1
    add('policy_action_decode', {'selected_latent': sample.float(), 'selected_canonical_fingerprint': fp,
                                'action_chunk': decoded.clone()})
    add('decision_committed', {'action_chunk': decoded.clone(), 'execution_horizon': 8})
    for i in range(1, m+1):
        g = start+i-1; final = terminal and i == m
        add('action_dispatch', {'execution_index': i}, g)
        add('executed_action', {'action_numpy': decoded[0, i-1].clone()}, g)
        actual = origin+(x[i].double()-x[0].double())+torch.tensor(residual, dtype=torch.float64)*(i/8)
        add('pre_reset_outcome', {'observation': {'robot0_eef_pos': actual}, 'terminated': final}, g)
        if final: add('automatic_reset_boundary', {'reset_will_follow': True, 'reset_completed': None}, g)
        add('step_returned', {'terminated': final, 'truncated': False}, g, 1 if final else 0)
    return rows


def find(rows, kind): return next(x for x in rows if x['event'] == kind)


def test_cast_origin_t0_and_observed_step_alignment():
    d = r.describe(fixture_rows())
    assert d['tracking_status'] == 'known_recorded_selected_prefix'
    assert d['actual_prefix'][0]['global_step'] == 0 and d['tracking'][0]['i'] == 1
    assert d['tracking'][-1]['e_disp'] == pytest.approx([.008, -.016, .024])
    origin_cast = d['projected']['origin_cast_delta']
    assert origin_cast != [0, 0, 0]
    assert d['tracking'][-1]['e_abs'] == pytest.approx([a+b for a, b in zip([.008, -.016, .024], origin_cast)])
    assert d['projected']['origin_bridge'] is None
    assert d['projected']['native']['dtype'] == 'torch.bfloat16'
    assert d['summary']['sent_outside_declared_unit_bounds_components'] == 8


def test_pre_reset_terminal_response_is_kept_and_short_prefix_is_not_padded():
    d = r.describe(fixture_rows(m=3, terminal=True))
    assert d['m'] == 3 and len(d['tracking']) == 3 and d['ended'] is True
    assert d['tracking'][-1]['e_disp'] == pytest.approx([.003, -.006, .009])
    assert d['summary']['disp_mse'] == pytest.approx(sum(p['disp_sse'] for p in d['tracking'])/3)
    next_d = r.describe(fixture_rows(start=3), d)
    assert next_d['projected']['origin_bridge'] is None
    assert r.temporal_pair(d, next_d)['reason'] == 'reset_or_terminal_boundary'


def test_fixed_previous_residual_predicts_next_partial_without_self_fit():
    prev = r.describe(fixture_rows(residual=(.008, 0, 0)))
    cur = r.describe(fixture_rows(start=8, m=3, residual=(.024, 0, 0)), prev)
    pair = r.temporal_pair(prev, cur)
    assert pair['status'] == 'retrospective_predictive_check' and pair['current_m'] == 3
    assert pair['previous_e_disp_8'] == pytest.approx([.008, 0, 0])
    assert pair['points'][0]['transported_error'] == pytest.approx([.002, 0, 0])
    assert pair['points'][-1]['transported_error'] == pytest.approx([.006, 0, 0])
    assert pair['transported_mse'] == pytest.approx(sum((.016*i/8)**2 for i in (1, 2, 3))/3)


@pytest.mark.parametrize('case,reason', [
    ('off', 'unguided_boundary'), ('gap', 'noncontiguous_boundary'),
    ('partial', 'previous_prefix_not_full_eight'), ('stage', 'stage_changed_or_unknown'),
    ('missing_identity', 'provider_identity_unknown'), ('changed_identity', 'provider_identity_changed'),
    ('reset', 'reset_or_terminal_boundary')])
def test_pair_boundaries_and_missing_identity_are_not_guessed(case, reason):
    prev = r.describe(fixture_rows()); cur = r.describe(fixture_rows(start=8), prev)
    if case == 'off': prev['use_guidance'] = False
    elif case == 'gap': cur['global_step'] = 9
    elif case == 'partial': prev['m'] = 7
    elif case == 'stage': cur['stage'] = 2
    elif case == 'missing_identity': cur['provider_identity_known'] = False
    elif case == 'changed_identity': cur['providers'][0]['source_text_sha256'] = 'c'*64
    elif case == 'reset': cur['reset_sequence'] = 1
    assert r.temporal_pair(prev, cur)['reason'] == reason


def test_fingerprint_is_not_native_dtype_identity():
    rows = fixture_rows(); score = find(rows, 'scoring_inputs')
    before = r.fingerprint(score['values']['samples'][0])
    score['values']['samples'] = score['values']['samples'].float()
    assert r.fingerprint(score['values']['samples'][0]) == before
    assert r.describe(rows)['tracking_status'] == 'Unknown_canonical_fingerprint_native_identity_ambiguous'


def test_same_selected_content_with_different_origin_is_unknown():
    rows = fixture_rows(); score = copy.deepcopy(find(rows, 'scoring_inputs'))
    origin = copy.deepcopy(find(rows, 'projection_origin'))
    origin['sequence'] = 900; score['sequence'] = 901
    origin['values']['source_eef_position'] += .02
    origin['values']['cast_eef_start'] = origin['values']['source_eef_position'].to(torch.bfloat16)
    score['values']['projected_xyz'][:, 0] = origin['values']['cast_eef_start']
    score['values']['projection_origin_sequences'] = [900]
    rows.extend([origin, score])
    assert r.describe(rows)['tracking_status'] == 'Unknown_selected_projection_or_origin_ambiguous'


def test_later_debug_origin_is_not_joined_by_position():
    rows = fixture_rows(); origin = copy.deepcopy(find(rows, 'projection_origin'))
    origin['sequence'] = 900; origin['values']['source_eef_position'] += 50
    rows.append(origin)
    d = r.describe(rows)
    assert d['tracking_status'] == 'known_recorded_selected_prefix'
    assert d['projected']['occurrences'][0]['origin_sequence'] == 2


def test_actual_sent_delta_is_retained_not_clipped_or_redecoded():
    rows = fixture_rows(); sent = find(rows, 'executed_action'); sent['values']['action_numpy'][0] = 3.
    d = r.describe(rows)
    assert d['actual_prefix'][0]['sent'][0] == 3.
    assert d['actual_prefix'][0]['sent_decode_delta'][0] == 1.
    assert d['summary']['sent_decode_changed_steps'] == 1


def test_unguided_missing_projection_does_not_break_actual_coverage():
    d = r.describe(fixture_rows(guided=False))
    assert d['m'] == 8 and d['tracking'] is None
    assert d['tracking_status'] == 'Unknown_unguided_no_recorded_selected_projection'


def test_dispatched_gap_fails_instead_of_aligning_by_row_order():
    rows = fixture_rows(); find(rows, 'action_dispatch')['values']['execution_index'] = 2
    with pytest.raises(ValueError, match='execution_index_gap'): r.describe(rows)


def test_allowlist_removes_unselected_qualities_and_keypoints():
    rows = fixture_rows(); small = [r.pruned(x) for x in rows]
    assert 'keypoints' not in find(small, 'decision_context')['values']
    assert 'keypoints' not in find(small, 'scoring_inputs')['values']
    assert set(find(small, 'final_selection')['values']) == {'selected_latent', 'selected_canonical_fingerprint'}
    assert r.pruned({'event': 'provider_return', 'values': {'result': object()}}) is None


def put(path, value, lines=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = ('\n'.join(json.dumps(v) for v in value)+'\n').encode() if lines else (json.dumps(value)+'\n').encode()
    path.write_bytes(data); return {'path': str(path), 'sha256': r.sha(data)}


def source_refs():
    return [{'relative_path': p, 'sha256': r.AUDITOR_SHA if p == 'scripts/audit_decision_evidence.py' else 'f'*64}
            for p in sorted(r.SOURCE_FILES)]


def universe(root, monkeypatch, defect=None):
    """Thirty invented cells bind tiny non-tensor bytes for admission tests only."""
    bound = {}; cells = []; extras = []; chronicles = []; certificates = []; originals = []
    def tracked(path, value, lines=False):
        ref = put(path, value, lines); bound[ref['path']] = ref['sha256']; return ref
    cr = root/'chronology'; attempt_root = root/'attempts'
    for task in range(10):
        for arm in ('C0', 'Q0', 'N2'):
            key = f't{task:02d}-{arm.lower()}'; aid = 'synthetic-'+key; output = attempt_root/aid
            ed = output/'eds_eval'; ep = ed/'decision_evidence/episode_000'; ep.mkdir(parents=True)
            identity = {'split': 'development', 'iteration': 2, 'profile': arm, 'task_id': task,
                        'env_seed': 100+task, 'policy_seed': 200+task, 'init_index': 0}
            originals.append({**identity, 'episode_key': key})
            terminal = {'attempt_id': aid, 'event': 'valid', 'outcome_valid': True, 'source_commit': r.SOURCE,
                        'identity': identity, 'retry_of': None, 'output_dir': str(output)}
            terminal_ref = tracked(output/'attempt-result.json', terminal)
            compute_ref = tracked(ed/'episode_compute.jsonl', [{'episode_id': 0, 'task_id': task,
                'episode_seed': 100+task, 'outcome': 'completed', 'guided_chunks': 1}], True)
            status_ref = tracked(ep/'status.json', {'schema': 'qd-ed-decision-evidence-v1', 'episode': 0,
                'complete': True, 'failed': False, 'pending_action': False, 'bundles': 1, 'decisions': 1})
            metadata = tracked(ed/'episode_metadata.jsonl', [{'episode_id': 0, 'task_id': task, 'episode_seed': 100+task}], True)
            bundle = ep/'bundle_000001.pt'; bundle.write_bytes(b'NOT_A_TENSOR_NO_DECODE_IN_ADMISSION')
            bound[str(bundle)] = r.sha(bundle.read_bytes())
            index_ref = tracked(ep/'events.jsonl', [{'bundle': bundle.name, 'sha256': bound[str(bundle)]}], True)
            fresh = {'schema': 'qd-ed-decision-evidence-audit-v1', 'accepted': True, 'evidence_complete': True,
                     'errors': [], 'original_execution_outcome': 'completed', 'episode_dir': str(ep),
                     'episode_compute_file': str(ed/'episode_compute.jsonl')}
            if defect == 'fresh_wrong_episode' and task == 0 and arm == 'C0': fresh['episode_dir'] += '-wrong'
            fresh_ref = put(cr/(key+'-fresh-audit.json'), fresh)
            derived = {'path': str(cr/(key+'.json')), 'sha256': 'd'*64}  # Deliberately absent: reader must not open it.
            chronicles.append({'cell': key, 'attempt_id': aid, 'identity': identity, 'retry_of': None,
                               'path': key+'.json', 'sha256': derived['sha256']})
            extras.append({'attempt_id': aid, 'metadata': metadata, 'status': status_ref, 'index': index_ref})
            certificate = {'attempt_id': aid, 'cell': key, 'episode_dir': str(ep), 'accepted': True,
                'evidence_complete': True, 'errors': [], 'derived_cell': derived, 'fresh_audit': fresh_ref,
                'bundle_index': index_ref, 'collector_status': status_ref, 'episode_compute': compute_ref,
                'bundle_hash_count': 1, 'bundle_hash_map': {'exact_parent_directory': str(ep), 'field': 'input_hashes',
                    'filename_pattern': 'bundle_*.pt'}}
            if task == 0 and arm == 'C0':
                if defect == 'index_binding': certificate['bundle_index'] = {**index_ref, 'sha256': '0'*64}
                if defect == 'status_binding': certificate['collector_status'] = {**status_ref, 'sha256': '0'*64}
                if defect == 'bundle_binding': del bound[str(bundle)]
                if defect == 'unindexed': (ep/'bundle_000002.pt').write_bytes(b'unindexed')
            certificates.append(certificate)
            cells.append({'valid_attempt_id': aid, 'status': 'complete_valid', 'identity': identity,
                          'attempts': [{'status': 'complete_valid', 'terminal': terminal,
                                        'references': {'terminal': terminal_ref, 'compute': compute_ref}}]})
    code_files = [{'path': x['relative_path'], 'sha256': x['sha256']} for x in source_refs()]
    if defect == 'source_inventory': code_files[0]['sha256'] = '0'*64
    base = tracked(root/'base.json', {'source_commit': 'wrong' if defect == 'source' else r.SOURCE,
        'n2_cohort': {'cohort_id': r.COHORT}, 'code_files': code_files,
        'episodes': originals})
    report = tracked(root/'report.json', {'schema': 'qd-ed-n2-matrix-report-v1', 'cohort_id': r.COHORT,
        'matrix': 'complete_valid_30', 'input_manifest': {'base_plan': base}, 'cells': cells})
    monkeypatch.setattr(r, 'REPORT_SHA', report['sha256'])
    ci = tracked(root/'chron-input.json', {'schema': 'n2-dev-chronology-input-v1', 'matrix_report': report, 'cells': extras})
    cf = put(root/'chron-freeze.json', {'local_files': {'read_full_dev.py': r.CHRON_READER_SHA}})
    monkeypatch.setattr(r, 'CHRON_FREEZE_SHA', cf['sha256'])
    ca = put(root/'chron-auth.json', {'schema': 'n2-dev-chronology-read-authorization-v1', 'status': 'AUTHORIZED_CPU_READ',
        'scope_reviewed': True, 'freeze': cf, 'matrix_report': report, 'input_manifest': ci})
    prov = put(cr/'inputs-and-audit.json', {'schema': 'n2-dev-chronology-provenance-v1', 'complete': True,
        'matrix_authority': report, 'cuda_initialized': False, 'new_quality_computation': False,
        'authorization_sha256': ca['sha256'], 'freeze': cf,
        'source_dependencies': {'sources': {'auditor': {'sha256': r.AUDITOR_SHA}}}, 'input_hashes': bound})
    index = put(cr/'index.json', {'schema': 'n2-dev-closed-loop-chronology-v1', 'complete': True, 'cells': chronicles})
    status = put(cr/'status.json', {'complete': True, 'cells': 30, 'original_task_outcomes_changed': False})
    for cert in certificates: cert['bundle_hash_map']['provenance'] = prov
    if defect == 'set': certificates[-1] = certificates[0]
    binding = put(root/'binding.json', {'schema': 'n2-dev-fresh-audit-provenance-bindings-v1', 'complete': True,
        'source_index': index, 'source_provenance': prov, 'reader_status': status,
        'auditor_source': {'sha256': r.AUDITOR_SHA}, 'cells': certificates})
    monkeypatch.setattr(r, 'REUSE_BINDING_SHA', binding['sha256'])
    return {'schema': 'selected-tracking-input-v1', 'matrix_report': report, 'chronology_provenance': prov,
            'chronology_index': index, 'chronology_status': status, 'chronology_authorization': ca,
            'fresh_audit_bindings': binding}


def test_all30_admission_reuses_bindings_without_any_tensor_decode(tmp_path, monkeypatch):
    manifest = universe(tmp_path, monkeypatch)
    monkeypatch.setattr(torch, 'load', lambda *a, **k: pytest.fail('admission decoded tensor'))
    admitted = r.admit(manifest, r.Inputs(tmp_path), source_refs())
    assert len(admitted) == 30 and [x['cell'] for x in admitted][:3] == ['t00-c0', 't00-q0', 't00-n2']


@pytest.mark.parametrize('defect,reason', [
    ('index_binding', 'reuse_input_references_differ'), ('status_binding', 'reuse_input_references_differ'),
    ('bundle_binding', 'bound_bundle_set_differs'), ('fresh_wrong_episode', 'fresh_audit_not_complete_or_linked'),
    ('unindexed', 'unindexed_bundle'), ('source', 'episode_source_differs'), ('set', 'representative_sets_differ'),
    ('source_inventory', 'interpreted_source_not_episode_inventory')])
def test_wrong_binding_fails_before_any_decode(tmp_path, monkeypatch, defect, reason):
    manifest = universe(tmp_path, monkeypatch, defect)
    monkeypatch.setattr(torch, 'load', lambda *a, **k: pytest.fail('failed admission decoded tensor'))
    with pytest.raises(ValueError, match=reason): r.admit(manifest, r.Inputs(tmp_path), source_refs())


def test_real_cpu_bundle_stream_short_terminal_and_precision(tmp_path):
    rows = fixture_rows(m=3, terminal=True)
    blob = io.BytesIO(); torch.save({'schema': 'qd-ed-decision-evidence-v1', 'events': rows}, blob)
    p = tmp_path/'bundle_000001.pt'; p.write_bytes(blob.getvalue())
    ref = {'bundle': p.name, 'sha256': r.sha(blob.getvalue()), 'first_sequence': 1,
           'last_sequence': rows[-1]['sequence'], 'events': [{k: x[k] for k in r.META} for x in rows]}
    item = {'ep': tmp_path, 'index': [ref], 'status': {'decisions': 1}, 'compute': {'guided_chunks': 1},
            'attempt_id': 'synthetic', 'identity': {'task_id': 0, 'profile': 'Q0'}, 'retry_of': None}
    result = r.episode(item, r.Inputs(tmp_path))
    assert result['summary']['observed_actions'] == 3 and result['summary']['by_step'][3]['n'] == 0
    assert result['decisions'][0]['projected']['native']['dtype'] == 'torch.bfloat16'
    assert not torch.cuda.is_initialized()


def test_no_actual_read_without_separate_explicit_authorization(tmp_path, monkeypatch):
    monkeypatch.setattr(r, 'ROOT', tmp_path)
    ref = put(tmp_path/'not-authorized.json', {'schema': 'selected-tracking-authorization-v1',
        'status': 'IMPLEMENTATION_ONLY', 'retrospective_transport_approved': True, 'source_commit': r.SOURCE})
    monkeypatch.setattr(torch, 'load', lambda *a, **k: pytest.fail('unauthorized read decoded tensor'))
    output = tmp_path/'continuation_20260923/selected-tracking-analysis/should-not-exist'
    with pytest.raises(ValueError, match='read_not_authorized'): r.run(ref['path'], ref['sha256'], output)
    assert not output.exists()
