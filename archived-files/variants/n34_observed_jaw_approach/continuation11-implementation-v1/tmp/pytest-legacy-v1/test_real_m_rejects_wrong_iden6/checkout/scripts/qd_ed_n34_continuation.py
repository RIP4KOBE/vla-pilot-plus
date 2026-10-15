"""Outcome-aware amended Dev screen: exact retained19 plus original missing11.

Read-only reconciliation. This module never approves, promotes, rewrites a receipt,
replays an audit, or launches the predecessor. Original episode keys are preserved;
the separately hashed plan/release is the new operational identity.
"""
import copy
import datetime as dt
import hashlib
import json
from pathlib import Path

from scripts import qd_ed_n23_worker as w, qd_ed_n34_contract as c
from scripts import qd_ed_n34_supervise as s, qd_ed_n34_release as legacy

BASE = '4b390b3e0c6b708572736939749a0fab0fb7ef37'
DESIGN_SHA = '83c0b81a19c4c88b93390a90b8a35b7d3546c41d37b711478cd2bcd21a66cd0d'
LABEL = 'N34_CONTINUATION11_OUTCOME_AWARE_AMENDED_DEV_20261009'
LIMITS = {'attempts': 11, 'baseline': 3, 'development': 8, 'recovery': 0,
          'automatic_recoveries': 0, 'max_gpu_seconds': 20240,
          'episode_seconds': 1800, 'cleanup_seconds': 40,
          'physical_gpu': 7, 'gpu_uuid': c.GPU_UUID}
GATES = {'all_valid_cells': 30, 'candidate_min_successes': 5, 'at_least_both_controls': True,
         'futility': 'complete valid triples only; 1 success plus4 remaining has upper bound5; any additional candidate failure makes >=5 impossible'}
LIFECYCLE = ('attempt_id', 'episode_key', 'identity', 'budget_bucket', 'replacement',
             'plan_sha256', 'release', 'source_commit', 'runtime_manifest_sha256',
             'runtime_inventory_sha256', 'init_row_sha256', 'output_dir', 'physical_gpu',
             'ledger_prefix', 'context', 'stage_backend', 'stage_model', 'stage_condition')


def load_design(reference, root=c.ROOT):
    w.require(reference['sha256'] == DESIGN_SHA, 'unreviewed continuation design')
    design = w.read_ref(reference)
    original = w.read_ref(design['predecessor_plan'])
    terminal = w.read_ref(design['terminal_reconciliation'])
    rows = c.expected_rows(root)
    w.require(design['schema'] == 'n34-separate-continuation-design-v1'
              and design['source'] == original['source']['commit'] == terminal['source'] == BASE
              and original['schema'] == 'n34-released-plan-v1'
              and original['frozen'] is True and original['release_enabled'] is True
              and original['episodes'] == rows and original['limits'] == c.LIMITS
              and original['worker_contract'] == c.WORKER_CONTRACT
              and design['retained_valid_episode_keys'] == [r['episode_key'] for r in rows[:19]]
              and design['unobserved_original_rows'] == rows[19:]
              and design['unchanged_gates'] == GATES and design['deadline'] == c.DEADLINE,
              'original design/plan/identity/gates differ')
    w.require(terminal['controller']['plan'] == design['predecessor_plan']
              and terminal['scientific_source'] == original['scientific_source']
              and terminal['worker_handles'] == []
              and terminal['disposition'] == 'BUDGET_CAPPED_PARTIAL_COHORT_NO_PROMOTION',
              'terminal reconciliation differs')
    return design, original, terminal


def read_prefix(path, anchor):
    legacy.prefix(path, anchor)
    with Path(path).open('rb') as stream:
        raw = stream.read(anchor['bytes'])
    w.require(not raw or raw.endswith(b'\n'), 'prefix ends inside journal row')
    return raw


def n34_events(raw):
    """Decode only this study's exposed N34 Dev rows, never protected outcomes."""
    events = []
    for line in raw.splitlines():
        if b'"n34' not in line:
            continue
        event = json.loads(line)
        if str(event.get('attempt_id', '')).startswith('n34'):
            w.require(event.get('identity', {}).get('split', 'dev') == 'dev', 'non-Dev N34 event')
            events.append(event)
    return events


