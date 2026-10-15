"""Bounded original metadata verification; never relabel receipts or replay tensors.

Trust terminates at the caller's detached root release, which commits the exact
preparation map and the independently reviewed original receipt closure.
"""
from pathlib import Path
from scripts import qd_ed_n23_worker as w, qd_ed_n32_contract as old
from scripts import qd_ed_n32_supervise as old_supervisor, qd_ed_n32_release as old_release
from scripts import qd_ed_n32r3_contract as c


def validate_mapping(plan):
    mapping = c.read_ref(plan['carry_forward_map'])
    verify_preparation_anchor(plan)
    parent = c.read_ref(plan['parent_plan'])
    old_release.validate_plan(parent)  # Original schema/matrix contract, unchanged.
    w.require(c.same_ref(mapping['parent_plan'], plan['parent_plan'])
              and parent['source'] == plan['scientific_source']
              and parent['source']['commit'] == c.BASE_SOURCE, 'immutable parent/source')
    released = c.read_ref(plan['parent_release'])
    expected = {'schema': 'n32-execution-release-v1', 'approved': True, 'plan': plan['parent_plan'],
                **{k: parent[k] for k in ('authority', 'protocol', 'source', 'runtime', 'limits', 'phase_authorization')}}
    w.require(released == {**expected, 'root_review': plan['parent_review']}, 'original detached release')
    w.require(c.read_ref(plan['parent_review']) == {**expected, 'schema': 'n32-root-production-review-v1', 'decision': 'APPROVED'}, 'original root review')
    evidence = c.read_ref(mapping['continuity_evidence'])
    w.require(c.same_ref(evidence['inputs']['plan.frozen.v1.json'], plan['parent_plan'])
              and c.same_ref(evidence['inputs']['execution-release-v1.json'], plan['parent_release'])
              and c.same_ref(evidence['inputs']['root-production-review-v1.json'], plan['parent_review']), 'parent evidence commitments')
    c.read_ref(mapping['terminal_review'])
    w.require(mapping['schema'] == 'n32r3-carry-forward-map-v1' and mapping['continuity_failures'] == []
              and mapping['release_enabled'] is False and mapping['pooling_authorized'] is False
              and mapping['command_candidates'] == plan['command_candidates'], 'immutable preparation map')
    accepted, proposed = mapping['accepted_cells'], mapping['proposed_cells']
    w.require(len(accepted) == 14 and len(proposed) == 16, '14+16 exact map')
    for entry, row in zip(accepted, parent['episodes'][:14]):
        w.require(entry['original_row'] == row and
                  entry['old_attempt_id'] == entry['new_attempt_id'] == entry['attempt_id'] == row['episode_key']
                  and entry['semantic_cell'] == {k: row[k] for k in c.SEMANTIC_FIELDS}
                  and entry['expected_manifest'] == parent['expected_manifests'][row['episode_key']]
                  and entry['source_commit'] == c.BASE_SOURCE and entry['runtime'] == parent['runtime']
                  and entry['denominator_eligible'] is True and entry['replay_permitted'] is False, 'carry-forward identity')
    invalid = mapping['old_invalid_cell']
    w.require(invalid['original_row'] == parent['episodes'][14] and invalid['attempt_id'] == c.OLD_INVALID
              and invalid['denominator_eligible'] is False and invalid['new_attempt_id'] is None
              and invalid['proposed_recovery_attempt_id'] == c.RECOVERY, 'unique invalid linkage')
    for entry, old_row, row in zip(proposed, parent['episodes'][14:], c.expected_rows(plan['worktree'])):
        w.require(entry['old_row'] == old_row and entry['proposed_row'] == row
                  and entry['old_attempt_id'] == old_row['episode_key'] and entry['new_attempt_id'] == row['episode_key']
                  and entry['semantic_continuity'] == {k: v for k, v in old_row.items() if k not in ('iteration', 'episode_key', 'budget_bucket')}
                  and entry['parent_expected_manifest'] == parent['expected_manifests'][old_row['episode_key']]
                  and entry['recovery_of'] == c.recovery_of(row) and entry['retry_of'] is None
                  and entry['native_receipt'] is None and entry['generic_audit'] is None
                  and entry['release_enabled'] is False, 'proposed semantic/execution identity')
    return mapping, parent


