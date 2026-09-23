#!/usr/bin/env python3
"""Bounded N3 first-three checkpoint reader. No dispatch or algorithm calls."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import torch

SCHEMA = 'n3-first3-native-review-v1'
CHECKS = ('finite_action', 'source_compute', 'raw_stage_separation', 'substantive_qd_activation',
          'exact_native_past_feedback_timing_selection', 'native_feedback_bundle_alignment',
          'runtime_tracking_validity', 'substantive_feedback_search_activity')
ROLES = {'canonical_initial', 'canonical_offspring', 'canonical_population'}
PROFILES = ('C0', 'Q0', 'N3')
METADATA_GATE_FILES = ('scripts/qd_ed_n3_report.py', 'scripts/qd_ed_n3_plan.py')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def parse(text):
    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    return json.loads(text, object_pairs_hook=pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def read(reference, hashes, *, lines=False):
    given = Path(reference['path'])
    require(not given.is_symlink(), 'input symlink forbidden')
    path = given.resolve()
    require(sha(path) == reference['sha256'], 'input SHA mismatch: ' + str(path))
    hashes[str(path)] = reference['sha256']
    text = path.read_text()
    return [parse(line) for line in text.splitlines() if line.strip()] if lines else parse(text)


def native_id(value):
    require(torch.is_tensor(value) and value.device.type == 'cpu' and torch.isfinite(value).all(), 'nonfinite/non-CPU native input')
    value = value.contiguous()
    return hashlib.sha256(f'{value.dtype}:{tuple(value.shape)}:'.encode()
                          + value.reshape(-1).view(torch.uint8).numpy().tobytes()).hexdigest()


def same(left, right):
    return torch.is_tensor(left) and torch.is_tensor(right) and left.shape == right.shape and left.dtype == right.dtype and native_id(left) == native_id(right)


def groups(values):
    order = sorted(range(len(values)), key=lambda i: (-values[i].item(), i))
    result = []
    for index in order:
        if not result or values[index].item() != values[result[-1][0]].item():
            result.append([])
        result[-1].append(index)
    return result


def compare_order(samples, raw, quality):
    require(samples.ndim == 3 and raw.shape == quality.shape == (len(samples),)
            and raw.dtype == quality.dtype, 'native quality population mismatch')
    ids = [native_id(row) for row in samples]
    native_id(raw); native_id(quality)
    transitions = Counter({f'{a}:{b}': 0 for a in (-1, 0, 1) for b in (-1, 0, 1)})
    different = Counter()
    duplicate_pairs = 0
    for i in range(len(samples)):
        for j in range(i + 1, len(samples)):
            before = int(bool(raw[i] > raw[j])) - int(bool(raw[i] < raw[j]))
            after = int(bool(quality[i] > quality[j])) - int(bool(quality[i] < quality[j]))
            transitions[f'{before}:{after}'] += 1
            if ids[i] == ids[j]:
                duplicate_pairs += 1
            elif before != after:
                different['strict_reversal' if before * after == -1 else 'tie_split' if before == 0 else 'tie_merge'] += 1
    return {'native_action_ids': ids, 'sample_dtype': str(samples.dtype), 'quality_dtype': str(raw.dtype),
            'raw': raw.tolist(), 'internal': quality.tolist(), 'raw_rank_groups': groups(raw),
            'internal_rank_groups': groups(quality), 'all_pair_transitions': dict(transitions),
            'duplicate_native_pairs': duplicate_pairs, 'distinct_native_order_changes': dict(different),
            'consumed_ordering_witness': sum(different.values()) > 0}


def remember(table, samples, raw, quality):
    for sample, original, internal in zip(samples, raw, quality):
        key = native_id(sample)
        pair = (original.item(), internal.item())
        require(key not in table or table[key] == pair, 'conflicting native action/raw/internal association')
        table[key] = pair


def final_pool(final, known, metric):
    population, raw = final['population'], final['raw_provider_quality']
    require(population.ndim == 3 and raw.shape == (len(population),) and raw.dtype == torch.float32,
            'final archive native-value/FP32 storage contract differs')
    ids = [native_id(row) for row in population]
    pairs = []
    for index, key in enumerate(ids):
        require(key in known and raw[index].item() == known[key][0], 'final native raw association missing')
        pairs.append(known[key])
    selected = final['selected_index']
    require(type(selected) is int and 0 <= selected < len(ids)
            and same(final['selected_latent'], population[selected:selected + 1]), 'selected native pool identity mismatch')
    qualities = [pair[1] for pair in pairs]
    raw_values = raw.tolist()
    raw_best, internal_best = max(raw_values), max(qualities)
    raw_max = [i for i, value in enumerate(raw_values) if value == raw_best]
    internal_max = [i for i, value in enumerate(qualities) if value == internal_best]
    require(selected in internal_max and final['selected_quality'] == qualities[selected]
            and final['selected_raw_provider_quality'] == raw_values[selected], 'recorded final selection quality mismatch')
    gap = raw_values[selected] - raw_best
    require(metric['qd_selected_raw_gap'] == gap and metric['qd_selected_raw_reward'] == raw_values[selected]
            and metric['qd_final_best_raw_reward'] == raw_best, 'metric final pool raw gap mismatch')
    return {'native_action_ids': ids, 'raw_container_dtype': str(raw.dtype), 'raw': raw_values,
            'internal_native_values_in_fp32_container': qualities, 'selected_index': selected,
            'selected_native_id': ids[selected], 'raw_max_indices': raw_max,
            'raw_max_native_ids': sorted({ids[i] for i in raw_max}), 'internal_max_indices': internal_max,
            'internal_max_native_ids': sorted({ids[i] for i in internal_max}), 'selected_raw_gap': gap,
            'strict_final_pool_witness': gap < 0 and ids[selected] not in {ids[i] for i in raw_max}}


def analyze_active(rows, metric):
    by_kind = defaultdict(list)
    for row in rows: by_kind[row['event']].append(row)
    canonical = by_kind['canonical_candidate_batch']
    require([row['values']['iter_idx'] for row in canonical] == list(range(-1, 10)), 'canonical iteration coverage differs')
    score_rows = [row for row in by_kind['scoring_inputs'] if row['values']['scoring_scope']['role'] in ROLES]
    scoring = {row['values']['scoring_scope']['iter_idx']: row for row in score_rows}
    require(len(score_rows) == len(scoring) == 11 and set(scoring) == set(range(-1, 10)), 'canonical scoring coverage differs')
    allocations = {row['values']['iter_idx']: row for row in by_kind['archive_parent_allocation']}
    parents = {row['values']['iter_idx']: row for row in by_kind['parent_allocation']}
    require(len(by_kind['archive_parent_allocation']) == len(by_kind['parent_allocation'])
            == len(allocations) == len(parents) == 10 and set(allocations) == set(parents) == set(range(10)), 'ten actual parent rounds required')
    known, batches, parent_rows = {}, [], []
    for row in canonical:
        values = row['values']; iteration = values['iter_idx']; source = scoring[iteration]
        samples, raw, quality = values['candidates'], values['raw_provider_quality'], values['effective_quality']
        require(samples.shape == (16, 64, 128) and raw.dtype == quality.dtype == samples.dtype
                and same(samples, source['values']['samples']) and values['quality_mode'] == 'executed_feedback_v1',
                'canonical native scoring association mismatch')
        effective = [r for r in by_kind['effective_quality'] if r['values']['scoring_batch_id'] == source['sequence']]
        aggregates = [r for r in by_kind['scoring_aggregate'] if r['values']['scoring_batch_id'] == source['sequence']]
        require(len(effective) == len(aggregates) == 1 and same(raw, aggregates[0]['values']['aggregate_before_reward_mode'])
                and same(raw, effective[0]['values']['raw_provider_quality']) and same(quality, effective[0]['values']['quality']),
                'canonical native raw/internal vector mismatch')
        require(source['sequence'] < aggregates[0]['sequence'] < effective[0]['sequence'] < row['sequence'],
                'canonical scoring/aggregate/effective causal order differs')
        if iteration >= 0:
            parent, allocation = parents[iteration], allocations[iteration]
            pv, av = parent['values'], allocation['values']
            require(all(prior['sequence'] < allocation['sequence'] < parent['sequence'] < source['sequence'] for prior in canonical if prior['values']['iter_idx'] < iteration),
                    'parent/scoring causal order differs')
            require(pv['source_population'].shape == (16, 64, 128) and pv['parent_indices'].shape == (16,)
                    and len(av['parent_fingerprints']) == 16 and av['parent_raw_rewards'].shape == av['parent_rewards'].shape == (16,),
                    'actual parent sixteen-slot contract differs')
            require(torch.isfinite(pv['parent_indices']).all() and pv['parent_indices'].dtype == torch.int64
                    and bool(((pv['parent_indices'] >= 0) & (pv['parent_indices'] < 16)).all()), 'actual parent index invalid')
            require(same(pv['source_quality'], av['parent_rewards']) and same(pv['source_costs'], av['parent_costs']), 'archive/ED parent quality association differs')
            parent_ids = [native_id(p) for p in pv['source_population']]
            for index, key in enumerate(parent_ids):
                require(key in known and known[key] == (av['parent_raw_rewards'][index].item(), av['parent_rewards'][index].item()),
                        'parent must have an earlier native raw/internal association')
            parent_rows.append({'iter_idx': iteration, 'source_native_ids': parent_ids,
                                'parent_indices': pv['parent_indices'].tolist(), 'slots': 16})
        comparison = compare_order(samples, raw, quality)
        batches.append({'iter_idx': iteration, 'event_sequence': row['sequence'], **comparison})
        remember(known, samples, raw, quality)
    require(len(by_kind['final_selection']) == 1, 'final selection missing/duplicate')
    require(all(row['sequence'] < by_kind['final_selection'][0]['sequence'] for row in canonical), 'final selection causal order differs')
    final = final_pool(by_kind['final_selection'][0]['values'], known, metric)
    return {'global_step': metric['global_step'], 'canonical_batches': batches, 'parent_rounds': parent_rows,
            'canonical_evaluations': 176, 'canonical_score_batches': 11, 'final_pool': final,
            'consumed_ordering_witness': any(b['consumed_ordering_witness'] for b in batches),
            'strict_final_pool_witness': final['strict_final_pool_witness']}


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def admit(manifest, authorization, freeze, hashes):
    require(os.environ.get('CUDA_VISIBLE_DEVICES') == '' and not torch.cuda.is_initialized(), 'CPU-only mask required')
    require(authorization['schema'] == 'n3-first3-read-authorization-v1' and authorization['status'] == 'authorized', 'read not authorized')
    require(manifest['schema'] == 'n3-first3-review-inputs-v1', 'input schema differs')
    matrix = read(manifest['matrix_report'], hashes)
    report_input = read(manifest['matrix_report_input'], hashes)
    require(matrix['schema'] == 'qd-ed-n3-matrix-report-v1' and matrix['cohort_id'] == 'N3_EXECUTED_FEEDBACK_DEV_20260923'
            and matrix['input_manifest_sha256'] == manifest['matrix_report_input']['sha256']
            and matrix['input_manifest'] == report_input, 'matrix report input binding differs')
    require(authorization['reviewed_matrix_report'] == manifest['matrix_report'], 'matrix report authority missing')
    require(len(manifest['cells']) == 3 and [row['profile'] for row in manifest['cells']] == list(PROFILES), 'exact ordered first three required')
    require(matrix['first_three']['all_complete_valid'] is True, 'first three incomplete')
    base = read(report_input['base_plan'], hashes)
    plans = {report_input['base_plan']['sha256']: base}
    for reference in report_input.get('plan_revisions', []): plans[reference['sha256']] = read(reference, hashes)
    source_root = Path(manifest['source_root']).resolve()
    require(base['worktree'] == str(source_root) and base['source_commit'] == manifest['source_commit'], 'source root/commit differs')
    require(subprocess.check_output(['git', '-C', str(source_root), 'rev-parse', 'HEAD'], text=True).strip() == manifest['source_commit'], 'live source HEAD differs')
    inventory = {row['path']: row['sha256'] for row in base['code_files']}
    require(len(inventory) == len(base['code_files']), 'duplicate source inventory path')
    metadata_sources = authorization.get('reviewed_metadata_gate_sources', {})
    require(set(metadata_sources) == set(METADATA_GATE_FILES), 'reviewed metadata source closure missing')
    require(not set(metadata_sources).intersection(freeze['reviewed_source_sha256']), 'source review namespaces overlap')
    for relative, expected in {**freeze['reviewed_source_sha256'], **metadata_sources}.items():
        require(inventory.get(relative) == expected and sha(source_root / relative) == expected, 'source review/inventory/live mismatch: ' + relative)
        committed = subprocess.check_output(['git', '-C', str(source_root), 'show', manifest['source_commit'] + ':' + relative])
        require(hashlib.sha256(committed).hexdigest() == expected, 'source git object differs')
        hashes[str(source_root / relative)] = expected
    sys.path.insert(0, str(source_root / 'scripts'))
    # Explicitly load the verified transitive local dependency; do not reuse a
    # preloaded module of the same name from another worktree. Its builder path is
    # never called; these two reviewed metadata helpers import stdlib only.
    load_module('qd_ed_n3_plan', source_root / 'scripts/qd_ed_n3_plan.py')
    report = load_module('qd_ed_n3_report', source_root / 'scripts/qd_ed_n3_report.py')
    original = report.plan_contract(base)
    for plan in plans.values():
        require(report.plan_contract(plan) == original and plan['code_files'] == base['code_files']
                and all(plan[k] == base[k] for k in report.BINDING), 'plan revision changes source/scientific identity')
    accepted = []
    for index, supplied in enumerate(manifest['cells']):
        cell = matrix['cells'][index]
        require(cell['identity']['task_id'] == 0 and cell['identity']['profile'] == supplied['profile']
                and cell['status'] == 'complete_valid' and cell['valid_attempt_id'] == supplied['attempt_id'], 'authoritative representative differs')
        representative = [a for a in cell['attempts'] if a['status'] == 'complete_valid']
        require(len(representative) == 1 and representative[0]['references'] == supplied['references'], 'representative references differ')
        refs = supplied['references']
        require(set(refs) == {'terminal', 'audit', 'compute', 'metrics'}, 'complete accepted references required')
        terminal = read(refs['terminal'], hashes); audit = read(refs['audit'], hashes)
        require(terminal['attempt_id'] == supplied['attempt_id'] and terminal['event'] == 'valid'
                and terminal['outcome_valid'] is True and audit.get('accepted') is True
                and audit.get('evidence_complete') is True and audit.get('errors') == [], 'terminal/audit not accepted')
        metrics = read(refs['metrics'], hashes, lines=True); compute = read(refs['compute'], hashes, lines=True)
        verified = report.load_attempt(refs, plans)
        require(verified['status'] == 'complete_valid' and verified['metrics'] == cell['metrics'], 'metadata report consistency differs')
        accepted.append({'profile': supplied['profile'], 'attempt_id': supplied['attempt_id'], 'terminal': terminal,
                         'audit': audit, 'metrics': metrics, 'compute': compute[0], 'verified': verified['metrics']})
    episode = manifest['n3_episode']; n3 = accepted[2]
    root = Path(n3['audit']['episode_dir']).resolve()
    require(str(root) == episode['episode_dir'] and root == Path(n3['terminal']['output_dir']).resolve()/'eds_eval/decision_evidence/episode_000', 'N3 episode path differs')
    require(Path(episode['status']['path']).resolve() == root/'status.json'
            and Path(episode['index']['path']).resolve() == root/'events.jsonl', 'N3 episode metadata paths differ')
    status = read(episode['status'], hashes); refs = read(episode['index'], hashes, lines=True)
    require(authorization['n3_audit_snapshot'] == {'audit': manifest['cells'][2]['references']['audit'],
            'status': episode['status'], 'index': episode['index'],
            'auditor_sha256': inventory['scripts/audit_decision_evidence.py'],
            'binding': 'root_verified_unchanged_after_complete_frozen_audit'}, 'fresh accepted snapshot binding absent')
    require(status['complete'] is True and status['failed'] is False and status['pending_action'] is False
            and status['episode'] == 0 and status['bundles'] == len(refs)
            and n3['compute']['decision_evidence']['bundles'] == len(refs), 'N3 complete status/index differs')
    expected = {f'bundle_{i:06d}.pt' for i in range(1, len(refs) + 1)}
    require({p.name for p in root.glob('bundle_*.pt')} == expected, 'unindexed/missing bundle')
    for i, reference in enumerate(refs, 1):
        require(reference['bundle'] == f'bundle_{i:06d}.pt', 'bundle order/path differs')
        path = root/reference['bundle']
        require(not path.is_symlink() and sha(path) == reference['sha256'], 'bundle hash mismatch before decoding')
        hashes[str(path)] = reference['sha256']
    # The reviewed metadata gate has checked the exact native-audit schema/counts;
    # all-unsupported N3 legitimately has no specialized audit and cannot pass.
    auditor = load_module('n3_checkpoint_frozen_auditor', source_root/'scripts/audit_decision_evidence.py')
    return accepted, auditor, root, status


def review(accepted, events):
    n3 = accepted[2]; contexts = [r for r in events if r['event'] == 'decision_context']
    require(len({r['global_step'] for r in contexts}) == len(contexts), 'duplicate decision step')
    by_step = {r['global_step']: r for r in contexts}
    rows_by_decision = defaultdict(list)
    for row in events: rows_by_decision[row['decision_id']].append(row)
    results = []
    for metric in n3['metrics']:
        step = metric['global_step']; require(step in by_step, 'metric decision missing')
        rows = rows_by_decision[by_step[step]['decision_id']]
        feedback = [r['values'] for r in rows if r['event'] == 'execution_feedback_selection']
        applicable, active = metric['qd_quality_applicable'], metric['qd_feedback_active']
        if applicable:
            require(len(feedback) == 1 and feedback[0]['active'] == active
                    and feedback[0]['context'] == metric['qd_feedback_context']
                    and feedback[0]['previous'] == metric['qd_feedback_previous']
                    and feedback[0]['selected'] == metric['qd_feedback_selected'], 'metric/feedback native evidence differs')
        else:
            require(not feedback and not active, 'unsupported decision claims feedback')
        row = {'global_step': step, 'applicable': applicable, 'active': active,
               'reason': metric['qd_feedback_reason'], 'stage': by_step[step]['values']['stage']}
        if active:
            require(metric['qd_archive_active_for_chunk'] is True and metric['qd_evaluation_count'] == 176,
                    'active feedback not in frozen QD search')
            row['analysis'] = analyze_active(rows, metric)
        results.append(row)
    active_rows = [r for r in results if r['active']]
    ordering = sum(r['analysis']['consumed_ordering_witness'] for r in active_rows)
    final = sum(r['analysis']['strict_final_pool_witness'] for r in active_rows)
    checks = {name: True for name in CHECKS}
    for name in ('substantive_qd_activation', 'exact_native_past_feedback_timing_selection',
                 'runtime_tracking_validity'):
        checks[name] = bool(active_rows)
    checks['native_feedback_bundle_alignment'] = any(r['applicable'] for r in results)
    checks['substantive_feedback_search_activity'] = ordering > 0 or final > 0
    return {'schema': SCHEMA, 'checks': checks, 'all_checks_pass': all(checks.values()),
            'release_authorized': False, 'original_outcomes': [{'profile': a['profile'], 'attempt_id': a['attempt_id'],
                'condition_valid': True, 'success': a['terminal']['success'],
                'gpu_process_wall_seconds': a['terminal']['gpu_process_wall_seconds']} for a in accepted],
            'metadata_evidence': {a['profile']: a['verified'] for a in accepted}, 'n3_all_guided_decisions': results,
            'activity_counts': {'recognized': sum(r['applicable'] for r in results), 'active': len(active_rows),
                                'ordering_witness_decisions': ordering, 'strict_final_witness_decisions': final},
            'limits': ['Actual normalized Stage arguments are not separately logged: Unknown; raw selection plus frozen source/CPU gates establish separation.',
                       'Canonical ordering witnesses prove different consumed ordering, not changed archive insertion, parent or future proposals.',
                       'Same-final-pool comparison does not reconstruct another search.',
                       'No task benefit, physical cause, target/contact/grasp or unexecuted outcome inference; all chunks are dependent.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--authorization', type=Path, required=True)
    parser.add_argument('--authorization-sha256', required=True)
    parser.add_argument('--freeze', type=Path, default=Path(__file__).with_name('freeze-v1.json'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--execute-reviewed', action='store_true')
    args = parser.parse_args()
    require(args.execute_reviewed, 'explicit reviewed execution flag required')
    hashes = {}
    auth = read({'path': str(args.authorization), 'sha256': args.authorization_sha256}, hashes)
    freeze = read(auth['freeze'], hashes)
    require(Path(auth['freeze']['path']).resolve() == args.freeze.resolve(), 'freeze path mismatch')
    for filename, expected in freeze['files'].items():
        path = args.freeze.parent/filename
        require(sha(path) == expected, 'frozen tool/protocol/test bytes differ')
        hashes[str(path.resolve())] = expected
    require(freeze['files']['review_first3.py'] == sha(__file__), 'reader self hash differs')
    require(auth['manifest'] == {'path': str(args.manifest.resolve()), 'sha256': sha(args.manifest)}, 'manifest authorization mismatch')
    require(auth['output'] == str(args.output.resolve()) and not args.output.exists(), 'new authorized output required')
    manifest = read(auth['manifest'], hashes)
    accepted, auditor, root, status = admit(manifest, auth, freeze, hashes)
    require(all(not args.output.resolve().is_relative_to(Path(a['terminal']['output_dir']).resolve()) for a in accepted), 'output inside episode forbidden')
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output/'status.json').write_text(json.dumps({'complete': False, 'phase': 'admitted'})+'\n')
    try:
        events = auditor.load_events(root, status)  # Integrity loader only: no second scientific audit.
        result = review(accepted, events)
        require(not torch.cuda.is_initialized(), 'CUDA initialized unexpectedly')
        for path, expected in hashes.items(): require(sha(path) == expected, 'input changed during review')
        with (args.output/'review.json').open('x') as stream: json.dump(result, stream, indent=2, allow_nan=False)
        with (args.output/'input-source-hashes.json').open('x') as stream: json.dump(hashes, stream, indent=2, sort_keys=True)
        text = f"N3 first-three correctness/activity: {'PASS' if result['all_checks_pass'] else 'NOT ESTABLISHED'}.\n\n"
        text += json.dumps(result['activity_counts'], sort_keys=True) + '\n\nOriginal task outcomes are informational; no release is authorized by this tool.\n'
        text += '\n'.join(result['limits']) + '\n'
        (args.output/'review.md').write_text(text)
        (args.output/'status.json').write_text(json.dumps({'complete': True, 'review_sha256': sha(args.output/'review.json')})+'\n')
        print(json.dumps({'complete': True, 'all_checks_pass': result['all_checks_pass'], 'output': str(args.output)}))
    except Exception as error:
        (args.output/'status.json').write_text(json.dumps({'complete': False, 'error': str(error), 'error_type': type(error).__name__})+'\n')
        raise


if __name__ == '__main__':
    main()