def _groups(rows, events):
    local = c.cohort_events(c.expected_rows(), events)
    groups = []
    for event in local:
        if not groups or groups[-1][0]['attempt_id'] != event['attempt_id']:
            groups.append([])
        groups[-1].append(event)
    w.require(len(groups) <= len(rows), 'replayed/extra original row')
    for row, group in zip(rows, groups):
        w.require([e['event'] for e in group] in (['reserved'], ['reserved', 'dispatched'],
                  ['reserved', 'dispatched', 'valid'], ['reserved', 'dispatched', 'aborted']),
                  'duplicated/malformed lifecycle')
        w.require(all(e['attempt_id'] == row['episode_key'] and e['identity'] == s.c_identity(row)
                      for e in group), 'omitted/duplicated/reordered original row')
        w.require(all(all(k in e and e[k] == group[0][k] for k in LIFECYCLE) for e in group),
                  'lifecycle binding differs')
    return groups


def _outcome(row, terminal, origin):
    return {'task_id': row['task_id'], 'profile': row['profile'], 'success': terminal['success'],
            'episode_key': row['episode_key'], 'attempt_id': terminal['attempt_id'],
            'origin': origin}


def verify_retained(design, original, reconciliation, ledger_path):
    """Verify frozen evidence, without requiring legacy files to equal new HEAD.

    The externally bound reconciliation anchors the exact receipt/audit hashes;
    the immutable journal prefix anchors terminal values and every historical cost.
    Runtime/source inventories are checked as historical claims, not re-executed.
    """
    from scripts import qd_ed_n34_source as source, qd_ed_n34_worker as worker
    raw = read_prefix(ledger_path, design['ledger_prefix'])
    events = n34_events(raw)
    c.require_replacement_history(events)
    rows = original['episodes'][:19]
    groups = _groups(rows, events)
    checks = reconciliation['receipt_checks']
    w.require(len(groups) == len(checks) == 19
              and [x['attempt_id'] for x in checks] == design['retained_valid_episode_keys'],
              'retained19 coverage differs')
    release_ref = reconciliation['controller']['release']
    release = w.read_ref(release_ref)
    w.require(release['plan'] == design['predecessor_plan'] and release['source'] == original['source']
              and release['scientific_source'] == original['scientific_source']
              and release['approved'] is True, 'retained release/source differs')
    w.require(release == {**{k: original[k] for k in ('authority', 'protocol', 'source',
              'scientific_source', 'runtime_closure', 'controller_semantics', 'runtime', 'limits', 'phase_authorization')},
              'schema': 'n34-execution-release-v1', 'approved': True,
              'plan': design['predecessor_plan'], 'root_review': release['root_review']},
              'retained release closure differs')
    review = w.read_ref(release['root_review'])
    w.require(review == {**{k: v for k, v in release.items() if k != 'root_review'},
                         'schema': 'n34-root-production-review-v1', 'decision': 'APPROVED'},
              'retained root review differs')
    protocol = w.read_ref(original['protocol'])
    w.require(protocol['episodes'] == original['episodes'] and protocol['limits'] == c.LIMITS
              and protocol['worker_contract'] == c.WORKER_CONTRACT, 'retained protocol differs')
    runtime = w.read_ref(original['runtime'])
    w.require(runtime['frozen_stage_provider']['backend'] == 'codex_cli', 'retained provider differs')
    legacy.r.stage_overrides(runtime)
    closure = w.read_ref(original['runtime_closure'])
    w.require(closure['runtime'] == original['runtime'], 'retained runtime closure binding')
    from scripts.qd_ed_n34_controller import verify_semantics
    proof = verify_semantics(original['controller_semantics'], original['runtime'], closure)
    expected_controller = {k: proof[k] for k in ('source', 'module', 'class', 'instance')}
    outcomes = []
    for row, group, check in zip(rows, groups, checks):
        w.require([x['event'] for x in group] == ['reserved', 'dispatched', 'valid'], 'retained lifecycle')
        final = group[-1]
        manifest_ref = original['expected_manifests'][row['episode_key']]
        manifest = w.read_ref(manifest_ref)
        output = Path(manifest['output_dir'])
        w.require(manifest['row'] == row and manifest['source'] == original['source']
                  and manifest['scientific_source'] == original['scientific_source']
                  and all(manifest[k] == original[k] for k in ('runtime', 'runtime_closure', 'controller_semantics')),
                  'retained legacy manifest differs')
        w.require(final['source_commit'] == BASE and final['plan_sha256'] == design['predecessor_plan']['sha256']
                  and final['release'] == release_ref and final['output_dir'] == str(output)
                  and final['runtime_manifest_sha256'] == original['runtime']['sha256']
                  and final['runtime_inventory_sha256'] == original['runtime_inventory_sha256']
                  and final['init_row_sha256'] == row['init_row_sha256'] and final['physical_gpu'] == 7
                  and final['outcome_valid'] is True and final['required_cost_telemetry_complete'] is True
                  and type(final['success']) is bool and final['n34_worker_receipt'] == check['receipt'],
                  'retained terminal/source/seed/receipt differs')
        c.finite(final['gpu_process_wall_seconds'], 'retained cost')
        read_prefix(ledger_path, final['ledger_prefix'])
        w.require(w.read_ref(c.ref(output / 'attempt-result.json')) == final, 'retained terminal JSON differs')
        context = w.read_ref(final['context'])
        expected_context = {'schema': 'n34-worker-context-v1', 'plan': design['predecessor_plan'],
            'release': release_ref, 'expected_manifest': manifest_ref, 'episode_key': row['episode_key'],
            'attempt_id': row['episode_key'], 'main_argv': manifest['argv'][1:], 'worker_contract': c.WORKER_CONTRACT}
        w.require(context == expected_context, 'retained context differs')
        receipt = w.read_ref(check['receipt'])
        report = w.read_ref(check['audit_report'])
        w.require(check['receipt']['path'] == str(output / 'eds_eval/n34-worker-receipt.json')
                  and check['audit_report']['path'] == str(output / 'eds_eval/decision-evidence-audit.json')
                  and receipt['audit_report'] == check['audit_report']
                  and receipt['accepted'] is True and report['accepted'] is True
                  and report['evidence_complete'] is True and receipt['process_unchanged'] is True
                  and receipt['schema'] == 'n34-worker-receipt-v2' and receipt['main_exit_code'] == 0,
                  'retained native receipt/audit differs')
        for key, value in {'context': final['context'], 'plan': design['predecessor_plan'],
                           'row': row, 'attempt_id': row['episode_key'], 'expected_manifest': manifest_ref,
                           'source': original['source'], 'scientific_source': original['scientific_source']}.items():
            w.require(receipt[key] == value, 'retained receipt binding ' + key)
        w.require(receipt['controller_instances'] and all(x == expected_controller for x in receipt['controller_instances']),
                  'retained deployed controller differs')
        cuda = receipt['worker_cuda']
        w.require(cuda['physical_gpu'] == 7 and cuda['uuid'] == c.GPU_UUID
                  and cuda['logical_device'] == 'cuda:0'
                  and worker.canonical_cuda_uuid(cuda['actual_uuid']) == worker.canonical_cuda_uuid(c.GPU_UUID),
                  'retained assigned CUDA identity differs')
        w.require(receipt['audit_backend']['kind'] == receipt['audit_backend']['logical_device'] == 'cpu'
                  and report['n23_arithmetic_backend'] == receipt['audit_backend'], 'retained audit backend differs')
        gate = report['n34_observed_jaw_audit' if row['profile'] == 'N34' else 'n31_capture_dwell_audit']
        w.require(gate['profile'] == row['profile'] and all(gate.get(k) == v for k, v in receipt['native_counts'].items()),
                  'retained native counts differ')
        if row['profile'] == 'N34':
            w.require(gate['runtime_identity'] == manifest['expected_runtime']
                      and receipt['native_counts'] == gate, 'retained candidate native identity differs')
        else:
            w.require(manifest['expected_runtime'] is None and 'n34_observed_jaw_audit' not in report
                      and report['n34_control_absence'] == {'profile': row['profile'], 'events': 0, 'metrics': 0},
                      'retained control absence differs')
        process = w.read_ref(c.ref(output / 'process.json'))
        w.require(all(process[k] == receipt['process'][k] for k in ('pid', 'boot_id', 'proc_start_ticks'))
                  and process['context'] == final['context'] and process['release'] == release_ref
                  and process['attempt_id'] == row['episode_key'], 'retained same-worker process differs')
        w.require(w.read_ref(c.ref(output / 'eds_eval/n34-worker-start.json')) ==
                  {'context': final['context'], 'process': receipt['process']}, 'retained worker start differs')
        w.require(w.read_ref(c.ref(output / 'command.json')) == {
            'argv': [manifest['argv'][0], '-m', 'scripts.qd_ed_n34_worker', '--context',
                     final['context']['path'], '--context-sha256', final['context']['sha256']],
            'main_argv': manifest['argv'], 'context': final['context']}, 'retained command differs')
        index = {f['path']: f['sha256'] for f in original['source']['files']}
        for phase in ('loaded_before', 'loaded_after'):
            inventory = receipt[phase]
            required = {'scripts.qd_ed_n34_worker', 'scripts.qd_ed_n34_source',
                        'scripts.qd_ed_n34_native', 'scripts.qd_ed_n31_native',
                        'scripts.audit_decision_evidence', 'scripts.qd_ed_n34_controller'}
            w.require(required <= set(inventory)
                      and all(index.get(v['path']) == v['sha256'] for v in inventory.values()),
                      'retained loaded source differs')
        for phase in ('runtime_before', 'runtime_after'):
            source.verify_runtime_receipt(closure, receipt[phase], binding=worker.runtime_receipt_binding(
                final['context'], original, receipt['process'], phase), after=phase == 'runtime_after')
        w.require(all(receipt['runtime_after']['generated_modules'].get(k) == v
                      for k, v in receipt['runtime_before']['generated_modules'].items()),
                  'retained generated runtime differs')
        # Hash checks only; no tensor/native audit or outcome recomputation.
        w.require(w.canonical_sha(receipt['evidence']['files']) == receipt['evidence']['sha256'],
                  'retained evidence inventory digest differs')
        outcomes.append(_outcome(row, final, 'retained_legacy'))
    expected = [{k: v for k, v in x.items() if k != 'origin'} for x in outcomes]
    w.require(expected == reconciliation['reconciliation']['outcomes'], 'retained outcomes differ')
    return outcomes


