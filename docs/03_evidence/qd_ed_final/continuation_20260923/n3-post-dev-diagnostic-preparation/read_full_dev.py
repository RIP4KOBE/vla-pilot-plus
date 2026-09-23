#!/usr/bin/env python3
"""N3 conditional complete-cohort description; no execution or promotion authority."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z')
SOURCE = 'bd618b931eb9d8fc2c01b978c4ef220c9bb03889'
COHORT = 'N3_EXECUTED_FEEDBACK_DEV_20260923'
ARMS = ('C0', 'Q0', 'N3')
IDENTITY = ('split', 'iteration', 'profile', 'task_id', 'env_seed', 'policy_seed', 'init_index')
BINDING = ('source_commit', 'profiles_sha256', 'runtime_manifest_sha256', 'runtime_inventory_sha256', 'seed_plan_sha256')
SNAPSHOT = 'root_verified_unchanged_after_complete_frozen_audit'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def parse(data):
    def pairs(rows):
        out = {}
        for key, value in rows:
            require(key not in out, 'duplicate_json_key')
            out[key] = value
        return out
    return json.loads(data, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite_json')))


def xjson(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


class Inputs:
    def __init__(self, root=ROOT):
        self.root = Path(root).resolve()
        self.hashes, self.absent = {}, []

    def path(self, value):
        path = Path(value)
        require(path.is_absolute() and path == path.resolve() and path.is_relative_to(self.root), 'noncanonical_or_outside_owned_root')
        return path

    def bytes(self, ref):
        require(set(ref) == {'path', 'sha256'} and re.fullmatch('[0-9a-f]{64}', ref['sha256']), 'invalid_reference')
        path = self.path(ref['path']); data = path.read_bytes()
        require(sha(data) == ref['sha256'], 'input_sha_mismatch')
        self.hashes[str(path)] = ref['sha256']
        return data

    def read(self, ref, lines=False):
        data = self.bytes(ref)
        return [parse(row) for row in data.splitlines() if row.strip()] if lines else parse(data)

    def finish(self):
        require(all(sha(Path(p).read_bytes()) == s for p, s in self.hashes.items()), 'input_changed')
        require(all(not p.exists() for p in self.absent), 'absent_source_appeared')


def dependency_module(name, ref):
    path = Path(ref['path'])
    require(sha(path.read_bytes()) == ref['sha256'], 'dependency_sha_mismatch')
    spec = importlib.util.spec_from_file_location('n3_complete_' + name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def dependencies(definition):
    # The reporter is imported only after its separately authorized SHA also
    # matches the complete source inventory in admit(). Pure helpers do no I/O.
    modules = {name: dependency_module(name, ref) for name, ref in definition['modules'].items() if name != 'report'}
    torch = modules['task0'].torch
    require(sys.version.split()[0] == definition['python_version'] and torch.__version__ == definition['torch_version'], 'CPU_environment_identity_differs')
    require(not torch.cuda.is_initialized(), 'CUDA_initialized')
    return modules


def optional_stage(extra, path, identity, inputs):
    if extra['status'] == 'not_recorded':
        require(set(extra) == {'status', 'path'} and inputs.path(extra['path']) == path and not path.exists(), 'absent_Stage_declaration_differs')
        inputs.absent.append(path)
        return None
    require(extra['status'] == 'present' and set(extra) == {'status', 'reference'} and inputs.path(extra['reference']['path']) == path, 'Stage_reference_differs')
    rows = inputs.read(extra['reference'], lines=True)
    require(all(all(r.get(k) == v for k, v in identity.items()) for r in rows), 'Stage_identity_differs')
    return rows


def admit(manifest, auth, definition, modules, inputs):
    """All30 source/representative/snapshot gates and all hashes before decode."""
    require(manifest['schema'] == 'n3-post-dev-input-v1', 'manifest_schema')
    require(auth['reviewed_matrix_report'] == manifest['matrix_report']
            and auth['completed_cohort_reviewed'] is True
            and auth['trigger'] == 'root_confirmed_existing_dev_gate_failed', 'root_scope_missing')
    report = inputs.read(manifest['matrix_report'])
    authority = inputs.read(manifest['matrix_report_input'])
    require(report['schema'] == 'qd-ed-n3-matrix-report-v1' and report['cohort_id'] == COHORT
            and report['matrix'] == 'complete_valid_30' and report['input_scope_complete'] is True
            and report['inflight_records'] == [] and authority['input_scope_complete'] is True
            and report['input_manifest'] == authority
            and report['input_manifest_sha256'] == manifest['matrix_report_input']['sha256'], 'matrix_authority_incomplete_or_different')
    require(authority['script_sha256'] == definition['modules']['report']['sha256'], 'matrix_reporter_definition_differs')
    base = inputs.read(authority['base_plan']); originals = [r for r in base['episodes'] if not r.get('retry_of')]
    universe = [(task, arm) for task in range(10) for arm in ARMS]
    require(base['source_commit'] == SOURCE and base['artifact_root'] == str(inputs.root)
            and base['n3_cohort']['cohort_id'] == COHORT
            and [(r['task_id'], r['profile']) for r in originals] == universe, 'source_or_original_universe_differs')
    inventory = {r['path']: r['sha256'] for r in base['code_files']}
    require(len(inventory) == len(base['code_files']) and all(inventory.get(p) == s for p, s in definition['reviewed_source_sha256'].items()), 'scientific_source_inventory_differs')
    metadata = {p: definition['reviewed_source_sha256'][p] for p in ('scripts/qd_ed_n3_report.py', 'scripts/qd_ed_n3_plan.py')}
    require(auth.get('reviewed_metadata_sources') == metadata
            and definition['modules']['report']['sha256'] == inventory['scripts/qd_ed_n3_report.py'], 'reviewed_metadata_identity_differs')
    modules['report'] = dependency_module('report', definition['modules']['report'])
    for task in range(10):
        require(len({tuple(r[k] for k in ('env_seed', 'policy_seed', 'init_index', 'init_row_sha256')) for r in originals[task*3:task*3+3]}) == 1, 'unmatched_task_seed_init')
    plans = {authority['base_plan']['sha256']: base}
    for ref in authority.get('plan_revisions', []):
        plan = inputs.read(ref)
        require(all(plan[k] == base[k] for k in BINDING)
                and plan['code_files'] == base['code_files'] and plan['candidate_profiles'] == base['candidate_profiles']
                and plan['n3_cohort'] == base['n3_cohort']
                and [r for r in plan['episodes'] if not r.get('retry_of')] == originals, 'revision_changes_frozen_condition')
        plans[ref['sha256']] = plan
    require(all(len({r['episode_key'] for r in p['episodes']}) == len(p['episodes']) for p in plans.values()), 'ambiguous_own_plan_rows')
    cells = report['cells']; extras = manifest['cells']; snapshots = auth['completed_audit_snapshots']
    require(len(cells) == len(extras) == len(snapshots) == 30
            and [(c['identity']['task_id'], c['identity']['profile']) for c in cells] == universe
            and len({c['valid_attempt_id'] for c in cells}) == 30
            and {r['attempt_id'] for r in extras} == {c['valid_attempt_id'] for c in cells}
            and {r['attempt_id'] for r in snapshots} == {c['valid_attempt_id'] for c in cells}, 'complete_representative_universe_differs')
    extra_by_id = {r['attempt_id']: r for r in extras}; snapshot_by_id = {r['attempt_id']: r for r in snapshots}
    admitted = []
    for original, cell in zip(originals, cells):
        require(cell['status'] == 'complete_valid' and cell['identity'] == {k: original[k] for k in IDENTITY} and not cell['inflight'], 'cell_not_complete')
        representatives = [a for a in cell['attempts'] if a['status'] == 'complete_valid']
        require(len(representatives) == 1, 'ambiguous_representative')
        saved = representatives[0]; refs = saved['references']; terminal = inputs.read(refs['terminal'])
        attempt_id = cell['valid_attempt_id']; extra = extra_by_id[attempt_id]
        require(set(refs) == {'terminal', 'audit', 'compute', 'metrics'}
                and terminal['attempt_id'] == attempt_id and terminal['event'] == 'valid' and terminal['outcome_valid'] is True
                and all(terminal.get(k) == v for k, v in saved['terminal'].items()), 'accepted_terminal_differs')
        require(terminal['plan_sha256'] in plans, 'unlisted_own_plan')
        plan = plans[terminal['plan_sha256']]
        row = modules['report'].validate_record_identity(terminal, plan, terminal['plan_sha256'])
        require(terminal['identity'] == cell['identity'] and row['init_row_sha256'] == original['init_row_sha256'], 'own_plan_cell_differs')
        if terminal.get('retry_of'):
            prior = [a for a in cell['attempts'] if a['terminal']['attempt_id'] == terminal['retry_of']]
            require(len(prior) == 1 and prior[0]['terminal']['outcome_valid'] is False
                    and prior[0]['terminal']['identity'] == terminal['identity'], 'accepted_recovery_link_missing')
        out = inputs.path(terminal['output_dir']); ed = out/'eds_eval'; ep = ed/'decision_evidence/episode_000'
        require(out.parent == inputs.root/'attempts' and out.name == attempt_id, 'attempt_root_differs')
        expected_paths = {'terminal': out/'attempt-result.json', 'audit': ed/'decision-evidence-audit.json',
                          'compute': ed/'episode_compute.jsonl', 'metrics': ed/'eds_metrics.jsonl'}
        require(all(inputs.path(refs[k]['path']) == p for k, p in expected_paths.items()), 'representative_path_differs')
        audit = inputs.read(refs['audit']); compute_rows = inputs.read(refs['compute'], lines=True)
        require(audit['accepted'] is True and audit['evidence_complete'] is True and audit['errors'] == []
                and audit['original_execution_outcome'] == 'completed' and audit['episode_dir'] == str(ep)
                and audit['episode_compute_file'] == str(ed/'episode_compute.jsonl') and len(compute_rows) == 1, 'accepted_audit_link_differs')
        compute = compute_rows[0]; identity = {'episode_id': 0, 'task_id': row['task_id'], 'episode_seed': row['env_seed']}
        require(all(compute[k] == v for k, v in identity.items()) and compute['outcome'] == terminal['compute_outcome'] == 'completed', 'compute_identity_differs')
        for kind, path in (('metadata', ed/'episode_metadata.jsonl'), ('status', ep/'status.json'), ('index', ep/'events.jsonl')):
            require(inputs.path(extra[kind]['path']) == path, 'episode_metadata_path_differs')
        require(inputs.read(extra['metadata'], lines=True) == [identity], 'episode_metadata_identity_differs')
        status = inputs.read(extra['status']); index = inputs.read(extra['index'], lines=True)
        expected_snapshot = {'attempt_id': attempt_id, 'audit': refs['audit'], 'status': extra['status'], 'index': extra['index'],
                             'auditor_sha256': inventory['scripts/audit_decision_evidence.py'], 'binding': SNAPSHOT}
        require(snapshot_by_id[attempt_id] == expected_snapshot, 'completed_audit_snapshot_missing')
        require(status['schema'] == 'qd-ed-decision-evidence-v1' and status['episode'] == 0 and status['complete'] is True
                and status['failed'] is False and status['pending_action'] is False
                and status['bundles'] == len(index) == compute['decision_evidence']['bundles'], 'collector_snapshot_incomplete')
        expected = [f'bundle_{i:06d}.pt' for i in range(1, len(index)+1)]
        require([r['bundle'] for r in index] == expected and {p.name for p in ep.glob('bundle_*.pt')} == set(expected), 'bundle_index_set_differs')
        stage = optional_stage(extra['stage_events'], ed/'stage_events.jsonl', identity, inputs)
        if row['profile'] == 'N3':
            metrics = inputs.read(refs['metrics'], lines=True)
            require([r['global_step'] for r in metrics] == [r['global_step'] for r in cell['metrics']['n3']['records']]
                    and len(metrics) == compute['guided_chunks']
                    and all(all(m.get(k) == v for k, v in saved.items()) for m, saved in zip(metrics, cell['metrics']['n3']['records'])), 'N3_metric_universe_differs')
        else:
            inputs.bytes(refs['metrics']); metrics = []
        admitted.append(dict(cell=cell, terminal=terminal, refs=refs, ep=ep, status=status, index=index,
                             compute=compute, stage_rows=stage, metrics=metrics))
    # All metadata admission completes before any tensor decoding; hash every indexed native file first.
    for item in admitted:
        for ref in item['index']:
            inputs.bytes({'path': str(item['ep']/ref['bundle']), 'sha256': ref['sha256']})
    return report, admitted


def stream_decisions(item, inputs, torch):
    pending, expected_sequence = [], 1
    for ref in item['index']:
        data = inputs.bytes({'path': str(item['ep']/ref['bundle']), 'sha256': ref['sha256']})
        payload = torch.load(io.BytesIO(data), weights_only=True, map_location='cpu')
        require(payload['schema'] == 'qd-ed-decision-evidence-v1' and payload['events'], 'bundle_schema_or_empty')
        rows = payload['events']
        require(ref['first_sequence'] == rows[0]['sequence'] and ref['last_sequence'] == rows[-1]['sequence']
                and ref['events'] == [{k: r[k] for k in ('sequence', 'event', 'decision_id', 'global_step', 'reset_sequence')} for r in rows], 'bundle_metadata_differs')
        for row in rows:
            require(row['sequence'] == expected_sequence and row['episode'] == item['status']['episode'], 'event_sequence_or_episode_differs')
            expected_sequence += 1
            if pending and row['decision_id'] != pending[0]['decision_id']:
                yield pending
                pending = []
            pending.append(row)
        del data, payload, rows
    if pending:
        yield pending


def runtime_record(profile, context, rows, metric, prefix_length, consumer):
    if profile != 'N3':
        return {'status': 'not_applicable_control', 'active': None, 'executed_actions': prefix_length}
    if not context['use_guidance']:
        require(metric is None, 'unguided_N3_has_metric')
        return {'status': 'unguided', 'active': False, 'executed_actions': prefix_length}
    require(metric is not None, 'guided_N3_metric_missing')
    applicable, active = metric['qd_quality_applicable'], metric['qd_feedback_active']
    selection_rows = [r for r in rows if r['event'] == 'execution_feedback_selection']
    selected = [r['values'] for r in selection_rows]
    if applicable:
        require(len(selected) == 1 and all(selected[0][k] == metric['qd_feedback_'+k] for k in ('active', 'context', 'previous', 'selected')), 'native_metric_feedback_link_differs')
    else:
        require(not selected and not active, 'unsupported_feedback_claim')
    current = metric['qd_feedback_context']
    return {'status': 'active' if active else 'recognized_inactive' if applicable else 'unsupported',
            'applicable': applicable, 'active': active, 'executed_actions': prefix_length,
            'quality_reason': metric['qd_quality_reason'], 'feedback_reason': metric['qd_feedback_reason'],
            'runtime_context': {k: current.get(k) for k in ('episode_generation', 'global_step', 'stage', 'provider_identity', 'target_index', 'target_valid', 'target_status', 'registry_instance_id', 'registry_generation', 'tracker_snapshot')},
            'feedback_selection_event_sequence': selection_rows[0]['sequence'] if selection_rows else None,
            'previous_recorded_provenance': metric['qd_feedback_previous'],
            'selected_recorded_provenance': metric['qd_feedback_selected'],
            'runtime_validity_evidence': 'original accepted frozen native audit; separate from retrospective structural eligibility',
            'consumer': consumer.analyze_active(rows, metric) if active else None}


def mean(values):
    return sum(values)/len(values) if values else None


def episode(item, inputs, modules):
    h, c, t, f = (modules[k] for k in ('task0', 'chronology', 'tracking', 'first3'))
    decisions, steps, resets, tracking, pairs, runtime = [], [], [], [], [], []
    previous = None; metrics = {r['global_step']: r for r in item['metrics']}
    require(len(metrics) == len(item['metrics']), 'duplicate_metric_step')
    profile = item['terminal']['identity']['profile']
    for rows in stream_decisions(item, inputs, h.torch):
        ctx = h.one(rows, 'decision_context'); v = ctx['values']; actual = h.actual_steps(rows)
        d = {k: ctx[k] for k in ('decision_id', 'global_step', 'reset_sequence')}
        d.update(stage=v['stage'], previous_stage=v['previous_stage'], stage_changed=v['stage_changed'],
                 use_guidance=v['use_guidance'], providers=[{k: p.get(k) for k in ('ordinal', 'code_sha256', 'original_code_sha256', 'source_text_sha256', 'source_path')} for p in v['providers']],
                 executed_prefix_length=len(actual), last_executed_step=actual[-1]['global_step'] if actual else None)
        decisions.append(d); steps.extend(actual)
        for row in rows:
            if row['event'] == 'automatic_reset_boundary':
                resets.append({**{k: row[k] for k in ('sequence', 'decision_id', 'global_step', 'reset_sequence')},
                               **{k: row['values'].get(k) for k in ('reset_will_follow', 'reset_completed')}})
        pruned = [value for row in rows if (value := t.pruned(row)) is not None]
        current = t.describe(pruned, previous); pairs.append(t.temporal_pair(previous, current)); tracking.append(current); previous = current
        runtime.append(dict(global_step=ctx['global_step'], decision_id=ctx['decision_id'],
                            **runtime_record(profile, v, rows, metrics.get(ctx['global_step']), len(actual), f)))
    require(len(decisions) == item['status']['decisions'] and sum(d['use_guidance'] for d in decisions) == item['compute']['guided_chunks'], 'decision_count_differs')
    require([s['global_step'] for s in steps] == list(range(len(steps))), 'actual_step_gap')
    if profile == 'N3':
        require(set(metrics) == {d['global_step'] for d in decisions if d['use_guidance']}, 'metric_guided_membership_differs')
    stage = None if item['stage_rows'] is None else [{k: r.get(k) for k in h.STAGE_KEYS} for r in item['stage_rows']]
    chronology = c.chronology(h, decisions, steps, stage)
    eligible = [p for p in pairs if p['status'] == 'retrospective_predictive_check']
    zero, transported = mean([p['zero_mse'] for p in eligible]), mean([p['transported_mse'] for p in eligible])
    return {'schema': 'n3-post-dev-episode-v1', 'attempt_id': item['terminal']['attempt_id'], 'identity': item['terminal']['identity'],
            'retry_of': item['terminal'].get('retry_of'), 'original_terminal_reference': item['refs']['terminal'],
            'original_audit_reference': item['refs']['audit'],
            'decisions': decisions, 'actual_steps': steps, 'automatic_reset_boundaries': resets, 'chronology': chronology,
            'selected_tracking': tracking, 'temporal_pairs': pairs, 'runtime_feedback': runtime,
            'summary': {'observed_actions': len(steps), 'guided_actions': chronology['guided_actions'],
                'guided_action_fraction': chronology['guided_action_fraction'], 'eligible_structural_pairs': len(eligible),
                'pair_disposition_counts': dict(Counter(p.get('reason', p['status']) for p in pairs)),
                'tracking_status_counts': dict(Counter(d['tracking_status'] for d in tracking)),
                'zero_mse_episode_mean': zero, 'transported_mse_episode_mean': transported,
                'transport_minus_zero_episode_mean': transported-zero if eligible else None,
                'runtime_disposition_counts': dict(Counter(r['status'] for r in runtime)),
                'active_executed_actions': sum(r['executed_actions'] for r in runtime if r['active'] is True) if profile == 'N3' else None,
                'final_selected_ordering_witness_decisions': sum(r['consumer']['selected_final_ordering_witness'] for r in runtime if r.get('consumer')) if profile == 'N3' else None,
                'strict_final_witness_decisions': sum(r['consumer']['strict_final_pool_witness'] for r in runtime if r.get('consumer')) if profile == 'N3' else None},
            'limits': ['Fixed float64 predictive arithmetic is not the native T7 internal quality.', 'Structural pairs do not certify runtime eligibility.',
                       'No task success/cost/promotion recomputation; no physical or counterfactual conclusion.']}


def aggregate(cells):
    require([(c['identity']['task_id'], c['identity']['profile']) for c in cells] == [(t, a) for t in range(10) for a in ARMS], 'aggregate_universe_differs')
    result = {}
    for arm in ARMS:
        rows = [c for c in cells if c['identity']['profile'] == arm]
        observed = [r['summary']['transport_minus_zero_episode_mean'] for r in rows if r['summary']['transport_minus_zero_episode_mean'] is not None]
        result[arm] = {'episodes': 10, 'eligible_episode_count': len(observed), 'no_eligible_episode_count': 10-len(observed),
                       'episode_mean_transport_minus_zero': mean(observed),
                       'tasks': [{k: r[k] for k in ('identity', 'attempt_id', 'summary')} for r in rows]}
    return result


def run(auth_path, auth_sha, output):
    require(os.environ.get('CUDA_VISIBLE_DEVICES') == '', 'CPU_mask_required')
    inputs = Inputs(); auth = inputs.read({'path': str(Path(auth_path).resolve()), 'sha256': auth_sha})
    require(auth['schema'] == 'n3-post-dev-read-authorization-v1' and auth['status'] == 'authorized', 'read_not_authorized')
    freeze = inputs.read(auth['freeze'])
    for name, expected in freeze['files'].items():
        require(Path(name).name == name and sha((HERE/name).read_bytes()) == expected, 'frozen_local_source_differs')
    require(freeze['files']['read_full_dev.py'] == sha(Path(__file__).read_bytes()) and freeze['actual_read_authorized'] is False, 'reader_freeze_differs')
    definition = parse((HERE/'dependencies-v1.json').read_bytes()); modules = dependencies(definition)
    manifest = inputs.read(auth['manifest'])
    out = inputs.path(output)
    require(str(out) == auth['output'] and out.is_relative_to(inputs.root/'continuation_20260923/n3-post-dev-analysis') and not out.exists(), 'new_authorized_output_required')
    out.mkdir(parents=True, exist_ok=False); start = time.monotonic(); phase = 'admission'; current = None
    def status(value):
        (out/'status.json').write_text(json.dumps(value, allow_nan=False)+'\n')
    status({'complete': False, 'phase': phase})
    try:
        report, admitted = admit(manifest, auth, definition, modules, inputs)
        index = []
        for item in admitted:
            identity = item['terminal']['identity']; current = f"t{identity['task_id']:02d}-{identity['profile'].lower()}"; phase = 'extraction'
            value = episode(item, inputs, modules); path = out/(current+'.json'); xjson(path, value)
            index.append({'cell': current, 'identity': identity, 'attempt_id': value['attempt_id'], 'path': path.name,
                          'sha256': sha(path.read_bytes()), 'summary': value['summary']})
            print(json.dumps({'completed_cells': len(index), 'cell': current}), flush=True)
        phase = 'final_verification'; current = None; inputs.finish()
        require(not modules['task0'].torch.cuda.is_initialized(), 'CUDA_initialized')
        for ref in definition['modules'].values(): require(sha(Path(ref['path']).read_bytes()) == ref['sha256'], 'dependency_changed')
        for name, expected in freeze['files'].items(): require(sha((HERE/name).read_bytes()) == expected, 'local_source_changed')
        xjson(out/'index.json', {'schema': 'n3-post-dev-index-v1', 'complete': True, 'cells': index,
                                'episode_level_aggregation': aggregate(index), 'matrix_authority': manifest['matrix_report'],
                                'promotion_authorized': False, 'unknown': modules['chronology'].UNKNOWN})
        xjson(out/'provenance.json', {'complete': True, 'authorization_sha256': auth_sha, 'manifest': auth['manifest'],
              'freeze': auth['freeze'], 'source_commit': SOURCE, 'input_hashes': inputs.hashes,
              'declared_absent_sources': [str(p) for p in inputs.absent], 'dependencies': definition,
              'fresh_audit_calls': 0, 'cuda_initialized': False, 'new_quality_computation': False,
              'wall_seconds': time.monotonic()-start, 'scientific_authority': 'unchanged original N3 matrix report'})
        status({'complete': True, 'cells': 30, 'index_sha256': sha((out/'index.json').read_bytes())})
    except Exception as error:
        status({'complete': False, 'phase': phase, 'cell': current, 'error_type': type(error).__name__, 'error': str(error)})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--authorization', required=True); parser.add_argument('--authorization-sha256', required=True)
    parser.add_argument('--output', required=True); parser.add_argument('--execute-reviewed', action='store_true')
    args = parser.parse_args(); require(args.execute_reviewed, 'explicit_review_required')
    run(args.authorization, args.authorization_sha256, args.output)


if __name__ == '__main__':
    main()