def verify_cell(entry, plan, parent, *, valid=True):
    """Verify exact reviewed metadata bytes and their cross-artifact identities.

    This is deliberately not a replacement native/generic audit. Original audit
    evidence remains committed by the original receipts and root review.
    """
    data = {k: c.read_ref(entry[k]) for k in ('terminal_receipt', 'native_receipt', 'generic_audit',
                                            'context', 'command_receipt', 'process_receipt', 'expected_manifest')}
    stage = entry['stage_events']
    path = Path(stage['path'])
    w.require(path.is_file() and not path.is_symlink() and w.sha(path) == stage['sha256']
              and path.stat().st_size == stage['bytes'], 'Stage metadata digest')
    terminal, native, context, process, manifest = (data[k] for k in ('terminal_receipt', 'native_receipt', 'context', 'process_receipt', 'expected_manifest'))
    row = entry['original_row']; key = row['episode_key']
    output = Path(manifest['output_dir'])
    paths = {'terminal_receipt': 'attempt-result.json', 'native_receipt': 'eds_eval/n32-worker-receipt.json',
             'generic_audit': 'eds_eval/decision-evidence-audit.json', 'context': 'n32-worker-context.json',
             'command_receipt': 'command.json', 'process_receipt': 'process.json', 'stage_events': 'eds_eval/stage_events.jsonl'}
    w.require(all(entry[k]['path'] == str(output / v) for k,v in paths.items()), 'original receipt paths')
    w.require(context == {'schema': 'n32-worker-context-v1', 'plan': plan['parent_plan'],
              'release': plan['parent_release'], 'expected_manifest': entry['expected_manifest'],
              'episode_key': key, 'attempt_id': key, 'main_argv': manifest['argv'][1:], 'worker_contract': old.WORKER_CONTRACT}, 'original context binding')
    w.require(manifest['row'] == row and manifest['source'] == parent['source'] and manifest['runtime'] == parent['runtime'], 'original manifest identity')
    w.require(process['attempt_id'] == key and process['context'] == entry['context'] and process['release'] == plan['parent_release'], 'original process binding')
    identity = {k: process[k] for k in ('pid', 'proc_start_ticks', 'boot_id')}
    w.require(native['process'] == identity and native['context'] == entry['context'] and native['plan'] == plan['parent_plan']
              and native['row'] == row and native['source'] == parent['source'] and native['expected_manifest'] == entry['expected_manifest']
              and native['attempt_id'] == key and c.same_ref(native['audit_report'], entry['generic_audit'])
              and native['native_counts'] == entry['native_counts'] and native['accepted'] is True
              and native['process_unchanged'] is True and native['main_exit_code'] == 0, 'original native binding')
    report = data['generic_audit']
    w.require(report['accepted'] is True and report['evidence_complete'] is True, 'original generic invalid')
    command = data['command_receipt']
    w.require(command == {'argv': [manifest['argv'][0], '-m', 'scripts.qd_ed_n32_worker', '--context', entry['context']['path'], '--context-sha256', entry['context']['sha256']],
                         'main_argv': manifest['argv'], 'context': entry['context']}, 'original command binding')
    w.require(terminal['identity'] == old_supervisor.c_identity(row) and terminal['attempt_id'] == terminal['episode_key'] == key
              and terminal['source_commit'] == parent['source']['commit'] and terminal['plan_sha256'] == plan['parent_plan']['sha256']
              and terminal['release'] == plan['parent_release'] and terminal['context'] == entry['context']
              and terminal['runtime_manifest_sha256'] == parent['runtime']['sha256']
              and terminal['runtime_inventory_sha256'] == parent['runtime_inventory_sha256']
              and terminal['budget_bucket'] == row['budget_bucket'] and terminal['init_row_sha256'] == row['init_row_sha256']
              and terminal['physical_gpu'] == 7 and terminal['output_dir'] == str(output), 'original terminal identity')
    elapsed = c.finite(terminal['gpu_process_wall_seconds'], 'original charge')
    w.require(elapsed / 3600 == entry['gpu_hours_retained'] and entry['budget_bucket_retained'] == row['budget_bucket'], 'retained charge differs')
    if valid:
        w.require(c.same_ref(terminal['n32_worker_receipt'], entry['native_receipt']), 'original terminal native receipt')
        w.require(terminal['event'] == 'valid' and terminal['outcome_valid'] is True
                  and terminal['required_cost_telemetry_complete'] is True and type(terminal['success']) is bool
                  and terminal['success'] == entry['success'], 'original terminal invalid')
    else:
        w.require(terminal['event'] == 'aborted' and terminal['outcome_valid'] is False and terminal['success'] is None, 'old invalid must remain invalid')
    return terminal


def verified_parent(plan, events):
    from scripts.qd_ed_n32r3_release import verify_continuity
    verify_continuity(plan)
    w.verify_source(plan['worktree'], plan['source'])
    mapping, parent = validate_mapping(plan)
    outcomes = []
    historical_ids = {x['attempt_id'] for x in mapping['accepted_cells']} | {c.OLD_INVALID}
    w.require(all(e['attempt_id'] in historical_ids for e in events
                  if e.get('identity', {}).get('iteration') == old.COHORT), 'parent cohort changed after reviewed prefix')
    for entry in mapping['accepted_cells'] + [mapping['old_invalid_cell']]:
        valid = entry is not mapping['old_invalid_cell']
        terminal = verify_cell(entry, plan, parent, valid=valid)
        group = [e for e in events if e['attempt_id'] == entry['attempt_id']]
        w.require([e['event'] for e in group] == ['reserved', 'dispatched', terminal['event']]
                  and group[-1] == terminal, 'original journal/receipt lifecycle differs')
        immutable = ('attempt_id','episode_key','identity','plan_sha256','release','source_commit','runtime_manifest_sha256',
                     'runtime_inventory_sha256','init_row_sha256','output_dir','physical_gpu','context','ledger_prefix','budget_bucket')
        w.require(all(all(k in e and e[k] == terminal[k] for k in immutable) and e.get('retry_of') is None
                      and e.get('recovery_of') is None for e in group), 'parent lifecycle drift')
        if valid:
            outcomes.append({'task_id': entry['original_row']['task_id'], 'profile': entry['original_row']['profile'],
                             'success': terminal['success'], 'attempt_id': terminal['attempt_id']})
    return outcomes


def verify_preparation_anchor(plan):
    """The existing independent bounded review is evidence, never new authority."""
    w.require(plan['preparation_review']['sha256'] == '8666822f801c4e04aece1e7e9bb48c245ec206e69a8d73f8821a9022fbc91428', 'independent preparation review anchor')
    review = c.read_ref(plan['preparation_review'])
    w.require(review['status'] == 'PASS_FOR_BOUNDED_CPU_IMPLEMENTATION_ONLY' and review['source'] == c.BASE_SOURCE
              and review['accepted_historical_cells'] == 14 and review['proposed_cells'] == 16, 'preparation review scope')
    index = c.read_ref(review['artifact_index'])
    for key in ('carry_forward_map', 'command_candidates'):
        matches = [x for x in index['artifacts'] if c.same_ref(x, plan[key])]
        w.require(len(matches) == 1, 'map/commands not independently reviewed')
        c.read_ref(matches[0])