def mapping(design):
    return [{'original': copy.deepcopy(row), 'dispatch': copy.deepcopy(row)}
            for row in design['unobserved_original_rows']]


def validate_shape(plan, design, original):
    w.require(plan['schema'] in ('n34-continuation-draft-v1', 'n34-continuation-plan-v1')
              and plan['label'] == LABEL and plan['limits'] == LIMITS
              and plan['identity_mapping'] == mapping(design)
              and plan['episodes'] == original['episodes'][19:] == design['unobserved_original_rows']
              and plan['retained_episode_keys'] == design['retained_valid_episode_keys']
              and plan['predecessor_plan'] == design['predecessor_plan']
              and plan['terminal_reconciliation'] == design['terminal_reconciliation']
              and plan['scientific_interpretation'] == design['scientific_interpretation']
              and plan['gates'] == GATES and plan['worker_contract'] == c.WORKER_CONTRACT
              and plan['deadline'] == c.DEADLINE and plan['stop_path'] == original['stop_path']
              and plan['phase_authorization']['validation'] is False
              and plan['phase_authorization']['formal'] is False
              and plan['automatic_promotion'] is False and plan['root_scientific_review_required'] is True,
              'continuation identity/interpretation/gates differ')
    retained = set(plan['retained_episode_keys'])
    pending = [x['episode_key'] for x in plan['episodes']]
    w.require(len(retained) == 19 and len(set(pending)) == len(pending) == 11
              and not retained.intersection(pending)
              and retained | set(pending) == {x['episode_key'] for x in original['episodes']},
              'retained/missing conservation/disjointness')
    w.require(set(plan['expected_manifests']) == set(pending), 'only missing11 manifests required')


