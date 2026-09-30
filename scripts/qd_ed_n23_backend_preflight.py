#!/usr/bin/env python3
"""Closed, one-attempt N23 backend preflight; no model/provider/simulator calls.

Draft builders do not dispatch or reserve anything. Only a later root-owned
release plus a runner-created recovery-attempt context can execute this worker.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import torch
from scripts import audit_decision_evidence as audit
from scripts import qd_ed_n23_worker as worker
from scripts.qd_ed_audit_backend import create_backend
from core.qd_actuator_clipped_quality import actuator_clipped_quality

PROTOCOL_SHA = 'ada387aa1320f76239a7d4db43e8e4d9c1734ed735667113bcd6b6abcf543dfe'
LIMITS = {'attempts': 1, 'timeout_seconds': 120, 'cleanup_seconds': 40,
          'budget_bucket': 'recovery', 'physical_gpu': 7, 'gpu_hours_reserved': 160 / 3600}
EXTRA_SOURCE = {'scripts/qd_ed_n23_backend_preflight.py', 'scripts/qd_ed_n23_backend_prepare.py', 'tests/test_qd_ed_n23_backend.py',
                'core/qd_executed_quality.py', 'core/eds_eval_metrics.py',
                'tests/test_qd_actuator_clipped_quality.py', 'tests/test_rdt_steer.py',
                'tests/test_decision_evidence_audit.py', 'tests/test_qd_ed_final_runner.py',
                'experiments/iteration_023_actuator_clipped_quality/protocol-cpu-v1.md',
                'experiments/iteration_023_actuator_clipped_quality/backend-runtime-contract-v1.md',
                'experiments/iteration_023_actuator_clipped_quality/backend-arithmetic-protocol-v1.md'}


def corpus_from_index(reference):
    index = worker.read_ref(reference)
    rows = [r for r in index['paths'] if r['label'] == 'n21_task0']
    worker.require(len(rows) == 1, 'preflight requires exactly the exposed N21 task0 corpus')
    row = rows[0]
    worker.require(row['attempt_id'] == 'rdt-qd-ed-final-20260921T093925Z__n21_dev_t00_n21_20260930__a4957aa45fc2'
                   and row['source_success'] is False and len(row['verified_bundles']) == 2250,
                   'preflight original completed GPU7 N21 corpus differs')
    return {'schema': 'n23-n21-exposed-corpus-v1', 'index': reference, 'attempt_id': row['attempt_id'],
            'native_audit_sha256': row['native_audit_sha256'], 'bundles': row['verified_bundles'],
            'expected_batches': 176, 'expected_candidates': 2816}


def build_plan(*, root, protocol, runtime, corpus_index, source_paths, artifact_root, predecessor_review=None):
    """Pure non-executable draft; no GPU, runtime, ledger or release mutation."""
    root = Path(root).resolve(); protocol = Path(protocol).resolve()
    worker.require(worker.sha(protocol) == PROTOCOL_SHA, 'preflight frozen protocol changed')
    source = worker.source_record(root, set(source_paths) | worker.REQUIRED_SOURCE | EXTRA_SOURCE)
    runtime_data = worker.read_ref(runtime)
    worker.require(worker.cuda_binding(runtime_data)['physical_gpu'] == 7, 'preflight requires frozen GPU7 runtime')
    return {'schema': 'n23-backend-preflight-plan-v1', 'worktree': str(root), 'limits': LIMITS,
            'artifact_root': str(Path(artifact_root).resolve()),
            'protocol': {'path': str(protocol), 'sha256': PROTOCOL_SHA}, 'runtime': runtime,
            'source': source, 'corpus': corpus_from_index(corpus_index),
            'predecessor_review': predecessor_review, 'synthetic_cases': 'fp32_bf16_native_seven_point_v1',
            'task_outcome': False, 'requires_separate_release': True}


def predecessor_gate(reference):
    review = worker.read_ref(reference)
    worker.require(set(review) == {'schema', 'source_plan', 'source_status', 'phase', 'disposition', 'allow_n23', 'rationale'}
                   and review['schema'] == 'n23-n22-prerequisite-v1'
                   and review['disposition'] == 'rejected' and review['allow_n23'] is True
                   and review['phase'] in {'dev', 'validation'}
                   and isinstance(review['rationale'], str) and review['rationale'].strip(),
                   'preflight requires explicit N22 aggregate rejection; invalid transition not authorized')
    prior_plan = worker.read_ref(review['source_plan'])
    worker.require(prior_plan.get('n22_cohort', {}).get('cohort_id') == 'N22_HOLD_LIFT_DEV_20260930',
                   'preflight predecessor plan differs')
    status = worker.read_ref(review['source_status'])
    if review['phase'] == 'dev':
        worker.require(status.get('status') in {'rejected_numeric_futility', 'completed_all_forty_audited'}
                       and status.get('dev_gate_promoted') is False, 'preflight N22 Dev is not aggregate rejected')
    else:
        worker.require(set(status) == {'schema', 'cohort_id', 'aggregate_only', 'terminal', 'gate_passed', 'outcome_valid', 'dev_promoted'}
                       and status['schema'] == 'n22-validation-aggregate-disposition-v1'
                       and status['cohort_id'] == prior_plan['n22_cohort']['cohort_id']
                       and status['aggregate_only'] is True and status['terminal'] is True
                       and status['dev_promoted'] is True and status['gate_passed'] is False
                       and status['outcome_valid'] is True, 'preflight validation aggregate rejection missing')
    return review


def validate_plan(plan):
    worker.require(set(plan) == {'schema', 'worktree', 'artifact_root', 'limits', 'protocol', 'runtime', 'source', 'corpus',
                                'predecessor_review', 'synthetic_cases', 'task_outcome', 'requires_separate_release'}
                   and plan['schema'] == 'n23-backend-preflight-plan-v1' and plan['limits'] == LIMITS
                   and plan['worktree'] == str(ROOT.resolve()) and plan['task_outcome'] is False
                   and plan['requires_separate_release'] is True
                   and plan['synthetic_cases'] == 'fp32_bf16_native_seven_point_v1', 'preflight finite scope differs')
    worker.require(plan['protocol']['sha256'] == PROTOCOL_SHA and worker.sha(plan['protocol']['path']) == PROTOCOL_SHA,
                   'preflight protocol source changed')
    worker.verify_source(ROOT, plan['source'])
    worker.require(EXTRA_SOURCE <= {r['path'] for r in plan['source']['files']}, 'preflight required source absent')
    worker.require(plan['corpus'] == corpus_from_index(plan['corpus']['index']), 'preflight corpus changed')
    predecessor_gate(plan['predecessor_review'])
    return worker.read_ref(plan['runtime'])


def verify_corpus_files(corpus):
    """CPU hashing only; used by the receipt consumer without CUDA replay."""
    for ref in corpus['bundles']:
        path = Path(ref['path'])
        worker.require(path.is_file() and not path.is_symlink() and worker.sha(path) == ref['sha256'],
                       'preflight input corpus bytes changed')


def iter_batches(corpus):
    origins, scores, contexts = {}, {}, {}
    for ref in corpus['bundles']:
        path = Path(ref['path'])
        worker.require(path.is_file() and not path.is_symlink() and worker.sha(path) == ref['sha256'], 'preflight corpus bundle hash differs')
        for event in torch.load(path, map_location='cpu', weights_only=True)['events']:
            v = event['values']
            if event['event'] == 'projection_origin': origins[event['sequence']] = v['source_eef_position']
            elif event['event'] == 'decision_context': contexts[event['decision_id']] = v
            elif event['event'] == 'scoring_inputs' and v['scoring_scope']['role'] in {'canonical_initial', 'canonical_offspring'}:
                scores[event['sequence']] = v
            elif event['event'] == 'scoring_aggregate' and v['scoring_batch_id'] in scores:
                scoring = scores.pop(v['scoring_batch_id'])
                yield {'decision_id': event['decision_id'], 'score_sequence': v['scoring_batch_id'],
                       'samples': scoring['samples'], 'projected_xyz': scoring['projected_xyz'],
                       'keypoints': scoring['keypoints'], 'raw': v['aggregate_before_reward_mode'],
                       'origins': [origins[s] for s in scoring['projection_origin_sequences']]}
    worker.require(not scores, 'preflight unfinished scoring input')


def check_batch(batch, backend):
    actions, xyz, keypoints, raw = (backend.native(batch[k]) for k in ('samples', 'projected_xyz', 'keypoints', 'raw'))
    origins = batch['origins']
    row = {'decision_id': batch['decision_id'], 'score_sequence': batch['score_sequence'],
           'dtype': str(actions.dtype), 'candidates': len(raw), 'mismatches': [],
           'production_helper_passed': False, 'independent_passed': False}
    # Record every mismatching candidate for both raw boundaries, without a tolerance.
    weights = torch.tensor([1., 1., 1., 1., 3., 3., 3.], device=actions.device)
    weights = weights / weights.sum()
    for i in range(len(raw)):
        origin = origins[i].to(device=actions.device, dtype=actions.dtype)
        projected = origin + torch.cumsum(actions[i, :8, 39:42] * .01, dim=0)
        if not torch.equal(projected, xyz[i, 1:]):
            row['mismatches'].append({'candidate': i, 'check': 'raw_projection',
                'max_abs_m': float((projected.float() - xyz[i, 1:].float()).abs().max().item())})
        d = torch.norm(xyz[i:i + 1, 1:8] - keypoints[0], dim=-1)
        reward = (-(d ** 2 * weights).sum(dim=1)).mean().to(raw.dtype)
        if not torch.equal(reward, raw[i]):
            row['mismatches'].append({'candidate': i, 'check': 'raw_score', 'reconstructed': reward.item(), 'stored': raw[i].item()})
    try:
        produced, changed = actuator_clipped_quality(actions[:, :8, [39, 40, 41]], origins, xyz, keypoints, raw)
        row['production_helper_passed'] = True
    except Exception as exc:
        row['mismatches'].append({'check': 'production_helper', 'error': type(exc).__name__ + ':' + str(exc)})
        produced = None
    try:
        expected, mask = audit.reconstruct_n23_arithmetic(actions, xyz, keypoints, raw, origins)
        row['independent_passed'] = True
        if produced is not None and (audit._native_sha(produced) != audit._native_sha(expected) or not torch.equal(changed, mask)):
            row['mismatches'].append({'check': 'clipped_quality_or_mask'})
        if produced is not None:
            unchanged = ~mask
            if audit._native_sha(produced[unchanged]) != audit._native_sha(raw[unchanged]):
                row['mismatches'].append({'check': 'unchanged_row_bits'})
            wrong = expected.clone()
            wrong[0] = torch.nextafter(wrong[0], torch.full_like(wrong[0], float('inf')))
            try:
                audit.verify_n23_quality(expected, mask, {'quality': wrong.cpu(), 'clipped_prefix_mask': mask.cpu()})
                row['wrong_score_rejected'] = False
            except audit.AuditFailure as exc:
                row['wrong_score_rejected'] = str(exc) == 'n23_native_clipped_quality'
            row['clipped_candidates'] = int(mask.sum().item())
    except Exception as exc:
        row['mismatches'].append({'check': 'independent_arithmetic', 'error': type(exc).__name__ + ':' + str(exc)})
    row['accepted'] = not row['mismatches'] and row.get('wrong_score_rejected') is True
    return row


def synthetic_batches(backend):
    for dtype in (torch.float32, torch.bfloat16):
        actions = torch.zeros(4, 64, 128, dtype=dtype, device=backend.device)
        actions[0, :8, 39:42] = torch.tensor([[2.2, -.2, -3.3], [-2.2, .4, 1.3], [.9, -.8, .7], [0, 0, 0],
                                             [.7, 2.8, 0], [-.8, -2.1, .2], [0, 0, -.2], [9, 9, 9]], device=backend.device, dtype=dtype)
        actions[1, :7, 39:42] = torch.tensor([.1, -.2, .3], device=backend.device, dtype=dtype)
        actions[1, 7, 39:42] = torch.tensor([100., -100., 100.], device=backend.device, dtype=dtype)
        actions[2, :8, 39:42] = torch.tensor([1., -1., 0.], device=backend.device, dtype=dtype)
        origin = torch.tensor([.12317, -.17312, .23141], dtype=torch.float64)
        # Exactly the unchanged adapter's guided seven-channel slice/layout.
        guided = actions[:, :8, [39, 40, 41, 42, 43, 44, 10]]
        xyz = torch.stack([torch.cat((origin.to(device=backend.device, dtype=dtype)[None],
                            origin.to(device=backend.device, dtype=dtype) + torch.cumsum(a[:, :3] * .01, dim=0))) for a in guided])
        keypoints = torch.tensor([[.1124, -.071, .3154]], device=backend.device, dtype=dtype)
        weights = torch.tensor([1., 1., 1., 1., 3., 3., 3.], device=backend.device)
        weights = weights / weights.sum()
        raw = torch.stack([(-(torch.norm(p[None, 1:8] - keypoints[0], dim=-1) ** 2 * weights).sum(1)).mean().to(dtype) for p in xyz])
        yield {'decision_id': 'synthetic_' + str(dtype), 'score_sequence': -1, 'samples': actions,
               'projected_xyz': xyz, 'keypoints': keypoints, 'raw': raw, 'origins': [origin] * 4}


def wrong_bounds_rejected():
    # Deliberate malformed static bound reaches the independent bound check
    # before provenance fields; this is not a claim about an actual controller.
    sem = {'controller_type': 'robosuite.controllers.osc.OperationalSpaceController', 'name': 'OSC_POSE',
           'use_delta': True, 'use_ori': True, 'control_dim': 6, 'impedance_mode': 'fixed'}
    for name, value in (('input_min', -1.), ('input_max', 1.), ('output_min', -.05), ('output_max', .05)):
        sem[name] = [value] * 6; sem[name + '_dtype'] = 'float64'
    sem['input_max'][0] = .5
    try:
        audit._audit_n23_metadata({'semantics': sem})
    except audit.AuditFailure as exc:
        return str(exc) == 'n23_controller_bounds'
    return False


def run_preflight(plan_path, release_path, attempt_context_path):
    started = time.perf_counter()
    plan_ref = {'path': str(Path(plan_path).resolve()), 'sha256': worker.sha(plan_path)}
    plan = worker.read_ref(plan_ref)
    runtime = validate_plan(plan)
    release = json.loads(Path(release_path).read_text())
    context = json.loads(Path(attempt_context_path).read_text())
    worker.require(set(context) == {'schema', 'attempt_id', 'output_dir', 'budget_bucket', 'plan', 'timeout_seconds', 'cleanup_seconds'}
                   and context['schema'] == 'n23-recovery-attempt-context-v1' and context['budget_bucket'] == 'recovery'
                   and context['plan'] == plan_ref and context['timeout_seconds'] == 120 and context['cleanup_seconds'] == 40,
                   'preflight requires separately charged recovery attempt context')
    worker.require(release == {'schema': 'n23-backend-preflight-release-v1', 'plan': plan_ref,
                               'source': plan['source'], 'runtime': plan['runtime'], 'limits': LIMITS,
                               'attempt_id': context['attempt_id'], 'predecessor_review': plan['predecessor_review']},
                   'preflight release differs from finite plan')
    output = Path(context['output_dir']).resolve()
    worker.require(output.name == context['attempt_id']
                   and output == Path(plan['artifact_root']).resolve() / 'attempts' / context['attempt_id'],
                   'preflight attempt/output identity differs')
    report_path = output / 'n23-backend-preflight-report.json'
    worker.require(not report_path.exists(), 'preflight cannot retry or overwrite output')
    identity = worker.process_identity()
    worker.atomic_json(output / 'n23-backend-preflight-start.json', {
        'schema': 'n23-backend-preflight-start-v1', 'process': identity, 'plan': plan_ref,
        'attempt_id': context['attempt_id'], 'source': plan['source']})
    report = {'schema': 'n23-backend-preflight-proof-v1', 'accepted': False, 'task_outcome': False,
              'plan': plan_ref, 'release': {'path': str(Path(release_path).resolve()), 'sha256': worker.sha(release_path)},
              'attempt_context': {'path': str(Path(attempt_context_path).resolve()), 'sha256': worker.sha(attempt_context_path)},
              'attempt_id': context['attempt_id'], 'process': identity, 'source': plan['source'],
              'runtime': plan['runtime'], 'limits': LIMITS, 'batches': [], 'synthetic': [], 'errors': []}
    try:
        backend = create_backend('cuda', binding=worker.cuda_binding(runtime))
        for batch in iter_batches(plan['corpus']):
            report['batches'].append(check_batch(batch, backend))
        for batch in synthetic_batches(backend):
            report['synthetic'].append(check_batch(batch, backend))
        report['wrong_bounds_rejected'] = wrong_bounds_rejected()
        backend.synchronize()
        report['backend'] = backend.report()
        worker.verify_source(ROOT, plan['source'])
        worker.require(worker.process_identity() == identity, 'preflight process identity changed')
        worker.require(len(report['batches']) == plan['corpus']['expected_batches']
                       and sum(r['candidates'] for r in report['batches']) == plan['corpus']['expected_candidates'],
                       'preflight corpus batch/candidate coverage differs')
        report['accepted'] = (all(r['accepted'] for r in report['batches'] + report['synthetic'])
                              and report['wrong_bounds_rejected'] and len(report['synthetic']) == 2)
    except Exception as exc:
        report['errors'].append(type(exc).__name__ + ':' + str(exc))
    finally:
        report['worker_wall_seconds'] = time.perf_counter() - started
        if report['worker_wall_seconds'] > 120:
            report['accepted'] = False; report['errors'].append('preflight_worker_timeout_bound')
        worker.atomic_json(report_path, report)
    return 0 if report['accepted'] else 2


def verify_preflight_proof(plan_path, report_path, attempt_result, future_source):
    """Hash/JSON-only readiness check; never executes CUDA in a supervisor."""
    plan = json.loads(Path(plan_path).read_text())
    validate_plan(plan)
    report = json.loads(Path(report_path).read_text())
    worker.require(report.get('schema') == 'n23-backend-preflight-proof-v1' and report.get('accepted') is True
                   and report.get('task_outcome') is False and report.get('plan') == {
                       'path': str(Path(plan_path).resolve()), 'sha256': worker.sha(plan_path)}
                   and report.get('source') == plan['source'] == future_source
                   and report.get('runtime') == plan['runtime'] and report.get('limits') == LIMITS,
                   'preflight proof/source/finite scope differs from future Dev')
    worker.require(json.loads((Path(report_path).parent / 'n23-backend-preflight-start.json').read_text()) == {
        'schema': 'n23-backend-preflight-start-v1', 'process': report['process'], 'plan': report['plan'],
        'attempt_id': report['attempt_id'], 'source': report['source']}, 'preflight start/process binding differs')
    worker.read_ref(report['release']); worker.read_ref(report['attempt_context'])
    worker.require(attempt_result.get('budget_bucket') == 'recovery'
                   and attempt_result.get('attempt_id') == report.get('attempt_id')
                   and attempt_result.get('outcome_valid') is True
                   and attempt_result.get('event') == 'valid'
                   and type(attempt_result.get('gpu_process_wall_seconds')) in (int, float)
                   and math.isfinite(attempt_result['gpu_process_wall_seconds'])
                   and 0 <= report['worker_wall_seconds'] <= 120
                   and report['worker_wall_seconds'] <= attempt_result['gpu_process_wall_seconds'] <= 160
                   and attempt_result.get('backend_preflight_report') == {'path': str(Path(report_path).resolve()), 'sha256': worker.sha(report_path)}
                   and attempt_result.get('process') == report['process'], 'preflight metered terminal proof differs')
    verify_corpus_files(plan['corpus'])
    runtime = worker.read_ref(plan['runtime']); backend = report.get('backend', {})
    worker.require(backend.get('kind') == 'cuda' and backend.get('logical_device') == 'cuda:0'
                   and backend.get('physical_uuid') == runtime['gpu_mapping']['uuid']
                   and isinstance(backend.get('torch_version'), str) and bool(backend['torch_version'])
                   and isinstance(backend.get('cuda_version'), str) and bool(backend['cuda_version'])
                   and {'torch.float32', 'torch.bfloat16'} <= set(backend.get('dtype_coverage', []))
                   and len(report['batches']) == 176 and sum(r['candidates'] for r in report['batches']) == 2816
                   and len(report['synthetic']) == 2 and all(r['accepted'] and not r['mismatches'] for r in report['batches'] + report['synthetic'])
                   and report.get('wrong_bounds_rejected') is True, 'preflight CUDA coverage or strict arithmetic proof missing')
    return {'path': str(Path(report_path).resolve()), 'sha256': worker.sha(report_path)}


def command(python, plan_path, release_path, attempt_context_path, *, root=ROOT):
    return [str(python), str(Path(root) / 'scripts/qd_ed_n23_backend_preflight.py'),
            '--plan', str(Path(plan_path).resolve()), '--release', str(Path(release_path).resolve()),
            '--attempt-context', str(Path(attempt_context_path).resolve()),
            '--ownership-main', str(Path(root) / 'main.py')]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--release', type=Path, required=True)
    parser.add_argument('--attempt-context', type=Path, required=True)
    parser.add_argument('--ownership-main', type=Path, required=True)
    args = parser.parse_args()
    worker.require(args.ownership_main.resolve() == ROOT / 'main.py', 'preflight ownership marker differs')
    return run_preflight(args.plan, args.release, args.attempt_context)


if __name__ == '__main__':
    raise SystemExit(main())