def summarize(outcomes, status):
    rows = c.expected_rows()
    w.require(len(outcomes) <= 30 and [x['episode_key'] for x in outcomes] ==
              [r['episode_key'] for r in rows[:len(outcomes)]], 'aggregate exact identity prefix')
    for item, row in zip(outcomes, rows):
        w.require(item['task_id'] == row['task_id'] and item['profile'] == row['profile']
                  and item['attempt_id'] == row['episode_key'] and type(item['success']) is bool
                  and item['origin'] == ('retained_legacy' if rows.index(row) < 19 else 'continuation'),
                  'aggregate identity/source/validity')
    triples = len(outcomes) // 3
    matched = outcomes[:triples * 3]
    totals = {arm: sum(x['success'] for x in matched if x['profile'] == arm) for arm in c.ARMS}
    return {'label': LABEL, 'status': status, 'valid_cells': len(outcomes), 'planned_cells': 30,
            'complete_triples': triples, 'matched_denominator_per_arm': triples,
            'planned_denominator_per_arm': 10, 'matched_successes': totals,
            'candidate_upper_bound': totals['N34'] + 10 - triples,
            'amended_dev_necessary_gate_met': len(outcomes) == 30 and status == 'COMPLETE'
                and totals['N34'] >= max(5, totals['C0'], totals['Q0']),
            'independent_replication': False, 'confirmatory_evidence': False,
            'automatic_promotion': False, 'root_scientific_review_required': True,
            'validation_authorized': False, 'formal_authorized': False}


def reconcile(plan, retained, events, verify_new, *, live_handles=()):
    """Input retained values must come from verify_retained in the same transaction."""
    original_rows = c.expected_rows()
    w.require(plan['episodes'] == original_rows[19:] and len(retained) == 19, 'exact continuation matrix')
    all_groups = _groups(original_rows, events)
    w.require(len(all_groups) >= 19, 'retained prefix omitted')
    for row, group, expected in zip(original_rows[:19], all_groups[:19], retained):
        w.require([e['event'] for e in group] == ['reserved', 'dispatched', 'valid']
                  and _outcome(row, group[-1], 'retained_legacy') == expected, 'retained outcome changed/replayed')
    outcomes = copy.deepcopy(retained)
    pending = all_groups[19:]
    status = 'READY_FOR_ROOT_RELEASE'
    for index, group in enumerate(pending):
        row = plan['episodes'][index]
        kinds = [e['event'] for e in group]
        if kinds in (['reserved'], ['reserved', 'dispatched']):
            w.require(index == len(pending) - 1, 'dispatch after unsettled attempt')
            status = 'LIVE_OR_UNSETTLED'; break
        if kinds != ['reserved', 'dispatched', 'valid']:
            w.require(index == len(pending) - 1, 'dispatch after invalid attempt')
            status = 'INVALID_STOP'; break
        final = group[-1]
        if not (final.get('outcome_valid') is True and final.get('required_cost_telemetry_complete') is True
                and type(final.get('success')) is bool):
            w.require(index == len(pending) - 1, 'dispatch after invalid outcome')
            status = 'INVALID_STOP'; break
        verify_new(row, final)  # full new release/native/provider/source closure; fail closed
        outcomes.append(_outcome(row, final, 'continuation'))
        if len(outcomes) % 3 == 0 and summarize(outcomes, status)['candidate_upper_bound'] < 5:
            w.require(index == len(pending) - 1, 'dispatch after complete-triple futility')
            status = 'NUMERIC_FUTILITY'; break
    else:
        status = 'COMPLETE' if len(outcomes) == 30 else status
    if live_handles:
        status = 'LIVE_OR_UNSETTLED'
    return {'status': status, 'next_row': original_rows[len(outcomes)] if status == 'READY_FOR_ROOT_RELEASE' else None,
            'outcomes': outcomes, 'summary': summarize(outcomes, status)}


def guard(row, allowance, *, now, stop_path):
    """Full 1840-second guard for the separate incremental ceiling."""
    w.require(row in c.expected_rows()[19:], 'dispatch missing11 only')
    w.require(not Path(stop_path).exists() and not Path(stop_path).is_symlink(), 'STOP pre-dispatch')
    w.require(now.tzinfo is not None, 'timezone-aware time required')
    start = dt.datetime.fromisoformat(allowance['authority_starts_at'].replace('Z', '+00:00'))
    end = min(dt.datetime.fromisoformat(allowance['authority_ends_at'].replace('Z', '+00:00')),
              dt.datetime.fromisoformat(c.DEADLINE.replace('Z', '+00:00')))
    w.require(start <= now and now + dt.timedelta(seconds=1840) <= end, 'expired/full1840-second window')
    w.require(allowance['private_budget'] is True and allowance['gpu_idle'] is True
              and allowance['physical_gpu'] == 7 and allowance['gpu_uuid'] == c.GPU_UUID
              and not allowance['live_handles'] and allowance['unsettled_reservations'] == 0,
              'assigned GPU/private/settled admission')
    for key in ('global_seconds_remaining', 'private_seconds_remaining', 'incremental_seconds_remaining'):
        w.require(c.finite(allowance[key], key) >= 1840, 'full1840-second admission ' + key)
    w.require(allowance['incremental_seconds_remaining'] <= 20240, 'incremental ceiling')
    protected = c.finite(allowance['protected_seconds_remaining'], 'protected reserve')
    w.require(min(allowance['global_seconds_remaining'], allowance['private_seconds_remaining']) - protected >= 1840,
              'protected reserve')
    for key in ('global_attempts_remaining', 'protected_attempts_remaining', 'incremental_attempts_remaining', 'bucket_attempts_remaining'):
        w.require(type(allowance[key]) is int and allowance[key] >= 0, 'attempt allowance ' + key)
    w.require(1 <= allowance['incremental_attempts_remaining'] <= 11
              and allowance['bucket_attempts_remaining'] >= 1
              and allowance['global_attempts_remaining'] - allowance['protected_attempts_remaining'] >= 1,
              'attempt/protected limit')
    return 1840
